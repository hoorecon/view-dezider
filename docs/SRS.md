# System Requirements Specification — Dezider

_metadata: { "version": "3.15.0", "updated": "2026-05-18" }

## 1. Architecture
Expo frontend → NGINX ingress → FastAPI pods → MongoDB replica-set.
4 API pods baseline, HPA 4–40. Mongo M30 (3 nodes prod). DPDP purge = k8s CronJob.

## 2. Stack
| Layer | Tech | Version |
|---|---|---|
| Mobile/Web | Expo SDK | 53 |
|  | expo-router | 5.x |
|  | expo-speech-recognition | latest |
|  | zustand / react-hook-form | latest |
| API | FastAPI | 0.118 |
|  | uvicorn (uvloop+httptools) | 0.30 |
|  | motor (mongo async) | 3.7 |
|  | pydantic | 2.x |
|  | slowapi | 0.1 |
|  | reportlab (PDF) | 4.4 |
| DB | MongoDB | 7 (3-node replica) |
| Obs | In-process counters + Prometheus text | n/a |

## 3. Collections (v3.5 additions in **bold**)

Core: `users, user_sessions, user_subscriptions, user_wallets, **user_preferences** (NEW — 4 key timings + nudge cadence), user_streaks`

Decisions: `decisions, factors, options, option_scores, solution_finders, solution_matrices, goal_setter_entries, goal_manifestations, unconditional_happiness, aala_entries, pna_entries, clds, cld_simulations, tepfi_matrices, swot_analyses, pros_cons_lists, journal_entries, consciousness_diary_entries, meditation_sessions`

**Accountability (NEW v3.5)**: `daily_time_logs, user_streaks, time_dezider_feedback, time_store_purchases, time_store_delegations`

ACM: `acm_modules, acm_features, acm_state, acm_quota_counters`

Public Pulse: `pp_consents, pp_demographic_profiles, pp_tool_sessions, pp_feedback_items, pp_orgs, pp_org_memberships, pp_portal_config`

Auditing: `audit_log, idempotency_keys`

Solutions Store: `solutions_store` (NEW optional fields: `time_save_per_day_min`, `time_save_per_week_min`)

## 4. Index plan
210+ indexes installed at boot. New in v3.5:
- `daily_time_logs.user_id, log_date` (compound, unique)
- `user_streaks.user_id, streak_key`
- `time_store_purchases.user_id, created_at -1`
- `time_store_delegations.requester_id, created_at -1`
- `time_dezider_feedback.user_id, created_at -1`
- `solutions_store.time_save_per_day_min` (sparse)
- `solutions_store.time_save_per_week_min` (sparse)

## 5. Hardening (unchanged from v3.4)
Body cap 10 MB, GZip 1 KB, sec headers, HSTS in prod, PII redaction on logs, audit log, DPDP endpoints, idempotency helper, circuit breaker + retry-with-jitter, /metrics.

## 6. Performance targets (v3.5 additions)

| Endpoint family | Target p95 | Measured (synth) |
|---|---|---|
| `/daily-time-log/{date}` with rollup | 400 ms | 80–200 ms |
| `/daily-time-log/weekly-review` | 500 ms | 100–220 ms |
| `/raja-guru/day-plan` | 300 ms | 40–120 ms |
| `/raja-guru/next-action` | 250 ms | 30–90 ms |
| `/time-store/time-audit` | 400 ms | 60–180 ms |
| `/time-store/services?save_minutes_per_day=30` | 300 ms | 40–100 ms |

## 7. Capacity model (unchanged)
1 M users, 1% DAU, 25% peak-hour, 3 req/min/user → ~7.5k req/min. Headroom 16k req/min across 4×4 pods.

## 8. Failure modes (unchanged v3.4)
Mongo failover 5–15 s of 503s; LLM budget exhausted → 503s on AI endpoints only; bad migration → mongorestore runbook.

## 9. v3.5 specific risk
- Auto-rollup can pull large result sets if user has 1000+ CTT tasks completed on a single day. Mitigation: limit on each source collection (200 CTT, 20 meditation, 20 journal).
- Time Store audit scans user's full Matrix. Matrix rows capped at 84 cells, so bounded.
- Raja Guru scoring is CPU-bounded; p99 observed ≈ 60 ms for 50-task workload.

---
## v3.14.0 — Tier Matrix · Customer Segments · Pricing (2026-05-07)

