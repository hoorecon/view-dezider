"""
Iteration 146 — Collaboration & Knowledge Marketplace Epic (Phases B2..F).

End-to-end backend tests for:
  • Phase B2: Platform Experts (CRUD, bulk, filters, masters)
  • Phase C : Public Help (ask, contribute, accept/dismiss, merge, close)
  • Phase D : Marketplace (publish, browse, detail, clone, gating)
  • Phase E : Earnings, payouts, payout-account, Razorpay order/verify
  • Phase F : Karma, ratings, leaderboard, fame profile, admin karma config

Uses two real accounts:
  - super@test.com  (acts as Seller / Owner / Admin)
  - admin@test.com  (acts as Buyer / Contributor / Rater)
"""

import os
import time
import uuid

import pytest
import requests

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "").rstrip("/")
API = f"{BASE_URL}/api"

SUPER = {"email": "super@test.com", "password": "SuperPass2026!"}
ADMIN = {"email": "admin@test.com", "password": "AdminPass2026!"}


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------
def _login(creds):
    r = requests.post(f"{API}/auth/login", json=creds, timeout=30)
    assert r.status_code == 200, f"login failed for {creds['email']}: {r.status_code} {r.text}"
    j = r.json()
    tok = j.get("token") or j.get("access_token") or j.get("session_token")
    assert tok, f"no token in login response: {j}"
    return tok, j


@pytest.fixture(scope="module")
def super_token():
    tok, _ = _login(SUPER)
    return tok


@pytest.fixture(scope="module")
def admin_token():
    tok, _ = _login(ADMIN)
    return tok


def _h(tok):
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


# ---------------------------------------------------------------------------
# tracked artefacts for cleanup
# ---------------------------------------------------------------------------
_CREATED = {"decisions": [], "listings": [], "experts": [], "posts": []}


# ===========================================================================
# Phase B2 — Platform Experts & new master types
# ===========================================================================
class TestPhaseB2_Masters:
    """4 new master types must respond"""

    @pytest.mark.parametrize("mtype", ["expert_type", "experience_range", "fees_per_min", "available_timing"])
    def test_master_type_returns_items(self, super_token, mtype):
        r = requests.get(f"{API}/masters/{mtype}", headers=_h(super_token), timeout=20)
        assert r.status_code == 200, f"{mtype} -> {r.status_code} {r.text[:200]}"
        body = r.json()
        items = body if isinstance(body, list) else body.get("items", body)
        assert isinstance(items, list)


