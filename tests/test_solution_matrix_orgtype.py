"""
Regression test — Solution Matrix OrgType (nested) persistence.

Validates:
  1. POST /api/solution-matrices with nested shape
     (matrix_{self,micro,macro}.{individual,org,govt,nature}.*)
     persists all 84 cells (3 layers × 4 OrgTypes × 7 dimensions).
  2. GET /api/solution-matrices/{id} round-trip returns the same 84 cells.
  3. PUT /api/solution-matrices/{id} with partial update preserves untouched cells.
  4. Legacy FLAT payload (matrix_self = {summary, knowledge_skills, ...}) is
     auto-normalised — the flat fields land in `individual` sub-level, other
     OrgTypes (org/govt/nature) are present as empty strings.
  5. Missing matrix_* fields on create default to full nested empty structure.
"""
import os
import sys
import time
import json
import requests

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8001")
API = f"{BASE_URL}/api"

ORG_TYPES = ["individual", "org", "govt", "nature"]
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
            print(f"  ✅ {label}")
        else:
            self.failed += 1
            self.errors.append(f"{label}: {detail}")
            print(f"  ❌ {label}{(' — ' + detail) if detail else ''}")

    def summary(self):
        total = self.passed + self.failed
        print(f"\n{'='*70}")
        print(f"Solution Matrix OrgType Regression — {self.passed}/{total} passed")
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
    """Build a matrix_* payload with every one of 84 cells uniquely filled."""
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
    """Verify each of 84 cells in `stored` equals the expected seed-derived value."""
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
        f"{label_prefix} — all 84 nested cells roundtrip correctly",
        f"{len(mismatches)} mismatches, first: {mismatches[:3]}",
    )


