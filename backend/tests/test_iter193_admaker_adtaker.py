"""Iter 193 — FRAME: Sponsored Solutions (AdMaker) + AdTaker widgets.

Covers:
  • core.ad_auction pure math — GSP pricing, AdRank ordering, quality gate,
    region + calendar + daily-hour (dayparting, overnight wrap) targeting
  • ai-wallet globals finder_min_cutoff_pct / finder_sponsored_n (PUT/GET)
  • CCM node override via PUT /catalog/nodes/{id} + /admaker/resolve-config
    (inheritance + -1 clears)
  • AdMaker bid CRUD + validation
  • Finder run returns organic Top-N UNCHANGED + sponsored BELOW (bid target
    above cutoff) + /admaker/track CPC charge
  • AdTaker publisher CRUD, widget.js, embed (impression), track (click),
    clone?ref → conversion, stats + earnings estimate
"""
import sys
import uuid
from datetime import datetime, timezone

import pytest
import requests
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")
sys.path.insert(0, "/app/backend")

from core.ad_auction import bid_is_live, score_bids  # noqa: E402


def _base_url() -> str:
    with open("/app/frontend/.env") as f:
        for line in f:
            line = line.strip()
            if line.startswith("EXPO_PUBLIC_BACKEND_URL="):
                return line.split("=", 1)[1].strip().rstrip("/")
    raise RuntimeError("EXPO_PUBLIC_BACKEND_URL not found")


BASE_URL = _base_url()
API = f"{BASE_URL}/api"
def _resolve_bmc() -> str:
    """The live Business Model Chooser Decider App (replaced bmp-55-patterns)."""
    import requests as _rq
    r = _rq.get(f"{API}/decider-store", timeout=30)
    return next(t["template_id"] for t in r.json()["templates"]
                if t.get("title") == "Business Model Chooser")


BMP = _resolve_bmc()
SUPER_EMAIL, SUPER_PASS = "super@test.com", "SuperPass2026!"


@pytest.fixture(scope="module")
def s():
    return requests.Session()


@pytest.fixture(scope="module")
def H(s):
    r = s.post(f"{API}/auth/login", json={"email": SUPER_EMAIL, "password": SUPER_PASS}, timeout=30)
    assert r.status_code == 200, f"login failed {r.status_code} {r.text[:200]}"
    return {"Authorization": f"Bearer {r.json()['session_token']}"}


