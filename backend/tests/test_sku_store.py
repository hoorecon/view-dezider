"""
Backend tests — Phase A+B+B+ SKU Store (L1/L2/L3/L4) + L1 PDF unlock flow.

Covers:
  * Public catalog GET /api/store/skus seeded with 4 SKUs at default prices.
  * Admin PUT /api/store/admin/skus/{code} editable; non-admin gets 403.
  * Admin POST /api/store/admin/skus/reset-defaults restores prices.
  * Admin POST /api/store/admin/seed-in-house-solutions idempotent.
  * GET /api/store/my-entitlements + /access-check for fresh user.
  * POST /api/store/purchase creates Razorpay order (L1..L4) and persists.
  * POST /api/store/verify with garbage signature → 400.
  * GET /api/reports/{module}/{decision_id}.pdf:
      - 402 without entitlement
      - After granting L1 entitlement (DB insert), 200 with PDF bytes
      - Idempotent re-download does NOT consume another L1
      - 400 for unknown module
      - 404 for unknown decision_id
"""
import os
import uuid
import time
import requests
import pytest
from datetime import datetime, timezone
from pymongo import MongoClient

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "https://voice-browse-epic.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "AdminPass2026!"
USER_EMAIL = "harden_1777921741@example.com"
USER_PASSWORD = "HardenPass2026!"

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")


# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────
def _login(email: str, pwd: str) -> dict:
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pwd}, timeout=15)
    assert r.status_code == 200, f"Login failed {r.status_code}: {r.text}"
    data = r.json()
    return data


@pytest.fixture(scope="session")
def admin_token():
    return _login(ADMIN_EMAIL, ADMIN_PASSWORD)["session_token"]


@pytest.fixture(scope="session")
def user_session():
    data = _login(USER_EMAIL, USER_PASSWORD)
    return {"token": data["session_token"], "user_id": data["user_id"]}


@pytest.fixture(scope="session")
def mongo_db():
    cl = MongoClient(MONGO_URL)
    db = cl[DB_NAME]
    yield db
    cl.close()


def H(tok: str) -> dict:
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


# ─────────────────────────────────────────────────────────────────────
# 1. Catalog seeding + defaults
# ─────────────────────────────────────────────────────────────────────
class TestCatalog:
    def test_get_skus_seeds_4_skus(self):
        r = requests.get(f"{API}/store/skus", timeout=15)
        assert r.status_code == 200, r.text
        skus = r.json().get("skus") or []
        codes = sorted(s["code"] for s in skus)
        assert {"L1", "L2", "L3", "L4"}.issubset(set(codes))
        # display_order ascending
        ordered = [s for s in skus if s["code"] in ("L1", "L2", "L3", "L4")]
        ordered.sort(key=lambda x: x["display_order"])
        assert [s["code"] for s in ordered] == ["L1", "L2", "L3", "L4"]
        for s in ordered:
            assert s["applies_to_modules"] == ["dezider", "pros_cons", "swot"]
            assert s["quota"] >= 1

    def test_default_prices(self, admin_token):
        # reset first to ensure defaults are in place
        r0 = requests.post(f"{API}/store/admin/skus/reset-defaults", headers=H(admin_token), timeout=15)
        assert r0.status_code == 200, r0.text
        r = requests.get(f"{API}/store/skus", timeout=15)
        skus = {s["code"]: s for s in r.json()["skus"]}
        assert skus["L1"]["price_paise"] == 19900
        assert skus["L2"]["price_paise"] == 99900
        assert skus["L3"]["price_paise"] == 199900
        assert skus["L4"]["price_paise"] == 280000