### Functional requirements
- F-TM-1: Admin can toggle module × tier cells with server-side cascade rules
- F-TM-2: Module-dominates rule forces all features=N when parent module=N
- F-CS-1: Admin can create / read / update / delete customer segments
- F-CS-2: Each segment auto-seeds 23 predefined factors across 4 categories
- F-CS-3: Admin can add unlimited custom factors with arbitrary keys
- F-CS-4: Per-factor AI-Research endpoint returns one-line value (LLM with static fallback dict)
- F-CS-5: Each segment supports multi-currency multi-country tier pricing
- F-PR-1: Public `/api/pricing` returns combined payload (tiers + segments + matrix_rows)

### Non-functional requirements
- NFR-TM-1: Indexed `(module_id, feature_id, tier_key)` composite unique
- NFR-CS-1: Indexed `segment_id` unique + `created_at` desc + `chakra_tier_link`
- NFR-PR-1: 60s in-process TTL cache on `/api/pricing`; invalidated on admin writes
- NFR-PR-2: Cache hit latency ≤ 10ms; cold latency ≤ 50ms (verified)
- NFR-AI-1: AI-research falls back to static dict if LLM budget capped (no user-facing error)

### Data model
- `db.tier_matrix`: `{module_id, feature_id, tier_key, allowed, updated_at, updated_by}`
- `db.customer_segments`: `{segment_id, name, description, chakra_tier_link, factors[], market_research_module_ids[], tier_pricings[], created_at, updated_at}`

---
## v3.15.0 — 8-Step Pros & Cons / SWOT Framework (2026-05-18)

### Functional requirements
- F-FW-1: Both Pros & Cons and SWOT analyses persist `factors[]`, `options[]`, `assessments{option_id:{factor_id:cell}}`, `config`, `current_step` alongside legacy quadrants/lists
- F-FW-2: `POST /{base}/{id}/factors` creates a Direct factor with optional `expected_value` + `unit` (Step #1.1)
- F-FW-3: `POST /{base}/{id}/options` and `POST .../options/{oid}/(pros|cons)` capture P&C per option (Step #2)
- F-FW-4: `POST .../promote-pros-cons` is idempotent; Cons text gets `"SHOULD NOT - "` prefix when promoted to a factor (Step #3.1); `source` + `source_option_id` + `source_item_id` preserved (Step #3.2)
- F-FW-5: `PUT .../factors/{fid}` accepts `parent_id` for sub-factor grouping (Step #4) and Mandatory/Optional notation (Step #6.1)
- F-FW-6: `PUT .../config` accepts `mandatory_threshold_pct` (Step #6.2)
- F-FW-7: `POST .../factors/reorder` accepts an ordered list of IDs → renumbers `priority_rank` (Step #7.1)
- F-FW-8: `PUT .../assessments/{oid}/{fid}` derives `cell_value = assessment_pct × std_rating / 100` and `satisfaction_value = realistic_rating × satisfaction_pct` (Step #7.2, #8.8)
- F-FW-9: `GET .../aggregate` returns per-option `joint_score`, `overall_satisfaction_pct`, `disqualified`, `rank_high_to_low`, plus 12 Final Decision Guidelines

### Non-functional requirements
- NFR-FW-1: Backward compatible — legacy `pros[]/cons[]` on Pros & Cons and `strengths/weaknesses/opportunities/threats` on SWOT remain readable
- NFR-FW-2: Cell-level mutations atomic on a single document (no two-phase commit needed)
- NFR-FW-3: Aggregate is computed on read and cached into `rollups[]` for cheap subsequent reads
- NFR-FW-4: Knock-out detection runs in O(factors × options) per aggregate — bounded by user input
- NFR-FW-5: New endpoints respect the same auth (Bearer) and rate-limit class as legacy Pros & Cons / SWOT
- NFR-FW-6: Shared model file `models/decision_framework_models.py` keeps math helpers pure (testable without DB)

### Data model additions
- `pros_cons`: + `options[]`, `factors[]`, `assessments{}`, `config{}`, `rollups[]`, `current_step`
- `swot_analyses`: same six fields appended
- `FrameworkFactor` schema: `id, name, expected_value, unit, source(direct|pro|con), source_option_id, source_item_id, parent_id, notation(mandatory|optional), priority_rank, std_rating, factor_type(subjective|objective), improvable(y|y_bf|n), my_expectation, others_expectations, market_standard, realistic_gap_pct, realistic_gap_value, realistic_rating, notes`
- `AssessmentCell` schema: `assessment_pct, cell_value, actual_value, satisfaction_pct, improvement_pct, satisfaction_value, notes`
- `FrameworkConfig` schema: `mandatory_threshold_pct, max_improvement_period_months, std_gap, gap_bands{low|standard|high|double}`

### API surface
+ 18 new endpoints on `/api/pros-cons/*`
+ 18 new endpoints on `/api/swot/*`
= 36 new endpoints (total app endpoints now 736)

### Performance target
- p95 < 250 ms on all new endpoints (single-document upserts on user-bounded data)
