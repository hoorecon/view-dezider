"""Unit tests for the Import-from-URL DETAIL-page pipeline (iter: world-class
URL import) — normalization of the LLM extraction, smart-operator coercion,
and the precise-tier credit multiplier.

Run:
    cd /app/backend && pytest tests/test_url_detail_import.py -v
"""
import pytest

from core.url_detail import normalize_detail, _parse_json_obj
from core.ai_wallet import precise_multiplier, DEFAULTS


# ── Sample LLM output modelled on the NoBroker Kodambakkam listing ──────────
SAMPLE = {
    "page_type": "detail",
    "main_item": {"name": "2 BHK Flat In Metro Flats for Rent In Kodambakkam"},
    "factors": [
        {"name": "Rent", "data_type": "numeric", "operator": "<=", "expected_value": "18000", "unit": "INR"},
        {"name": "Area", "data_type": "numeric", "operator": ">=", "expected_value": "650", "unit": "sqft"},
        {"name": "Deposit", "data_type": "numeric", "operator": "<=", "expected_value": "100000", "unit": "INR"},
        {"name": "Furnishing Status", "data_type": "text", "operator": "equals", "expected_value": "Semi", "unit": None},
        {"name": "Livability Score", "data_type": "numeric", "operator": ">=", "expected_value": "6.2", "unit": None},
        {"name": "Balcony", "data_type": "text", "operator": "equals", "expected_value": "NA", "unit": None},
        {"name": "Floor", "data_type": "text", "operator": "equals", "expected_value": "0/4", "unit": None},
    ],
    "items": [
        {"name": "2 BHK Flat In Metro Flats for Rent In Kodambakkam",
         "values": {"Rent": "18000", "Area": "650", "Deposit": "100000",
                    "Furnishing Status": "Semi", "Livability Score": "6.2",
                    "Balcony": "NA", "Floor": "0/4"},
         "scores": {"Rent": 100, "Area": 100, "Deposit": 100,
                    "Furnishing Status": 100, "Livability Score": 100,
                    "Balcony": 100, "Floor": 100}},
        {"name": "2 BHK Flat In Dhamu House for Rent In 7th Street",
         "values": {"Rent": "18000", "Area": "580"},
         "scores": {"Rent": 100, "Area": 89}},
        {"name": "2 BHK Flat In Golden Jublee Apartment",
         "values": {"Rent": "20000"},
         "scores": {"Rent": 90}},
    ],
}


def test_normalize_detail_happy_path():
    out = normalize_detail(SAMPLE)
    assert out is not None
    assert out["main_name"].startswith("2 BHK Flat In Metro Flats")
    assert len(out["factors"]) == 7
    assert len(out["candidates"]) == 3
    # main item first, all scores 100
    main = out["candidates"][0]
    assert main["name"].startswith("2 BHK Flat In Metro Flats")
    assert all(v == 100 for v in main["scores"].values())
    # similar item keeps partial values + scores; unknown factors → None
    dhamu = out["candidates"][1]
    assert dhamu["unit_values"]["Area"] == "580"
    assert dhamu["scores"]["Area"] == 89
    assert dhamu["scores"]["Deposit"] is None


def test_normalize_detail_operators_preserved():
    out = normalize_detail(SAMPLE)
    by_name = {f["name"]: f for f in out["factors"]}
    assert by_name["Rent"]["operator"] == "<="
    assert by_name["Area"]["operator"] == ">="
    assert by_name["Furnishing Status"]["operator"] == "equals"
    assert by_name["Balcony"]["expected_value"] == "NA"
    assert by_name["Floor"]["data_type"] == "text"   # composite 0/4 stays text


def test_normalize_detail_bad_operator_coerced():
    data = {
        "page_type": "detail",
        "main_item": {"name": "X"},
        "factors": [
            {"name": "Price", "data_type": "numeric", "operator": "less", "expected_value": "10"},
            {"name": "Color", "data_type": "text", "operator": "<=", "expected_value": "Red"},
        ],
        "items": [],
    }
    out = normalize_detail(data)
    by_name = {f["name"]: f for f in out["factors"]}
    assert by_name["Price"]["operator"] == ">="       # invalid numeric op → default
    assert by_name["Color"]["operator"] == "equals"   # numeric op on text → equals


