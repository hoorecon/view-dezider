# 🚀 DEPLOYMENT_EMERGENT.md — Running Jelcos AI on Emergent-Native Hosting

> Created: 2026-07-20 (Migration Phases 1–4)
> Audience: you — the operator of the parallel EC2 + Cloudflare production stack.
> Companion docs: `DEPLOY.md` (old EC2/Cloudflare flow — still valid for prod),
> `PORTABILITY.md` (multi-platform guide), `memory/carry_forward.md` (migration log).

**TL;DR**: Your prod (`jelcos.ai` on EC2 + Cloudflare) is untouched and stays exactly
as it is. This document covers the NEW, parallel Emergent-hosted stack only.

---

## 1. Architecture on Emergent (vs the old stack)

On Emergent, ONE origin serves everything:

```
        https://<your-app>.emergentagent.com   (preview)
        https://app.jelcos.ai                  (after custom-domain cutover)
                        │
        ┌───────────────┴────────────────┐
        │      Emergent ingress          │
        │  /api/*  ──────►  FastAPI :8001 (supervisor-managed)
        │  /*      ──────►  Expo web :3000 (Metro / static export)
        └───────────────┬────────────────┘
                        │
                Managed MongoDB (local to the environment)
```

### Mental-model contrast table

| Concern | OLD (EC2 + Cloudflare) | NEW (Emergent) |
|---|---|---|
| Backend runtime | Docker container, uvicorn ×4 workers, rebuilt by `deploy/sync.sh` | **supervisor** runs uvicorn directly; restart with `sudo supervisorctl restart backend`; NO Docker |
| Frontend hosting | Cloudflare Pages auto-build on push to `emergent-v3` (`expo export -p web` → CDN) | Same codebase served by the same environment; Expo web on port 3000 behind the ingress |
| Two pipelines? | YES — sync.sh (backend) + Cloudflare (frontend), the classic "I deployed but nothing changed" trap | **NO — one deploy updates both.** The trap is gone |
| Origins | `www.jelcos.ai` (frontend) + `api.jelcos.ai` (backend) — cross-origin CORS | **Single origin**, backend under `/api` — no cross-origin CORS in practice |
| Database | MongoDB Atlas (Cluster0, ap-south-1) | Managed MongoDB inside the environment (`MONGO_URL=mongodb://localhost:27017`, `DB_NAME=dezider`) |
| TLS / DNS | GoDaddy A-record → EC2 IP, Let's Encrypt + NGINX | Emergent platform handles TLS; custom domain via CNAME (see §5) |
| `BUILD_VERSION` stamp in README | Used by sync.sh to verify the running build | Not used by Emergent (harmless to keep; sync.sh still needs it for prod) |
| deploy/sync.sh | THE deploy command on EC2 | **Not used at all** on Emergent. Do not run it here |
| Health check | `curl https://api.jelcos.ai/api/health` | `curl https://<origin>/api/health` (same endpoint) |
| OpenAPI | `api.jelcos.ai/openapi.json` (NGINX forwarded all paths) | `/api/openapi.json` (ingress only forwards `/api/*` — this was a 1-line migration fix in `server.py`) |

---

## 2. Deployment lifecycle on Emergent

1. **Make/approve code changes** in the Emergent chat (this environment).
2. **Save to GitHub** (button in the chat input) → pushes to branch **`emergent-v3-e3`**.
   ⚠️ Cloudflare Pages watches `emergent-v3` (no `-e3`), so a Save to GitHub from here
   does NOT trigger a prod frontend build. The two stacks stay independent.
3. **Deploy** via the Emergent platform (Deploy button). The platform builds and hosts
   the app at its own deployment URL, separate from this preview environment.
4. Post-deploy smoke: `GET /api/health`, log in, open one tool screen.

### Where env vars live

| File | Contents | In git? |
|---|---|---|
| `backend/.env` | Mongo URL/DB, JWT secret, ALL third-party keys, `PUBLIC_APP_URL`, rate limits, LLM keys | **NO (gitignored)** — must be re-entered/configured per environment |
| `frontend/.env` | `EXPO_PUBLIC_BACKEND_URL`, `EXPO_PUBLIC_APP_URL`, PostHog | **NO (gitignored)** |