# ═══════════════════════ pure auction math ═══════════════════════
class TestAuctionMath:
    ELIGIBLE = [
        {"option_id": "o1", "name": "Alpha", "worth_percentage": 90.0},
        {"option_id": "o2", "name": "Beta", "worth_percentage": 80.0},
        {"option_id": "o3", "name": "Gamma", "worth_percentage": 60.0},
    ]

    def test_adrank_beats_raw_bid(self):
        # Beta bids more but Alpha's quality wins: 500×0.9=450 > 520×0.8=416
        bids = [
            {"bid_id": "b1", "advertiser_name": "A", "option_name": "alpha", "bid_paise": 500},
            {"bid_id": "b2", "advertiser_name": "B", "option_name": "Beta ", "bid_paise": 520},
        ]
        w = score_bids(bids, self.ELIGIBLE, 2)
        assert [x["option_id"] for x in w] == ["o1", "o2"]
        assert w[0]["slot"] == 1 and w[1]["slot"] == 2

    def test_gsp_price_second_rank_over_own_qs(self):
        bids = [
            {"bid_id": "b1", "advertiser_name": "A", "option_name": "Alpha", "bid_paise": 500},
            {"bid_id": "b2", "advertiser_name": "B", "option_name": "Beta", "bid_paise": 300},
        ]
        w = score_bids(bids, self.ELIGIBLE, 2)
        # winner1 pays next_adrank/own_qs + 1 = (300*0.8)/0.9 + 1 = 267
        assert w[0]["price_paise"] == int(300 * 0.8 / 0.9) + 1
        assert w[0]["price_paise"] <= w[0]["bid_paise"]
        assert w[1]["price_paise"] == 1  # last winner pays reserve

    def test_bid_on_below_cutoff_option_never_wins(self):
        bids = [{"bid_id": "b1", "advertiser_name": "A", "option_name": "Omega", "bid_paise": 99999}]
        assert score_bids(bids, self.ELIGIBLE, 3) == []

    def test_one_slot_per_option_strongest_bid(self):
        bids = [
            {"bid_id": "low", "advertiser_name": "L", "option_name": "Alpha", "bid_paise": 100},
            {"bid_id": "high", "advertiser_name": "H", "option_name": "Alpha", "bid_paise": 400},
        ]
        w = score_bids(bids, self.ELIGIBLE, 3)
        assert len(w) == 1 and w[0]["bid_id"] == "high"

    def test_sponsored_n_caps_slots(self):
        bids = [{"bid_id": f"b{i}", "advertiser_name": "X", "option_name": n, "bid_paise": 100}
                for i, n in enumerate(["Alpha", "Beta", "Gamma"])]
        assert len(score_bids(bids, self.ELIGIBLE, 2)) == 2

    def test_region_and_status_targeting(self):
        base = {"bid_id": "b", "status": "active", "bid_paise": 100}
        assert bid_is_live({**base, "region": "global"}, region="in")
        assert bid_is_live({**base, "region": "IN "}, region="in")
        assert not bid_is_live({**base, "region": "us"}, region="in")
        assert not bid_is_live({**base, "status": "paused"}, region="in")
        assert not bid_is_live({**base, "budget_paise": 100, "spent_paise": 100}, region="in")

    def test_calendar_and_daily_hours(self):
        now = datetime(2026, 7, 19, 10, 0, tzinfo=timezone.utc)  # 15:30 IST
        base = {"bid_id": "b", "status": "active", "bid_paise": 100, "region": "global"}
        assert bid_is_live({**base, "slot_start": "2026-07-01", "slot_end": "2026-07-31"}, now=now)
        assert not bid_is_live({**base, "slot_start": "2026-08-01"}, now=now)
        assert not bid_is_live({**base, "slot_end": "2026-07-01"}, now=now)
        ist = {**base, "timezone": "Asia/Kolkata"}
        assert bid_is_live({**ist, "daily_start_hour": 9, "daily_end_hour": 18}, now=now)
        assert not bid_is_live({**ist, "daily_start_hour": 18, "daily_end_hour": 22}, now=now)
        # overnight wrap 22→06 IST does NOT include 15:30 IST
        assert not bid_is_live({**ist, "daily_start_hour": 22, "daily_end_hour": 6}, now=now)


# ═══════════════════ globals + CCM inheritance ═══════════════════
class TestCutoffConfig:
    def test_global_defaults_roundtrip(self, s, H):
        r = s.put(f"{API}/admin/ai-wallet/config",
                  json={"finder_min_cutoff_pct": 55, "finder_sponsored_n": 4}, headers=H, timeout=30)
        assert r.status_code == 200
        g = s.get(f"{API}/admin/ai-wallet/config", headers=H, timeout=30).json()
        assert g["finder_min_cutoff_pct"] == 55 and g["finder_sponsored_n"] == 4
        # restore
        s.put(f"{API}/admin/ai-wallet/config",
              json={"finder_min_cutoff_pct": 60, "finder_sponsored_n": 3}, headers=H, timeout=30)

    def test_node_override_and_clear(self, s, H):
        nodes = s.get(f"{API}/catalog/nodes?level=0", headers=H, timeout=30).json()["items"]
        assert nodes, "catalog not seeded"
        nid = nodes[0]["node_id"]
        r = s.put(f"{API}/catalog/nodes/{nid}",
                  json={"finder_min_cutoff_pct": 75, "finder_sponsored_n": 2}, headers=H, timeout=30)
        assert r.status_code == 200
        assert r.json()["finder_ad_config"] == {"min_cutoff_pct": 75.0, "sponsored_n": 2}
        eff = s.get(f"{API}/admaker/resolve-config?node_id={nid}", headers=H, timeout=30).json()
        assert eff["min_cutoff_pct"] == 75 and eff["sponsored_n"] == 2
        assert eff["cutoff_source"]["node_id"] == nid
        # child inherits from this L0 ancestor
        kids = s.get(f"{API}/catalog/nodes?life_area_id={nodes[0]['life_area_id']}&level=1",
                     headers=H, timeout=30).json()["items"]
        if kids:
            keff = s.get(f"{API}/admaker/resolve-config?node_id={kids[0]['node_id']}",
                         headers=H, timeout=30).json()
            assert keff["min_cutoff_pct"] == 75
            assert keff["cutoff_source"]["node_id"] == nid
        # -1 clears → back to global
        r = s.put(f"{API}/catalog/nodes/{nid}",
                  json={"finder_min_cutoff_pct": -1, "finder_sponsored_n": -1}, headers=H, timeout=30)
        assert r.status_code == 200 and r.json()["finder_ad_config"] == {}
        eff = s.get(f"{API}/admaker/resolve-config?node_id={nid}", headers=H, timeout=30).json()
        assert eff["cutoff_source"] == "global"


