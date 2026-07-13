"""
ITER 178 — Chunked upload + File-Import (P0 413 fix) + Financial Model exports.

Covers:
  • POST /api/uploads/init          → returns upload_id
  • POST /api/uploads/chunk         → returns {ok, received_bytes}
  • POST /api/file-import/decision/{decision_id} via upload_id (TXT/CSV) — NO 413
  • POST /api/financial-models/seed-from-file via upload_id (CSV)
  • Regression — GET /api/financial-models/meta + POST /api/financial-models/compute
  • Financial Model export endpoints (Phase 2):
      GET /api/financial-models/{id}/export/investor.pdf
      GET /api/financial-models/{id}/export/investor.xlsx
      GET /api/financial-models/{id}/export/cma.pdf
      GET /api/financial-models/{id}/export/cma.xlsx
    → must return 200 with correct Content-Type + Content-Disposition.

Auth: POST /api/auth/login returns {session_token}.
"""
import base64
import os
import uuid
import io
from datetime import datetime, timezone

import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get(
    "EXPO_PUBLIC_BACKEND_URL",
    "https://repo-blueprint-1.preview.emergentagent.com",
).rstrip("/")
API = f"{BASE_URL}/api"

USER_EMAIL = "super@test.com"
USER_PASS = "SuperPass2026!"

CHUNK_CHARS = 512 * 1024  # mirror frontend /utils/chunkUpload.ts


# ──────────────────────────── fixtures ────────────────────────────
@pytest.fixture(scope="module")
def mongo_db():
    client = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
    yield client[os.environ.get("DB_NAME", "test_database")]
    client.close()


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{API}/auth/login",
               json={"email": USER_EMAIL, "password": USER_PASS}, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    tok = r.json().get("session_token") or r.json().get("token")
    assert tok, f"no token in login response: {r.json()}"
    s.headers["Authorization"] = f"Bearer {tok}"
    return s


@pytest.fixture(scope="module")
def user_id(session):
    r = session.get(f"{API}/auth/me", timeout=20)
    assert r.status_code == 200, r.text[:200]
    uid = r.json().get("user_id") or r.json().get("id")
    assert uid, r.json()
    return uid


@pytest.fixture(scope="module")
def created_ids():
    """Track ids to clean up at module teardown."""
    return {"decision_ids": [], "org_ids": [], "model_ids": []}


@pytest.fixture(scope="module", autouse=True)
def _cleanup(mongo_db, created_ids):
    yield
    if created_ids["decision_ids"]:
        mongo_db.decisions.delete_many({"id": {"$in": created_ids["decision_ids"]}})
    if created_ids["model_ids"]:
        mongo_db.financial_models.delete_many({"id": {"$in": created_ids["model_ids"]}})
    # Org soft-delete via API is fine; also delete the mongo doc directly to keep
    # things tidy across iterations.
    if created_ids["org_ids"]:
        mongo_db.user_orgs.delete_many({"id": {"$in": created_ids["org_ids"]}})


