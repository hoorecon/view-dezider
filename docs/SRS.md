# System Requirements Specification — Dezider

_metadata: { "version": "3.23.0", "updated": "2026-07-19" }

> **v3.23.0 (2026-07-19):** **FRAME @ scale** — Option-Bank Finder (indexed pre-filter → streamed heap Top-K, async jobs with % progress + 'finder' loader-music slot, benchmarked 200K options in 2.65s), 3-source ingestion (Solution Store/ReviewNet · partner APIs · Deep-Import/bulk), **AdMaker Studio** (advertiser self-serve on the SAME user login, ACM-gated `admaker_program`), **AdTaker publisher identity** (API Key + Secret self-serve rail AND Org-login portal). Full section at the end of this document.

> **v3.22.0 (2026-07-19):** **FRAME** — the Finder Ranking & Monetization Engine spec (Filter → Rank → Auction → Merge → Embed) for DeciderApps: organic Top-N (money can never reorder it), hierarchical Min-Cutoff % quality gate from the Central Catalog Manager, **AdMaker** Sponsored-Solutions auction (AdRank = bid × Quality Score, GSP pricing, region + time-slot targeting), and **AdTaker** embeddable widgets with tracker IDs + publisher revenue share. See the full section at the end of this document.

> **v3.21.0 (2026-07-13):** New non-functional/integration items — **Stripe** payment rail (`/api/stripe/*`, USD/INR, idempotent server-side-priced checkout for wallet + subscriptions); **AI Assistant** model policy = Claude default + quota-based fallback to `gpt-4.1-mini`; **auth** `effective_whatsapp_verified` applied at register/google-session; **build** `opencv-python==4.11.0.86` pin; env adds `SECRET_KEY`/`CORS_ORIGINS`. Architecture overview: see `SYSTEM_KT`.

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

**Voice / audio (NEW v3.19)**: `conflict_audio_files` — one row per saved voice clip in The Conflict Breaker. Schema: `audio_id` (uuid), `session_id`, `user_id`, `module="conflict-breaker"`, `field` (e.g. "about", "emotions_strong"), `ext` (webm|wav|mp3|m4a|ogg), `content_type`, `size_bytes`, `duration_sec`, `rel_path` (relative to `/app/backend/uploads/conflict_audio/`), `credits_charged`, `retention_days`, `created_at`. Index: `(user_id, audio_id)` unique, `(session_id, field)`.

**AI Wallet config additions (v3.19)** — within the existing `ai_wallet_config` doc, four new fields whitelisted in `update_config`: `audio_storage_usd_per_gb_month` (default 0.023), `audio_storage_retention_days` (90), `audio_storage_markup_pct` (30.0), `audio_max_upload_mb` (10.0). Ledger features for revenue-recon split: `conflict_breaker_audio` (storage, provider=`storage`) and `cb_voice_transcribe` (provider=`whisper`).

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

---
## v3.18.0 — Notification Engine requirements (2026-06-12)

### FR-NE-1 Trigger-event registry (NEW)
The system MUST expose a fixed registry of trigger-event keys (initial:
`import-analytics` scheduled, `import-run-failed` event), each declaring kind,
description, default schedule and a payload-builder. Admins MUST only be able
to create triggers for registered keys (400 otherwise).

### FR-NE-2 Trigger CRUD (NEW)
Super-admin-only CRUD over `notification_triggers` documents. Channel lists
MUST be validated (email regex; WhatsApp 10–15 digits, normalised) and
de-duplicated. Schedules MUST validate frequency/day/time/IANA timezone.
Event-kind triggers MUST NOT accept a schedule (400).

### FR-NE-3 Scheduling (NEW)
A 60-second scheduler tick MUST fire every enabled scheduled trigger whose
`next_run_at <= now`, then recompute `next_run_at` from the trigger's
timezone-aware schedule. Exactly one scheduler MUST run across uvicorn
workers (fcntl singleton lock; `NOTIFICATION_SCHEDULER_DISABLED` opt-out).
Boot MUST idempotently seed the default weekly import-analytics digest
(Mon 09:00 Asia/Kolkata, email channel ON with empty recipients).

