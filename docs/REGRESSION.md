# Regression Test Catalogue — Dezider

_metadata: { "version": "3.16.1", "updated": "2026-06-12" }

All suites live in `/app/tests/` plus the legacy `/app/backend_test_regression.py`.

## Suites (v3.5)

| File | Coverage | Last result |
|---|---|---|
| `tests/test_solution_matrix_orgtype.py` | Solution Matrix nested OrgType + modes + influences + templates + PDF | 61 / 61 |
| `tests/test_yoy_and_portal_smoke.py` | YoY analytics + sub-portal endpoints | 13 / 13 |
| `tests/test_hardening.py` | Security headers, body cap, gzip, audit log, DPDP, metrics | 23 / 23 |
| `tests/test_dtl_timedezider_timestore.py` (NEW) | Daily Time Log + Raja Guru + Time Store | 31 / 31 |
| `backend_test_regression.py` | Auth + ACM + Solutions Store + 30+ legacy modules | 28 / 28 |

**TOTAL: 156 / 156 PASSING** — 0 regressions between v3.4 and v3.5.

## How to run

```bash
cd /app
python tests/test_solution_matrix_orgtype.py
python tests/test_yoy_and_portal_smoke.py
python tests/test_hardening.py
python tests/test_dtl_timedezider_timestore.py
python backend_test_regression.py
```

Exit code 0 = green; non-zero on any failure. For CI, chain them with `&&`.

## CI integration (sample GitHub Actions)

```yaml
name: API regression
on: [push, pull_request]
jobs:
  api:
    runs-on: ubuntu-latest
    services:
      mongo: { image: mongo:7, ports: ['27017:27017'] }
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.11' }
      - name: Install deps
        run: pip install -r backend/requirements.txt
      - name: Start backend
        run: cd backend && (uvicorn server:app --host 0.0.0.0 --port 8001 &)
      - name: Run suites
        run: |
          sleep 5
          python tests/test_solution_matrix_orgtype.py
          python tests/test_yoy_and_portal_smoke.py
          python tests/test_hardening.py
          python tests/test_dtl_timedezider_timestore.py
          python backend_test_regression.py
```

## What's covered — v3.5 additions

### Daily Time Log (11 assertions)
- Preferences GET+POST for 4 key timings + 5 nudge flags
- Day upsert persists manual blocks with correct minute math
- Auto-rollup adds CTT / Lifestyle / Meditation / Journal sources
- Per-category rollup correctness (CTT = 90 min for 09:30–11:00)
- refresh-rollup endpoint
- Streak increments on first >=15 min day
- Week view returns exactly 7 day slots
- Weekly-review returns shape keys (variance_notes, total_logged_minutes)

### Time Dezider (10 assertions)
- All 4 slots (day-plan, midday-check, evening-retro, next-action) return 200 with expected fields
- Preferences toggle persists
- Feedback accept returns ok; invalid decision returns 400

### Time Store (10 assertions)
- Time-audit returns opportunities + total_minutes_saveable_per_week
- Services endpoint returns list + buckets
- Purchases / delegations list endpoints
- Delegate POST happy path + bad source_type = 400
- Purchase unknown solution = 404

## Adding a new suite
1. Drop a `tests/test_<area>.py` that exits non-zero on failure.
2. Add a row to the table above.
3. Append the run command to CI.
4. Bump version in this doc's `_metadata`.

---
## v3.14.0 — New regression scenarios (2026-05-07)

### Tier Matrix
- TM-R-1: GET `/api/tiers` returns 7 chakras in order (root → crown)
- TM-R-2: PUT cell ON cascades to higher tiers (verify with subsequent GET)
- TM-R-3: PUT module=N forces all child features N at same tier
- TM-R-4: PUT feature=Y when parent module=N auto-enables parent
- TM-R-5: POST reset wipes + reseeds → matrix returns to smart-seed defaults

### Customer Segments
- CS-R-1: POST creates segment with 23 default factors + 7 INR tier pricings
- CS-R-2: POST `/factor` adds custom factor; DELETE removes it
- CS-R-3: POST `/ai-research` fills factor value (200 even when LLM capped → fallback)
- CS-R-4: PUT `/pricing` upserts multi-currency rows; rejects unknown tier_key (400)
- CS-R-5: DELETE segment is hard-delete; subsequent GET returns 404

### Pricing
- PR-R-1: GET `/api/pricing` returns `{tiers, segments, matrix_rows}`
- PR-R-2: 2nd identical GET within 60s served from cache (≤10ms)
- PR-R-3: Admin write to segment invalidates cache → next GET returns fresh data

---
## v3.15.0 — 8-Step Pros & Cons / SWOT Framework regression scenarios (2026-05-18)

### Pros & Cons 8-step (PCFW-)
- PCFW-R-1: POST `/api/pros-cons/{id}/factors` creates direct factor with expected_value+unit
- PCFW-R-2: POST `/api/pros-cons/{id}/options` and POST `.../options/{oid}/pros`/`.../cons` creates per-option items
- PCFW-R-3: POST `.../promote-pros-cons` promotes all P&C, Cons prefixed `SHOULD NOT - `, idempotent on second call (skips already-promoted)
- PCFW-R-4: PUT `.../factors/{fid}` with `parent_id` makes a factor a sub-factor
- PCFW-R-5: PUT `.../factors/{fid}` with `notation:mandatory` and PUT `.../config` `mandatory_threshold_pct:60` activates knock-out rule
- PCFW-R-6: PUT `.../assessments/{oid}/{fid}` with `assessment_pct:80` and `std_rating:80` → `cell_value:64.0` (computed server-side)
- PCFW-R-7: PUT cell with `satisfaction_pct:0.85` × `realistic_rating:80` → `satisfaction_value:68.0`
- PCFW-R-8: GET `.../aggregate` returns rollups with `joint_score`, `overall_satisfaction_pct`, `disqualified=true` when mandatory factor below threshold, surviving options ranked high-to-low
- PCFW-R-9: GET `.../aggregate` returns 12 `final_decision_guidelines` items
- PCFW-R-10: POST `.../factors/reorder` with `ordered_ids` renumbers `priority_rank` 1..N