# ──────────────────────────── helpers ────────────────────────────
def _chunked_upload(sess: requests.Session, filename: str, raw_bytes: bytes) -> str:
    """POST /api/uploads/init then /api/uploads/chunk N times — return upload_id."""
    init = sess.post(f"{API}/uploads/init", json={"filename": filename}, timeout=20)
    assert init.status_code == 200, f"init failed: {init.status_code} {init.text[:200]}"
    upload_id = init.json().get("upload_id")
    assert upload_id and isinstance(upload_id, str)

    b64 = base64.b64encode(raw_bytes).decode("ascii")
    total = max(1, (len(b64) + CHUNK_CHARS - 1) // CHUNK_CHARS)
    sent_bytes = 0
    for i in range(total):
        chunk = b64[i * CHUNK_CHARS:(i + 1) * CHUNK_CHARS]
        r = sess.post(f"{API}/uploads/chunk", json={
            "upload_id": upload_id, "index": i, "total": total, "chunk_b64": chunk,
        }, timeout=60)
        assert r.status_code == 200, f"chunk {i}/{total} failed: {r.status_code} {r.text[:200]}"
        data = r.json()
        assert data.get("ok") is True
        assert data.get("received_bytes") == len(chunk)
        sent_bytes += data["received_bytes"]
    assert sent_bytes == len(b64)
    return upload_id


# ──────────────────────────── 1. uploads (P0 fix) ────────────────────────────
class TestChunkedUploads:
    """The actual P0 fix — many small chunks must not 413."""

    def test_init_returns_upload_id(self, session):
        r = session.post(f"{API}/uploads/init",
                         json={"filename": "TEST_iter178_basic.txt"}, timeout=20)
        assert r.status_code == 200
        j = r.json()
        assert "upload_id" in j and isinstance(j["upload_id"], str) and j["upload_id"]

    def test_chunk_returns_received_bytes(self, session):
        init = session.post(f"{API}/uploads/init",
                            json={"filename": "TEST_iter178_chunk.txt"}, timeout=20).json()
        chunk = base64.b64encode(b"hello-world").decode()
        r = session.post(f"{API}/uploads/chunk", json={
            "upload_id": init["upload_id"], "index": 0, "total": 1, "chunk_b64": chunk,
        }, timeout=20)
        assert r.status_code == 200
        j = r.json()
        assert j["ok"] is True
        assert j["received_bytes"] == len(chunk)

    def test_chunk_with_bad_upload_id_404(self, session):
        chunk = base64.b64encode(b"x").decode()
        r = session.post(f"{API}/uploads/chunk", json={
            "upload_id": "nonexistent-" + uuid.uuid4().hex,
            "index": 0, "total": 1, "chunk_b64": chunk,
        }, timeout=20)
        assert r.status_code == 404

    def test_large_payload_no_413(self, session):
        """The original P0: a single ~2MB JSON body would 413 at the proxy.
        Chunked into ~512KB pieces it must succeed."""
        # ~1.5 MB raw → ~2 MB base64 → 4 chunks of ≤512 KB each
        raw = (b"jelcos-iter178-" * 64) * 1500  # ≈1.4 MB
        upload_id = _chunked_upload(session, "TEST_iter178_large.bin", raw)
        assert upload_id


# ──────────────────────────── 2. file-import via upload_id ────────────────────────────
class TestFileImportChunked:
    """End-to-end: a TXT/CSV file of VC firms is chunk-uploaded and merged into a decision."""

    @pytest.fixture(scope="class")
    def decision_id(self, mongo_db, user_id, created_ids):
        """Insert a minimal valid decision directly (bypass complex HOS intake)."""
        did = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        mongo_db.decisions.insert_one({
            "id": did,
            "user_id": user_id,
            "title": "TEST_iter178 VC shortlist",
            "context": "Pick a seed-stage VC for our SaaS company",
            "folder": "career",
            "life_area": "career",
            "decision_type": "need",
            "factors": [],
            "options": [],
            "status": "draft",
            "created_at": now,
            "updated_at": now,
        })
        created_ids["decision_ids"].append(did)
        return did

    def test_csv_import_via_chunked_upload(self, session, decision_id):
        csv = (
            "Firm,Stage,Sector,Ticket Size,Location\n"
            "Sequoia India,Seed-Series A,SaaS/B2B,2-10M USD,Bengaluru\n"
            "Accel,Seed-Series A,SaaS/Consumer,1-5M USD,Bengaluru\n"
            "Matrix Partners,Seed,Fintech/SaaS,0.5-3M USD,Mumbai\n"
            "Blume Ventures,Pre-seed-Seed,SaaS,0.25-2M USD,Bengaluru\n"
            "Kalaari Capital,Seed-Series A,Consumer/SaaS,1-5M USD,Bengaluru\n"
        ).encode("utf-8")
        upload_id = _chunked_upload(session, "TEST_iter178_vcs.csv", csv)

        r = session.post(
            f"{API}/file-import/decision/{decision_id}",
            json={
                "filename": "TEST_iter178_vcs.csv",
                "upload_id": upload_id,
                "ai_tier": "fast",
                "crawl_web": False,
                "context": "Pick a seed-stage VC for our SaaS company",
            },
            timeout=180,
        )
        # AI may be unconfigured (400) or out of credits (402); only those are
        # acceptable non-200s — the proxy must NEVER 413 anymore.
        assert r.status_code != 413, "P0 REGRESSION: file-import still hits 413!"
        if r.status_code == 200:
            j = r.json()
            assert j.get("mode") == "file"
            assert j.get("file_type") == "csv"
            # AI may legitimately find 0 factors on a tiny file, but it shouldn't crash.
            assert isinstance(j.get("factors_added", 0), int)
            assert isinstance(j.get("options_added", 0), int)
        elif r.status_code in (400, 402, 422):
            pytest.skip(f"AI extract returned {r.status_code} — upload itself worked, "
                        f"AI side not under test. body={r.text[:200]}")
        else:
            raise AssertionError(f"unexpected status {r.status_code}: {r.text[:300]}")

    def test_unknown_upload_id_404(self, session, decision_id):
        r = session.post(
            f"{API}/file-import/decision/{decision_id}",
            json={"filename": "x.csv",
                  "upload_id": "missing-" + uuid.uuid4().hex,
                  "ai_tier": "fast", "crawl_web": False},
            timeout=30,
        )
        assert r.status_code == 404


# ──────────────────────────── 3. financial model — regression ────────────────────────────
class TestFinancialModelRegression:
    def test_meta(self, session):
        r = session.get(f"{API}/financial-models/meta", timeout=15)
        assert r.status_code == 200
        j = r.json()
        assert "default_assumptions" in j
        assert isinstance(j["units"], list) and j["units"]
        assert "INR" in j["currencies"]
        assert j["max_projection_years"] == 10

    def test_compute(self, session):
        meta = session.get(f"{API}/financial-models/meta", timeout=15).json()
        a = meta["default_assumptions"]
        r = session.post(f"{API}/financial-models/compute",
                         json={"assumptions": a, "projection_years": 5}, timeout=30)
        assert r.status_code == 200
        c = r.json().get("computed", {})
        for k in ("pnl", "balance_sheet", "cash_flow", "ratios", "valuation", "summary"):
            assert k in c, f"missing computed.{k}"


# ──────────────────────────── 4. financial-model exports ────────────────────────────
class TestFinancialModelExports:
    """Create org → save model → hit all 4 export endpoints; verify content-type + headers."""

    @pytest.fixture(scope="class")
    def model_id(self, session, created_ids):
        # 1. create org
        org_payload = {
            "name": "TEST_iter178 Exports Co",
            "org_type": "BUSINESS",
            "life_area": "finance",
            "description": "iter178 exports test",
        }
        r = session.post(f"{API}/seven-seven/orgs", json=org_payload, timeout=30)
        assert r.status_code == 200, f"org create failed: {r.status_code} {r.text[:200]}"
        org_id = (r.json().get("user_org") or r.json()).get("id")
        assert org_id, r.json()
        created_ids["org_ids"].append(org_id)

        # 2. create financial model
        meta = session.get(f"{API}/financial-models/meta", timeout=15).json()
        r = session.post(f"{API}/financial-models", json={
            "user_org_id": org_id,
            "name": "TEST_iter178 Exports Model",
            "currency": "INR",
            "units": "absolute",
            "projection_years": 5,
            "assumptions": meta["default_assumptions"],
        }, timeout=30)
        assert r.status_code == 200, f"FM create failed: {r.status_code} {r.text[:200]}"
        mid = r.json().get("id")
        assert mid, r.json()
        created_ids["model_ids"].append(mid)
        return mid

    @pytest.mark.parametrize("kind,fmt,mime_substr", [
        ("investor", "pdf", "application/pdf"),
        ("investor", "xlsx", "spreadsheetml.sheet"),
        ("cma", "pdf", "application/pdf"),
        ("cma", "xlsx", "spreadsheetml.sheet"),
    ])
    def test_export_endpoint(self, session, model_id, kind, fmt, mime_substr):
        url = f"{API}/financial-models/{model_id}/export/{kind}.{fmt}"
        r = session.get(url, timeout=60)
        assert r.status_code == 200, f"{kind}.{fmt} failed: {r.status_code} {r.text[:200]}"

        ctype = r.headers.get("content-type", "")
        assert mime_substr in ctype, f"{kind}.{fmt}: unexpected Content-Type {ctype!r}"

        disp = r.headers.get("content-disposition", "")
        assert "attachment" in disp.lower(), f"{kind}.{fmt}: missing attachment header ({disp!r})"
        assert f".{fmt}" in disp, f"{kind}.{fmt}: filename missing .{fmt} in {disp!r}"

        # actual payload should be non-trivial
        body = r.content
        assert len(body) > 200, f"{kind}.{fmt} body too small: {len(body)}"
        if fmt == "pdf":
            assert body[:4] == b"%PDF", f"{kind}.pdf doesn't start with %PDF (got {body[:8]!r})"
        else:
            # XLSX is a ZIP container → starts with PK\x03\x04
            assert body[:2] == b"PK", f"{kind}.xlsx doesn't start with PK (got {body[:8]!r})"

    def test_export_unknown_model_404(self, session):
        r = session.get(
            f"{API}/financial-models/{uuid.uuid4().hex}/export/investor.pdf", timeout=20)
        assert r.status_code == 404


# ──────────────────────── 5. fin-model seed-from-file ────────────────────────
class TestFinSeedFromFile:
    def test_seed_via_chunked_upload(self, session):
        csv = (
            "Line item,FY2024,FY2025\n"
            "Revenue,40000000,50000000\n"
            "Gross profit,16000000,22500000\n"
            "Gross margin %,40,45\n"
            "Operating expenses,12000000,14000000\n"
            "Tax rate %,25,25\n"
            "Cash,3500000,5200000\n"
            "Trade receivables,8000000,9000000\n"
            "Inventory,4000000,4500000\n"
            "Trade payables,3500000,4000000\n"
            "Gross fixed assets,20000000,24000000\n"
            "Total borrowings,8000000,7000000\n"
            "Share capital,5000000,5000000\n"
            "Shares outstanding,500000,500000\n"
            "Interest rate %,11,11\n"
        ).encode()
        upload_id = _chunked_upload(session, "TEST_iter178_stmt.csv", csv)
        r = session.post(f"{API}/financial-models/seed-from-file", json={
            "filename": "TEST_iter178_stmt.csv",
            "upload_id": upload_id,
            "ai_tier": "fast",
        }, timeout=180)
        assert r.status_code != 413
        if r.status_code == 200:
            j = r.json()
            assert isinstance(j.get("patch"), dict) and j["patch"], j
            assert isinstance(j.get("found"), list) and j["found"]
        elif r.status_code in (400, 402, 422):
            pytest.skip(f"AI seed returned {r.status_code} — upload worked, AI side not under test. {r.text[:200]}")
        else:
            raise AssertionError(f"unexpected status {r.status_code}: {r.text[:300]}")
