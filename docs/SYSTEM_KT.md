# System KT — Block Diagram & Flow Charts (Whole System)

_metadata: { "version": "3.23.1", "updated": "2026-07-19", "author": "engineering" }

**Purpose:** One-stop **Knowledge Transfer** doc. Read this first to understand
how the whole system fits together — the block diagram, the major end-to-end
flow charts, the data stores, the third-party integrations, a screen-by-screen
visual reference, and the deploy pipeline.

> Diagrams are ASCII (they render as monospace in the in-app viewer at
> `/admin/docs/SYSTEM_KT`). A "Screens catalogue" further below gives a mini
> wireframe + the live in-app route for each key screen so you can open the
> real screen on your device as the "screenshot".

---

## 1. System Block Diagram

```
                        ┌───────────────────────────────────────────────┐
                        │                   CLIENTS                      │
                        │  iOS / Android (Expo Go & native builds)       │
                        │  Web (React Native Web via Metro / Cloudflare) │
                        └───────────────────────┬───────────────────────┘
                                                 │  HTTPS
                                                 │  Bearer <session_token>
                                                 ▼
              ┌───────────────────────────────────────────────────────────────┐
              │                     INGRESS / EDGE                              │
              │   "/"     → Frontend (Metro dev :3000 / Cloudflare Pages)      │
              │   "/api/*"→ Backend (FastAPI :8001)                            │
              └───────────────┬───────────────────────────┬───────────────────┘
                              │                            │
                ┌────────────▼─────────────┐   ┌───────────▼───────────────────┐
                │      FRONTEND (Expo)      │   │      BACKEND (FastAPI)         │
                │  expo-router file routes  │   │  server.py mounts api_router   │
                │  /app/**  screens         │   │   (prefix /api)                │
                │  /src/**  components,      │   │  routes/*.py  (per module)     │
                │           store (zustand), │   │  core/*.py    (auth, metering, │
                │           utils, api.ts    │   │     wallet, billing, db, ...)  │
                │  AsyncStorage/SecureStore  │   │  APScheduler (nightly jobs)    │
                └───────────────────────────┘   └───────┬───────────────┬───────┘
                                                         │               │
                                          ┌──────────────▼───┐   ┌───────▼────────────────┐
                                          │     MongoDB      │   │  THIRD-PARTY SERVICES   │
                                          │  (motor async)   │   │  • Emergent LLM Key →    │
                                          │  users, sessions │   │      OpenAI/Anthropic/   │
                                          │  decisions, ...  │   │      Gemini (text+img)   │
                                          │  ai_wallets,     │   │  • Stripe (payments)     │
                                          │  credit_wallets, │   │  • Razorpay/RazorpayX     │
                                          │  stripe_payments,│   │  • Zoho Books (finance)  │
                                          │  financial_models│   │  • Resend (email)        │
                                          │  + ~100 more     │   │  • UltraMsg (WhatsApp)   │
                                          └──────────────────┘   │  • RapidOCR (in-proc)    │
                                                                 │  • Google OAuth (Emergent)│
                                                                 └─────────────────────────┘
```

**Rules of the road (never break):**
- Frontend calls the backend only via `EXPO_PUBLIC_BACKEND_URL` + `/api`. No hardcoded URLs/ports.
- Backend binds `0.0.0.0:8001`. Every route is under `/api`.
- DB is MongoDB only, via `MONGO_URL`. No other DB engines.

---

## 2. Technology Stack

```
Layer        Tech
-----------  ------------------------------------------------------------
Mobile/Web   Expo (React Native + RN-Web), expo-router, zustand,
             react-native-reanimated, react-native-safe-area-context
Backend      FastAPI (Python 3.11), uvicorn, motor (async Mongo),
             APScheduler, emergentintegrations, stripe, rapidocr-onnxruntime,
             PyMuPDF, openpyxl/reportlab (exports)
Data         MongoDB
AI           Emergent Universal LLM Key → Anthropic Claude / OpenAI / Gemini
Payments     Stripe (USD/INR) + Razorpay/RazorpayX (INR)
Finance      Zoho Books API (+ nightly auto-sync)
Comms        Resend (email), UltraMsg (WhatsApp OTP/alerts)
Deploy       Emergent workspace → GitHub emergent-v3 →
             Cloudflare Pages (frontend) + EC2 sync.sh (backend API)
```

---

## 3. Module Map (major functional areas)

