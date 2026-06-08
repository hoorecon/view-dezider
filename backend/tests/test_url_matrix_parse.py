"""Offline regression for the transposed comparison-matrix parser + clean-numeric
factor derivation (the GSMArena-style 'items as columns' layout).

Reads a static fixture HTML so it needs no live server / LLM budget.
"""
import os
import asyncio

from core.url_crawl import (
    _comparison_matrix_candidates, _names_from_title, _is_low_quality,
)
from routes.url_analyze import _derive_factors_and_scores, _measure_num
from bs4 import BeautifulSoup

FIX = os.path.join(os.path.dirname(__file__), "fixtures", "phone_compare.html")


def _html():
    with open(FIX, encoding="utf-8") as f:
        return f.read()


def test_names_from_title():
    soup = BeautifulSoup(_html(), "html.parser")
    names = _names_from_title(soup)
    assert names == ["Alpha One", "Beta Max", "Gamma Pro"]


def test_matrix_items_and_category_prefix():
    cands = _comparison_matrix_candidates(_html())
    assert [c["name"] for c in cands] == ["Alpha One", "Beta Max", "Gamma Pro"]
    # Category-prefixed, readable attribute keys.
    keys = set(cands[0]["attributes"].keys())
    assert "Body · Weight" in keys
    assert "Battery · Capacity" in keys
    # First column value mapped to the right item.
    assert cands[0]["attributes"]["Body · Weight"].startswith("169")
    assert cands[2]["attributes"]["Battery · Capacity"].startswith("5000")


def test_clean_numeric_detection():
    # Clean measurements parse; messy spec strings do NOT.
    assert _measure_num("169 g (5.96 oz)") == 169.0
    assert _measure_num("3500 mAh") == 3500.0
    assert _measure_num("2.10") == 2.10
    assert _measure_num("GSM 850 / 900 / 1800") is None      # band list
    assert _measure_num("2018, August. Released") is None     # date blob
    assert _measure_num("256GB 12GB RAM, 512GB") is None      # multi-spec


def test_derive_produces_clean_factors_no_band_garbage():
    cands = _comparison_matrix_candidates(_html())
    factors, scored = _derive_factors_and_scores(cands, 8)
    fnames = [f["name"] for f in factors]
    # Weight & Battery capacity become genuine numeric factors.
    weight = next(f for f in factors if f["name"] == "Body · Weight")
    assert weight["data_type"] == "numeric"
    battery = next(f for f in factors if f["name"] == "Battery · Capacity")
    assert battery["data_type"] == "numeric" and battery["expected_value"] == "7025.0"
    # Band lists must NOT be numeric factors (the old '850' bug).
    for f in factors:
        if "bands" in f["name"]:
            assert f["data_type"] == "text", f
    # Higher battery → higher score for Beta Max (7025 is max).
    beta = next(s for s in scored if s["name"] == "Beta Max")
    assert beta["scores"]["Battery · Capacity"] == 100.0


def test_low_quality_detection():
    # Generic colN keys → low quality (should trigger matrix/AI fallback).
    assert _is_low_quality([{"attributes": {"col0": "a", "col1": "b"}},
                            {"attributes": {"col0": "c", "col1": "d"}}]) is True
    # Real header keys → good quality.
    assert _is_low_quality([{"attributes": {"Returns": "10", "Fee": "1"}},
                            {"attributes": {"Returns": "20", "Fee": "2"}}]) is False


# ── Hierarchical (two-level) parse + scoring ────────────────────────────────
from core.url_crawl import parse_hierarchy
from routes.url_analyze import _score_hierarchy_numeric
from core.decision_builder import _effective_pct, _hier_worth
from models.decisions_models import Factor, OptionAssessment


def test_parse_hierarchy_groups_and_subs():
    h = parse_hierarchy(_html())
    assert h is not None
    assert h["items"] == ["Alpha One", "Beta Max", "Gamma Pro"]
    cats = [g["category"] for g in h["groups"]]
    assert {"Body", "Battery", "Network"}.issubset(set(cats))
    body = next(g for g in h["groups"] if g["category"] == "Body")
    labels = [r["label"] for r in body["rows"]]
    assert "Weight" in labels and "Build" in labels
    # Each row carries one value per item.
    weight_row = next(r for r in body["rows"] if r["label"] == "Weight")
    assert len(weight_row["values"]) == 3 and weight_row["values"][0].startswith("169")


