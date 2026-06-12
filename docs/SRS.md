# System Requirements Specification — Dezider

_metadata: { "version": "3.17.1", "updated": "2026-06-12" }

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

---
## v3.16.0 — PostHog Replays · Revenue Recon · Import-URL v3 · AI Wallet (2026-06-12)

### Functional requirements
- F-PH-1: Web client uses `posthog-js` for session replay; native uses `posthog-react-native` (events-only).
- F-PH-2: Replay never persists raw input bodies (`maskAllInputs:true`, `capture_performance:false`).
- F-PH-3: Backend emits server-truth events (signup / payment_success / ai_credits_consumed / otp_sent / eg_session_completed) via `core/posthog_client.py`, no-op when key missing.
- F-RC-1: Daily Razorpay sync, incremental with 5-day overlap, into `recon_rzp_payments / recon_rzp_transfers / recon_rzp_settlements`.
- F-RC-2: BigQuery Billing Export (Gemini cost) pulled into `recon_gcp_daily` with 2 GB max-bytes-billed guard.
- F-RC-3: Per-txn tally exposes `at_loss=true` when `collected − rzp_fee − routed_markup − earmarked_cost_inr < 0`.
- F-RC-4: Daily tally compares LLM token-derived ₹ estimate vs GCP actual cost; variance surfaced.
- F-RC-5: All `/api/admin/recon/*` routes gated by `require_super_admin`.
- F-IU-1: `Factor.factor_type` persisted (`quantitative | qualitative`) on every Factor through all 4 create/merge paths in `core/decision_builder.py`.
- F-IU-2: `core/url_detail.py` returns groups-based schema with `source: page | ai | none`; page-defined groups never overridden by AI.
- F-IU-3: Server-side guard flattens AI-grouping when factor count ≤ `import_group_threshold` (default 15).
- F-IU-4: Hints (`expected_factor_count`, `expected_option_count`, `first_factor_name`, `first_option_name`) validated; ONE corrective self-heal retry on mismatch beyond ±max(2, 20%).
- F-IU-5: Unknown value keys DROPPED from items (zero-tolerance on option↔factor value mapping).
- F-IU-6: `POST /url-analyze/decision/{id}/set-expectations` updates `expected_value + operator` on leaf factors only (parents untouched); 422-gated until factors + options + ≥1 unit_value present.
- F-AW-1: AI Wallet config persists `precise_model`, `precise_usd_per_mtok`, `import_group_threshold`; validated `>0`.
- F-AW-2: `metered_chat(tier="precise")` routes to Claude FIRST via Emergent Universal Key; falls back Claude → Gemini → OpenAI → Groq; charges at multiplier (`precise_usd_per_mtok / blended_usd_per_mtok`) preserving zero-loss invariant.

### Non-functional requirements
- NFR-PH-1: Posthog client never raises; missing key → no-op log only.
- NFR-PH-2: `posthog-js` bundled at frontend build time (Cloudflare Pages) — no runtime fetch dependency.
- NFR-RC-1: `/api/admin/recon/sync` is idempotent (incremental cursor with 5d overlap).
- NFR-RC-2: BigQuery query bounded to 2 GB scan to cap GCP cost.
- NFR-RC-3: CSV export streams via PlainTextResponse (no in-memory buffering).
- NFR-IU-1: Import endpoints fetch the page ONCE per call (rendered HTML via ScraperAPI when configured).
- NFR-IU-2: DETAIL_MAX_FACTORS=24 cap on extraction output.
- NFR-IU-3: Import LLM call timeout 180s (300s with hints).
- NFR-AW-1: Wallet ledger writes are atomic per debit; PostHog `ai_credits_consumed` emitted with feature + provider + balance_after.

### Data model additions
- `settings.ai_wallet.config` → +`precise_model`, +`precise_usd_per_mtok`, +`import_group_threshold`.
- `decisions.factors[].factor_type` → `'quantitative' | 'qualitative'`.
- `recon_rzp_payments`, `recon_rzp_transfers`, `recon_rzp_settlements`, `recon_gcp_daily`, `recon_config` (singleton, holds b64 GCP SA JSON), `recon_runs`.

### Index plan additions (v3.16)
- `recon_rzp_payments.payment_id` unique; `recon_rzp_payments.created_at` desc
- `recon_rzp_transfers.transfer_id` unique; `recon_rzp_settlements.settlement_id` unique
- `recon_gcp_daily.usage_date` desc

### Performance targets (v3.16)
| Endpoint family | Target p95 | Measured |
|---|---|---|
| `/url-analyze/decision/{id}/import-v2` (rendered HTML + LLM) | 12 s | 4–8 s |
| `/url-analyze/decision/{id}/set-expectations` (Claude) | 8 s | 3–5 s |
| `/admin/recon/summary` | 400 ms | 80–180 ms |
| `/admin/recon/sync` (incremental, 100 payments) | 30 s | 4–12 s |
| `/admin/ai-wallet/config` (read/write) | 200 ms | 30–60 ms |

