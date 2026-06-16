# Collab Integration Recipe — v3.23

Wiring step-share + A/V appointment + decision-continue CTAs into any module.

## The 3 reusable pieces

1. **`CollabBar`** — small two-button row that exposes “Share this step” and “Schedule call”.
2. **`DecisionContinuePanel`** — end-of-flow CTA panel offering the 8 onward modules.
3. **`StepShareModal`** / **`AppointmentSchedulerModal`** — already mounted inside `CollabBar`; only use directly if you need a custom trigger.

## Wiring recipe (per module)

```tsx
// 1. Add imports
import { CollabBar } from '../../src/components/CollabBar';
import { DecisionContinuePanel } from '../../src/components/DecisionContinuePanel';

// 2. Inside the active-decision render, just below the title / step header:
{decisionId && (
  <CollabBar
    module="pros-cons"            // 'conflict-breaker' | 'pros-cons' | 'swot' |
                                   // 'solution-finder' | 'goal-setter' | 'my-dezider'
    decisionId={decisionId}        // the analysis / session id
    stepId={currentStepKey}        // a stable string per step
    stepLabel={currentStepLabel}   // human-readable label
    decisionTitle={analysis.title}
  />
)}

// 3. At the very end of the active-decision render (after the final
//    step / recommendation), before </ScrollView>:
{isOnFinalStep && (
  <DecisionContinuePanel
    sourceModule="pros-cons"
    sourceDecisionId={decisionId}
    title={analysis.title}
    contextSummary={`From your Pros & Cons analysis on ${analysis.created_at?.slice(0,10) || 'today'}.`}
  />
)}
```

### Step IDs (suggested)

| Module | Suggested `stepId` keys |
|---|---|
| `pros-cons` | `s1_context` → `s8_final_recommendation` |
| `swot` | `s_strengths`, `s_weaknesses`, `s_opportunities`, `s_threats`, `s_synthesis` |
| `solution-finder` | `s_problem`, `s_constraints`, `s_options`, `s_selected_solution` |
| `goal-setter` | `s_define`, `s_smart`, `s_milestones`, `s_lock` |
| `my-dezider` | `s_step_1` … `s_step_8` |

### Final step (where to mount `DecisionContinuePanel`)

| Module | Final step |
|---|---|
| Conflict Breaker | After step 9 (Follow-Up and Closure) — **already wired** |
| Pros & Cons | After Final Recommendation |
| SWOT | After AI Synthesis |
| Solution Finder | After Selected Solution |
| Goal Setter | After Goal Locked |

## Backend collab endpoints (already live)

| Path | Purpose |
|---|---|
| `POST /api/collab/invite` | Owner creates a share invite |
| `GET /api/collab/invite/{id}` | Invitee opens the link |
| `POST /api/collab/invite/{id}/submit` | Invitee submits |
| `POST /api/collab/invite/{id}/merge` | Owner accepts (optional override notes) |
| `POST /api/collab/invite/{id}/cancel` | Owner cancels |
| `GET /api/collab/invites/owner/{module}/{decision_id}` | Owner: list invites |
| `GET /api/collab/invites/incoming` | Invitee: list inbound invites |
| `POST /api/collab/appointment` | Schedule an A/V call |
| `GET /api/collab/appointments/{module}/{decision_id}` | List appointments |
| `POST /api/collab/appointment/{id}/cancel` | Cancel an appointment |

Reminders run from the existing notification engine tick (60 s). No new scheduler.

## Notes

- **In-app only**: invites route to `/share/invite/[id]`. If the invitee isn't logged in, the page bounces them to `/login?next=...` — the existing signup flow (with WhatsApp OTP) already handles new users.
- **Late submissions**: stored with `late: true` and not auto-merged; owner sees them as “late note”.
- **Merge preserves originality**: the invitee submission is immutable; owner adds free-form `override_notes`.
- **A/V** uses the existing `jitsi-room.tsx` page; `jitsi_room` field is set on the appointment doc.
- **Org-level theming** (future): the appointment + invite docs carry `module_label` already; org theming hooks can be layered later without schema changes.
