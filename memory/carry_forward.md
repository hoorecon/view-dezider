# Carry-forward — checkpoint 2026-05-19 (post-EC2 prod launch)

> **Last session ended:** Backend FULLY LIVE in production on AWS EC2 + MongoDB Atlas + HTTPS.
> **Next decision point:** Where to host the frontend (Cloudflare Pages vs same EC2).
> **Production health:** ✅ Backend operational at `https://api.jelcos.ai`.

---

## 🟢 Production status snapshot (2026-05-19 02:48 IST)

| Layer | Status | Details |
|---|---|---|
| **AWS EC2** | ✅ Live | `t4g.medium` ARM, IP `3.111.141.66`, Ubuntu 24.04 |
| **NGINX reverse proxy** | ✅ Live | `:443 → :8001` for `api.jelcos.ai` |
| **Let's Encrypt TLS** | ✅ Live | Cert valid until 2026-08-16, auto-renewal scheduled |
| **DNS** | ✅ Live (mostly) | `api.jelcos.ai → 3.111.141.66` on GoDaddy. Some ISPs (incl. Google `8.8.8.8`) still propagating |
| **Docker Compose** | ✅ Live | `/opt/dezider/deploy/docker-compose.yml` (api only, no local mongo) |
| **MongoDB Atlas** | ✅ Connected | Cluster0 (ap-south-1, free tier), `dezider` DB |
| **Admin user** | ✅ Created | `veales.vedic.decisions@gmail.com` / `Jelcos@Admin2026` / role=`admin` |
| **ACM seed** | ✅ Seeded | 32 modules, 89 features, seed_version `2026-05-04-04` |
| **Hardening** | ✅ Active | env=prod, HSTS=true, sec_headers=true, gzip, metrics, body_cap=10MB |
| **GitHub branch** | `emergent-v3` | Latest deploy code lives here |

### Quick re-verify commands (run on EC2)
```bash
curl -s https://api.jelcos.ai/api/health
# Expect: {"status":"ok","service":"View Dezider API"}

TOKEN=$(curl -s -X POST https://api.jelcos.ai/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"veales.vedic.decisions@gmail.com","password":"Jelcos@Admin2026"}' \
  | python3 -c "import sys,json;d=json.load(sys.stdin);print(d.get('access_token') or d.get('session_token') or '')")
curl -s https://api.jelcos.ai/api/auth/me -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
# Expect: role=admin
```

---

## 🛠️ What was fixed in this session (2026-05-19)

1. **DNS propagation for `api.jelcos.ai`** — GoDaddy A record points to EC2 IP; Cloudflare resolver picked it up first (used `dig +short @1.1.1.1`).
2. **Let's Encrypt Certbot** — succeeded once DNS resolved publicly; NGINX reverse proxy now serves HTTPS.
3. **`MONGO_URL` typo** — user had `NGO_URL=...` instead of `MONGO_URL=...` in `backend/.env`. Fixed.
4. **Docker-compose pointing to local mongo, not Atlas** — `/opt/dezider/deploy/docker-compose.yml` had hardcoded `MONGO_URL: "mongodb://mongo:27017/dezider"` in the `api.environment` block which **overrode** the `.env`. Rewrote the file:
   - Removed `mongo:` service (Atlas-only)
   - Removed hardcoded `MONGO_URL` / `DB_NAME` from `environment:` block
   - Added `env_file: ../backend/.env`
   - Changed `HSTS_ENABLED: "true"` and `DEZIDER_ENV: "prod"`
5. **Bootstrapped Atlas admin** — registered via `/api/auth/register`, then promoted role=admin directly via Mongo update (no admin-promotion endpoint exists).
6. **🐛 ACM seed bug (codebase-wide, pre-existing)** — `backend/core/db_indices.py` declared a UNIQUE index on `("user_type", 1)` for `acm_user_types` and `("plan_id", 1)` for `acm_subscription_plans`. But the seed data in `backend/data/acm_seed_data.py` only populates an `id` field. Result: every seed insert had `user_type: null` → 2nd insert hit duplicate-key on null. **Fix applied locally in `/app/backend/core/db_indices.py`** (changed both indices to `("id", 1)`). **NOT YET PUSHED to GitHub `emergent-v3`** — push from Emergent UI when convenient. The fix was verified end-to-end on prod (after dropping stale `acm_*` collections so the old indices got wiped).

