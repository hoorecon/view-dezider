"""Regression tests for the hint-aware Import-from-URL pipeline.

Covers the carwale.com bug (Jun 2026): a thin deterministic table parse
(2 generic factors) silently overrode the user's accuracy hints + selected
AI engine. Hints must now gate deterministic results, and the AI extraction
must accept comparison/listing pages.
"""
import sys

sys.path.insert(0, "/app/backend")

from core.url_detail import (  # noqa: E402
    deterministic_hint_issues, normalize_detail, validate_against_hints,
    _user_facts_block, DETAIL_SYSTEM,
)

CARWALE_HINTS = {
    "expected_factor_count": 6,
    "expected_option_count": 4,
    "first_factor_name": "All Brands",
    "first_option_name": "Tata Tiago EV",
}

# The exact deterministic parse the carwale page produced (the bug).
DET_FACTORS = [
    {"name": "PRICE", "data_type": "numeric"},
    {"name": "MODEL", "data_type": "text"},
]
DET_SCORED = [
    {"name": "Volkswagen Taigun"}, {"name": "Tata Tiago EV"},
    {"name": "MG Comet EV"}, {"name": "Tata Punch EV"},
]


class TestDeterministicHintGate:
    def test_carwale_flat_parse_fails_hints(self):
        """The 2-factor PRICE/MODEL parse MUST be rejected against the user's hints."""
        issues = deterministic_hint_issues(CARWALE_HINTS, factors=DET_FACTORS, candidates=DET_SCORED)
        assert issues, "thin parse must NOT pass the hint gate"
        joined = " ".join(issues)
        assert "All Brands" in joined          # first-factor mismatch flagged
        assert "6" in joined                   # factor-count mismatch flagged

    def test_no_hints_means_no_gate(self):
        assert deterministic_hint_issues(None, factors=DET_FACTORS, candidates=DET_SCORED) == []
        assert deterministic_hint_issues({}, factors=DET_FACTORS, candidates=DET_SCORED) == []

    def test_matching_parse_passes(self):
        factors = [{"name": n} for n in
                   ["All Brands", "Budget", "Body Type", "Fuel Type", "Transmission", "Seating Capacity"]]
        cands = [{"name": n} for n in
                 ["Tata Tiago EV", "MG Comet EV", "Tata Punch EV", "Volkswagen Taigun"]]
        assert deterministic_hint_issues(CARWALE_HINTS, factors=factors, candidates=cands) == []

    def test_hierarchy_shape_gate(self):
        hierarchy = {
            "items": ["Phone A", "Phone B"],
            "groups": [
                {"category": "Body", "rows": [{"label": "Weight", "values": ["1", "2"]}]},
                {"category": "Display", "rows": [{"label": "Size", "values": ["6", "6.5"]}]},
            ],
        }
        # Hints that contradict the hierarchy → issues returned.
        issues = deterministic_hint_issues(
            {"first_factor_name": "All Brands", "expected_factor_count": 6}, hierarchy=hierarchy)
        assert issues
        # Hints that match → passes.
        ok = deterministic_hint_issues(
            {"first_factor_name": "Weight", "expected_option_count": 2}, hierarchy=hierarchy)
        assert ok == []