```
DECISION ENGINES            LIFE / GROWTH                 ORG / FINANCE
 • MyDezider (PRR)           • My 360° Life (PNA)          • Organizations
 • Pros & Cons               • Life Goals (7-level GEM)    • Financial Model
 • SWOT                      • Goal Setter (SMART)            (3-stmt, DSCR,
 • Solution Finder           • Goal Manifestation             IIMB Valuation,
 • Test123 (quick)           • Conflict Breaker               CMA/Investor exports,
 • CLD (causal loops)        • Consciousness Diary            Zoho Books sync)
 • Decision Templates        • Lifestyle Dezider/Designer  • Solutions Store
                             • Unconditional Happiness     • Collaboration Hub

PLATFORM / ADMIN            MONETISATION                  INTELLIGENCE
 • Auth + WhatsApp gate      • Subscriptions (7 tiers)     • AI Assistant (Claude)
 • Admin Panel + Handbook    • AI Wallet (metered credits) • Import-from-File (OCR)
 • Feature flags / tiers     • Stripe + Razorpay checkout  • Web-crawl enrichment
 • Notification Engine       • Revenue reconciliation      • Set Expectations (AI)
```

---

## 4. Key End-to-End Flow Charts

### 4.1 Authentication (+ WhatsApp gate)

```
 User ─▶ Login/Register screen
          │
          ├─ Email/password ──▶ POST /api/auth/login|register
          │                        │  bcrypt verify · issue session_token (DB-backed)
          │                        ▼
          │                     whatsapp_verified = effective_whatsapp_verified(user)
          │                        │  (TRUE if skip_whatsapp_gate ON, or admin, or verified)
          │
          └─ "Continue with Google" ─▶ auth.emergentagent.com
                                          │ returns session_id
                                          ▼
                                       POST /api/auth/google/session → create/update user + token
          ▼
 _layout.tsx gate:  whatsapp_verified === true ? enter app : route to /whatsapp-verify
```
Fix (2026-07): register + google-session now BOTH honour `skip_whatsapp_gate`
(previously register hard-coded false → users were wrongly sent to OTP).

### 4.2 MyDezider (PRR) decision lifecycle

```
 Create decision ─▶ Step 1 factors ─▶ Step 2 options & values ─▶ Step 3 score/compare ─▶ Recommendation
                         │                    │
                         │                    └─ "Set Expectations · By AI"  (POST /api/.../set-expectations)
                         │                         operator + expected_value driven by the VALUE type:
                         │                         numeric → ≥ ≤ > < = ≠ · text → Contains/Equals/... (default Contains)
                         └─ "Import from File"  (POST /api/file-import/decision/{id})  → §4.6
```

### 4.3 AI Assistant — Claude default + quota fallback

```
 User asks (AI Assistant / More Tools)
        │  POST /api/ai-assistant/quick-ask | conversations/{id}/message
        ▼
 _assistant_reply()
        │
        ├─ metered_chat(tier="precise")  ──▶  Claude (claude-sonnet-4-6)   ── charges AI wallet
        │        │                              (on provider failure → free chain: Gemini→Groq→OpenAI)
        │        ▼
        │   InsufficientCredits?  (wallet balance ≤ 0 = quota exceeded)
        │        │ yes
        │        ▼
        └─▶ Fallback: gpt-4.1-mini (Emergent key, un-gated)  → response label "gpt-4.1-mini (quota fallback)"
 Response includes { ai_response, model } so the UI can show which model answered.
```

### 4.4 Stripe checkout + fulfillment  (runs ALONGSIDE Razorpay)

```
 Client ─▶ POST /api/stripe/checkout {kind, currency, pack_id|plan_id, success_url}
              │  kind = ai_wallet | subscription ; currency = usd | inr
              │  amount computed SERVER-SIDE (core.ai_billing) — client never sends amount
              ▼
           stripe.checkout.Session.create → {checkout_url, session_id}
              │  store pending row in `stripe_payments`
              ▼
 Web: full-page redirect to Stripe ─┐         Native: WebBrowser auth-session ─┐
                                     ▼                                          ▼
                    Stripe hosted checkout ──(paid)──▶ returns to /checkout-result
                                     │
        ┌────────────────────────────┴───────────────────────────┐
        │ Confirmation (either path triggers idempotent fulfill)  │
        │  • Webhook  POST /api/stripe/webhook (verified if secret)│
        │  • Poll     GET  /api/stripe/status/{session_id}         │
        └────────────────────────────┬───────────────────────────┘
                                     ▼
                 _fulfill(): atomic pending→completed flip on stripe_payments
                    │ (guarantees exactly-once — webhook & poll can't double-grant)
                    ├─ ai_wallet    → _credit_refill() → ai_wallet.grant()  (credits ai_wallets)
                    └─ subscription → subscriptions.apply_charge()          (activates plan)
```
NOTE: pod `STRIPE_API_KEY` is a PLACEHOLDER (`sk_test_emergent`). Live session
creation returns 401 until a REAL Stripe key is set in prod (+ optional
`STRIPE_WEBHOOK_SECRET` and a dashboard webhook → `/api/stripe/webhook`).

