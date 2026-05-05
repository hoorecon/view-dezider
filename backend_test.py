"""
Central Catalog Management (CCM) backend regression tests.
Tests /api/catalog/* endpoints per review request.
"""
import json
import os
import sys
from typing import Any, Dict, Optional

import requests

BASE_URL = "http://localhost:8001/api"
ADMIN_EMAIL = "admin@test.com"
ADMIN_PASS = "AdminPass2026!"
USER_EMAIL = "harden_1777921741@example.com"
USER_PASS = "HardenPass2026!"

results = []


def log(name: str, passed: bool, detail: str = "") -> None:
    mark = "PASS" if passed else "FAIL"
    line = f"[{mark}] {name} :: {detail}"
    print(line)
    results.append({"name": name, "pass": passed, "detail": detail})


def hdr(token: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def login(email: str, password: str) -> Optional[str]:
    r = requests.post(f"{BASE_URL}/auth/login", json={"email": email, "password": password}, timeout=15)
    if r.status_code != 200:
        return None
    return r.json().get("session_token")


def walk_find(node: dict, names: list) -> Optional[dict]:
    cur = node
    for n in names:
        match = None
        for c in cur.get("children", []):
            if c.get("name") == n:
                match = c
                break
        if not match:
            return None
        cur = match
    return cur


def find_solution_id_via_mongo() -> Optional[str]:
    try:
        import pymongo
        mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
        client = pymongo.MongoClient(mongo_url, serverSelectionTimeoutMS=3000)
        # enumerate DBs
        for name in client.list_database_names():
            if name in ("admin", "local", "config"):
                continue
            try:
                doc = client[name].solutions_store.find_one({})
                if doc and doc.get("solution_id"):
                    return doc["solution_id"]
            except Exception:
                continue
    except Exception as e:
        print(f"mongo scan failed: {e}")
    return None


def verify_solution_mapping(sol_id: str) -> Optional[dict]:
    try:
        import pymongo
        mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
        client = pymongo.MongoClient(mongo_url, serverSelectionTimeoutMS=3000)
        for name in client.list_database_names():
            if name in ("admin", "local", "config"):
                continue
            doc = client[name].solutions_store.find_one({"solution_id": sol_id})
            if doc:
                return doc
    except Exception as e:
        print(f"verify failed: {e}")
    return None


def run():
    admin_token = login(ADMIN_EMAIL, ADMIN_PASS)
    log("1. Admin login", bool(admin_token), ADMIN_EMAIL if admin_token else "login failed")
    if not admin_token:
        return

    user_token = login(USER_EMAIL, USER_PASS)
    log("1. User login", bool(user_token), USER_EMAIL if user_token else "login failed")
    if not user_token:
        return

    # 2. Idempotent seed
    r = requests.post(f"{BASE_URL}/catalog/seed", headers=hdr(admin_token), timeout=60)
    if r.status_code == 200:
        d = r.json()
        total = d.get("total_nodes", 0)
        ok = (total >= 250 and d.get("backbone_inserted", -1) >= 0 and d.get("l2_l3_inserted", -1) >= 0)
        log("2. POST /catalog/seed (admin, 1st)", ok,
            f"total={total} backbone_ins={d.get('backbone_inserted')} l2l3_ins={d.get('l2_l3_inserted')}")
    else:
        log("2. POST /catalog/seed (admin, 1st)", False, f"status={r.status_code} body={r.text[:200]}")

    r = requests.post(f"{BASE_URL}/catalog/seed", headers=hdr(admin_token), timeout=60)
    if r.status_code == 200:
        d = r.json()
        ok = d.get("l2_l3_inserted") == 0 and d.get("l2_l3_skipped_existing", 0) > 0
        log("2. POST /catalog/seed (admin, 2nd idempotent)", ok,
            f"l2_l3_inserted={d.get('l2_l3_inserted')} skipped={d.get('l2_l3_skipped_existing')}")
    else:
        log("2. POST /catalog/seed (admin, 2nd idempotent)", False, f"status={r.status_code}")

    r = requests.post(f"{BASE_URL}/catalog/seed", headers=hdr(user_token), timeout=30)
    log("2. POST /catalog/seed (user, non-admin) -> 403", r.status_code == 403, f"status={r.status_code}")

    # 3. Force reseed
    r = requests.post(f"{BASE_URL}/catalog/seed?force=true", headers=hdr(admin_token), timeout=60)
    if r.status_code == 200:
        d = r.json()
        ok = (d.get("wiped_l2_l3_nodes", 0) > 0 and d.get("l2_l3_inserted", 0) > 0 and d.get("total_nodes", 0) >= 250)
        log("3. POST /catalog/seed?force=true", ok,
            f"wiped={d.get('wiped_l2_l3_nodes')} inserted={d.get('l2_l3_inserted')} total={d.get('total_nodes')}")
    else:
        log("3. POST /catalog/seed?force=true", False, f"status={r.status_code}")

    # 4. Tree shape (finance)
    r = requests.get(f"{BASE_URL}/catalog/tree?life_area_id=la_finance", headers=hdr(user_token), timeout=30)
    tree_ok = r.status_code == 200
    log("4. GET /catalog/tree?life_area_id=la_finance", tree_ok, f"status={r.status_code}")
    if tree_ok:
        tree = r.json()
        roots = tree.get("roots", [])
        fin_root = next((x for x in roots if x.get("name") == "Finance"), None)
        if not fin_root:
            log("4. Finance root in tree", False, "no Finance L0 found")
        else:
            checks = [
                (["Savings", "Fixed Deposit", "Senior Citizen FD"], "Finance-Savings-Fixed Deposit-Senior Citizen FD"),
                (["Investments", "Mutual Funds", "ELSS (Tax-Saver)"], "Finance-Investments-Mutual Funds-ELSS (Tax-Saver)"),
                (["Risk Management", "Health Insurance", "Family Floater"], "Finance-Risk Management-Health Insurance-Family Floater"),
            ]
            for path, label in checks:
                found = walk_find(fin_root, path)
                log(f"4. Tree path: {label}", bool(found),
                    f"node_id={found.get('node_id') if found else 'None'}")
            hl = walk_find(fin_root, ["Debt", "Home Loan"])
            hl_ok = hl is not None and hl.get("level") == 2 and len(hl.get("children", [])) == 0
            log("4. Finance-Debt-Home Loan (L2 leaf, no L3)", hl_ok,
                f"level={hl.get('level') if hl else None} kids={len(hl.get('children', [])) if hl else None}")

    # Career VC check
    r = requests.get(f"{BASE_URL}/catalog/tree?life_area_id=la_career", headers=hdr(user_token), timeout=30)
    if r.status_code == 200:
        career_root = next((x for x in r.json().get("roots", []) if x.get("name") == "Career"), None)
        vc = walk_find(career_root, ["Fundraise & Growth Capital", "Venture Capital"]) if career_root else None
        log("4. Career-Fundraise & Growth Capital-Venture Capital", bool(vc),
            f"node_id={vc.get('node_id') if vc else 'None'}")
    else:
        log("4. GET Career tree", False, f"status={r.status_code}")

    # 5. Read endpoints
    r = requests.get(f"{BASE_URL}/catalog/nodes?level=2&life_area_id=la_finance",
                     headers=hdr(user_token), timeout=30)
    if r.status_code == 200:
        items = r.json().get("items", [])
        all_ok = all(it.get("level") == 2 and it.get("life_area_id") == "la_finance" for it in items)
        log("5. GET /catalog/nodes?level=2&life_area_id=la_finance", len(items) >= 5 and all_ok,
            f"count={len(items)} all_level2_fin={all_ok}")
    else:
        log("5. GET /catalog/nodes level=2 finance", False, f"status={r.status_code}")

    r = requests.get(f"{BASE_URL}/catalog/nodes/cn_fin_fd", headers=hdr(user_token), timeout=30)
    if r.status_code == 200:
        d = r.json()
        bc = d.get("breadcrumb", [])
        expected = ["Finance", "Savings", "Fixed Deposit"]
        has_keys = all(k in d for k in ("node", "ancestors", "breadcrumb", "children_count", "solutions_count"))
        log("5. GET /catalog/nodes/cn_fin_fd structure",
            has_keys and bc == expected,
            f"breadcrumb={bc} children_count={d.get('children_count')} solutions_count={d.get('solutions_count')}")
    else:
        log("5. GET /catalog/nodes/cn_fin_fd", False, f"status={r.status_code}")

    # 6. Admin CRUD
    new_id = None
    r = requests.post(f"{BASE_URL}/catalog/nodes", headers=hdr(admin_token),
                      json={"name": "NRI FD", "parent_id": "cn_fin_fd"}, timeout=30)
    if r.status_code in (200, 201):
        d = r.json()
        new_id = d.get("node_id")
        log("6. POST create L3 under cn_fin_fd", d.get("level") == 3 and bool(new_id),
            f"node_id={new_id} level={d.get('level')}")
    else:
        log("6. POST create L3 under cn_fin_fd", False, f"status={r.status_code} body={r.text[:200]}")

    if new_id:
        r = requests.put(f"{BASE_URL}/catalog/nodes/{new_id}", headers=hdr(admin_token),
                         json={"name": "NRE/NRO FD", "sort_order": 99}, timeout=30)
        if r.status_code == 200:
            d = r.json()
            log("6. PUT update L3 name+sort_order",
                d.get("name") == "NRE/NRO FD" and d.get("sort_order") == 99,
                f"name={d.get('name')} sort_order={d.get('sort_order')}")
        else:
            log("6. PUT update L3", False, f"status={r.status_code} body={r.text[:200]}")

        r = requests.delete(f"{BASE_URL}/catalog/nodes/{new_id}", headers=hdr(admin_token), timeout=30)
        log("6. DELETE new L3", r.status_code == 200, f"status={r.status_code}")

        r = requests.delete(f"{BASE_URL}/catalog/nodes/{new_id}", headers=hdr(admin_token), timeout=30)
        log("6. DELETE same id again (should 404)", r.status_code == 404, f"status={r.status_code}")

    # 7. Backbone protection
    r = requests.put(f"{BASE_URL}/catalog/nodes/cn_l0_la_finance", headers=hdr(admin_token),
                     json={"name": "Money"}, timeout=30)
    log("7. PUT rename cn_l0_la_finance (backbone) -> 403", r.status_code == 403,
        f"status={r.status_code}")

    r = requests.delete(f"{BASE_URL}/catalog/nodes/cn_l1_sa_fin_savings", headers=hdr(admin_token), timeout=30)
    log("7. DELETE cn_l1_sa_fin_savings (backbone) -> 403", r.status_code == 403,
        f"status={r.status_code}")

    # 8. Leaf-only delete
    r = requests.delete(f"{BASE_URL}/catalog/nodes/cn_fin_fd", headers=hdr(admin_token), timeout=30)
    body = r.text
    log("8. DELETE cn_fin_fd (has children) -> 409", r.status_code == 409,
        f"status={r.status_code} body_mentions_children={'child' in body.lower()}")

    # 9. Solution mapping
    r = requests.post(f"{BASE_URL}/catalog/auto-map-existing", headers=hdr(admin_token), timeout=120)
    if r.status_code == 200:
        d = r.json()
        log("9. POST /catalog/auto-map-existing", True,
            f"updated={d.get('updated')} unmapped={d.get('unmapped')}")
    else:
        log("9. POST /catalog/auto-map-existing", False, f"status={r.status_code} body={r.text[:200]}")

    sol_id = find_solution_id_via_mongo()
    if sol_id:
        r = requests.post(f"{BASE_URL}/catalog/solutions/{sol_id}/map", headers=hdr(admin_token),
                          json={"catalog_node_id": "cn_fin_fd"}, timeout=30)
        if r.status_code == 200:
            d = r.json()
            log("9. POST /catalog/solutions/{sid}/map", d.get("level") == 2,
                f"solution_id={sol_id} level={d.get('level')} node={d.get('catalog_node_id')}")
        else:
            log("9. POST /catalog/solutions/{sid}/map", False,
                f"status={r.status_code} body={r.text[:200]}")

        doc = verify_solution_mapping(sol_id)
        if doc:
            ok = doc.get("catalog_node_id") == "cn_fin_fd" and doc.get("catalog_level") == 2
            log("9. DB verification solution mapping", ok,
                f"catalog_node_id={doc.get('catalog_node_id')} catalog_level={doc.get('catalog_level')}")
        else:
            log("9. DB verification solution mapping", False, "solution doc not found")
    else:
        log("9. Solution mapping - find solution_id", False, "no solution found in DB")

    # 10. User read access
    r = requests.get(f"{BASE_URL}/catalog/tree", headers=hdr(user_token), timeout=30)
    log("10. User GET /catalog/tree", r.status_code == 200, f"status={r.status_code}")

    r = requests.get(f"{BASE_URL}/catalog/nodes/cn_fin_fd", headers=hdr(user_token), timeout=30)
    log("10. User GET /catalog/nodes/cn_fin_fd", r.status_code == 200, f"status={r.status_code}")

    r = requests.post(f"{BASE_URL}/catalog/nodes", headers=hdr(user_token),
                      json={"name": "UserAttempt", "parent_id": "cn_fin_fd"}, timeout=30)
    log("10. User POST /catalog/nodes -> 403", r.status_code == 403, f"status={r.status_code}")

    print("\n=========================================")
    passed = sum(1 for x in results if x["pass"])
    total = len(results)
    print(f"RESULTS: {passed}/{total} passed")
    for x in results:
        if not x["pass"]:
            print(f"  FAIL :: {x['name']} :: {x['detail']}")


if __name__ == "__main__":
    run()
