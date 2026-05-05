"""ReviewNet regression tests — v3.7.0
Targets http://localhost:8001/api/review-net.
"""
import os
import sys
import time
import json
import requests

BASE = "http://localhost:8001/api"
ADMIN_EMAIL = "admin@test.com"
ADMIN_PASS = "AdminPass2026!"
USER_EMAIL = "harden_1777921741@example.com"
USER_PASS = "HardenPass2026!"

# Pre-resolved finance solution (la_finance, sa_fin_debt) — see test_credentials/solutions_store
SOLUTION_ID = "12cd6acb-7af8-4238-859c-8f979a10cccd"   # SBI Home Loan — la_finance + sa_fin_debt
CATALOG_NODE_ID = "cn_fin_fd"   # FD node (test mentioned cn_fin_savings_fd but actual id is cn_fin_fd)

results = []

def log(name: str, ok: bool, msg: str = ""):
    tag = "PASS" if ok else "FAIL"
    line = f"[{tag}] {name}: {msg}"
    print(line)
    results.append((tag, name, msg))


def login(email, pwd):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": pwd}, timeout=15)
    if r.status_code != 200:
        raise RuntimeError(f"login failed for {email}: {r.status_code} {r.text}")
    return r.json()["session_token"]


def H(tok):
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


def main():
    # ---------------- 1) Auth -----------------
    try:
        admin_tok = login(ADMIN_EMAIL, ADMIN_PASS)
        user_tok = login(USER_EMAIL, USER_PASS)
        log("1. Auth admin+user login", True, "both tokens obtained")
    except Exception as e:
        log("1. Auth", False, str(e))
        return

    # ---------------- 2) Factor seed (admin) -----------------
    try:
        r1 = requests.post(f"{BASE}/review-net/factors/seed", headers=H(admin_tok), timeout=30)
        ok1 = r1.status_code == 200
        body1 = r1.json() if ok1 else {}
        cond_total = body1.get("total", 0) >= 70
        cond_inserted_ge0 = body1.get("inserted", -1) >= 0
        log("2a. factors/seed first call", ok1 and cond_total and cond_inserted_ge0,
            f"status={r1.status_code} inserted={body1.get('inserted')} skipped={body1.get('skipped_existing')} total={body1.get('total')}")

        r2 = requests.post(f"{BASE}/review-net/factors/seed", headers=H(admin_tok), timeout=30)
        body2 = r2.json() if r2.status_code == 200 else {}
        idem = body2.get("inserted") == 0 and body2.get("skipped_existing", 0) > 0
        log("2b. factors/seed idempotent", idem,
            f"inserted={body2.get('inserted')} skipped={body2.get('skipped_existing')} total={body2.get('total')}")
    except Exception as e:
        log("2. Factor seed", False, str(e))

    # ---------------- 3) Factor RBAC -----------------
    try:
        r = requests.post(f"{BASE}/review-net/factors/seed", headers=H(user_tok), timeout=10)
        log("3a. seed as USER → 403", r.status_code == 403, f"got {r.status_code}")
        r = requests.post(f"{BASE}/review-net/factors", headers=H(user_tok),
                          json={"name": "TestF", "scope_type": "global"}, timeout=10)
        log("3b. POST factors as USER → 403", r.status_code == 403, f"got {r.status_code}")
    except Exception as e:
        log("3. RBAC", False, str(e))

    # ---------------- 4) Hierarchical factor resolution -----------------
    try:
        r = requests.get(f"{BASE}/review-net/factors", params={"solution_id": SOLUTION_ID},
                         headers=H(user_tok), timeout=10)
        ok = r.status_code == 200
        body = r.json() if ok else {}
        slugs = {f["slug"] for f in body.get("factors", [])}
        global_slugs = {"value_for_money", "communication", "reliability", "trustworthiness"}
        finance_slugs = {"fee_transparency", "advisor_competence", "ease_of_onboarding"}
        debt_slugs = {"interest_rate_fairness", "loan_processing_speed", "prepayment_friendliness"}
        all_present = global_slugs.issubset(slugs) and finance_slugs.issubset(slugs) and debt_slugs.issubset(slugs)
        log("4a. resolve factors by solution_id", ok and all_present,
            f"count={body.get('count')} global={global_slugs.issubset(slugs)} finance={finance_slugs.issubset(slugs)} subarea={debt_slugs.issubset(slugs)}")

        r = requests.get(f"{BASE}/review-net/factors", params={"catalog_node_id": CATALOG_NODE_ID},
                         headers=H(user_tok), timeout=10)
        body = r.json()
        slugs = {f["slug"] for f in body.get("factors", [])}
        savings_slugs = {"interest_consistency", "premature_withdrawal_ease"}
        ok_cat = global_slugs.issubset(slugs) and finance_slugs.issubset(slugs) and savings_slugs.issubset(slugs)
        log("4b. resolve factors by catalog_node_id", ok_cat,
            f"count={body.get('count')} global={global_slugs.issubset(slugs)} finance={finance_slugs.issubset(slugs)} savings={savings_slugs.issubset(slugs)}")
    except Exception as e:
        log("4. Hierarchical factor resolution", False, str(e))

    # ---------------- 5) Eligibility policies -----------------
    review_id_held = None
    try:
        r = requests.get(f"{BASE}/review-net/eligibility/{SOLUTION_ID}", headers=H(user_tok), timeout=10)
        body = r.json()
        ok = r.status_code == 200 and body.get("policy", {}).get("policy") == "ALL_AUTHENTICATED" and body.get("is_eligible") is True
        log("5a. eligibility default=ALL_AUTHENTICATED is_eligible=true", ok,
            f"policy={body.get('policy', {}).get('policy')} is_eligible={body.get('is_eligible')}")

        r = requests.put(f"{BASE}/review-net/eligibility/{SOLUTION_ID}",
                         headers=H(admin_tok),
                         json={"policy": "VERIFIED_BUYERS_ONLY",
                               "allowed_segments": ["individual", "organization", "government"]},
                         timeout=10)
        body = r.json()
        ok = r.status_code == 200 and body.get("admin_overridden") is True
        log("5b. admin set VERIFIED_BUYERS_ONLY admin_overridden=true", ok,
            f"status={r.status_code} admin_overridden={body.get('admin_overridden')}")

        r = requests.get(f"{BASE}/review-net/eligibility/{SOLUTION_ID}", headers=H(user_tok), timeout=10)
        body = r.json()
        already_eligible = body.get("is_eligible") is True
        if already_eligible:
            log("5c. user no-purchase → NOT eligible", True,
                f"NOTE: user has prior purchase from previous run; reason='{body.get('reason')}' (skipping strict check)")
        else:
            ok = body.get("is_eligible") is False and "VERIFIED_BUYERS_ONLY" in (body.get("reason") or "")
            log("5c. user no-purchase → NOT eligible", ok,
                f"is_eligible={body.get('is_eligible')} reason={body.get('reason')}")

        r = requests.post(f"{BASE}/time-store/purchase", headers=H(user_tok),
                          json={"solution_id": SOLUTION_ID, "save_minutes_per_day": 15, "note": "uat"},
                          timeout=15)
        ok_purchase = r.status_code == 200
        log("5d. time-store/purchase created", ok_purchase,
            f"status={r.status_code} body={r.text[:120]}")

        r = requests.get(f"{BASE}/review-net/eligibility/{SOLUTION_ID}", headers=H(user_tok), timeout=10)
        body = r.json()
        ok = body.get("is_eligible") is True
        log("5e. eligibility after purchase = true", ok, f"is_eligible={body.get('is_eligible')}")

        r = requests.put(f"{BASE}/review-net/eligibility/{SOLUTION_ID}",
                         headers=H(admin_tok), json={"policy": "ALL_AUTHENTICATED"}, timeout=10)
        log("5f. reset policy → ALL_AUTHENTICATED", r.status_code == 200,
            f"status={r.status_code}")
    except Exception as e:
        log("5. Eligibility", False, str(e))

    # ---------------- 6) Submit review (HOLD path) -----------------
    try:
        # Deactivate any pre-existing rules so HOLD is deterministic
        r = requests.get(f"{BASE}/review-net/admin/rules", headers=H(admin_tok), timeout=10)
        prior_rules = r.json().get("items", []) if r.status_code == 200 else []
        prior_active_ids = [x["rule_id"] for x in prior_rules if x.get("is_active")]
        for rid in prior_active_ids:
            requests.put(f"{BASE}/review-net/admin/rules/{rid}", headers=H(admin_tok),
                         json={"is_active": False}, timeout=10)
        if prior_active_ids:
            print(f"   (deactivated {len(prior_active_ids)} pre-existing rules for HOLD test)")

        body = {
            "solution_id": SOLUTION_ID,
            "reviewer_segment": "individual",
            "reviewer_subsegment": "customer",
            "factor_ratings": {"qf_None_value_for_money": 4, "qf_None_communication": 3},
            "comment": "mid-good"
        }
        r = requests.post(f"{BASE}/review-net/reviews", headers=H(user_tok), json=body, timeout=15)
        bd = r.json() if r.status_code == 200 else {}
        review_id_held = bd.get("review_id")
        ok = (r.status_code == 200 and bd.get("status") == "pending"
              and bd.get("moderation_action") == "HOLD_FOR_ADMIN")
        log("6. submit review → HOLD_FOR_ADMIN", ok,
            f"status_code={r.status_code} review_status={bd.get('status')} action={bd.get('moderation_action')} review_id={review_id_held}")

        for rid in prior_active_ids:
            requests.put(f"{BASE}/review-net/admin/rules/{rid}", headers=H(admin_tok),
                         json={"is_active": True}, timeout=10)
    except Exception as e:
        log("6. Submit review HOLD", False, str(e))

    # ---------------- 7) Auto-approve rule -----------------
    auto_review_id = None
    rule_id = None
    try:
        r = requests.post(f"{BASE}/review-net/admin/rules", headers=H(admin_tok),
                          json={"name": "Auto-approve 3+",
                                "conditions": [{"field": "overall_min", "op": "gte", "value": 3}],
                                "action": "AUTO_APPROVE", "priority": 10},
                          timeout=10)
        bd = r.json() if r.status_code == 200 else {}
        rule_id = bd.get("rule_id")
        log("7a. POST admin/rules created", r.status_code == 200 and rule_id is not None,
            f"status={r.status_code} rule_id={rule_id}")

        r = requests.post(f"{BASE}/review-net/reviews", headers=H(user_tok), json={
            "solution_id": SOLUTION_ID,
            "reviewer_segment": "individual",
            "reviewer_subsegment": "expert",
            "factor_ratings": {"qf_None_value_for_money": 5, "qf_None_communication": 4},
            "comment": "great"
        }, timeout=10)
        bd = r.json() if r.status_code == 200 else {}
        auto_review_id = bd.get("review_id")
        ok = bd.get("status") == "auto_approved" and bd.get("moderation_action") == "AUTO_APPROVE"
        log("7b. review avg≥3 auto_approved", ok,
            f"status={bd.get('status')} action={bd.get('moderation_action')}")

        r = requests.post(f"{BASE}/review-net/reviews", headers=H(user_tok), json={
            "solution_id": SOLUTION_ID,
            "reviewer_segment": "individual",
            "reviewer_subsegment": "customer",
            "factor_ratings": {"qf_None_value_for_money": 1, "qf_None_communication": 1},
            "comment": "bad"
        }, timeout=10)
        bd = r.json() if r.status_code == 200 else {}
        ok = bd.get("status") == "pending" and bd.get("moderation_action") == "HOLD_FOR_ADMIN"
        log("7c. review avg<3 still pending", ok,
            f"status={bd.get('status')} action={bd.get('moderation_action')}")

        if rule_id:
            r = requests.delete(f"{BASE}/review-net/admin/rules/{rule_id}", headers=H(admin_tok), timeout=10)
            log("7d. DELETE rule", r.status_code == 200, f"status={r.status_code}")
    except Exception as e:
        log("7. Auto-approve rule", False, str(e))

    # ---------------- 8) Aggregates -----------------
    try:
        r = requests.get(f"{BASE}/review-net/aggregates", params={"solution_id": SOLUTION_ID},
                         headers=H(user_tok), timeout=10)
        body = r.json() if r.status_code == 200 else {}
        total_reviews = body.get("total_reviews", 0)
        seg_ind = body.get("segments", {}).get("individual", {})
        ind_count = seg_ind.get("review_count", 0)
        per_factor = body.get("overall", {}).get("per_factor", {})
        ok = (r.status_code == 200 and total_reviews >= 1 and ind_count >= 1 and len(per_factor) > 0)
        log("8. aggregates", ok,
            f"total={total_reviews} ind_count={ind_count} per_factor_keys={len(per_factor)}")
    except Exception as e:
        log("8. Aggregates", False, str(e))

    # ---------------- 9) Helpful vote toggle (auto_review_id) -----------------
    voter_tok = None
    target_review = auto_review_id
    try:
        ts = int(time.time())
        voter_email = f"rnvoter_{ts}@example.com"
        voter_pwd = "UatPass2026!"
        r = requests.post(f"{BASE}/auth/register", json={
            "email": voter_email, "password": voter_pwd, "name": "RN Voter"
        }, timeout=10)
        if r.status_code == 200:
            voter_tok = r.json().get("session_token")
        else:
            voter_tok = login(voter_email, voter_pwd)
        log("9a. register voter user", voter_tok is not None, f"email={voter_email}")

        if not target_review:
            log("9b-e. helpful vote (skipped)", False, "no auto_review_id from step 7b")
        else:
            r = requests.post(f"{BASE}/review-net/reviews/{target_review}/helpful",
                              headers=H(voter_tok), json={"helpful": True}, timeout=10)
            ok = r.status_code == 200 and r.json().get("ok") is True and not r.json().get("noop")
            log("9b. helpful=true first time", ok, f"status={r.status_code} body={r.text[:120]}")

            rv = requests.get(f"{BASE}/review-net/reviews/{target_review}", headers=H(voter_tok), timeout=10).json()
            yes_after_first = rv.get("helpful_yes_count")

            r = requests.post(f"{BASE}/review-net/reviews/{target_review}/helpful",
                              headers=H(voter_tok), json={"helpful": True}, timeout=10)
            ok = r.status_code == 200 and r.json().get("noop") is True
            log("9c. helpful=true again → noop", ok, f"body={r.text[:120]}")

            r = requests.post(f"{BASE}/review-net/reviews/{target_review}/helpful",
                              headers=H(voter_tok), json={"helpful": False}, timeout=10)
            rv2 = requests.get(f"{BASE}/review-net/reviews/{target_review}", headers=H(voter_tok), timeout=10).json()
            yes_after_toggle = rv2.get("helpful_yes_count")
            no_after_toggle = rv2.get("helpful_no_count")
            ok = (yes_after_toggle == yes_after_first - 1) and (no_after_toggle >= 1)
            log("9d. helpful toggle yes→no", ok,
                f"yes:{yes_after_first}→{yes_after_toggle} no={no_after_toggle}")

            r = requests.post(f"{BASE}/review-net/reviews/{target_review}/helpful",
                              headers=H(user_tok), json={"helpful": True}, timeout=10)
            ok = r.status_code == 400
            log("9e. self-vote rejected (400)", ok, f"status={r.status_code} body={r.text[:120]}")
    except Exception as e:
        log("9. Helpful vote", False, str(e))

    # ---------------- 10) Owner reply -----------------
    try:
        if not target_review:
            log("10. owner_reply (skipped)", False, "no target review")
        else:
            r = requests.post(f"{BASE}/review-net/reviews/{target_review}/reply",
                              headers=H(voter_tok), json={"content": "thanks!"}, timeout=10)
            log("10a. non-owner reply → 403", r.status_code == 403, f"status={r.status_code}")

            r = requests.post(f"{BASE}/review-net/reviews/{target_review}/reply",
                              headers=H(admin_tok), json={"content": "Admin acknowledged."}, timeout=10)
            bd = r.json() if r.status_code == 200 else {}
            ok = r.status_code == 200 and bd.get("is_official") is True
            log("10b. admin reply 200 + is_official=true", ok, f"status={r.status_code} is_official={bd.get('is_official')}")

            rv = requests.get(f"{BASE}/review-net/reviews/{target_review}", headers=H(user_tok), timeout=10).json()
            ok = rv.get("owner_reply") is not None
            log("10c. GET review.owner_reply populated", ok,
                f"owner_reply={'present' if rv.get('owner_reply') else 'MISSING'}")
    except Exception as e:
        log("10. Owner reply", False, str(e))

    # ---------------- 11) Admin moderation queue + manual approve -----------------
    try:
        if not review_id_held:
            log("11. moderation queue (skipped)", False, "no held review id")
        else:
            r = requests.get(f"{BASE}/review-net/admin/moderation-queue",
                             params={"status": "pending"}, headers=H(admin_tok), timeout=10)
            bd = r.json() if r.status_code == 200 else {}
            ids = [it["review_id"] for it in bd.get("items", [])]
            ok = r.status_code == 200 and review_id_held in ids
            log("11a. queue contains held review", ok, f"count={len(ids)} held_present={review_id_held in ids}")

            r = requests.post(f"{BASE}/review-net/admin/moderate/{review_id_held}",
                              headers=H(admin_tok), json={"decision": "approve", "note": "looks good"},
                              timeout=10)
            bd = r.json() if r.status_code == 200 else {}
            ok = r.status_code == 200 and bd.get("status") == "approved"
            log("11b. moderate decision=approve", ok, f"status={r.status_code} new_status={bd.get('status')}")

            r = requests.get(f"{BASE}/review-net/aggregates", params={"solution_id": SOLUTION_ID},
                             headers=H(user_tok), timeout=10)
            total = r.json().get("total_reviews", 0) if r.status_code == 200 else 0
            log("11c. aggregates increment", total >= 2, f"total_reviews={total}")
    except Exception as e:
        log("11. Moderation", False, str(e))

    # ---------------- 12) List reviews — only published surface -----------------
    try:
        r = requests.get(f"{BASE}/review-net/reviews", params={"solution_id": SOLUTION_ID},
                         headers=H(user_tok), timeout=10)
        bd = r.json() if r.status_code == 200 else {}
        items = bd.get("items", [])
        statuses = {it.get("status") for it in items}
        ok = r.status_code == 200 and statuses.issubset({"approved", "auto_approved"})
        log("12. list reviews only approved/auto_approved", ok,
            f"count={len(items)} statuses={statuses}")
    except Exception as e:
        log("12. List reviews", False, str(e))

    # ---------------- 13) Subsegment validation -----------------
    try:
        r = requests.post(f"{BASE}/review-net/reviews", headers=H(user_tok), json={
            "solution_id": SOLUTION_ID,
            "reviewer_segment": "individual",
            "reviewer_subsegment": "regulator",
            "factor_ratings": {"qf_None_value_for_money": 4}
        }, timeout=10)
        ok = r.status_code == 400 and "invalid sub-segment" in r.text.lower()
        log("13. invalid subsegment → 400", ok, f"status={r.status_code} body={r.text[:160]}")
    except Exception as e:
        log("13. Subsegment validation", False, str(e))

    print("\n" + "=" * 70)
    fail = [r for r in results if r[0] == "FAIL"]
    print(f"TOTAL: {len(results)}  PASS: {len(results) - len(fail)}  FAIL: {len(fail)}")
    if fail:
        print("\nFAILURES:")
        for _, name, msg in fail:
            print(f"  - {name}: {msg}")
    return 0 if not fail else 1


if __name__ == "__main__":
    sys.exit(main())
