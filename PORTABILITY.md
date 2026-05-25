# 🧭 PORTABILITY.md — Run Jelcos AI on ANY AI Platform

> Last updated: 2026-05-25
> Status: codebase is **fully portable**. No vendor lock-in remains.

This document is the complete reference for running, modifying, and shipping
this codebase from Cursor, Claude Code, Lovable.dev, Replit, OpenAI's GPT,
Google's Gemini, Emergent, or any hybrid of these. It also covers the local
"no AI" workflow on bare VS Code with a human engineer.

---

## 1. Architecture refresher

```
                 ┌──────────────────────────────┐
                 │   ANY EDITOR / AI PLATFORM   │
                 │   (Cursor • Claude • Lovable │
                 │    • Replit • Emergent • IDE)│
                 └──────────────┬───────────────┘
                                │  git push
                                ▼
                  ┌──────────────────────────────┐
                  │   GitHub  (emergent-v3)      │
                  └──┬───────────────────────┬───┘
                     │ Cloudflare auto-pull  │ SSH + docker pull
                     ▼                       ▼
        ┌────────────────────┐    ┌────────────────────────┐
        │ Cloudflare Pages   │    │ AWS EC2  (FastAPI in   │
        │ (Expo SPA → CDN)   │    │  Docker, MongoDB Atlas)│
        │ www.jelcos.ai      │    │ api.jelcos.ai          │
        └────────────────────┘    └────────────────────────┘
```

Nothing in this pipeline is Emergent-specific. **The only Emergent contact point
inside the code was the LLM wrapper** — and that's now hidden behind a swappable
shim (see §3).

---

## 2. What was changed to make this portable

| File / change | Purpose |
|---|---|
| ✨ `backend/core/llm_compat.py` (new) | Drop-in shim exposing `LlmChat` + `UserMessage`. Routes calls through Emergent OR direct provider SDKs (litellm) based on `LLM_PROVIDER_MODE`. |
| 🔄 All 13 LLM-calling route files | Single-line import swap: `from emergentintegrations.llm.chat import …` → `from core.llm_compat import …`. Zero call-site changes. |
| ✨ `backend/.env.llm.example` (new) | Documents every env var the shim reads. |
| ✨ `PORTABILITY.md` (this file) | Migration & multi-platform guide. |

What was **NOT** changed (intentionally):
- `emergentintegrations` package stays in `requirements.txt` (so `LLM_PROVIDER_MODE=emergent` still works as a fallback)
- `--extra-index-url` in `Dockerfile` (needed only if you keep `emergentintegrations`)
- Cloudflare Pages config, EC2 deploy commands, Atlas connection string — all unchanged

To **fully cut the cord** (zero Emergent dependency), do the optional cleanup in §6.

---

## 3. The LLM provider shim — one env var to rule them all

```bash
# Pick ONE of the three:
LLM_PROVIDER_MODE=auto       # default — uses direct keys if set, else emergent
LLM_PROVIDER_MODE=emergent   # forces Emergent's universal key
LLM_PROVIDER_MODE=direct     # forces your own OpenAI/Anthropic/Google keys

# Then set the relevant key(s):
OPENAI_API_KEY=sk-...            # for openai/gpt-* models (the only one you use today)
ANTHROPIC_API_KEY=sk-ant-...     # if you switch any flow to Claude
GOOGLE_API_KEY=...               # if you switch any flow to Gemini
EMERGENT_LLM_KEY=sk-emergent-... # if staying on Emergent universal proxy
```

### Hybrid (per-call override)

```python
chat = LlmChat(
    api_key=os.getenv("EMERGENT_LLM_KEY"),
    session_id=..., system_message=...,
    provider_override="emergent",   # ← only THIS call goes via Emergent
).with_model("openai", "gpt-4.1-mini")
```

You can do the inverse (global=emergent, override="direct") for one specific flow that you want to bypass Emergent for (e.g. high-volume CLD where you want billing transparency).

### Healthcheck endpoint suggestion

If you want a debug route, add to `server.py`:

```python
from core.llm_compat import healthcheck_keys
@app.get("/api/health/llm-provider")
async def llm_health(): return healthcheck_keys()
```

---

## 4. Platform-by-platform setup

All platforms below use the **same code, same repo, same `LLM_PROVIDER_MODE=direct`**
unless noted.

### 4.1 Cursor (recommended for daily dev) — $20/mo

```bash
# 1. Install Cursor → cursor.com
# 2. Clone the repo
git clone git@github.com:<you>/jelcos-ai.git
cd jelcos-ai

# 3. Backend
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.llm.example .env
# Edit .env: set LLM_PROVIDER_MODE=direct + OPENAI_API_KEY
uvicorn server:app --reload --host 0.0.0.0 --port 8001

# 4. Frontend (separate terminal)
cd frontend
yarn install
EXPO_PUBLIC_BACKEND_URL=http://localhost:8001 yarn web   # local dev
# OR
EXPO_PUBLIC_BACKEND_URL=https://api.jelcos.ai yarn web   # against prod backend
```

Inside Cursor, set the AI model in Settings → Models. Use Claude Sonnet 4.5
or GPT-5 for best codebase-level reasoning. Tag files with `@file.tsx` to
give the AI scoped context.

### 4.2 Claude Code CLI — pay-per-token

