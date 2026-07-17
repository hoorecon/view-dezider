# 🔁 FORK KICKOFF — read me FIRST on every fork (standing operating procedure)

> Purpose: stop context-amnesia after fork/summary. Everything an agent must
> know to continue View Dezider lives here or is linked from here. Keep this
> file SHORT and CURRENT — it is the first thing to read after PRD.md.


> 🚨 **DEPLOY / OPS + INCIDENT RUNBOOK: `/app/memory/DEPLOY_OPS_RUNBOOK.md`** —
> READ IT before any deploy, build-stamp bump, or "my data is gone" report.
> It has the prod topology (EC2 `deploy-api-1`, **Atlas `dezider`**, Cloudflare-Pages
> frontend), the build-stamp rule, the post-deploy per-module verification checklist,
> and the data-loss incident runbook. Owner has been burned by agents forgetting this.

## 0) Last user intent (update at end of every session)
- 2026-07-17 (fork — Solution Finder UX + Pros&Cons Step4/5/7/8 + PROD INCIDENT):
  (A) DONE+TESTED (testing_agent, 2 rounds, all PASS): Solution Finder — clickable breadcrumbs,
      AI-credits meter row (Q3/Q4), Step-4 & Step-5 hierarchy trail chips + Expand/Collapse-all,
      Step-5 action items colour-coded by source (solution/mitigation/contingency) + Download PDF
      (402→store) + Share (ReportShareSheet). Pros&Cons — Step-4 sub-factor chip web tooltip (WebTitle
      div), Step-5 ALL operators common to both types, Step-7 Show/Hide-Realistic-Gap toggle + per-factor
      reveal + option-name wrap, Step-8 Case-1 vs Case-2 comparison table + Mandatory/Optional relabel +
      Quantitative/Qualitative type chips (preselected from Step-5) + `|` separator + multi-select
      improvability (`y_both`) + "Compare all options" winner bar. Pre-prod regression: BE 21/21, FE 4/4 PASS.
  (B) 🔥 PROD INCIDENT (MyDezider looked "empty" right after deploy; owner feared data loss).
      ROOT CAUSE = NOT data loss. Atlas `dezider` had all 47 decisions the whole time. The
      `dezider-list.tsx` fetch `catch` only logged and left items=[] → rendered the SAME "No Decisions
      Yet" screen as a truly-empty account. During deploy the backend workers were still booting
      (health-check attempts 1–2 failed) + Cloudflare Pages mid-propagation, so the one focus-time fetch
      came back empty and stuck (no auto-retry). Owner opened MyDezider in that window; Pros&Cons/Solution
      Finder were opened after healthy → they showed data. A plain refresh fixed it (proof: no data change).
      FIX SHIPPED (build v3.102): dezider-list now distinguishes load-error from empty → shows
      "Couldn't load — your data is safe — Retry", never wipes loaded items.
      ⏭️ TODO: apply the SAME load-error/Retry guard to Pros&Cons, Solution Finder, and SWOT list screens.
  (C) Build stamps this session (hand-bumped README, auto-bump-on-Save was NOT firing):
      2026.07.17.001 (v3.101-solfinder-ux-proscons-step8) → .002 (v3.102-dezider-list-load-error-guard)
      → .003 (v3.103-solfinder-pdf-hierarchy-groups-ailimits).
  (D) DONE+TESTED (iter186, FE+BE all PASS): Solution Finder report PDF — hierarchy column now shows the
      FULL path (Concern › Root Cause › Solution › ⚠ Risk, no truncation, RCA no longer missing); Action
      Plan split into "Solution / Risk Mitigation / Risk Contingency Actions" subsections; Action Plan
      starts on a fresh page (PageBreak). AI auto-fill now opens a LIMITS pop-up: Q3 "Max Solutions per
      Root Cause" (default 2, 1–10); Q4 "Max Risks per Solution / Max Mitigations per Risk / Max
      Contingencies per Risk" (each default 2, 1–10). Enforced BOTH frontend (stepper clamp) AND backend
      (`_lim()` clamp 1–10 in routes/tools.py + prompt + slice) so the "172 action items" explosion is
      architecturally impossible. PDF renderer gained a `page_break` section flag (decision_reports.py).
  (E) DONE+VERIFIED (build v3.104): Solution Finder step-breadcrumb icons now show web hover tooltips
      (WebTitle → real <div title> "N. Title — desc"); added "Clear all (N)" reset button at top of
      Q2 RCA / Q3 Solutions / Q4 Risks (cascades: clearing RCAs also clears solutions/risks/mits/cons;
      clearing solutions clears risks/mits/cons; confirm dialog before wiping). NOTE: user said "Pros &
      Cons flow" but the icon breadcrumbs + RCA/Solution/Risk pages are SOLUTION FINDER (P&C wizard has no
      icon breadcrumbs) — implemented in Solution Finder.

