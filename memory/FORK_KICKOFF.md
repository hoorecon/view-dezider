# 🔁 FORK KICKOFF — read me FIRST on every fork (standing operating procedure)

> Purpose: stop context-amnesia after fork/summary. Everything an agent must
> know to continue View Dezider lives here or is linked from here. Keep this
> file SHORT and CURRENT — it is the first thing to read after PRD.md.

## 0) Last user intent (update at end of every session)
- 2026-06-27 (latest): EPIC Phase 1 & 2 (Status filter + Public-template gating) DONE + tested
  (BE 12/12, FE all pass). (1) Solution Box (app/(tabs)/prr.tsx) now has a SECOND chip row of
  STATUS filters under the type chips — Any/Draft/In Progress <35%/35–70%/>70%/Completed
  (testID status-chip-{all,draft,ip_low,ip_mid,ip_high,completed}); selecting refetches
  /api/solution-box?status=<band>. Card status pill reads band+% ("In Progress · 75%" /
  "Completed · 100%" / "Draft"). Bands kept at <35 / 35–70 / >70 (user choice). (2) Public
  Decision Templates can ONLY be created from a COMPLETED (100%) flow — CloneTemplateModal
  greys+locks the "Public" option (testID visibility-public, lock icon, "· Completed only")
  for non-completed flows; Private/Shared allowed any time. Backend guard added in
  routes/decisions/templates.py (save-as-template returns 400 when visibility=public and
  solution_box._progress_decider(original).status != 'completed'). Also switched the modal's
  RN Alert → cross-platform showAlert (src/utils/alert) so web users get visible feedback.
  Build 2026.06.27.002 (v3.86-status-band-filter-public-template-gating).
  ⏭️ NEXT (Epic Phase 3 — NOT STARTED, needs equation specifics from user): publish a flow's
  Option values → Solutions Store (quantitative) / ReviewNet (qualitative) with confirm/override
  + FREE vs Paid toggle generating Karma/Cash; Admin Catalog L0–L3 config (free-usage count +
  payment ranges) driving the payout equation. catalog_nodes already has level 0–3; NO payout/
  free-usage schema exists yet (net-new). Existing bridges: POST /solutions-store/apply-to-option,
  GET /solutions-store/for-decision (store→decision); Phase 3 is the reverse direction.