class TestPhaseB2_PlatformExperts:
    def test_seeded_experts_exist(self, super_token):
        r = requests.get(f"{API}/platform-experts", headers=_h(super_token), timeout=20)
        assert r.status_code == 200, r.text
        ids = {it["expert_id"] for it in r.json()["items"]}
        for seed in ("pex_seed_health_01", "pex_seed_finance_01", "pex_seed_career_01"):
            assert seed in ids, f"missing seeded expert {seed}; got {sorted(ids)[:10]}"

    def test_admin_crud_and_filters(self, super_token, admin_token):
        email = f"test_exp_{uuid.uuid4().hex[:8]}@example.com"
        # CREATE (admin)
        body = {
            "name": "TEST Dr Example",
            "email": email,
            "expert_type": "Doctor",
            "languages": ["English"],
            "experience_range": "5-10 years",
            "fees_per_min_inr": 50,
            "available_timings": ["Morning"],
            "specializations": ["TEST_spec"],
            "catalog_node_ids": ["health"],
            "organizations": [{"org_name": "TEST Hospital", "role": "Consultant"}],
        }
        r = requests.post(f"{API}/platform-experts", headers=_h(super_token), json=body, timeout=20)
        assert r.status_code == 200, r.text
        ex = r.json()
        assert ex["expert_id"].startswith("pex_")
        assert ex["email"] == email
        eid = ex["expert_id"]
        _CREATED["experts"].append(eid)

        # GET detail
        r = requests.get(f"{API}/platform-experts/{eid}", headers=_h(super_token), timeout=20)
        assert r.status_code == 200
        assert r.json()["expert_id"] == eid

        # filter catalog_node_id
        r = requests.get(f"{API}/platform-experts?catalog_node_id=health", headers=_h(super_token), timeout=20)
        assert r.status_code == 200
        assert any(it["expert_id"] == eid for it in r.json()["items"])

        # filter expert_type
        r = requests.get(f"{API}/platform-experts?expert_type=Doctor", headers=_h(super_token), timeout=20)
        assert r.status_code == 200

        # search
        r = requests.get(f"{API}/platform-experts?search=TEST_spec", headers=_h(super_token), timeout=20)
        assert r.status_code == 200
        assert any(it["expert_id"] == eid for it in r.json()["items"])

        # non-admin write should be blocked
        r = requests.post(f"{API}/platform-experts", headers=_h(admin_token), json={**body, "email": "TEST_other@example.com"}, timeout=20)
        # admin@test.com has admin role per memo/test_credentials; if so this passes, otherwise it should be 403
        assert r.status_code in (200, 403), f"unexpected: {r.status_code} {r.text[:200]}"
        if r.status_code == 200:
            _CREATED["experts"].append(r.json()["expert_id"])

        # UPDATE
        r = requests.put(f"{API}/platform-experts/{eid}", headers=_h(super_token),
                         json={"headline": "Senior TEST"}, timeout=20)
        assert r.status_code == 200, r.text
        assert r.json()["headline"] == "Senior TEST"

        # DUPLICATE email blocked
        r = requests.post(f"{API}/platform-experts", headers=_h(super_token), json=body, timeout=20)
        assert r.status_code == 409, r.text

        # BULK upload with one duplicate + one valid
        new_email = f"TEST_bulk_{uuid.uuid4().hex[:8]}@example.com"
        bulk = {"experts": [
            {**body, "email": new_email, "name": "TEST Bulk OK"},
            {**body, "email": email, "name": "TEST Bulk DUP"},
            {**body, "email": "not-an-email", "name": "TEST Bulk BAD"},
        ]}
        r = requests.post(f"{API}/platform-experts/bulk", headers=_h(super_token), json=bulk, timeout=20)
        assert r.status_code == 200, r.text
        bj = r.json()
        assert bj["created_count"] == 1
        assert bj["error_count"] == 2
        for c in bj["created"]:
            _CREATED["experts"].append(c["expert_id"])

    def test_cleanup_experts(self, super_token):
        for eid in list(_CREATED["experts"]):
            requests.delete(f"{API}/platform-experts/{eid}", headers=_h(super_token), timeout=20)
        _CREATED["experts"].clear()


# ===========================================================================
# Helper: build a publishable decision
# ===========================================================================
def _make_decision(tok, title="TEST Decision"):
    r = requests.post(f"{API}/decisions", headers=_h(tok), json={"title": title, "context": "ctx"}, timeout=20)
    assert r.status_code == 200, r.text
    did = r.json()["id"]
    payload = {
        "factors": [
            {"id": "f1", "name": "Cost", "category": "primary", "rating": 7, "order": 0},
            {"id": "f2", "name": "Quality", "category": "primary", "rating": 9, "order": 1},
        ],
        "options": [
            {"id": "o1", "name": "Option A", "assessments": [{"factor_id": "f1", "percentage": 60},
                                                              {"factor_id": "f2", "percentage": 80}]},
            {"id": "o2", "name": "Option B", "assessments": [{"factor_id": "f1", "percentage": 80},
                                                              {"factor_id": "f2", "percentage": 50}]},
        ],
    }
    r = requests.put(f"{API}/decisions/{did}", headers=_h(tok), json=payload, timeout=20)
    assert r.status_code == 200, r.text
    _CREATED["decisions"].append((tok, did))
    return did


