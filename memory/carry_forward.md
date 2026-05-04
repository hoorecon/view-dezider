# Carry-Forward List for the Next Fork

**Last updated:** End of fork session after Public Pulse Phase 1+2+2.5 ship + Solution Matrix OrgType backend hardening.

**Read this first** before starting new work so you know what's done, what's blocked, and what's waiting.

---

## ✅ Just completed in this fork (do NOT redo)
- Public Pulse Phase 1 — 27 endpoints + 5 citizen screens (Life Direction / Marriage Readiness / Govt Benefit Finder + 5 public dashboards with k-anonymity + consent layer). Backend 51/51, frontend retest ✅.
- Public Pulse Phase 2 — 27 endpoints + Org/Gov/Admin portals + state-machine rectification workflow + admin-configurable (cooldown, visibility, routing cascade). Backend 51/51, frontend retest ✅.
- Public Pulse Phase 2.5 — Pluggable file storage (`core/file_storage.py`: Mongo/S3/GCS backends), admin upload limits API, `apply.tsx` with server-loaded limits. 6 upload categories. ✅
- P0 Production Hardening — 169+ MongoDB indexes, `slowapi` rate limiting (DEFAULT=120, AUTH=10, AI=10, EXPENSIVE=20/min, all ENV-overridable), request observability (X-Request-ID, X-Response-Time-MS), typed LLM error polish (503 + Retry-After + X-Request-ID on budget/rate-limit/upstream). ✅
- P1 Refactor — `models/` + `prompts/` packages; `admin_docs.py` 720→343 lines; `decisions.py` -22%. 28/28 regression green. ✅
- ACM — 32 modules / 83 features; auto-reseed on version bump via `ensure_acm_seeded_on_boot()`. ✅
- **Solution Matrix OrgType backend hardening** (items 4–6 from prior carry-forward):
  - New `backend/models/solution_matrix_models.py` with `MatrixResourceCell`, `MatrixLayerSet`, `normalise_layer_set()`
  - `routes/tools.py` defaults now use nested shape; PUT handler normalises incoming matrix fields
  - `tests/test_solution_matrix_orgtype.py` — **31/31 assertions pass** covering 84-cell roundtrip, partial update, legacy flat auto-migration, empty defaults
  - Run with: `python /app/tests/test_solution_matrix_orgtype.py`

---

## 🔴 P0 — External blockers (cannot code around)

| # | Item | Blocker | What unblocks it |
|---|------|---------|------------------|
| 1 | DigiLocker eKYC (API Setu) | Awaiting user's API Setu government approval + keys | User injects `APISETU_CLIENT_ID` + `APISETU_CLIENT_SECRET` + `APISETU_ENV` into `backend/.env`, then wire sandbox flow |
| 2 | Exotel SMS OTP | Awaiting user's DLT template approval from TRAI | User adds `EXOTEL_SID`, `EXOTEL_TOKEN`, `EXOTEL_SENDER_ID`, `EXOTEL_DLT_TEMPLATE_ID` to `.env` |
| 3 | LLM Budget Reset re-test | Emergent LLM key at $0.4254 / $0.40 cap | Budget resets naturally — re-run the single curl in `/app/memory/pending_verifications.md`; when 200, re-run the 4 AI flows listed there |

---

## 🟠 P1 — Ready to ship (no blockers)

