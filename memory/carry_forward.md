# Carry-Forward List for the Next Fork

**Last updated:** End of fork session after **v3.11.0 LDC + AALA + Daily Tracker + Time Allocation + Drift Report** + v3.10.0 multi-edition brand architecture + v3.9.1 ExpertNet expert self-serve + v3.9.0 OrgSurveys + ExpertNet Jitsi-Room.

**Read this first** before starting new work.

**🚨 CRITICAL FOR ALL FUTURE SESSIONS:** Read `/app/memory/brand_architecture.md` for locked brand decisions.

---

## ✅ Just completed in this fork (do NOT redo)

### v3.11.0 — Life Directions Compass + AALA + Daily Tracker (NEW)
The personal-decision-OS layer the user asked for: **direction → inventory → plan → reality → allocation → drift**.

**Backend (4 new modules):**
- `routes/life_directions.py` — LDC: 7 default freedoms (Business · Financial · Time · Health · Emotional · Social · Mission), 3 reserved suggestions (Sexual · Spiritual · Eternal), custom freedoms allowed. Rank-based weight (1→10, 10→1). **This-week pin = 1.5× multiplier** (Q2c hybrid). Auto-clears Sunday 23:59 UTC. `models/life_directions_models.py`.
- `routes/aala.py` — AALA = **Accrued Assets & Liabilities Analysis**: TEPFI × {Self, Micro, Macro} = 15-cell ledger. Each cell: assets[] + liabilities[] + balance_score(-10..+10) + summaries. Append-only delta journal. `models/aala_models.py`.
- `routes/daily_tracker.py` — multi-modal entry log (text now; voice/AI hybrid endpoint already wired). LLM classify endpoint with **graceful keyword fallback** when LLM budget capped. Each entry can attach AALA deltas + LDC freedom tags + minutes; AALA cell auto-updates on submit.
- `routes/time_allocation.py` — LDC + AALA-aware allocator: `/suggestions` ranks CTT tasks + routines + PNA goals; `/drift` produces the Drift Report (LDC ideal % vs daily-tracker actual %).

**TEPFI canonicalisation:**
- ⚠️ Founder lock 2026-05-06: **TEPFI-I = "Infrastructure"** (NOT "Intellectual"). All new modules use this. Solution Matrix already used Infrastructure; consistency preserved.

**Frontend (4 new screens + entry points):**
- `app/tools/life-directions-compass.tsx` — drag-to-reorder via chevrons, add custom + reserved suggestions, this-week pin with star-flag, influence slider 0-100%
- `app/tools/aala.tsx` — 5×3 grid colored by balance, tap any cell → modal with summaries + asset/liability lists + score editor
- `app/tools/daily-tracker.tsx` — text entry + AI classify (engine-aware UX), activity/minutes, freedom multi-select chips, AALA delta picker
- `app/tools/drift-report.tsx` — LDC-ideal vs actual %, color-coded over/under/aligned, suggested-correction-minutes per freedom, 7d/14d/30d window
- 4 new entry points added to Profile tab → routes to all 4 screens

**Smoke tests passed (manual python script):**
- LDC: seed/reorder/pin/weight (with 1.5× multiplier verified)
- AALA: 15-cell auto-seed, summary edit, asset/liability add+remove, feasibility score
- Daily Tracker: classify (LLM + keyword fallback), create entry, AALA delta cascading, today roll-up
- Time Allocation: suggestions ranked correctly, drift report produced — `over` / `under` / `aligned` statuses + suggested-correction minutes
- Cross-module: a daily-tracker entry with AALA delta correctly bumped `finance/self` balance from 6.5 → 8.0

**Visual UAT:** all 4 screens screenshot-verified rendering live with real data (rank weights, color-coded cells, drift bars).

### v3.10.0 — Multi-edition brand architecture
[unchanged from earlier in this file]

### v3.9.1 — ExpertNet expert self-serve dashboard (4 missing screens)
Fully shipped end-to-end (frontend UAT 8/8 PASS).
Locked the platform to support **JELCOS AI** (now), **GeoDezider AI** (next), **Earth Dezider Consumer** (year 3) on a single codebase.

- **Brand decisions locked** in `/app/memory/brand_architecture.md`:
  - **Legal entity:** VEALES Vedic Decisions Private Limited
  - **Internal codename:** View Dezider
  - **Master / roof brand:** Earth Dezider — *"The Decision OS for People"*
  - **Product line 1:** JELCOS AI = *"Joyful Executive's Life Choices Operating System powered by Artificial Intelligence"* — domain `jelcos.ai`
  - **Product line 2:** GeoDezider AI — domain `geodezider.ai`
  - **Future consumer:** Earth Dezider — domain `earthdezider.com`
  - Whitelabels sit *under* JELCOS / GeoDezider (not a separate edition)
  - Imprint rule: **"by Earth Dezider"** on every product surface; "VEALES" only on legal/billing