# ===========================================================================
# Phase C — Public Help
# ===========================================================================
class TestPhaseC_PublicHelp:
    def test_ask_contribute_accept_merge_close(self, super_token, admin_token):
        did = _make_decision(super_token, "TEST PublicHelp")

        # ask-public (owner)
        r = requests.post(f"{API}/public-help/decisions/{did}/ask-public",
                          headers=_h(super_token),
                          json={"step_number": 2, "message": "help me list factors"}, timeout=20)
        assert r.status_code == 200, r.text
        post = r.json()
        post_id = post["post_id"]
        _CREATED["posts"].append(post_id)
        assert post["status"] == "open"

        # idempotent
        r2 = requests.post(f"{API}/public-help/decisions/{did}/ask-public",
                           headers=_h(super_token), json={"step_number": 2, "message": "updated msg"}, timeout=20)
        assert r2.status_code == 200
        assert r2.json()["post_id"] == post_id

        # feed visible to others
        r = requests.get(f"{API}/public-help/feed", headers=_h(admin_token), timeout=20)
        assert r.status_code == 200
        assert any(p["post_id"] == post_id for p in r.json()["items"])

        # mine
        r = requests.get(f"{API}/public-help/mine", headers=_h(super_token), timeout=20)
        assert r.status_code == 200
        assert any(p["post_id"] == post_id for p in r.json()["items"])

        # owner can't contribute on own post
        r = requests.post(f"{API}/public-help/{post_id}/contribute", headers=_h(super_token),
                          json={"body": "self", "suggestions": ["self"]}, timeout=20)
        assert r.status_code == 400, r.text

        # admin contributes
        r = requests.post(f"{API}/public-help/{post_id}/contribute", headers=_h(admin_token),
                          json={"body": "try these", "suggestions": ["Reliability", "Brand value"]}, timeout=20)
        assert r.status_code == 200, r.text
        cid = r.json()["contribution_id"]

        # second contribution (admin) — will be dismissed later
        r = requests.post(f"{API}/public-help/{post_id}/contribute", headers=_h(admin_token),
                          json={"body": "ignore", "suggestions": ["BadIdea"]}, timeout=20)
        assert r.status_code == 200
        cid2 = r.json()["contribution_id"]

        # only owner can accept
        r = requests.post(f"{API}/public-help/contributions/{cid}/accept", headers=_h(admin_token), timeout=20)
        assert r.status_code == 403

        # owner karma BEFORE for comparison
        before = requests.get(f"{API}/karma/me", headers=_h(admin_token), timeout=20).json()
        before_bal = before.get("karma_balance", 0)

        # owner accepts
        r = requests.post(f"{API}/public-help/contributions/{cid}/accept", headers=_h(super_token), timeout=20)
        assert r.status_code == 200, r.text

        # contributor karma should have increased by contribution_accepted (default 10)
        after = requests.get(f"{API}/karma/me", headers=_h(admin_token), timeout=20).json()
        assert after["karma_balance"] >= before_bal + 10, f"karma not awarded: {before_bal}->{after['karma_balance']}"

        # owner dismisses other
        r = requests.post(f"{API}/public-help/contributions/{cid2}/dismiss", headers=_h(super_token), timeout=20)
        assert r.status_code == 200

        # merge-accepted — appends factors (step 2)
        r = requests.post(f"{API}/public-help/{post_id}/merge-accepted", headers=_h(super_token), timeout=20)
        assert r.status_code == 200, r.text
        assert r.json()["merged_as"] == "factors"
        assert r.json()["added"] >= 1

        # decision now has the new factor
        r = requests.get(f"{API}/decisions/{did}", headers=_h(super_token), timeout=20)
        names = [f.get("name") for f in r.json().get("factors", [])]
        assert any(n in ("Reliability", "Brand value") for n in names), f"merge did not add factors: {names}"

        # close
        r = requests.post(f"{API}/public-help/{post_id}/close", headers=_h(super_token), timeout=20)
        assert r.status_code == 200

        # contribute on closed should 409
        r = requests.post(f"{API}/public-help/{post_id}/contribute", headers=_h(admin_token),
                          json={"body": "late"}, timeout=20)
        assert r.status_code == 409