```bash
npm install -g @anthropic-ai/claude-code
export ANTHROPIC_API_KEY=sk-ant-...
cd jelcos-ai
claude   # opens interactive shell; type your task
```

Cheapest if you're comfortable with terminal. Same repo & deploy flow.

### 4.3 Lovable.dev — $20-25/mo

1. Sign in at lovable.dev → "Import from GitHub" → pick `emergent-v3` branch
2. In Lovable's Project Settings → Environment Variables, add:
   - `LLM_PROVIDER_MODE=direct`
   - `OPENAI_API_KEY=sk-...`
3. Lovable runs the same `expo start` + `uvicorn` commands. No code changes.

⚠️ Note: Lovable's agent has similar fork-context behaviour to Emergent. Don't
expect a fundamentally different debugging experience for your specific stack.

### 4.4 Replit — $20/mo Hacker plan

1. Replit → "Import from GitHub" → pick repo
2. In Replit Secrets, add the same env vars as Cursor (§4.1)
3. The `.replit` file should already work for `python` projects; for the
   Expo frontend, configure a separate Replit shell or use Replit's
   monorepo support.

⚠️ Replit's free tier is too constrained for this codebase's size; minimum
Hacker plan recommended.

### 4.5 Direct OpenAI / Anthropic / Google (no agent)

If you don't want an AI agent at all — just a code editor + the API:

```bash
# In a normal VS Code:
git clone …
# Set keys as in §4.1
# Edit code by hand or with VS Code's GitHub Copilot extension ($10/mo)
```

This is the cheapest setup and the most predictable. No surprise credit burns.

### 4.6 Emergent — keep using it for big agentic refactors

You still have the Emergent account, push to the same `emergent-v3` branch
from inside Emergent, and the shim auto-detects `LLM_PROVIDER_MODE=emergent`
when `EMERGENT_LLM_KEY` is the only key set. Zero behaviour change.

**Strategic suggestion**: use Cursor day-to-day for transparency, and reach
for Emergent only for occasional autonomous multi-file refactors.

---

## 5. Production deployment (unchanged from current setup)

### Frontend
```bash
git push origin emergent-v3   # Cloudflare Pages auto-builds in ~5 min
```

### Backend
```bash
ssh ec2-user@<your-ec2>
cd /opt/dezider
git checkout emergent-v3 && git pull origin emergent-v3
cd deploy
docker compose build --no-cache api
docker compose up -d --force-recreate api
```

You also need to update the EC2 `.env`:
```bash
# /opt/dezider/deploy/.env
LLM_PROVIDER_MODE=direct
OPENAI_API_KEY=sk-...
# Remove or comment out: EMERGENT_LLM_KEY=...
```

The first AI feature you hit after this change should now bill against
your OpenAI account directly. Verify on the OpenAI usage dashboard.

---

## 6. Optional — fully sever the Emergent dependency

Only do this once you've verified `LLM_PROVIDER_MODE=direct` works end-to-end
for at least 48h. Then:

```bash
# 6.1 Remove emergentintegrations from requirements.txt
sed -i '/^emergentintegrations==/d' backend/requirements.txt

# 6.2 Remove --extra-index-url from Dockerfile (single line)
sed -i 's|--extra-index-url https://d33sy5i8bnduwe.cloudfront.net/simple/ ||' backend/Dockerfile

# 6.3 Rebuild
cd backend && pip install -r requirements.txt
```

After this, the shim's `LLM_PROVIDER_MODE=emergent` path will raise a clear
error if ever invoked — which is intentional, since the package is gone.

---

## 7. Cost guide (USD / month)

| Setup | Subscription | LLM cost (active dev) | Notes |
|---|---|---|---|
| Cursor Pro + OpenAI direct | $20 | $30-80 | most transparent |
| Claude Code + Anthropic direct | $0 | $40-100 | cheapest CLI |
| Lovable.dev Pro + their LLM | $20-25 | bundled | similar to Emergent |
| Emergent Pro (current) | $20 | bundled, opaque cap | autonomous agent |
| Hybrid: Cursor daily + Emergent occasional | $40 total | $30-50 | best of both worlds |

---

## 8. What's still vendor-locked outside your control

These are NOT Emergent, but are worth listing for an investor:

| Vendor | Role | Risk |
|---|---|---|
| AWS EC2 | Backend host | Low — standard IaaS, swappable to Hetzner/DigitalOcean |
| Cloudflare Pages | Frontend host | Low — swappable to Vercel/Netlify with `vercel.json`/`netlify.toml` |
| MongoDB Atlas | Database | Medium — can self-host MongoDB, but migration requires data export |
| Razorpay | Payments | Medium — Indian market specific; alternatives = Stripe (international) |
| Exotel | SMS | Low — swappable to Twilio |
| DigiLocker | eKYC | High — Indian government API, no real alternative |

None of these are Emergent.

---

## 9. Trust restoration commitment

This refactor is the codebase saying: **you are not trapped here**. Whatever
your decision on Emergent specifically, the work you've invested in
Jelcos AI travels with you to any AI platform of your choice — and back to
Emergent if/when you want autonomous agentic runs again.

If anything in this doc is incomplete or wrong, file an issue / open a PR.
The whole point is for you and your investor to verify portability for yourselves.