### Env vars you MUST re-point at deploy/cutover time

These currently hold the preview origin and must become the deployed origin
(ultimately `https://app.jelcos.ai`):

```
backend/.env :  PUBLIC_APP_URL=https://app.jelcos.ai
backend/.env :  ALLOWED_ORIGINS=https://app.jelcos.ai
frontend/.env:  EXPO_PUBLIC_BACKEND_URL=https://app.jelcos.ai
frontend/.env:  EXPO_PUBLIC_APP_URL=https://app.jelcos.ai
```

Everything URL-related is env-driven since Phase 2 (share links, email footers,
PDF brand links, SEO canonical/og:url) — re-pointing these four lines is the whole job.
`EXPO_PUBLIC_*` values are baked into the web bundle at build time → the frontend
must be rebuilt/restarted after changing them.

---

## 3. Data: moving the snapshot to the deployed database

The environment's local MongoDB holds a **restored snapshot of prod Atlas**
(DB `dezider`, 198 collections / 3,875 docs, verified 1:1 parity on 2026-07-20).

Recommended path to seed the deployed environment's DB:

```bash
# In THIS environment (source):
mongodump --uri="mongodb://localhost:27017" --db=dezider --out=/tmp/dezider_dump

# Transfer the dump, then in the deployed environment (target):
mongorestore --uri="<deployed MONGO_URL>" --nsInclude="dezider.*" --drop /tmp/dezider_dump

# Verify parity (per-collection counts) after restore.
```

If the Emergent platform offers a managed data-migration/copy facility for
deployments, prefer that — same outcome, less manual work.

> ### ⚠️ SNAPSHOT IS FROZEN
> The data was captured on **2026-07-20**. Your real prod (Atlas) keeps changing.
> **Before the real cutover you MUST re-sync from Atlas** (fresh mongodump →
> restore), inside a maintenance window, or you will lose everything users did on
> prod after 2026-07-20. The Atlas IP allowlist will need to be temporarily
> reopened for that re-sync (it was a 6-hour temporary rule last time).
> Rule stays: **never write to Atlas from this stack — Atlas is read-only source.**

Local test fixtures added during migration (safe to keep, or drop before cutover):
`admin@test.com`, `super@test.com`, `migration.tester@test.com`,
`harden_1777921741@example.com` — see `memory/test_credentials.md`.

---

## 4. Third-party keys — ⚠️ READ THIS

`backend/.env` here carries the **LIVE prod keys** copied from your prod env file:

| Integration | Key type | Implication in THIS stack |
|---|---|---|
| Razorpay / RazorpayX | **LIVE** (`rzp_live_…`) | A checkout/payout triggered here is a REAL money movement |
| Resend | LIVE | Emails sent here are REAL (share/report/OTP emails go to real inboxes) |
| UltraMsg (WhatsApp) | LIVE (instance82054) | WhatsApp messages/OTPs sent here reach REAL phone numbers |
| Zoho Books | LIVE (org 60068643866) | A sync here reads your REAL books (current usage is read-only P&L/BS pull) |
| PostHog | LIVE (eu.i.posthog.com) | Analytics from this stack mixes into the same PostHog project as prod |
| Gemini / Groq / OpenAI | User keys | Usage consumes your quotas (OpenAI key was quota-exhausted as of 2026-07-20; free-first chain auto-falls to Gemini) |
| Emergent LLM key | Environment key | Fallback provider via `core/llm_compat.py` (`LLM_PROVIDER_MODE=auto`) |

**Recommendation until cutover**: switch Razorpay to test-mode keys, use a Resend
sandbox/test domain, and (optionally) a separate PostHog project, so parallel-run
testing can never fire real customer-facing side effects. Swap the live keys back
in as part of the cutover checklist.

---

## 5. Custom domain: attaching app.jelcos.ai

1. In Emergent: **Deployments → your deployment → Custom Domain → add `app.jelcos.ai`**.
   The platform shows the exact DNS target (typically a CNAME) and provisions TLS
   automatically once DNS resolves.