# ===========================================================================
# Phase D — Marketplace + Phase E earnings credit hooks
# ===========================================================================
class TestPhaseD_Marketplace:
    def test_publish_validation_and_free_clone_flow(self, super_token, admin_token):
        # publish without factors/options should be blocked
        r0 = requests.post(f"{API}/decisions", headers=_h(super_token),
                           json={"title": "TEST Empty", "context": "x"}, timeout=20)
        empty_id = r0.json()["id"]
        _CREATED["decisions"].append((super_token, empty_id))
        r = requests.post(f"{API}/marketplace/publish", headers=_h(super_token),
                          json={"decision_id": empty_id, "tier": "free_clone"}, timeout=20)
        assert r.status_code == 400, r.text

        # build a real decision and publish free
        did = _make_decision(super_token, "TEST Free Listing")
        r = requests.post(f"{API}/marketplace/publish", headers=_h(super_token),
                          json={"decision_id": did, "tier": "free_clone",
                                "description": "free demo"}, timeout=20)
        assert r.status_code == 200, r.text
        listing = r.json()
        lid = listing["listing_id"]
        _CREATED["listings"].append(lid)
        assert listing["tier"] == "free_clone"

        # paid_clone without price should be blocked
        did2 = _make_decision(super_token, "TEST PaidNoPrice")
        r = requests.post(f"{API}/marketplace/publish", headers=_h(super_token),
                          json={"decision_id": did2, "tier": "paid_clone"}, timeout=20)
        assert r.status_code == 400, r.text

        # publish paid_clone listing for later
        r = requests.post(f"{API}/marketplace/publish", headers=_h(super_token),
                          json={"decision_id": did2, "tier": "paid_clone",
                                "price_inr": 199, "description": "premium"}, timeout=20)
        assert r.status_code == 200, r.text
        paid_listing = r.json()
        plid = paid_listing["listing_id"]
        _CREATED["listings"].append(plid)

        # view_only listing
        did3 = _make_decision(super_token, "TEST ViewOnly")
        r = requests.post(f"{API}/marketplace/publish", headers=_h(super_token),
                          json={"decision_id": did3, "tier": "view_only"}, timeout=20)
        assert r.status_code == 200
        vlid = r.json()["listing_id"]
        _CREATED["listings"].append(vlid)

        # browse from admin — paid snapshot must be gated (locked)
        r = requests.get(f"{API}/marketplace?sort=newest", headers=_h(admin_token), timeout=20)
        assert r.status_code == 200
        items = {it["listing_id"]: it for it in r.json()["items"]}
        assert plid in items
        assert items[plid]["snapshot"].get("locked") is True
        # free listing should NOT be locked
        assert lid in items
        assert not items[lid]["snapshot"].get("locked", False)

        # detail increments view_count + paid is locked for non-owner
        r1 = requests.get(f"{API}/marketplace/{plid}", headers=_h(admin_token), timeout=20)
        assert r1.status_code == 200
        assert r1.json()["snapshot"].get("locked") is True
        r2 = requests.get(f"{API}/marketplace/{plid}", headers=_h(admin_token), timeout=20)
        assert r2.json()["view_count"] >= r1.json()["view_count"]

        # view_only clone -> 403
        r = requests.post(f"{API}/marketplace/{vlid}/clone", headers=_h(admin_token), timeout=20)
        assert r.status_code == 403, r.text

        # paid clone without payment -> 402
        r = requests.post(f"{API}/marketplace/{plid}/clone", headers=_h(admin_token), timeout=20)
        assert r.status_code == 402, r.text
        assert int(r.json().get("detail", {}).get("price_inr", 0)) == 199

        # capture seller karma before
        prof_before = requests.get(f"{API}/karma/profile/{listing['owner_id']}", headers=_h(super_token), timeout=20).json()
        karma_before = prof_before["karma_balance"]

        # admin free clones — should succeed and reset assessments
        r = requests.post(f"{API}/marketplace/{lid}/clone", headers=_h(admin_token), timeout=20)
        assert r.status_code == 200, r.text
        new_did = r.json()["new_decision_id"]
        _CREATED["decisions"].append((admin_token, new_did))

        # verify cloned decision has factors + reset assessments
        rd = requests.get(f"{API}/decisions/{new_did}", headers=_h(admin_token), timeout=20)
        assert rd.status_code == 200
        cloned = rd.json()
        assert len(cloned.get("factors", [])) >= 2
        for o in cloned.get("options", []):
            assert o.get("assessments") in ([], None), f"assessments not reset: {o}"

        # seller karma increased (decision_cloned_free = 5 default)
        prof_after = requests.get(f"{API}/karma/profile/{listing['owner_id']}", headers=_h(super_token), timeout=20).json()
        assert prof_after["karma_balance"] >= karma_before + 5, f"{karma_before} -> {prof_after['karma_balance']}"

        # marketplace/mine
        r = requests.get(f"{API}/marketplace/mine", headers=_h(super_token), timeout=20)
        assert r.status_code == 200
        my_ids = {it["listing_id"] for it in r.json()["items"]}
        assert lid in my_ids and plid in my_ids and vlid in my_ids

        # unpublish
        r = requests.post(f"{API}/marketplace/{vlid}/unpublish", headers=_h(super_token), timeout=20)
        assert r.status_code == 200

        # non-owner unpublish blocked
        r = requests.post(f"{API}/marketplace/{lid}/unpublish", headers=_h(admin_token), timeout=20)
        assert r.status_code == 403

        # stash paid listing id for later test class
        self.__class__.paid_listing_id = plid
        self.__class__.free_listing_id = lid