def test_normalize_detail_synthesizes_main_item_when_items_missing():
    data = {
        "page_type": "detail",
        "main_item": {"name": "Solo Listing"},
        "factors": [{"name": "Rent", "data_type": "numeric", "operator": "<=",
                     "expected_value": "5000", "unit": "INR"}],
        "items": [],
    }
    out = normalize_detail(data)
    assert out["candidates"][0]["name"] == "Solo Listing"
    assert out["candidates"][0]["scores"]["Rent"] == 100
    assert out["candidates"][0]["unit_values"]["Rent"] == "5000"


def test_normalize_detail_rejects_comparison_signal():
    assert normalize_detail({"page_type": "comparison"}) is None
    assert normalize_detail(None) is None
    assert normalize_detail({"page_type": "detail", "main_item": {}, "factors": []}) is None


def test_normalize_detail_dedupes_factors_and_caps():
    factors = [{"name": f"F{i}", "data_type": "text", "operator": "equals",
                "expected_value": "x"} for i in range(40)]
    factors.append({"name": "F0", "data_type": "text", "operator": "equals",
                    "expected_value": "dup"})
    data = {"page_type": "detail", "main_item": {"name": "M"},
            "factors": factors, "items": []}
    out = normalize_detail(data, max_factors=24)
    assert len(out["factors"]) == 24
    assert len({f["name"] for f in out["factors"]}) == 24


def test_parse_json_obj_strips_prose():
    assert _parse_json_obj('Here you go:\n```json\n{"a": 1}\n```')["a"] == 1
    assert _parse_json_obj("no json here") is None


# ── Precise-tier credit multiplier (zero-loss invariant for Claude) ─────────
def test_precise_multiplier_default():
    # 9.0 / 2.0 = 4.5× with shipped defaults
    assert precise_multiplier(DEFAULTS) == pytest.approx(4.5)


def test_precise_multiplier_floor_is_one():
    cfg = {"blended_usd_per_mtok": 10.0, "precise_usd_per_mtok": 2.0}
    assert precise_multiplier(cfg) == 1.0


def test_precise_multiplier_tracks_config():
    cfg = {"blended_usd_per_mtok": 2.0, "precise_usd_per_mtok": 12.0}
    assert precise_multiplier(cfg) == pytest.approx(6.0)


# ═════════════════════════════════════════════════════════════════════════════
# v2: hierarchical groups, factor-NATURE doctrine, zero-tolerance mapping,
# accuracy-hint validation (self-healing oracle)
# ═════════════════════════════════════════════════════════════════════════════
from core.url_detail import validate_against_hints

HIER_SAMPLE = {
    "page_type": "detail",
    "main_item": {"name": "Oppo F9"},
    "groups": [
        {"name": "BODY", "source": "page", "factors": [
            {"name": "Weight", "data_type": "numeric", "factor_type": "quantitative",
             "operator": "<=", "expected_value": "169", "unit": "g"},
            {"name": "Build", "data_type": "text", "factor_type": "quantitative",
             "operator": "equals", "expected_value": "Glass front, aluminum back"},
        ]},
        {"name": "DISPLAY", "source": "page", "factors": [
            {"name": "Size", "data_type": "numeric", "factor_type": "quantitative",
             "operator": ">=", "expected_value": "6.3", "unit": "inches"},
            {"name": "Comfort", "data_type": "text", "factor_type": "qualitative",
             "operator": "equals", "expected_value": "High"},
        ]},
    ],
    "items": [
        {"name": "Oppo F9",
         "values": {"BODY::Weight": "169", "BODY::Build": "Glass front, aluminum back",
                    "DISPLAY::Size": "6.3", "DISPLAY::Comfort": "High"},
         "scores": {"BODY::Weight": 100, "BODY::Build": 100,
                    "DISPLAY::Size": 100, "DISPLAY::Comfort": 100}},
        {"name": "Galaxy A57",
         "values": {"BODY::Weight": "179", "DISPLAY::Size": "6.7",
                    "Bogus::Key": "evil"},          # unknown path → must be DROPPED
         "scores": {"BODY::Weight": 90, "DISPLAY::Size": 100}},
    ],
}