### Files modified locally this session (push pending)
- `/app/backend/core/db_indices.py` — index keys for `acm_user_types` & `acm_subscription_plans` changed from `user_type`/`plan_id` to `id`

### Files modified directly on EC2 this session
- `/opt/dezider/backend/.env` — fixed `NGO_URL` → `MONGO_URL` typo
- `/opt/dezider/deploy/docker-compose.yml` — full rewrite (see §🛠️ above)
- Atlas: `dezider.users` collection — `role` of admin user manually set to `"admin"`

---

## ⏭️ NEXT IMMEDIATE TASK (when user resumes)

### Decision pending: Where to host frontend?

User explicitly asked tonight to **PAUSE** and decide later between:

- **(a) Cloudflare Pages** → `app.jelcos.ai`
  - Auto-build on git push to `emergent-v3`
  - Global CDN, free DDoS protection
  - Setup ~20–30 min
- **(b) Same EC2 + NGINX serves `expo export -p web` static `dist/`**
  - 10–15 min setup, all on one box
  - Manual deploy script needed
  - Adds CPU/RAM/bandwidth load to the `t4g.medium`

Agent's recommendation if pressed: **(a) Cloudflare Pages** marginally — to keep API EC2 lean during web bundle builds and gain free DDoS/global CDN. But (b) is perfectly viable for India-only traffic.

**Whichever is chosen, the steps are:**
1. Build: `cd /app/frontend && yarn install && npx expo export -p web` (outputs `dist/`)
2. Set `EXPO_PUBLIC_BACKEND_URL=https://api.jelcos.ai` at build time
3. Configure SPA fallback (all routes → `index.html`)
4. Add DNS for `app.jelcos.ai`
5. Smoke test: register → login → tools list → open Pros&Cons wizard

---

## 🟠 P1 — Open backlog (not blockers, in priority order)