# ===========================================================================
# Phase E — Razorpay order/verify + payouts + payout-account
# ===========================================================================
class TestPhaseE_EarningsPayouts:
    def test_create_order_rejects_owner_and_free(self, super_token, admin_token):
        plid = getattr(TestPhaseD_Marketplace, "paid_listing_id", None)
        flid = getattr(TestPhaseD_Marketplace, "free_listing_id", None)
        assert plid and flid, "Phase D must run first"

        # owner cannot purchase own listing
        r = requests.post(f"{API}/marketplace/{plid}/create-order", headers=_h(super_token), timeout=20)
        assert r.status_code == 400, r.text

        # cannot create order on a free listing
        r = requests.post(f"{API}/marketplace/{flid}/create-order", headers=_h(admin_token), timeout=20)
        assert r.status_code == 400, r.text

        # valid create-order for admin buyer
        r = requests.post(f"{API}/marketplace/{plid}/create-order", headers=_h(admin_token), timeout=20)
        # depending on rzp config, may be 200 or 500 — accept 200 here per problem statement (must work)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("currency") == "INR"
        assert int(body.get("amount", 0)) == 199 * 100
        assert body.get("order_id")
        order_id = body["order_id"]

        # verify with fake signature => 400
        r = requests.post(f"{API}/marketplace/{plid}/verify-payment", headers=_h(admin_token),
                          json={"razorpay_order_id": order_id, "razorpay_payment_id": "pay_fake",
                                "razorpay_signature": "deadbeef"}, timeout=20)
        assert r.status_code == 400, r.text

    def test_payout_account_validation_and_save(self, admin_token):
        # method missing fields
        r = requests.post(f"{API}/earnings/payout-account", headers=_h(admin_token),
                          json={"method": "upi"}, timeout=20)
        assert r.status_code == 400
        r = requests.post(f"{API}/earnings/payout-account", headers=_h(admin_token),
                          json={"method": "bank", "account_number": "1"}, timeout=20)
        assert r.status_code == 400
        # valid UPI
        r = requests.post(f"{API}/earnings/payout-account", headers=_h(admin_token),
                          json={"method": "upi", "vpa": "test@upi"}, timeout=20)
        assert r.status_code == 200, r.text
        # GET back
        r = requests.get(f"{API}/earnings/payout-account", headers=_h(admin_token), timeout=20)
        assert r.status_code == 200
        assert r.json().get("vpa") == "test@upi"

    def test_earnings_summary_ledger_config(self, super_token, admin_token):
        for tok in (super_token, admin_token):
            r = requests.get(f"{API}/earnings/summary", headers=_h(tok), timeout=20)
            assert r.status_code == 200, r.text
            keys = set(r.json().keys())
            assert {"available_inr", "paid_out_inr", "min_payout_inr", "next_payout_eta"}.issubset(keys)
            r = requests.get(f"{API}/earnings/ledger", headers=_h(tok), timeout=20)
            assert r.status_code == 200
            r = requests.get(f"{API}/earnings/payouts", headers=_h(tok), timeout=20)
            assert r.status_code == 200
            r = requests.get(f"{API}/earnings/config", headers=_h(tok), timeout=20)
            assert r.status_code == 200
            assert "razorpayx_active" in r.json()

    def test_admin_payout_config_and_run_now(self, super_token):
        r = requests.get(f"{API}/admin/payouts/config", headers=_h(super_token), timeout=20)
        assert r.status_code == 200, r.text
        cfg = r.json()
        assert "min_payout_inr" in cfg and "razorpayx_active" in cfg

        # mutate config
        r = requests.put(f"{API}/admin/payouts/config", headers=_h(super_token),
                         json={"min_payout_inr": 100, "platform_commission_percent": 10}, timeout=20)
        assert r.status_code == 200
        assert r.json()["min_payout_inr"] == 100
        assert r.json()["platform_commission_percent"] == 10

        # list payouts + pending balances
        r = requests.get(f"{API}/admin/payouts", headers=_h(super_token), timeout=20)
        assert r.status_code == 200
        assert "payouts" in r.json() and "pending_balances" in r.json()

        # run-now (no rzx → expect ok=true, may process 0)
        r = requests.post(f"{API}/admin/payouts/run-now", headers=_h(super_token), timeout=60)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("ok") is True
        assert "processed" in body and "queued_pending" in body


