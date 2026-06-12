# Ways of Working / Out (WOWO) — Dezider

_metadata: { "version": "3.16.0", "updated": "2026-06-12" }

## Folder map (v3.5.1)

```
/app
├── backend/
│   ├── server.py                       ← entry; CORS, hardening, router mount
│   ├── core/
│   │   ├── auth.py                     ← get_current_user, get_current_user_optional, require_admin
│   │   ├── database.py                 ← motor client, ensure_indexes
│   │   ├── db_indices.py               ← 200+ index defs
│   │   ├── rate_limiting.py            ← slowapi limiter profiles
│   │   ├── hardening.py                ← sec headers, body cap, gzip, metrics, audit, idempotency, retry
│   │   ├── acm_engine.py               ← ACM seed + feature checks + quota counters
│   │   ├── llm_errors.py               ← Emergent LLM key budget → 503
│   │   └── openapi_helpers.py
│   ├── routes/                         ← one file per module — see table
│   ├── models/                         ← Pydantic schemas (incl. daily_time_log_models.py)
│   ├── data/                           ← seed data (ACM, HOS, matrix_templates, ...)
│   ├── scripts/                        ← one-shot migrations (seed_time_store_services.py, …)
│   ├── utils/                          ← PDF renderer, etc.
│   └── prompts/                        ← LLM prompt templates
├── frontend/
│   ├── app/                            ← expo-router file-based routes
│   │   ├── _layout.tsx                 ← root stack + GlobalVoiceNav
│   │   ├── (tabs)/                     ← main tab nav (Profile has Privacy & Data link)
│   │   ├── auth/
│   │   ├── admin/handbook/             ← admin docs viewer (list + [slug])
│   │   ├── tools/                      ← every tool screen
│   │   │   ├── daily-time-log.tsx       (v3.5)
│   │   │   ├── weekly-review.tsx        (v3.5)
│   │   │   ├── time-dezider.tsx         (v3.5 — Raja Guru UI)
│   │   │   ├── time-store.tsx           (v3.5)
│   │   │   └── privacy-data.tsx         (NEW v3.5.1 — DPDP Export / Delete / Cancel)
│   │   └── p/[slug].tsx                ← public org sub-portal
│   └── src/
│       ├── components/GlobalVoiceNav.tsx
│       ├── hooks/useACM.ts
│       ├── store/authStore.ts
│       └── utils/routeVoiceParser.ts   ← 21 routes in 6 languages
├── deploy/                             ← Dockerfile, docker-compose, k8s
├── docs/                               ← PRD, SRS, API, UAT, ACM, WOWO, CLD, SECURITY, DEPLOYMENT
└── tests/                              ← 5 regression suites (156 cases total)
```

## Backend route → file map (v3.5)

| Module | File | Prefix |
|---|---|---|
| Auth | `routes/auth_routes.py` | `/api/auth` |
| Decisions | `routes/decisions.py` | `/api/decisions` |
| Solution Finder + Matrix | `routes/tools.py` | `/api/solution-finders`, `/api/solution-matrices` |
| Goal Setter | `routes/goal_setter.py` | `/api/goal-setter` |
| Goal Manifestation | `routes/goal_manifestation.py` | `/api/goal-manifestation` |
| AALA | `routes/aala.py` | `/api/aala` |
| Conflict Breaker | `routes/conflict_breaker.py` | `/api/conflict-breaker` |
| CLD | `routes/cld.py` | `/api/cld` |
| TEPFI / AAAA / SWOT / Pros-Cons | `routes/tools.py` | `/api/tepfi`, `/api/swot`, `/api/pros-cons` |
| Lifestyle Designer | `routes/lifestyle_designer.py` | `/api/lifestyle-designer` |
| Lifestyle Eval | `routes/lifestyle_eval.py` | `/api/lifestyle-eval` |
| GEM Flight / Goal | `routes/gem_flight.py`, `routes/ctt_gem.py` | `/api/gem-flight`, `/api/gem-goal` |
| Time Dezider (legacy schedule) | `routes/time_dezider.py` | `/api/time-dezider` |
| **Time Dezider — Raja Guru** (NEW) | `routes/time_dezider_guide.py` | `/api/raja-guru` |
| **Daily Time Log** (NEW) | `routes/daily_time_log.py` | `/api/daily-time-log` |
| **Time Store** (NEW) | `routes/time_store_engine.py` | `/api/time-store` |
| Unconditional Happiness | `routes/unconditional_happiness.py` | `/api/uh` |
| Consciousness Diary | `routes/consciousness_diary.py` | `/api/consciousness-diary` |
| Meditation | `routes/meditation_settings.py` | `/api/meditation` |
| Emotional Gatekeeper | `routes/emotional_gatekeeper.py` | `/api/emotional-gatekeeper` |
| PNA | `routes/pna.py` | `/api/pna` |
| CTT (Task Tracker) | `routes/ctt_gem.py` | `/api/ctt` |
| AI Assistant | `routes/ai_assistant.py` | `/api/ai-assistant` |
| Public Pulse (Phase 1+2+3) | `routes/public_pulse.py` | `/api/public-pulse` |
| PP Org Phase 2.5 | `routes/public_pulse_org.py` | `/api/public-pulse` |
| PP Sub-Portals (Phase 3) | `routes/public_pulse_portal.py` | `/api/p`, `/api/embed` |
| Solutions Store | `routes/solutions_store.py` | `/api/solutions-store` |
| Subscriptions / Payments | `routes/payments.py` | `/api/payments` |
| Collaboration / Video Calls | `routes/collaboration.py`, `routes/video_calls.py` | `/api/collaboration`, `/api/video-calls` |
| ACM | `routes/acm.py` | `/api/acm` |
| Audit Trail | `routes/audit_trail.py` | `/api/audit` |
| DPDP / GDPR | `routes/dpdp.py` | `/api/dpdp` |
| Observability / Metrics | `routes/observability.py` | `/api`, `/api/metrics` |
| Admin Docs (legacy content refresh) | `routes/admin_docs.py` | `/api/admin/docs` |
| **Admin Handbook Viewer** (NEW) | `routes/admin_docs_viewer.py` | `/api/admin-docs` |

