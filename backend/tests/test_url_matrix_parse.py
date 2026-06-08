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
