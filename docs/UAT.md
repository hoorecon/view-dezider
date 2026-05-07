# UAT Test Cases — Dezider

_metadata: { "version": "3.5", "updated": "2026-05-04" }

## How to UAT
1. Login with a test account (see `/app/memory/test_credentials.md`). Free tier is fine for most tests.
2. Walk each scenario top-to-bottom in the order listed. Each scenario is independently runnable in 5–10 min.
3. Flag anything that doesn't behave as "Expected" under the "Comments" column.

## Auth (unchanged)
AUTH-01..05 (signup, persistence, forgot-password, logout, brute-force).

## Solution Matrix v3.4
SM-01..06 (Standard/Accurate modes, influences +/-, templates picker, PDF export, locked OrgType).

## Public Pulse
PP-01..06 (consent, withdraw, tool run, feedback, dashboards, YoY tab).

## Public Sub-Portal
PORTAL-01..05 (open by slug, anon feedback, bad slug, iframe embed, resolved feed).

## Voice navigation
VOICE-01..06 (bubble visibility rules, language picker, hint chips).

## DPDP
DPDP-01..04 (export, delete-request, cancel-within-grace, admin purge).

---

## Daily Time Log (NEW v3.5)

| ID | Scenario | Steps | Expected |
|---|---|---|---|
| DTL-01 | Fresh user opens log for today | Navigate `/tools/daily-time-log` | Loads with 0 blocks, streak 0, all 4 key timings show defaults (06:30 / 22:30 / 09:30 / 18:30) |
| DTL-02 | Set key timings via Time Dezider settings | Time Dezider screen → gear icon → change wake to `05:30` → Save → go back to DTL | Same timings reflected in DTL header; persists across sessions |
| DTL-03 | Add a manual block | DTL → tap “Add block” → category Lifestyle → 06:00–07:00 → label “Run” → Save | Block appears in timeline with green border and `LIFESTYLE` tag |
| DTL-04 | Auto-rollup from CTT | Mark a CTT task `done` for today → DTL refresh-rollup | A new block appears tagged `AUTO` with correct duration estimate |
| DTL-05 | Auto-rollup from Meditation | Complete a meditation session today → DTL | Meditation block auto-appears |
| DTL-06 | Edit a manual block | Pencil icon on a manual block → change end time → Save | Duration updates; Category totals row recalculates |
| DTL-07 | Cannot delete auto block | Trash icon on an `AUTO` block | Alert “Auto-imported blocks cannot be deleted. Edit the source record instead.” |
| DTL-08 | Streak increments | Log ≥15 min for today → reload | Streak chip shows 1🔥 (or current+1 if you've logged earlier days) |
| DTL-09 | Week strip navigation | Tap a date chip → view that date | Timeline shows that day's blocks (empty if none logged) |
| DTL-10 | Open Weekly Review | DTL → calendar icon top-right | Shows 7-day bar chart + streak tile + variance notes |
| DTL-11 | Weekly adherence calculation | If Lifestyle Designer has a plan, Weekly Review shows `adherence_pct` and a note like “Lifestyle adherence within ±10% of plan” | Text matches actual lifestyle minutes vs planned |

## Time Dezider — Raja Guru (NEW v3.5)

| ID | Scenario | Steps | Expected |
|---|---|---|---|
| TD-01 | Morning intent-setter | Navigate `/tools/time-dezider` → Morning tab | Intro “Good morning, Raja…”, key timings strip, up to 5 picks ranked by score, raja_note at bottom |
| TD-02 | Pick comes from CTT | Create a high-priority CTT task with due today → return to Morning tab | Task appears as a pick with TASK chip and score > 15 |
| TD-03 | Pick comes from Lifestyle | Have a Lifestyle Designer plan with morning fitness → go to Morning tab in actual morning | Fitness area appears with reason “Best window for this is now” |
| TD-04 | Accept feedback | Tap green checkmark on any pick | Alert “Recorded: accept”; feedback row inserted in `time_dezider_feedback` |
| TD-05 | Defer feedback | Tap amber clock on a pick | Alert “Recorded: defer” |
| TD-06 | Skip feedback | Tap red cross on a pick | Alert “Recorded: skip” |
| TD-07 | Midday tab | Tap Midday | Intro “Raja, half the day is done…” + up to 4 picks |
| TD-08 | Evening retrospective | Tap Evening | Intro “sun sets with grace”, Wins + Gaps lists populated from today's DTL |
| TD-09 | Next-action | Tap Now | Single highest-score pick returned, raja_note “Do it for 5 minutes” |
| TD-10 | Settings — key timings | Gear icon → change bed_time to 23:30 → Save | DTL + Raja Guru pick up new timing immediately |
| TD-11 | Settings — nudge cadence | Toggle `nudge_hourly=true` → Save | Persists; GET `/raja-guru/preferences` returns true |
| TD-12 | Empty-state copy | Fresh user with no CTT / Lifestyle plan → Morning tab | Shows “No plan is still a plan — but a weaker one…” |

## Time Store (NEW v3.5)

| ID | Scenario | Steps | Expected |
|---|---|---|---|
| TS-01 | Time Audit empty | Fresh user | Audit tab shows 0h saveable + empty-state copy |
| TS-02 | Time Audit with signals | Add a CTT task priority=`low` duration=`45` → return to Audit | Opportunity card appears, lever tag `People`, suggested action `delegate`, ~45 min/event |
| TS-03 | Delegate an opportunity | Tap `Delegate` on an audit card → confirm description | Delegation modal closes; navigates to Delegations tab; new row appears with status OPEN |
| TS-04 | Services — 30 min/day bucket | Services tab → 30m/day chip | 5 seeded services render (Personal Admin Assistant, Chore Concierge, Expense & GST, Meal Prep, Social Media) with prices, org badge |
| TS-05 | Services — 120 min/day bucket | Services tab → 2h/day chip | Only services with time_save ≥ 90 min/day show (Personal Admin Assistant, Meal Prep) |
| TS-06 | Purchase (MOCKED) | Tap `Buy back time` on any service | Alert with order ID + status `PENDING_PAYMENT` + note about MOCKED payment |
| TS-07 | Purchases history | Purchases tab | Previous order shows with MOCKED badge + PENDING_PAYMENT status |
| TS-08 | Delegations tab | Delegations tab | Row from TS-03 visible with estimated minutes saved |
| TS-09 | TEPFI lever labels | Observe each opportunity card in Audit tab | Each shows its lever chip (People / Finance / Time), matching the suggested_action |

## Performance (manual)
| ID | Scenario | Expected |
|---|---|---|
| PERF-01 | Open Daily Time Log with 20 blocks | < 2 s on 4G |
| PERF-02 | Raja Guru day-plan with 50 CTT tasks | < 1.5 s |
| PERF-03 | Time Audit with 100 CTT tasks + full Matrix | < 2.5 s |
| PERF-04 | Time Store services list (25 results) | < 1 s |

---
## v3.14.0 — UAT scenarios (2026-05-07)

### UC-TM — Tier Matrix admin
1. Admin opens `/admin/tier-matrix` → 32 module rows × 7 chakra columns load
2. Admin taps "Heart" cell on `expert_net` module → cell turns green; verify Throat/Third Eye/Crown also turn green (cascade)
3. Admin expands a module → feature rows appear; toggle a feature; verify lock icon when parent is OFF
4. Admin taps Reset → confirmation; matrix returns to smart-seed defaults

### UC-CS — Customer Segment master
1. Admin opens `/admin/customer-segments` → "New" button → enter name + description + recommended tier → Create
2. Expand new segment → 23 factors visible across 4 category sections
3. Tap ✨ AI button on Income Range → spinner → value populates within 5s
4. Tap "Custom factor" → add `caffeine_intake` under Behavioural → factor appears with delete button
5. Tap "Tier pricing" → modal opens with 7 tier blocks; add USD row to Sacral; toggle disabled on Crown for IN; Save

### UC-PR — Public pricing
1. Visitor opens `/pricing` (auth not required) → 7 chakra tier cards visible
2. Toggle Monthly → Annual → prices update; "save 16%" badge visible on Annual
3. Switch country IN → US → prices flip currency (or show "Contact us" if not configured)
4. Tap "All" segment → defaults shown; tap a specific segment chip → segment-specific pricing applied
5. Expand "Show feature comparison" → 32-row × 7-col grid renders with check/cross icons