- 2026-07-02 (fork — Anthropic-in-AI-Assistant + Stripe integration):
  (A) ANTHROPIC as DEFAULT in AI Assistant (More Tools). `routes/ai_assistant.py` now routes
      send_message + quick_ask through a shared `_assistant_reply()` → `metered_chat(tier="precise")`
      = Claude (claude-sonnet-4-6) via the AI wallet. On `InsufficientCredits` (quota exhausted) it
      falls back to gpt-4.1-mini so the assistant keeps replying. Response includes `model` label.
      VERIFIED: credits→claude-sonnet-4-6; balance 0→"gpt-4.1-mini (quota fallback)".
  (B) STRIPE (alongside Razorpay) — new `routes/stripe_payments.py` (prefix /api/stripe): /checkout,
      /status/{id} (poll+fulfil), /webhook (verified if STRIPE_WEBHOOK_SECRET set, else parses),
      /health. Flows built+TESTED: kind="ai_wallet" (reuses ai_wallet packs pricing + `_credit_refill`
      → ai_wallet.grant) and kind="subscription" (reuses subscriptions.apply_charge). Fulfillment is
      idempotent via atomic pending→completed flip on `stripe_payments` (verified: no double-grant).
      Currency USD or INR (server-side pricing via core.ai_billing; USD = price_inr/fx). Frontend:
      `src/utils/stripeCheckout.ts` (web redirect + native auth-session + poll), `app/checkout-result.tsx`,
      and AI Wallet screen now has a USD/INR toggle + "Card" (Stripe) button per pack.
      ⚠️ Pod STRIPE_API_KEY is a PLACEHOLDER ("sk_test_emergent") → live session creation returns 401
      until a REAL Stripe test/live key is injected (added to backend/.env; replace on deploy). Money
      paths tested directly (DB-level) since a live Stripe call needs the real key.
      NOT YET DONE (immediate follow-up): Stripe UI on subscription-plans.tsx (backend ready) and the
      MARKETPLACE/solutions-store flow (kind not built — store fulfillment is SKU/entitlement/payout-based).
  (C) NOTE: "Sign in with Google" (Emergent-managed) was already fully implemented — no change needed.
- 2026-07-02 (fork — operators-common + WhatsApp-gate register fix): build 2026.06.29.002 → see below.
  (1) EC2 Docker build was failing at `pip install` (ResolutionImpossible): `opencv-python==4.13.0.92`
      declares numpy>=2 but `numpy==1.26.4` is pinned (mediapipe needs <2). FIX: pinned
      `opencv-python==4.11.0.86` (matches opencv-contrib/headless; numpy<2 OK). Verified imports +
      `pip install --dry-run` resolves. This is a backend/requirements deploy fix only.
  (2) "Skip WhatsApp Gate" (Admin → Settings) wasn't reflecting for freshly-registered users: the
      /auth/register response HARD-CODED whatsapp_verified:false (and /auth/google/session used the raw
      stored flag) while only /auth/login + /auth/me applied effective_whatsapp_verified(). FIX: both
      register + google-session now return `await effective_whatsapp_verified(user_doc)`. Frontend gate
      (_layout.tsx:288) trusts that flag. Verified via curl (register → whatsapp_verified:true when gate ON).
  (3) Operators are now COMMON to both Quantitative & Qualitative factors (user request). Added
      ALL_OPERATORS (decisionHelpers.ts) = numeric (≥ ≤ > < = ≠) + text (Contains/Starts with/Ends with/
      Equals/Not equals); Step2.tsx renderCriteria always shows the full list. Default is AUTO-SELECTED by
      the expected VALUE type (numeric→">=", text→"contains") but user can override to any. Backend
      set-expectations (url_analyze.py) now derives operator+data_type from the ACTUAL value (regex numeric
      test) — a text value even on a Quantitative factor (e.g. Role/Title="Managing Partner") gets
      "contains", never ">=". EXPECTATIONS_SYSTEM prompt updated to enforce value-typed operators.
      Verified: FE screenshot shows all 11 operator chips; BE coercion unit-checked. Build 2026.07.02.001.
