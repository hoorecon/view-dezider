# Pending Reminders / Deferred Work

## 🔴 Paid-template checkout — The Decider Store (BLOCKED: awaiting Razorpay-side dependencies)
- **What**: Paid Decider Store templates currently return **HTTP 402** from `POST /api/decider-store/{id}/clone`
  (backend `routes/decider_store.py`) with `{price_paise, currency, creator_split_pct}`. The frontend
  (`app/decider-store/[id].tsx`) shows a "Paid template · checkout coming soon" alert.
- **To finish once Razorpay dependencies are ready**:
  1. Create a Razorpay order for `price_paise` on "Use this template" (paid), open Razorpay checkout.
  2. On payment success/webhook → mark entitlement → run the existing clone → open `/prr/{decision_id}`.
  3. Split proceeds per `creator_split_pct` (creator) vs platform — reuse the marketplace earnings/payout ledger.
  4. Stripe test key is already in the pod if we want a Stripe path too (live checkout only works post-deploy).
- **Owner note**: user is waiting on Razorpay side; revisit when they confirm.
- Logged: ITER 191.
