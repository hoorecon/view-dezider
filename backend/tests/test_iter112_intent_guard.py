"""Iteration 112 — Deep Import hard-constraint intent guard (rent vs buy).

Bug: context "…2 BHK Flat for RENT in Chennai Mugappair…" returned SALE /
new-project listings. The AI treated transaction type as soft relevance.
Fix: deterministic intent detection enforced at 4 layers — link ranking,
post-pick filtering (options + hubs), per-page text guard, prompt clause.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from routes import deep_import as di  # noqa: E402

CTX_RENT = "Choose best 2 BHK Flat for Rent in Chennai Mugappair area"
CTX_BUY = "Buy a 3 BHK flat in Pune under 1.2 Cr"


def test_intent_detection():
    assert di._intent_of(CTX_RENT) == "rent"
    assert di._intent_of(CTX_BUY) == "buy"
    assert di._intent_of("Compare laptops under 60k") is None
    # ambiguous (both) → None, never guess
    assert di._intent_of("rent vs buy decision for a flat") is None


def test_rank_links_sinks_contradicting_transaction():
    links = [
        {"text": "2 BHK Flats for Sale in Mogappair", "url": "https://x.in/flats-for-sale-in-mogappair"},
        {"text": "New Projects in Mogappair Chennai", "url": "https://x.in/new-projects-mogappair-chennai"},
        {"text": "2 BHK Flats for Rent in Mogappair", "url": "https://x.in/flats-for-rent-in-mogappair"},
    ]
    ranked = di._rank_links(links, CTX_RENT)
    assert ranked[0]["url"].endswith("rent-in-mogappair")
    assert ranked[-1]["url"].endswith(("sale-in-mogappair", "new-projects-mogappair-chennai"))


def test_drop_contradicting_options_and_hubs():
    opts = [
        {"name": "2 BHK Apartment (Sale)", "url": "https://x.in/2bhk-for-sale/d1"},
        {"name": "2 BHK Flat for Rent", "url": "https://x.in/2bhk-for-rent/d2"},
        {"name": "2 BHK In Crown Residences", "url": "https://x.in/np/crown/d3"},  # neutral → kept
    ]
    kept = di._drop_contradicting(opts, "rent")
    assert [k["url"][-2:] for k in kept] == ["d2", "d3"]
    # hubs are plain strings
    hubs = ["https://x.in/flats-for-sale-in-chennai", "https://x.in/flats-for-rent-in-chennai"]
    assert di._drop_contradicting(hubs, "rent") == ["https://x.in/flats-for-rent-in-chennai"]
    # no intent → untouched
    assert di._drop_contradicting(opts, None) == opts


def test_page_text_guard():
    sale_page = ("Super Passcode by Casagrand. Price per sq.ft 8753. Booking open. "
                 "EMI options available. Possession Dec 2027.")
    rent_page = ("2 BHK flat for rent in Mogappair. Monthly Rent 18,000. "
                 "Deposit 1,00,000. Available from July.")
    assert di._page_matches_intent(rent_page, "rent") is True
    assert di._page_matches_intent(sale_page, "rent") is False
    assert di._page_matches_intent(sale_page, "buy") is True
    assert di._page_matches_intent(sale_page, None) is True  # no intent → no guard


def test_intent_clause_injected_text():
    rent = di._intent_clause("rent")
    assert "FOR RENT" in rent and "INVALID" in rent and "SALE" in rent
    buy = di._intent_clause("buy")
    assert "SALE/PURCHASE" in buy and "rental" in buy
    assert di._intent_clause(None) == ""