# ─────────────────────────────────────────────────────────────────────
# 2. Admin updates + role guard + reset
# ─────────────────────────────────────────────────────────────────────
class TestAdmin:
    def test_admin_update_price(self, admin_token):
        new_price = 29900
        r = requests.put(
            f"{API}/store/admin/skus/L1",
            json={"price_paise": new_price},
            headers=H(admin_token),
            timeout=15,
        )
        assert r.status_code == 200, r.text
        assert r.json()["price_paise"] == new_price

        # GET reflects it
        g = requests.get(f"{API}/store/skus/L1", timeout=15)
        assert g.json()["price_paise"] == new_price

        # Reset for downstream tests
        requests.post(f"{API}/store/admin/skus/reset-defaults", headers=H(admin_token), timeout=15)

    def test_non_admin_update_forbidden(self, user_session):
        r = requests.put(
            f"{API}/store/admin/skus/L1",
            json={"price_paise": 12345},
            headers=H(user_session["token"]),
            timeout=15,
        )
        assert r.status_code == 403, r.text

    def test_non_admin_reset_forbidden(self, user_session):
        r = requests.post(
            f"{API}/store/admin/skus/reset-defaults",
            headers=H(user_session["token"]),
            timeout=15,
        )
        assert r.status_code == 403

    def test_seed_in_house_solutions(self, admin_token, mongo_db):
        r = requests.post(
            f"{API}/store/admin/seed-in-house-solutions",
            headers=H(admin_token),
            timeout=15,
        )
        assert r.status_code == 200, r.text
        rows = r.json().get("in_house_solutions") or []
        slugs = {row["slug"] for row in rows}
        assert {"module_dezider", "module_pros_cons", "module_swot"}.issubset(slugs)
        for row in rows:
            assert row["org_id"] == 0
            assert set(["L1", "L2", "L3", "L4"]).issubset(set(row.get("linked_sku_codes") or []))

        # Idempotent — call twice doesn't add duplicates
        r2 = requests.post(
            f"{API}/store/admin/seed-in-house-solutions",
            headers=H(admin_token),
            timeout=15,
        )
        assert r2.status_code == 200
        # count remains 3
        cnt = mongo_db.solutions_store.count_documents(
            {"org_id": 0, "slug": {"$in": ["module_dezider", "module_pros_cons", "module_swot"]}}
        )
        assert cnt == 3

    def test_non_admin_seed_forbidden(self, user_session):
        r = requests.post(
            f"{API}/store/admin/seed-in-house-solutions",
            headers=H(user_session["token"]),
            timeout=15,
        )
        assert r.status_code == 403


# ─────────────────────────────────────────────────────────────────────
# 3. Entitlements + access-check
# ─────────────────────────────────────────────────────────────────────
class TestEntitlements:
    def test_my_entitlements_shape(self, user_session, mongo_db):
        # Clear any entitlements for clean state
        mongo_db.user_entitlements.delete_many({"user_id": user_session["user_id"]})
        mongo_db.decision_report_unlocks.delete_many({"user_id": user_session["user_id"]})

        r = requests.get(f"{API}/store/my-entitlements", headers=H(user_session["token"]), timeout=15)
        assert r.status_code == 200
        body = r.json()
        assert "entitlements" in body and "raw" in body
        assert body["entitlements"] == []
        assert body["raw"] == []

    def test_access_check_no_access(self, user_session):
        r = requests.get(
            f"{API}/store/access-check",
            params={"module": "swot"},
            headers=H(user_session["token"]),
            timeout=15,
        )
        assert r.status_code == 200
        # Without subscription/entitlement
        assert r.json().get("has_access") is False


# ─────────────────────────────────────────────────────────────────────
# 4. Purchase order creation
# ─────────────────────────────────────────────────────────────────────
class TestPurchase:
    @pytest.mark.parametrize("code,expected_amount", [
        ("L1", 19900),
        ("L2", 99900),
        ("L3", 199900),
        ("L4", 280000),
    ])
    def test_create_purchase_order(self, user_session, mongo_db, code, expected_amount):
        r = requests.post(
            f"{API}/store/purchase",
            json={"sku_code": code},
            headers=H(user_session["token"]),
            timeout=20,
        )
        if r.status_code == 500 and "gateway not configured" in r.text.lower():
            pytest.skip("Razorpay not configured in this env")
        assert r.status_code == 200, f"{code}: {r.text}"
        body = r.json()
        assert body["order_id"].startswith("order_")
        assert body["amount"] == expected_amount
        assert body["currency"] == "INR"
        assert body["key_id"]
        assert body["sku"]["code"] == code
        # Persisted in payment_orders
        doc = mongo_db.payment_orders.find_one({"order_id": body["order_id"]})
        assert doc is not None
        assert doc["type"] == "sku_purchase"
        assert doc["sku_code"] == code