### FR-NE-4 Event emission + throttling (NEW)
`emit_event(key, payload)` MUST dispatch all enabled event-kind triggers for
that key unless the trigger ran within its `throttle_minutes` window. Emission
MUST be fire-and-forget and MUST NEVER break the calling flow (import runs).
`url_telemetry.record_run` MUST emit `import-run-failed` on non-success runs.

### FR-NE-5 Channel dispatch + run log (NEW)
Each dispatch MUST attempt every recipient on every ENABLED channel
(email→Resend, whatsapp→UltraMsg), record per-recipient outcomes to
`notification_runs` (statuses: sent / failed / skipped_no_recipients / error),
update the trigger's `last_run_at`/`last_status`, and lazily prune the log to
the newest ~500 entries. Test sends MUST NOT mutate schedule/throttle state.

### FR-NE-6 Admin UI (NEW)
`/admin/notification-engine` MUST list triggers (kind badge, schedule label,
next/last run), allow inline enable + per-channel toggles, full create/edit
modal (event picker, schedule, recipients chips, throttle), instant "Test now"
with per-channel delivery report, and show the recent dispatch log.

---
## v3.22.0 — FRAME: Finder Ranking & Monetization Engine · AdMaker · AdTaker (2026-07-19)

**FRAME** = **F**ilter → **R**ank → **A**uction → **M**erge → **E**mbed.
The end-to-end pipeline behind every DeciderApp run. Design principles are borrowed from the
best-understood ranking/monetization systems in the industry:

| Principle | Borrowed from | FRAME rule |
|---|---|---|
| Hard constraints before scoring | Amazon retrieval (candidate generation → ranking) | Mandatory factors FILTER before anything is scored |
| Organic is sacred | Google Search (organic ≠ paid) | Money can NEVER reorder the organic Top-N |
| Ads must be relevant | Google AdWords (AdRank = bid × Quality Score) | A bid only competes if its option clears the user's own quality cutoff |
| Pay the minimum to win | GSP auction (AdWords) | Winner pays `next AdRank ÷ own QS + ₹0.01`, never above its own bid |
| Config cascades | Apple entitlements / iOS profiles | Cutoff & slot-count inherit down the Central Catalog: leaf overrides win |
| Distribution network | AdSense @ GDN, Meta Audience Network | Any DeciderApp embeds on 3rd-party sites with a tracker ID + revenue share |

