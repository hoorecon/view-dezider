# 🔁 FORK KICKOFF — read me FIRST on every fork (standing operating procedure)

> Purpose: stop context-amnesia after fork/summary. Everything an agent must
> know to continue View Dezider lives here or is linked from here. Keep this
> file SHORT and CURRENT — it is the first thing to read after PRD.md.

## 0) Last user intent (update at end of every session)
- 2026-06-26: Fixed AI-chat URL import (ChatGPT React-Router parse + Claude
  snapshot-JSON via ScraperAPI), Gemini = not importable (guard 422),
  review-before-merge modal with drag-reorder, auto-jump to Step 6 + "Top pick"
  spotlight. Build bumped to 2026.06.26.001 (tag v3.75-ai-chat-import-claude-review-reorder).
  PENDING: user to Save-to-GitHub (emergent-v3) + run EC2 sync (see §2).

## 1) What this app is
View Dezider — decision-making SaaS (PRR framework). Frontend = Expo/React-Native
(file routes in frontend/app), Backend = FastAPI (/app/backend), DB = Mongo.
Full product detail: /app/memory/PRD.md. History: /app/memory/CHANGELOG.md.

## 2) DEPLOY RITUAL (production = jelcos.ai, branch emergent-v3, EC2 /opt/dezider)
Whenever code is ready to ship, BEFORE finishing:
  1. Bump the build stamp:
       python3 backend/scripts/bump_build_version.py --tag v3.<n>-<short-desc>
     (auto-sets BUILD_VERSION=YYYY.MM.DD.NNN in README.md; prints the new value)
  2. Tell the user the exact two steps:
       a. Click "Save to GitHub" in Emergent (pushes to emergent-v3).
       b. On EC2:  cd /opt/dezider && EXPECT_BUILD=<new BUILD_VERSION> ./deploy/sync.sh emergent-v3
  3. NOTE: the agent CANNOT push to GitHub itself — only the user's Save-to-GitHub
     action does. Never claim a git push happened. sync.sh fail-fasts if the
     remote BUILD_VERSION != EXPECT_BUILD (catches dropped/partial pushes).
Cloudflare Pages auto-builds the frontend on push to emergent-v3 (~3-5 min).

## 3) Local QA facts
- Test creds: /app/memory/test_credentials.md (admin super@test.com / SuperPass2026!).
- Dev AI-wallet can go negative during testing; top up ai_wallets.balance for QA.
- Metro runs in CI mode → ALWAYS `sudo supervisorctl restart expo` to rebundle FE edits.
- Web preview route for a decision: /prr/{id}?step=2 (hard goto can bounce to
  /auth/login due to rehydration race — retry goto / re-login).

## 4) Active integrations
ScraperAPI (configured, used for Claude import + page crawls), Emergent LLM key
(Gemini/OpenAI/Claude text), Razorpay (test). See PRD.md for the full list.
