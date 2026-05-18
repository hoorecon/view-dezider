# Carry-forward — last fork

## ✅ Done in this fork (2026-05-18)

### 8-step Pros & Cons / SWOT decision framework
Implementation of the 8-step framework mapped 1:1 against the user's
`REFERENCE Career Consultation to Dr Raj.xlsx` workbook.

**Backend:**
- NEW `backend/models/decision_framework_models.py` — shared Pydantic
  models: `FrameworkFactor`, `DecisionOption`, `AssessmentCell`, `FrameworkConfig`,
  `FINAL_DECISION_GUIDELINES` (12 reference rules), plus pure helpers:
  `compute_cell_value`, `compute_realistic_rating`, `compute_satisfaction_value`,
  `compute_option_rollups`.
- `backend/routes/pros_cons.py` — extended with 18 new endpoints
  (factors CRUD + reorder, options CRUD, per-option pros/cons CRUD,
  promote pros-cons → factors, config, assessments upsert, aggregate, step).
  Cons are auto-prefixed with `"SHOULD NOT - "` on promotion (per spec).
- `backend/routes/swot.py` — mirrored set of 18 endpoints over `db.swot_analyses`,
  same shape so a single wizard UI can drive both modules.

**Frontend:**
- NEW `frontend/app/tools/pros-cons-wizard.tsx` — full 8-step wizard with
  horizontal step strip, per-step UI:
    1. List direct factors (name + optional expected value/unit)
    2. List options + per-option pros/cons
    3. Auto-promote pros→factors, cons→`SHOULD NOT - `factors
    4. Manual de-dup / group under direct factor (parent selector)
    5. Collapsible factor tree (parent + sub-factors)
    6. Mandatory(A) / Optional(B) + knock-out threshold %
    7. Drag-reorder priority + std_rating + per-option Assessment % (cell value auto)
    8. Full assessment matrix: subjective/objective, improvable, expectations,
       gap, realistic rating, actual value, satisfaction%, satisfaction value;
       per-option Overall Satisfaction % with knock-out flag and ranking
  Final Decision Guidelines modal (the 12 tie-breaker rules) accessible from
  the header bulb icon and via a CTA at the end of Step 8.
- `frontend/app/tools/pros-cons.tsx` — added "Open 8-Step Framework" gradient
  CTA in detail view.
- `frontend/app/tools/swot.tsx` — added the same CTA.

**Smoke tests (manual curl) — all PASS:**
- Pros & Cons full flow: create → factor → 2 options → 1 pro + 1 con per option →
  promote (3 pros/cons → factors, cons prefixed `SHOULD NOT - `) → mandatory + 60%
  threshold → assessments → aggregate
  - Cell value = `Assessment% × Std Rating` ✅
  - Satisfaction Value = `Realistic Rating × % Satisfaction` ✅
  - Per-option Overall Satisfaction % computed ✅
  - Mandatory knock-out: Car Y disqualified for assessment 50% < threshold 60% ✅
  - Surviving options ranked high-to-low ✅
  - 12 Final Decision Guidelines returned ✅
- SWOT mirror: same flow, identical math, all 200 OK.

### Other (carry-overs from prior forks, still valid)
- `/api/decision-links/sources` was reported broken — verified working (200 OK).
- 7-Chakra subscription tier matrix, Public Pulse, Customer Segments,
  WebFrame, AdminShell, Decision Enhancements #4 timing + #5 linking
  are all in place from prior sessions.

---

## 🟠 P1 — Open backlog (not blockers)
- **Decision Enhancements #4 + #5 UI polish** — backend models support deadline +
  impact horizon configurable units + linking + single-option bypass, but the
  PRR `new.tsx` form still needs the chip-based unit picker (days/weeks/months/
  years, default 1 week) and the single-option bypass link.
- **AI guidance for de-dup / group** (Step #4) — RESERVED for WOWO subscription tier
  per user direction. Hook point exists; just no UI yet.
- **Sub-factor level rating** (Step #5) — RESERVED. Sub-factor display only for now.
- **Step #7 dual rankings** (high-to-low + low-to-high columns) — RESERVED.

## 🔴 P0 — External blockers (unchanged)
- DigiLocker eKYC keys (API Setu) — awaiting user.
- Exotel SMS OTP DLT template — awaiting user.
- LLM budget cap (Emergent LLM Key) — still capped; AI flows 503 gracefully.

## 🎯 Recommended next-fork plan
1. UI screenshot UAT for the new wizard at all 8 steps.
2. Wire Enhancement #4 chip-unit picker in `prr/new.tsx`.
3. Implement Step #4 AI suggestion (when LLM budget resets).