### Stage 1 — FILTER (eligibility funnel) `core/finder_engine.run_finder`
1. Apply every **Mandatory** (Step-3 "primary") factor that has an expectation as a boolean,
   operator-aware constraint (`match_rule` = all|any across a factor's sub-factors).
2. Adaptive funnel: if survivors < `min_options` → **relax** to the full option set
   (stage=`relaxed_all`); if survivors > `max_options` → **tighten** with Optional
   ("secondary") factors too (stage=`mandatory+optional`) but only when that still leaves
   ≥ `min_options`.
3. Complexity O(options × factors) — deterministic, no LLM in the hot path.

### Stage 2 — RANK (quality scoring, organic)
- Leaf score (0–100) is operator-directional: `≤ target` → `min(100, target/actual·100)`;
  `≥ target` → `min(100, actual/target·100)`; `=` → proximity decay; text ops → binary;
  no expectation → the option's own % value stands in.
- Roll-up 1: sub-factor → main factor by **Split %** weights (authoring enforces Σ=100).
- Roll-up 2: main factor → **Overall Suitability %** by the user's Step-4 priority ratings
  (rating-weighted mean; equal weights when the user skipped prioritization).
- Optional `engine=llm`: missing actuals are AI-filled for the survivor set ONLY (bounded
  cost), then the SAME deterministic scorer runs — the math never changes.
- Organic list = survivors sorted by Overall %, top `top_n` returned. **No pay-to-play.**

### Stage 3 — QUALITY GATE (Min-Cutoff %, hierarchical) `core/ad_auction.resolve_ad_config`
Only options with `Overall % ≥ min_cutoff_pct` are auction-eligible ("Sponsored" can never
be a worse match than the user's own bar). Resolution precedence, nearest wins:
```
template.finder_settings.min_cutoff_pct / sponsored_n     (per-app override)
  → CCM node chain: Scenario(L3) → Category(L2) → SubArea(L1) → LifeArea(L0)
      (catalog_nodes.finder_ad_config, per-key inheritance; -1 clears an override)
  → global admin defaults (ai_wallet_config.finder_min_cutoff_pct=60, finder_sponsored_n=3)
```
Templates map to the catalog via `decider_store_templates.catalog_node_id`
(Admin → Decider Store → "Catalog" action).

### Stage 4 — AUCTION (AdMaker Program) `core/ad_auction.score_bids`
- **Bid** = `{template_id, option_name, advertiser_name, region('global'|country),
  bid_paise, budget_paise, slot_start/slot_end (calendar window),
  daily_start_hour/daily_end_hour + timezone (dayparting, overnight wrap supported),
  status active|paused|exhausted}` in `admaker_bids`.
- Liveness (`bid_is_live`, pure): active + budget not exhausted + region matches the
  runner's region (body.region → user.country → 'global') + inside calendar window +
  inside daily hours in the bid's IANA timezone.
- **AdRank = bid_paise × QualityScore**, QS = Overall %/100 (floor 0.05). One slot per
  option (strongest bid wins the option). Top `sponsored_n` by AdRank win slots.
- **GSP price**: winner i pays `⌊AdRank(i+1) ÷ QS(i)⌋ + 1` paise, clamped to
  `[reserve=1, own bid]`; last winner pays the reserve. Charged **per click** (CPC) via
  `POST /api/admaker/track`; budget exhaustion auto-pauses (status=exhausted).
- Impressions logged per run (`admaker_events`), the computed CPC snapshots to
  `last_price_paise`.

### Stage 5 — MERGE (assembly, trust-preserving)
`POST /api/decisions/{id}/finder/run` returns:
```
organic:   result.top (unchanged, ranked by Overall % only)
sponsored: result.sponsored — rendered BELOW the organic list, each card labelled
           "AD / Promoted by <advertiser>"; bid amounts & CPC prices NEVER exposed
ad_config: {min_cutoff_pct, sponsored_n, region, eligible_above_cutoff}
```
Persisted: `decisions.finder_sponsored_ids` next to `finder_result_ids`.

### Stage 6 — EMBED (AdTaker Program) `routes/adtaker.py`
- **Publisher** = `{publisher_id, tracker_id "DZ-PUB-XXXXXXXX", name, site_url,
  revenue_share_pct (default ai_wallet_config.adtaker_default_share_pct=68),
  status}` in `adtaker_publishers` (tracker minted server-side, AdSense-style).
- Drop-in snippet (any 3rd-party site):
  `<script src="{host}/api/adtaker/widget.js?tracker=DZ-PUB-…&app={template_id}"></script>`
  → injects a responsive iframe → `GET /api/adtaker/embed/{template_id}?tracker=…`
  (self-contained HTML card, `frame-ancestors *`, brand color from the template).
- Telemetry: embed render logs an **impression**; the CTA beacons a **click**
  (`POST /api/adtaker/track`, public) and deep-links to
  `/decider-store/{id}?ref={tracker}`; a clone with `ref` logs a **conversion**
  (`routes/decider_store.clone` → `adtaker.log_conversion`). All events in
  `adtaker_events` keyed by tracker.
- Earnings estimate (per publisher stats): `conversions × adtaker_conversion_bounty_paise
  (default 500) × revenue_share_pct%`. CPC-share upgrade path reserved for when AdMaker
  clicks are attributed through embeds.

### Functional requirements
- F-FR-1: Finder MUST return organic Top-N ranked ONLY by Overall Suitability % (funnel → score → sort); no monetization signal may affect organic order or membership.
- F-FR-2: Sponsored candidates MUST clear the resolved Min-Cutoff %; the resolution MUST honour template → CCM-chain → global precedence with per-key (cutoff vs slots) inheritance.
- F-FR-3: AdRank MUST equal bid × QualityScore; slot pricing MUST be GSP clamped to [reserve, own bid]; billing is per click; budget exhaustion MUST auto-set status=exhausted.
- F-FR-4: Bids MUST support region targeting ('global' or country code) and time-slot targeting (calendar window + daily hours in an IANA timezone, overnight wrap included).
- F-FR-5: Sponsored results MUST render BELOW organic, labelled "AD"/"Promoted by", and MUST NOT expose bid amounts or CPC prices to end users.
- F-FR-6: Admin CRUD: `/api/admaker/bids*` (bids), `/api/adtaker/publishers*` (publishers), `PUT /api/catalog/nodes/{id}` (finder_min_cutoff_pct / finder_sponsored_n, -1 clears), `PUT /api/admin/ai-wallet/config` (global defaults) — all admin/super-admin gated.
- F-FR-7: `GET /api/admaker/resolve-config?node_id|template_id` MUST expose the effective config AND the source of each value (template / node / global) for admin transparency.
- F-FR-8: AdTaker widget delivery MUST be public + iframe-safe; every embed render logs an impression, CTA click logs a click, attributed clone logs a conversion — all keyed by tracker ID; unknown/paused trackers are rejected (404).
- F-FR-9: Publisher stats MUST return totals, CTR, daily series and an earnings estimate derived from the conversion bounty × revenue share.

### Non-functional requirements
- NFR-FR-1: Auction math (`bid_is_live`, `score_bids`) is pure/DB-free (unit-testable); auction adds ≤1 indexed query per Finder run; O(bids log bids).
- NFR-FR-2: Ad-config resolution ≤ 8 ancestor hops, each an indexed point read.
- NFR-FR-3: Telemetry writes are fire-and-forget relative to UX; failures never break a Finder run, an embed render, or a clone.
- NFR-FR-4: Tracker IDs are unguessable (uuid4-derived) and unique-indexed; public track endpoint validates event whitelist + active tracker.
- NFR-FR-5: `widget.js` cacheable 5 min; embed HTML `no-store` (fresh impression accounting).

### Data model additions
- `catalog_nodes.finder_ad_config = {min_cutoff_pct?, sponsored_n?}` (any level, inherited).
- `decider_store_templates.catalog_node_id`; `finder_settings += {min_cutoff_pct?, sponsored_n?}`.
- `decisions.finder_sponsored_ids`.
- NEW `admaker_bids`, `admaker_events` (impression|click, price_paise), `adtaker_publishers`, `adtaker_events` (impression|click|conversion).
- `ai_wallet_config += {finder_min_cutoff_pct, finder_sponsored_n, adtaker_default_share_pct, adtaker_conversion_bounty_paise}`.

### Index plan additions (v3.22)
- `admaker_bids (template_id, status)`, `admaker_bids.created_at desc`
- `admaker_events (bid_id, ts desc)`, `(template_id, ts desc)`
- `adtaker_publishers.tracker_id` unique, `.publisher_id` unique
- `adtaker_events (tracker_id, ts desc)`, `(template_id, event)`

### API surface (v3.22)
`/api/admaker/*` (6 routes) + `/api/adtaker/*` (9 routes) + finder-run response extension + catalog-node ad-config fields. Admin UI: `/admin/ad-programs` (Bids · Publishers · Cutoffs & Slots), Decider-Store "Catalog" mapping + global Sponsored defaults in "Finder & Landing".

### Performance targets (v3.22)
| Endpoint family | Target p95 | Notes |
|---|---|---|
| finder/run incl. auction (deterministic) | 600 ms | auction adds 1 indexed query + O(bids log bids) |
| /adtaker/embed/{id} | 250 ms | 2 point reads + 1 insert |
| /adtaker/publishers/{id}/stats | 400 ms | single aggregation, tracker-indexed |
| /admaker/track (CPC charge) | 200 ms | 1 read + 2 writes |

---
## v3.23.0 — FRAME @ Scale: Option Bank · AdMaker Studio · AdTaker Identity (2026-07-19)

Extends FRAME (v3.22.0) from embedded options (≤ ~15K, Mongo doc cap) to a
search-engine-shaped pipeline able to serve the best Top-N out of **millions of
options in ≤ 60s**, plus advertiser/publisher identity rails.

### Part A — Option-Bank Finder (10M-option architecture)

**Shape**: candidate generation → light ranking → exact re-rank (the 3-tier
retrieval shape used by Google Search / Amazon product ranking).

```
S0 INGEST (pay parse cost ONCE)      decider_option_bank — 1 doc/option/template
   {bank_id, template_id, name, name_norm, source, source_ref,
    vals: {<sub_factor_id>: {num, txt}}}       ← pre-normalized at ingest
   Indexes: (template_id,name_norm) UNIQUE · (template_id,source) · vals.$** wildcard

S1 PRE-FILTER (inside the DB engine) mandatory expectations compile to native
   Mongo clauses (vals.<sid>.num ranges / .txt regex) → wildcard index prunes
   N → 10⁴-10⁵ BEFORE Python sees a row. Adaptive funnel preserved:
   too few → relaxed_all · too many → tighten with optional factors.
   Non-compilable ops become residual Python checks (never lose correctness).

S2 STREAM + HEAP (O(K) memory)       Motor cursor, projection = only needed
   vals paths, batch 5K, deterministic FRAME scorer, heapq Top-K (K≥50),
   progress % per batch, event-loop yield every 1K docs.

S3 RE-RANK + AUCTION                 unchanged v3.22 stages: quality gate →
   AdRank×GSP auction (bid-targeted bank options are scored individually via
   name_norm lookup even outside the heap — they still must clear the cutoff).

S4 ASYNC JOB + LOADER MUSIC          finder_jobs {status, progress{pct,label},
   result, spec_hash}; POST /api/decisions/{id}/finder/jobs (returns cached
   job when an identical expectations-hash finished < 10 min ago),
   GET /api/finder/jobs/{job_id}. Frontend polls @1.2s, renders a progress bar
   + the 'finder' loader-music slot (same UX contract as Deep-Import).
```

**Decision→Bank join**: cloned factors persist `source_sub_id` (the original
template sub-factor id — the bank's `vals` key). Legacy clones fall back to
normalized-name matching (`core.finder_bank.build_leaf_specs`).

**Ingestion — all 3 mandated sources** (`routes/option_bank.py`, admin):
1. INTERNAL — `POST /decider-store/{tid}/bank/sync-template` (embedded options)
   and `POST …/bank/ingest/solutions` (Solution-Store items bridged via
   `decider_template_id` + quantitative_factors keyed by sub-factor id, merged
   with ReviewNet `baseline_profile`).
2. PARTNER APIs — `POST …/bank/ingest/partner` {api_url, items_path, name_key,
   value_map {sub_id: json_key}, headers, limit}: fetch → map → normalize.
3. DEEP-IMPORT / BULK — `POST …/bank/ingest/bulk` {items[], source} (≤50K/call).
All rails converge on `finder_bank.bank_upsert` (idempotent on template+name).
Plus `GET …/bank` (stats by source), `DELETE …/bank?source=` (targeted clear).

**Measured benchmark** (`scripts/seed_finder_bank_synthetic.py`, single worker,
in-cluster Mongo, BMP template with ~60 leaf sub-factors):
| Metric | Value |
|---|---|
| Bank size | 200,000 synthetic options |
| S1 prune (indexed) | 200,000 → 25,026 candidates (mandatory+optional stage) |
| End-to-end pipeline | **2.65 s** |
| Scan throughput | ~9,400 options/s/worker at 60 leaves (scales inversely with leaf count) |
| Extrapolation | ≤60s SLA holds up to ~500K SCANNED candidates/worker; the indexed S1 filter is the contract that keeps scanned ≪ N at 10M. Scale-out levers (documented, not yet needed): batch-parallel scan across API pods, per-factor pre-scores, numeric quantization. |

**FRs**
- FB-FR-1: Bank pipeline MUST return the identical Top-N ordering the embedded scorer would produce for the same specs (same `_score` roll-up math — verified by unit tests).
- FB-FR-2: S1 MUST execute mandatory filtering inside MongoDB via the wildcard index; residual (non-compilable) constraints MUST still be enforced in-stream.
- FB-FR-3: Jobs MUST stream progress {pct,label}, terminate in done|error (never spin), and serve a spec-hash cache for identical re-runs within 10 min.
- FB-FR-4: All ingestion rails normalize values ONCE at ingest and upsert idempotently on (template_id, name_norm); per-source clear supported.
- FB-FR-5: The finder UI MUST auto-switch to job mode when bank_options > 0 (exposed by GET /finder/config) and keep the classic sync run otherwise.

### Part B — Identity architecture (AdMaker · AdTaker · OrgLogin)

**Identity ladder** (no third auth stack — deliberate):
```
Free user ──ACM tier──▶ Premium subscriber ──org membership──▶ Organization (OrgLogin)
     │                        │                                     │
  Solution Store         AdMaker Studio                    Publisher Portal (AdTaker)
  (list solutions)       (admaker_program,                 + white-label Partner Embed
                          paid_pro+ / trial)               + org member mgmt
```

**AdMaker = SAME user login.** ACM feature `ad_programs.admaker_program`
(ga_paid: trial/paid_pro/paid_enterprise full; free/paid_starter locked);
Org members with `org_role ∈ {org_admin, advertiser}` bypass the matrix;
platform admins always pass. Enforcement: `routes/admaker._require_admaker`.
- **AdMaker Studio** (`/admaker-studio`): metrics dashboard (impressions,
  clicks, CTR, spend, avg CPC, budget headroom — per bid + account totals via
  `GET /api/admaker/my/dashboard`) + self-serve bid CRUD (`/api/admaker/my/bids*`).
- **Ownership invariant**: advertisers may ONLY bid on options whose bridged
  Solution-Store listing they created (or a same-org member created) —
  `GET /api/admaker/my/eligible-options?template_id=` resolves the whitelist
  from `options[].linked_solution_id` ∪ bank `source_ref` × `solutions_store.created_by`.

**AdTaker = BOTH rails enabled.**
1. **API Key + Secret** (AdSense-style, no login): minted at publisher
   creation — `api_key` (`dzk_…`, public) + `api_secret` (`dzs_…`, returned
   ONCE, stored sha256-hashed). Admin can rotate
   (`POST /api/adtaker/publishers/{id}/rotate-keys` → old pair dies instantly).
   Self-serve API with `X-Adtaker-Key` / `X-Adtaker-Secret` headers:
   `GET /api/adtaker/self/profile | /self/stats?days= | /self/apps`
   (apps includes a ready-to-paste embed snippet per Decider App).
2. **Org-login portal**: admin links a publisher to an organization
   (`org_id` on the publisher). Org-authenticated members open
   `/adtaker-portal` (`GET /api/adtaker/portal/me`) → tracker ID, API key,
   snippet builder, 30-day stats + earnings estimate.

**Widget code (unchanged public contract)**:
`<script src="{host}/api/adtaker/widget.js?tracker=DZ-PUB-…&app={template_id}"></script>`
The tracker ID is deliberately public (it ships in page source, like AdSense
pub-IDs); the key+secret pair guards only the reporting/management API.

**FRs**
- ID-FR-1: No new auth stack: AdMaker rides user sessions + ACM; AdTaker rides API-key headers or Org sessions.
- ID-FR-2: API secrets are irrecoverable by design (hash-only storage); rotation invalidates the old pair atomically; secrets are shown exactly once (create/rotate responses + one-time admin modal).
- ID-FR-3: Publisher responses NEVER include `api_secret_hash`; self-serve endpoints reject paused publishers (403) and bad credentials (401).
- ID-FR-4: `/adtaker/portal/me` requires an org identity (403 otherwise) and returns only publishers whose org_id matches the caller's org.
- ID-FR-5: AdMaker Studio surfaces the ACM upgrade message on 403 (frontend shows the locked state + "See plans").

### Admin & UX surface (v3.23)
- Admin → Decider Store: per-template **Bank** modal (counts by source, sync-template, ingest-solutions, clear; partner/bulk documented as API).
- Admin → AdMaker & AdTaker → Publishers: API key display + copy, **Rotate keys** (one-time secret modal), Org-link field.
- `/finder/[id]`: auto job mode with progress bar + % + loader music ('finder' slot, admin-uploadable at Admin → Appearance); results show funnel numbers + duration; Step-7 link hidden in bank mode (bank results aren't embedded options).
- Decider Store hero (signed-in): quick links to **AdMaker Studio** and **Publisher Portal**.

### Index plan additions (v3.23)
- `decider_option_bank (template_id,name_norm) unique · (template_id,source) · vals.$** wildcard`
- `finder_jobs (decision_id,created_at desc) · (user_id,created_at desc)`

### Performance targets (v3.23)
| Path | Target | Measured |
|---|---|---|
| Bank job, ≤200K candidates after S1 | ≤ 30 s | 2.65 s @ 25K candidates / 60 leaves |
| Bank job, worst case (SLA) | ≤ 60 s | holds to ~500K scanned/worker |
| Spec-hash cache hit | instant | job reused < 10 min |
| /adtaker/self/* · /admaker/my/* | ≤ 400 ms p95 | indexed point reads + small aggregates |