### 4.5 Zoho Books finance sync

```
 Manual:  Financial Model screen → "Sync historicals from Zoho" (date range)
              → POST /api/financial-models/zoho-sync → live pull → patch preview → Apply
 Auto:    APScheduler nightly job → for each model with zoho_auto_sync=ON →
              pull current-FY-to-date → cache in model.zoho_snapshot (user applies manually)
```

### 4.6 Import-from-File (OCR pipeline)

```
 Upload (pdf/docx/txt/xlsx/csv/image)
   │  large files → chunked upload (POST /api/uploads/init → /chunk)  (bypasses proxy limits)
   ▼
 Extract text ─ image-only PDF? ─▶ PyMuPDF rasterise → RapidOCR (in-process, pip; NOT Tesseract)
   │                                     │  live progress: GET /api/file-import/progress/{job_id}
   ▼                                     ▼
 AI factor + option extraction ─▶ merge into decision (does NOT overwrite existing parsed factors)
   │
   └─ optional metered web-crawl enrichment
```

### 4.7 Deploy pipeline (source of truth = Emergent workspace)

```
 Emergent workspace  ──("Save to GitHub")──▶  GitHub: hoorecon/view-dezider @ emergent-v3
        │  (bump README BUILD_VERSION first)                 │
        │                                     ┌──────────────┴───────────────┐
        │                                     ▼                              ▼
        │                        Cloudflare Pages (FRONTEND)      EC2 /opt/dezider (BACKEND)
        │                          auto-builds on push              ./deploy/sync.sh emergent-v3
        │                                                            EXPECT_BUILD guard = README build
        ▼
  Live: https://www.jelcos.ai (FE) + https://api.jelcos.ai (BE)
```
Guard: `sync.sh` refuses to deploy if `origin/emergent-v3` README `BUILD_VERSION`
≠ `EXPECT_BUILD` (protects against stale / dropped pushes).

---

## 5. Primary Data Stores (MongoDB collections)

```
Collection            Holds
--------------------  --------------------------------------------------------
users                 accounts, roles, whatsapp_verified
user_sessions         opaque session_token → user (auth lookup)
app_settings          security_config (skip_whatsapp_gate, ...), branding
decisions             MyDezider/PRR + factors, options, expectations
ai_wallets            metered AI credits (used by AI Assistant / metered_chat)
ai_wallet_ledger      per-call debits/credits audit
ai_wallet_orders      top-up orders (Razorpay + Stripe) → _credit_refill
credit_wallets        subscription plan credits + subscription state
stripe_payments       Stripe checkout txns (idempotent fulfillment)
subscription_plans    7-tier plan catalogue (price_inr, credits_per_month)
financial_models      3-stmt inputs, IIMB valuation, zoho_snapshot, zoho_auto_sync
life_goals            My 360° Life 7-level GEM planner
notifications*        Generic Notification Engine (triggers, dispatch log)
```

---

## 6. Third-Party Integrations

```
Integration        Auth / Key                      Used for
-----------------  ------------------------------   ----------------------------
Emergent LLM Key   EMERGENT_LLM_KEY (universal)     Claude/OpenAI/Gemini text+img, OCR-adjacent AI
Stripe             STRIPE_API_KEY (+WEBHOOK_SECRET) Card checkout (USD/INR): wallet + subscriptions
Razorpay/RazorpayX Razorpay keys                    INR checkout + referral payout engine
Zoho Books         ZOHO_* (refresh token, org id)   Financial statement sync + nightly cron
Resend             RESEND_API_KEY                   Transactional/digest email
UltraMsg           UltraMsg creds                   WhatsApp OTP + alerts
Google OAuth       Emergent-managed                 "Continue with Google"
```

