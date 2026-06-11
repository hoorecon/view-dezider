"""Unit tests for the AI-wallet pricing breakdown — specifically the
`markup_routed_pct` split that protects the primary treasury account from a
Razorpay-fee deficit.

Run:
    cd /app/backend && pytest tests/test_ai_wallet_markup.py -v
"""
import pytest

from core.ai_billing import price_for_credits, _routed_pct, _markup_pct


CFG_DEFAULT = {
    "tokens_per_credit": 100.0,
    "blended_usd_per_mtok": 2.0,
    "markup_user_pct": 13.0,
    "markup_admin_pct": 1.0,
    "markup_routed_pct": 77.0,
}


def test_user_markup_pct():
    assert _markup_pct(CFG_DEFAULT, is_admin=False) == 13.0


def test_admin_markup_pct():
    assert _markup_pct(CFG_DEFAULT, is_admin=True) == 1.0


def test_routed_pct_default():
    assert _routed_pct(CFG_DEFAULT) == 77.0


def test_routed_pct_clamped_to_100():
    assert _routed_pct({"markup_routed_pct": 250}) == 100.0


def test_routed_pct_clamped_to_0():
    assert _routed_pct({"markup_routed_pct": -10}) == 0.0


def test_routed_pct_fallback_when_missing():
    assert _routed_pct({}) == 77.0


def test_routed_pct_invalid_falls_back():
    assert _routed_pct({"markup_routed_pct": "junk"}) == 77.0


def test_price_breakdown_routed_split():
    """On a ₹100 LLM cost @ 13% markup, 77% of markup should be routed."""
    # Choose credits such that cost is exactly ₹100 at fx=50:
    # credits * 100 * 2 / 1_000_000 = $1.0 → credits = 5000  → cost_usd $1.0 → cost_inr ₹50
    # Use fx so cost_inr = ₹100 → fx = 100
    fx = 100.0
    pr = price_for_credits(5000, is_admin=False, cfg=CFG_DEFAULT, fx=fx)
    # cost_usd = 5000 * 100 * 2 / 1_000_000 = 1.0
    assert pr["cost_usd"] == pytest.approx(1.0, rel=1e-3)
    # cost_inr = 1.0 * 100 = 100
    assert pr["cost_inr"] == pytest.approx(100.0, rel=1e-3)
    # total_inr = 100 * 1.13 = 113
    assert pr["total_inr"] == pytest.approx(113.0, rel=1e-3)
    # markup_inr ≈ 13
    assert pr["markup_inr"] == pytest.approx(13.0, rel=1e-2)
    # routed = 13 * 0.77 = 10.01 → paise = 1001
    assert pr["routed_paise"] == 1001
    # retained = 1300 - 1001 = 299 paise
    assert pr["retained_markup_paise"] == 299
    # And routed_inr / retained_inr exposed as floats
    assert pr["routed_inr"] == pytest.approx(10.01, abs=0.01)
    assert pr["retained_markup_inr"] == pytest.approx(2.99, abs=0.01)


def test_admin_buyer_no_route_split():
    """Admin buyers get 1% markup — routed amount stays consistent."""
    pr = price_for_credits(5000, is_admin=True, cfg=CFG_DEFAULT, fx=100.0)
    # 1% markup on ₹100 = ₹1.00 → 100 paise
    assert pr["markup_paise"] == 100
    # 77% routed = 77 paise → below ROUTE_MIN_TRANSFER_PAISE (100) so the
    # route layer skips creating the transfer entirely
    assert pr["routed_paise"] == 77


def test_zero_loss_invariant_at_default_split():
    """The whole point: on a ₹100 LLM cost at default config, primary account
    should NET more than ₹100 after Razorpay fee and Route transfer.

    Razorpay INR fee = 2% + 18% GST = 2.36% effective.
    """
    pr = price_for_credits(5000, is_admin=False, cfg=CFG_DEFAULT, fx=100.0)
    charged = pr["total_inr"]                # ₹113
    routed = pr["routed_inr"]                # ₹10.01
    rzp_fee = charged * 0.0236              # ₹2.667
    primary_net = charged - routed - rzp_fee
    cost = pr["cost_inr"]                    # ₹100
    surplus = primary_net - cost
    # We require strictly non-negative surplus on the default config.
    assert surplus > 0, (
        f"DEFICIT! primary_net={primary_net:.2f} cost={cost:.2f} "
        f"(charged={charged:.2f}, routed={routed:.2f}, fee={rzp_fee:.2f})"
    )


def test_full_route_eats_buffer():
    """If user mis-configures routed_pct=100, primary account loses money —
    proving the math actually depends on the new config knob."""
    cfg = {**CFG_DEFAULT, "markup_routed_pct": 100.0}
    pr = price_for_credits(5000, is_admin=False, cfg=cfg, fx=100.0)
    charged = pr["total_inr"]
    routed = pr["routed_inr"]
    rzp_fee = charged * 0.0236
    primary_net = charged - routed - rzp_fee
    surplus = primary_net - pr["cost_inr"]
    assert surplus < 0, "Expected deficit when 100% of markup is routed"


def test_zero_route_keeps_all_markup_in_primary():
    cfg = {**CFG_DEFAULT, "markup_routed_pct": 0.0}
    pr = price_for_credits(5000, is_admin=False, cfg=cfg, fx=100.0)
    assert pr["routed_paise"] == 0
    assert pr["retained_markup_paise"] == pr["markup_paise"]
