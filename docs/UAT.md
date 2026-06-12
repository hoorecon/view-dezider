# UAT Test Cases — Dezider

_metadata: { "version": "3.16.1", "updated": "2026-06-12" }

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

---
## v3.15.0 — 8-Step Pros & Cons / SWOT Framework UAT (2026-05-18)

### UC-PCFW — Pros & Cons 8-step wizard
1. From Pros & Cons list → open any record → tap purple **"Open 8-Step Framework"** banner → wizard loads on Step 1 with horizontal step strip
2. **Step 1**: enter factor `Mileage`, expected `15`, unit `kmpl` → tap "Add Direct Factor" → factor appears with **D** tag
3. **Step 2**: add option `Car X` → add Pro `Lower price` → add Con `Less boot space` → repeat for `Car Y` with Pro `More features` → all P&C visible per option
4. **Step 3**: tap **"Auto-Promote all Pros & Cons"** → toast `3 pros/cons converted to factors`; verify Cons row in list shows `SHOULD NOT - Less boot space`
5. **Step 4**: tap "Group ↳" on a Pro-derived factor → pick `Mileage` as parent → row updates with "↳ sub-factor of: Mileage"
6. **Step 5**: factor tree shows Mileage with 1 sub indicator, tappable to collapse/expand
7. **Step 6**: tap **A** chip on Mileage → notation = mandatory; enter `60` in threshold field → Save
8. **Step 7**: rank #1 visible; std rating 80 default; for Car X enter Assessment % `80` → cell value auto = `64.0`; for Car Y enter `50` → cell `40.0`
9. **Step 8**: each factor row exposes Subjective/Objective + Improvable chips, expectations row, gap input; per-option row asks Actual + Satisfaction → enter `0.85` for Car X and `0.50` for Car Y → satisfaction values compute
10. Overall card at top of Step 8 shows: **Car X 23.4% Rank #1**, **Car Y Disqualified** (mandatory below threshold)
11. Bulb icon in header → "Final Decision Guidelines" modal with 12 ranked rules

### UC-SWFW — SWOT 8-step wizard
12. From SWOT list → open any record → tap purple **"Open 8-Step Framework"** banner → same wizard loads
13. Repeat the Steps 1–11 flow above; verify all endpoints fire against `/api/swot/*` and math is identical

### UC-LEG — Legacy compatibility
14. From Pros & Cons / SWOT list → open an old record created **before** v3.15.0 → legacy flat list view still works; banner appears at top to "Open 8-Step Framework"; opening the wizard shows empty 8-step containers (no migration of legacy pros/cons into the new shape — by design)

### Performance
- PCFW-PERF-01: full wizard load on a fresh analysis < 1.5 s
- PCFW-PERF-02: aggregate computation < 250 ms for 20 factors × 5 options

---
## v3.16.0 — UAT scenarios (2026-06-12)

### UC-IU — Import-from-URL v3 (Factor-Type + Hints + Tiers)
| ID | Scenario | Steps | Expected |
|---|---|---|---|
| IU-01 | Default Fast import — generic site | Decision → Step 2 → Import URL → paste any product URL → leave tier=Fast → Import | Factors+options imported within 30s; toast shows mode + provider |
| IU-02 | Precise Claude import — NoBroker | Same as IU-01 with tier=Precise + NoBroker URL | `ai_provider=emergent_precise`; ALL user-listed values matched; 3+ options including "Main Listing"; text-facts (Color/Furnishing) tagged Quantitative |
| IU-03 | Hint-driven self-heal | Provide hint `expected_factor_count=20` for a page that returns 10 on first try | Server retries once; final count within ±max(2, 20%); UI shows hint_warnings if any |
| IU-04 | Page-defined groups SACRED | Import GSMArena phone URL | "BODY", "DISPLAY" etc. preserved as `source=page` groups; AI does not regroup |
| IU-05 | AI-grouping only above threshold | Set `import_group_threshold=15` → import a 12-factor page with no page groups | Result is `kind=flat` (no AI groups); set threshold=10 → re-import → result is `kind=hier` (AI groups) |
| IU-06 | Zero-tolerance values | Inspect imported items in DB | No item carries a factor key that wasn't in the groups schema |
| IU-07 | Set Expectations — By AI | After import, tap "Set Expectations - By AI" button | All leaf factors get `expected_value + operator` filled; parents untouched; toast shows "21/21 updated" |
| IU-08 | Set Expectations gating | Before adding any unit_value, tap the button | 422 error toast: "Provide factors + options + at least one unit_value before requesting AI expectations" |
| IU-09 | Factor-type doctrine | Open a freshly imported decision's Factor Tree | Subjective traits (Comfort, Luxury Feel) = Qualitative; objective traits (Color=Blue, Furnishing=Semi, Rent=18000) = Quantitative regardless of data_type |
| IU-10 | Tier fallback notice | Trigger Precise but force exhausted budget (dev) | UI surfaces "Precise tier fell back to Fast — top-up Universal Key to re-enable Claude" |

