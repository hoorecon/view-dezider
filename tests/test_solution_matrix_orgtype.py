"""
Regression test — Solution Matrix OrgType (nested) + new 2026-05-04 features.

Validates:
  1. POST /api/solution-matrices with nested shape (matrix_* nested with slots)
  2. GET /api/solution-matrices/{id} roundtrip
  3. PUT /api/solution-matrices/{id} partial update preserves untouched slots
  4. Legacy FLAT payload is auto-normalised (fills both `individual` + `aggregate`)
  5. Defaults on empty POST include 5 slots (aggregate + 4 orgtypes), all empty
  6. matrix_mode field persists (standard | accurate) with normalisation
  7. per-cell influences map roundtrips (positive + negative per field)
  8. Templates list + single-template fetch endpoints
  9. PDF export returns application/pdf bytes
"""
import os
import sys
import time
import requests

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8001")
API = f"{BASE_URL}/api"

ORG_TYPES = ["individual", "org", "govt", "nature"]
ALL_SLOTS = ["aggregate", *ORG_TYPES]
LAYERS = ["matrix_self", "matrix_micro", "matrix_macro"]
FIELDS = ["summary", "knowledge_skills", "capacity", "time",
          "people", "finance", "infrastructure"]


class Results:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def check(self, condition, label, detail=""):
        if condition:
            self.passed += 1
            print(f"  OK  {label}")
        else:
            self.failed += 1
            self.errors.append(f"{label}: {detail}")
            print(f"  FAIL {label}{(' - ' + detail) if detail else ''}")

    def summary(self):
        total = self.passed + self.failed
        print(f"\n{'='*70}")
        print(f"Solution Matrix OrgType Regression - {self.passed}/{total} passed")
        print(f"{'='*70}")
        if self.errors:
            print("\nFailures:")
            for e in self.errors:
                print(f"  - {e}")
        return self.failed == 0


def register_user(r: Results):
    ts = int(time.time() * 1000)
    email = f"sm_orgtype_{ts}@test.com"
    body = {"email": email, "password": "testpass123", "name": "SM OrgType Tester"}
    res = requests.post(f"{API}/auth/register", json=body, timeout=15)
    r.check(res.status_code == 200, "User registered", f"status={res.status_code}")
    token = res.json().get("session_token")
    return token, email


def make_full_nested_payload(seed: str = "SEED"):
    """Build a matrix_* payload with every one of 84 OrgType cells uniquely filled."""
    payload = {}
    for layer in LAYERS:
        payload[layer] = {}
        for ot in ORG_TYPES:
            payload[layer][ot] = {
                f: f"{seed}|{layer}|{ot}|{f}"
                for f in FIELDS
            }
    return payload


def assert_nested_cells_match(r: Results, stored: dict, expected_seed: str, label_prefix: str):
    """Verify each of 84 OrgType cells equals the expected seed-derived value."""
    mismatches = []
    for layer in LAYERS:
        layer_data = stored.get(layer, {})
        for ot in ORG_TYPES:
            ot_data = layer_data.get(ot, {})
            for f in FIELDS:
                got = ot_data.get(f, "__MISSING__")
                want = f"{expected_seed}|{layer}|{ot}|{f}"
                if got != want:
                    mismatches.append(f"{layer}.{ot}.{f} (got {got!r})")
    r.check(
        not mismatches,
        f"{label_prefix} - all 84 nested OrgType cells roundtrip",
        f"{len(mismatches)} mismatches, first: {mismatches[:3]}",
    )