def main():
    r = Results()

    print("\n" + "="*70)
    print(" Solution Matrix OrgType Regression Test")
    print("="*70)

    token, email = register_user(r)
    if not token:
        r.summary(); sys.exit(1)
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # ------------------------------------------------------------------
    # Test 1: POST with full nested payload (84 cells filled)
    # ------------------------------------------------------------------
    print("\n[Test 1] POST /solution-matrices with full nested 84-cell payload")
    nested = make_full_nested_payload("S1")
    body = {
        "area_of_life": "career",
        "smart_goal": "Test goal with OrgType matrix",
        **nested,
    }
    res = requests.post(f"{API}/solution-matrices", headers=headers, json=body, timeout=15)
    r.check(res.status_code == 200, "POST returns 200", f"status={res.status_code} body={res.text[:200]}")
    created = res.json() if res.status_code == 200 else {}
    entry_id = created.get("entry_id")
    r.check(bool(entry_id), "entry_id returned")
    assert_nested_cells_match(r, created, "S1", "POST response")

    # ------------------------------------------------------------------
    # Test 2: GET roundtrip — all 84 cells persisted correctly
    # ------------------------------------------------------------------
    print("\n[Test 2] GET /solution-matrices/{id} — 84-cell roundtrip")
    res = requests.get(f"{API}/solution-matrices/{entry_id}", headers=headers, timeout=10)
    r.check(res.status_code == 200, "GET returns 200", f"status={res.status_code}")
    fetched = res.json() if res.status_code == 200 else {}
    assert_nested_cells_match(r, fetched, "S1", "GET response")

    # ------------------------------------------------------------------
    # Test 3: PUT partial update — only matrix_self changes; micro/macro retained
    # ------------------------------------------------------------------
    print("\n[Test 3] PUT partial — update only matrix_self")
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

    # matrix_self should reflect new values
    mismatches_self = []
    for ot in ORG_TYPES:
        for f in FIELDS:
            want = f"UPDATED|{ot}|{f}"
            got = updated.get("matrix_self", {}).get(ot, {}).get(f, "__MISSING__")
            if got != want:
                mismatches_self.append(f"matrix_self.{ot}.{f}")
    r.check(not mismatches_self, "matrix_self updated cells correct",
            f"{len(mismatches_self)} mismatches")

    # matrix_micro and matrix_macro retain original S1 seed
    for layer in ["matrix_micro", "matrix_macro"]:
        layer_data = updated.get(layer, {})
        preserved_ok = all(
            layer_data.get(ot, {}).get(f) == f"S1|{layer}|{ot}|{f}"
            for ot in ORG_TYPES for f in FIELDS
        )
        r.check(preserved_ok, f"{layer} untouched cells preserved after partial PUT")

    # ------------------------------------------------------------------
    # Test 4: Legacy FLAT payload → auto-normalised to nested `individual`
    # ------------------------------------------------------------------
    print("\n[Test 4] POST with legacy FLAT matrix_self (no OrgType keys)")
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
        # matrix_micro / matrix_macro omitted → should default to empty nested
    }
    res = requests.post(f"{API}/solution-matrices", headers=headers, json=legacy_body, timeout=15)
    r.check(res.status_code == 200, "Legacy POST returns 200",
            f"status={res.status_code} body={res.text[:200]}")
    legacy_created = res.json() if res.status_code == 200 else {}

    # matrix_self.individual should contain the legacy values
    ind = legacy_created.get("matrix_self", {}).get("individual", {})
    r.check(ind.get("summary") == "LEGACY_SELF_SUM", "Legacy flat → individual.summary mapped",
            f"got={ind.get('summary')!r}")
    r.check(ind.get("knowledge_skills") == "LEGACY_SELF_KS",
            "Legacy flat → individual.knowledge_skills mapped")
    r.check(ind.get("infrastructure") == "LEGACY_SELF_I",
            "Legacy flat → individual.infrastructure mapped")

    # matrix_self.{org,govt,nature} should all be empty strings for all 7 fields
    for ot in ["org", "govt", "nature"]:
        cell = legacy_created.get("matrix_self", {}).get(ot, {})
        all_empty = all(cell.get(f) == "" for f in FIELDS)
        r.check(all_empty, f"Legacy flat → matrix_self.{ot} zeroed (7 empty fields)",
                f"got {cell}")

    # matrix_micro / matrix_macro: missing on input → full empty nested shape
    for layer in ["matrix_micro", "matrix_macro"]:
        ld = legacy_created.get(layer, {})
        has_all_ot = set(ld.keys()) >= set(ORG_TYPES)
        r.check(has_all_ot, f"Missing input → {layer} has all 4 OrgType keys",
                f"got keys={list(ld.keys())}")
        all_empty = all(ld.get(ot, {}).get(f) == "" for ot in ORG_TYPES for f in FIELDS)
        r.check(all_empty, f"Missing input → {layer} all 28 cells empty strings")

    # ------------------------------------------------------------------
    # Test 5: Fully empty POST (no matrix fields at all) → all defaults nested
    # ------------------------------------------------------------------
    print("\n[Test 5] POST with NO matrix fields → nested defaults")
    res = requests.post(
        f"{API}/solution-matrices",
        headers=headers,
        json={"area_of_life": "relationships", "smart_goal": "Empty defaults test"},
        timeout=15,
    )
    r.check(res.status_code == 200, "Empty POST returns 200")
    empty_created = res.json() if res.status_code == 200 else {}
    for layer in LAYERS:
        ld = empty_created.get(layer, {})
        has_all = set(ld.keys()) == set(ORG_TYPES)
        r.check(has_all, f"Default {layer} has exactly 4 OrgType keys",
                f"got={list(ld.keys())}")
        all_empty = all(ld.get(ot, {}).get(f) == "" for ot in ORG_TYPES for f in FIELDS)
        r.check(all_empty, f"Default {layer} — all 28 cells are empty strings")

    # ------------------------------------------------------------------
    # Test 6: Cleanup
    # ------------------------------------------------------------------
    print("\n[Test 6] Cleanup — delete test entries")
    for eid in [entry_id, legacy_created.get("entry_id"), empty_created.get("entry_id")]:
        if eid:
            res = requests.delete(f"{API}/solution-matrices/{eid}", headers=headers, timeout=10)
            r.check(res.status_code == 200, f"Delete {eid[:8]}…")

    return r.summary()


if __name__ == "__main__":
    ok = main()
    sys.exit(0 if ok else 1)
