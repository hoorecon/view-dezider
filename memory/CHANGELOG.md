# Dezider — Session Changelog (chronological build log)
_Split out of PRD.md on 12 Jun 2026. Newest entries at the BOTTOM._

# Decision Reports & Intake Track (added 3 Jun 2026)

## User feedback captured
1. PDF formatting/branding — DONE (text wrap, "JELCOS AI").
2. Pros & Cons report completeness — DONE (single "Satisfaction %" = assessment %,
   worth-based ranking, life-area/decision-type labels, app-flow section order,
   MPPS analysis + Standard & Final Recommendation).
3. Timezone: "Generated" time in user's local zone (Profile/Self-contact `country`,
   default IST) — DONE (Phase 1).
4. Show initial intake info (For/Individual, Life Area, Need, Sub-area, Scenario, Title,
   Description) in PDF + list-detail.
5. Apply full treatment (intake + detailed %, Standard Rec, MPPS, Final Rec) to
   My Dezider, SWOT, Solution Finder reports (not just Pros & Cons).
6. Add Solution Finder items into Solution Box listing.
7. My Dezider MPPS must be enabled for ALL options (not just Rank #1) → re-rank by MPPS.
8. Back-fill existing items: Title/Life-area/Type only (Sub-area/Scenario unrecoverable).
9. Show "For: Individual/Org/Govt" acting-as line. 10. Solution Box intake persist+display.

## Open earlier request
- Share report by email (SendGrid/Resend) to non-registered (email) + registered
  (in-app "Shared with me"); free recipient access; "Shared by <facilitator>".

## Phases
- Phase 1 (DONE, tested): timezone in all PDFs; shared `_decision_overview_section`
  used by Pros&Cons/Dezider/SWOT; persist intake on Pros&Cons create
  (backend `ProsConsCreate` + `new-decision.tsx`); life-area/decision-type labels.
- Phase 2 (NEXT): list-detail intake display (Pros&Cons/Solution Box/Dezider/SWOT);
  Solution Box intake persist; add Solution Finder items to Solution Box; back-fill.
- Phase 3: My Dezider report parity (detailed %, ranking, Standard/MPPS/Final Rec).
- Phase 4: My Dezider MPPS for ALL options (engine + UI + re-rank).
- Phase 5: SWOT & Solution Finder report parity.
- Phase 6: Share report by email.

## Technical notes
- Pros&Cons MPPS = Step-8 `improvement_pct` delta; effective% = clamp(0..100,
  assessment%+improvement%); worth = joint_score / Σ std_rating × 100.
- My Dezider MPPS on `decisions` doc (`mpps_*`); worth via `calculateDynamicWorth`
  (`frontend/src/utils/decisionHelpers.ts`).
- Life-area canonical ids in models/decisions_models.py (DB may store `la_`-prefixed).
- Self-contact (`db.contacts`, is_self=True) `country` = Profile country → timezone.
- Report builder: `/app/backend/routes/decision_reports.py`.


---

# Decision Embed Framework (PMSBazaar pitch) — P0–P4 (built earlier this initiative)
- Multi-tenant partner embed config CRUD (`partner_embed.py`), white-label iframe widget + JS loader
  (`partner_embed_widget.py`), cross-origin pre-seeding, Bulk Screener engine (`screener.py`,
  `ScreenerPanel.tsx`) with flat-credit billing, and Admin Embed Console (`app/admin/embed-partners.tsx`).
- Demo org `pmsbazaar-demo` (frictionless). Re-seed: `python -m scripts.seed_embed_partner_demo`.

## Fork session — 8 Jun 2026 (verified, testing iteration_89)
- ✅ Issue 1 (legacy, was untested): My Dezider Step 10 "Complete Decision" button works (confirm →
  status=completed → redirect); ActionItemEditor → CTT / → LifeStyle port buttons clickable & navigate;
  Add Action Item modal inputs render as muted placeholders (not pre-filled). Verified end-to-end.
- ✅ Issue 2 (P2): Added 36 `embed-*` testIDs to embed-partners.tsx and 17 `screener-*` testIDs to
  ScreenerPanel.tsx. No logic change. Screener CSV→factors→quote→run flow re-verified.
- NOTE: newly added testIDs needed `sudo supervisorctl restart expo` for Metro to surface them.

## AI Assess gap-fill + Screener P3b — 8 Jun 2026 (tested, iteration_90)
- ✅ Screener P3b (AI assessment for qualitative TEXT factors on finalists) was ALREADY built
  (`screener.py::_ai_assess_finalists`, `use_ai` flag, `screener_ai_assess` meter) — verified working.
- ✅ My Dezider "AI Assess All" gap-fill: previously skipped cells missing Expected/Actual. Now the
  bulk dialog offers Cancel / Ready only / AI-fill all when gaps exist. AI-fill sends `force_fill=true`;
  backend `core/ai_assess.ai_assess_factor(force_fill=True)` runs an extra metered LLM call
  (`_forcefill_generate`, feature `ai_assess_fill`) to set a STANDARD Expected (+operator/unit) and a
  realistic estimated Actual, then scores %. Generated Expected/Operator/Unit are PERSISTED onto the
  factor (route `decisions/assessment.py` `$set` now writes `factors` too — bug fixed in iter90).
  Higher credits come naturally from the heavier token usage. Files: `core/ai_assess.py`,
  `routes/decisions/assessment.py`, `frontend/src/components/steps/Step7.tsx`.
- NOTE: dev LiteLLM proxy has a low budget cap ($0.4) that can 502 repeated live AI calls in sandbox.
- Test: `/app/backend/tests/test_ai_assess_force_fill.py`.

## URL Analyse + Screener→Decision bridge + Consent gate — 8 Jun 2026 (tested, iteration_91)
Full plan (Phases A–D) approved by user; all 11 backend tests + frontend e2e PASS.
- **Phase A — Screener → decision bridge**: `POST /api/embed/screener/run/{run_id}/to-decision`
  and `/to-pros-cons` convert a saved run into a MyDezider decision / Pros & Cons analysis
  (finalists→options, factors→ratings, per-factor pct→assessments). UI: "Send to MyDezider" /
  "Send to Pros & Cons" buttons on Screener results (`ScreenerPanel.tsx`).
- **Phase B — Standalone "Analyse a URL"**: new screen `app/tools/analyse-url.tsx` (+ entry in the
  prr New menu, testID `new-menu-analyse-url`). Crawls a comparison page, derives weighted factors,
  proportionally scores items, and auto-creates a decision (lands on Step 7). Backend:
  `routes/url_analyze.py` + shared `core/url_crawl.py` (fetch→HTML table→AI fallback) +
  `core/decision_builder.py` (shared by screener bridge & url-analyze).
- **Phase C — Legal/consent gate**: `UrlAccessConsentModal.tsx` — mandatory access-eligibility type
  (Own / Partner / Free-Public / Custom) + disclaimer acceptance before ANY pasted URL is processed
  (used by both Analyse-a-URL and the Screener paste-URL mode). Auditable consent stored in
  `db.url_access_consents` (user, url, eligibility_type, ip, ua, disclaimer_version, ts).
- **Phase D — PMSBazaar ranking demo**: `GET /api/embed/demo-host/pmsbazaar-demo?flow=screener`
  now shows ranking-engine framing ("Rank these for me").
- NOTE: dev LiteLLM budget cap can 502 the AI table-less extraction path; the HTML-table path needs
  no AI. Test: `/app/backend/tests/test_iter91_url_analyse_screener.py`.

## PROD BUG FIX — "AI Assess All" 405 burst → chunked batch — 8 Jun 2026 (tested, iteration_92)
- Symptom (jelcos.ai): "AI Assess All" → "Assessed 0 cells • N failed"; console showed 405 (Method
  Not Allowed) on every `/api/decisions/{id}/factors/{fid}/ai-assess` call, while the single-cell ✨AI
  button worked. Root cause: the bulk runner fired one POST PER CELL (47+ rapid requests) — a burst the
  production edge/CDN rejects with 405. Dev never reproduces (returns 502 not 405). Not a rate limit
  (0 succeeded; a limiter would let the first few through).
- Fix: new backend `POST /api/decisions/{decision_id}/ai-assess-batch` (≤12 cells/request) sharing a
  `_apply_assessment()` helper with the single-cell route. Frontend `Step7.tsx` `runBulkAssess` now
  chunks all empty cells (CHUNK=6) and calls the batch endpoint via the shared axios `api` instance
  (assessCellSilent removed). ~48 cells → ~8 requests instead of 48, on the proven single-POST path.
- Verified: backend 5/5 (`test_iter92_ai_assess_batch.py`); frontend network shows 2× batch calls for
  12 cells, 0 per-cell calls, no 405s; single-cell ✨AI regression intact.
- ⚠️ ACTION: user must REDEPLOY to jelcos.ai for the fix to take effect. Dev LiteLLM has a $0.4 budget
  cap that can still make "AI-fill all" cells fail inside the batch (not a code issue).

## Three UX changes: Step-2 URL import, Instant Dezider rename, Profile admin cleanup — 8 Jun 2026 (tested, iteration_93)
- **#1 Step 2 "Import from URL"** (MyDezider): new card in `Step2.tsx` → consent gate → `POST
  /api/url-analyze/decision/{id}/import` crawls a comparison page and MERGES factors (with suggested
  Expected values + operators), options (Step 6) and partial assessments (Step 7). Backend: new
  `merge_into_mydezider()` in `core/decision_builder.py` (name-matches to avoid dup factors/options).
  Reuses `crawl_candidates` + `_derive_factors_and_scores`. Curl + e2e verified.
- **#2 Rename "Test 123" → "Instant Dezider"** across New menu (now FIRST, before Decider), home
  "Decision Kickstarters" (first card), filter chips, list/new screens, voice parser, and
  `app/_layout.tsx` headerTitle. Internal route `/test123` + backend unchanged.
- **#3 Profile admin cleanup**: removed 387 lines (9 admin-module sections) from `app/(tabs)/profile.tsx`;
  replaced with a single admin-only "Admin Console" shortcut (testID `profile-open-admin-console`) →
  `/admin`. All those modules already live in the `/admin` console (ADMIN_NAV). Non-admin/user
  settings untouched. Gating `userRole !== 'user'` (hidden for regular users).
- NOTE: URL-import expected_value defaults to column max (cost-style "lower-is-better" factors may need
  the user to flip — out of scope, editable in Step 2). Dev LiteLLM budget cap still applies to AI paths.

## URL-import direction-awareness — 8 Jun 2026 (tested)
- `routes/url_analyze.py::_derive_factors_and_scores` now auto-detects "lower-is-better" columns
  (cost/fee/expense/price/charge/premium/risk/drawdown/debt/loss/latency/.../churn) via
  `_is_lower_better()`. Those factors get operator `<=`, Expected = column MIN, and inverted
  proportional scores (lowest value → 100%). Higher-is-better columns keep `>=`/MAX as before.
- Applies to BOTH standalone "Analyse a URL" and Step-2 "Import from URL". Verified e2e (Expense Ratio
  → `<=` 0.85, Alpha 100% / Gamma 0%) + unit test `tests/test_url_import_direction.py` (2 passed).

## Comparison-MATRIX parsing fix (GSMArena etc.) — 8 Jun 2026 (tested)
- Symptom: pasting a GSMArena phone-compare URL fetched fine (UA fix worked) but produced
  garbage factors ("col2", "col3", Expected 850.0). Root cause: GSMArena is a TRANSPOSED matrix —
  compared items are COLUMNS (names in the page `<title>`) and specs are ROWS split across ~15
  per-category tables — but our parser assumed row-per-item.
- Fix (`core/url_crawl.py`): new `_comparison_matrix_candidates()` parses transposed matrices
  (items from `_names_from_title()` "Compare A vs. B vs. C"; attributes prefixed with their
  category section header → readable factor names like "Body · Weight", "Battery · Capacity").
  A `_is_low_quality()` gate (generic colN keys / <2 items) routes standard-parse misses into the
  matrix parser, then the AI fallback. Standard row-per-item tables (fixture funds.html) still use
  the original path.
- Fix (`routes/url_analyze.py`): new `_measure_num()` only treats CLEAN single measurements as
  numeric ("169 g (5.96 oz)", "3500 mAh") and REJECTS messy spec strings ("GSM 850 / 900",
  "2018, August", "256GB 12GB RAM") — killing the fake-850 numeric factors. Derive now also drops
  over-long columns (avg>60 chars) and tie-breaks toward tidier values; messy specs become
  qualitative factors instead of bogus numerics.
- Verified e2e on the live GSMArena URL: 3 phones → options; "Body · Weight" & "Battery · Capacity"
  numeric+scored; band/date/OS columns now qualitative. Offline regression `tests/test_url_matrix_parse.py`
  (5 passed) + iter91/direction still green (13 passed). Fixtures added: phone_compare.html, funds.html.
- ⚠️ Heuristic ceiling: free-text spec sites yield only a few clean numeric factors (rest qualitative).
  Truly clean factor extraction (Battery mAh, RAM, Price as numerics) would need LLM refinement
  (user's key) — offered as a follow-up. JS-rendered retail (Amazon) still needs a headless/scraping API.
- ⚠️ Prod (jelcos.ai) must REDEPLOY.

## FULL HIERARCHICAL URL import (GSMArena benchmark) — 8 Jun 2026 (tested iter94)
- Requirement: pasting a category-grouped comparison page (GSMArena phone-compare) into "Analyse a URL"
  must import the COMPLETE two-level structure into MyDezider Step 2 — each spec CATEGORY → a main/parent
  factor, each spec ROW → a sub-factor, compared items → options, all cells assessed.
- `core/url_crawl.py`: extracted shared `_fetch_html()` (browser headers + retry); added
  `parse_hierarchy()` / `crawl_hierarchy()` → {items (from <title>), groups:[{category, rows:[{label,values}]}]}.
  GSMArena → 15 categories (Network…EU LABEL), correct sub-specs (Body→Dimensions/Weight/Build/SIM).
- `core/decision_builder.py`: `create_hierarchical_mydezider()` builds 15 parent factors (rating 50) +
  sub-factors (parent_id, weights split to EXACTLY 100 via last-sub remainder) + options with LEAF
  assessments (percentage + raw value as unit_value). `_effective_pct()`/`_hier_worth()` mirror the
  frontend's weighted sub-factor rollup so stored worth matches the UI.
- `routes/url_analyze.py`: `_score_hierarchy_numeric()` (proportional, direction-aware) + `_ai_score_text_rows()`
  (ONE metered LLM call scoring all text specs 0-100, best-effort — graceful no-op if wallet empty).
  `analyze_url` auto-routes category-grouped matrices to the hierarchical builder; flat derive is the fallback.
- Verified (iter94, testing agent): Step 2 renders 15/15 parents + 55/55 sub-factors, expand/collapse + split UI
  working, 3 options (Oppo F9 / Find X9s Pro / Galaxy A57). Backend: `POST /api/url-analyze` → mode='hierarchical',
  category_count=15, item_count=3. Graceful degradation confirmed when LLM wallet is empty (structure + raw
  values still build; user can run "AI Assess All"). New tests: test_url_matrix_parse.py (incl. hierarchy),
  test_iter94_url_hierarchy_import.py. Fixed cosmetic weight-total 100.02% float display (Step2.tsx tolerance +
  builder exact-100 weights).
- ⚠️ AI cell-scoring consumes Emergent-LLM credits (one batched call per import). ⚠️ Redeploy jelcos.ai.
- Pending follow-up: option 3 = LLM factor refinement (done as part of this) + headless/scraping API for
  JS-rendered retail (Amazon) — NOT yet wired; needed only for non-static sites.

## Emotional Gatekeeper AI now METERED + per-session cost + session filters — 10 Jun 2026 (tested)
- **Was unmetered**: all EG AI (`ai_engine._call_llm`) hit the Emergent key directly — no wallet gate,
  no per-user charge, not on the free-first chain (→ hard 500s, no "charge wallet" prompt).
- **Part A — metering**: `ai_engine._call_llm/_call_llm_json` now route through `ai_metering.metered_chat`
  with `feature` (eg_trap_analyze / eg_loop_recommend / eg_loop_reframe / eg_limitation_classify /
  eg_limitation_reframe / eg_outlet_analyze / eg_aim_analyze / eg_breakthrough_report) + `session_id`.
  Threaded user_id+session_id through all 8 AI fns + their routes (trap/loop/limitation/outlet_aim/
  session-report). Errors mapped: `402 {code:insufficient_credits}`, `503 {code:ai_unavailable}`,
  `502 {code:ai_error}` (routes re-raise HTTPException instead of wrapping as 500).
- **Per-session cost**: `ai_wallet._ledger`/`charge` now store `session_id`; new `ai_wallet.session_cost()`.
  `GET /sessions/{id}` returns `ai_cost {credits, calls}`, shown as a chip on the session screen.
- **Part B — frontend prompts**: shared `src/utils/aiErrors.ts::handleAiError` wired into eg-trap/loop/
  limitation/aim/session — shows "Charge Wallet" (402), "Use OpenAI (share data)" consent + Top-up
  (503 ai_unavailable), or generic retry. Each passes a `retry` callback.
- **Part C — session history**: Recent Sessions expanded inline with filter chips (status: All/In
  progress/Completed, type: All/Trap/Loop/Limitation/Outlet/AIM) via `GET /sessions?status=&session_type=`.
- **Verified (curl)**: trap analyze 200 charges wallet (≈25 cr, provider gemini→groq), ledger tagged
  session_id+feature, `ai_cost` returned; 0 credits → 402 insufficient_credits; session filters return
  correct subsets. Frontend lint clean.
- ⚠️ Redeploy jelcos.ai + set GROQ_API_KEY/OPENAI_API_KEY in prod .env. ⚠️ OpenAI key out of quota (429).

## Voice transcription 500 fixed — Whisper (Groq→OpenAI) replaces Google STT — 10 Jun 2026 (tested)
- **Bug**: EG-Trap "Voice Input" → 500 ("Transcription failed"). Root cause reproduced in dev:
  the STT engine used Google's unofficial free STT (`SpeechRecognition`+`pydub`), which needs the
  `flac` CLI (missing → uncaught `OSError` → **500**) and `ffmpeg` for webm. Only `ValueError` was caught.
- **Fix** (`routes/social_learning/stt_engine.py`): `STTEngine.transcribe` now uses **litellm Whisper**
  — `groq/whisper-large-v3-turbo` (free) PRIMARY → OpenAI `whisper-1` FALLBACK. Accepts wav/webm/mp3/m4a
  **directly (no ffmpeg/flac/pydub)**. Raises `ValueError` (→ 400 "type instead") only when every provider
  fails — never an uncaught 500. Benefits all callers (EG-Trap voice + social-learning upload).
  Also hardened `trap_routes` content-type parsing to strip `;codecs=opus` and default to webm.
- **Verified**: round-trip + `tests/test_stt_whisper.py` 2/2 pass — real harvard.wav transcribes
  accurately via Groq free tier; no-provider → ValueError (not 500).
- ⚠️ The user's `OPENAI_API_KEY` is currently **out of quota (429)** — OpenAI fallback (chat & Whisper)
  won't work until they enable billing / the free data-sharing tier; Groq (free) is the working primary.
- ⚠️ Redeploy jelcos.ai + set `GROQ_API_KEY` in prod .env for this to take effect there.

## Free-first multi-provider LLM chain + batched AI scoring + OpenAI consent — 9 Jun 2026 (tested iter97 + pytest)
- **Why**: "AI Assess All" showed "0 cells • N failed" because the only LLM providers were
  Gemini (rate-limited/timeout in some envs) and the Emergent universal key (budget exhausted). Root
  cause confirmed in logs: `Budget has been exceeded`.
- **Provider chain (`core/ai_metering.py`)**: `metered_chat` now runs a FREE-FIRST fallback chain —
  **Gemini → Groq → OpenAI(consent) → Emergent** — with per-provider retry+back-off on 429 and a 30s
  timeout so a hung provider fails over fast. Only the first provider that returns text is charged.
  Keys: `GROQ_API_KEY`, `OPENAI_API_KEY` added to backend/.env. Models: Groq `llama-3.3-70b-versatile`,
  OpenAI `gpt-4o-mini`. Verified in dev: Gemini times out/503 → "advancing chain" → **Groq scores 200**.
- **Batched scoring (`core/ai_assess.batch_score_cells` + `POST /decisions/{id}/ai-assess-all-batched`)**:
  scores ~40 cells per LLM call instead of 1-2 calls/cell — a 192-cell decision goes from ~384 calls to
  ~5, keeping usage inside free quotas. Frontend `Step7.runBulkAssess` AND
  `DecisionContext.bulkAssessAllRemaining` (post-URL-import auto-score) both migrated to this endpoint.
  Old per-cell `/ai-assess-batch` retained but no longer the primary path.
- **OpenAI data-sharing consent (3c)**: `GET/PUT /api/ai-wallet/provider-consent` stores
  `users.ai_provider_consent {allow_openai, mode}`. AI Wallet screen has a Settings toggle + mode chips
  (Ask each time / Always). When free quotas exhaust mid-run, Step 7 shows an in-the-moment prompt:
  [Top up] / [Use OpenAI once] / [Always use OpenAI] (saves consent). OpenAI only enters the chain when
  the user consents (privacy: it shares decision data with OpenAI for the free tier).
- **Tests**: `tests/test_provider_chain_batched.py` 2/2 pass (consent round-trip + batched-via-Groq).
  iter97 frontend: consent toggle/chips persist (200 PUT/GET), Step-2 banner confirmed removed.
- ⚠️ Redeploy jelcos.ai + set `GROQ_API_KEY`/`OPENAI_API_KEY` in prod .env for this to take effect there.

## "AI Assess All — 0 cells • N failed" diagnosis + clearer message — 9 Jun 2026 (verified)
- **Root cause (confirmed via backend logs, funded wallet)**: the AI assessment LLM call fails with
  `litellm.BadRequestError: Budget has been exceeded! ... Max budget: 0.4` (Emergent Universal LLM key
  budget/balance exhausted). `ai_assess_factor` then raises 502 → the batch route marked each cell
  `status:error` → the UI showed the confusing "N failed". This is NOT the app's in-app AI-wallet (that
  path returns 402 → "Out of AI credits"); it's the underlying Universal LLM key balance.
  → User fix: **Profile → Universal Key → Add Balance** (or enable auto-topup), then retry. In dev/preview
  the sandbox key has a fixed $0.40 cap, so live AI calls 502 here regardless of in-app credits.
- **UX fix**: `routes/decisions/assessment.py::md_ai_assess_batch` now returns `ai_unavailable: true` and
  STOPS at the first 502 (no more burning through 30+ chunks with the same failure). `Step7.tsx`
  `runBulkAssess` shows "AI temporarily unavailable — Universal LLM key balance may be exhausted; add
  balance and retry (already-scored cells are saved)" instead of "N failed". Verified in dev: batch now
  returns `ai_unavailable:true, results:0` and the UI message is actionable.
- ⚠️ Redeploy jelcos.ai for the clearer message; the underlying remedy is topping up the Universal Key.

## Step-2 URL import → hierarchical + removed redundant assess banner — 9 Jun 2026 (curl-verified)
- **FIX (Step 2 "Import from URL" now hierarchical)**: previously it used the FLAT parser
  (`merge_into_mydezider`, capped at 8 factors) so GSMArena gave ~8 flat factors ("Body · Weight").
  Now `routes/url_analyze.py::import_url_into_decision` first tries `crawl_hierarchy`; for a
  category-grouped matrix (≥2 groups & ≥2 items) it scores (`_score_hierarchy_numeric` +
  `_ai_score_text_rows`) and calls the NEW `core/decision_builder.merge_hierarchical_into_mydezider()`
  — merges 15 PARENT factors + sub-factors (weights split to exactly 100) + options w/ leaf
  assessments into the EXISTING decision (name-dedup). Flat derive remains the fallback.
  Verified via curl on the user's GSMArena compare URL: mode=hierarchical, category_count=15,
  55 sub-factors, 3 options, per-parent weights sum=100.0.
- **REMOVED the "AI Assess All remaining" banner from Step 2** (`Step2.tsx`) — assessment belongs on
  Step 7 where "AI Assess All" already exists; the Step-2 banner was redundant. Dropped its handler,
  the `aar` styles, and now-unused `useAiWalletStore`/context imports.
- ⚠️ User tests on PROD (jelcos.ai) — these changes are in dev/preview; **redeploy required** for them
  to appear on jelcos.ai. ⚠️ AI text-row scoring may no-op in dev if the LLM wallet is empty (structure
  + raw values still build; run "AI Assess All" on Step 7 after top-up).

## Multi-source imports (Step 2 + Step 7 URL actuals) — 8 Jun 2026 (tested iter96)
- **Step 2 multi-source import (3-icon layout)**: `Step2.tsx` imports a comparison matrix into a NEW
  decision via XLS/CSV (`step2-import-xls`), Google Sheet (`step2-import-sheet`), or URL
  (`step2-import-url`) → consent gate. Adds factors (+suggested Expected), options, partial
  assessments. Backend: `routes/matrix_import.py` (`import-matrix-file`, `import-matrix-sheet`,
  `factor-matrix-template.xlsx`) + `core/matrix_import.py`.
- **Step 7 "Import from URL" (actuals mapper) — COMPLETED THIS SESSION**: added the missing UI in
  `Step7.tsx` — `md-import-actuals-url` button → URL input dialog (`md-actuals-url-input` /
  `md-actuals-url-continue`) → `UrlAccessConsentModal` (purple) → `POST /api/decisions/{id}/import-actuals-from-url`
  extracts ACTUAL values against the decision's EXISTING templatized factors, then AUTO-triggers
  `bulkAssessAllRemaining()` AI scoring. Graceful out-of-credits handling.
- Verified iter96: backend 7/7 pytest (`test_iter96_matrix_import.py`) — template/csv-import/sheet/
  actuals-from-url all 200 on happy path, 400/422 on bad input/consent gate. Frontend: all Step 2 icons
  render + URL→consent chain; Step 7 new button→dialog→consent→import API call all work.
- ⚠️ Recurring: `sudo supervisorctl restart expo` needed after FE source edits (Metro cache).
- ⚠️ AI scoring may report out-of-credits in dev (expected). ⚠️ Redeploy jelcos.ai + re-enter ScraperAPI key.

## Skip-WhatsApp-Gate flag + one-tap AI Assess + ScraperAPI — 8 Jun 2026 (tested iter95)
- **Skip WhatsApp Gate (testing)**: new global flag in `core/security_config.py`
  (`skip_whatsapp_gate`, default False). `effective_whatsapp_verified()` returns True for ALL users
  when ON, so the post-login `/whatsapp-verify` gate is bypassed (login/auth-me already return the
  effective value → no frontend gate change). Super-Admin toggle in Admin → Settings
  (testID `toggle-skip-whatsapp-gate`, red track). PUT `/admin/security-config` is super-admin-only.
  ⚠️ Currently ON in dev/preview for QA — turn OFF in production.
- **One-tap "AI Assess All remaining"**: `DecisionContext.bulkAssessAllRemaining()` + `countUnscoredCells()`
  score every un-scored LEAF cell via chunked `/ai-assess-batch` (force_fill), re-fetching per chunk so
  worth updates live; graceful 402/out-of-credits handling. Surfaced as a purple banner on Step 2
  (testID `ai-assess-all-remaining-btn`) shown when ≥2 options + un-scored cells exist — turns a raw
  import into a ranked recommendation in one tap.
- **ScraperAPI integration (optional)**: registered provider `scraperapi` in `/admin/integrations`
  (api_key + optional country_code). `core/integrations.resolve_scraperapi()` (Admin UI → env fallback).
  `core/url_crawl._fetch_html` routes JS-heavy domains (amazon/flipkart/google-shopping/myntra/ajio/…)
  through ScraperAPI render, and escalates to it when a direct fetch is bot-blocked; gracefully falls
  back to direct httpx when no key. NEEDS the user's ScraperAPI key to activate Amazon-class imports.
- Verified iter95 (7/7 pytest + frontend): gate bypass, admin toggle (super-admin-only), banner +
  graceful out-of-credits, scraperapi provider listed, no-key GSMArena fallback intact.
- ⚠️ Redeploy jelcos.ai for these to go live.

## ScraperAPI activated + Amazon product-grid import — 8 Jun 2026 (tested)
- User provided a ScraperAPI key; configured via `PUT /api/admin/integrations/scraperapi` (stored in
  db.integrations, masked). Verified: key valid (5,000 credits), ScraperAPI **renders Amazon** (1.67MB,
  product grid + prices) — bypasses the 503 that direct httpx hit.
- Added `core/url_crawl._product_grid_candidates()` — deterministic extractor for e-commerce SEARCH
  grids (Amazon `[data-asin]` cards / schema.org Product) → name + Price + Rating. Wired into
  `crawl_candidates` BEFORE the LLM fallback, so Amazon/Flipkart imports need **no AI**.
- Fixed `_MEASURE_RE` to accept a leading currency symbol (₹ $ € £ ¥) so "₹2,498" parses as numeric →
  Price becomes a numeric lower-better factor, Rating numeric higher-better.
- Verified e2e: `POST /api/url-analyze {amazon search url, target:mydezider}` → decision with 24 options,
  factors Price(<=)+Rating(>=), options ranked by worth (top ~97.5% = cheap + high-rated). New tests in
  test_url_matrix_parse.py (currency + product grid). GSMArena (no-key) unaffected.
- ⚠️ ScraperAPI key is in the PREVIEW db only — on PROD (jelcos.ai) after redeploy, re-enter the key in
  Admin → Integrations → ScraperAPI (the provider only appears post-redeploy).
- Note: 3 Screener-converter tests fail in dev solely due to a drained AI wallet (insufficient_credits),
  not code — they pass once the Emergent LLM wallet is topped up.

## Remaining backlog (post-fork)
- P1: CLD Engine Phase B & C (Rules Engine + AI Suggestions)
- P1: PRR Enhancement #4 & #5 (configurable timing fields + decision-linking bypass)
- P1: DigiLocker eKYC Integration (needs sandbox credentials or mock-first)
- P2: Webhook API Integration; Org-Type Master Migration

## Fork session — 8 Jun 2026 (verification + 2 fixes)
- ✅ Regression verified on fork: URL-crawl→MyDezider/ProsCons (iter91 11/11, with a recreated
  local fixture `tests/fixtures/funds.html` served on :9777), AI-assess-batch (iter92), URL-import
  direction, force-fill — all green. "Instant Dezider" rename + profile admin cleanup confirmed shipped.
- ✅ UI FIX (Step2.tsx): moved the **Type (Quantitative/Qualitative)** selector ABOVE the
  Operator/Expected/Unit criteria (was below). Data Source toggle split into its own row to stay
  adjacent to its collapsible config panel. Pure layout reorder, lint clean.
- ✅ BUG FIX (`core/url_crawl.py`): "Import from URL" failed with HTTP 503 on Amazon. Root cause: the
  crawler sent a **bot User-Agent** (`ViewDeziderBot`) → retail/CDN sites reject with 403/503. Fix:
  realistic desktop-Chrome headers (UA + Accept/Accept-Language), 3 attempts with backoff on
  403/429/503, and specific error copy distinguishing bot-block vs JS-rendered vs not-found. Verified:
  Amazon no longer 503s (now 200; still JS-rendered so needs AI extraction), fixture table → 4 candidates,
  13/13 tests pass. NOTE: removed `br` from Accept-Encoding (brotli not installed → would garble HTML).
  ⚠️ Known limit: JS-heavy retail giants (Amazon/Flipkart/Google) load lists via JS we can't render —
  feature works best on comparison/aggregator pages with real HTML tables or JSON, or Screener CSV upload.
  A headless-browser/scraping-API integration would be required to reliably scrape those (not yet wired).
  ⚠️ Prod (jelcos.ai) must REDEPLOY for this fix to take effect.

## Fork session — 10 Jun 2026 (EG AI credit estimate badges + >15cr confirm gate)
- ✅ COMPLETED & TESTED (iter98 PASS): Finished wiring per-action AI credit estimate badges
  ("· ~N cr") on every Emotional Gatekeeper AI button and the >15-credit confirmation gate.
  Backend `GET /api/ai-wallet/estimates` (tokens_per_credit=100, confirm_threshold_credits=15)
  and `src/utils/aiEstimates.ts` (useAiEstimate + confirmAiSpend) were pre-built; this session
  completed the frontend rollout across all 5 screens:
    - eg-trap: Get AI Awareness ~9cr
    - eg-loop: Get AI Recommendation ~7cr · Generate Reframe ~10cr
    - eg-limitation: Classify ~7cr · Generate Breakthrough ~10cr
    - eg-aim: Analyze & Get Insights ~14cr
    - eg-session: Generate AI Breakthrough Report ~20cr → ONLY this pops Alert.alert confirm (>15)
  - Fixed a corrupted trailing line in eg-session.tsx (duplicate `ight: 18 },`) that broke parsing.
  - Note: on react-native-web preview, Alert.alert is polyfilled; native iOS/Android shows real modal.
- Backlog unchanged below.

## Remaining backlog (post-fork, as of 10 Jun 2026)
- P1: CLD Engine Phase B & C (Rules Engine + AI Suggestions)
- P1: PRR Enhancement #4 & #5 (configurable timing fields + decision-linking bypass)
- P1: DigiLocker eKYC Integration (needs sandbox credentials or mock-first)
- P2: Webhook API Integration; Org-Type Master Migration
- Refactor (P2): extract shared AI-execution/error hook from duplicated eg-*.tsx logic

## Fork session — 10 Jun 2026 (EG header AI-credits balance pill)
- ✅ COMPLETED & TESTED (iter99 PASS): Added an "AI Credits" balance pill to the header (top-right,
  next to back button) of all 5 EG tool screens (eg-trap, eg-loop, eg-limitation, eg-aim, eg-session).
  Reuses existing `src/components/AiCreditsBadge.tsx` (compact + autoRefresh) backed by
  `useAiWalletStore` → GET /api/ai-wallet. Tapping opens /ai-wallet. Verified pill renders on every
  screen with live balance, autoRefresh hits /api/ai-wallet per screen, and the "~N cr" estimate
  badges still render (no regression). New header style `headerTop` (row, space-between) added to each.

## Fork session — 10 Jun 2026 (low-balance "Top up" nudge on EG credits pill)
- ✅ COMPLETED & TESTED (self-test via Playwright screenshots): Enhanced `AiCreditsBadge.tsx` with an
  optional `lowThreshold` prop. When the wallet balance drops below the cost of the next AI action on
  the screen, the pill turns amber (or red when empty), gets a subtle tinted background, and appends a
  "· Top up" nudge. Each EG screen passes its most-expensive action estimate as the threshold:
  eg-trap=trapEst(9), eg-loop=loopRefEst(10), eg-limitation=limRefEst(10), eg-aim=aimEst(14),
  eg-session=reportEst(20). Default (no threshold) preserves prior <3cr behaviour for other screens.
  - Verified: balance 921 → plain purple pill; balance 5 (< trap cost 9) → amber "5.0 · Top up".
  - NOTE: Metro runs in CI mode (reloads disabled) — restart `expo` supervisor to serve latest bundle.

## Fork session — 10 Jun 2026 (EG session-detail empty content + result scroll-to-top)
- ✅ BUG 1 FIXED & VERIFIED: Opening a completed EG session from the listing (eg-session.tsx) showed
  only the Generate-Report button + empty Commitments/Journal — the captured AI analysis was never
  rendered though the backend already returns trap_reflection.ai_summary / loop_reflection.ai_reframe_full
  / limitation_reflection.ai_summary / aim_reflection.ai_analysis. Added analysis render cards
  (AI Trap Awareness, Loop Reframe, Limitation Breakthrough, AIM Analysis) mirroring the in-flow result
  screens. Verified on admin-owned session EG-4B460C2111 — full Trap Awareness now displays.
- ✅ BUG 2 FIXED: Result/step screens (eg-trap/loop/limitation/aim) didn't reset scroll position, so the
  AI result rendered mid-page. Added a ScrollView ref + `useEffect(()=>scrollTo({y:0}),[step])` so every
  step change snaps to top. Smoke-verified screens load without errors.
- NOTE: did NOT run full-flow testing agent to avoid spending the user's AI credits; bug 1 verified by
  direct render screenshot, bug 2 is a deterministic scroll reset.

## Fork session — 10 Jun 2026 (ROOT CAUSE: empty draft sessions + generic reports)
Investigation findings (user on PROD jelcos.ai → EC2 + separate prod Mongo; dev DB can't see prod data):
- `POST /sessions` creates a session as **"draft"** the instant a tool opens; the CAPTURE step is what
  creates the reflection doc + flips status to "in_progress". So a **"draft" session = opened but never
  captured = genuinely empty** → detail page was blank. The user was clicking these empty drafts.
- The "completed" session's report was full of generic "not yet recorded" text because the
  **Breakthrough Report was generated on an EMPTY session**. Confirmed the report generator works:
  on a session with real capture ("Missed a deadline / career") it returned a personalized report.
Fixes (all verified in dev):
- BACKEND: generate_report now returns **400 no_reflection_data** when the session has no
  trap/loop/limitation/aim/outlet content → no more generic placeholder reports.
- BACKEND: trap-analyze, loop-reframe, limitation-reframe now set session **status="completed"**
  (previously only report-gen did) → analyzed flows now show "Completed" instead of draft/in_progress.
- FRONTEND eg-session.tsx: renders **"What You Shared"** captured inputs (trap/loop/limitation) +
  existing AI analysis cards; shows an **"incomplete session → Resume"** state (routes back into the
  correct tool) for empty sessions; **hides** the Generate Report button when there's no content.
- ⚠️ REQUIRES REDEPLOY to prod (Cloudflare frontend + EC2 backend). Existing old empty/generic prod
  sessions stay as-is; new sessions behave correctly. Old generic reports can be regenerated on a
  session that has real data.
- FOLLOW-UP (not yet done): empty draft sessions still clutter the listing — consider lazy session
  creation (create on first capture) or hiding empty drafts from the list.

## Fork session — 11 Jun 2026 ("Classify My Limitation nothing happens" → 503 + silent web alerts)
TWO distinct issues found:
1. ROOT of "nothing happens" on web (jelcos.ai): React Native `Alert.alert` is a NO-OP on
   react-native-web, so the 503 error (and all validations + the >15cr confirm) were swallowed
   silently. FIX: added `src/utils/crossAlert.ts` (window.alert/confirm on web, native Alert on
   mobile) and repointed `Alert` imports in eg-trap/loop/limitation/aim/session + aiErrors.ts +
   aiEstimates.ts. VERIFIED on web: clicking an AI button now fires a real browser dialog.
2. The underlying 503 itself is a PROD CONFIG issue, NOT a code bug. classify works in dev (200):
   the metered fallback chain Gemini→Groq→OpenAI→Emergent catches Gemini's 429 and advances to Groq.
   The chain is built ONLY from keys present in the backend `.env`. On prod EC2 the `.env` is almost
   certainly missing GROQ_API_KEY / OPENAI_API_KEY / EMERGENT_LLM_KEY (added this session in dev; .env
   is not in git), so when Gemini rate-limits there's no fallback → 503 ai_unavailable.
   ACTION FOR USER: add GEMINI_API_KEY, GROQ_API_KEY, OPENAI_API_KEY, EMERGENT_LLM_KEY to the EC2
   backend `.env` and restart the backend. Optional model overrides: METERED_GEMINI_MODEL /
   METERED_GROQ_MODEL / METERED_OPENAI_MODEL (defaults gemini-2.5-flash / llama-3.3-70b-versatile /
   gpt-4o-mini).
- Needs REDEPLOY of frontend (Cloudflare) for the alert fix + the EC2 .env keys for the 503 fix.
- FOLLOW-UP: other EG screens (eg-outlet, eg-advisor, eg-emotional-reception) may still use RN Alert
  directly — sweep them to crossAlert too if they show AI errors.

## Fork session — 11 Jun 2026 (back arrow + resume in-progress session)
- BACK ARROW: `router.back()` is a no-op on react-native-web when there's no in-app history (direct
  URL / resume). Added a `goBack()` helper to all EG screens: `router.canGoBack?.() ? router.back() :
  router.replace('/tools/emotional-gatekeeper')`. Verified on web: back now navigates to the dashboard.
- RESUME: eg-limitation always started at step 0 with empty fields (no mount-load). Added a mount
  useEffect that GETs the session, prefills capture inputs + classification + flow answers, and jumps
  to step 1 (explore) if ai_classification exists or step 2 if ai_summary (reframe) exists. Verified:
  resumes to "Classify & Explore" with the 90% classification + the user's data prefilled.
- CONTINUE BUTTON: eg-session detail now shows a "Continue Session" button for non-completed sessions
  with content (routes back into the correct tool via resumeRoutes[session_type]).
- Backend fields used: limitation_reflection.{limitation_statement,why_limited,origin,belief_duration,
  cost_of_limitation,ai_classification,limitation_category,flow_answers,ai_summary}.
- ⚠️ Needs frontend REDEPLOY (Cloudflare) to reach jelcos.ai.
- FOLLOW-UP: resume-to-step + prefill is implemented for eg-limitation only. eg-trap / eg-loop / eg-aim
  still start at step 0 on re-open — replicate the same mount-load pattern there next.

## Fork session — 11 Jun 2026 (PROACTIVE SWEEP: back + web-alert + resume across ALL EG screens)
Completed the full sweep the user asked for (both items):
1. BACK BUTTON + WEB-SAFE ALERTS on the 3 remaining screens (eg-advisor, eg-outlet,
   eg-emotional-reception): added `goBack()` (canGoBack?back:replace dashboard) + swapped RN `Alert`
   for the web-safe `crossAlert` shim. Now ALL 8 EG screens have both fixes (verified: no screen uses
   raw `() => router.back()`; goBack present in all 8).
2. RESUME-TO-STEP + PREFILL on eg-trap, eg-loop, eg-aim, eg-outlet (limitation already done): mount
   useEffect GETs the session, prefills saved inputs, and jumps to the furthest completed step.
   - Backend field names verified per tool (trap stores landscaping_pattern/linking_meaning/
     looping_thought/ai_summary, not the granular scanning_* fields — fixed trap step-detection to use
     real fields). loop: ai_recommended_method/selected_method/method_answers/ai_reframe_full. aim:
     addictions/irritations/ai_analysis. outlet: ai_analysis.
   - VERIFIED on web: limitation→"Classify & Explore", trap→"Looping"(step3), loop→inputs prefilled.
   - KNOWN BACKEND GAP (pre-existing): trap landscaping endpoint stores `landscaping_pattern`=None and
     drops the granular scanning_* inputs, so landscaping sub-answers aren't restorable on resume; step
     detection still routes correctly via linking_meaning. Not fixed (out of scope).
- ⚠️ Needs frontend REDEPLOY (Cloudflare) for all of the above to reach jelcos.ai.

## Fork session — 11 Jun 2026 (trap resume field-name correction — NO backend gap)
- CORRECTION to the earlier "trap landscaping persistence gap" note: there is NO backend gap. The
  landscaping endpoint DOES persist scanning_for / scanning_patterns / scanning_without_urgency /
  repeated_concern; `landscaping_pattern` is just an unused legacy field. The earlier issue was my
  resume code reading the wrong fields. Fixed eg-trap resume to read the REAL fields:
  scanning_*, trigger_type, trigger_description, linking_meaning, looping_thought, getting_new_solution,
  emotion_increasing, intensity_after_loop, ai_summary — and prefill all corresponding inputs.
- VERIFIED on web: a capture→landscaping→linking→looping session resumes to step 3 "Looping" with the
  looping thought prefilled ("They will laugh at me"), "No, just replaying" selected, Intensity After 9/10.
- Trap resume now fully restores all prior answers + jumps to the furthest completed step. No backend
  changes were needed.

## Fork session — 10 Jun 2026 (Emotional Outlet Analyzer REVAMP — DONE & tested)
User-approved spec ("1.a 2.b 3.b + same Outlet Group", + breakdown weighted by frequency).
Backend (constants.py / ai_engine.py / outlet_aim_routes.py):
- COPING_STRATEGIES expanded to 40 statements = 10 per Outlet Group (Physical 🔴 / Mental 🔵 /
  Emotional 🟠 / Energy 🟣), each a MIX of healthy (default_constructive=True) & unhealthy (False).
- Route now computes a deterministic frequency-weighted % breakdown (Often=7/Sometimes=4/Rarely=1/
  Not-at-all=0) per group + Top-2 modes (primary/secondary), stored in ai_analysis so resume renders them.
- `analyze_outlets` AI prompt rewritten to: interpret Top-2 modes (mode_insight) + return EXACTLY 5
  constructive replacement_activities that stay in the SAME Outlet Group as the replaced behavior
  (fills extra slots with primary-mode elevating activities), + overall_pattern + encouragement.
Frontend (app/tools/eg-outlet.tsx — full rewrite):
- Step 0: 40 statements shown MIXED (seeded shuffle, no category headers), color-coded left-border by
  nature + a legend. Tap reveals frequency chips + "feels compulsive". testIDs on all interactive els.
- Step 1 (surprise reveal): Primary + Secondary Mode chips, "Where Your Energy Goes" % bars (color-
  coded), mode_insight, "5 Healthier Swaps" cards (group pill + Replaces + why), overall_pattern,
  encouragement. Resume of completed session renders saved analysis.
VERIFIED: curl e2e (37/37/21/5 breakdown, physical/mental modes, 5 same-group swaps) + web screenshots
of both steps. NOTE: Metro runs in CI mode (reloads disabled) — must restart `expo` to rebundle FE edits.

## Fork session — 10 Jun 2026 (Outlet Analyzer refinements + P0 session regression fix)
P0 REGRESSION FIX: eg-session.tsx never rendered the OUTLET reflection (user saw an empty
completed Outlet session). Added a "What You Shared (Outlets)" input card + "Your Outlet Profile"
analysis card (modes, % breakdown, mode_insight, primary/secondary swaps, overall_pattern,
encouragement) + an "Open Full Report (PDF & Share)" button. Trap/loop/limitation/aim sections
untouched.
Refinements (all tested):
1. Color legend moved from the TOP of step 0 to just ABOVE the Reveal button (smaller font) so it
   no longer spoils the surprise.
2. "Feels Compulsive" is now the FIRST chip in each outlet's options row (before Often), not a
   separate checkbox.
3. AI suggestions split into 5 PRIMARY-group + 3 SECONDARY-group activities (no longer 5 mixed).
   ai_engine.analyze_outlets returns primary_activities[5] + secondary_activities[3], each strictly
   within that mode's Outlet Group. Frontend renders two grouped sections.
4. Branded PDF + Share: new backend module outlet_report_routes.py —
   GET /api/emotional-gatekeeper/outlet/{sid}/report.pdf (reuses decision_reports._build_pdf →
   same JELCOS header/footer as MyDezider) and POST .../outlet/{sid}/share {channel,email/phone}
   (email = branded HTML + PDF attachment via Resend; whatsapp = branded text via UltraMsg).
   No L1/L2 paywall (Outlet is AI-credit metered). eg-outlet results page now has Download PDF +
   Share buttons + a channel/recipient modal.
VERIFIED: curl (5 physical + 3 mental swaps; PDF 200/valid 5-page; email share sent:true) + web
screenshots (results grouped swaps, session-page inputs+analysis, compulsive-first chip).

## Fork session — 10 Jun 2026 (Outlet share: attach PDF on WhatsApp too)
WhatsApp share now ATTACHES the branded PDF (previously text-only). Added
_send_whatsapp_document() using UltraMsg POST /messages/document with the PDF as a base64
`document` + `filename` + `caption` (branded summary). Email already attached the PDF (Resend).
VERIFIED: curl email share sent:true (PDF attached) + WhatsApp share to owner's verified number
sent:true (PDF document delivered).

## Fork session — 11 Jun 2026 (P0: "AI Assess All" escalation — empty cells + step jump)
User escalation: after AI-Wallet top-up, "AI Assess All" consumed credits but left cells empty AND
auto-navigated back to Step 6 (Define Options). THREE root causes found & fixed:
1. BACKEND (core/ai_assess.py batch_score_cells): prompt was hard-truncated at 11K chars → LLM
   silently skipped cells while the call was still charged. Replaced with size-aware chunking
   (_chunk_work: ≤40 cells AND ≤9K-char items-JSON per call, never truncated) + ONE automatic
   retry pass (chunks of 12) for dropped/malformed/parse-failed cells.
2. FRONTEND (DecisionContext.tsx): the smart step auto-jump in fetchDecision() ran on EVERY
   refetch — added autoJumpDoneRef so it runs ONLY on first load; refetches after Assess All /
   saves / imports never move the user's step anymore.
3. FRONTEND RACE (Step7.tsx applyCellResult) — found by testing agent: bulk path fired one PUT
   /decisions/{id} per cell from stale React snapshots (last-write-wins → only 1/8 cells survived
   in MongoDB). Bulk path no longer PUTs at all (backend already persisted); local echo only +
   fetchDecision() repaint. Manual per-cell saves still PUT (regression-verified).
Plus: completion alert now offers "Retry failed cells" when some cells errored.
TESTS: /app/backend/tests/test_batch_assess.py (4 unit) + tests/test_ai_assess_all_batched_e2e.py
(live e2e, by testing agent) = 6/6 pass. Frontend e2e iteration_101: 8/8 cells persisted, 0 racing
PUTs, stays on Step 7, alert OK, manual-edit regression pass.
PENDING (user-deferred until he verifies this fix): EG dashboard "empty Draft sessions" cleanup.

## Fork session — 11 Jun 2026 (PostHog Analytics integration, EU cloud)
User requested PostHog analytics across all app flows. Choices: frontend + backend events,
identify by user_id ONLY (no PII), named business events. Project: eu.posthog.com #199570.
IMPLEMENTED (no-op safe — activates when keys land in env):
- Frontend: src/utils/analytics.ts (posthog-react-native v4.46, EU host). _layout.tsx
  AnalyticsListener → screen event on EVERY expo-router route change + auto tool_opened for
  /tools/*. identify(user_id) on auth (authStore success paths + _layout effect), reset() on
  logout. Named events: login{method}, signup, decision_created (prr/new), ai_assess_all_run
  (Step7 w/ cell count).
- Backend: core/posthog_client.py (lazy-init, no-op w/o POSTHOG_API_KEY, never raises).
  Server-truth events: signup (auth register), payment_success (payments verify + webhook),
  ai_credits_consumed (ai_wallet._ledger debits w/ feature+provider+balance_after),
  otp_sent (whatsapp_otp), eg_session_completed (outlet+aim completion).
- Env: POSTHOG_HOST / EXPO_PUBLIC_POSTHOG_HOST set to https://eu.i.posthog.com in dev .envs.
PENDING: user must supply Project API Key (phc_..., from eu.posthog.com/project/199570/settings/project
— they pasted a phx_ personal key by mistake, advised to revoke). PRODUCTION rollout:
Cloudflare Pages env (EXPO_PUBLIC_POSTHOG_KEY/HOST) + redeploy; EC2 /opt/dezider/backend/.env
(POSTHOG_API_KEY/POSTHOG_HOST) + docker compose up -d --build. Google-auth signups currently
fire frontend login{method:google} only (no backend signup event) — minor gap, note if needed.
VERIFIED: pytest 4/4, tsc clean for changed files, signup curl OK w/ clean no-op log, app loads.
LIVE event verification possible only after the phc_ key arrives.

### PostHog activation (same session, 11 Jun 2026)
phc_ key received, added to dev .envs (frontend EXPO_PUBLIC_POSTHOG_KEY, backend POSTHOG_API_KEY).
LIVE VERIFIED: (1) direct capture curl → {"status":"Ok"}; (2) core.posthog_client flush OK;
(3) real signup via API fired with "PostHog server-side analytics enabled" log; (4) frontend SDK
initialized — config fetch from eu-assets.i.posthog.com HTTP 200. User instructed to do the
production rollout (Cloudflare Pages env + redeploy; EC2 backend .env + compose rebuild).

### PostHog Session Replay — Web (fork session, 11 Jun 2026)
Problem: events worked but PostHog showed "no recording available" — posthog-react-native
CANNOT record sessions on web. Fix (user-approved "Option A"): installed posthog-js@1.386,
rewrote src/utils/analytics.ts with a platform split — web uses posthog-js (replay-capable),
native keeps posthog-react-native. Privacy-hardened replay config: maskAllInputs:true,
capture_performance:false (no network bodies → no JWT/PII leakage), person_profiles:
'identified_only', capture_pageview:false (manual $pageview per expo-router change keeps
parity with old trackScreen). posthog client exposed on window.posthog for verification.
LIVE VERIFIED in preview browser: posthog-recorder.js loaded, sessionRecordingStarted:true,
7x POST /s/ replay snapshots + 8x event captures to eu.i.posthog.com. tsc clean.
GOTCHAS learned: (1) posthog-js bot detection (UA + userAgentData.brands + webdriver)
silently blocks ALL captures incl. replay in headless browsers — spoof all three when
testing via Playwright; real users unaffected. (2) Metro runs in CI mode (no file watch)
in this env — `sudo supervisorctl restart expo` REQUIRED after editing frontend files
before browser-verifying changes. (3) Replay snapshots go to /s/, events to /e/ or
/i/v0/e/, RN SDK uses /batch/ + /array/<key>/config — distinguish SDKs by endpoint.
PROD ROLLOUT (user must do): redeploy Cloudflare Pages (posthog-js is bundled at build
time; env vars already set). Backend unchanged.

### Revenue Reconciliation — Razorpay ⟷ Ledger ⟷ Google Cloud (fork session, 11 Jun 2026)
User goal: primary account must NEVER lose money vs Gemini postpaid invoices — granular
per-transaction. Approved choices: BigQuery Billing Export (1a), daily auto-sync + on-demand
(2b), all fields for zero-loss tally (3), Super-Admin report (4).
BUILT:
- backend/core/recon.py — engine: sync_razorpay() (payments/transfers/settlements, paginated,
  incremental w/ 5d overlap, into recon_rzp_* collections), sync_gcp() (BigQuery billing-export
  daily Gemini costs via service-account JSON stored b64 in recon_config, 2GB maximum_bytes_billed
  guard), transactions_tally() (per-txn: collected − rzp fee − routed markup − earmarked cost_inr
  = buffer; at_loss flag), daily_tally() (tokens→est ₹ vs GCP actual, variance), summary()
  (verdict at_risk), start_daily_sync_task() (24h loop, starts in server startup).
- backend/routes/admin_recon.py — /api/admin/recon/{summary,transactions,daily,sync,gcp-config,
  transactions.csv} — ALL require_super_admin.
- frontend/app/admin/recon.tsx — "Revenue Recon" in admin nav (Subscriptions & GTM): verdict
  banner, 8 summary cards, per-txn tally table, daily tally, GCP setup form (paste SA JSON,
  never returned to browser), Sync-now, CSV export. Full testIDs.
- deps: google-cloud-bigquery==3.41.0 (pip freeze'd).
TESTED: pytest tests/test_admin_recon.py 6/6 PASS; curl-verified all endpoints incl. live
Razorpay sync (57 payments, 5 transfers, 26 settlements pulled), 403 regular user, 401 unauth,
400 invalid SA JSON; UI screenshot-verified (all sections render, admin login works).
PENDING (user side): on PRODUCTION — enable GCP Billing export to BigQuery, create
service-account (BigQuery Data Viewer + Job User), paste JSON in Admin → Revenue Recon.
Push to GitHub + redeploy backend (EC2 needs `pip install google-cloud-bigquery`).
KEY INSIGHT surfaced: markup is routed AWAY to the linked account, so primary account nets
collected − fee − markup ≈ cost − fee → structurally slightly BELOW the earmarked Gemini cost
(e.g. ₹92.71 net vs ₹95.37 cost on the ₹104.91 txn). Suggest raising markup_user_pct or keeping
part of markup in primary account if buffer must be ≥ 0 per txn.

### World-class "Import from URL" — single-listing DETAIL pages (fork session, 12 Jun 2026)
User goal: NoBroker property-detail URL (not a comparison page) must intelligently import ALL
factors with expected values + smart operators (Rent ≤ 18000+600, Area ≥ 650 sqft, Furnishing =
Semi, Livability ≥ 6.2 …), main listing as Option 1, 'Similar Properties' as extra options.
Approved choices: ScraperAPI + LLM extraction; default 'Cheap & Fast AI' (Gemini wallet-billed)
with optional 'Costly & Precise AI' (Claude via Emergent universal key, wallet-billed at an
admin-configurable multiplier); auto-assigned smart operators; generic for ANY site.
BUILT:
- backend/core/url_detail.py (NEW) — DETAIL_SYSTEM prompt + ai_extract_detail() (one metered
  LLM call → factors w/ operators/expected/units + items w/ per-factor values+scores),
  normalize_detail() (op coercion, whitespace dedupe, main-item synthesis, 24-factor cap),
  _embedded_related_snippets() (mines inline SPA-state JSON for similar/related-items blocks —
  strips photos/urls/empty fields; NoBroker's rail is JS-rendered but server-embedded).
- backend/core/url_crawl.py — refactor: fetch_page(), fetch_rendered() (ScraperAPI render=true),
  page_text() (visible text + JSON-LD), deterministic_candidates(), candidates_from_response()
  (non-raising); crawl_candidates kept as raising wrapper (matrix_import still uses it).
- backend/routes/url_analyze.py — both endpoints fetch ONCE; flow: hierarchy → deterministic
  flat (≥2) → DETAIL extraction (rendered HTML when ScraperAPI configured, DETAIL_MAX_FACTORS=24)
  → AI flat fallback. ai_tier param ('fast'|'precise'); 402 on InsufficientCredits; responses
  include mode='detail', main_item, ai_provider (surfaces precise→fast fallback).
- backend/core/ai_metering.py — metered_chat(tier=, meta=): precise ⇒ Claude (cfg precise_model,
  default claude-sonnet-4-6) via Emergent key FIRST, charged at multiplier
  precise_usd_per_mtok/blended_usd_per_mtok (zero-loss invariant preserved); graceful fallback.
- backend/core/ai_wallet.py — config: precise_model, precise_usd_per_mtok (validated >0);
  charge(credit_multiplier=); precise_multiplier() helper.
- backend/core/decision_builder.py — merge_into_mydezider now stores unit_value (raw values) per
  assessment for flat/detail candidates.
- frontend Step2.tsx — Import URL dialog: 'AI engine' selector (step2-ai-tier-fast default /
  step2-ai-tier-precise), 180s timeout, detail-mode success message + precise-fallback notice.
- frontend admin/ai-wallet-config.tsx — 2 new fields + live 'Precise tier credit multiplier ×N'
  row in worked example.
TESTED: pytest 16/16 (tests/test_url_detail_import.py NEW, tests/test_iter_url_world_class_import.py
NEW by testing agent); live curl: NoBroker import → mode=detail, 20 factors (all user-listed values
matched), 3 options (main 100% + Dhamu/Golden Jublee w/ partial values); testing agent iteration_102
5/5 PASS (backend + frontend dialog + admin config UI).
KNOWN: EMERGENT_LLM_KEY budget EXHAUSTED in this workspace → precise tier currently falls back to
fast chain (graceful, surfaced in UI note). User must top up Universal Key balance
(Profile → Universal Key → Add Balance) to activate Claude precise tier.
NOTE: factor count varies by provider in fast chain (Gemini ~20, Groq fallback ~10-16) — prompt
hardened with exhaustiveness floor.

### Import-from-URL v3 — nature doctrine, hierarchy, hints, Set Expectations (12 Jun 2026, same fork)
User approved full scope (~35-45 cr). Clarifications honored: page-defined groups SACRED (GSMArena
BODY example); AI-grouping only when no page groups AND factors > admin-configurable threshold
(`import_group_threshold`, default 15, editable in Admin → AI Wallet Config); ZERO TOLERANCE on
option↔factor-value mapping; Steps 3/4/5 remain user-owned; button named "Set Expectations - By AI";
Claude-first (Universal Key topped up — VERIFIED WORKING, ai_provider=emergent_precise), fallback
Claude→Gemini→OpenAI→Groq (_build_chain openai_before_groq for precise tier).
BUILT:
- models/decisions_models.py: Factor.factor_type persisted ('quantitative' = undisputed fact/spec
  even when text e.g. Color=Blue, Furnishing=Semi; 'qualitative' = person-dependent judgment e.g.
  Comfort, Luxury Feel — needs AI-assisted assessment). Root cause fixed: field previously dropped
  by backend, frontend fell back to text⇒qualitative.
- core/url_detail.py v2: groups-based schema {groups:[{name,source:page|ai|none,factors[]}],
  items:[{values/scores keyed "Group::Factor"}]}; normalize emits kind=flat|hier (hier feeds
  merge_hierarchical_into_mydezider with equal weight split); server-side guard flattens AI-grouping
  under threshold; unknown value keys DROPPED (zero tolerance); validate_against_hints() + ONE
  corrective self-heal retry (hints: expected_factor_count ±max(2,20%), expected_option_count ±1,
  first_factor_name / first_option_name fuzzy).
- routes/url_analyze.py: hints fields on Import/Analyze requests; kind-aware merging (hier→
  hierarchical merge/create); _factor_nature keyword heuristic for deterministic comparison-page
  rows; NEW POST /url-analyze/decision/{id}/set-expectations (gated 422: needs factors+options+
  ≥1 unit_value; Claude-first; updates expected_value+operator on the 21 leaf factors only,
  parents untouched; anchored to option actuals).
- decision_builder.py: factor_type wired through all 4 create/merge paths.
- frontend Step2.tsx: collapsible "Boost accuracy (recommended, optional)" hints UI (4 inputs,
  testIDs step2-hint-*), 300s import timeout, hierarchical+hint-warning success messages,
  "Set Expectations - By AI" button (step2-set-expectations-ai) gated + hint text.
- admin/ai-wallet-config.tsx: import_group_threshold field (NOTE: parallel search_replace writes
  silently dropped this FIELDS entry once — re-applied + verified; also required expo restart due
  to corrupted Metro cache serving a stale bundle).
TESTED: 47/47 pytest (17 in test_url_detail_import incl. hier preservation, zero-tolerance, hints
tolerance); live precise import WITH 4 hints → emergent_precise, structure=hierarchical, 4 AI groups,
21 sub-factors equal-split (33.33/33.33/33.34), ALL text-facts quantitative, 4 options (main 100% +
Dhamu/Golden Jublee/Standalone partial), hint_warnings=[]; set-expectations 21/21 via Claude;
422 gating; testing agent iteration_103 4/5 (5th = the FIELDS gap, fixed + screenshot-verified).
DEV NOTE: admin@test.com dev AI wallet manually topped to 5000 credits (was -75.98).

## Session 2026-06-12B — Import-URL "Hints are Law" hotfix (v3.16.1) — USER-REPORTED CRITICAL
PROBLEM: carwale.com/new/best-electric-cars-under-10-lakh/ + 4 hints (6 factors, first "All Brands",
3+1 options, first "Tata Tiago EV") + Costly & Precise AI returned 2 irrelevant factors (PRICE, MODEL).
ROOT CAUSE (reproduced 100%): page embeds a tiny "Top 3" HTML table → FREE deterministic table parser
matched it and returned EARLY — Claude never invoked, hints never validated (hints only wired into the
detail-page path). Bonus: deterministic factors had no factor_type → PRICE showed "Qualitative".
FIX:
- routes/url_analyze.py: BOTH endpoints now gate deterministic parses (hierarchy + flat) through
  deterministic_hint_issues(); mismatch → escalate to AI extraction; precise tier escalates thin
  (<3 factor) parses even hint-less; AI-vs-deterministic arbitration (fewer hint issues wins);
  deterministic fallback merged WITH hint_warnings if AI fails; _derive_factors_and_scores sets
  factor_type=_factor_nature(k).
- core/url_detail.py: DETAIL_SYSTEM now extracts comparison/listing/filter pages too
  (page_type="comparison": facets→factors, listed items→options, peers NOT force-scored 100;
  knowledge-fill allowed for objective specs of well-known products); old comparison bail-out
  REMOVED; _user_facts_block() injects hints as ground truth into the FIRST prompt; page_text
  limits 30000 (precise) / 12000 (fast); normalize_detail accepts detail|comparison; NEW export
  deterministic_hint_issues().
VERIFIED: live e2e same URL/hints/precise → 6 facet factors (All Brands, Budget, Body Type, Fuel
Type, Transmission, Seating Capacity), 4 options Tiago-EV-first, emergent_precise, hint_warnings=[],
57s, all values+scores filled. NEW backend/tests/test_url_import_hints.py (11 tests). Full URL-import
suite 41 passed (GSMArena hierarchical regression intact). Stale iter94 prebuilt-decision test now
skips on 404 (data dependency). Docs bumped v3.16.1: PRD/SRS/API_REFERENCE/UAT/REGRESSION.
NO frontend changes needed (UI already sends hints + tier + shows hint_warnings).

## Session 2026-06-12C — Import-URL Intelligence (v3.17.0) — NEW FEATURE, TESTED
USER REQUEST: per-page-type prompt engineering + granular Import-URL accuracy tracking in Admin UI
(PostHog-style) — URL, 4 hints, AI engine, page type, prompts. Choices: 5 page types, ALWAYS-LLM
classification, store exact prompt+raw response (15KB/90-day purge), 👍/👎 feedback chip, MongoDB-first
+ lightweight PostHog events (default).
BUILT:
- core/url_pagetype.py: classify_page_type() — fast-tier LLM (gemini) → {page_type, confidence,
  provider}; heuristic fallback (never blocks). 5 types: comparison_matrix, listing_filter, detail,
  search_grid, article_roundup.
- core/url_detail.py: PAGE_TYPE_GUIDANCE blocks injected via {page_guidance} into DETAIL_SYSTEM;
  ai_extract_detail(page_type=, capture=) captures exact prompt/raw/attempts/tokens even on failure.
- core/ai_metering.py: metered_chat now sets meta["tokens"].
- core/url_telemetry.py: url_import_runs collection — new_tel/record_run/set_feedback/_lazy_purge
  (90d bodies, metadata forever)/summary/list_runs/get_run; PostHog events url_import_completed +
  url_import_feedback; telemetry NEVER raises.
- routes/url_analyze.py: both endpoints wrapped (analyze_url→_analyze_url_inner,
  import_url_into_decision→_import_inner); tel threaded; route labels at every exit incl. errors;
  responses now carry run_id; POST /url-analyze/runs/{run_id}/feedback (owner, up|down).
- routes/admin_import_analytics.py (super-admin): GET summary?days=, GET runs?days&page_type&route&
  status&feedback&limit&skip (400 on bad enums), GET runs/{id} (full prompt bodies). Registered in
  server.py.
- Frontend: app/admin/import-analytics.tsx (KPIs, 3 breakdowns, filterable runs, drill-down modal w/
  prompt+raw); admin/index.tsx tile + adminTheme.ts sidebar "Import-URL Intel" (Overview); Step2.tsx
  feedback chip (import-feedback-row/up/down) after URL import.
GOTCHAS FIXED: parallel search_replace on Step2.tsx raced → trailing junk + missing state (repaired,
trimmed to first `});` of stylesheet); expo CI mode needs `sudo supervisorctl restart expo` for NEW
route files; veales login response key is `session_token` (not access_token); admin@test.com is
role=admin (403 on super-admin routes) — super admin is veales.vedic.decisions@gmail.com.
TESTED: pytest 47/47 (new tests/test_import_telemetry.py 7 tests); live e2e carwale → listing_filter
conf 1.0, ai_extraction, 6F/4O, prompt(6583c)+raw(2480c) stored, tokens 10402, 👍 recorded; admin
endpoints+RBAC verified; testing agent FRONTEND 7/7 PASS (/app/test_reports/iteration_104.json).
DOCS: all bumped v3.17.0 (PRD/SRS/API_REFERENCE/UAT/REGRESSION/ADMIN_USER_GUIDE section).

## Session 2026-06-12D — AI Auto-Tune for extraction prompts (v3.17.1) — TESTED
USER REQUEST: enable the proposed "auto-tune suggestions" panel (AI reads failed runs per page type →
proposes prompt edits → admin approval).
BUILT:
- core/url_prompt_tuning.py: generate_suggestions (failing runs = status error|hint_pass false|
  feedback down, max 6 evidence runs, precise-tier Claude, one pending per page type),
  decide(approve→upsert db.url_prompt_overrides / reject), revert_override, _normalize_guidance
  (exactly one "PAGE-TYPE GUIDANCE —" header). Collections: prompt_tuning_suggestions,
  url_prompt_overrides{key=page_type,guidance}.
- core/url_detail.py: get_active_guidance(page_type) — DB override wins over built-in
  PAGE_TYPE_GUIDANCE, fails open; ai_extract_detail now awaits it.
- routes/admin_import_analytics.py: POST tuning/generate?days&page_type, GET tuning,
  POST tuning/{id}/approve|reject (404/409 guards), DELETE tuning/override/{page_type}. Super-admin.
- frontend admin/import-analytics.tsx: "AI Auto-Tune (prompt suggestions)" card — Generate (AI) btn,
  active-override chips with revert, suggestion list (status badge, rationale, expected impact,
  expandable current vs proposed blocks, Approve & go live / Reject). testIDs import-tuning-*.
TESTED: pytest 24/24 (new tests/test_prompt_tuning.py 6 tests — lifecycle/reject/guards/evidence/
normalizer); LIVE e2e: seeded failing carwale-pattern run → REAL Claude suggestion (diagnosed the
exact original bug: "misclassified as detail, extracted PRICE/MODEL instead of facets") → approve →
get_active_guidance returns override → 409 double-approve → 403 regular admin → revert → default.
UI smoke screenshot green (panel + Generate button rendered). DB artifacts cleaned.
DOCS: v3.17.1 (PRD/SRS FR-IU-18/19/API_REFERENCE/UAT AT-1..6/REGRESSION).
NOTE: expo tunnel returns transient 502 ~60s after `supervisorctl restart expo` — wait & retry.

## Session 2026-06-12E — Generic Notification Engine (v3.18.0) — TESTED iter105
USER ASK: instead of a single weekly digest email, build a GENERIC notification engine with
CRUD-able trigger events (start with 'import-analytics'), reusable for future triggers, with
WhatsApp channel + on/off toggles. Choices: weekly Mon 9AM IST default; WA = short text + link;
dedicated admin screen; digest = summary + page-type breakdowns + top failures + 👍/👎; include
event-based triggers in V1.
BUILT:
- core/notification_engine.py (473L): EVENT_REGISTRY {'import-analytics' scheduled digest,
  'import-run-failed' event alert}; compute_next_run (daily/weekly/monthly, IANA tz);
  run_trigger (Resend email HTML + UltraMsg WA text per-recipient, statuses sent/failed/
  skipped_no_recipients/error, run log w/ lazy prune 500); emit_event + emit_event_bg
  (per-trigger throttle_minutes); 60s APScheduler tick (fcntl singleton lock,
  NOTIFICATION_SCHEDULER_DISABLED opt-out); seed_default_triggers (idempotent, Mon 09:00 IST,
  email ON/empty, WA OFF). Collections: notification_triggers, notification_runs (+indexes).
- routes/admin_notifications.py (209L): /api/admin/notification-engine/{registry, triggers CRUD,
  triggers/{id}/test, runs}. Super-admin. Validation: email regex, phone 10-15 digits normalised,
  tz via ZoneInfo, 400 schedule-on-event-kind.
- core/url_telemetry.record_run now fires emit_event_bg('import-run-failed') on non-success runs.
- frontend app/admin/notification-engine.tsx (629L): trigger cards (kind badge, schedule label,
  next/last run, master switch, email/WA channel pills, recipient chips), Test-now w/ per-channel
  report, Edit/Create modal (event picker, freq/day/time/tz, throttle, ChipInput), dispatch log.
  testIDs notification-*. Admin home tile + sidebar nav (adminTheme.ts).
TESTED: pytest 17/17 (tests/test_notification_engine.py — schedule math IST→UTC, seed idempotency,
throttle, builders) + testing agent 28/28 API (tests/test_notification_engine_api.py) + 8/8
frontend flows (iteration_105.json). LIVE: test-send delivered BOTH channels (Resend 200,
UltraMsg 200). DB left clean (only seeded digest trigger, empty recipients).
DOCS: all bumped v3.18.0 — PRD/SRS (FR-NE-1..6)/API_REFERENCE/UAT (NE-1..12)/REGRESSION/POSTMAN +
Postman_Collection.json folder "Notification Engine (Admin)" (53 folders, 979 endpoints) +
ADMIN_USER_GUIDE + INDEX.
NOTE: new expo-router route files need `sudo supervisorctl restart expo` (Metro CI mode, no watch);
tunnel 502s ~60s after restart — wait & retry.

## v3.19.0 — 12 Jun 2026 (Iteration 106): Org-Type Master + URL-Import live progress
USER CHOICES: 1a separate "Family" card · 2b searchable icon picker · 3 login org types untouched.
- ORG-TYPE MASTER: discovered an EXISTING master (db.org_types_master, payment_admin.py — public
  GET /api/org-types + admin CRUD /api/admin/org-types) built earlier for coupon filters; EXTENDED
  it instead of duplicating: + FAMILY seed row (people / #EC4899 / "Family / household", sort 2),
  + `description` field (seeder backfills legacy rows, allowed in POST/PUT), INDIVIDUAL desc now
  "Self / personal". decision_intake.py validates acting_as_context against ACTIVE master keys
  (dynamic) ∪ legacy constant.
- ADMIN UI: new "Org Types" tab (default tab) under /admin/masters →
  src/components/admin/OrgTypesManager.tsx (320L): CRUD modal w/ label, auto-key, description,
  SEARCHABLE Ionicons picker (~900 icons, glyphMap), 12 color presets + hex, is_org/active
  switches, sort order; system rows soft-disable on delete; custom rows hard-delete (409 if used
  by decisions). payments.tsx org-type modal gained Description field (same API).
- DYNAMIC INTAKE: new src/hooks/useOrgTypes.ts (fetch /org-types, bundled-defaults fallback);
  new-decision.tsx (My Dezider/SWOT/Pros-Cons shared intake — hardcoded ACTING_AS removed) and
  add-solution.tsx (ORG_TYPES_LIST removed) now render the 7 dynamic cards/chips incl. Family.
- IMPORT PROGRESS UX: url_analyze.py writes REAL stages (5 consent → 12 fetch → 22 structure →
  45/50 scoring/rendered → 62 AI extract → 85-88 merge → 100 done/error) to db.url_import_progress
  (TTL 1h); new GET /api/url-analyze/progress/{id}; Step2.tsx generates progress_id, polls 1.2s,
  shows modal (import-progress-modal) w/ stage label, % bar, elapsed seconds. Consent modal now
  closes when import starts.
- IMPORT SPEED: classify_page_type now an asyncio task running CONCURRENTLY with deterministic
  parsing/scoring and with fetch_rendered on the AI path (~5-15s saved); telemetry page_type still
  recorded on every route via await-before-return.
- SET-EXPECTATIONS CLARITY (answered user Q "is it auto-called?" — NO): import pre-fills Expected
  values deterministically (best-of-set heuristic); the button is a separate AI pass. Endpoint now
  returns {changed, confirmed}; alerts say "CHANGED x / confirmed y"; import popup + button hint
  explain the pre-suggestion. ACTING_AS removed from new-decision.tsx.
TESTED: pytest 9/9 (tests/test_iter106_org_types_master.py) + testing agent full frontend pass
(iteration_106.json): Masters CRUD incl. icon search, 7/7 cards dezider+swot, 7/7 add-solution
chips, FAMILY decision creation, regression on other master tabs + payments screen.

## v3.20.0 — 12 Jun 2026 (Iteration 107): Import trust (P0) + Org-type templates (P1) + Deep Import (P2)
ROOT-CAUSE of user's "584000 wrong Budget" complaint (carwale import): NOT an AI hallucination —
the crawler fetched the page's DEFAULT geo variant ("Rs. 5.84 - 9.99 Lakh · Avg. Ex-Showroom")
while the user's browser showed Chennai on-road prices (7.58-10.69L). Value was page-faithful but
had zero provenance visibility. Diagnosed from stored ai_prompt_text/ai_raw_response telemetry.
- P0 PAGE-GROUNDING: new core/import_verify.py — every imported NUMERIC value must trace to an
  explicit page number (Lakh/Crore/Indian-comma/range-endpoint expansion); unverified numerics
  BLANKED + scores nulled + reported; text values flagged-but-kept; evidence quote (source line)
  captured per verified value. Hooked into _extract_detail_for_url (both import+analyze AI paths);
  response carries {verification, geo_note}; record_run persists verification+evidence; new GET
  /api/url-analyze/runs/{run_id}/provenance. Prompt rule 9 added (grounding + range min/max);
  ScraperAPI country_code now defaults to "in". Step2 popup shows "✓/⚠ Page-grounding check" +
  geo note; feedback row gained "Source quotes" button → provenance modal (import-provenance-modal).
- P1 ORG-TYPE TEMPLATES: /hos/scenarios now accepts acting_as (wildcard = untagged); new admin
  CRUD GET/POST/PUT /api/hos/admin/templates (org_types tagging, mirrors acting_as_contexts);
  5 FAMILY starter templates seeded (vacation/school/home/health-insurance/budget, v-gated
  family_templates_seed); new Admin → Intake Scenarios screen (app/admin/scenarios.tsx) with
  org-type filter chips + editor (org/life-area/ask-type/modules/tags/active); registered in
  admin sidebar + home tile; new-decision passes acting_as to scenarios fetch.
- P2 DEEP IMPORT (opt-in, NOT automatic — 5-10x credits): routes/deep_import.py — POST
  /api/deep-import/decision/{id}/start (consent + background asyncio job, deep_import_jobs TTL
  24h) → AI link-picker (fast) → crawls ≤8 rendered pages → ONE consolidation AI call (factors +
  per-option values) → status factors_ready; GET /jobs/{id} (poll, page_texts excluded); POST
  /jobs/{id}/finalize merges ONLY approved factors (zero extra AI), deterministic direction-aware
  scoring, P0 verification vs combined page text, telemetry run w/ provenance. Frontend
  src/components/steps/DeepImport.tsx (setup → progress → factor review w/ include + H/M/L
  priority → merge) mounted in Step2 import card.
TESTED: pytest 10/10 (tests/test_iter107_import_trust.py incl. symbol-wiring regression);
REAL deep-import e2e on books.toscrape.com (3 pages, 6 factors, 13/13 verified, provenance OK);
testing agent frontend 4/4 PASS + regression (iteration_107.json). Agent-fixed bug: my parallel
search_replace race dropped the verify_detail/page_text imports in url_analyze.py (NameError 500
on import) — testing agent restored them; symbol-wiring pytest now guards this.
LESSON: NEVER issue two parallel search_replace calls against the SAME file (2nd race this session).

## 2026-06-12 — Deep Import "blocked site" fix (bookmyshow.com)
BUG: Prod Deep Import of bookmyshow.com failed with the generic "configure ScraperAPI" 422 even
though ScraperAPI WAS configured. Root cause: BMS is an Akamai-protected domain — ScraperAPI's
standard pool intermittently returns 500 "Protected domains may require premium=true"; the old
_scraperapi_fetch swallowed the reason and _fetch_html showed the misleading "configure it" text.
Also confirmed: current ScraperAPI plan does NOT include Premium proxies (403 "upgrade plan").
FIX (core/url_crawl.py):
- _scraperapi_fetch now returns (html, fail_reason), logs status+body, and AUTO-RETRIES once with
  premium=true when ScraperAPI flags a protected domain (works automatically once plan upgraded).
- _scraperapi_reason() maps failures to admin-readable text (protected domain / plan upgrade
  needed / invalid key-credits / rate limit).
- _fetch_html 422 now branches: key configured → "ScraperAPI fallback also failed — <reason>";
  no key → original "configure ScraperAPI" guidance. fetch_rendered unpacks the tuple.
- tests/test_iter95: stale "configured is False" assertion relaxed (key now set in preview).
TESTED: reproduced original failure; reason-mapping unit checks; pytest 16 passed/1 skipped
(iter107 + iter95 suites); REAL deep-import e2e on https://www.bookmyshow.com/ → factors_ready
(3 movie options, 4 factors). NOTE: needs DEPLOY to jelcos.ai; prod may still fail intermittently
on protected domains until ScraperAPI plan includes Premium — error now says exactly that.

## 2026-06-12 — Iter 108: Scrape metering + deep-import failure telemetry + Recon ScraperAPI
User asked: (1) why the Deep Import failure was invisible in Admin Import Analytics, (2) per-user
metering of ScraperAPI costs + Revenue Recon coverage so there is no unit-economics loss.
A) FAILURE TELEMETRY (routes/deep_import.py): _discover now takes a tel ctx (new_tel endpoint=
   "deep_import", route="deep_import_discovery"); all 5 error paths go through _fail() which sets
   the job error AND records an error run in url_import_runs (visible in Import-URL Intel + fires
   failure alert). Discovery success also records a symmetric success run; finalize unchanged.
B) SCRAPE METERING (NEW core/scrape_meter.py + url_crawl.py threading): every SUCCESSFUL
   ScraperAPI fetch charges the user's AI wallet, auto cost-derived: scraper_credits (render=10,
   premium=25) × plan_usd/plan_credits × (1+scrape_markup_pct%) → app credits via blended rate.
   Defaults: Business $299/3M credits, 5% markup → rendered fetch ≈ 5.23 cr. Wallet balance ≤ 0
   BLOCKS scrape (InsufficientCredits → 402 "top up" in url_analyze/import/matrix_import; deep
   import surfaces it on the job). Rows in scrape_usage + ai_wallet_ledger (feature=scrape_fetch).
   fetch_page/fetch_rendered now accept user_id (all callers updated). url_telemetry.record_run
   aggregates the run's scrape usage onto doc["scrape"]. New wallet config keys (admin-editable
   in /admin/ai-wallet-config): scraperapi_plan_usd_month, scraperapi_plan_credits_month,
   scrape_markup_pct.
C) RECON (core/recon.py + app/admin/recon.tsx): summary() gains "scraperapi" block (fetches,
   credits used, est_cost_inr at plan rate, charged credits/value incl markup, LIVE /account
   snapshot, plan config); verdict surplus now subtracts scrape liability; daily_tally rows gain
   scrape_fetches + scrape_cost_inr (new table columns).
TESTED: pytest tests/test_iter108_scrape_metering.py 6/6 + iter107/95 regression 16 pass; live
metering verified (5.23 cr debit, ledger+scrape_usage rows); zero-balance gate verified;
example.com deep-import failure visible in admin runs; testing agent iteration_108.json ALL 5
frontend tests PASS. LESSON: expo runs with CI=true → bundle is STALE after tsx edits; ALWAYS
`sudo supervisorctl restart expo` after frontend changes before UI testing.

## Iteration 109 — Deep Import two-hop discovery (homepage/portal base URLs) — 12 Jun 2026
USER BUG (angry): Deep Import failed on base URL https://www.nobroker.in/ + context "Choose best
2 BHK Flat for Rent in Chennai Mugappair area" → "AI could not identify option detail pages".
ROOT CAUSE (2 compounding bugs in routes/deep_import.py):
 1) _extract_links capped at the FIRST 150 anchors — nobroker homepage has 1,910 links and the
    first 150 are Bangalore/Mumbai SALE footer links; the 67 Chennai-rent links never reached AI.
 2) ONE-HOP discovery only: portals/homepages link to LISTING HUB pages ("Flats for Rent in
    Chennai"), never to individual property detail pages → AI correctly returned 0 options.
FIX (routes/deep_import.py):
 A) _rank_links(): context-keyword relevance ranking (text+url, stopword-filtered) applied
    BEFORE the 150-link prompt cap; _extract_links cap raised 150→600.
 B) TWO-HOP discovery: hop-1 detail-pick (LINKS_SYSTEM now STRICTLY excludes hub/listing pages —
    a detail page = exactly ONE item) → if 0 options, NEW _pick_hubs() AI call (HUBS_SYSTEM,
    metered feature=deep_import_hubs) returns ≤3 same-domain listing-hub urls (validated:
    same-domain only, relative resolved, dupes/base dropped; construction allowed but 404/410
    tolerated) → fetch each hub → detail-pick on hub links → need ≥2 options.
 C) CREDIT SAVER: _page_links() fetches direct FIRST and only escalates to ScraperAPI render
    when the page is link-thin (<10 anchors) — base+hub fetches on nobroker are now FREE
    (previously every base page burned a rendered fetch unconditionally).
 D) Clearer failure copy (paste a listing/search-results URL) + DeepImport.tsx dialog copy now
    says homepage URLs work. Progress labels: "locating a listing page…", "Scanning listing
    page N…"; crawl loop re-based to pct 40.
E2E VERIFIED (real nobroker.in, exact user inputs): hop-1 → [] → hub-hop found
properties-for-rent-in-mogappair-chennai → 5 REAL 2BHK Mogappair flats crawled → 19 grounded
factors (Rent 15-23k, Deposit, Area, Transit Score…) → factors_ready in 221s. Metering intact:
5 rendered option fetches charged (5.23 cr each), hub+base direct = free, deep_import_hubs in
ledger, telemetry success run recorded.
TESTED: tests/test_iter109_deep_import_hub_hop.py 9/9 + iter108 + url_detail_import regression
= 31 pass. Smoke screenshot OK. expo restarted after tsx edit (CI=true stale-bundle rule).

## Iteration 110 — Admin AI Observability + Auto-Tune over Deep Import (per user request) — 12 Jun 2026
USER ASK: In Admin UI, track the AI engine used, the engineered prompt fed to it, and credits
consumed per run — for R&D and AI auto-tuning. Also: auto-tune should run DAILY automatically
AND stay available on-demand via the Generate (AI) button.
IMPLEMENTED (P0+P1+P2, all user-approved):
 P0 backend:
  - core/ai_metering.py: metered_chat meta now returns provider + EXACT MODEL + tokens +
    CREDITS charged (ai_wallet.charge return captured) on both precise & chain paths.
  - core/url_telemetry.py: NEW add_ai_call() multi-call trace (stage, engine, tokens, credits,
    latency, system_prompt/prompt_text/raw_response @6KB each). record_run persists ai_calls +
    rollups: ai_calls_count, ai_tokens, ai_engines[], ai_credits (wallet-ledger debit rollup,
    scrape_fetch excluded), total_credits (= ai + scrape). _lazy_purge strips trace bodies after
    90d ($[] unset), keeps engine/credit metadata. summary() adds avg_credits per segment.
    PostHog event includes ai_credits/total_credits. _LIST_PROJECTION excludes ai_calls bodies.
  - routes/deep_import.py: all 4-6 AI stages traced (links_pick, hubs_pick, links_pick@hubN,
    consolidate) and each stage system prompt now appends active Auto-Tune guidance via
    url_prompt_tuning.get_guidance(deep_links|deep_hubs|deep_consolidate).
 P1 admin UI (app/admin/import-analytics.tsx):
  - Run rows + breakdown tables show credits (new "Avg cr" column on all 3 tables).
  - Drill-down: Engine row lists ALL engines used; Credits row "AI x + scrape y = z cr (N
    fetches)"; NEW expandable "AI call trace" — per call: stage · engine · tokens · credits ·
    latency → tap to reveal engineered system prompt, input prompt, raw response.
 P2 auto-tune:
  - core/url_prompt_tuning.py: DEEP_KEYS {deep_links, deep_hubs, deep_consolidate} added to
    TUNE_KEYS; _failing_runs queries endpoint=deep_import for deep keys; _evidence_text now
    includes engines/credits + per-stage trace excerpts (stage_prefix filtered).
  - DAILY scheduler start_daily_auto_tune_task() (24h cadence, 30min after boot; metered to
    first super_admin; suggestions remain status=proposed → admin approval required). Wired in
    server.py lifespan. Route validation now accepts TUNE_KEYS for generate/revert.
VERIFIED LIVE: nobroker 3-page deep import → run doc has 6-call trace (gemini-2.5-flash, groq
llama-3.3-70b, claude-sonnet-4-6), ai_credits 730.57 + scrape 15.70 = 746.27 cr. Admin UI
screenshot: trace + credits + Avg cr all render; on-demand generate for deep_links produced a
proposed suggestion from real failing-run evidence.
R&D INSIGHT SURFACED BY THE NEW DATA: deep import costs ~730 AI credits/run — links_pick calls
are ~7-10K tokens each (150-link prompt). Candidate optimization: cap link list ~60 + page text
4K for pick stages → est. ~50% cost cut. PENDING USER DECISION.
TESTS: tests/test_iter110_ai_observability.py (8) + conftest.py event-loop guard; converted
iter108/109/110 to persistent-loop convention (asyncio.run was breaking sibling suites by
order). Full battery 52/52 passes in both orders.
NOTE: drill-down requires SUPER ADMIN (veales.vedic.decisions@gmail.com in dev); admin@test.com
gets "Super Admin access required" on import-analytics data.

## Iteration 111 — Engine tiering (margin protection) + upfront credits UX in import dialogs — 12 Jun 2026
USER ASK: (1) complete the proposed "engine downgrade" improvement; (2) explicitly & elegantly
show credits required + credits available (with top-up option) in Import URL AND Deep Import —
both flows confirmed metered.
IMPLEMENTED:
 A) Engine tiering (margin protection):
  - NEW core/engine_recos.py: per-stage tier config (links_pick/hubs_pick/consolidate →
    fast|precise|job; 'job'=user's chosen tier; stored app_config key=deep_stage_tiers) +
    compute_recos(): per-stage success% + avg credits per tier from ai_calls trace, with
    conservative recommendations (downgrade_to_fast ≥90% over ≥3 fast calls; upgrade_to_precise
    <60%; try_fast for consolidate when no fast sample).
  - routes/deep_import.py honors stage tiers at runtime (pick_tier/hub_tier/cons_tier).
  - Admin API: GET /api/admin/import-analytics/engine-recos, PUT .../engine-tiers (super admin,
    validated). Admin UI: "Engine tiering — Deep Import" card with per-stage stats, reco text,
    and fast/precise/job chips (apply = instant).
 B) Credits preview strips (user-facing):
  - NEW GET /api/ai-wallet/import-estimate?endpoint=import|deep_import&pages&tier — history-based
    estimate (avg total_credits of recent successful runs; per-page for deep) with static
    fallback (url fast 90 / precise 350; deep 250/page) + balance + sufficient/shortfall.
  - NEW src/components/ImportCreditsStrip.tsx: "≈ N cr needed · M cr available" green when
    sufficient; red + "⚡ Top up" button (→ /ai-wallet) when short; re-fetches on pages/tier change.
  - Mounted in DeepImport.tsx (below pages chips) and Step2.tsx URL dialog (below AI ENGINE tier
    selector). Added testID step-dot-N to PRR wizard step circles.
VERIFIED LIVE (screenshots + curl): Deep Import 5 pages → RED "≈ 1244 cr needed · 931 cr
available" + Top up; switch to 3 pages → GREEN "≈ 746 cr needed · 931 cr"; URL dialog → GREEN
"≈ 90 cr needed (est.)". Admin card shows Link pick fast 100% @86.8 cr, Consolidate precise
@305.9 cr. engine-tiers PUT 200 + invalid tier 400. TESTS: tests/test_iter111_*.py — battery
57/57 PASS. Stage-tier defaults intact (fast/fast/job).
GOTCHAS FOR NEXT AGENT:
 - Login API returns `session_token` (NOT access_token) — use it for Bearer curl tests.
 - Playwright login can bounce once back to /auth/login (expo-router getRehydratedState race on
   dev bundle) — retry login in same context; hard goto /prr/{id} loses session, click through
   Solution Box tab instead.
 - admin@test.com is role=admin (no import-analytics data access); super admin =
   veales.vedic.decisions@gmail.com / Jelcos@Admin2026.

## Iteration 112 — Deep Import hard-constraint intent guard (rent vs buy) — 12 Jun 2026
USER BUG (prod): context "…2 BHK Flat for RENT in Chennai Mugappair…" returned SALE/new-project
listings (Price-per-sqft options). AI treated transaction type as SOFT relevance → nondeterministic.
FIX (routes/deep_import.py) — deterministic intent enforced at 4 layers:
 1. _intent_of(context): regex rent|lease|tenant|pg vs buy|sale|purchase|resale|new-projects —
    only when unambiguous (both → None, never guess).
 2. _rank_links: +3 intent match / −6 contradiction → sale links sink below the 150-link cap.
 3. _drop_contradicting: AI-picked options AND hubs whose url+name mention the opposite type
    (and not the requested one) are dropped post-pick. Neutral names kept (page guard decides).
 4. _page_matches_intent: after crawling each option page, rent-intent pages must mention
    rent/per month/monthly/deposit in first 4K chars, else SKIPPED (logged + listed in the
    failure message if <2 valid pages remain: "N page(s) did not match your 'rent' requirement").
 5. _intent_clause injected into LINKS_SYSTEM + HUBS_SYSTEM prompts: "HARD CONSTRAINT: …
    SALE/new-project pages are INVALID".
VERIFIED LIVE (exact user context, nobroker.in homepage, 3 pages): all 3 options now "for Rent
in Mogappair West" with Monthly Rent (25-35k)/Deposit/Maintenance/Total Monthly Outflow factors,
22 factors, 156s, factors_ready. TESTS: tests/test_iter112_intent_guard.py (5) — battery 62/62.
NOTE: dev wallet topped up +2000 cr (ledger feature=dev_test_topup) for E2E. Prod jelcos.ai
needs a DEPLOY to receive iterations 109-112.

## Iteration 113 — Generic hard-constraint gate (any domain) + ~50% deep-import cost cut — 12 Jun 2026
USER ASK: extend the rent/buy guard to a GENERIC constraint extractor (budget caps "under ₹30k",
counts "2 BHK", attributes "furnished") enforced in ANY context, auto-rejecting violating options
before consolidation + deliver the ~50% cost optimization.
IMPLEMENTED (routes/deep_import.py):
 A) CONSTRAINT_SYSTEM + _constraint_check(): ONE fast-tier AI call after page crawl derives the
    context's hard constraints (domain-agnostic) and verdicts each option page pass|fail|unknown.
    - "fail" requires page EVIDENCE + a violated reason (never guess); "unknown" never rejects.
    - FAIL-OPEN: AI/parse errors keep all options. InsufficientCredits propagates.
    - Rejected options removed before consolidate; job gets constraint_note ("N option(s)
      auto-rejected … — <violation>"); <2 valid → honest failure naming the constraint.
    - Traced as stage=constraint_check (engine/credits visible in Admin AI trace).
    - LINKS_SYSTEM also derives generic hard constraints at link-pick time.
 B) COST KNOBS: _rank_links cap 150→60; PICK_TEXT_LIMIT 8000→3000 (base+hub pick prompts);
    CONSOLIDATE_TEXT_LIMIT 6000→4500; CONSTRAINT_TEXT_LIMIT 2500/option.
 C) Frontend DeepImport.tsx: amber shield banner (testID deep-import-constraint-note) in the
    factor-review stage shows the rejection note.
VERIFIED LIVE (nobroker homepage, "…Rent in Chennai Mugappair area under ₹30000 per month"):
gate auto-rejected "Bbcl Vajra — under ₹30,000: Rent - ₹35,000"; kept 15k+25k rent flats; 20
factors; constraint_note populated. COST: 746.3 cr → 330.3 cr per 3-page run (−56%, including
the new gate call): links_pick 9097→3309 tok, consolidate 6798→3724 tok.
TESTS: tests/test_iter113_constraint_gate.py (5) — battery 67/67 PASS. Bundle smoke OK.
GOTCHA: search_replace edits occasionally do not persist when many edits run in one batch —
ALWAYS re-grep critical lines after batch edits (lost edits found twice: admin copy iter110,
hub filter iter112).

## Iteration 161 — FIX: ChatGPT share-link Import URL (React-Router stream) — 25 Jun 2026
USER BUG (prod): Step-2 "Import URL" of a ChatGPT conversation share link always failed with 422
"Couldn't find clear decision factors/options in this conversation".
ROOT CAUSE: chatgpt.com share pages moved to a React-Router v7 turbo-stream payload
(window.__reactRouterContext.streamController.enqueue("...")). The old extract_conversation_text
split on escaped quotes and scraped the page's JS-bundle UI/system-prompt template strings
("Please make this response more concise", Codex ad prompts) instead of the real chat → LLM found
nothing → 422.
FIX (core/url_crawl.py): extract_conversation_text now decodes the React-Router enqueue stream
(_decode_rr_stream) and pulls each user/assistant TEXT message body via the
'"content_type":"text","parts":[..],"<body>"' shape with its role (_messages_from_rr_stream),
falling back to the legacy heuristic only for non-RR pages.
VERIFIED: live E2E on user's real URL https://chatgpt.com/share/6a36d8d2-3b08-83e8-b67a-6dffa9cc9ffa →
POST /api/url-analyze/decision/{id}/import 200 {mode:conversation, item_count:9, factors_added:8,
options_added:9}. testing_agent confirmed (unit 2/2 + live e2e 2/2, no 422 regression).
TESTS: backend/tests/test_chatgpt_share_import.py, test_chatgpt_import_e2e.py.
SCOPE NOTE: ChatGPT only. Claude.ai / Gemini share links use different SSR formats — NOT yet
implemented/verified (need sample share URLs from each to build+test deterministically).

## Iteration 162 — Claude share-link import + Review-before-merge — 26 Jun 2026
1) CLAUDE IMPORT (claude.ai/share/<uuid>): page is a client-rendered shell; transcript is at the
   Cloudflare-gated chat_snapshots JSON API. Added fetch_ai_conversation + _scraperapi_get_text
   (fetches that JSON via ScraperAPI) + _claude_messages_from_snapshot (joins message text blocks,
   drops 'not supported on your current device' placeholders). Wired into the import conversation branch.
   VERIFIED live: POST /api/url-analyze/decision/{id}/import {url:claude.ai/share/4b324e58..., own} ->
   200 factors_added:8 options_added:9. test: backend/tests/test_claude_share_import.py.
2) REVIEW-BEFORE-MERGE: ImportRequest.preview=true (conversation imports only) -> returns
   {mode:"conversation_preview", factors:[names], options:[names]} WITHOUT writing to the decision.
   New POST /api/url-analyze/decision/{id}/import/confirm {factors,options} merges the reviewed
   (renamed/trimmed) list with NO extra fetch/LLM cost. Frontend: new ImportReviewModal.tsx
   (testID import-review-modal) + Step2 sends preview:true for chatgpt/claude/gemini share links,
   opens the modal on preview, confirm calls /import/confirm. Fixed a brief progress/review modal overlap.
   testing_agent: backend 9/9 + frontend PASS (rename from UI persisted).
GEMINI: NOT implemented — the URL the user provided was a private gemini.google.com/app/<id> session
   (not a public share); needs a real gemini.google.com/share/<id> or g.co/gemini/share/<id> to build+verify.
DEV NOTE: super@test.com AI-wallet was overdrawn during testing; topped back to 2000 cr (ai_wallets.balance).

## Iteration 163 — Gemini guard + drag-reorder reviewed options — 26 Jun 2026
GEMINI: Investigated the user's link (share.gemini.google/eOlCCzMAqeHt -> gemini.google.com/share/eb754d628ffa).
  Gemini serves a SIGNED-OUT shell; the conversation loads only for the logged-in owner via an authenticated
  batchexecute RPC. Not in direct HTML; NOT captured by ScraperAPI render=true (DOM stays empty;
  render+wait_for_selector -> 500). Automated import not feasible. Added is_gemini_share_url() + an early guard
  in _import_inner returning a clear 422 (points to the 'Text' import) BEFORE any fetch/LLM spend. Verified 422 fast.
DRAG-REORDER: Rewrote ImportReviewModal to use react-native-draggable-flatlist for OPTIONS (GestureHandlerRootView
  wraps the Modal). Drag handle (review-option-drag-N) + rank badge (1..N) per option; onConfirm sends options in the
  reordered array order; merge_into_mydezider preserves order so option #1 is most-preferred in Step 6. Factors stay a
  simple editable list. NOTE: Metro runs in CI mode — must `supervisorctl restart expo` to rebundle frontend changes.
testing_agent: backend 6/6 + frontend PASS — real mouse drag reordered options and the new order PERSISTED to
  GET /api/decisions/{id} options[]. retest_needed:false.

## Iteration 164 — Auto-jump to Step 6 + spotlight top option after reviewed import — 26 Jun 2026
After the review-before-merge confirm (ImportReviewModal), Step2.confirmReviewedImport now jumps to Step 6
(Options) via setCurrentStep(6) and spotlights the top-ranked option. Added highlightOptionName +
setHighlightOptionName to DecisionContext; Step6 highlights the matching option card (amber border + 'Top pick'
star badge) and auto-clears after 4.5s. Removed the blocking success alert (the jump+spotlight is the feedback).
The top option = first item in the (drag-reordered) options list, so the user lands on their stated priority.
VERIFIED via screenshot: confirm -> 'Step 6/10' active, 'Java Capital' card shows 'Top pick' badge highlighted.
Reminder: Metro CI mode — restart expo to rebundle frontend edits.

## Iteration 165 — FIX: platform admin roles truly bypass ACM — 26 Jun 2026
BUG: Admin 'User View' (super-admin opening the normal app) hid 5 release-disabled features
(collab_knowledge_marketplace, collab_my_earnings, collab_karma_fame, digilocker, sub_auto_renew).
ROOT CAUSE: access_key 'platform_admin' did not bypass the matrix — it fell back to paid_enterprise/paid_pro
rules, so features hidden for those tiers were hidden for admins too. FIX (core/acm_engine.py):
check_feature_access + get_all_feature_access early-return access_level='full' (quota -1) when
access_key=='platform_admin'. testing_agent 6/6: super-admin 152/152 full; free user still governed
(full:95/locked:34/hidden:19/read:4); digilocker hidden for free, full for admin.
NOTE (open item, not a bug): user_types unit_tester/integration_tester/alpha/beta are defined and ALL 152
features already have ACM columns for them (granular per-role control via Admin > ACM matrix). However there is
NO Admin UI to ASSIGN a user_type to a specific user yet — only the API PUT /api/acm/user/{user_id}/type exists.

## Iteration 166 — Admin UI: assign user_type (tester/alpha/beta/trial) on User Lookup — 26 Jun 2026
FEATURE (user request): Admins can now flip a user to a tester/early-access tier from the UI.
- backend/routes/acm.py: PUT /acm/user/{id}/type gate changed to super_admin OR can_view_pii (the per-admin
  permission Super Admin grants for User Lookup). Invalid type -> 400; non-permitted -> 403.
- backend/routes/pii_admin.py: PII lookup profile now returns user_type + effective_user_type.
- frontend/app/admin/user-lookup.tsx: after a successful lookup, a 'User Type & Access' card (assign-type-card)
  shows current tier + chips (assign-type-{free,trial,unit_tester,integration_tester,alpha,beta}) + Save
  (assign-type-save) -> PUT /acm/user/{id}/type. Screen already lives under Dashboard → Essentials.
- Which features each tier unlocks stays GRANULAR via Admin → ACM matrix (all 152 features already have
  unit_tester/integration_tester/alpha/beta columns). No bypass added for tester tiers (per user choice).
testing_agent: backend 8/8 + frontend PASS. Test target user: acmtarget@test.com / WhatsApp +919900112233.
NDA-checkbox tap nuance noted in test_credentials/test_result for future Playwright runs.

## Iteration 167 — Tier feature-visibility preview on assign card — 26 Jun 2026
New GET /api/acm/user-type-access-summary?user_type=<t> (gated super_admin OR can_view_pii) returns
{total, usable=full+read, visible=usable+locked, full, read, locked, hidden} for a tier WITHOUT changing
any user — synthetic profile through get_all_feature_access. User Lookup assign card now shows a live preview:
when a different tier is selected -> "Beta → 143 of 152 usable (+44 vs now) · 9 hidden"; when same as current
-> "Currently N of 152 usable · H hidden". Added testIDs pii-nda-ack, pii-lookup-submit, assign-type-preview.
Verified: endpoint counts (free 99u/19h, beta 143u/9h, unit_tester 148u/4h); screenshot shows preview on card.