- 2026-06-29 (fork — Financial Model + Zoho verify/polish): smoke-tested all FM endpoints (3-statement,
  DSCR/ratios, IIMB DCF, Investor/CMA xlsx+pdf exports, template import, Zoho live sync + nightly autosync
  snapshot). All PASS, nothing mocked. Build 2026.06.29.001.
- 2026-06-27 (latest, fork — REAL-FLOW step contribution for ALL 3 modules, built on share-step):
  User clarified "Contribute" must open the SAME module flow scoped to a step (Google-Docs-style), NOT a
  text box / PDF. RETIRED the collaboration-session text box. Built on the existing share-step system.
  • Backend (routes/decisions/sharing.py): added module + step_access to shares; ShareStepRequest gains
    step_access. New endpoints: GET /shared-steps/{id}/decision (recipient-read for decision),
    DELETE /shared-steps/{id}/contribution (withdraw), POST /shared-steps/create (module-aware: decision|
    pros_cons|swot|solution_finder), POST /shared-steps/{id}/open (decision→read owner doc; others→create
    per-recipient sandbox CLONE in same collection, user_id=contributor, tagged contribution_clone).
    contribute is module-aware (clone snapshot for non-decision). Clones filtered out of pros_cons list,
    solution-finders list (tools.py), and solution_box aggregator.
  • Frontend: MyDezider (prr/[id].tsx + DecisionContext) = Contribution Mode (loads owner decision via
    share, LOCAL-only edits, jumps to step, banner, only-target-step, "Submit my contribution"→/contribute).
    Pros&Cons (pros-cons-wizard) + SolutionFinder (solution-finder) = open CLONE via /open, edit natively,
    banner+inline Submit, step scoping. inbox.tsx "Open & contribute" (was simplified modal) now navigates
    into the real flow (+Edit/Withdraw). ShareStepModal is module-aware (posts /shared-steps/create for
    pros_cons/swot/solution_finder) + a Hidden/Read-only "other steps" selector.
  • Verified: BE E2E tests/verify_step_contribution.py (decision share→read→contribute→merge→withdraw) &
    verify_pc_contribution.py (P&C clone→edit→submit→owner snapshot, no list clutter) PASS; FE screenshot of
    MyDezider Contribution Mode at Step 7 with Submit bar. Merge: decision step-7 auto-weighted (exists);
    P&C/SF = owner reviews per-contributor snapshots (manual/AI merge). Build 2026.06.27.012.
  • PENDING: testing_agent validation of P&C + SF FE contribution screens; owner per-contributor review UI.

- 2026-06-27 (latest, fork — Collaborate ASYNC Contribute+Merge wired to frontend + both flows proven):
  User reported async collaboration wasn't integrated on the frontend. CONFIRMED GAP: backend had
  /contribute and /merge endpoints but the UI (app/tools/collaborate.tsx detail modal) only had Verify +
  (live_sync) Join Call — no way to contribute or merge. FIX: added to the session detail modal — a
  "Contribute" button (participants) opening an inline form (notes textarea + mode-specific Yes/No vote
  for voting mode, Accept/Reject for consensus mode) → POST /contribute; a "Merge & Finalize" button
  (owner) → POST /merge with status handling (merged / pending_consensus / voting_failed); and a
  "Finalized result" card showing the merge message + per-participant contribution weights. Added
  useAuthStore for owner/participant detection + refreshDetail() via GET /sessions/{id}. Verified E2E:
  BE tests/verify_collab_async.py PASS (contribute→contributed, merge→completed, 50/50 weights); FE
  screenshots for ALL THREE flows — async Contribute form, async merged-result card, and Live Sync Jitsi
  video call (real meet.jit.si embed with join/mic/cam/share/people/end). Live Sync was already wired
  (collab-call.tsx). Build 2026.06.27.010 (v3.94-collab-contribute-merge).