### A. Public Pulse Phase 3 — AI Intelligence Layer
- [ ] AI-summarised feedback clusters (embedding-based grouping of citizen feedback per org)
- [ ] Smart recommendations engine — link score band → curated govt schemes / solutions
- [ ] Auto-drafted Org responses using the state-machine hooks (acknowledge / respond templates)
- [ ] Advanced analytics — trend lines, YoY comparisons on the 5 public dashboards
- ⚠️ Requires LLM budget reset (item #3 above) before full E2E testing

### B. White-labelled Org Public Sub-Portals
- [ ] Per-org slug-based public page `/p/{org_slug}` — branded hero, primary_color theming, org's survey feed
- [ ] Org-scoped surveys (not just feedback): multi-question public forms → aggregate to org dashboard
- [ ] Embeddable widget / iframe for orgs to place on their own site
- [ ] Social-share meta tags (OG image from org logo)

### C. Solution Matrix OrgType — polish items (not blockers; enhancements)
- [ ] **PDF export renderer** — does the existing action-plan PDF handle the new 84-cell layout? Verify / update renderer if needed (check `backend/utils/pdf_generator.py` or similar)
- [ ] **AI CLD hook** for `solution_matrix` module_type — CLD engine supports 16 module types; wire matrix → `/api/cld/module/solution_matrix/generate` (blocked on LLM budget)
- [ ] **Per-OrgType ACM feature gating** — e.g., only Govt orgs see Govt column; hide others. Add `pp_org_role` → `solution_matrix_orgtype_*` mapping in `data/acm_seed_data.py`
- [ ] **Starter templates per OrgType** — seed 4 sample matrices (one per Individual/Org/Govt/Nature) via admin-curated template system

### D. Voice Browsing — Epic (new module)
Current state: **scoped to PRR Decision Steps only** (`VoiceStepInput.tsx`, `stepVoiceParser.ts`, `voiceCommandParser.ts`, `VoiceAssessmentInput.tsx`).
- [ ] **Global voice navigation layer** — floating command bubble on every screen with route-aware parser ("Open Goal Setter", "Show my decisions", "Start Conflict Breaker")
  - Implementation path: `frontend/src/components/GlobalVoiceNav.tsx` + `frontend/src/utils/routeVoiceParser.ts` + mount in `frontend/app/_layout.tsx`
- [ ] **Voice input in other modules**:
  - Solution Matrix (critical: "Switch to Govt" / "Set time to 2 weeks")
  - Public Pulse self-discovery (citizen inclusion + accessibility win)
  - Goal Setter, Journal, Conflict Breaker 9-stage wizard
  - Test123, Lifestyle Designer, PNA, TEPFI, CLD Engine
- [ ] **TTS readout across all tools** — `expo-speech` is currently only in AI Assistant; extend to read on-screen content on demand (accessibility)
- [ ] **Multi-language voice** — match Solutions Store's 9 languages (en, ta, hi, te, kn, ml, mr, bn, gu). Use `expo-speech-recognition` locale + `Speech.speak({ language })`.
- [ ] **Continuous voice mode + voice undo/redo** — currently press-to-talk only

### E. Minor Polish (safe, under 30 min each)
- [ ] Auto-reseed ACM for `pp_org_portal` feature at boot without manual `POST /acm/seed?force=true` (the testing agent flagged this; already fixed via `ensure_acm_seeded_on_boot` on version bump — just bump `ACM_SEED_VERSION` next time you add features)
- [ ] Fix benign `backend_test_regression.py` assertion for SolutionsStore `config/countries` / `config/languages` (expects bare array, endpoint returns `{countries: [...]}` — trivial test-side fix)
- [ ] Verify `core/file_storage.py` S3 + GCS code paths once any cloud key is provided (currently only Mongo backend verified E2E)
- [ ] 3 Public Pulse API contract callsites flagged by testing agent (non-blocking, UI works):
  - `POST /consent` 422 (schema mismatch on test-side payload, not UI)
  - `POST /feedback` 422 (same)
  - `POST /score/submit` 404 (actual endpoint is `/tools/{slug}/start`)
  - Verify no legacy callers exist in `frontend/app/tools/public-pulse/*` using old paths

---

## 🟡 P2 — Physical device E2E tests (require real phone/camera/SIM)

| # | Test | Why physical device |
|---|------|---------------------|
| 4 | Face Authentication / MediaPipe continuous presence tracking | Needs real camera stream |
| 5 | Razorpay payment end-to-end | Keys in `.env`, needs real UPI/card; test mode works but live flow is the real check |
| 6 | WhatsApp OTP (UltraMsg) end-to-end | Real phone number receives SMS |
| 7 | Camera-based document scan for DigiLocker (when unblocked) | Real document in hand |
| 8 | Push notifications via Expo Push API | Real device token |

---

## 🔵 P3 — Backlog (nice-to-haves, no strict schedule)

- [ ] `server.py` is now 189 lines — split into router groups (`routers/_public.py`, `routers/_private.py`) if it grows further
- [ ] `admin_docs.py` is 343 lines — fine, but if more docs are added, break `PROMPT_REGISTRY` into `prompts/admin_docs/{prd,srs,regression,uat,api,postman,acm}.py`
- [ ] Add GraphQL layer for the 5 Public Pulse dashboards (currently REST; GraphQL would let orgs query just their cohort slices)
- [ ] i18n pass for all hard-coded strings in `frontend/app/tools/public-pulse/*` (Indic-language priority: Tamil, Hindi, Telugu first)
- [ ] Accessibility audit — contrast ratios, screen-reader labels on all chips and icon-only buttons

---

## 📁 Key files & locations for the new fork agent

### Backend
- `backend/core/acm_engine.py` — auto-reseed on version bump (bump `ACM_SEED_VERSION` in `acm_seed_data.py` to force refresh at boot)
- `backend/core/file_storage.py` — pluggable Mongo/S3/GCS backends; admin-tunable via `PUT /api/public-pulse/admin/storage-backend`
- `backend/core/llm_errors.py` — wrap every `emergentintegrations.LlmChat` call with `llm_error_to_http()` for typed 503
- `backend/core/rate_limiting.py` — limits in `.env` vars `RATE_LIMIT_DEFAULT / _AUTH / _AI / _EXPENSIVE`
- `backend/models/solution_matrix_models.py` — **NEW**: nested OrgType matrix schema + `normalise_layer_set()`
- `backend/routes/public_pulse.py` — Phase 1 (27 endpoints)
- `backend/routes/public_pulse_org.py` — Phase 2 + 2.5 (27 endpoints + admin storage + upload limits)
- `backend/routes/tools.py` — Solution Finder + Solution Matrix (updated with nested defaults + PUT normalisation)

### Frontend
- `frontend/app/tools/public-pulse/*` — Phase 1 + 2 + 2.5 screens
- `frontend/app/tools/solution-matrix.tsx` — nested OrgType UI (3 × 4 × 7 = 84 cells)
- `frontend/src/components/VoiceStepInput.tsx` — existing PRR-only voice input (reuse pattern when expanding)
- `frontend/src/utils/stepVoiceParser.ts` — existing PRR step parser (use as template for module-specific parsers)

### Tests
- `tests/test_solution_matrix_orgtype.py` — **NEW**: 31/31 assertions on Solution Matrix OrgType persistence
- `backend_test_regression.py` — 28-test quick regression sweep (run after any backend change)
- `backend_test_public_pulse.py` — Phase 1 (51 assertions)
- `backend_test_public_pulse_phase2.py` — Phase 2 (51 assertions)

### Memory
- `memory/test_credentials.md` — test user credentials for auth flows
- `memory/pending_verifications.md` — LLM budget reset re-test checklist
- `memory/carry_forward.md` — **THIS FILE**

---

## 🧪 Quick health checks for the new fork agent (run at session start)

```bash
# 1. Services up?
sudo supervisorctl status
# Expected: backend RUNNING, expo RUNNING, mongodb RUNNING

# 2. Backend healthy + DB reachable?
curl -s http://localhost:8001/api/health
curl -s http://localhost:8001/api/health/ready
# Expected: {"status":"ok",...} on both

# 3. ACM up-to-date?
# Boot log should show: 'ACM boot check: ACM already seeded (up to date) (modules=32, features=83, version=2026-05-04-01)'

# 4. Regression sweep (no code changes needed to run)
python /app/backend_test_regression.py         # expect 26-28/28
python /app/tests/test_solution_matrix_orgtype.py   # expect 31/31

# 5. LLM budget still capped?
EMAIL="budget_probe_$(date +%s)@test.com"
TOKEN=$(curl -s -X POST http://localhost:8001/api/auth/register \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$EMAIL\",\"password\":\"pass1234\",\"name\":\"P\"}" | python3 -c "import sys,json; print(json.load(sys.stdin)['session_token'])")
curl -s -X POST http://localhost:8001/api/ai-assistant/quick-ask \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"question":"Say hi in 3 words","language":"en"}'
# 503 llm_budget_exceeded = still capped. 200 with answer = BUDGET RESET → run the 4 verification flows in pending_verifications.md
```

---

## 🎯 Recommended first-hour plan for the next fork agent

1. Run the 5 health checks above. Log results.
2. Read `test_result.md` from line 4380 onwards (Public Pulse / Phase 2.5 / LLM polish section).
3. Ask user: which of P1 items (A / B / C / D / E) to tackle first — they are independent and all ready.
4. If LLM budget has reset: knock out the 4 AI verification curls in `pending_verifications.md` first (15 min of work, unblocks Phase 3).
5. DO NOT touch any `.env` URL / port values — they are fork-specific.