- 2026-06-26 (latest): Fixed the browser-tab title flashing blank/"frontend"
  before resolving to JELCOS AI. ROOT CAUSE: expo-router static export emitted an
  EMPTY `<title data-rh></title>` FIRST (helmet placeholder) ahead of the real
  +html `<title>`; browsers honour the first <title> → blank tab → app-name
  fallback. FIX: render the brand <title> ONCE via `<Head>` in app/_layout.tsx
  ROOT (this serializes content correctly, unlike page-level Seo Head which
  stayed empty); removed the <title> from +html and from Seo.tsx so there's
  exactly ONE <title>; renamed app.json expo.name "frontend" → "JELCOS AI";
  unified _layout client document.title to match. Verified: every page (index,
  legal/*, contact) has exactly one brand <title>, no empty, no "frontend".
  Also confirmed Contact details ARE Admin-configurable via /admin/appearance
  (legal_name/address/phone/email/website/support_hours) and refreshed those
  field placeholders to the new merchant identity. Build 2026.06.26.008
  (v3.81-fix-title-flash-admin-contact).
- 2026-06-26 (earlier): Razorpay card-activation compliance for jelcos.ai. (a) New
  separate /legal/cancellation route + cancellationPolicy builder (title exactly
  "Cancellation Policy"); refund split out as standalone "Refund Policy" (7–10
  working-day timeline, original-payment-method, duplicate/failed/non-delivery
  rules). (b) Rewrote Terms (14 required sections + decision-support disclaimer),
  Privacy (10 sections + "we do not store full card numbers, CVV, UPI PIN…"
  wording), Delivery (exact JELCOS.AI digital-delivery wording) in
  src/constants/company.ts. (c) Merchant identity updated everywhere: legalName
  "HOORECON IT-Sys Private Limited", merchant website www.jelcos.ai, support
  email support@hoorecon.com, phone 044 4697 2104 (04446972104), support hours
  Mon–Sat 10–6 IST, business type + Razorpay gateway + company website
  www.hoorecon.com — updated frontend COMPANY defaults AND backend
  app_appearance.py DEFAULTS AND the preview-DB app_settings 'appearance' doc.
  (d) MarketingFooter now has a "Merchant Details" block + Cancellation link;
  footer legal links are real <a href> anchors. (e) Seo SITE_URL → www.jelcos.ai;
  legal og:title is now exactly the policy name; sitemap.xml + robots.txt → www
  (robots allows /legal/ + /contact). Verified via expo export: all 7 pages
  (/, /contact, /legal/{terms,privacy,refund,cancellation,delivery}) render full
  static content, no "enable JavaScript", no noindex, www canonical, exact
  og:titles. Build 2026.06.26.007 (v3.80-razorpay-card-compliance-legal).
  ⚠️ PROD ACTIONS NEEDED: (1) Save-to-GitHub → Cloudflare rebuild. (2) On the
  PROD app, update Company Info via Admin → Appearance (prod Mongo has its own
  app_settings doc; the preview DB was updated here but prod is separate) so
  logged-in/JS users see the same merchant identity as the static pages.
  (3) In Cloudflare, ensure a clean non-www → www (or single canonical) redirect
  for jelcos.ai (DNS/Pages custom-domain setting — not in code).
- 2026-06-26 (earlier): Added SEO to the static marketing/legal pages. New
  src/components/Seo.tsx (expo-router <Head>) injects per-page meta description,
  canonical and Open Graph + Twitter Card tags (incl. per-page og:title) on
  index.tsx, LegalShell.tsx and contact.tsx. Added public/robots.txt,
  public/sitemap.xml (home, contact, legal/*), public/og-image.png. Removed the
  hardcoded <title>/<meta description> dup from app/+html.tsx (kept a brand-level
  <title> fallback). KEY LEARNING: expo-router 6 SSG serializes <Head> META tags
  (data-rh) into static HTML but NOT a per-page <title> (no generateMetadata in
  v6.0.24) — so og:title carries the per-page title for crawlers/social; the
  client sets document.title per route. Verified via expo export: title present,
  1 description, per-page og:title (Privacy Policy · JELCOS AI etc), robots/
  sitemap/og-image in dist root. FRONTEND deploy → Save-to-GitHub → Cloudflare
  rebuild. Build 2026.06.26.006 (v3.79-seo-meta-og-sitemap-robots).
- 2026-06-26 (earlier): Made site CRAWLER-READABLE for Razorpay (was a JS-only SPA
  showing "enable JavaScript"). Switched Expo web to `output: "static"` (SSG) in
  app.json — every route now prerenders to real HTML at `expo export`. Fixed the
  homepage (app/index.tsx) to render the marketing landing during static render
  (`typeof window === 'undefined'`) instead of the auth spinner. Footer legal
  links (MarketingFooter.tsx) are now real `<a href>` anchors on web
  (accessibilityRole="link" + href) → /legal/privacy /legal/terms /legal/refund
  /legal/delivery /contact are all crawlable with full content (source: company.ts).
  Verified via local `expo export`: index.html 90KB w/ hero + anchors, legal
  pages 87KB w/ full policy text. ⚠️ This is a FRONTEND deploy → Save-to-GitHub
  triggers Cloudflare Pages rebuild (no EC2 sync needed; CF runs expo export).
  IMPORTANT: when running `expo export` in THIS pod, use an isolated
  METRO_CACHE_ROOT and do NOT restart expo concurrently or the export emits empty
  shells (cache contention). Build 2026.06.26.005 (v3.78-ssg-crawlable-marketing-legal).
- 2026-06-26 (earlier): Seller payout hardening. Payout form (/earnings) now
  collects BOTH UPI (primary) + Bank (fallback, with Account Type from India
  list + Bank Name/Branch auto-filled from IFSC); account is payout-eligible
  only when UPI-format valid AND IFSC validates (free ifsc.razorpay.com) AND —
  when RazorpayX is live — a ₹1 penny-drop passes (skipped while test-mode).
  Admin Payouts writes a tamper-evident audit trail per run (who/when/channel/
  amount/outcome) via payout_audit_log + /admin/payouts/audit-log. /earnings now
  linked from Profile tab. Build 2026.06.26.004 (v3.77-seller-payout-verify-audit).
  Tested 14/14 BE + FE. PENDING: user Save-to-GitHub + EC2 sync.
- 2026-06-26 (earlier): Admin Payouts CHANNEL selector (Manual-IDFC default vs
  (Manual-IDFC default vs RazorpayX). Replaced the two ambiguous triggers with
  ONE unified Run → POST /api/admin/payouts/run {channel}. RazorpayX hard-errors
  (400) if not configured (no silent manual fallback). Removed legacy unused
  endpoints /run-now and /create-manual-batch (now 404) to shrink double-pay
  surface. Tested both BE (7/7 pytest) + FE (Playwright). Build bumped to
  2026.06.26.003 (tag v3.76-payouts-channel-selector).
  PENDING: user to Save-to-GitHub (emergent-v3) + run EC2 sync (see §2).
- 2026-06-26: Fixed AI-chat URL import (ChatGPT React-Router parse + Claude
  snapshot-JSON via ScraperAPI), Gemini = not importable (guard 422),
  review-before-merge modal with drag-reorder, auto-jump to Step 6 + "Top pick"
  spotlight. Build bumped to 2026.06.26.001 (tag v3.75-ai-chat-import-claude-review-reorder).

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
(Gemini/OpenAI/Claude text), Razorpay + RazorpayX (test mode; live approval pending).
RazorpayX adds: free IFSC lookup (ifsc.razorpay.com, no key) + ₹1 penny-drop
fund-account validation (only when RazorpayX is live). See PRD.md for the full list.

## 5) 🚨 UI RULES — DO NOT VIOLATE (user repeated this; stop making them ask)
- **Forms & modals must NEVER stretch to full viewport width on web.** Cap them:
  `maxWidth: ~480-520, width: '100%', alignSelf: 'center'`. Bottom-sheet modals:
  keep `modalBg` as `alignItems: 'center'` + the sheet `maxWidth`. A form that
  spans the whole desktop screen is a BUG, not a layout choice.
- Inputs/labels inside such forms inherit the capped container — never set fixed
  full-width pixel widths.

