# View Dezider

<!--
═══════════════════════════════════════════════════════════════════════
BUILD STAMP — DO NOT EDIT BY HAND; bumped automatically every Save-to-
GitHub. Used by `deploy/sync.sh` to verify the running build matches
the latest pushed commit. Version format: year.month.day.seq3 (e.g. the
line below). The three keys must each start at column 1 — sync.sh looks
for ^BUILD_VERSION=, ^BUILD_TIMESTAMP=, ^BUILD_TAG= anchored to a line
start so this descriptive paragraph CANNOT trip the extractor.
═══════════════════════════════════════════════════════════════════════
BUILD_VERSION=2026.06.27.008
BUILD_TIMESTAMP=2026-06-27T20:33:15Z
BUILD_TAG=v3.92-my-published-hub
-->

> The Decision OS — codebase powering **JELCOS AI** (live), **GeoDezider AI** (next), and **Earth Dezider Consumer** (year 3) — under master brand **Earth Dezider**.

[![Status](https://img.shields.io/badge/status-active-success)]() [![Edition](https://img.shields.io/badge/active%20edition-JELCOS%20AI-7C3AED)]() [![Stack](https://img.shields.io/badge/stack-Expo%20%2B%20FastAPI%20%2B%20MongoDB-blue)]()

---

## Brand Architecture

| Layer | Name | Surface |
|---|---|---|
| Legal entity | VEALES Vedic Decisions Pvt Ltd | Billing, contracts, legal only |
| Internal codename | **View Dezider** | This repo, CI, internal docs |
| Master brand | **Earth Dezider** — *"The Decision OS for People"* | "by Earth Dezider" imprint on every product surface |
| Active edition (live) | **JELCOS AI** — *"Joyful Executive's Life Choices Operating System powered by AI"* | `jelcos.ai` |
| Future edition (next) | **GeoDezider AI** | `geodezider.ai` |
| Future edition (yr 3) | **Earth Dezider Consumer** | `earthdezider.com` |

Edition is selected at runtime via `PRODUCT_EDITION` env var (`jelcos` / `geodezider` / `consumer`). Single codebase serves all three.

---

## Tech Stack

| Layer | Stack |
|---|---|
| Frontend | Expo (React Native) · Expo Router · Zustand · expo-speech-recognition |
| Backend | FastAPI · Python 3.11 · Motor (async MongoDB) · Pydantic |
| Database | MongoDB |
| AI | Emergent LLM Key (OpenAI / Anthropic / Google via LiteLLM) |
| Auth | Bearer session tokens (7-day expiry) |
| Deployment | Native Emergent (preview) → custom domain (production) |

---

## Module Catalog (32 modules · 89 features · v3.14.0)

**Decision tools**: My Dezider (PRR HOS), Test123, Pros & Cons, SWOT, Decision Templates, Solution Matrix, Goal Setter, Goal Manifestation, Conflict Breaker, PNA, CTT/GEM, Lifestyle Dezider, Time Dezider · 

**Personal OS**: Life Directions Compass (LDC), AALA (Accrued Assets & Liabilities), Daily Tracker, Drift Report, Decision Journal, Consciousness Diary, LEE (Lifestyle Effectiveness Eval), Unconditional Happiness · 

**Collaborative**: ExpertNet, Public Pulse, Solutions Store, ReviewNet, Shared Steps, Org Surveys · 

**Admin**: Tier Matrix (7 chakras), Customer Segment Master, ACM (Access Control Matrix), CLD Engine, Public Pulse Org Portal, Admin Docs Hub.

---

## Local Development

### Prerequisites
- Node 18+ · Yarn · Python 3.11 · MongoDB 6+

### Setup
```bash
# Backend
cd backend
cp .env.example .env          # fill in values (MongoDB URL, LLM key, etc.)
pip install -r requirements.txt
uvicorn server:app --host 0.0.0.0 --port 8001 --reload

# Frontend
cd frontend
cp .env.example .env          # fill in EXPO_PUBLIC_BACKEND_URL
yarn install
yarn start                     # opens Expo Dev Tools
```

### Test admin login
After running `python backend/seed_admin.py` (or auto-seed on first boot):
- Email: `admin@test.com`
- Password: `AdminPass2026!`

---

## Repository Structure

```
/
├── backend/                   FastAPI app
│   ├── core/                  Auth, DB, hardening, rate limiting, branding
│   ├── data/                  ACM seed data
│   ├── models/                Pydantic schemas (32+ models)
│   ├── prompts/               LLM prompt registry, doc taxonomy
│   ├── routes/                FastAPI routers (one per module)
│   ├── tests/                 Backend regression suites
│   ├── server.py              App entry + router registration
│   └── requirements.txt
├── frontend/                  Expo app
│   ├── app/                   Expo Router file-based routes
│   │   ├── (tabs)/            Bottom-tab navigator
│   │   ├── admin/             Admin-only screens
│   │   ├── auth/              Login / register
│   │   ├── tools/             32+ decision tools
│   │   └── pricing.tsx        Public pricing page
│   ├── src/
│   │   ├── components/        Reusable UI
│   │   ├── store/             Zustand stores
│   │   └── utils/             API client, helpers
│   └── package.json
├── docs/                      Auto-generated docs (PRD, SRS, API, Postman, ACM, CLD, WOWO, etc.)
├── tests/                     Cross-module integration tests
└── memory/                    Agent handoff state (carry_forward.md, brand_architecture.md, test_credentials.md)
```

---

## Production Hardening

- **Scale target**: 1M users · 10K concurrent
- **Rate limiting**: tiered (default / auth / AI / expensive) via `core/rate_limiting.py`
- **Hardening middleware**: 10MB body cap, security headers, HSTS, gzip, slow-request log
- **DB indexing**: 200+ indices auto-applied on boot via `core/db_indices.py`
- **In-process TTL cache**: `/api/pricing` (60s, auto-invalidated)
- **LLM resilience**: graceful 503 + static fallback dictionaries when budget capped
- **Auth**: Bearer tokens, role hierarchy `super_admin → admin → co_admin → user`

---

## Documentation

All docs live in `/docs/` and are also viewable in-app via `/admin/docs`:

- `PRD.md` · Product Requirements
- `SRS.md` · System Requirements
- `API_REFERENCE.md` · REST API reference
- `POSTMAN.md` · Postman guide
- `Postman_Collection.json` · Auto-generated v2.1 collection (52 folders, 700+ endpoints)
- `ACM.md` · Access Control Matrix spec
- `CLD.md` · CLD Engine spec
- `WOWO.md` · Ways of Working / Out
- `REGRESSION.md` · Regression test catalogue
- `UAT.md` · UAT test cases
- `SECURITY.md` · Security & threat model
- `DEPLOYMENT.md` · Deployment runbook

---

## Versioning

Active version: **v3.14.0** (2026-05-07)

See `/memory/carry_forward.md` for full version history and pending epic backlog.

Branch strategy:
- `emergent-v1` · prior fork snapshot (preserved as fallback)
- `emergent-v2` · current working state (this push)
- `main` · production-blessed (after E2E pass)

---

## License

**Proprietary · All Rights Reserved**

© 2026 VEALES Vedic Decisions Pvt Ltd. See `LICENSE` for full terms.

This repository and its contents are confidential and proprietary. Unauthorized copying, distribution, modification, public display, or public performance is strictly prohibited.

---

## Contact

For partnership, licensing, or commercial enquiries: refer to the operating company's website or your assigned point of contact.

> An Earth Dezider product · Powered by VEALES