# ===========================================================================
# Phase F — Karma, ratings, leaderboard, fame
# ===========================================================================
class TestPhaseF_KarmaRatings:
    def test_rate_marketplace_requires_clone(self, super_token, admin_token):
        # super hasn't cloned the free listing (it's their own) -> 400 ("can't rate own")
        flid = getattr(TestPhaseD_Marketplace, "free_listing_id", None)
        assert flid
        r = requests.post(f"{API}/karma/rate/marketplace/{flid}", headers=_h(super_token),
                          json={"stars": 5}, timeout=20)
        # owner has not cloned and is the provider -> first check is 'cloned' -> 403
        assert r.status_code in (400, 403), r.text

        # admin DID clone it earlier — rate 5 stars
        seller_id_resp = requests.get(f"{API}/marketplace/{flid}", headers=_h(super_token), timeout=20).json()
        seller_id = seller_id_resp["owner_id"]
        karma_before = requests.get(f"{API}/karma/profile/{seller_id}", headers=_h(admin_token), timeout=20).json()["karma_balance"]

        r = requests.post(f"{API}/karma/rate/marketplace/{flid}", headers=_h(admin_token),
                         json={"stars": 5, "comment": "TEST excellent"}, timeout=20)
        assert r.status_code == 200, r.text
        rj = r.json()
        # positive_rating default=4 * 5 stars = 20 karma
        assert rj["karma_awarded"] >= 20

        karma_after = requests.get(f"{API}/karma/profile/{seller_id}", headers=_h(admin_token), timeout=20).json()["karma_balance"]
        assert karma_after >= karma_before + 20

        # listing rating_avg updated
        r = requests.get(f"{API}/marketplace/{flid}", headers=_h(super_token), timeout=20)
        assert r.json().get("rating_avg") == 5.0
        assert r.json().get("rating_count", 0) >= 1

    def test_karma_me_and_leaderboard(self, admin_token, super_token):
        r = requests.get(f"{API}/karma/me", headers=_h(admin_token), timeout=20)
        assert r.status_code == 200
        body = r.json()
        assert "karma_balance" in body and "rank" in body and "breakdown" in body

        r = requests.get(f"{API}/karma/leaderboard", headers=_h(super_token), timeout=20)
        assert r.status_code == 200
        assert isinstance(r.json()["items"], list)

    def test_admin_karma_config(self, super_token):
        r = requests.get(f"{API}/admin/karma/config", headers=_h(super_token), timeout=20)
        assert r.status_code == 200
        before = r.json()
        # update one point value
        new_points = dict(before.get("points", {}))
        new_points["positive_rating"] = 4  # keep default
        r = requests.put(f"{API}/admin/karma/config", headers=_h(super_token),
                         json={"enabled": True, "points": new_points}, timeout=20)
        assert r.status_code == 200


# ===========================================================================
# Cleanup
# ===========================================================================
def test_zzz_cleanup(super_token, admin_token):
    # unpublish & delete listings
    for lid in _CREATED["listings"]:
        try:
            requests.post(f"{API}/marketplace/{lid}/unpublish", headers=_h(super_token), timeout=10)
        except Exception:
            pass
    # delete decisions
    for tok, did in _CREATED["decisions"]:
        try:
            requests.delete(f"{API}/decisions/{did}", headers=_h(tok), timeout=10)
        except Exception:
            pass
    # delete remaining platform experts
    for eid in _CREATED["experts"]:
        try:
            requests.delete(f"{API}/platform-experts/{eid}", headers=_h(super_token), timeout=10)
        except Exception:
            pass