---

## 7. Screens Catalogue (visual reference + live route)

> Open the live route on your device to see the real screen (this is the
> "screenshot" for KT). Mini wireframes below show layout at a glance.

### 7.1 Landing / Marketing  — route: `/`
```
┌───────────────────────────────┐
│ JELCOS AI      Sign in [Start] │
│ ✨ Powered by AI               │
│ Make every life choice with    │
│ clarity & confidence           │
│ [ Get started free ]  [Sign in]│
│ 6+ frameworks · 10 life areas  │
└───────────────────────────────┘
```

### 7.2 Login / Register — route: `/auth/login`, `/auth/register`
```
┌───────────────────────────────┐
│  Email  [______________]       │
│  Password [____________]       │
│  [ Log in ]                    │
│  ───────── or ─────────        │
│  [  Continue with Google  ]    │
└───────────────────────────────┘
```

### 7.3 Home / Dashboard — route: `/(tabs)` (post-login)
```
┌───────────────────────────────┐
│ Hi, <name>            [bell]   │
│ Quick actions: New Decision …  │
│ Modules grid: MyDezider · PNA  │
│  · Goals · Financial · More    │
└───────────────────────────────┘
```

### 7.4 MyDezider Step 2 (factors/expectations) — route: `/prr/{id}?step=2`
```
┌───────────────────────────────┐
│ Factor: Role/Title             │
│ Type: [Quantitative][Qualit.]  │
│ Operator: ≥ ≤ > < = ≠ Contains │
│           Starts/Ends/Equals   │   ← operators COMMON to both types
│ Expected: [Managing Partner]   │      (auto-default by value; overridable)
│ [ Set Expectations · By AI ]   │
└───────────────────────────────┘
```

### 7.5 AI Wallet (+ Stripe) — route: `/ai-wallet`
```
┌───────────────────────────────┐
│ Balance: <credits>             │
│ Top up credits                 │
│ Card currency: [USD] INR       │
│ Starter · 5,000 cr  [₹96][Card]│   ← ₹ = Razorpay · Card = Stripe
│ Pro …               [₹][Card]  │
└───────────────────────────────┘
```

### 7.6 AI Assistant — route: `/tools/ai-assistant` (More Tools)
```
┌───────────────────────────────┐
│  (chat bubbles)                │
│  Answered by claude-sonnet-4-6 │   ← default model
│  [ Ask anything…        ][➤]   │
└───────────────────────────────┘
```

### 7.7 Financial Model — route: `/tools/financial-model?org={id}`
```
┌───────────────────────────────┐
│ Inputs|P&L|BS|CF|Ratios|Val|   │
│                    Val(IIMB)   │
│ [Template][Import Excel/Sheet] │
│ [Sync from Zoho] auto-sync[ ]  │
└───────────────────────────────┘
```

### 7.8 Admin Handbook (these docs) — route: `/admin/handbook`
```
┌───────────────────────────────┐
│ Documentation                  │
│ • SYSTEM_KT  ← you are here     │
│ • PRD · SRS · API_REFERENCE …  │
└───────────────────────────────┘
```

### 7.9 Checkout result — route: `/checkout-result`
```
┌───────────────────────────────┐
│      ✓  Payment successful     │
│  Your purchase has been applied│
│      [ Back to Wallet ]        │
└───────────────────────────────┘
```

---

## 8. How to add real screenshot images later

The in-app viewer now supports images. Drop an image reference in any doc:

```
![AI Wallet screen](https://<public-url>/ai-wallet.png)
```

Host the PNG at a public URL (e.g., a Cloudflare/asset URL) and it renders in
both web and native. (Captured-in-CI screenshots can't be auto-embedded from
the agent environment, so use hosted URLs or commit the PNGs and reference them.)

---

## 9. Quick "where do I look?" cheat-sheet

```
Symptom / task                     Start here
---------------------------------  --------------------------------------------
Auth / OTP gate issue              routes/auth_routes.py, core/security_config.py
AI Assistant model/quota           routes/ai_assistant.py, core/ai_metering.py
Stripe payment                     routes/stripe_payments.py, src/utils/stripeCheckout.ts
AI wallet top-up / pricing         routes/ai_wallet.py, core/ai_billing.py
Subscriptions                      routes/subscriptions.py
Financial model / Zoho             routes/financial_model.py, core/zoho_books.py
Import from file / OCR             routes/file_import.py, core/chunk_upload.py
Postman collection out of date     backend/scripts/generate_postman_collection.py (+ prompts/admin_docs_taxonomy.py folder names)
Deploy / build guard               deploy/sync.sh, README.md (BUILD_VERSION)
```

