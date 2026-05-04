# System Requirements Specification — Dezider

_metadata: { "version": "3.5", "updated": "2026-05-04" }

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