- **NEW backend** `core/branding.py` — edition registry (`jelcos` / `geodezider` / `consumer`) with display name, full expansion, primary_color, audience_segments, enabled_features
- **NEW backend** `routes/branding.py` — 3 endpoints:
  - `GET /api/branding/current` (public; for splash/login hydration)
  - `GET /api/branding/editions` (super-admin; lists all)
  - `POST /api/branding/me/edition` (auth; user picks home edition)
- **NEW env var** `PRODUCT_EDITION=jelcos` (default) in `backend/.env` — single switch to deploy as any edition
- **NEW frontend** `src/store/brandingStore.ts` — Zustand store, hydrates on app boot, AsyncStorage cached, fallback constants for offline/cold-boot
- **NEW frontend** `src/components/BrandFooter.tsx` — small "An Earth Dezider product" / hero variant with edition wordmark
- **Wired in** `app/_layout.tsx` (boot-time hydration) + `app/auth/login.tsx` (footer rendered live ✅)
- **Smoke-tested** 6/6 backend assertions PASS (anon read, user 403, admin list, set my edition, invalid 400, reset)
- **Visually verified** "An Earth Dezider product" footer renders on login page

### v3.9.1 — ExpertNet expert self-serve dashboard (4 missing screens)
Fully shipped end-to-end (frontend UAT 8/8 PASS).

- **NEW** `/tools/expert-net/manage/[expert_id]` — single screen with 4 tabs:
  - **Inbox** — incoming bookings filtered to this expert; status filter chips; confirm/decline; start-call (Jitsi); view intake answers modal; deep-link to recommend
  - **Schedule** — availability editor (weekly windows weekday/start/end/slot + blackout dates)
  - **Intake form** — builder for both modes (built-in JSON-schema fields OR external URL like Google Forms)
  - **Webinars** — list mine + Create webinar modal (free/paid, capacity, schedule); Go-live → Jitsi
- **NEW** `/tools/expert-net/recommend?booking_id=…` — search Solutions Store, pick item, optional note + auto-create CTT task + recurring routine (daily/weekdays/weekly/custom)
- Wiring: each expert card in Manage tab now has "Open dashboard" CTA → routes to manage screen
- Bug fixes shipped during build: removed inline `useRouter()` hook misuse, removed `withCredentials: true` from `src/utils/api.ts` AND `src/store/authStore.ts` (5 occurrences) — was breaking CORS on cross-origin testing without affecting auth (Bearer token in header)

### v3.9.0 — OrgSurveys (white-label sub-portal Phase 3-B)
Backend regression: 42/43 PASS (1 minor yes_no bucket-label bug fixed in-place).

- **NEW** `backend/routes/org_surveys.py` — 8 endpoints under `/api/p/{slug}/surveys/*`
  - 7 question types: short_text/long_text/single_select/multi_select/rating_5/yes_no/number
  - Full org-admin CRUD + public read + anon-or-auth submit + aggregates with bucket counts and averages
  - Cascade delete responses; org-admin authorization via `_is_org_admin` helper
- **REBUILT** `frontend/app/p/[slug].tsx` — 4-tab branded portal (About / Surveys / Reviews / Feedback) with primary_color theming
- Seeded: "Annual Skills Survey 2026" on slug `coimbatore-skills-foundation-5b9c19`

### v3.9.0 — ExpertNet Jitsi-Room fix
- 3 ExpertNet endpoints (connect-now / booking start-call / webinar start) now return `video_url=/tools/jitsi-room?room={sid}` instead of broken collab-call URL
- **NEW** `frontend/app/tools/jitsi-room.tsx` — public meet.jit.si via WebView (native) / iframe (web), auth-free
- Backend regression: 17/17 PASS

### Bundle bug fix bonus
- `frontend/app/tools/solution-detail.tsx` — removed pre-existing duplicate `myPending` declaration that was blocking the entire metro bundle

---

## 🔴 P0 — External blockers (cannot code around)

| # | Item | Blocker | What unblocks it |
|---|------|---------|------------------|
| 1 | DigiLocker eKYC (API Setu) | Awaiting user's API Setu approval + keys | User injects `APISETU_*` into `backend/.env` |
| 2 | Exotel SMS OTP | Awaiting user's DLT template approval | User adds `EXOTEL_*` keys |
| 3 | LLM Budget Reset re-test | Emergent LLM key budget capped | Budget resets — re-run curls in `pending_verifications.md` |

