# Backlog — Dezider

Items intentionally deferred. Each entry: rationale, prerequisites, rough scope.

---

## AI layer on top of Time Dezider ("Raja Guru+")

**Why**: v1 Time Dezider is rule-based — deterministic and fast, but doesn't
read free-form user context. The next iteration should add an AI overlay
that reads the user's latest CLD (causal loop diagram), recent journal
entries, Solution Matrix narrative cells, and personalises the 4 daily
nudges in the user's own language and tone.

**Prerequisites**:
1. LLM budget reset (currently capped — endpoints return 503).
2. At least one populated CLD per user so the engine has a graph to reason over.
3. Prompt version registry so we can A/B-test new prompts without redeploying.

**Scope**:
- New helper `core/raja_guru_llm.py` that synthesises a short paragraph per
  pick + per slot (morning/midday/evening).
- Wrap in existing `llm_errors.try_llm_call` so it 503s gracefully.
- Feed context: key timings, top 3 rule-based picks, CLD loop narratives,
  user's last 2 Journal entries, last Solution Matrix summary.
- Output tone: "Raja Guru to a Raja" — confident, concise, compassionate,
  references the user's own phrasing from CLD nodes.
- Cache for 1 hour per (user, slot) to contain cost.
- Front-end: if LLM response present, render in a dedicated "Guru says" card
  above the rule-based picks; if 503, skip silently.

**Estimated effort**: 1 focused session once LLM budget is restored.

---

## Payment wiring for Time Store

**Why**: v1 Time Store "purchase" is MOCKED — status=pending_payment, never
flips to paid. Real flow needs Razorpay (already mostly wired in
`routes/payments.py` for subscriptions).

**Prerequisites**: Razorpay merchant activation in live mode (user already has
test keys per prior session).

**Scope**:
- Move mock block in `routes/time_store_engine.py::purchase` to call the
  existing Razorpay order-create helper.
- Add `payment_verified` webhook receiver at `/api/time-store/webhook`.
- Frontend Time Store "Buy back time" button surfaces Razorpay checkout
  modal via the existing SDK wrapper.
- Settlement flow: 80% to org, 20% platform fee (configurable per-org).

**Estimated effort**: 1 session.

---

## Delegation inbox routing + Org-side view

**Why**: v1 delegations land in `time_store_delegations` but are not routed
anywhere — the org / contact / family member has no UI to see them.

**Prerequisites**: none blocking.

**Scope**:
- Push notification to `proposed_delegate_id` when a delegation targets them.
- Org admin screen under `/tools/public-pulse/org/...` showing inbound
  delegations assigned to the org's members.
- Accept / propose-alt / decline flow.
- Close-the-loop: once delegate marks done, requester gets a summary +
  can rate the work.

**Estimated effort**: 2 sessions.

---

## Daily Time Log smart heuristics

**Why**: v1 auto-rollup is purely additive (one block per source record).
Smarter heuristics can detect conflicts (two blocks at the same time),
merge adjacent meditation sessions, and propose missing blocks (e.g.
wake/bed derived from user prefs but no logged activity).

**Scope**:
- Conflict detection at save time + UI nudge.
- Auto-generated sleep block from bed→wake.
- Gap detection: if 3+ hours between adjacent blocks, propose "What were
  you doing between X and Y?" prompt on week end.

---

## Streaks & gamification

**Why**: v1 tracks streaks but doesn't surface them prominently in other
modules.

**Scope**:
- Weekly review card on `(tabs)/index` showing streak + "keep going" copy.
- Badge system (7-day, 30-day, 100-day).
- Leaderboard among followed Contacts (opt-in).
