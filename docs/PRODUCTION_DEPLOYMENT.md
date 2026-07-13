# Jelcos Production Deployment — Complete Runbook
**Version:** 1.1 (2026-07-13)

> **v1.1 (2026-07-13):** Deploy ritual = bump `README.md BUILD_VERSION` → **Save to GitHub** (repo `hoorecon/view-dezider` @ `emergent-v3`) → Cloudflare Pages auto-builds the FRONTEND + on EC2 run `EXPECT_BUILD=<build> ./deploy/sync.sh emergent-v3` for the BACKEND. `sync.sh` aborts if `origin/emergent-v3` build ≠ `EXPECT_BUILD` (guards stale/dropped pushes). Recovery from a wrong push: re-push correct workspace via Save-to-GitHub, then on EC2 `git fetch && git reset --hard origin/emergent-v3` (env files are gitignored — verify `backend/.env` after). **Prod secrets to set:** real `STRIPE_API_KEY` (+`STRIPE_WEBHOOK_SECRET`), `SECRET_KEY`, `CORS_ORIGINS`.
**Audience:** Junior engineers, ops handover, future agent sessions
**Live URLs:** `https://www.jelcos.ai` (frontend) + `https://api.jelcos.ai` (backend)

---

## 1. Architecture at a Glance

```
                        Internet (Users)
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
www.jelcos.ai          jelcos-app.pages.dev      api.jelcos.ai
   (custom)               (preview/test)         (custom)
        │                     │                     │
        └─────────┬───────────┘                     │
                  ▼                                  ▼
         ┌──────────────────┐              ┌─────────────────┐
         │ Cloudflare Pages │              │  NGINX :443     │
         │ (global CDN)     │              │  /etc/nginx     │
         │  ↓ static dist/  │              │  + Let's Encrypt│
         └──────────────────┘              └─────────┬───────┘
                  │                                  ▼
                  │                          ┌─────────────────┐
                  │                          │ Docker: api-1   │
                  │                          │ FastAPI :8001   │
                  │                          │ 4 uvicorn wkrs  │
                  │                          └─────────┬───────┘
                  │                                    ▼
                  │                          ┌─────────────────┐
                  └─── HTTPS API calls ─────►│  MongoDB Atlas  │
                                             │  (free tier,    │
                                             │   ap-south-1)   │
                                             └─────────────────┘

Source of truth: GitHub `hoorecon/view-dezider` branch `emergent-v3`
```

---

## 2. Tech Stack Summary

### Frontend (Cloudflare Pages)
| Layer | Tech | Version |
|---|---|---|
| Framework | Expo SDK | 54 |
| Routing | Expo Router (file-based) | v6 |
| Language | TypeScript / React 19 | — |
| State | Zustand | — |
| Forms | React Hook Form | — |
| Animations | react-native-reanimated | — |
| Build target | Web (Metro bundler → static) | `expo export -p web` |
| Hosting | Cloudflare Pages (free tier, global CDN) | — |
| Auto-deploy | On every `git push emergent-v3` | ~3-5 min |

### Backend (AWS EC2)
| Layer | Tech | Version |
|---|---|---|
| Framework | FastAPI | latest |
| Async DB driver | Motor (async MongoDB) | — |
| Models | Pydantic v2 | — |
| Server | Uvicorn + uvloop + httptools (4 workers) | — |
| Reverse proxy | NGINX | 1.24+ |
| TLS | Let's Encrypt (Certbot, auto-renew 60 days) | — |
| Runtime | Docker Compose | v2 |
| Host | AWS EC2 `t4g.medium` ARM64 | Ubuntu 24.04 |
| Region | `ap-south-1` (Mumbai) | — |
| Rate limits | slowapi (120/min default, 10/min auth & AI) | — |
| Security | HSTS, security headers, gzip, body cap 10 MB | — |
| Metrics | `/api/metrics/json` (admin-only) | — |

### Database
| Layer | Tech |
|---|---|
| Provider | MongoDB Atlas (free tier, M0 cluster) |
| Cluster | `cluster0.c39ovvo.mongodb.net` |
| DB name | `dezider` |
| Region | `ap-south-1` (Mumbai) |
| Indices | Auto-created on backend boot via `core/db_indices.py` (211 indices) |