---

## 🟠 P1 — Ready to ship (no blockers)

### A. Public Pulse Phase 3 — AI Intelligence Layer  *(blocked on LLM budget)*
- [ ] AI-summarised feedback clusters
- [ ] Smart recommendations linking score band → schemes
- [ ] Auto-drafted Org responses
- [ ] Trend lines / YoY comparisons on the 5 dashboards

### B. White-labelled Org Sub-Portals — *partially shipped*
- [x] Per-org branded `/p/{slug}` page in Expo (4 tabs, themed)
- [x] **Org-scoped surveys** (multi-question forms, public submit, aggregates)
- [x] HTML embed widget (existed previously)
- [ ] **Org-admin UI** to manage their own surveys (currently admin-only via API; no Expo screen yet)
- [ ] Social-share OG meta tags for `/api/embed/{slug}`
- [ ] Per-org CSS overrides beyond primary_color (logo upload, hero image, fonts)

### C. Solution Matrix OrgType — polish
- [ ] PDF export renderer for the 84-cell layout
- [ ] AI CLD hook for `solution_matrix` module_type *(blocked on LLM budget)*
- [ ] Per-OrgType ACM feature gating
- [ ] 4 starter templates (Individual / Org / Govt / Nature)

### D. Voice Browsing — Epic
- [ ] Global floating voice command bubble + route-aware parser
- [ ] Voice input in Solution Matrix / Public Pulse / Goal Setter / Conflict Breaker
- [ ] TTS readout across all tools (extend `expo-speech` beyond AI Assistant)
- [ ] Multi-language voice (9 Solutions Store languages)
- [ ] Continuous voice mode + voice undo/redo

### E. ExpertNet — Polish (FULLY SHIPPED for v1; below items are *nice-to-have*)
- [ ] Calendar grid slot picker (currently chip list)
- [ ] Expert ratings & review surface (separate from ReviewNet which is solutions-only)
- [ ] Push notifications when booking confirmed / call starting / webinar countdown
- [ ] Add `testID="xnm-webinar-title"` etc. for cleaner UAT scripting (cosmetic)
- [ ] Delivery status update UI for users (currently passive view)

### F. Minor Polish
- [ ] Auto-reseed ACM for `pp_org_portal` at boot
- [ ] Fix benign `backend_test_regression.py` Solutions Store countries/languages assertion
- [ ] Verify `core/file_storage.py` S3 + GCS code paths once any cloud key is provided

---

## 🟡 P2 — Physical device E2E tests (require real phone/camera/SIM)

| # | Test | Why physical device |
|---|------|---------------------|
| 4 | Face Authentication / MediaPipe presence tracking | Real camera stream |
| 5 | Razorpay payment end-to-end | Real UPI/card |
| 6 | WhatsApp OTP (UltraMsg) end-to-end | Real phone receives SMS |
| 7 | DigiLocker camera scan (when unblocked) | Real document |
| 8 | Push notifications via Expo Push API | Real device token |

---

## 📁 Key files added/changed in this fork

### Backend
- **NEW** `backend/routes/org_surveys.py` — 8 endpoints under `/api/p/{slug}/surveys/*`
- `backend/server.py` — registers `org_surveys_router`
- `backend/routes/expert_net.py` — `video_url` now points to `/tools/jitsi-room?room=…`

### Frontend
- **NEW** `frontend/app/tools/expert-net/manage/[expert_id].tsx` — 4-tab expert dashboard
- **NEW** `frontend/app/tools/expert-net/recommend.tsx` — recommend a Solution Store item
- **NEW** `frontend/app/tools/jitsi-room.tsx` — public Jitsi WebView (auth-free)
- `frontend/app/p/[slug].tsx` — rebuilt with 4-tab branded portal
- `frontend/app/tools/expert-net/index.tsx` — Manage tab now has "Open dashboard" CTA per expert
- `frontend/app/tools/solution-detail.tsx` — duplicate-declaration fix
- `frontend/src/utils/api.ts` + `frontend/src/store/authStore.ts` — removed all `withCredentials: true` (was breaking cross-origin auth in test harness; Bearer token in Authorization header is the actual auth path)

### Tests
- Backend regression by `deep_testing_backend_v2`: 42/43 + 17/17 + 38/38 = 97/98 PASS
- Frontend UAT by `expo_frontend_testing_agent`: 8/8 ExpertNet + Public Portal full flow PASS

### Memory
- This file (`memory/carry_forward.md`)
- `memory/test_credentials.md` — unchanged

---