- 2026-06-27 (latest, fork — Collaborate modal clipping FIX + async/sync audit): User reported the
  "Identity Verification" (and other) modals on app/tools/collaborate.tsx were clipped off the bottom on
  wide/desktop web viewports. ROOT CAUSE: shared `modalOverlay` used justifyContent:'flex-end' (bottom
  sheet) + `modalContent` borderTop-only radius — on tall web windows the card overflowed below the fold,
  cutting off action buttons. FIX: modalOverlay → justifyContent:'center' + padding:16; modalContent →
  borderRadius:24 (all corners) + maxHeight:'88%' (internal ScrollViews already cap height). This centers
  ALL 3 modals on the screen (create/detail/verify) and guarantees full visibility on web + mobile.
  Verified via desktop-viewport screenshot (modal centered, fully visible). Async vs Live Sync audit:
  BOTH modes fully implemented in routes/collaboration.py (create accepts session_mode; live_sync
  auto-creates a Jitsi room meet.jit.si + start/join/end-call + screen-share endpoints; async uses
  invite→verify→contribute→merge with weighting). Not mocked. Build 2026.06.27.009 (v3.93-collab-modal-center).

- 2026-06-27 (latest, fork — "My Published Solutions" hub DONE + tested E2E): New creator hub screen
  app/tools/my-published.tsx (route /tools/my-published) — header summary card (🏆 Karma rank, balance,
  totals: published/uses/Karma/₹) + a list of published solutions each with per-item stats (uses · people ·
  Karma · ₹), tap → /tools/solution-detail. Entry point: NEW trophy-outline icon in the Solution Box
  (prr.tsx) header actions (testID prr-my-published). Backend: GET /option-publish/my-published now returns
  a `summary` object {solutions,total_uses,total_unique_users,total_karma_earned,total_cash_earned,
  karma_balance,karma_rank} (rank/balance via core.karma get_rank/get_balance) alongside the per-item
  stats. Verified: BE summary correct (rank #2, balance 60, 2 published, 10 Karma); FE E2E screenshot
  showed the populated hub. Build 2026.06.27.008 (v3.92-my-published-hub).

- 2026-06-27 (latest, fork — Creator "Your impact" card DONE + tested E2E): Added flywheel visibility for
  publishers. Backend: NEW GET /option-publish/impact/{solution_id} (creator-only; usage_count,
  unique_users, karma_earned [sum karma_ledger.points where ref.solution_id], cash_earned [sum
  earnings_ledger.net_inr]); my-published now also returns those 4 fields (via _solution_impact helper).
  Frontend (app/tools/solution-detail.tsx Overview): when the viewer IS the creator of an option-published
  solution, an effect fetches /impact and renders a "Your impact" card (uses · people · Karma · ₹earned)
  with a nudge to publish more. NOTE: impact fetch is its own useEffect keyed on [solution,user,solution_id]
  to avoid the auth-hydration race (inline fetch in fetchSolution silently skipped). Verified: BE impact
  endpoint returns correct stats + 403 for non-creator; FE E2E screenshot showed "1 use · 1 person · 10
  Karma" for the creator. Build 2026.06.27.007 (v3.91-creator-impact-card).

- 2026-06-27 (latest, fork — "Use this solution" CTA DONE + tested E2E): Added a casual-usage reward
  CTA on the Solution Store detail (app/tools/solution-detail.tsx, Overview tab). Shows only for
  option-published solutions (published_from_option) that aren't locked and aren't viewed by their own
  creator. Tapping → cross-platform confirm (showAlert) → POST /option-publish/record-usage {solution_id}
  → publisher credited (Karma free/in-quota, Cash on paid beyond quota); button then locks to "Marked as
  used" for the session. Verified: BE tests/verify_use_solution.py PASS (cross-user → +karma, self-use →
  no reward); FE E2E screenshot (admin viewing super's PUBLIC listing) showed confirm → "+5 Karma Points"
  success. Build 2026.06.27.006 (v3.90-use-this-solution-cta).

- 2026-06-27 (latest, fork — Publish modal UI polish DONE + tested): Applied the 4 requested
  PublishOptionsModal tweaks: header "Classify factors"→"Categorize Factors"; segment labels now show
  full "Quantitative"/"Qualitative" (was Quant/Qual) with the flow's default kind pre-selected and
  overridable; each factor row now has a checkbox (factorSelected, default ON) so factors are
  skippable like options; "(Karma)" wording→"(Karma Points)". Backend POST /option-publish/publish
  already honours factor_ids (unchecked factors excluded from solutions_store quantitative/qualitative).
  Verified: FE modal renders all 4 changes (screenshot), BE tests/verify_factor_skip.py PASS (skipped
  factor excluded, quant/qual partition correct). Build 2026.06.27.005 (v3.89-publish-modal-polish).

- 2026-06-27 (latest, iter171 — Phase 3B/3C DONE + tested 11/11 BE + FE E2E): Publish a COMPLETED
  decider's Option values into the existing modules. NEW backend: routes/option_publish.py
  (prefix /option-publish under /api) — GET /source/{decision_id}, POST /publish, POST /record-usage,
  GET /my-published; core/karma.award_karma_points() (exact-points award); usage-credit hook added in
  solutions_store.apply-to-option. Publishing creates one db.solutions_store solution PER option
  (quantitative_factors -> Store; qualitative_factors -> ReviewNet via db.review_policies) tagged with
  monetization {mode free|paid, reward_kind}. Crediting on usage: free use (and first
  free_usage_solution_store uses of a paid listing) -> Karma = karma_solution_store*(1+star/5); paid use
  beyond quota -> Cash = compute_cash_payout(...) minus platform commission, into db.earnings_ledger.
  NEW frontend: src/components/PublishOptionsModal.tsx (factor Quant/Qual toggles, option checkboxes,
  Free/Paid, live /catalog/payout/preview earnings) launched from a storefront icon on completed decider
  cards in prr.tsx (gated: non-completed shows 'Completed flows only'). Also moved the floating
  GlobalFontScale FAB to bottom-LEFT (was overlapping right-aligned card action icons). Seeded a
  persistent completed decider for testing: id dec_phase3_publish_demo (super@test.com). Builds:
  3B/3C = 2026.06.27.004 (v3.88).
- 2026-06-27 (iter171): Epic Phase 3A DONE + tested. Admin Central Catalog now has an L0–L3
  monetization config screen at /admin/catalog-payout (reached via the cash-outline icon in the
  /admin/catalog header). Backend: NEW core/payout_engine.py + routes/catalog_payout.py (router prefix
  /catalog/payout, mounted under /api), registered in server.py. Config is per catalog node OR global,
  inheriting L3→L2→L1→L0→global→default (nearest non-null per field, incl. per-step dict fields).
  Fields: free_usage_solution_store + free_usage_template_by_step{5 steps} (=6 free-usage quotas, before
  paid), payment_min/max (₹), karma_solution_store, karma_reviewnet, karma_template_by_step{5 steps}.
  Equations (server-side): cash = pmin+(pmax-pmin)*(avg★/5)*(#ratings/3000) clamp[min,max];
  karma = karma_per_use*(1+★/5). Cash ONLY for Store paid use; free use + ReviewNet => Karma.
  Tested: 9/9 pytest (iter170) + curl for 6-quota refinement + screenshots of the admin UI.
  Also (iter169, earlier this session): Phase 1 status-band filter chips + card %  and Phase 2 public-
  template gating (CloneTemplateModal + backend) — DONE + tested.
  ⏭️ NEXT (Epic Phase 3B/3C — NOT STARTED): publish a Completed flow's Option values → Solutions Store
  (quantitative, cash on paid use) / ReviewNet (qualitative, karma) with FREE/Paid toggle; wire usage →
  compute_cash_payout / compute_karma into earnings wallet + karma. Build on solutions_store.py
  (create_solution already carries quantitative_factors + catalog_node_id) and review_net.py. Gating:
  Store publish = Completed only; Decision Template = any step (public template share still Completed).
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
After it builds, HARD-REFRESH the site (per-route JS chunks + CF cache can be stale).

### 2a) POST-DEPLOY VERIFICATION — never call a deploy "done" on /api/health alone
A "healthy" backend can still be mid-worker-boot. After deploy + hard-refresh, confirm
EACH module's list actually loads a real user's data (this is what the 2026-07-17 incident
would have caught): MyDezider (`/tools/dezider-list`), Pros & Cons, Solution Finder, SWOT,
plus login (email + Google). Full checklist + topology: `/app/memory/DEPLOY_OPS_RUNBOOK.md`.

### 2b) "MY DATA IS GONE" — it's almost always a display glitch, NOT loss
Prod DB is **MongoDB Atlas `dezider`** (NOT the local `deploy_mongo_data` volume). Prove data
is safe first, then fix routing — do NOT run destructive ops. Exact commands in the runbook §5.
Empty list right after a deploy = transient fetch failure or a frontend→backend URL mismatch.

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