### Source Control & CI/CD
| Layer | Tech |
|---|---|
| Repo | `https://github.com/hoorecon/view-dezider` |
| Production branch | `emergent-v3` |
| Code authoring | Emergent platform → "Save to GitHub" button |
| Frontend CI/CD | Cloudflare Pages (auto on push) |
| Backend CI/CD | Manual `git pull` + `docker compose up -d --build` (see §5) |
| DNS | Cloudflare (Domain registered at GoDaddy, nameservers point to CF) |

### 3rd-Party Integrations
| Service | Purpose | Status |
|---|---|---|
| Emergent LLM Key | AI Chat / CLD / Recommendations (OpenAI/Anthropic/Gemini) | Budget-capped → graceful 503 |
| DuckDuckGo Search | Public web search | No key needed |
| Google Calendar API | Calendar sync | User key required (not configured) |
| UltraMsg (WhatsApp OTP) | WhatsApp 2FA | User key required (not configured) |
| DigiLocker / API Setu | eKYC | User key required (not configured) |
| Exotel | SMS OTP | User key + DLT template required (not configured) |
| Razorpay | Payments | User key required (not configured) |

---

## 3. All Production URLs & Endpoints

### 3.1 Public URLs (no auth)
| URL | Purpose |
|---|---|
| `https://www.jelcos.ai` | Frontend home page |
| `https://jelcos-app.pages.dev` | Cloudflare Pages preview (same content) |
| `https://api.jelcos.ai/api/health` | Liveness probe `{"status":"ok"}` |
| `https://api.jelcos.ai/api/health/live` | Bare liveness |
| `https://api.jelcos.ai/api/health/ready` | DB readiness check |
| `https://api.jelcos.ai/api/feature-flags/public` | Public feature flags |
| `https://api.jelcos.ai/api/branding/current` | Public branding theme |
| `https://api.jelcos.ai/api/p/{slug}` | Public org sub-portal |

### 3.2 Auth Endpoints
| Method | Path | Purpose |
|---|---|---|
| POST | `/api/auth/register` | Create new user `{email,password,name}` |
| POST | `/api/auth/login` | Issue session token `{email,password}` |
| POST | `/api/auth/logout` | Invalidate current session |
| POST | `/api/auth/forgot-password` | Generate OTP `{email}` (returns OTP in JSON since no SMTP) |
| POST | `/api/auth/reset-password` | `{email,otp,new_password}` |
| POST | `/api/auth/set-password` | Set password for Google users (auth required) |
| POST | `/api/auth/google/session` | Google OAuth sign-in |
| POST | `/api/auth/push-token` | Register Expo push token |
| GET  | `/api/auth/me` | Current user profile |