## 🧪 Quick health checks for the new fork agent

```bash
sudo supervisorctl status
curl -s http://localhost:8001/api/health
python /app/backend_test_regression.py            # ~26-28/28
python /app/tests/test_solution_matrix_orgtype.py # 31/31
```

---

## 🎯 Recommended first-hour plan for the next fork agent

1. Run the health checks above. Log results.
2. Read `test_result.md` from line 7203 onwards (ExpertNet v3.9.1 manage dashboard section).
3. Ask user which P1 item to tackle first — A is LLM-blocked; B/C/D/E are all unblocked and independent.
4. **Hot recommendation**: tackle D (Voice Browsing global expansion) since it's the only major user-visible epic still partially scoped (currently restricted to PRR 10-step flow). Backend is voice-agnostic; this is mostly frontend work.
5. DO NOT touch any `.env` URL / port values — they are fork-specific.
6. DO NOT re-introduce `withCredentials: true` to api.ts or authStore.ts. Bearer token via Authorization header is intentional.

---

## ⚠️ Known minor issues (NOT blockers)

- ESLint can't parse TypeScript type aliases in `.tsx` files (parser config gap, NOT a real bug — Metro bundles fine).
- `passlib bcrypt __about__` warning at startup is a benign passlib version mismatch; auth works correctly.
- Screenshot tool's headless browser may show "Expert not found" when navigating directly to /tools/expert-net/manage/{id} — that's because the screenshot tool doesn't set the localStorage session_token. Inject it via `add_init_script` before navigation in tests.

---

## ✅ Just completed in this fork (do NOT redo)
- **OrgSurveys v3.9.0** (Phase 3-B white-label sub-portals) — 8 endpoints under `/api/p/{slug}/surveys/*`
  - Full CRUD by org admins, public read + submit, anon-or-auth submission
  - 7 question types: short_text/long_text/single_select/multi_select/rating_5/yes_no/number
  - Server-side required-field validation, public aggregates with bucket counts + averages
  - Backend regression: **42/43 PASS** (yes_no bucket label bug fixed post-test)
  - Module: `backend/routes/org_surveys.py`
  - Seeded sample: "Annual Skills Survey 2026" on slug `coimbatore-skills-foundation-5b9c19`
- **RN Public Org Portal** at `frontend/app/p/[slug].tsx` — 4-tab branded page (About / Surveys / Reviews / Feedback) with primary_color theming pulled from org doc
- **ExpertNet Jitsi-Room v3.9.0** — fixed 3 ExpertNet endpoints to return `video_url=/tools/jitsi-room?room={sid}` instead of broken collab-call URL. New screen `frontend/app/tools/jitsi-room.tsx` mounts public meet.jit.si via WebView (native) / iframe (web). Auth-free.
- **Pre-existing bug fix**: removed duplicate `myPending` declaration in `frontend/app/tools/solution-detail.tsx` (was blocking entire metro bundle).

---

## 🔴 P0 — External blockers (cannot code around)

| # | Item | Blocker | What unblocks it |
|---|------|---------|------------------|
| 1 | DigiLocker eKYC (API Setu) | Awaiting user's API Setu approval + keys | User injects `APISETU_CLIENT_ID/_SECRET/_ENV` into `backend/.env` |
| 2 | Exotel SMS OTP | Awaiting user's DLT template approval from TRAI | User adds `EXOTEL_*` keys to `.env` |
| 3 | LLM Budget Reset re-test | Emergent LLM key budget capped | Budget resets naturally — re-run the curl in `/app/memory/pending_verifications.md` |

---

## 🟠 P1 — Ready to ship (no blockers)

### A. Public Pulse Phase 3 — AI Intelligence Layer  *(blocked on LLM budget)*
- [ ] AI-summarised feedback clusters
- [ ] Smart recommendations linking score band → schemes
- [ ] Auto-drafted Org responses
- [ ] Trend lines / YoY comparisons on the 5 dashboards

### B. White-labelled Org Sub-Portals — *partially shipped this fork*
- [x] Per-org branded `/p/{slug}` page in Expo (4 tabs, themed)
- [x] **Org-scoped surveys** (multi-question forms, public submit, aggregates)
- [x] HTML embed widget (already existed before)
- [ ] **Org-admin UI to manage their own surveys** (currently admin-only via API; no Expo screen yet)
- [ ] Social-share OG meta tags for `/api/embed/{slug}`
- [ ] Per-org CSS overrides beyond primary_color (logo, fonts, hero image)

