"""Iteration 107 regression — P0 page-grounding verification, P1 org-type
templates, P2 deep-import helpers. Pure-unit tests (no network/DB).
Run: cd /app/backend && python -m pytest tests/test_iter107_import_trust.py -q
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.import_verify import build_value_index, verify_detail, _match_number  # noqa: E402
from routes.deep_import import _extract_links, _parse_json, _score_candidates  # noqa: E402

PAGE = """Tata Tiago EV
Rs.  5.84 - 9.99 Lakh
Avg. Ex-Showroom price
MG Comet EV
Rs.  6.31 - 8.82 Lakh
Tata Punch EV
Rs. 8.09 Lakh
onwards
Seating Capacity 5 Seater
Battery 19.2 to 24 kWh
Price 7,58,000 onwards
1.2 Crore penthouse
"""


# ── P0: value index ──
def test_lakh_range_expansion():
    idx = build_value_index(PAGE)
    assert _match_number("584000", idx)          # 5.84 Lakh (range min)
    assert _match_number("999000", idx)          # 9.99 Lakh (range max)
    assert _match_number("631000", idx)
    assert _match_number("809000", idx)          # single "8.09 Lakh"


def test_indian_comma_and_crore():
    idx = build_value_index(PAGE)
    assert _match_number("758000", idx)          # 7,58,000
    assert _match_number("12000000", idx)        # 1.2 Crore
    assert _match_number("19.2", idx)            # plain decimal


def test_unstated_number_not_matched():
    idx = build_value_index(PAGE)
    assert _match_number("1100000", idx) is None
    assert _match_number("424242", idx) is None


# ── P0: verify_detail (flat) blanks hallucinated numerics ──
def test_verify_flat_blanks_hallucination():
    detail = {
        "kind": "flat", "main_name": "Tata Tiago EV",
        "factors": [
            {"name": "Budget", "data_type": "numeric", "operator": "<=",
             "expected_value": "584000", "unit": "INR"},
            {"name": "Body", "data_type": "text", "operator": "equals",
             "expected_value": "Hatchback", "unit": None},
        ],
        "candidates": [
            {"name": "Tata Tiago EV", "scores": {"Budget": 100},
             "unit_values": {"Budget": "584000", "Body": "Hatchback"}},
            {"name": "VW Taigun", "scores": {"Budget": 30},
             "unit_values": {"Budget": "1100000"}},
        ],
    }
    s = verify_detail(detail, PAGE)
    assert s["blanked"] == 1
    assert "Budget" not in detail["candidates"][1]["unit_values"]
    assert detail["candidates"][1]["scores"].get("Budget") is None
    assert s["verified"] >= 1
    assert s["has_currency"] is True
    # verified value carries a provenance quote with the source line
    quotes = [e["quote"] for e in s["evidence"] if e["factor"] == "Budget"]
    assert any("5.84" in q for q in quotes)


def test_verify_hier_blanks_and_expected():
    detail = {
        "kind": "hier", "main_name": "x",
        "items": ["Tiago EV", "Comet EV"],
        "groups": [{"category": "Costs", "rows": [
            {"label": "Price", "values": ["584000", "777777"]},
        ]}],
        "row_scores": {(0, 0): [100, 80]},
        "row_meta": {(0, 0): {"is_numeric": True, "expected": "777777",
                              "operator": "<=", "unit": "INR", "factor_type": "quantitative"}},
    }
    s = verify_detail(detail, PAGE)
    assert s["blanked"] == 1
    assert detail["groups"][0]["rows"][0]["values"][1] == ""
    assert detail["row_meta"][(0, 0)]["expected"] is None   # 777777 not on page


def test_verify_never_raises_on_garbage():
    assert verify_detail({"kind": "nope"}, "")["verified"] == 0
    assert verify_detail({}, None)["blanked"] == 0


# ── P2: deep-import helpers ──
def test_extract_links_same_domain_only():
    html = ('<a href="/catalogue/book1.html">A Nice Travel Book</a>'
            '<a href="https://other.com/x">External Site Link</a>'
            '<a href="https://books.toscrape.com/catalogue/book2.html"><b>Second Book</b></a>')
    links = _extract_links(html, "https://books.toscrape.com/index.html")
    urls = [l["url"] for l in links]
    assert "https://books.toscrape.com/catalogue/book1.html" in urls
    assert "https://books.toscrape.com/catalogue/book2.html" in urls
    assert all("other.com" not in u for u in urls)
    assert links[1]["text"] == "Second Book"  # tags stripped


def test_parse_json_extracts_object():
    assert _parse_json('noise {"options":[{"name":"a","url":"u"}]} tail')["options"][0]["name"] == "a"
    assert _parse_json("no json here") is None


def test_score_candidates_direction_aware():
    factors = [{"name": "Price", "data_type": "numeric", "operator": "<="},
               {"name": "Rating", "data_type": "numeric", "operator": ">="}]
    cands = [{"name": "A", "unit_values": {"Price": "100", "Rating": "4"}},
             {"name": "B", "unit_values": {"Price": "200", "Rating": "5"}}]
    _score_candidates(factors, cands)
    assert cands[0]["scores"]["Price"] == 100      # cheapest wins
    assert cands[1]["scores"]["Price"] == 50
    assert cands[1]["scores"]["Rating"] == 100     # highest rating wins
    assert cands[0]["scores"]["Rating"] == 80
