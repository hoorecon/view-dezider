# Admin User Guide

**Version:** 1.0 (2026-05-19)
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
