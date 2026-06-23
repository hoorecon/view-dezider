# Collaboration + Knowledge-Marketplace Epic — Progress Tracker

Autonomous Max-mode build of B2, C, D, E, F (Phases 3 & 4 deferred per user).

## Status — ALL BUILT + BACKEND e2e VERIFIED (curl)
- [x] B1 — Share to Contacts/Experts tab (v3.44)
- [x] B2 — Platform Experts (v3.45)
- [x] C  — Public Help Feed (v3.46)
- [x] D  — Knowledge Marketplace (v3.47)
- [x] E  — Earnings & Payouts (v3.48)
- [x] F  — Ratings, Karma & Fame (v3.49)

## Backend modules (all registered in server.py)
- routes/platform_experts.py  → /platform-experts  (collection platform_experts)
- routes/public_help.py        → /public-help       (public_help_posts, public_help_contributions)
- routes/marketplace.py        → /marketplace        (marketplace_listings, marketplace_clones, marketplace_orders)
- routes/earnings.py           → /earnings + /admin/payouts (earnings_ledger, payout_accounts, payout_config, payouts) + weekly scheduler
- routes/karma.py              → /karma + /admin/karma (ratings, karma_ledger, karma_config; balance reuses referral_profiles.karma_balance)
- core/razorpayx.py            → RazorpayX payouts helper (guarded by X account number)
- core/karma.py                → award/spend/balance/rank + karma_config
- masters: added expert_type, experience_range, fees_per_min, available_timing (seed v2026-06-23-01)
- admin_data_seed v2026-06-23-01 seeds 3 platform experts

## Frontend screens
- app/admin/platform-experts.tsx, app/admin/payouts.tsx, app/admin/karma.tsx (+ admin/index cards)
- app/public-help.tsx, app/marketplace.tsx, app/earnings.tsx, app/leaderboard.tsx, app/fame/[id].tsx
- ShareStepModal: experts tab merges platform-experts + legacy; "Ask the public for help" button
- inbox.tsx: "Public" header button; profile.tsx: Marketplace / Earnings / Karma&Fame menu cards
- marketplace + public-help: star-rating UI

## Verified e2e (curl, super@test.com / admin@test.com)
- B2: masters CRUD, platform-experts CRUD + bulk + catalog filter, 3 seeded
- C: ask-public → feed → contribute → accept → merge (factors/options added)
- D: publish (free/paid/view), browse, detail gating, free clone copies factors+options (assessments reset), paid → 402
- E: payout config get/update, link UPI/bank, ledger credit, run-now → payout pending_manual (RazorpayX not yet active), schedule eta
- F: clone→karma, 5★ rating→karma (×stars), leaderboard, fame profile, reviews, admin karma config

## NEEDS USER ACTION (flagged)
- RazorpayX: payouts QUEUE as `pending_manual` until user activates RazorpayX and sets the X virtual
  account number in Admin → Payouts. Razorpay PAYMENTS (paid clone purchase) already works with existing keys.
- Paid-clone purchase verified by signature logic; live checkout needs a real Razorpay payment (testing_agent can mock).

## Remaining (deferred by user)
- Phase 3: Dependent Decisions for Pros & Cons (P2)
- Phase 4: CLD Decision Dependency Map (P2)
- Dialog width audit (P2), solution-finder.tsx refactor (P3), Admin EFT per-point images (P3)

## Build stamps
B2 v3.45 / C v3.46 / D v3.47 / E v3.48 / F v3.49 (BUILD_VERSION 2026.06.23.001→005)