class TestComparisonPageNormalization:
    CARWALE_LLM_OUTPUT = {
        "page_type": "comparison",
        "main_item": {"name": "Tata Tiago EV"},
        "groups": [{
            "name": "General", "source": "none",
            "factors": [
                {"name": "All Brands", "data_type": "text", "factor_type": "quantitative",
                 "operator": "equals", "expected_value": "Tata", "unit": None},
                {"name": "Budget", "data_type": "numeric", "factor_type": "quantitative",
                 "operator": "<=", "expected_value": "5.84", "unit": "Lakh INR"},
                {"name": "Body Type", "data_type": "text", "factor_type": "quantitative",
                 "operator": "equals", "expected_value": "Hatchback", "unit": None},
                {"name": "Fuel Type", "data_type": "text", "factor_type": "quantitative",
                 "operator": "equals", "expected_value": "Electric", "unit": None},
                {"name": "Transmission", "data_type": "text", "factor_type": "quantitative",
                 "operator": "equals", "expected_value": "Automatic", "unit": None},
                {"name": "Seating Capacity", "data_type": "numeric", "factor_type": "quantitative",
                 "operator": ">=", "expected_value": "5", "unit": "seats"},
            ],
        }],
        "items": [
            {"name": "Tata Tiago EV",
             "values": {"General::All Brands": "Tata", "General::Budget": "5.84",
                        "General::Body Type": "Hatchback", "General::Fuel Type": "Electric",
                        "General::Transmission": "Automatic", "General::Seating Capacity": "5"},
             "scores": {"General::All Brands": 100, "General::Budget": 100,
                        "General::Body Type": 100, "General::Fuel Type": 100,
                        "General::Transmission": 100, "General::Seating Capacity": 100}},
            {"name": "MG Comet EV",
             "values": {"General::All Brands": "MG", "General::Budget": "6.31",
                        "General::Seating Capacity": "4"},
             "scores": {"General::All Brands": 80, "General::Budget": 90,
                        "General::Seating Capacity": 70}},
            {"name": "Tata Punch EV",
             "values": {"General::All Brands": "Tata", "General::Budget": "8.09"},
             "scores": {"General::All Brands": 100, "General::Budget": 70}},
            {"name": "Volkswagen Taigun",
             "values": {"General::All Brands": "Volkswagen", "General::Budget": "11.0"},
             "scores": {"General::All Brands": 60, "General::Budget": 40}},
        ],
    }

    def test_comparison_page_is_accepted(self):
        res = normalize_detail(self.CARWALE_LLM_OUTPUT, max_factors=24, group_threshold=15)
        assert res is not None, "comparison page_type must be normalised, not rejected"
        assert res["kind"] == "flat"
        assert [f["name"] for f in res["factors"]] == [
            "All Brands", "Budget", "Body Type", "Fuel Type", "Transmission", "Seating Capacity"]
        assert [c["name"] for c in res["candidates"]] == [
            "Tata Tiago EV", "MG Comet EV", "Tata Punch EV", "Volkswagen Taigun"]
        # Result satisfies the user's hints end-to-end.
        assert validate_against_hints(res, CARWALE_HINTS) == []

    def test_comparison_does_not_backfill_peer_scores(self):
        """Peers on a comparison page must NOT be force-scored 100 like a detail
        page's main item — known scores are kept, unknown stay None."""
        res = normalize_detail(self.CARWALE_LLM_OUTPUT, max_factors=24, group_threshold=15)
        punch = next(c for c in res["candidates"] if c["name"] == "Tata Punch EV")
        assert punch["scores"]["Budget"] == 70
        assert punch["scores"]["Body Type"] is None  # unknown stays unknown

    def test_detail_page_still_backfills_main(self):
        data = {
            "page_type": "detail",
            "main_item": {"name": "2 BHK in HSR Layout"},
            "groups": [{"name": "General", "source": "none", "factors": [
                {"name": "Rent", "data_type": "numeric", "factor_type": "quantitative",
                 "operator": "<=", "expected_value": "18000", "unit": "INR"},
                {"name": "Area", "data_type": "numeric", "factor_type": "quantitative",
                 "operator": ">=", "expected_value": "650", "unit": "sqft"},
            ]}],
            "items": [{"name": "2 BHK in HSR Layout", "values": {}, "scores": {}}],
        }
        res = normalize_detail(data, max_factors=24, group_threshold=15)
        assert res is not None and res["kind"] == "flat"
        main = res["candidates"][0]
        assert main["scores"]["Rent"] == 100 and main["scores"]["Area"] == 100
        assert main["unit_values"]["Rent"] == "18000"

    def test_unusable_page_type_rejected(self):
        assert normalize_detail({"page_type": "garbage"}) is None
        assert normalize_detail({"page_type": "comparison"}) is None  # no groups/items


class TestUserFactsInjection:
    def test_facts_block_renders_all_hints(self):
        block = _user_facts_block(CARWALE_HINTS)
        assert "USER-VERIFIED PAGE FACTS" in block
        for needle in ("6", "All Brands", "4", "Tata Tiago EV"):
            assert needle in block

    def test_no_hints_no_block(self):
        assert _user_facts_block(None) == ""
        assert _user_facts_block({}) == ""

    def test_prompt_has_injection_point_and_comparison_mode(self):
        assert "{user_facts}" in DETAIL_SYSTEM
        assert '"comparison"' in DETAIL_SYSTEM
        # The old bail-out instruction must be gone.
        assert 'reply exactly {"page_type":"comparison"}' not in DETAIL_SYSTEM
