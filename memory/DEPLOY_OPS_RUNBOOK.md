# 🚨 DEPLOY / OPS RUNBOOK — READ THIS FIRST (every fork / after every summary)

This file exists because agents keep forgetting production/deploy facts after a
conversation summary and waste the owner's time & money. **Do not deviate.**

---

## 1. PRODUCTION TOPOLOGY (know this before touching anything)

- **Prod host:** AWS EC2, code at `/opt/dezider`, deploy branch **`emergent-v3`**.
- **Backend:** Docker container **`deploy-api-1`** (image `deploy-api`), serves on `:8001`.
  Deployed by **`./deploy/sync.sh emergent-v3`** (backend only).
- **Database:** **MongoDB Atlas** — `DB_NAME=dezider`, cluster `cluster0.c39ovvo.mongodb.net`.
  Data is **NOT** on the local `deploy_mongo_data` docker volume (that volume is a red herring).
  ⚠️ NEVER commit the full `MONGO_URL` (it contains the Atlas password) to any file.
- **Frontend (live jelcos.ai):** **Cloudflare Pages**, which **auto-builds on every push to `emergent-v3`**.
  `sync.sh` prints "Frontend: NOT deployed by this script." The frontend's
  `EXPO_PUBLIC_BACKEND_URL` is baked at build time in Cloudflare — a mismatch here
  makes the app read from the wrong backend and look "empty".
- **The pod DB (this container, `mongodb://localhost:27017`, `test_database`) is COMPLETELY
  SEPARATE from prod.** Agent has NO access to prod data from the pod.

---

## 2. BUILD-VERSION DISCIPLINE (the auto-bump does NOT fire reliably)

`README.md` lines ~12–14 hold the deploy stamp (column-1 anchored, DO NOT indent):
```
BUILD_VERSION=YYYY.MM.DD.NNN
BUILD_TIMESTAMP=<UTC ISO8601>
BUILD_TAG=vX.Y-short-description
```
**RULE: On EVERY code change set, BEFORE the owner clicks "Save to GitHub", manually bump:**
- `BUILD_VERSION` → today's date; `.001` on a new day, else increment (`.002`, `.003`).
- `BUILD_TIMESTAMP` → `date -u +"%Y-%m-%dT%H:%M:%SZ"`.
- `BUILD_TAG` → new `vX.(Y+1)-slug`.
Reason: `sync.sh` fail-fasts if the pushed README `BUILD_VERSION` ≠ the operator's `EXPECT_BUILD`.
The platform's "auto-bump on Save-to-GitHub" has repeatedly NOT happened.

---

## 3. DEPLOY SEQUENCE (give the owner exactly this)

```
# 1) Save to GitHub -> emergent-v3 (includes the bumped README + all commits)
# 2) Confirm the stamp landed:
cd /opt/dezider && git fetch origin emergent-v3 && git show origin/emergent-v3:README.md | grep BUILD_VERSION
# 3) Deploy backend (value from step 2):
cd /opt/dezider && EXPECT_BUILD=<that value> ./deploy/sync.sh emergent-v3
# 4) Frontend: wait ~1-2 min for Cloudflare Pages auto-build, then HARD-REFRESH the site
#    (Cloudflare cache + per-route JS chunks can be stale right after a build).
```
⚠️ Before Save-to-GitHub, ALWAYS have the owner verify the correct **repo + branch**
(a prior wrong-branch push wiped `deploy/sync.sh` on EC2).

---

## 4. POST-DEPLOY VERIFICATION CHECKLIST (never call a deploy "done" on /health alone)

After deploy + hard-refresh, verify EACH module's list loads a real user's data:
- [ ] MyDezider list (`/tools/dezider-list` → `GET /api/decisions`)
- [ ] Pros & Cons list
- [ ] Solution Finder list
- [ ] SWOT list
- [ ] Login (email + Google) returns session + `whatsapp_verified`
Not just `GET /api/health`. A backend that is "healthy" can still be mid-worker-boot.

---

## 5. "MY DATA IS GONE!" INCIDENT RUNBOOK (usually a display glitch, NOT data loss)

Empty list ≠ data loss. First prove data is safe using the backend's OWN connection
(works regardless of where Mongo lives; `mongosh` is NOT installed on prod):
```
docker exec deploy-api-1 printenv | grep -E "MONGO_URL|DB_NAME"
docker exec deploy-api-1 python -c "
import os, asyncio
from motor.motor_asyncio import AsyncIOMotorClient
async def m():
    c=AsyncIOMotorClient(os.environ['MONGO_URL']); db=c[os.environ.get('DB_NAME','dezider')]
    print('decisions TOTAL:', await db.decisions.count_documents({}))
    u=await db.users.find_one({'email':'REAL_EMAIL'},{'user_id':1,'_id':0})
    print('user:',u)
    if u: print('their decisions:', await db.decisions.count_documents({'user_id':u['user_id']}))
asyncio.run(m())
"
```
- Data present → it is a **frontend→backend URL mismatch** (Cloudflare build env) OR a
  **transient fetch failure during the deploy/boot window**. Fix routing / hard-refresh.
- Data absent but Atlas reachable → wrong `DB_NAME` → repoint, do NOT restore.
- Truly gone → restore from Atlas backup / `mongorestore`. Never run destructive ops blindly.

---

## 6. LIST-SCREEN RESILIENCE RULE (root cause of the 2026-07-17 MyDezider scare)

Every list screen's fetch `catch` MUST set an error flag and show a **"Couldn't load —
your data is safe — Retry"** state. It must **NEVER** fall through to the generic
"No Decisions Yet"/empty state on a failed fetch, and must **not wipe** already-loaded items.
- DONE: `frontend/app/tools/dezider-list.tsx` (build `v3.102`).
- TODO: apply the identical guard to Pros & Cons, Solution Finder, and SWOT list screens.

---

## 7. STANDING NOTES

- Report PDFs (`/api/reports/{module}/{id}.pdf`) 402 without a paid L1 entitlement — EXPECTED.
- Stripe key in the pod is placeholder `sk_test_emergent`; live charge only works post-deploy.
- WhatsApp OTP SMS cannot be delivered in-pod; only gate-decision logic is testable here.
- `improvable='y_both'` + Step-8 `data_type`/`factor_type` are metadata only (not in scoring/report).