### Code fix to push to GitHub `emergent-v3`
- [ ] `backend/core/db_indices.py` — ACM index keys fix (see §🛠️ #6 above). Push from Emergent UI → user pulls on EC2 → next `docker compose up -d --build` will have correct indices. Until then, prod has the stale wrong index alongside the correct one; harmless since `force=true` seed works.

### PRR Enhancement #4 + #5 — UI completion
- Backend models support deadline + impact horizon configurable units + linking + single-option bypass.
- `frontend/app/prr/new.tsx` still needs:
  - Chip-based unit picker (days/weeks/months/years, default 1 week)
  - Single-option bypass link (when decision-link has only one option, auto-populate factors and skip)

### 8-step Pros & Cons / SWOT wizard — Phase 2
- AI guidance for de-dup / group (Step #4) — RESERVED for WOWO subscription tier. Hook point exists; just no UI yet.
- Sub-factor level rating (Step #5) — RESERVED. Sub-factor display only for now.
- Step #7 dual rankings (high-to-low + low-to-high columns) — RESERVED.

### Voice Browsing Epic Expansion (carried over)
- Currently limited to PRR 10-step flow (`VoiceStepInput.tsx`, `stepVoiceParser.ts`).
- Expand to global navigation: Solution Matrix, Public Pulse, Goal Setter, Tools list.
- Multi-language voice support (match Solutions Store's 9 languages).

### Public Pulse Phase 3 (carried over, blocked on LLM budget)
- AI smart recommendations, AI-summarised feedback clusters, auto-drafted Org responses.
- White-labelled per-Org public sub-portals (slug-based theming, branded surveys).

### Solution Matrix Polish (carried over)
- PDF Export renderer for the 84-cell nested matrices.
- ACM feature-gating for Govt/Org specific columns.
- Starter templates / seed content for the 4 OrgTypes.

### Web UI polish
- Apply `WebFrame`/`AdminShell` tokens fully to Home, Login, Profile (desktop).
- Remove duplicate mobile headers inside `/admin/*` inner pages.

---

## 🔴 P0 — External blockers (unchanged)

| Item | Waiting on | Status |
|---|---|---|
| DigiLocker eKYC keys (API Setu) | User to obtain & supply | Mocked / blocked |
| Exotel SMS OTP | DLT template approval + keys | Mocked / blocked |
| Razorpay live keys | User to enable + supply | Mocked / blocked |
| Emergent LLM Key budget | System budget reset (Anthropic/OpenAI/Gemini cap) | AI endpoints return graceful 503 |
| Face Auth (MediaPipe) | ARM aarch64 compat — `mediapipe` disabled in `requirements.txt`, returns 503 | Future P2 |

---

## 🗂️ Key files / locations (cheatsheet for next agent)

### On EC2 (`ubuntu@3.111.141.66`)
- Repo: `/opt/dezider/` (git branch `emergent-v3`)
- Compose: `/opt/dezider/deploy/docker-compose.yml`
- Backend env: `/opt/dezider/backend/.env` (contains real Atlas URI; **never modify carelessly**)
- Backend container name: `deploy-api-1`
- NGINX site config: `/etc/nginx/sites-enabled/api`
- TLS cert: `/etc/letsencrypt/live/api.jelcos.ai/`

### In Emergent workspace (`/app`)
- Decision framework backend: `backend/models/decision_framework_models.py`, `backend/routes/pros_cons.py`, `backend/routes/swot.py`
- Decision framework frontend: `frontend/app/tools/pros-cons-wizard.tsx`
- DB indices (with the local fix pending push): `backend/core/db_indices.py`
- ACM seed data: `backend/data/acm_seed_data.py`
- ACM engine: `backend/core/acm_engine.py`

### Memory / docs
- This file: `/app/memory/carry_forward.md`
- Test credentials: `/app/memory/test_credentials.md` (prod admin added below; dev creds untouched)
- Pending verifications: `/app/memory/pending_verifications.md`
- All admin docs (PRD, SRS, UAT, API_REFERENCE, etc.): `/app/docs/` — last regenerated v3.15.0

---

## 🔑 Production credentials reference

| Account | Email | Password | Role |
|---|---|---|---|
| Prod superadmin | `veales.vedic.decisions@gmail.com` | `Jelcos@Admin2026` | `admin` |

⚠️ No SMTP gateway is wired on prod yet — `/api/auth/forgot-password` returns OTP in the JSON response (not via email). Use this for resets via shell.

---

## 🚨 Important notes / gotchas for next agent

1. **NEVER assume `docker compose` works from `/opt/dezider/`** — the compose file is in `/opt/dezider/deploy/`. Always `cd /opt/dezider/deploy` first.
2. **NEVER add a `mongo:` service back to compose** — Atlas is the production database. Local mongo would silently re-divert writes if env loading regresses.
3. **`MONGO_URL` MUST be loaded via `env_file: ../backend/.env`** — do NOT hardcode it in the `environment:` block (the previous bug).
4. **The ACM seed code-fix is local-only until next GitHub push** — pulling on EC2 today won't help. Either:
   - Push from Emergent UI → user pulls + rebuilds, OR
   - The current prod state is already seeded correctly (workaround was the collection drop). It's fine to leave until next rebuild.
5. **DNS for non-Cloudflare resolvers may still NXDOMAIN for `api.jelcos.ai`** — propagation continues for ~24h from 2026-05-19 ~01:23 IST. User's PC may need to switch DNS to `1.1.1.1` if browsing directly.
6. **Old user_id `user_051a0a744843`** was registered against the WRONG (local) Mongo and is now orphaned. The active prod user is `user_920f13fca2ca`.
7. **STRICT TESTING POLICY in effect** — do NOT invoke `deep_testing_backend_v2` or `expo_frontend_testing_agent` without explicit user permission. Use manual `curl` and screenshots.

---

## 📝 Last 3 user messages (for tone/context)

1. (User) "Unable to decide for Frontend - to be in Cloudflare or EC2? why not EC2? why Cloudflare?" → Agent gave side-by-side comparison + honest recommendation.
2. (User) "c + create a checkpoint memo in /app/memory/carry_forward.md so next session picks up exactly where we are" → THIS file is the response.
3. User has expressed frustration earlier about credit consumption during ACM debug; agent acknowledged. Future sessions should prioritise tight, decisive fixes over exploratory commands.

---

## ✅ Suggested first 3 actions for next session

1. Re-verify backend prod health: `curl https://api.jelcos.ai/api/health` + login + `/api/auth/me`.
2. Ask user: **Frontend hosting — Cloudflare Pages or same EC2?** (decision pending from this session).
3. Push the `db_indices.py` ACM fix from Emergent UI to GitHub `emergent-v3` so EC2 rebuilds will be clean.
