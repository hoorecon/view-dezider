"""Unit tests for direction-aware factor derivation in URL import/analyse.

Cost/fee/risk-style columns must be detected as "lower is better": operator '<=',
Expected = column MIN, and per-item scores inverted (lowest value -> 100%).
"""
from routes.url_analyze import _is_lower_better, _derive_factors_and_scores


def test_is_lower_better_keywords():
    assert _is_lower_better("Expense Ratio")
    assert _is_lower_better("Annual Fees")          # plural
    assert _is_lower_better("Total Cost")
    assert _is_lower_better("Management Charges")
    assert _is_lower_better("Risk Score")
    assert _is_lower_better("Max Drawdown")
    # higher-is-better / neutral columns
    assert not _is_lower_better("1Y Return")
    assert not _is_lower_better("AUM")
    assert not _is_lower_better("Rating")
    # must not false-match substrings
    assert not _is_lower_better("Coffee Quality")
    assert not _is_lower_better("Average Tenure")


def _candidates():
    return [
        {"name": "Alpha", "attributes": {"Name": "Alpha", "1Y Return": "44.4", "Expense Ratio": "0.85"}},
        {"name": "Beta",  "attributes": {"Name": "Beta",  "1Y Return": "31.9", "Expense Ratio": "1.10"}},
        {"name": "Gamma", "attributes": {"Name": "Gamma", "1Y Return": "52.1", "Expense Ratio": "1.45"}},
    ]


def test_derivation_directions_and_scores():
    factors, scored = _derive_factors_and_scores(_candidates(), max_factors=8)
    fmap = {f["name"]: f for f in factors}

    # higher-is-better return
    assert fmap["1Y Return"]["operator"] == ">="
    assert fmap["1Y Return"]["expected_value"] == "52.1"
    # lower-is-better expense
    assert fmap["Expense Ratio"]["operator"] == "<="
    assert fmap["Expense Ratio"]["expected_value"] == "0.85"

    by_name = {s["name"]: s["scores"] for s in scored}
    # Return: Gamma best (100), Beta worst (0)
    assert by_name["Gamma"]["1Y Return"] == 100.0
    assert by_name["Beta"]["1Y Return"] == 0.0
    # Expense: Alpha best/lowest (100), Gamma worst/highest (0)
    assert by_name["Alpha"]["Expense Ratio"] == 100.0
    assert by_name["Gamma"]["Expense Ratio"] == 0.0