def test_hier_page_groups_preserved():
    out = normalize_detail(HIER_SAMPLE, group_threshold=15)
    assert out["kind"] == "hier"                       # page groups are sacred (≤ threshold!)
    assert [g["category"] for g in out["groups"]] == ["BODY", "DISPLAY"]
    assert [r["label"] for r in out["groups"][0]["rows"]] == ["Weight", "Build"]


def test_hier_factor_type_in_row_meta():
    out = normalize_detail(HIER_SAMPLE)
    assert out["row_meta"][(0, 0)]["factor_type"] == "quantitative"
    assert out["row_meta"][(1, 1)]["factor_type"] == "qualitative"
    # text-format FACT stays quantitative (Build = undisputed spec)
    assert out["row_meta"][(0, 1)]["factor_type"] == "quantitative"
    assert out["row_meta"][(0, 1)]["is_numeric"] is False


def test_hier_zero_tolerance_value_mapping():
    out = normalize_detail(HIER_SAMPLE)
    assert out["items"] == ["Oppo F9", "Galaxy A57"]
    # values are positional per item, mapped only via exact Group::Factor paths
    weight_row = out["groups"][0]["rows"][0]
    assert weight_row["values"] == ["169", "179"]
    # unknown "Bogus::Key" must never leak into any row
    all_vals = [v for g in out["groups"] for r in g["rows"] for v in r["values"]]
    assert "evil" not in all_vals
    assert out["row_scores"][(0, 0)] == [100, 90]


def test_ai_grouping_flattened_under_threshold():
    data = {
        "page_type": "detail", "main_item": {"name": "X"},
        "groups": [
            {"name": "Costs", "source": "ai", "factors": [
                {"name": "Rent", "data_type": "numeric", "operator": "<=", "expected_value": "10"}]},
            {"name": "Space", "source": "ai", "factors": [
                {"name": "Area", "data_type": "numeric", "operator": ">=", "expected_value": "500"}]},
        ],
        "items": [],
    }
    # 2 factors ≤ threshold 15 and NO page-defined groups → AI grouping rejected, flat
    out = normalize_detail(data, group_threshold=15)
    assert out["kind"] == "flat"
    assert {f["name"] for f in out["factors"]} == {"Rent", "Area"}
    # …but with threshold 1 the AI grouping is allowed
    out2 = normalize_detail(data, group_threshold=1)
    assert out2["kind"] == "hier"


def test_flat_factor_type_defaults_quantitative():
    out = normalize_detail(SAMPLE)               # v1 back-compat payload (flat "factors")
    assert out["kind"] == "flat"
    assert all(f["factor_type"] == "quantitative" for f in out["factors"])


def test_hints_validation_passes_and_fails():
    out = normalize_detail(HIER_SAMPLE)
    assert validate_against_hints(out, {"expected_factor_count": 4,
                                        "expected_option_count": 2,
                                        "first_factor_name": "Weight",
                                        "first_option_name": "Oppo F9"}) == []
    issues = validate_against_hints(out, {"expected_factor_count": 20,
                                          "first_factor_name": "Rent",
                                          "first_option_name": "Some Other"})
    assert len(issues) == 3
    assert validate_against_hints(out, None) == []


def test_hints_factor_count_tolerance():
    out = normalize_detail(HIER_SAMPLE)          # 4 leaf factors
    assert validate_against_hints(out, {"expected_factor_count": 6}) == []   # |4-6| ≤ max(2, 20%)
    assert len(validate_against_hints(out, {"expected_factor_count": 7})) == 1