### v3.16 known structural risk
- **Markup routing**: Razorpay Route sends the entire markup to the linked account; primary account therefore nets `collected − fee − markup ≈ cost − fee`, structurally slightly BELOW the earmarked Gemini cost. Mitigation: raise `markup_user_pct` (admin → AI Wallet Config) OR retain part of markup in the primary account.

---
## v3.16.1 — Import-URL extraction routing requirements (2026-06-12)

### FR-IU-10 Hint-gated routing (NEW)
When ANY accuracy hint (`expected_factor_count`, `expected_option_count`,
`first_factor_name`, `first_option_name`) is supplied:
- Deterministic parses (hierarchical matrix, flat table, product grid) MUST be
  validated against the hints BEFORE being merged; a mismatching parse MUST
  NOT be returned while the AI path is available.
- The AI extraction MUST receive the hints as ground-truth facts in its FIRST
  prompt, and MUST be re-validated post-hoc (one corrective retry).
- If the AI output matches the hints WORSE than the deterministic parse, the
  deterministic parse wins; if the AI path fails, the deterministic parse is
  merged with `hint_warnings` populated — the import never hard-fails when a
  parse exists.

### FR-IU-11 Comparison/listing page extraction (NEW)
The AI extractor MUST handle multi-item comparison / listing / filter pages
(page_type="comparison"): factors = the page's own comparison facets/filter
labels; options = the listed items in page order; peer items are scored purely
against expectations (NO forced 100% main item).

### FR-IU-12 Precise-tier guarantee (NEW)
A request with `ai_tier="precise"` MUST escalate thin deterministic parses
(<3 factors) to the Claude engine even when no hints are given — the user
explicitly chose AI-grade extraction.

---
## v3.17.0 — Import-URL Intelligence requirements (2026-06-12)

### FR-IU-13 Page-type classification (NEW)
Every non-JSON import/analyze run MUST be LLM-classified (fast tier) into one
of: comparison_matrix | listing_filter | detail | search_grid | article_roundup,
with confidence 0-1. On LLM failure a structural heuristic MUST be used —
classification MUST NOT block or fail an import.

### FR-IU-14 Prompt specialisation (NEW)
The extraction prompt MUST embed a page-type-specific guidance block selected
by the classifier (facet-factors for listing_filter, card-visible attributes
only for search_grid, author-verdict factor for article_roundup, page-defined
group preservation for comparison_matrix, exhaustive specs for detail).

### FR-IU-15 Run telemetry (NEW)
Every run (success AND error) MUST be persisted to `url_import_runs` with:
url, hints, ai_tier, page_type(+confidence, classifier provider), route
(deterministic_hier | deterministic_flat | ai_extraction |
deterministic_fallback | llm_flat_fallback), outcome counts, hint_warnings,
hint_pass, latency_ms, ai tokens/retry flag, exact system prompt + raw LLM
response truncated to 15 KB, status/error. Prompt/response bodies MUST be
purged after 90 days (metadata retained). A lightweight PostHog event
`url_import_completed` MUST be emitted per run. Telemetry failures MUST be
non-fatal to the import.

### FR-IU-16 Accuracy feedback (NEW)
`POST /api/url-analyze/runs/{run_id}/feedback {verdict: up|down}` — owner-only,
last vote wins; emits PostHog `url_import_feedback`. Step 2 MUST surface a
1-tap chip after each URL import.

### FR-IU-17 Admin analytics (NEW)
Super-admin-only endpoints under `/api/admin/import-analytics/*` (summary,
runs list with page_type/route/status/feedback filters + input validation,
run detail incl. prompt bodies) powering `/admin/import-analytics`.

---
## v3.17.1 — Auto-Tune requirements (2026-06-12)

### FR-IU-18 AI prompt suggestions (NEW)
On demand, the system MUST analyse failing runs (status=error OR
hint_pass=false OR feedback=down) per page type from `url_import_runs` and
produce a proposed revision of that page type's guidance block (precise tier,
metered to the requesting admin), stored as status="proposed" in
`prompt_tuning_suggestions`. At most ONE pending suggestion per page type.

### FR-IU-19 Override lifecycle (NEW)
Approve → upsert `url_prompt_overrides[key=page_type]`; the extraction prompt
MUST use the override over the built-in block from the next run onward
(`get_active_guidance`). Reject → archive only. Revert → delete override,
built-in default applies. Deciding a non-proposed suggestion → 409. All
endpoints super-admin only. Override reads MUST fail open to the built-in
default (guidance can never block an import).