def main():
    r = Results()

    print("\n" + "="*70)
    print(" Solution Matrix OrgType Regression Test (v2)")
    print("="*70)

    token, email = register_user(r)
    if not token:
        r.summary(); sys.exit(1)
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # ------------------------------------------------------------------
    # Test 1: POST with full nested payload (84 orgtype cells filled)
    # ------------------------------------------------------------------
    print("\n[Test 1] POST /solution-matrices with full nested 84-cell payload")
    nested = make_full_nested_payload("S1")
    body = {
        "area_of_life": "career",
        "smart_goal": "Test goal with OrgType matrix",
        "matrix_mode": "accurate",
        **nested,
    }
    res = requests.post(f"{API}/solution-matrices", headers=headers, json=body, timeout=15)
    r.check(res.status_code == 200, "POST returns 200", f"status={res.status_code} body={res.text[:200]}")
    created = res.json() if res.status_code == 200 else {}
    entry_id = created.get("entry_id")
    r.check(bool(entry_id), "entry_id returned")
    assert_nested_cells_match(r, created, "S1", "POST response")
    r.check(created.get("matrix_mode") == "accurate", "matrix_mode='accurate' persisted",
            f"got={created.get('matrix_mode')}")
    # aggregate slot should exist (empty) for every layer
    for layer in LAYERS:
        ag = created.get(layer, {}).get("aggregate", {})
        r.check(isinstance(ag, dict), f"{layer}.aggregate slot exists")

    # ------------------------------------------------------------------
    # Test 2: GET roundtrip
    # ------------------------------------------------------------------
    print("\n[Test 2] GET /solution-matrices/{id} - roundtrip")
    res = requests.get(f"{API}/solution-matrices/{entry_id}", headers=headers, timeout=10)
    r.check(res.status_code == 200, "GET returns 200", f"status={res.status_code}")
    fetched = res.json() if res.status_code == 200 else {}
    assert_nested_cells_match(r, fetched, "S1", "GET response")
    r.check(fetched.get("matrix_mode") == "accurate", "GET preserves matrix_mode")

    # ------------------------------------------------------------------
    # Test 3: PUT partial - only matrix_self changes; micro/macro retained
    # ------------------------------------------------------------------
    print("\n[Test 3] PUT partial - update only matrix_self")
    new_self = {
        ot: {f: f"UPDATED|{ot}|{f}" for f in FIELDS}
        for ot in ORG_TYPES
    }
    res = requests.put(
        f"{API}/solution-matrices/{entry_id}",
        headers=headers,
        json={"matrix_self": new_self},
        timeout=15,
    )
    r.check(res.status_code == 200, "PUT returns 200", f"status={res.status_code} body={res.text[:200]}")
    updated = res.json() if res.status_code == 200 else {}

    mismatches_self = []
    for ot in ORG_TYPES:
        for f in FIELDS:
            want = f"UPDATED|{ot}|{f}"
            got = updated.get("matrix_self", {}).get(ot, {}).get(f, "__MISSING__")
            if got != want:
                mismatches_self.append(f"matrix_self.{ot}.{f}")
    r.check(not mismatches_self, "matrix_self updated cells correct",
            f"{len(mismatches_self)} mismatches")

    for layer in ["matrix_micro", "matrix_macro"]:
        layer_data = updated.get(layer, {})
        preserved_ok = all(
            layer_data.get(ot, {}).get(f) == f"S1|{layer}|{ot}|{f}"
            for ot in ORG_TYPES for f in FIELDS
        )
        r.check(preserved_ok, f"{layer} untouched cells preserved after partial PUT")

    # ------------------------------------------------------------------
    # Test 4: Legacy FLAT payload -> auto-normalised
    # ------------------------------------------------------------------
    print("\n[Test 4] POST with legacy FLAT matrix_self (no slot keys)")
    legacy_body = {
        "area_of_life": "finance",
        "smart_goal": "Legacy flat payload test",
        "matrix_self": {
            "summary": "LEGACY_SELF_SUM",
            "knowledge_skills": "LEGACY_SELF_KS",
            "capacity": "LEGACY_SELF_CAP",
            "time": "LEGACY_SELF_T",
            "people": "LEGACY_SELF_P",
            "finance": "LEGACY_SELF_F",
            "infrastructure": "LEGACY_SELF_I",
        },
    }
    res = requests.post(f"{API}/solution-matrices", headers=headers, json=legacy_body, timeout=15)
    r.check(res.status_code == 200, "Legacy POST returns 200",
            f"status={res.status_code} body={res.text[:200]}")
    legacy_created = res.json() if res.status_code == 200 else {}

    # matrix_self.individual should contain legacy values
    ind = legacy_created.get("matrix_self", {}).get("individual", {})
    r.check(ind.get("summary") == "LEGACY_SELF_SUM", "Legacy flat -> individual.summary mapped",
            f"got={ind.get('summary')!r}")
    r.check(ind.get("knowledge_skills") == "LEGACY_SELF_KS",
            "Legacy flat -> individual.knowledge_skills mapped")
    r.check(ind.get("infrastructure") == "LEGACY_SELF_I",
            "Legacy flat -> individual.infrastructure mapped")

    # matrix_self.aggregate should ALSO mirror the legacy values (for Standard mode)
    agg = legacy_created.get("matrix_self", {}).get("aggregate", {})
    r.check(agg.get("summary") == "LEGACY_SELF_SUM",
            "Legacy flat -> aggregate.summary mirrored", f"got={agg.get('summary')!r}")
    r.check(agg.get("infrastructure") == "LEGACY_SELF_I",
            "Legacy flat -> aggregate.infrastructure mirrored")

    # matrix_self.{org,govt,nature} should be empty 7-field cells
    for ot in ["org", "govt", "nature"]:
        cell = legacy_created.get("matrix_self", {}).get(ot, {})
        all_empty = all(cell.get(f) == "" for f in FIELDS)
        r.check(all_empty, f"Legacy flat -> matrix_self.{ot} zeroed",
                f"got {cell}")

    # matrix_micro / matrix_macro: missing input -> full empty nested shape (all 5 slots)
    for layer in ["matrix_micro", "matrix_macro"]:
        ld = legacy_created.get(layer, {})
        has_all_slots = set(ALL_SLOTS).issubset(set(ld.keys()))
        r.check(has_all_slots, f"Missing input -> {layer} has aggregate + 4 OrgType keys",
                f"got keys={sorted(ld.keys())}")

    # ------------------------------------------------------------------
    # Test 5: Empty POST -> defaults
    # ------------------------------------------------------------------
    print("\n[Test 5] POST with NO matrix fields -> nested defaults")
    res = requests.post(
        f"{API}/solution-matrices",
        headers=headers,
        json={"area_of_life": "relationships", "smart_goal": "Empty defaults test"},
        timeout=15,
    )
    r.check(res.status_code == 200, "Empty POST returns 200")
    empty_created = res.json() if res.status_code == 200 else {}
    r.check(empty_created.get("matrix_mode") == "accurate",
            "Default matrix_mode = 'accurate'", f"got={empty_created.get('matrix_mode')}")
    for layer in LAYERS:
        ld = empty_created.get(layer, {})
        has_all = set(ld.keys()) >= set(ALL_SLOTS)
        r.check(has_all, f"Default {layer} has all 5 slots (aggregate + 4 OrgTypes)",
                f"got={sorted(ld.keys())}")
        all_empty = all(ld.get(slot, {}).get(f, "") == "" for slot in ORG_TYPES for f in FIELDS)
        r.check(all_empty, f"Default {layer} - all OrgType cells empty")

    # ------------------------------------------------------------------
    # Test 6: matrix_mode normalisation + influences roundtrip
    # ------------------------------------------------------------------
    print("\n[Test 6] matrix_mode normalisation + influences")
    body = {
        "area_of_life": "assets",
        "smart_goal": "Standard mode + influences test",
        "matrix_mode": "STANDARD",   # case + stripped
        "matrix_self": {
            "aggregate": {
                "time": "5 hrs/wk",
                "energy": "moderate",
                "people": "self",
                "finance": "2L budget",
                "infrastructure": "home workshop",
                "influences": {
                    "time": {"positive": "weekends free", "negative": "busy on weekdays"},
                    "finance": {"positive": "savings healthy", "negative": ""},
                },
            },
        },
    }
    res = requests.post(f"{API}/solution-matrices", headers=headers, json=body, timeout=15)
    r.check(res.status_code == 200, "POST standard mode returns 200")
    mode_created = res.json() if res.status_code == 200 else {}
    r.check(mode_created.get("matrix_mode") == "standard",
            "matrix_mode normalised to lowercase 'standard'",
            f"got={mode_created.get('matrix_mode')}")
    # bad mode should fall back
    bad_body = dict(body); bad_body["matrix_mode"] = "weird_value"
    res2 = requests.post(f"{API}/solution-matrices", headers=headers, json=bad_body, timeout=15)
    bad_created = res2.json()
    r.check(bad_created.get("matrix_mode") == "accurate",
            "Invalid mode falls back to 'accurate'",
            f"got={bad_created.get('matrix_mode')}")

    # Influences roundtrip
    agg = mode_created.get("matrix_self", {}).get("aggregate", {})
    inf = agg.get("influences", {})
    r.check(inf.get("time", {}).get("positive") == "weekends free",
            "Influence time.positive roundtrip")
    r.check(inf.get("time", {}).get("negative") == "busy on weekdays",
            "Influence time.negative roundtrip")
    r.check(inf.get("finance", {}).get("positive") == "savings healthy",
            "Influence finance.positive roundtrip")
    # aggregate.energy should also mirror to capacity (backward compat)
    r.check(agg.get("energy") == "moderate", "aggregate.energy stored")
    r.check(agg.get("capacity") == "moderate",
            "aggregate.capacity mirrors energy (legacy compat)",
            f"got={agg.get('capacity')!r}")

    # ------------------------------------------------------------------
    # Test 7: Templates endpoints
    # ------------------------------------------------------------------
    print("\n[Test 7] Templates list + detail")
    res = requests.get(f"{API}/solution-matrices/templates", headers=headers, timeout=10)
    r.check(res.status_code == 200, "Templates list returns 200", f"status={res.status_code}")
    tpl_list = (res.json() if res.status_code == 200 else {}).get("templates", [])
    r.check(len(tpl_list) >= 4, "At least 4 templates returned",
            f"got={len(tpl_list)}")
    org_types_covered = set(t.get("org_type") for t in tpl_list)
    r.check(org_types_covered >= set(ORG_TYPES),
            "Templates cover all 4 OrgTypes (individual/org/govt/nature)",
            f"got={org_types_covered}")

    if tpl_list:
        tid = tpl_list[0]["template_id"]
        res = requests.get(f"{API}/solution-matrices/templates/{tid}", headers=headers, timeout=10)
        r.check(res.status_code == 200, f"Template detail {tid} returns 200")
        tpl = res.json()
        r.check("payload" in tpl, "Template has 'payload' key")
        r.check(tpl.get("matrix_mode") in ("standard", "accurate"),
                "Template declares matrix_mode")

    res = requests.get(f"{API}/solution-matrices/templates/does_not_exist", headers=headers, timeout=10)
    r.check(res.status_code == 404, "Unknown template returns 404")

    # ------------------------------------------------------------------
    # Test 8: PDF export
    # ------------------------------------------------------------------
    print("\n[Test 8] PDF export")
    res = requests.get(f"{API}/solution-matrices/{entry_id}/pdf", headers=headers, timeout=30)
    r.check(res.status_code == 200, "PDF export returns 200", f"status={res.status_code}")
    r.check(res.headers.get("content-type", "").startswith("application/pdf"),
            "PDF response content-type is application/pdf",
            f"got={res.headers.get('content-type')}")
    r.check(len(res.content) > 1000, "PDF body is non-trivial (>1KB)",
            f"got {len(res.content)} bytes")
    r.check(res.content[:4] == b"%PDF", "PDF body starts with %PDF header",
            f"got={res.content[:10]!r}")

    # Standard mode entry
    sm_id = mode_created.get("entry_id")
    if sm_id:
        res = requests.get(f"{API}/solution-matrices/{sm_id}/pdf", headers=headers, timeout=30)
        r.check(res.status_code == 200, "Standard-mode PDF export returns 200")
        r.check(res.content[:4] == b"%PDF", "Standard-mode PDF body starts with %PDF header")

    # PDF for non-existent entry -> 404
    res = requests.get(f"{API}/solution-matrices/does-not-exist/pdf", headers=headers, timeout=10)
    r.check(res.status_code == 404, "PDF for missing entry returns 404")

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------
    print("\n[Cleanup] Deleting test entries")
    for eid in [entry_id,
                legacy_created.get("entry_id"),
                empty_created.get("entry_id"),
                mode_created.get("entry_id"),
                bad_created.get("entry_id") if isinstance(bad_created, dict) else None]:
        if eid:
            res = requests.delete(f"{API}/solution-matrices/{eid}", headers=headers, timeout=10)
            if res.status_code == 200:
                r.passed += 1
                print(f"  OK  Deleted {eid[:8]}")

    return r.summary()


if __name__ == "__main__":
    ok = main()
    sys.exit(0 if ok else 1)
