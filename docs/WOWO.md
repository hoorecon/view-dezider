# Ways of Working / Out (WOWO) — Dezider

_metadata: { "version": "3.4", "updated": "2026-05-04" }

Maintainer's quick-ref for which file does what.

## Folder map

```
/app
├── backend/
│   ├── server.py                       ← entry; CORS, hardening, router mount
│   ├── core/
│   │   ├── auth.py                     ← get_current_user, require_admin
│   │   ├── database.py                 ← motor client, ensure_indexes
│   │   ├── db_indices.py               ← 200+ index defs
│   │   ├── rate_limiting.py            ← slowapi limiter, profiles
│   │   ├── hardening.py                ← sec headers, body cap, gzip, metrics, audit, idempotency, retry
│   │   ├── acm_engine.py               ← ACM seed boot, feature checks, quota counters
│   │   ├── llm_errors.py               ← Emergent LLM key budget cap → 503
│   │   ├── file_storage.py             ← base64 / S3 abstraction
│   │   ├── helpers.py                  ← misc utilities
│   │   └── openapi_helpers.py          ← OpenAPI schema customisations
│   ├── routes/                         ← ONE FILE PER MODULE — see table below
│   ├── models/                         ← Pydantic schemas
│   ├── data/                           ← seed data (ACM, hos catalog, templates, etc.)
│   ├── utils/                          ← PDF renderer, etc.
│   └── prompts/                        ← LLM prompt templates
├── frontend/
│   ├── app/                            ← expo-router file-based routes
│   │   ├── _layout.tsx                 ← root stack + GlobalVoiceNav mount
│   │   ├── (tabs)/                     ← main tab nav
│   │   ├── auth/                       ← login/register/forgot/reset
│   │   ├── admin/                      ← admin-only screens (incl. /admin/handbook viewer)
│   │   ├── tools/                      ← every tool (solution-matrix, goal-setter, ...)
│   │   └── p/[slug].tsx                ← public org sub-portal page
│   └── src/
│       ├── components/                 ← GlobalVoiceNav, VoiceStepInput, ...
│       ├── hooks/                      ← useACM, useAuth, ...
│       ├── store/                      ← zustand stores (auth, decisions)
│       ├── utils/                      ← api, alert, routeVoiceParser, stepVoiceParser
│       └── constants/                  ← colors, life-areas
├── deploy/                             ← Dockerfile, docker-compose, k8s
├── docs/                               ← PRD, SRS, API, UAT, ACM, WOWO, CLD, SECURITY, DEPLOYMENT
├── memory/                             ← carry_forward, test_credentials, pending_verifications
└── tests/                              ← regression suites
```

## Backend route → file map

| Module | File | Mount prefix |
|---|---|---|
| Auth | `routes/auth_routes.py` | `/api/auth` |
| Decisions | `routes/decisions.py` | `/api/decisions` |
| Notifications | `routes/notifications.py` | `/api/notifications` |
| Analytics | `routes/analytics.py` | `/api/analytics` |
| Tools (Solution Finder/Matrix) | `routes/tools.py` | `/api/solution-finders`, `/api/solution-matrices` |
| Goal Setter | `routes/goal_setter.py` | `/api/goal-setter` |
| Goal Manifestation | `routes/goal_manifestation.py` | `/api/goal-manifestation` |
| AALA | `routes/aala.py` | `/api/aala` |
| Conflict Breaker | `routes/conflict_breaker.py` | `/api/conflict-breaker` |
| CLD | `routes/cld.py` | `/api/cld` |
| TEPFI | (in `routes/tools.py`/`tepfi`) | `/api/tepfi` |
| SWOT | `routes/swot.py` | `/api/swot` |
| Pros & Cons | `routes/pros_cons.py` | `/api/pros-cons` |
| Lifestyle Designer | `routes/lifestyle_designer.py` | `/api/lifestyle-designer` |
| Lifestyle Eval | `routes/lifestyle_eval.py` | `/api/lifestyle-eval` |
| GEM Flight | `routes/gem_flight.py` | `/api/gem-flight` |
| Time Dezider | `routes/time_dezider.py` | `/api/time-dezider` |
| Unconditional Happiness | `routes/unconditional_happiness.py` | `/api/uh` |
| Consciousness Diary | `routes/consciousness_diary.py` | `/api/consciousness-diary` |
| Meditation | `routes/meditation_settings.py` | `/api/meditation` |
| Emotional Gatekeeper | `routes/emotional_gatekeeper.py` | `/api/emotional-gatekeeper` |
| PNA | `routes/pna.py` | `/api/pna` |
| CTT (Task Tracker) | `routes/ctt_gem.py` | `/api/ctt`, `/api/gem-goal` |
| AI Assistant | `routes/ai_assistant.py` | `/api/ai-assistant` |
| Public Pulse Phase 1+2 | `routes/public_pulse.py` | `/api/public-pulse` |
| Public Pulse Org Phase 2.5 | `routes/public_pulse_org.py` | `/api/public-pulse` |
| Public Pulse Sub-Portals | `routes/public_pulse_portal.py` | `/api/p`, `/api/embed` |
| Solutions Store | `routes/solutions_store.py` | `/api/solutions-store` |
| Subscriptions | `routes/payments.py` | `/api/payments` |
| Collaboration | `routes/collaboration.py` | `/api/collaboration` |
| Video Calls | `routes/video_calls.py` | `/api/video-calls` |
| ACM | `routes/acm.py` | `/api/acm` |
| Audit Trail | `routes/audit_trail.py` | `/api/audit` |
| DPDP / GDPR | `routes/dpdp.py` | `/api/dpdp` |
| Observability / Metrics | `routes/observability.py` | `/api`, `/api/metrics` |
| Admin | `routes/admin.py` | `/api/admin` |
| Admin Docs | `routes/admin_docs.py` | `/api/admin/docs` |
| Face Auth | `routes/face_auth.py` | `/api/face-auth` |
| Social Learning | `routes/social_learning.py` | `/api/social-learning` |
| Google Calendar | `routes/google_calendar.py` | `/api/google-calendar` |
| Decision Templates | `routes/decision_templates.py` | `/api/decision-templates` |
| Decision Intake | `routes/decision_intake.py` | `/api/decision-intake` |
| DEO | `routes/deo.py` | `/api/deo` |
| Org Auth | `routes/org_auth.py` | `/api/org-auth` |
| Incidents | `routes/incident_response.py` | `/api/incidents` |
| Contacts | `routes/contacts.py` | `/api/contacts` |
| AAAA | `routes/aaaa.py` (planned) | `/api/aaaa` |

## How to add a new module

1. Add `routes/<my_module>.py` exporting `router = APIRouter(prefix="/<slug>")`.
2. Register in `server.py` (`from routes.<my_module> import router; api_router.include_router(...)`).
3. Add models to `models/<my_module>_models.py` if non-trivial.
4. Add ACM feature(s) in `data/acm_seed_data.py`, bump version.
5. Add at least one regression test in `tests/test_<my_module>.py`.
6. Add UI route in `app/tools/<my_module>.tsx` or wherever appropriate.
7. Add to relevant docs (PRD modules section + API_REFERENCE).

## Local commands

```bash
sudo supervisorctl restart backend
sudo supervisorctl restart expo
tail -f /var/log/supervisor/backend.err.log
cd /app && python tests/test_solution_matrix_orgtype.py   # any suite
```
