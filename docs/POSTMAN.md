# Postman / Insomnia collection — Dezider API

_metadata: { "version": "3.23.1", "updated": "2026-07-19" }

Collection JSON: `/app/docs/Postman_Collection.json` — **fully regenerated 2026-07-19 from the live OpenAPI: 126 folders, 1,316 requests, 100% endpoint coverage** (every route in the codebase; no "Other" bucket). Folder names come from the module taxonomy in `backend/prompts/admin_docs_taxonomy.py`.

**Regenerate any time (keeps the collection in lock-step with the code):**
```bash
cd /app/backend && python scripts/generate_postman_collection.py
```
or download the identical output from `GET /api/admin/docs/postman-collection` (admin Bearer token).
> Adding a new route module? Add its path prefix to `CATEGORY_MAP` in
> `backend/prompts/admin_docs_taxonomy.py` so its requests land in a named folder,
> then re-run the script. The script warns if anything falls into "Other".

## Environments
- **Local Dev** (`baseUrl` = http://localhost:8001)
- **Stage** (`baseUrl` = https://stage.dezider.app)

## Folders (v3.5)

1. **0. Auth** — register / login / me / logout
2. **1. Health & Metrics** — health, ready, live, version, metrics
3. **2. DPDP** — export, delete-request, cancel, status, admin/audit-log, admin/purge
4. **3. Solution Matrix** — templates list/detail, CRUD, PDF export
5. **4. Solution Finder** — CRUD
6. **5. Public Pulse** — consent, feedback, dashboards, YoY analytics
7. **6. Public Pulse Org** — apply, dashboard, feedback, members
8. **7. Public Sub-Portal** — /p/{slug}, /embed/{slug}, widget.js
9. **8. ACM** — my-access, feature, admin/seed
10. **9. Daily Time Log** (NEW) — preferences, upsert-day, get-day, refresh-rollup, week, streaks, weekly-review
11. **10. Time Dezider — Raja Guru** (NEW) — day-plan, midday-check, evening-retro, next-action, preferences, feedback
12. **11. Time Store** (NEW) — time-audit, services, purchase, purchases, delegate, delegations
13. **12. Tools (sample)** — goal-setter, AALA, CLD, conflict-breaker

## Auth flow tip
After **Auth → Login**, the test script copies `session_token` into the env
automatically. Other requests pick it up via the collection-level Bearer auth.

## Smoke test sequence (CI)

```
POST /auth/register           (random email)
POST /auth/login
GET  /auth/me
GET  /solution-matrices/templates
POST /solution-matrices       (accurate mode)
GET  /solution-matrices/{id}/pdf
GET  /dpdp/status
GET  /daily-time-log/preferences
POST /daily-time-log          (one day, 2 blocks)
GET  /daily-time-log/streaks
GET  /raja-guru/day-plan
GET  /time-store/time-audit
GET  /time-store/services?save_minutes_per_day=30
POST /auth/logout
```

---
## v3.14.0 — New folders (auto-generated 2026-05-07)
- **Tier Matrix — 7 Chakras (Admin)** · 6 endpoints
- **Customer Segments — TG Master** · 11 endpoints
- **Subscription Tiers (Public)** · `/api/tiers`
- **Pricing — 7 Chakras** · `/api/pricing` (cached 60s)
- **Tier Matrix (Public)** · `/api/tier-matrix`
- **My Tier Access** · `/api/me/tier-access`

Run `GET /api/admin-docs/postman-collection` (admin-only) to download the latest auto-generated collection.

---
## v3.16.0 — Folders added (auto-generated 2026-06-12)
- **URL Analyse** · 3 endpoints (generic analyze, decision import, set-expectations)
- **AI Wallet** · 11 user endpoints + 4 admin endpoints (config, grant, users, packs/refill)
- **Admin Revenue Recon** · 6 super-admin endpoints (summary, transactions, daily, sync, gcp-config, transactions.csv)
- **Analytics** · server-side only via `core/posthog_client.py` (no REST surface; events listed in API_REFERENCE)

### Regeneration
The collection is regenerated from the live OpenAPI schema:
```bash
TOKEN=$(curl -s -X POST $BASE_URL/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@test.com","password":"AdminPass2026!"}' \
  | jq -r .session_token)

curl -s -o /app/docs/Postman_Collection.json \
  "$BASE_URL/api/admin/docs/postman-collection" \
  -H "Authorization: Bearer $TOKEN"
```

### Stats (2026-06-12 build)
- 52 folders, **972 endpoints**, ~520 KB JSON.
- All v3.16 routes verified present: `url-analyze`, `ai-wallet/*`, `admin/recon/*`, `set-expectations`.

### Smoke test sequence add-ons (v3.16)
```
POST /url-analyze/decision/{id}/import       (ai_tier=fast)
POST /url-analyze/decision/{id}/set-expectations
GET  /ai-wallet                              (read balance)
GET  /admin/ai-wallet/config                 (super-admin)
PUT  /admin/ai-wallet/config                 (precise_usd_per_mtok, import_group_threshold)
GET  /admin/recon/summary                    (super-admin)
POST /admin/recon/sync                       (super-admin)
GET  /admin/recon/transactions.csv?month=2026-06
```

## v3.23.0 additions (2026-07-19)
New FRAME monetization folders:
1. **AdMaker Program (Sponsored Auction)** — 12 requests: admin bid CRUD, CPC click track,
   resolve-config, and the advertiser self-serve `my/*` set (eligible-options, bids CRUD, dashboard).
2. **AdTaker Program (Publisher Widgets)** — 13 requests: publisher CRUD + rotate-keys + stats,
   self-serve trio (auto-populated `{{adtakerKey}}` / `{{adtakerSecret}}` collection vars in
   `X-Adtaker-Key/-Secret` headers), org portal, and the public widget.js / embed / track endpoints.
3. **Option Bank & Finder Jobs** — 10 requests: bank stats, the 3 ingestion rails (+ sync-template,
   clear), finder config/run, async job start + poll (uses `{{decisionId}}` / `{{finderJobId}}`).
Env-var tips: set `{{templateId}}` = `bmp-55-patterns` for smoke runs; `{{trackerId}}` comes from
the create-publisher response (the API **secret is returned only once** — save it to the env immediately).

## v3.23.1 — Full regeneration + taxonomy overhaul (2026-07-19)
The collection was previously auto-generated on 2026-06-12 and only hand-patched
since, leaving ~300 newer endpoints missing and 419 requests in a generic "Other"
folder. Fixed permanently:
- **`backend/prompts/admin_docs_taxonomy.py`** now maps ALL ~130 route prefixes to
  named module folders (incl. subpath overrides: `/decider-store/*/bank` → Option Bank,
  `/decisions/*/finder` → Finder Jobs, `/decisions/*/deep-import` → Deep Import; admin
  sub-areas like Recon, Notification Engine, Import Analytics, PII Lookup split out of
  the "Admin Management" catch-all).
- **`backend/scripts/generate_postman_collection.py`** (NEW) — one command rebuilds the
  committed JSON from the live OpenAPI; prints folder/request counts and warns on "Other".
- Builder extracted to `core/openapi_helpers.build_postman_collection` — the admin
  download endpoint and the script share the exact same code path.
- Collection-level variables now include `BASE_URL, AUTH_TOKEN, adtakerKey, adtakerSecret,
  trackerId, templateId, decisionId, finderJobId`. Path params use `{{SAMPLE_<NAME>}}`.
- **Current stats: 126 folders · 1,316 requests · 0 uncategorized.**