# ═══════════════ AdMaker CRUD + Finder integration ═══════════════
class TestAdMakerEndToEnd:
    @pytest.fixture(scope="class")
    def decision(self, s, H):
        r = s.post(f"{API}/decider-store/{BMP}/clone", json={"mode": "full"}, headers=H, timeout=60)
        assert r.status_code == 200, r.text[:300]
        did = r.json()["decision_id"]
        # v2 checkbox app: value-role children only score when SELECTED —
        # tick one value (Solo >= 1) so options have a scoring basis.
        dec = s.get(f"{API}/decisions/{did}", headers=H, timeout=30).json()
        factors = dec["factors"]
        solo = next(f for f in factors if f["name"] == "Solo" and f.get("parent_id"))
        solo.update({"operator": ">=", "expected_value": 1, "data_type": "numeric"})
        r = s.put(f"{API}/decisions/{did}", json={"factors": factors}, headers=H, timeout=30)
        assert r.status_code == 200, r.text[:300]
        yield did
        s.delete(f"{API}/decisions/{did}", headers=H, timeout=30)

    def test_bid_validation(self, s, H):
        assert s.post(f"{API}/admaker/bids", json={"template_id": "nope", "option_name": "x",
                      "advertiser_name": "y", "bid_paise": 100}, headers=H, timeout=30).status_code == 404
        assert s.post(f"{API}/admaker/bids", json={"template_id": BMP, "option_name": "x",
                      "advertiser_name": "y", "bid_paise": 0}, headers=H, timeout=30).status_code == 400
        assert s.post(f"{API}/admaker/bids", json={"template_id": BMP, "option_name": "x",
                      "advertiser_name": "y", "bid_paise": 100, "timezone": "Not/AZone"},
                      headers=H, timeout=30).status_code == 400

    def test_sponsored_below_organic_and_cpc(self, s, H, decision):
        # Baseline run — organic snapshot, no bids yet.
        r0 = s.post(f"{API}/decisions/{decision}/finder/run", json={"top_n": 5}, headers=H, timeout=60)
        assert r0.status_code == 200
        base = r0.json()
        assert base["sponsored"] == [] and "ad_config" in base
        assert base["ranked"], "no ranked options"
        target = base["ranked"][0]  # best option — certainly above any cutoff
        organic_ids = [x["option_id"] for x in base["top"]]

        # Place a bid on the top option (cutoff-eligible by construction).
        r = s.post(f"{API}/admaker/bids", json={
            "template_id": BMP, "option_name": target["name"],
            "advertiser_name": "PyTest Ads", "bid_paise": 700, "region": "global",
        }, headers=H, timeout=30)
        assert r.status_code == 200
        bid_id = r.json()["bid_id"]
        try:
            r1 = s.post(f"{API}/decisions/{decision}/finder/run",
                        json={"top_n": 5, "min_cutoff_pct_ignored": True}, headers=H, timeout=60)
            assert r1.status_code == 200
            res = r1.json()
            # organic unchanged by money
            assert [x["option_id"] for x in res["top"]] == organic_ids
            spon = res["sponsored"]
            assert len(spon) == 1 and spon[0]["bid_id"] == bid_id
            assert spon[0]["advertiser_name"] == "PyTest Ads"
            assert "bid_paise" not in spon[0] and "price_paise" not in spon[0]
            # impression recorded
            bids = s.get(f"{API}/admaker/bids?template_id={BMP}", headers=H, timeout=30).json()["bids"]
            mine = next(b for b in bids if b["bid_id"] == bid_id)
            assert mine["impressions"] >= 1 and mine["last_price_paise"] >= 1
            # CPC click charge
            rc = s.post(f"{API}/admaker/track",
                        json={"bid_id": bid_id, "decision_id": decision}, headers=H, timeout=30)
            assert rc.status_code == 200 and rc.json()["charged_paise"] >= 1
            bids = s.get(f"{API}/admaker/bids?template_id={BMP}", headers=H, timeout=30).json()["bids"]
            mine = next(b for b in bids if b["bid_id"] == bid_id)
            assert mine["clicks"] == 1 and mine["spent_paise"] == rc.json()["charged_paise"]
            # pause → disappears from auction
            s.put(f"{API}/admaker/bids/{bid_id}", json={"status": "paused"}, headers=H, timeout=30)
            r2 = s.post(f"{API}/decisions/{decision}/finder/run", json={"top_n": 5}, headers=H, timeout=60)
            assert r2.json()["sponsored"] == []
        finally:
            s.delete(f"{API}/admaker/bids/{bid_id}", headers=H, timeout=30)