## Playbook: add a new module

1. `routes/<my_module>.py` — export `router = APIRouter(prefix="/<slug>")`
2. Register in `server.py`
3. Add Pydantic models to `models/<my_module>_models.py`
4. Add ACM feature(s) in `data/acm_seed_data.py`, bump version
5. Add at least one regression test in `tests/test_<my_module>.py`
6. Add UI screen at `app/tools/<my_module>.tsx`
7. Add to `API_REFERENCE.md` + Postman collection + PRD changelog

## Local commands
```bash
sudo supervisorctl restart backend
sudo supervisorctl restart expo
tail -f /var/log/supervisor/backend.err.log
cd /app && python tests/test_<area>.py
```

---
## v3.14.0 — Subscription tiering & TG segmentation workflow (2026-05-07)

### Roles for the new modules
- **Super-admin only**: edit Tier Matrix, manage Customer Segments
- **Admin**: assign individual users to a tier (`PUT /api/admin/users/{id}/tier`)
- **All users**: read public `/api/pricing`, see their own `/api/me/tier-access`

### Standard workflow
1. **Define TG** → Admin creates Customer Segment in `/admin/customer-segments` with demography/psychography filled (manually or via ✨ AI-Research per factor)
2. **Set pricing** → Admin opens segment's Tier Pricing modal, defines monthly/annual prices for each chakra tier × country (8 supported: IN/US/GB/EU/AE/SG/AU/CA)
3. **Map features** → Admin opens `/admin/tier-matrix`, toggles which modules/features are available at each tier (cascade rules apply)
4. **Public pricing page** → `/pricing` consumes both: shows tier cards with pricing pulled from the segment, perks pulled from the matrix
5. **User upgrade** → User clicks tier card CTA → payment flow → tier assigned → `/api/me/tier-access` returns new unlocked modules

### Cache & invalidation
- `/api/pricing` is cached in-process (60s TTL)
- Any admin write to segment, pricing, factor, or matrix cell auto-invalidates the cache

---
## v3.16.0 — Folder & route additions (2026-06-12)

### Backend route → file map (v3.16 additions)
| Module | File | Prefix |
|---|---|---|
| URL Analyse (Import v3) | `routes/url_analyze.py` | `/api/url-analyze` |
| AI Wallet (user + admin) | `routes/ai_wallet.py` | `/api/ai-wallet`, `/api/admin/ai-wallet` |
| Revenue Reconciliation (super-admin) | `routes/admin_recon.py` | `/api/admin/recon` |

### Backend core additions
| File | Role |
|---|---|
| `core/url_detail.py` | DETAIL-page single-fetch LLM extraction; groups-aware normalization; embedded SPA-state mining |
| `core/url_crawl.py` | Refactored ScraperAPI-aware fetch (`fetch_page`, `fetch_rendered`, `page_text`); plain HTTP + JS-rendered modes |
| `core/ai_metering.py` | `metered_chat(tier=, meta=)` — tier-aware LLM routing (Claude precise vs Gemini fast) with zero-loss multiplier |
| `core/ai_wallet.py` | Wallet ledger + `charge(credit_multiplier=)`; new config fields `precise_model`, `precise_usd_per_mtok`, `import_group_threshold` |
| `core/posthog_client.py` | Lazy server-side PostHog client; no-op without key; emits signup, payment_success, ai_credits_consumed, otp_sent, eg_session_completed |
| `core/recon.py` | Razorpay incremental sync + BigQuery billing-export reader + per-txn tally + daily variance |
| `core/decision_builder.py` | `factor_type` wired through all 4 create/merge paths (factors, hierarchical merge, sub-factors) |

### Frontend additions / updates
| File | Role |
|---|---|
| `src/utils/analytics.ts` | Platform-split PostHog: `posthog-js` on web (replay-capable), `posthog-react-native` on native (events-only) |
| `src/components/steps/Step2.tsx` | Import URL dialog: ai_tier selector, 4 optional hints, "Set Expectations - By AI" button, 300s timeout, hierarchical merge support |
| `app/admin/ai-wallet-config.tsx` | precise_model / precise_usd_per_mtok / import_group_threshold + live multiplier worked-example row |
| `app/admin/recon.tsx` | "Revenue Recon" page (verdict banner, 8 KPI cards, tally table, daily variance, GCP config form, Sync-now, CSV export) |

### Playbook: regenerate the Postman collection
```bash
TOKEN=$(curl -s -X POST http://localhost:8001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@test.com","password":"AdminPass2026!"}' \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['session_token'])")

curl -s -o /app/docs/Postman_Collection.json \
  http://localhost:8001/api/admin/docs/postman-collection \
  -H "Authorization: Bearer $TOKEN"
```

### Local commands (v3.16)
```bash
# Backend & frontend
sudo supervisorctl restart backend
sudo supervisorctl restart expo

# Targeted tests
cd /app && pytest backend/tests/test_url_detail_import.py -v
cd /app && pytest backend/tests/test_admin_recon.py -v

# Live import check
curl -X POST $BASE/api/url-analyze/decision/{id}/import \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"url":"...","ai_tier":"precise","expected_factor_count":20}'
```
