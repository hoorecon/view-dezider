# Admin User Guide

**Version:** 3.21.0 (2026-07-13)

> **v3.21.0 additions:** **AI Assistant** (More Tools) now runs on **Anthropic Claude (claude-sonnet-4-6)** by default via the AI wallet; when a user's credits/quota run out it automatically switches to `gpt-4.1-mini` so answers keep flowing (the reply shows which model answered). **AI Wallet** screen now offers **card payment via Stripe** (USD/INR toggle + a "Card" button per pack) in addition to Razorpay (₹). **WhatsApp gate:** turning ON "Skip WhatsApp Gate" (Admin → Settings) now also applies to brand-new sign-ups/registrations (previously only to later logins).
**Audience:** Anyone with admin/super_admin/co_admin role
**Purpose:** Explain every Admin Panel menu item — what it does, when to use it, and a sample workflow.

---

## How to Read This Guide

Each section follows the same structure:
- **Purpose:** What this page exists for
- **Sidebar location:** Where to find it
- **Required role:** admin / super_admin / co_admin
- **How to use:** Step-by-step
- **Sample config:** What to enter for the first time
- **Linked APIs:** Backend endpoints called

---

## OVERVIEW Section

### 📊 Dashboard (`/admin`)

- **Purpose:** Single-pane-of-glass for org KPIs (active users, decisions in progress, ACM modules count, recent activity).
- **Required role:** Any admin.
- **How to use:** Land here after login. Stat cards refresh on page load. Click any stat to drill into the corresponding admin sub-page.
- **Sample config:** No setup needed — it's a read-only view of live data.
- **Linked APIs:** `GET /api/admin/tier-matrix`, `GET /api/admin/customer-segments`, `GET /api/admin/pricing`, `GET /api/acm/health`.

### ⏱️ Audit Trail (`/admin/audit-trail`)

- **Purpose:** Immutable log of every privileged action — credential updates, ACM seed, role changes, integration edits.
- **Required role:** super_admin (full view), admin (own actions only).
- **How to use:** Filter by event_type, actor, or date range. Use this when investigating a security event ("who changed the Razorpay key on 2026-05-18?").
- **Sample config:** Nothing to set — events auto-write to `audit_log` collection.
- **Linked APIs:** `GET /api/admin/audit-trail?from=...&to=...&actor=...`

### ⚠️ Incident Response (`/admin/incident-response`)

- **Purpose:** Track and resolve operational incidents (downtime, data anomalies, abuse reports).
- **Required role:** admin.
- **How to use:** Create a new incident → assign severity P0/P1/P2 → log timeline updates → close with RCA.
- **Sample config:** First incident as a smoke test: severity=P2, title="Test incident", reporter=yourself, mark "Resolved" in 5 min.

---

## PEOPLE & ACCESS Section

### 👥 Org Members (`/admin/org-members`)

- **Purpose:** Manage who can join your org, their roles, and offboarding.
- **Required role:** admin.
- **How to use:** Invite by email → assign role (user / decision_owner / co_admin / admin) → resend invite if expired.
- **Sample config:** Add `colleague@example.com` as `user` role. Verify they get a magic-link invite email (or, on the test stack, that the row appears with status=pending).

### ⭐ Experts (`/admin/experts`)

- **Purpose:** Curate the directory of subject-matter experts users can book for decision consultations.
- **Required role:** admin.
- **How to use:** Add expert → upload bio + photo → set hourly rate + availability → approve. Once approved, they're discoverable in /tools/expert-net.
- **Sample config:** Add an internal expert: name="Sample Expert", domain="Finance", rate=₹500/hr, available_slots=5.

### ✅ Pending Approvals (`/admin/pending-approvals`)

- **Purpose:** Inbox for all human-in-the-loop approvals — new org signups, expert applications, refund requests.
- **Required role:** admin.
- **How to use:** Click each item → review the supporting evidence → approve / reject / request more info.
- **Sample config:** Walk through any 1 pending item to learn the flow. Reject test items so the queue stays clean.

### 🛡️ Access Control (`/admin/acm`)