2. At **GoDaddy** (DNS for jelcos.ai): add the record the platform asks for, e.g.
   `CNAME  app  →  <target shown by Emergent platform>`
   (If an old `app` record exists — it currently points at Cloudflare Pages — it must be
   replaced. That is the ONLY prod-adjacent record you touch, and only at cutover.)
3. Re-point the four env vars from §2 to `https://app.jelcos.ai`, rebuild frontend.
4. Verify: `https://app.jelcos.ai/api/health`, login, canonical tag shows `app.jelcos.ai`.

**Explicitly untouched**: `www.jelcos.ai` (Cloudflare Pages), `api.jelcos.ai`
(EC2/NGINX), the EC2 box, MongoDB Atlas, and all other DNS records. The old prod
keeps serving users throughout.

---

## 6. Rollback & safety

- **Prod is never at risk.** This stack shares no infrastructure with EC2/Cloudflare/
  Atlas. Worst case here = broken preview/deployment; prod users see nothing.
- **Redeploy**: deploy again from a known-good chat state (or roll back the chat to a
  previous checkpoint and redeploy). GitHub branch `emergent-v3-e3` is the code trail.
- **Abandon**: simply delete the Emergent deployment. Undo the `app` CNAME at GoDaddy
  if it was already created; DNS reverts to the old behavior.
- **Domain rollback after cutover**: point the `app` CNAME back to its previous target
  — old stack resumes within DNS TTL.
- The old prod branch (`emergent-v3`) and `deploy/sync.sh` remain fully functional for
  the EC2 pipeline — nothing in this migration modified them.

---

## 7. Quick reference (this environment)

```bash
sudo supervisorctl status                    # backend / frontend / mongodb
sudo supervisorctl restart backend           # after backend/.env changes
sudo supervisorctl restart frontend          # after frontend/.env changes (rebuild bundle)
tail -n 50 /var/log/supervisor/backend.err.log
curl -s localhost:8001/api/health
```

Test credentials: `memory/test_credentials.md` · Regression results: Phase 3 log in
`test_result.md` (329 pass / 15 fail, zero migration-caused) · Migration history:
`memory/carry_forward.md`.

---

## 8. BACKPORT_README — prod backports

**Status:** the original 5-fix backport was applied to prod on 2026-07-20
(`emergent-v3` @ `28e749c2` — "Backport E3 fixes: …"). That patch file has been
removed from this repo to avoid confusion.

**Current patch: `backport_3defects_for_emergent-v3.patch`** (repo root) — 3 real
defects found by code-review triage, backend-only, verified `git apply --check`
clean against `origin/emergent-v3` @ `28e749c2`:
1. `backend/routes/ai_wallet.py` — restore missing `@router.put` + signature for
   `PUT /api/ai-wallet/provider-consent` (endpoint body was orphaned/unreachable;
   frontend consent saves silently failed with 405)
2. `backend/routes/ai_tools.py` — `except _aw.InsufficientCredits` (was undefined
   `ai_wallet` → NameError → 500 instead of 402 on credit exhaustion)
3. `backend/routes/financial_model.py` — add missing `import logging` (Zoho-snapshot
   failure path raised NameError instead of degrading gracefully)

```bash
git checkout emergent-v3 && git pull origin emergent-v3
git show origin/emergent-v3-e3:backport_3defects_for_emergent-v3.patch > /tmp/backport_3defects.patch
git apply --check /tmp/backport_3defects.patch   # dry-run — must print nothing
git apply /tmp/backport_3defects.patch
git add backend/routes/ai_wallet.py backend/routes/ai_tools.py backend/routes/financial_model.py
git commit -m "fix: restore provider-consent PUT endpoint, 402 on credit exhaustion, financial_model logging import (backport)"
git push origin emergent-v3
```

Deploy: backend-only → `./deploy/sync.sh` on EC2. No Cloudflare/frontend build needed.
If prod moves ahead and `--check` complains, re-request a regenerated patch.

> An Earth Dezider product · Powered by VEALES
