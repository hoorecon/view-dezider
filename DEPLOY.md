# Deployment Guide — jelcos.ai (Dezider)

This app has **TWO independent deployment pipelines**. They are NOT connected.
Deploying one does **not** deploy the other. This is the #1 cause of
"I deployed but my fix didn't show up" confusion.

| Part                         | Where it runs          | How it deploys                                  |
|------------------------------|------------------------|-------------------------------------------------|
| 🔧 Backend (FastAPI `/api/*`) | EC2 Docker container   | `./deploy/sync.sh` on the EC2 box               |
| 🖥️ Frontend (the web app)     | **Cloudflare Pages**   | **Auto-builds on every push to `emergent-v3`**  |

---

## ✅ To deploy a FRONTEND change (UI, screens, components)

Frontend fixes (login screen, Contacts, Solution Finder, headers, etc.) live on
**Cloudflare Pages**. They reach your browser ONLY after the code is pushed to
the GitHub branch Cloudflare watches (`emergent-v3`) and Cloudflare rebuilds.

1. In Emergent, click **"Save to GitHub"** (pushes the latest code to `emergent-v3`).
2. Cloudflare Pages detects the push and rebuilds automatically (~1–2 min).
3. Hard-refresh the live site (Ctrl/Cmd + Shift + R) to drop the old cached bundle.

> ⚠️ Running `./deploy/sync.sh` does **NOT** rebuild the frontend.
> It only touches the backend container. If you change UI and only run
> `sync.sh`, your browser keeps serving the old bundle.

---

## ✅ To deploy a BACKEND change (API, Python, DB migration)

1. Make sure the code is on `emergent-v3` (via "Save to GitHub").
2. SSH into the EC2 box and run:
   ```bash
   cd /opt/dezider
   ./deploy/sync.sh
   ```
   This pulls, **rebuilds** the backend image, recreates the container, and
   health-checks `/api/health`.

> Boot-time migrations (e.g. the masters duplicate cleanup) run automatically
> when the backend container restarts — no manual step needed.

---

## 🧭 Quick decision table

| I changed…                              | What to do                                   |
|-----------------------------------------|----------------------------------------------|
| Only UI / frontend                      | Save to GitHub → wait for Cloudflare build   |
| Only backend / API / DB                 | Save to GitHub → `./deploy/sync.sh` on EC2   |
| Both frontend AND backend               | Save to GitHub → `./deploy/sync.sh` on EC2 (+ Cloudflare auto-builds the frontend) |

After deploying, always **hard-refresh** the browser to bypass the cached bundle.