### 3.3 Admin-Only Endpoints (require `role: admin`)
| Method | Path | Purpose |
|---|---|---|
| POST | `/api/acm/seed?force=true` | Re-seed Admin Capability Matrix |
| GET  | `/api/acm/features` | List all 89 ACM features |
| GET  | `/api/acm/modules` | List all 32 modules |
| GET  | `/api/acm/user-types` | List 7 user types |
| GET  | `/api/admin-docs/INDEX` | Documentation index |
| GET  | `/api/admin-docs/PRD` | Product Requirements |
| GET  | `/api/admin-docs/SRS` | System Requirements Spec |
| GET  | `/api/admin-docs/UAT` | UAT Test Cases |
| GET  | `/api/admin-docs/REGRESSION` | Regression Test Results |
| GET  | `/api/admin-docs/API_REFERENCE` | API Reference (this file's neighbor) |
| GET  | `/api/admin-docs/DEPLOYMENT` | Deployment Guide |
| GET  | `/api/admin-docs/PRODUCTION_DEPLOYMENT` | This file |
| GET  | `/api/metrics/json` | Server metrics (requests/sec, latency, etc.) |
| GET  | `/api/dpdp/audit-log` | DPDP compliance audit log |

### 3.4 Decision Tools (User Endpoints, auth required)
| Module | Base Path | Key Endpoints |
|---|---|---|
| PRR (10-step) | `/api/prr` | CRUD + step navigation |
| Pros & Cons | `/api/pros-cons` | Classic CRUD + 18 framework endpoints (factors, options, assessments, knock-outs) |
| SWOT | `/api/swot` | Mirror of Pros & Cons |
| Solution Matrix | `/api/tools/solution-matrix` | 4 OrgTypes × 3 layers × 7 cells (84 cells) |
| Decision Linking | `/api/decision-links` | Link decisions, find sources |
| Public Pulse | `/api/public-pulse` | Surveys, feedback, analytics |
| Goal Setter | `/api/goal-setter` | Goal CRUD |
| Time / TEPFI | `/api/time-dezider` | Time blocks, TEPFI entries |

### 3.5 Tools Catalog (Frontend Routes)
| URL | Page |
|---|---|
| `https://www.jelcos.ai/` | Home |
| `https://www.jelcos.ai/login` | Login |
| `https://www.jelcos.ai/profile` | User profile |
| `https://www.jelcos.ai/admin` | Admin dashboard |
| `https://www.jelcos.ai/prr/new` | New PRR decision |
| `https://www.jelcos.ai/prr/[id]` | PRR detail |
| `https://www.jelcos.ai/tools/pros-cons` | Classic Pros & Cons list |
| `https://www.jelcos.ai/tools/pros-cons-wizard` | 8-step framework wizard |
| `https://www.jelcos.ai/tools/swot` | SWOT list |
| `https://www.jelcos.ai/tools/solution-matrix` | Solution Matrix |
| `https://www.jelcos.ai/tools/public-pulse` | Public Pulse |
| `https://www.jelcos.ai/p/[slug]` | Public org portal |

---

## 4. Test Credentials & Smoke Test Data

### 4.1 Production Admin Account
```
Email:    veales.vedic.decisions@gmail.com
Password: Jelcos@Admin2026
Role:     admin
user_id:  user_920f13fca2ca
```
⚠️ **Password reset path:** SMTP not configured. Use:
```bash
# Step 1 - request OTP (returned in JSON, not email)
curl -X POST https://api.jelcos.ai/api/auth/forgot-password \
  -H "Content-Type: application/json" \
  -d '{"email":"veales.vedic.decisions@gmail.com"}'

# Step 2 - reset
curl -X POST https://api.jelcos.ai/api/auth/reset-password \
  -H "Content-Type: application/json" \
  -d '{"email":"...", "otp":"123456", "new_password":"NewPass@2026"}'
```

### 4.2 End-to-End Smoke Test Sequence

```bash
# 0. Health
curl -s https://api.jelcos.ai/api/health
# Expect: {"status":"ok","service":"View Dezider API"}

# 1. Register a test user (idempotent — will say "already registered" on retry)
curl -s -X POST https://api.jelcos.ai/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"smoketest@example.com","password":"Smoke@Test2026","name":"Smoke Tester"}'

# 2. Login
TOKEN=$(curl -s -X POST https://api.jelcos.ai/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"smoketest@example.com","password":"Smoke@Test2026"}' \
  | python3 -c "import sys,json;d=json.load(sys.stdin);print(d.get('session_token') or d.get('access_token'))")

# 3. Verify auth
curl -s https://api.jelcos.ai/api/auth/me -H "Authorization: Bearer $TOKEN"

# 4. List tools
curl -s https://api.jelcos.ai/api/pros-cons -H "Authorization: Bearer $TOKEN"

# 5. Create a Pros & Cons entry
curl -s -X POST https://api.jelcos.ai/api/pros-cons \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title":"Smoke test decision","description":"Test"}'
```

### 4.3 UI Smoke Test (manual, 2 minutes)
1. Open `https://www.jelcos.ai` in incognito.
2. Register → login → land on Home.
3. Navigate to Tools → Pros & Cons → "Open 8-Step Framework".
4. Add 1 factor → 2 options → 1 pro + 1 con per option → promote → save.
5. Open DevTools → Network tab → confirm all calls go to `https://api.jelcos.ai/api/*`.

---

## 5. Continuous Deployment (Day-2 Operations)

### How to Push Future Bug Fixes & Features

```
┌──────────────────────────────────────────────────────────────────┐
│                       YOUR DAY-TO-DAY LOOP                       │
└──────────────────────────────────────────────────────────────────┘

1. EDIT code in Emergent platform (chat with E1 agent)
            │
            ▼
2. Click "Save to GitHub" button (top-right)
   → Pushes to branch `emergent-v3`
            │
            ├─────────────────┬─────────────────┐
            ▼                 ▼                 ▼
       FRONTEND          BACKEND            DATABASE
   (Cloudflare Pages) (AWS EC2 Docker)   (MongoDB Atlas)
            │                 │                 │
            ▼                 ▼                 ▼
  AUTO-DETECTS push     MANUAL pull        AUTO-MIGRATES
  → build 3-5 min       (commands below)   on backend boot
  → live on             → 1-2 min          (indices created
   www.jelcos.ai                            in db_indices.py)
```

### 5.1 Frontend (Cloudflare Pages) — Automatic
Every push to `emergent-v3` triggers an auto-build. Watch progress at:
```
https://dash.cloudflare.com → Workers & Pages → jelcos-app → Deployments
```
Rollback: click any previous deployment → "Rollback to this version". One click.

### 5.2 Backend (AWS EC2) — Manual SSH

```bash
# SSH in
ssh ubuntu@3.111.141.66

# Pull latest code
cd /opt/dezider
git checkout emergent-v3
git pull origin emergent-v3

# Rebuild & restart only what changed (zero-downtime-ish: ~10s gap)
cd deploy
docker compose up -d --build api

# Watch boot logs
docker compose logs --tail=40 api

# Verify health
curl -s https://api.jelcos.ai/api/health
```

**Rollback (if a deploy breaks):**
```bash
cd /opt/dezider
git log --oneline -5
git reset --hard <previous-commit-sha>
cd deploy && docker compose up -d --build api
```

### 5.3 Database (MongoDB Atlas) — Auto-Migrating
- Schema changes are driven by `backend/core/db_indices.py` (declarative index list).
- On every backend boot, missing indices are auto-created, existing ones are kept.
- ACM data is auto-seeded on boot if missing OR version-bumped; force re-seed: `POST /api/acm/seed?force=true` (admin only).
- **No manual migrations needed in normal flow.**

### 5.4 Suggested Git Workflow for a Junior

```bash
# Always work from a clean state
cd /opt/dezider
git status                              # ensure clean
git pull origin emergent-v3             # always start fresh

# (Make changes via Emergent → it pushes to emergent-v3)

# Then on EC2:
git pull origin emergent-v3
cd deploy && docker compose up -d --build api
docker compose logs --tail=50 api       # smoke check
curl -s https://api.jelcos.ai/api/health
```

### 5.5 Monitoring & Logs

```bash
# Live tail backend logs
docker logs -f deploy-api-1

# Last 100 lines
docker logs --tail=100 deploy-api-1

# NGINX access log
sudo tail -f /var/log/nginx/access.log

# NGINX error log
sudo tail -f /var/log/nginx/error.log

# Server metrics
curl -s -H "Authorization: Bearer $TOKEN" \
  https://api.jelcos.ai/api/metrics/json
```

---

## 6. Lessons Learned (Pitfalls We Hit & How to Avoid Them)

### Pitfall 1 — `.env` typo `NGO_URL=` instead of `MONGO_URL=`
**Symptom:** Backend "worked" but data went to local Mongo container, not Atlas.
**Fix:** `grep -E "^MONGO_URL=" backend/.env` should return exactly one line.
**Avoidance:** Always verify env vars with `docker exec deploy-api-1 env | grep MONGO` after any `.env` change.

### Pitfall 2 — Hardcoded `MONGO_URL` in `docker-compose.yml` overrode `.env`
**Symptom:** Same as Pitfall 1.
**Fix:** Use `env_file: ../backend/.env` only; never put secrets in `environment:` block.
**File reference:** `/opt/dezider/deploy/docker-compose.yml`.

### Pitfall 3 — ACM seed failed with `E11000 duplicate key: user_type=null`
**Symptom:** Boot log showed `ACM boot seed failed`.
**Root cause:** `db_indices.py` defined unique index on `user_type`/`plan_id` but `acm_seed_data.py` populates `id` field. Schema mismatch.
**Fix:** `db_indices.py` indices now use `id` (committed). For any historical Atlas DBs still carrying the bad index, drop the collection once: `db.acm_user_types.drop()` then restart api.

### Pitfall 4 — DNS propagation delays for `.ai` TLD
**Symptom:** Certbot/curl/browser fail with NXDOMAIN even though config is correct.
**Workaround:** Test with `dig +short @1.1.1.1 <hostname>` (Cloudflare resolver picks up changes fastest). Set Windows DNS to `1.1.1.1` for immediate testing.
**Timeline:** `.ai` TLD can take up to 24 hours; usually 30 min – 4 hours.

### Pitfall 5 — Yarn not pre-installed on Cloudflare build env
**Symptom:** `No preset version installed for command yarn`.
**Fix:** Use `npm install --legacy-peer-deps` in the Pages build command.

### Pitfall 6 — Cloudflare new UI hides Pages under "Compute"
**Symptom:** Can't find Pages create flow in new dashboard.
**Fix:** Direct URL: `https://dash.cloudflare.com/?to=/:account/pages/new/provider/github`.
**Avoid Workers Build flow** (it has "Deploy command: npx wrangler deploy" — wrong for static sites).

### Pitfall 7 — Wrong production branch in Cloudflare Pages
**Symptom:** Build cloned `main` (empty) instead of `emergent-v3`.
**Fix:** Pages → Settings → Builds & deployments → set Production branch = `emergent-v3`.

---

## 7. Quick Reference Card (Print/Pin)

```
╔══════════════════════════════════════════════════════════════════╗
║                     JELCOS PRODUCTION CARD                       ║
╠══════════════════════════════════════════════════════════════════╣
║ FRONTEND:     https://www.jelcos.ai                              ║
║ BACKEND API:  https://api.jelcos.ai                              ║
║ PREVIEW:      https://jelcos-app.pages.dev                       ║
║ HEALTH:       curl https://api.jelcos.ai/api/health              ║
║                                                                  ║
║ EC2 SSH:      ssh ubuntu@3.111.141.66                            ║
║ REPO ROOT:    /opt/dezider                                       ║
║ COMPOSE DIR:  /opt/dezider/deploy                                ║
║ BACKEND ENV:  /opt/dezider/backend/.env                          ║
║ NGINX CONF:   /etc/nginx/sites-enabled/api                       ║
║ TLS CERT:     /etc/letsencrypt/live/api.jelcos.ai/               ║
║                                                                  ║
║ DEPLOY CMD:   cd /opt/dezider && git pull origin emergent-v3 &&  ║
║               cd deploy && docker compose up -d --build api      ║
║                                                                  ║
║ LOGS:         docker logs -f deploy-api-1                        ║
║ DB:           MongoDB Atlas → cluster0.c39ovvo.mongodb.net       ║
║ GITHUB:       hoorecon/view-dezider @ emergent-v3                ║
╚══════════════════════════════════════════════════════════════════╝
```

---

## 8. Emergency Contacts & Escalation

| Issue | Action |
|---|---|
| Backend 500 errors | `docker logs --tail=100 deploy-api-1` → look for stack trace |
| Backend not responding | `docker compose restart api`; if not fixed, `docker compose up -d --build api` |
| HTTPS cert expired | Certbot auto-renews. Manual: `sudo certbot renew && sudo nginx -s reload` |
| Frontend not updating | Check Cloudflare Pages → Deployments → latest must show "Success" |
| Database connection lost | Check Atlas IP whitelist (must include EC2 IP `3.111.141.66`) |
| DNS issues | `dig +short @1.1.1.1 <hostname>` — if missing, check Cloudflare DNS tab |

---

## 9. Open Backlog (P1 — Not Blocking Production)

1. Push local `db_indices.py` ACM fix from Emergent UI to GitHub `emergent-v3` (cosmetic — prod already seeded correctly via workaround).
2. Wire SMTP gateway for password reset emails (currently OTP returned in JSON).
3. PRR Enhancement #4/#5 — chip-based unit picker + decision linking auto-bypass.
4. 8-step Pros & Cons Phase 2 — AI sub-factor guidance (when LLM budget resets).
5. Public Pulse Phase 3 — AI feedback summaries (when LLM budget resets).
6. Voice Browsing — expand beyond PRR flow to global app navigation.
7. DigiLocker, Exotel SMS, Razorpay integrations (awaiting user keys).
8. Web UI polish — WebFrame tokens for Home/Login/Profile desktop layouts.

---

## 10. How to Hand This Off to a Junior

1. **Give them this doc + read-only access** to GitHub repo & Cloudflare dashboard.
2. **Walk through §5.4** (Git workflow) live once.
3. **Have them deploy a tiny no-op change** (e.g., update a string in `README.md`) end-to-end while you watch.
4. **Show them §6 (Pitfalls)** — most likely 80% of future issues will be one of these.
5. **Save their SSH key on EC2:** `ssh-copy-id ubuntu@3.111.141.66`.

**Things to NEVER let them do without review:**
- ❌ Edit `/opt/dezider/backend/.env` directly (Atlas URI / API keys live here)
- ❌ Run `docker compose down -v` (the `-v` deletes volumes — but volumes are unused on prod since Atlas; still risky)
- ❌ Drop any MongoDB collection in Atlas without backup
- ❌ Modify NGINX config without backup (`cp /etc/nginx/sites-enabled/api{,.bak}` first)
- ❌ Force-push to `emergent-v3` branch on GitHub

---

**Document maintained by:** Emergent E1 agent on behalf of Veales Vedic Decisions.
**Last update:** 2026-05-19. Bump on every meaningful infra change.