### UC-AW — AI Wallet & Admin Config
| ID | Scenario | Steps | Expected |
|---|---|---|---|
| AW-01 | User balance | User opens `/profile` → AI Wallet section | Shows balance, recent ledger entries, providers consented |
| AW-02 | Refill quote → order → verify | Tap "Add Balance" → pick pack → checkout via Razorpay test mode | Order created → payment success → balance increases; ledger entry created |
| AW-03 | Provider consent toggle | Toggle OpenAI off → Save | Subsequent calls skip OpenAI in fallback chain |
| AW-04 | Admin reads config | Super-admin → `/admin/ai-wallet-config` | All fields populated; "Precise tier credit multiplier ×N" row recomputes live |
| AW-05 | Admin updates `import_group_threshold` | Change from 15 → 10 → Save → re-import a 12-factor page | New imports honor the new threshold immediately |
| AW-06 | Admin updates `precise_usd_per_mtok` | Change pricing → Save → run a Precise import | Wallet debit reflects new multiplier; PostHog `ai_credits_consumed` event fires |
| AW-07 | Admin grants credits | Super-admin → Grant 1000 credits to test user | User's balance increases; audit log row inserted |

### UC-RC — Revenue Reconciliation (Super-Admin)
| ID | Scenario | Steps | Expected |
|---|---|---|---|
| RC-01 | Open dashboard | `/admin/recon` | Verdict banner (at_risk / safe); 8 KPI cards (net collected, total markup, total cost, buffer) |
| RC-02 | Run sync | Tap "Sync Now" | Razorpay (payments + transfers + settlements) + GCP synced incrementally; "Last synced: just now" stamp updates |
| RC-03 | Per-txn tally | Scroll to Transactions table | Each row shows collected / fee / markup / earmarked_cost / buffer; `at_loss=true` rows highlighted red |
| RC-04 | Daily variance | Scroll to Daily tally | LLM-token-derived ₹ vs GCP actual ₹; variance % per day |
| RC-05 | GCP config upload | Tap "Configure GCP" → paste base64 SA JSON + project_id → Save | Form clears (JSON never echoed); subsequent sync pulls billing-export data |
| RC-06 | CSV export | Tap "Export CSV" with month=2026-06 | Browser downloads `transactions-2026-06.csv` |
| RC-07 | Non-super-admin blocked | Login as regular admin → hit `/admin/recon/summary` | 403 Forbidden |
| RC-08 | Structural at_loss alert | Run on default markup_user_pct → inspect | Verdict shows "at_risk" structurally; banner suggests raising markup_user_pct OR retaining markup in primary |

### UC-PH — PostHog Web Session Replay (browser only)
| ID | Scenario | Steps | Expected |
|---|---|---|---|
| PH-01 | Replay capture | Open app on web → login → navigate 3 screens → log out | PostHog EU dashboard shows session with 3+ pageview events + replay snapshots in `/s/` requests |
| PH-02 | PII not leaked | Fill in a password / OTP field during recorded session | Replay shows masked input (`***`); network bodies absent |
| PH-03 | Anonymous identity | Visit `/pricing` without login | Anonymous session with `distinct_id ≠ user_id`; no identify() call until login |
| PH-04 | Native = events only | Open Expo Go app on phone | Native fires named events (login / decision_created) but no replay snapshots |
| PH-05 | Headless bot detection | Test via vanilla Playwright (no UA spoof) | PostHog silently blocks; verify by spoofing UA + brands + webdriver to enable in tests |

### Performance (v3.16)
| ID | Scenario | Expected |
|---|---|---|
| PERF-IU-1 | Precise Claude import + Set Expectations on 4-option page | ≤ 25 s end-to-end |
| PERF-RC-1 | Recon sync of 100 payments + 30-day GCP | ≤ 15 s |
| PERF-AW-1 | AI Wallet config read + 1 update | ≤ 200 ms |

---
## v3.16.1 — Import-URL hint enforcement (2026-06-12)

| ID | Scenario | Expected |
|---|---|---|
| IU-HINT-1 | Import carwale "best electric cars under 10 lakh" with hints (6 factors, first "All Brands", 4 options, first "Tata Tiago EV") + Costly & Precise AI | 6 facet factors (All Brands, Budget, Body Type, Fuel Type, Transmission, Seating Capacity), 4 cars with Tata Tiago EV first, `ai_provider=emergent_precise`, `hint_warnings=[]` — NOT the thin PRICE/MODEL table |
| IU-HINT-2 | Same URL, NO hints, Cheap & Fast AI | Deterministic table parse allowed (back-compat): PRICE/MODEL accepted, no AI charge |
| IU-HINT-3 | GSMArena 3-phone compare, NO hints | Hierarchical matrix import unchanged (15 categories, no AI extraction charge) |
| IU-HINT-4 | Hints that the AI cannot satisfy either (deliberately wrong, e.g. 50 factors) | Import still succeeds with the best available structure + non-empty `hint_warnings` surfaced in the UI |
| IU-HINT-5 | Precise tier + page whose only table has 2 columns, NO hints | Escalates to Claude extraction (thin-parse rule) |