def test_hierarchy_numeric_vs_text_scoring():
    h = parse_hierarchy(_html())
    row_scores, row_meta, text_rows = _score_hierarchy_numeric(h["items"], h["groups"])
    # Locate Battery·Capacity (3500 / 7025 / 5000) → numeric, proportional.
    for gi, g in enumerate(h["groups"]):
        for ri, row in enumerate(g["rows"]):
            if g["category"] == "Battery" and row["label"] == "Capacity":
                assert row_meta[(gi, ri)]["is_numeric"] is True
                assert row_scores[(gi, ri)] == [0, 100, round((5000 - 3500) / (7025 - 3500) * 100)]
            if row["label"] == "2G bands":   # messy band list → text, needs AI
                assert row_meta[(gi, ri)]["is_numeric"] is False
                assert (gi, ri) in [(t[0], t[1]) for t in text_rows]


def test_effective_pct_and_worth():
    parent = Factor(id="p", name="Body", rating=50)
    s1 = Factor(id="s1", name="Weight", parent_id="p", weight=50)
    s2 = Factor(id="s2", name="Build", parent_id="p", weight=50)
    assessments = [OptionAssessment(factor_id="s1", percentage=80),
                   OptionAssessment(factor_id="s2", percentage=40)]
    pct_by = {"s1": 80, "s2": 40}
    # Equal weights → mean = 60.
    assert _effective_pct(parent, [s1, s2], pct_by) == 60.0
    # Single parent worth == its effective pct.
    assert _hier_worth([parent], [parent, s1, s2], assessments) == 60.0


# ── E-commerce product grid (Amazon-style) + currency numerics ──────────────
from core.url_crawl import _product_grid_candidates
from routes.url_analyze import _measure_num

_AMAZON_HTML = """
<div data-asin="A1"><h2><span>ACWO Wireless Earbuds Bold</span></h2>
  <span class="a-price"><span class="a-offscreen">₹2,498</span></span>
  <span class="a-icon-alt">3.6 out of 5 stars</span></div>
<div data-asin="A2"><h2><span>Boult TWS Earbuds 42H</span></h2>
  <span class="a-price"><span class="a-offscreen">₹899</span></span>
  <span class="a-icon-alt">4.8 out of 5 stars</span></div>
<div data-asin="A3"><h2><span>OnePlus Nord Buds 3r</span></h2>
  <span class="a-price"><span class="a-offscreen">₹1,999</span></span>
  <span class="a-icon-alt">4.3 out of 5 stars</span></div>
"""


def test_currency_measure_num():
    assert _measure_num("₹2,498") == 2498.0
    assert _measure_num("$19.99") == 19.99
    assert _measure_num("₹899") == 899.0
    assert _measure_num("GSM 850 / 900") is None


def test_product_grid_extraction_and_scoring():
    cands = _product_grid_candidates(_AMAZON_HTML)
    assert len(cands) == 3
    names = [c["name"] for c in cands]
    assert any("OnePlus" in n for n in names)
    a2 = next(c for c in cands if "Boult" in c["name"])
    assert a2["attributes"]["Price"].startswith("₹899")
    assert a2["attributes"]["Rating"] == "4.8"
    # Derived: Price numeric lower-better, Rating numeric higher-better.
    factors, scored = _derive_factors_and_scores(cands, 4)
    price = next(f for f in factors if f["name"] == "Price")
    rating = next(f for f in factors if f["name"] == "Rating")
    assert price["data_type"] == "numeric" and price["operator"] == "<="
    assert rating["data_type"] == "numeric" and rating["operator"] == ">="
    # Cheapest (Boult ₹899) scores best on Price.
    boult = next(s for s in scored if "Boult" in s["name"])
    assert boult["scores"]["Price"] == 100.0


