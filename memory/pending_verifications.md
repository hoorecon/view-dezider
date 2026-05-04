# Pending Verifications (re-check on/after the listed date)

This file is a lightweight reminder tracker for items that are blocked on
external/environmental factors (budget caps, regulatory approvals, etc.).
The next agent should check this file at session start.

---

## ⏰ LLM Budget Reset Verification — Re-test on/after 2026-05-05T11:42 UTC

**Status:** BLOCKED on Emergent LLM key budget cap ($0.4254 / $0.4 max).
**Logged:** 2026-05-04T11:42:48Z

**What to verify (one happy-path test):**

```bash
EMAIL="budget_recheck_$(date +%s)@test.com"
TOKEN=$(curl -s -X POST http://localhost:8001/api/auth/register \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$EMAIL\",\"password\":\"pass1234\",\"name\":\"R\"}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['session_token'])")

curl -s -X POST http://localhost:8001/api/ai-assistant/quick-ask \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"question":"What is 2+2? One sentence.","language":"en"}'
```

**Expected on success:** `200 OK` with body
```json
{"question":"What is 2+2? One sentence.","answer":"4 (or similar)","language":"en"}
```

**If still blocked:** Same response continues — `503 llm_budget_exceeded` with
`Retry-After: 60`. Wait or top up Emergent LLM key.

**On success — also re-test:**
1. `POST /api/admin/docs/refresh/regression_tests` (admin only) — should generate
   actual AI test cases instead of fallback template.
2. `POST /api/admin/docs/refresh/uat_cases` (admin only) — same.
3. `POST /api/cld/{decision_id}/generate` with a real decision — should return
   200 with nodes + links + factor_analysis.
4. `POST /api/conflict-breaker/sessions/{sid}/ai-generate/script_builder` —
   should rewrite user's script with calmer phrasing.

After verification, update `test_result.md` for the four tasks under "current_focus"
and remove this entry from the file (or move it to ## Completed below).

---

## ✅ Completed
*(none yet — populate as items get verified)*