# ─────────────────────────────────────────────────────────────────────
# 5. Verify endpoint with forged signature
# ─────────────────────────────────────────────────────────────────────
class TestVerify:
    def test_garbage_signature_400(self, user_session):
        # First create an order
        order_r = requests.post(
            f"{API}/store/purchase",
            json={"sku_code": "L1"},
            headers=H(user_session["token"]),
            timeout=20,
        )
        if order_r.status_code != 200:
            pytest.skip("Cannot create order to verify")
        oid = order_r.json()["order_id"]
        r = requests.post(
            f"{API}/store/verify",
            json={
                "razorpay_order_id": oid,
                "razorpay_payment_id": "pay_FAKEFAKE12345",
                "razorpay_signature": "deadbeef" * 8,
            },
            headers=H(user_session["token"]),
            timeout=15,
        )
        assert r.status_code == 400, r.text
        assert "signature" in r.text.lower() or "mismatch" in r.text.lower()


# ─────────────────────────────────────────────────────────────────────
# 6. PDF unlock flow (L1 grant via DB → download → idempotent)
# ─────────────────────────────────────────────────────────────────────
class TestPdfFlow:
    @pytest.fixture
    def swot_doc(self, user_session, mongo_db):
        """Insert a minimal SWOT analysis owned by the test user."""
        did = f"TEST_SWOT_{uuid.uuid4().hex[:8]}"
        doc = {
            "id": did,
            "user_id": user_session["user_id"],
            "title": "TEST SWOT for PDF flow",
            "context": "Testing PDF L1 unlock",
            "strengths": [{"text": "Strong team", "impact": "high"}],
            "weaknesses": [{"text": "Low budget", "impact": "medium"}],
            "opportunities": [{"text": "Growing market", "impact": "high"}],
            "threats": [{"text": "Competition", "impact": "medium"}],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        mongo_db.swot_analyses.insert_one(doc)
        yield did
        mongo_db.swot_analyses.delete_one({"id": did})
        mongo_db.decision_report_unlocks.delete_many({"key": f"swot:{did}"})

    @pytest.fixture
    def dezider_doc(self, user_session, mongo_db):
        did = f"TEST_DEZ_{uuid.uuid4().hex[:8]}"
        mongo_db.decisions.insert_one({
            "id": did,
            "user_id": user_session["user_id"],
            "title": "TEST Dezider PDF",
            "context": "context",
            "decision_type": "career",
            "life_area": "Career",
            "options": [{"name": "Opt A", "final_score": 7.5}],
            "factors": [{"name": "Cost", "weightage": 5, "polarity": "negative"}],
            "final_decision": "Opt A wins",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        yield did
        mongo_db.decisions.delete_one({"id": did})
        mongo_db.decision_report_unlocks.delete_many({"key": f"dezider:{did}"})

    @pytest.fixture
    def pros_cons_doc(self, user_session, mongo_db):
        did = f"TEST_PC_{uuid.uuid4().hex[:8]}"
        mongo_db.pros_cons_analyses.insert_one({
            "id": did,
            "user_id": user_session["user_id"],
            "title": "TEST Pros&Cons PDF",
            "context": "ctx",
            "options": [{
                "name": "Option Alpha",
                "pros": [{"text": "Pro1"}],
                "cons": [{"text": "Con1"}],
            }],
            "final_decision": "Alpha",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        yield did
        mongo_db.pros_cons_analyses.delete_one({"id": did})
        mongo_db.decision_report_unlocks.delete_many({"key": f"pros_cons:{did}"})

    def _clear_user_entitlements(self, mongo_db, user_id):
        mongo_db.user_entitlements.delete_many({"user_id": user_id})

    def _grant_l1(self, mongo_db, user_id, qty=1):
        mongo_db.user_entitlements.insert_one({
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "sku_code": "L1",
            "balance": qty,
            "granted_qty": qty,
            "consumed_qty": 0,
            "source_order_id": "test_grant",
            "granted_at": datetime.now(timezone.utc).isoformat(),
            "last_used_at": None,
            "status": "active",
        })

    def test_report_info(self, user_session, swot_doc, mongo_db):
        self._clear_user_entitlements(mongo_db, user_session["user_id"])
        r = requests.get(
            f"{API}/reports/swot/{swot_doc}/info",
            headers=H(user_session["token"]),
            timeout=15,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["unlocked"] is False
        assert body["l1_balance"] == 0
        assert body["l2_balance"] == 0

    def test_pdf_402_without_entitlement(self, user_session, swot_doc, mongo_db):
        self._clear_user_entitlements(mongo_db, user_session["user_id"])
        mongo_db.decision_report_unlocks.delete_many({"key": f"swot:{swot_doc}"})
        r = requests.get(
            f"{API}/reports/swot/{swot_doc}.pdf",
            headers=H(user_session["token"]),
            timeout=15,
        )
        assert r.status_code == 402, f"Expected 402 got {r.status_code}: {r.text[:200]}"

    def test_pdf_unlock_with_l1_and_idempotent(self, user_session, swot_doc, mongo_db):
        self._clear_user_entitlements(mongo_db, user_session["user_id"])
        mongo_db.decision_report_unlocks.delete_many({"key": f"swot:{swot_doc}"})
        self._grant_l1(mongo_db, user_session["user_id"], qty=2)

        # First download → 200 + PDF
        r = requests.get(
            f"{API}/reports/swot/{swot_doc}.pdf",
            headers=H(user_session["token"]),
            timeout=20,
        )
        assert r.status_code == 200, r.text[:300]
        assert r.headers.get("content-type", "").startswith("application/pdf")
        assert r.content[:4] == b"%PDF"

        # L1 balance went from 2 -> 1
        info = requests.get(
            f"{API}/reports/swot/{swot_doc}/info",
            headers=H(user_session["token"]),
            timeout=15,
        ).json()
        assert info["unlocked"] is True
        assert info["l1_balance"] == 1

        # Second download for same decision → still 200, no further consumption
        r2 = requests.get(
            f"{API}/reports/swot/{swot_doc}.pdf",
            headers=H(user_session["token"]),
            timeout=20,
        )
        assert r2.status_code == 200
        info2 = requests.get(
            f"{API}/reports/swot/{swot_doc}/info",
            headers=H(user_session["token"]),
            timeout=15,
        ).json()
        assert info2["l1_balance"] == 1, f"L1 should be idempotent, got {info2['l1_balance']}"

    def test_pdf_dezider_module(self, user_session, dezider_doc, mongo_db):
        self._clear_user_entitlements(mongo_db, user_session["user_id"])
        self._grant_l1(mongo_db, user_session["user_id"])
        r = requests.get(
            f"{API}/reports/dezider/{dezider_doc}.pdf",
            headers=H(user_session["token"]),
            timeout=20,
        )
        assert r.status_code == 200, r.text[:300]
        assert r.content[:4] == b"%PDF"

    def test_pdf_pros_cons_module(self, user_session, pros_cons_doc, mongo_db):
        self._clear_user_entitlements(mongo_db, user_session["user_id"])
        self._grant_l1(mongo_db, user_session["user_id"])
        r = requests.get(
            f"{API}/reports/pros_cons/{pros_cons_doc}.pdf",
            headers=H(user_session["token"]),
            timeout=20,
        )
        assert r.status_code == 200, r.text[:300]
        assert r.content[:4] == b"%PDF"

    def test_pdf_404_unknown_decision(self, user_session, mongo_db):
        self._clear_user_entitlements(mongo_db, user_session["user_id"])
        self._grant_l1(mongo_db, user_session["user_id"])
        r = requests.get(
            f"{API}/reports/swot/DOES_NOT_EXIST_{uuid.uuid4().hex[:6]}.pdf",
            headers=H(user_session["token"]),
            timeout=15,
        )
        assert r.status_code == 404

    def test_pdf_400_unknown_module(self, user_session, mongo_db):
        self._clear_user_entitlements(mongo_db, user_session["user_id"])
        self._grant_l1(mongo_db, user_session["user_id"])
        r = requests.get(
            f"{API}/reports/garbage_module/somethign.pdf",
            headers=H(user_session["token"]),
            timeout=15,
        )
        assert r.status_code == 400