### C. Solution Matrix OrgType — polish items
- [ ] PDF export renderer for the 84-cell layout
- [ ] AI CLD hook for `solution_matrix` module_type *(blocked on LLM budget)*
- [ ] Per-OrgType ACM feature gating
- [ ] 4 starter templates (Individual / Org / Govt / Nature)

### D. Voice Browsing — Epic
- [ ] Global floating voice command bubble + route-aware parser
- [ ] Voice input in Solution Matrix / Public Pulse / Goal Setter / Conflict Breaker
- [ ] TTS readout across all tools (extend `expo-speech` beyond AI Assistant)
- [ ] Multi-language voice (9 Solutions Store languages)
- [ ] Continuous voice mode + voice undo/redo

### E. ExpertNet — Polish
- [ ] **Frontend UAT** of the 5 ExpertNet tabs end-to-end (Discover / Bookings / Recommendations / Webinars / Be-an-Expert) — UI was scaffolded in prior fork, video-call routing fixed this fork; needs full visual UAT
- [ ] Calendar slot picker (calendar grid view) — currently chip list only
- [ ] Expert ratings & review surface (separate from ReviewNet which is solutions-only)
- [ ] Push notifications when booking confirmed / call starting / webinar countdown

### F. Minor Polish
- [ ] Auto-reseed ACM for `pp_org_portal` at boot
- [ ] Fix benign `backend_test_regression.py` Solutions Store countries/languages assertion
- [ ] Verify `core/file_storage.py` S3 + GCS code paths once any cloud key is provided
- [ ] 3 Public Pulse API contract callsites flagged previously (consent/feedback 422; score/submit 404)

---

## 🟡 P2 — Physical device E2E tests (require real phone/camera/SIM)

| # | Test | Why physical device |
|---|------|---------------------|
| 4 | Face Authentication / MediaPipe presence tracking | Real camera stream |
| 5 | Razorpay payment end-to-end | Real UPI/card |
| 6 | WhatsApp OTP (UltraMsg) end-to-end | Real phone receives SMS |
| 7 | DigiLocker camera scan (when unblocked) | Real document |
| 8 | Push notifications via Expo Push API | Real device token |

---

## 📁 Key files added/changed in this fork

### Backend
- **NEW** `backend/routes/org_surveys.py` — 8 endpoints under `/api/p/{slug}/surveys/*`
- `backend/server.py` — registers `org_surveys_router`
- `backend/routes/expert_net.py` — `video_url` now points to `/tools/jitsi-room?room=…`

### Frontend
- **NEW** `frontend/app/tools/jitsi-room.tsx` — public Jitsi WebView screen (auth-free)
- `frontend/app/p/[slug].tsx` — rebuilt with 4-tab branded portal (About/Surveys/Reviews/Feedback)
- `frontend/app/tools/expert-net/index.tsx` — webinar non-host fallback now uses jitsi-room URL
- `frontend/app/tools/solution-detail.tsx` — removed duplicate `myPending` declaration (bundle fix)

### Tests
- Backend regression executed by `deep_testing_backend_v2`: **42/43 PASS** (1 minor yes_no bucket-label bug fixed post-test).

### Memory
- This file (`memory/carry_forward.md`)
- `memory/test_credentials.md` — unchanged (credentials still valid)

---

## 🧪 Quick health checks for the new fork agent (run at session start)

```bash
sudo supervisorctl status
curl -s http://localhost:8001/api/health
# Expect 200 + {"status":"ok"} on both
python /app/backend_test_regression.py   # 26-28/28
python /app/tests/test_solution_matrix_orgtype.py   # 31/31
```

---

## 🎯 Recommended first-hour plan for the next fork agent

1. Run the health checks above. Log results.
2. Read `test_result.md` from line 6973 onwards (OrgSurveys + ExpertNet Jitsi-Room sections).
3. Ask user which P1 item to tackle first — they are all independent and unblocked except A (LLM-blocked).
4. If LLM budget has reset: knock out the 4 AI verification curls in `pending_verifications.md` first (15 min, unblocks Phase 3-A).
5. **Hot recommendation**: tackle E (ExpertNet frontend UAT) since it's the only thing standing between the user and a fully shippable ExpertNet module. The video-call fix this fork was the last backend gap.
6. DO NOT touch any `.env` URL / port values — they are fork-specific.

---

## ⚠️ Known minor issues (NOT blockers)

- ESLint can't parse TypeScript type aliases in `.tsx` files (parser config gap, NOT a real bug — Metro bundles fine).
- `passlib bcrypt __about__` warning at startup is a benign passlib version mismatch; auth works correctly.
- Screenshot tool's headless browser cannot reach external preview URLs (sandboxing artifact). External API access works fine for the actual app.

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