---

## 10. FRAME — Finder Ranking & Monetization Engine (v3.22–v3.23)

**FRAME** = Filter → Rank → Auction → Merge → Embed. Powers "Decider Apps"
(auto-finders) in The Decider Store, at two scales: embedded options (classic
sync run) and the **Option Bank** (indexed pipeline for millions of options).

```
                 USER RUNS A DECIDER APP (/finder/{decision_id})
                                    │
             bank_options == 0      │      bank_options > 0
        ┌───────────────────────────┴───────────────────────────┐
        ▼                                                        ▼
  POST /finder/run  (sync)                       POST /finder/jobs (async, %progress
  core/finder_engine.py                          + 'finder' loader-music slot)
        │                                        core/finder_bank.py
        │                                              │
        │                          S0 decider_option_bank (vals pre-normalized
        │                             at ingest; wildcard index vals.$**)
        │                          S1 mandatory expectations → NATIVE Mongo query
        │                             (DB prunes 10M → 10⁴-10⁵; adaptive funnel;
        │                              residual Python checks for odd operators)
        │                          S2 motor cursor + projection + heapq Top-K
        │                             (O(K) memory, progress every batch)
        ▼                                              ▼
        └──────────────────────┬───────────────────────┘
                               ▼
        S3  QUALITY GATE: min_cutoff_pct — resolution precedence:
            template.finder_settings → CCM node chain (Scenario→…→LifeArea,
            catalog_nodes.finder_ad_config, nearest wins) → ai_wallet globals
                               │
        S4  ADMAKER AUCTION (core/ad_auction.py):
            AdRank = bid_paise × QualityScore(worth/100)
            GSP price = next AdRank ÷ own QS + 1p  (clamped [1, own bid])
            bid liveness: region + calendar slot + daily hours (IANA tz)
            billing: CPC at POST /admaker/track; budget → status=exhausted
                               │
        S5  MERGE: organic Top-N first (money NEVER reorders it),
            "Sponsored Solutions · AD" block BELOW; impressions logged
                               │
        S6  EMBED (AdTaker): widget.js + tracker DZ-PUB-… on 3rd-party sites
            impression → click → conversion (clone?ref=) per tracker;
            publisher revenue share; API key dzk_/secret dzs_ (hash-only) or
            org-login portal (/adtaker-portal)
```

**Data stores**: `decider_option_bank`, `finder_jobs`, `admaker_bids`,
`admaker_events`, `adtaker_publishers`, `adtaker_events`,
`catalog_nodes.finder_ad_config`, `decisions.finder_sponsored_ids`,
`Factor.source_sub_id` (decision→bank join key — must survive factor saves).

**Ingestion rails** (routes/option_bank.py, all → `bank_upsert`, idempotent on
template+name_norm): template sync · Solution-Store/ReviewNet bridge ·
partner JSON APIs · Deep-Import/bulk. Synthetic seeder + benchmark:
`scripts/seed_finder_bank_synthetic.py` (measured: 200K → 25K → 2.65s;
full 200K scan ≈ 10s; ≤60s SLA).

**Identity ladder** (no third auth stack):
```
Free user → Premium (ACM tier) → Organization (OrgLogin)
   │              │                      │
Solution     AdMaker Studio        Publisher Portal (AdTaker)
Store        /admaker-studio       /adtaker-portal
             (admaker_program)     (publisher.org_id link)
```

### Cheat-sheet additions
```
Symptom / task                     Start here
---------------------------------  --------------------------------------------
Sponsored results wrong/missing    core/ad_auction.py (cutoff resolution, GSP)
Finder slow / bank job stuck       core/finder_bank.py, finder_jobs collection
Bank ingest issues                 routes/option_bank.py (3 rails), bank_upsert
Advertiser can't bid (403)         routes/admaker.py _require_admaker/_owned_options
Publisher widget/keys              routes/adtaker.py (widget.js, self/*, rotate)
Cutoff/slots config               /admin/ad-programs → Cutoffs tab; catalog_nodes.finder_ad_config
```