### SWOT 8-step (SWFW-)
Same 10 scenarios mirrored on `/api/swot/{id}/*` — verified manually (this fork).

### Smoke result
- Pros & Cons: 10/10 manual PASS (curl)
- SWOT: 10/10 manual PASS (curl)
- No automated suite added yet — to be wrapped into `tests/test_decision_framework.py` next session.

---
## v3.16.0 — Regression scenarios (2026-06-12)

### New / updated suites

| File | Coverage | Last result |
|---|---|---|
| `tests/test_url_detail_import.py` | URL import v3: factor_type doctrine, hierarchical preservation, hints validation + self-heal, zero-tolerance, set-expectations gating | 17 / 17 |
| `tests/test_iter_url_world_class_import.py` | NoBroker live extraction, mode=detail, ai_provider surface, fallback chain | 5 / 5 |
| `tests/test_admin_recon.py` | Revenue Recon: super-admin auth (401 / 403), Razorpay sync, GCP config (b64 SA JSON never echoed), tally math, CSV export | 6 / 6 |
| `tests/test_batch_assess.py` | Batched AI assess + retry-failed-cells (existing v3.15) | 4 / 4 |

### URL Import v3 (IU-R-)
- IU-R-1: Import preserves page-defined groups verbatim when `source=page`; AI never overrides them.
- IU-R-2: When no page groups AND factors ≤ `import_group_threshold`, response `kind=flat`.
- IU-R-3: When no page groups AND factors > threshold, response `kind=hier` with AI-generated groups.
- IU-R-4: Hints out-of-tolerance → ONE corrective self-heal retry; `hint_warnings[]` populated if still off.
- IU-R-5: Unknown value keys in `items[]` are DROPPED (zero tolerance).
- IU-R-6: `Factor.factor_type` round-trips correctly through every create / merge path in `decision_builder.py`.
- IU-R-7: Text-fact factors (Color, Furnishing) classified `quantitative` by the keyword heuristic.
- IU-R-8: `POST /set-expectations` returns 422 if factors / options / unit_value missing.
- IU-R-9: `POST /set-expectations` updates ONLY leaf factors (parents untouched).
- IU-R-10: Precise tier routes Claude first; surfaces `ai_provider=emergent_precise` in response.

### Revenue Recon (RC-R-)
- RC-R-1: `GET /admin/recon/summary` returns verdict + 8 KPI fields.
- RC-R-2: `POST /admin/recon/sync` is idempotent (run twice → same row counts in collections).
- RC-R-3: `PUT /admin/recon/gcp-config` accepts valid b64 SA JSON, rejects garbage with 400.
- RC-R-4: `GET /admin/recon/gcp-config` returns presence flag only (never the SA JSON itself).
- RC-R-5: Per-txn tally math: `buffer = collected − fee − markup − cost`; `at_loss=true` when negative.
- RC-R-6: Non-super-admin requests → 403 across all `/admin/recon/*` routes.

### AI Wallet (AW-R-)
- AW-R-1: `PUT /admin/ai-wallet/config` rejects `precise_usd_per_mtok ≤ 0` with 400.
- AW-R-2: `import_group_threshold` change is honored on the very next import.
- AW-R-3: `metered_chat(tier="precise")` charges at multiplier (`precise / blended`).

### PostHog (PH-R-)
- PH-R-1: Backend `posthog_client.capture()` is a no-op when `POSTHOG_API_KEY` is unset; never raises.
- PH-R-2: Backend signup endpoint emits `signup` event server-side (verified via mock).
- PH-R-3: Wallet debit emits `ai_credits_consumed` with `feature`, `provider`, `balance_after`.

### Smoke result (manual, this fork)
- URL Import v3: 17/17 + 5/5 (iter_world_class) PASS.
- Recon: 6/6 PASS + 1 live Razorpay sync (57 payments, 5 transfers, 26 settlements pulled in test env).
- AI Wallet: manual UI walkthrough + curl PUT + read-back PASS.
- PostHog: live web replay verified in preview browser (sessionRecordingStarted=true, snapshots to `/s/`, events to `/e/` + `/batch/`).

---
## v3.16.1 — Import-URL "Hints are Law" (2026-06-12)

### New automated suite
- `backend/tests/test_url_import_hints.py` — 11 tests:
  deterministic hint-gate (carwale PRICE/MODEL parse MUST fail the gate; matching
  parses pass; hierarchy-shape gating), comparison-page normalisation (facet
  factors + peer items NOT force-scored 100), detail-page main-item backfill
  unchanged, USER-VERIFIED-FACTS prompt injection, old comparison bail-out
  removed from the prompt.

### Smoke result (this fork)
- Full URL-import suite: **41 passed** (test_url_detail_import, test_url_import_direction,
  test_url_matrix_parse, test_iter94_url_hierarchy_import incl. live GSMArena
  hierarchical import, test_url_import_hints).
- Live e2e: carwale URL + 4 hints + precise tier → 6 facet factors / 4 options
  (Tata Tiago EV first), `emergent_precise`, `hint_warnings=[]`, 57 s.
- Stale iter94 pre-built-decision check now skips gracefully when the seeded
  decision is absent (data dependency, not code).
