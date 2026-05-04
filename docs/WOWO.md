# Ways of Working / Out (WOWO) — Dezider

_metadata: { "version": "3.5", "updated": "2026-05-04" }

## Folder map (v3.5)

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
│   ├── utils/                          ← PDF renderer, etc.
│   └── prompts/                        ← LLM prompt templates
├── frontend/
│   ├── app/                            ← expo-router file-based routes
│   │   ├── _layout.tsx                 ← root stack + GlobalVoiceNav
│   │   ├── (tabs)/                     ← main tab nav
│   │   ├── auth/
│   │   ├── admin/handbook/             ← admin docs viewer (list + [slug])
│   │   ├── tools/                      ← every tool screen
│   │   │   ├── daily-time-log.tsx       (NEW v3.5)
│   │   │   ├── weekly-review.tsx        (NEW v3.5)
│   │   │   ├── time-dezider.tsx         (REWRITTEN v3.5 — Raja Guru UI)
│   │   │   └── time-store.tsx           (NEW v3.5)
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