- **Purpose:** View the **Access Control Matrix** — which user types can access which modules/features. This is the **source of truth** for feature gating across the entire app.
- **Required role:** admin.
- **How to use:** Each row = a user_type, each column = a module/feature. Cells are read-only in v1 (gated at code-level). v2 will allow per-org overrides.
- **Sample config:** Confirm seed is in place — should show 7 user_types × 32 modules × 89 features. If empty, run `POST /api/acm/seed?force=true`.

---

## SUBSCRIPTIONS & GTM Section

### 🔲 Tier Matrix (`/admin/tier-matrix`)

- **Purpose:** **THIS is the WOWO subscription-tier × module/feature mapping.** Define which modules and individual features are unlocked at which of the 7 chakra tiers (Root → Crown).
- **Required role:** admin.
- **How to use:**
  - Rows = ACM modules (collapsible to show child features)
  - Columns = 7 chakra tiers
  - Click a cell to toggle the module/feature on/off for that tier
  - Changes apply instantly
- **Sample config:** Verify that "PRR Decision Tool" is enabled across all tiers (since it's core). Verify "AI Chat" is enabled only from Heart Chakra (Anahata) and above. Toggle a non-critical feature like "Voice Browsing" to see the UI update.
- **Linked APIs:** `GET /api/admin/tier-matrix`, `PATCH /api/admin/tier-matrix/{module_id}/{feature_id}/{tier_key}`.

### 👥 Customer Segments (`/admin/customer-segments`)

- **Purpose:** Define customer segments (Student, Professional, Enterprise, etc.) and the recommended tier for each. Drives the "best fit for you" pricing recommendation.
- **Required role:** admin.
- **How to use:** Add segment → set demographic attributes (income, profession, age) → assign recommended tier. The pricing page uses this to highlight the right tier per visitor.
- **Sample config:** Add segment "Solo Entrepreneur" with recommended_tier="Sacral Chakra (Svadhisthana)".

### 🏷️ Pricing Page (`/admin/pricing`)

- **Purpose:** Preview of the public `/pricing` page, rendered inside admin shell. Shows tier cards + module-availability matrix (read-only).
- **Required role:** admin.
- **How to use:** To EDIT pricing → go to Tier Matrix and Customer Segments. This page is for previewing what end-users see.
- **Sample config:** Just visit and verify all 7 tiers show price + aspiration + perks.

---

## CATALOG & EXPERIENCE Section

### ⚙️ Decision Modes (`/admin/decision-modes`)

- **Purpose:** Configure the available "decision-making modes" (solo, consultative, consensus, autocratic) and their meta-config.
- **Required role:** admin.
- **How to use:** Add/edit modes → set "min_participants", "voting_method", "default_template".
- **Sample config:** Default 4 modes shipped. Disable any mode not relevant to your org (e.g., remove "autocratic" for democratic-only orgs).

### 📄 Templates (`/admin/templates`)

- **Purpose:** Manage pre-built decision templates that appear on the user's "New Decision" wizard ("Buy a House", "Hire a candidate", etc.).
- **Required role:** admin.
- **How to use:** Create template → define starter factors + options → set category. Users will see it in the wizard's "Start from template" tab.
- **Sample config:** Add template "Choose a coding bootcamp" with 3 factors (cost, duration, placement_rate) and 0 options (user adds their own).

### 🎓 Social Learning (`/admin/catalog/social-learning`)

- **Purpose:** Curate community case-studies and decision archetypes that appear in the Social Learning module.
- **Required role:** admin.
- **How to use:** Add case-study → upload thumbnail + summary → tag with module (PRR/SWOT/etc.).
- **Sample config:** Add 1 sample case "How a startup chose its first city" tagged with PRR + Pros&Cons.

### 👍 ReviewNet (`/admin/review-net`)

- **Purpose:** Manage user reviews and expert ratings.
- **Required role:** admin.
- **How to use:** Browse all reviews → moderate offensive content → respond on behalf of the org.
- **Sample config:** Review queue should be empty on a fresh install — that's correct.

---

## SYSTEM Section

### 📚 Admin Docs (`/admin/docs`)

- **Purpose:** AI-generated documentation hub (PRD, SRS, UAT, Regression Tests, API Catalog). Powered by the Emergent LLM.
- **Required role:** admin.
- **How to use:** Switch tabs at top → click "Refresh All" to regenerate from current code/spec.
- **Sample config:** Pre-generated content ships with the app. AI regeneration is paused if LLM budget is capped (you'll see a graceful 503 message).

### 📖 Handbook (`/admin/handbook`)

- **Purpose:** Static markdown documentation that ships with the codebase — PRD, SRS, API_REFERENCE, UAT, DEPLOYMENT, PRODUCTION_DEPLOYMENT runbook, this Admin User Guide, etc. Works without LLM.
- **Required role:** admin.
- **How to use:** Click any card to read the full markdown rendered in-browser.
- **Sample config:** Read PRODUCTION_DEPLOYMENT.md first if you're onboarding to ops.

### 🛟 Admin User Guide (`/admin/handbook/ADMIN_USER_GUIDE`)

- **Purpose:** **This very document.** Onboarding reference for new admins.
- **Required role:** admin.
- **How to use:** Bookmark it. Share the URL with any new admin you onboard.

### ⚙️ Settings (`/admin/settings`)

- **Purpose:** Configure 3rd-party integration credentials (Razorpay, Exotel SMS, DigiLocker eKYC, UltraMsg WhatsApp, Google Calendar, Emergent LLM Universal Key).
- **Required role:** admin.
- **How to use:**
  1. Click "Configure" on the integration you want to enable
  2. Fill in the keys/secrets from the provider dashboard (see docs link on each card)
  3. Toggle "Enable" ON
  4. Click "Save credentials" — masked confirmation shows the value is stored
  5. Click "Test" to verify required fields are present (Phase 2 will do a real ping)
- **Sample config:** Enter Razorpay TEST keys (from https://dashboard.razorpay.com/app/keys) → enable → save → test → ✅ green.
- **Security:** All secrets stored encrypted in MongoDB `integrations` collection. NOT in .env. Hot-reloads — no container restart needed.
- **Linked APIs:** `GET/PUT /api/admin/integrations/{provider}`, `POST /api/admin/integrations/{provider}/test`.

---

## Switching Between Admin and User Views

Top-right of the admin panel has a **"User View"** button (open-outline icon). Click it to switch to the user-facing app. From the user app, the top-right has a **shield-checkmark** icon — click it to switch back to admin.

**Both directions force a full page reload** (web) to keep the React Router state clean. This is intentional and prevents the "blank page" or "redirected to login" bugs we saw early in development.

---

## Logout

Bottom-left of the sidebar (next to your name + role badge): the **log-out icon** + "Logout" text. Click to:
1. Invalidate your session token on the backend
2. Clear local storage
3. Redirect to `/admin/login`

After logout, admin URLs are protected by the auth guard — any further attempt to access `/admin/*` redirects back to `/admin/login`.

---

## Common Admin Workflows

### Onboarding a new admin
1. Org Members → invite by email with role=`admin`
2. They accept invite → set password
3. You point them to: `https://www.jelcos.ai/admin/handbook/ADMIN_USER_GUIDE`
4. They walk through this guide top-to-bottom (~30 min)

### Going live with payments
1. Settings → Razorpay → enter LIVE keys (not test) → enable
2. Pricing Page → verify tiers display correctly
3. Customer Segments → verify recommended tier per segment
4. Audit Trail → confirm the integration_updated event was logged

### Investigating a user-reported issue
1. Audit Trail → filter by user_id and event_type
2. Incident Response → create an incident with the timeline
3. Org Members → check user's role and last login
4. Decision Modes/Templates → verify the feature they used isn't disabled

### Adding a new chakra tier perk
1. Tier Matrix → toggle the desired feature ON for that tier
2. Pricing Page → preview to confirm it appears in the matrix
3. Customer Segments → if the new perk targets a segment, update recommendation
4. Save → no restart required

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Sidebar item click shows blank page | Page-level component missing `flex:1` | Bug report to dev team — see `frontend/app/admin/*.tsx` |
| Icons showing as empty squares | Ionicons font not loaded | Hard refresh (Ctrl+Shift+R). If persists, dev to verify `frontend/public/fonts/Ionicons.ttf` exists in build output |
| "Not authenticated" on admin API call | Session expired (24h TTL by default) | Re-login via `/admin/login` |
| Integration Test button says "Missing fields" | Required fields blank | Settings → Configure that integration → fill required fields → Save → Test again |
| `/admin/docs` AI docs are blank | LLM budget capped on Emergent | Use `/admin/handbook` for static docs instead |
| Can't see expected sidebar items | Your role is not admin | Org owner / super_admin must promote you (Org Members → edit your row → role=admin) |

---

## Where Things Live (for technical curiosity)

- **Frontend:** React Native Web (Expo SDK 54) → hosted on Cloudflare Pages → `https://www.jelcos.ai`
- **Backend:** FastAPI + Motor (async MongoDB) → AWS EC2 ARM → `https://api.jelcos.ai`
- **Database:** MongoDB Atlas free tier (M0, ap-south-1) → `cluster0.c39ovvo.mongodb.net`
- **Source code:** GitHub `hoorecon/view-dezider` branch `emergent-v3`
- **Code edits:** Authored in Emergent platform → pushed via "Save to GitHub" button → Cloudflare auto-builds, EC2 needs `git pull + docker compose up --build`

For deeper technical detail, see `PRODUCTION_DEPLOYMENT.md` in Handbook.

---

**Need help?** Ping #admin-ops Slack channel or email support@emergent.sh. For platform-specific support, your Emergent account dashboard has a "Contact Support" button.

*This guide is auto-served from the codebase. To update it, edit `/app/docs/ADMIN_USER_GUIDE.md` and push to GitHub `emergent-v3`.*

---

## v3.16.0 — New Admin Pages (2026-06-12)

### 💳 AI Wallet Config (`/admin/ai-wallet-config`)

- **Purpose:** Govern the AI cost economics — provider pricing, the **precise** (Claude) tier multiplier, the auto-grouping threshold for URL Import, and refill packs.
- **Required role:** super_admin.
- **How to use:**
  1. **Pricing fields** — set `blended_usd_per_mtok` (Fast tier, Gemini/Groq) and `precise_usd_per_mtok` (Claude). The "Precise tier credit multiplier ×N" row recomputes live.
  2. **Markup** — `markup_user_pct` is your gross margin slice on every paid AI call. ⚠️ Note the structural recon insight: with Razorpay Route sending markup to the linked account, raise this if you need per-txn `buffer ≥ 0`.
  3. **Import group threshold** — `import_group_threshold` (default 15). Pages with `factors > threshold` and no page-defined groups get AI-grouped; smaller pages stay flat. Tune higher for verbose marketplaces.
  4. **Refill packs** — edit price/credit ratios for the buy-credits modal users see.
  5. Save → no restart needed; next AI call honours the new config.
- **Linked APIs:** `GET/PUT /api/admin/ai-wallet/config`, `POST /api/admin/ai-wallet/grant`, `GET /api/admin/ai-wallet/users`.
- **Sample config:** `blended_usd_per_mtok=2.5`, `precise_usd_per_mtok=18`, `markup_user_pct=35`, `import_group_threshold=15`.

### 💰 Revenue Reconciliation (`/admin/recon`)

- **Purpose:** Per-transaction tally of money we collected (Razorpay) vs money we paid the LLM provider (Gemini via BigQuery Billing Export). Surfaces `at_loss` rows so we can catch structural margin slippage before the month closes.
- **Required role:** **super_admin only** (regular admins get 403).
- **How to use:**
  1. **Configure GCP** (one-time per environment) — tap "Configure GCP" → paste base64-encoded Service-Account JSON + `project_id` → Save. The JSON is stored encrypted; the UI never echoes it back.
  2. **Sync Now** — pulls Razorpay (payments + transfers + settlements, incremental 5-day overlap) and GCP billing export. Idempotent; safe to run multiple times a day.
  3. **Verdict banner** — green "safe" / red "at_risk" based on the latest tally. At-risk surfaces the structural fix (raise `markup_user_pct` in AI Wallet Config OR retain part of markup in primary account).
  4. **8 KPI cards** — net collected, total markup, total LLM cost, gross buffer, etc.
  5. **Transactions table** — per-payment tally. Red rows = `at_loss=true`.
  6. **Daily tally** — token-derived ₹ estimate vs GCP actual ₹ variance.
  7. **Export CSV** — pick a month → downloads `transactions-YYYY-MM.csv`.
- **Daily auto-sync** — backend startup task runs sync every 24h.
- **Sample workflow:**
  - After enabling paid AI for a new region: run RC-02 (Sync Now) → RC-03 (inspect tally) → if `at_risk`, jump to AI Wallet Config and raise `markup_user_pct` → re-sync → verdict should flip to safe.
- **Linked APIs:** `GET /api/admin/recon/summary`, `GET /api/admin/recon/transactions`, `GET /api/admin/recon/daily`, `POST /api/admin/recon/sync`, `GET/PUT /api/admin/recon/gcp-config`, `GET /api/admin/recon/transactions.csv`.

### 🔍 PostHog Analytics & Replays (external)

- **Purpose:** Product analytics + web session replays for usability research.
- **Required role:** read-only — admins read on `eu.posthog.com` project 199570.
- **Privacy posture (memorise this):** Only `user_id` is sent. No email, phone, name, Aadhaar, or PAN. Inputs are masked at the DOM level. Network bodies (payment payloads, JWTs) are NOT recorded. Replays on web only.
- **How to use:**
  1. Log into PostHog EU (`https://eu.i.posthog.com`).
  2. Switch to project 199570.
  3. Live events tab — verify `signup`, `login`, `decision_created`, `payment_success`, `ai_credits_consumed` flow in real time.
  4. Session Replay tab — pick a recent session → scrub to inspect UX friction.
- **Operational gotcha:** Replay does NOT work on Expo Go (native) — only on the web build. Bot/headless detection silently blocks captures; production users unaffected.

### Common v3.16 workflows

#### Onboarding GCP for Revenue Recon
1. In Google Cloud Console → Billing → Export to BigQuery → enable.
2. Create a Service Account with roles: **BigQuery Data Viewer** + **BigQuery Job User**.
3. Download SA JSON → `base64 -i sa.json` → copy result.
4. Admin → Revenue Recon → Configure GCP → paste base64 + project_id → Save.
5. Tap "Sync Now". After 30s, the verdict banner + KPI cards populate.

#### Setting up paid AI for a new region
1. AI Wallet Config → tune `markup_user_pct` (≥ 35% recommended to absorb Razorpay Route).
2. AI Wallet Config → verify `precise_usd_per_mtok` matches the current Claude pricing.
3. Tier Matrix → unlock `url_import_precise` for Heart Chakra and above.
4. Revenue Recon → Sync Now → confirm verdict=safe.
5. Customer Segments → add the new region's currency + tier pricing.

---
## Import-URL Intelligence (v3.17.0)

**Where:** Sidebar → Overview → *Import-URL Intel* (`/admin/import-analytics`). Super-admin only.

**What it shows:** every Import-from-URL run — the user's URL, the 4 accuracy
hints, chosen AI engine, the LLM-classified page type (Comparison Matrix /
Listing-Filter / Detail / Search Grid / Article Round-up), the pipeline route,
factors/options produced, hint pass/fail, latency, ~tokens and the user's 👍/👎
verdict.

**How to use it for prompt tuning:**
1. Watch the *Hint pass* and *👍 Satisfaction* KPIs per page type.
2. A page type trending down? Open its runs → drill-down shows the EXACT
   system prompt sent (incl. its PAGE-TYPE GUIDANCE block) and the raw LLM
   response — compare against the user's hints to spot the failure pattern.
3. Prompt bodies are kept 90 days; run metadata is kept forever for trends.

**Playbook when a user reports a bad import:** Runs list → filter by page type
or find the URL → drill-down → check `hint_warnings`, retry flag and the raw
response before deciding whether the prompt or the page is at fault.

---
## Notification Engine (v3.18.0)

**Where:** Admin home → *Notification Engine* tile (`/admin/notification-engine`). Super-admin only.

**What it is:** a generic, reusable alerting hub. You create *triggers* from a
catalogue of trigger events; each trigger sends to **Email** (Resend, branded
HTML) and/or **WhatsApp** (UltraMsg, short text + deep link) — both channels
have independent ON/OFF toggles and their own recipient lists.

**Trigger kinds:**
- **Scheduled** — daily / weekly / monthly at HH:MM in any timezone. The
  built-in *Weekly Import Analytics Digest* (`import-analytics`) is seeded at
  **Monday 09:00 IST**: last-7-days runs, success %, hint pass, per-page-type
  table, top failures and 👍/👎 feedback.
- **Event** — fires instantly from inside the product. *Import Run Failure
  Alert* (`import-run-failed`) pings you when a URL import errors; the
  per-trigger **throttle** (default 60 min) prevents alert storms.

**How to use:**
1. Open the trigger card → toggle Email/WhatsApp pills, or Edit to manage
   recipients (email chips) and numbers (country code + number, e.g.
   `919876543210`).
2. Tap **Test now** to send immediately — you get a per-channel delivery
   report (e.g. ✉ 1/1 · 💬 1/1) and the run shows in *Recent dispatches*.
3. **New Trigger** lets you bind any registered event again with a different
   schedule/recipient set (e.g. a second digest for the leadership list).
4. Master ON/OFF switch pauses a trigger without losing its configuration.

**Ops notes:** dispatches are logged (newest ~500 kept); the scheduler ticks
every 60 s and survives restarts (next-run times are stored in MongoDB);
new trigger events only need a backend builder function — the UI picks them
up automatically from the registry.


---
## v3.19.0 — Conflict Breaker Voice Input + Audio-Storage Knobs (2026-06-15)

### Dashboard reshuffle you'll see in the app
Sections are now cleanly numbered §1-§9 with **Quick Links** pinned on top:
1. Self Discovery · 2. Decision Kickstarters · 3. **Inner Wellbeing** (renamed from "Inner State") · 4. Goals & Manifestation · 5. **Execute & Track** (now includes Lifestyle Dezider) · 6. **Reflection & Awareness** (consolidated 8-tile section) · 7. Collaboration & Management · 8. Solution Space · 9. More Tools.
"Public Pulse" has been renamed **"Life Mirror"** to better invite first-time users into the self-discovery quiz. The legacy "Lifestyle Architecture" section is gone — its two tiles moved to §5 and §6. Route paths are unchanged so existing deep links / WOWO entries still work.

### 🎙️ Voice Input in The Conflict Breaker
Every text field across the 9-stage wizard now has an inline mic chip. After recording, the user picks one of two intuitive actions:
- 📝 **Transcribe to Text** — Whisper turns speech into English text and appends it to the field (cost: per-second AI credit, ~0.5 cr/sec at default config).
- 💾 **Save as Audio** — the raw clip is persisted to disk and listed below the field as a playable chip (play/pause + size + retention + delete). Cost: storage-credit charge shown inline BEFORE the user commits.

The cost-estimate chip on the "Save Audio" button reads live config — change the rates below and the next click reflects them instantly.

### 💳 AI Wallet Config — 4 new audio-storage knobs (`/admin/ai-wallet-config`)

| Field | Default | Range | What it controls |
|---|---|---|---|
| **Audio storage $/GB-month** | `$0.023` | ≥ 0 | Base cloud-storage cost basis. The default is AWS S3 Standard; change if you move to S3-IA, GCS Coldline, etc. |
| **Audio retention (days)** | `90` | 1-365 | How long a clip is kept on disk. Users are billed for the FULL retention up-front (zero-loss). |
| **Audio storage markup %** | `30%` | 0-500 | Hidden margin layered over the raw storage cost. |
| **Audio max upload size (MB)** | `10` | 1-100 | Per-clip upload cap. Larger files rejected up-front so users are never surprise-charged for an oversized clip. |

**Math (same zero-loss invariant as LLM tokens):**
```
usd     = bytes × (usd_per_gb_month / 1024³) × (retention_days / 30)
          × (1 + markup_pct / 100)
credits = usd ÷ ((tokens_per_credit / 1_000_000) × blended_usd_per_mtok)
```

**Worked example at defaults** — a 30-sec opus clip (~200 KB) at 90-day retention, 30% markup, `blended_usd_per_mtok=2.0`, `tokens_per_credit=100`:
- raw storage = 200×1024 × (0.023/1024³) × 3 = **$1.32e-5**
- with markup = $1.72e-5
- credits = $1.72e-5 ÷ $0.0002/cr = **≈ 0.09 cr** (rounded up to 4 dp)

A 5-MB clip at the same settings = ~2.2 credits. A user with a fresh 20-credit wallet can save ~225 short clips before needing a top-up.

**How to use:**
1. Open `/admin/ai-wallet-config` → scroll past the ScraperAPI block → the four `Audio …` fields are at the bottom of the Pricing block.
2. Change a value (e.g. drop retention to 30 days for a freemium tier) → Save.
3. No restart needed; the next `Save Audio` press in Conflict Breaker reflects the new rate, and the cost-estimate chip on the button updates instantly.

**Linked APIs:**
- `GET/PUT /api/admin/ai-wallet/config` (the same endpoint that powers all other AI Wallet fields; the new 4 keys are now whitelisted)
- `GET /api/conflict-breaker/audio/estimate?bytes=N` (read-only preview)
- `POST /api/conflict-breaker/sessions/{id}/audio/upload` (charges storage)
- `POST /api/conflict-breaker/sessions/{id}/audio/transcribe` (charges AI credits)
- `GET /api/conflict-breaker/audio/{audio_id}` (auth-gated playback)
- `DELETE /api/conflict-breaker/audio/{audio_id}` (no credit refund — clip already stored)

**Operational notes:**
- Ledger key for the charge: `feature="conflict_breaker_audio"` (storage) and `feature="cb_voice_transcribe"` (Whisper). Revenue-recon will split these cleanly.
- Files live under `/app/backend/uploads/conflict_audio/{user_id}/{audio_id}.{ext}`. Plan disk-pressure alerts accordingly. (Auto-purge cron deferred to v3.20.)
- The user-facing wallet panel does NOT itemise "audio storage" separately yet — show users the running balance as a single number for now.


---

## Life Goals & Import-from-File (v3.20.0 · 2026-06-28) — admin/ops notes

**Life Goals ("My 360° Life" → Life Goals tab)**
- Data lives in the existing `gem_goals` collection (no new collection). A Life Goal is a GEM goal with
  `lg_mode` ('timeline'|'tree'), `lg_level` (1-7), `parent_id`, `horizon`, `sub_type`. They surface in the
  normal GEM goal lists/dashboards, so support can inspect them via the same admin tooling as GEM goals.
- No admin config knobs — it's an end-user planning surface. Sub-types are fixed in code/order.

**Import from File (MyDezider Step 2 → "File")**
- AI usage is **metered through the AI Wallet** exactly like URL import: the extraction call (and each
  web-enrichment call when "Also research the web" is on) debits the user's wallet. Fast tier uses the
  Gemini free-tier first; Precise tier uses a Claude-grade model and costs more credits.
  - Ledger features to watch in Revenue-Recon: `feature="file_import_extract"` and `feature="file_import_enrich"`.
- Web enrichment uses DuckDuckGo search (no key) + LLM synthesis, capped at 8 options per import.
- If a user is out of credits, extraction returns **402**; enrichment failures are best-effort and never
  fail the whole import. Uploads are capped at **8 MB**; legacy `.doc` is rejected (ask for `.docx`/PDF).
- The post-import "Fetch My Best Factors" prompt reuses the existing plan-capped `tp_best_factors` flow
  (default cap 25 factors), so no separate quota to manage.