# ═══════════════════════ AdTaker Program ═══════════════════════
class TestAdTaker:
    @pytest.fixture(scope="class")
    def pub(self, s, H):
        r = s.post(f"{API}/adtaker/publishers",
                   json={"name": f"PyTest Pub {uuid.uuid4().hex[:5]}", "site_url": "https://example.org"},
                   headers=H, timeout=30)
        assert r.status_code == 200
        p = r.json()
        assert p["tracker_id"].startswith("DZ-PUB-") and p["revenue_share_pct"] == 68.0
        yield p
        s.delete(f"{API}/adtaker/publishers/{p['publisher_id']}", headers=H, timeout=30)

    def test_widget_and_embed_and_events(self, s, H, pub):
        t = pub["tracker_id"]
        w = s.get(f"{API}/adtaker/widget.js?tracker={t}&app={BMP}", timeout=30)
        assert w.status_code == 200 and "javascript" in w.headers["content-type"]
        assert t in w.text and BMP in w.text
        e = s.get(f"{API}/adtaker/embed/{BMP}?tracker={t}", timeout=30)  # logs impression
        assert e.status_code == 200 and "Open Decider App" in e.text
        assert e.headers.get("content-security-policy") == "frame-ancestors *"
        assert s.get(f"{API}/adtaker/embed/{BMP}?tracker=DZ-PUB-FAKE0000", timeout=30).status_code == 404
        # public click beacon
        c = s.post(f"{API}/adtaker/track",
                   json={"tracker": t, "template_id": BMP, "event": "click"}, timeout=30)
        assert c.status_code == 200 and c.json()["ok"]
        assert s.post(f"{API}/adtaker/track",
                      json={"tracker": t, "template_id": BMP, "event": "bogus"}, timeout=30).status_code == 400
        # conversion via clone?ref
        r = s.post(f"{API}/decider-store/{BMP}/clone", json={"mode": "full", "ref": t}, headers=H, timeout=60)
        assert r.status_code == 200
        did = r.json()["decision_id"]
        try:
            st = s.get(f"{API}/adtaker/publishers/{pub['publisher_id']}/stats?days=7",
                       headers=H, timeout=30).json()
            assert st["totals"]["impressions"] >= 1
            assert st["totals"]["clicks"] >= 1
            assert st["totals"]["conversions"] >= 1
            assert st["earnings_estimate_paise"] >= int(500 * 0.68)
        finally:
            s.delete(f"{API}/decisions/{did}", headers=H, timeout=30)

    def test_publisher_listing_totals(self, s, H, pub):
        pubs = s.get(f"{API}/adtaker/publishers", headers=H, timeout=30).json()["publishers"]
        mine = next(p for p in pubs if p["publisher_id"] == pub["publisher_id"])
        assert mine["totals"]["impressions"] >= 1
