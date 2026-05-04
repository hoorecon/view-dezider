# UAT Test Cases — Dezider

_metadata: { "version": "3.4", "updated": "2026-05-04" }

UAT scripts grouped by area. Each scenario is independently runnable in
5–10 minutes by a non-engineer using the production app + a real account.

## Auth & onboarding

| ID | Scenario | Steps | Expected |
|---|---|---|---|
| AUTH-01 | New signup | Open app → sign up with new email | Verification mail → click link → lands on tools hub |
| AUTH-02 | Login persistence | Sign in → close app → reopen 24h later | Still signed in (token TTL is 7 days) |
| AUTH-03 | Forgot password | Tap "Forgot" → enter email | Email arrives within 30 s; reset link valid 1h |
| AUTH-04 | Logout | Profile → Logout | Lands on /auth/login; cannot reach tools |
| AUTH-05 | Brute force protection | 11 wrong passwords in a minute | 11th attempt rate-limited (429) |

## Solution Matrix (NEW)

| ID | Scenario | Steps | Expected |
|---|---|---|---|
| SM-01 | Standard mode quick fill | Open Solution Matrix → Step 4 → toggle Standard | Only SELF/MICRO/MACRO tabs; no OrgType row |
| SM-02 | Accurate mode | Toggle Accurate | OrgType chips appear (Individual/Org/Govt/Nature) |
| SM-03 | Influence annotation | Tap "Add +/-" on Time field | Positive + Negative inputs expand; persist on save |
| SM-04 | Use template | Tap albums icon → pick "Home Renovation" | Wizard auto-fills with template data |
| SM-05 | PDF export | Save matrix → tap download icon | PDF downloads on web; opens URL on mobile |
| SM-06 | Locked OrgType | (free tier) Open Accurate mode | Govt + Nature chips show lock icon; tapping shows upgrade modal |

## Public Pulse

| ID | Scenario | Steps | Expected |
|---|---|---|---|
| PP-01 | Consent flow | First-run | Consent screen appears; cannot skip |
| PP-02 | Withdraw consent | Profile → Privacy | Withdraw button; immediate effect |
| PP-03 | Take a research tool | Tools → Pulse → Life Direction | Wizard runs; submit → thank-you screen |
| PP-04 | Submit feedback | Pulse → Feedback | Form accepts up to 4000 chars; success toast |
| PP-05 | Dashboards | Pulse → Insights | At least 5 tabs render; some may be k-anon-blocked early on |
| PP-06 | YoY trend | Insights → YoY tab | Target picker; tiles + monthly bars OR k-anon block |

## Public Sub-Portal (NEW)

| ID | Scenario | Steps | Expected |
|---|---|---|---|
| PORTAL-01 | Open by slug | Visit `/p/coimbatore-skills-foundation-5b9c19` | Branded header + about + form (no login required) |
| PORTAL-02 | Submit anonymous feedback | Fill form on portal | Success message #ID |
| PORTAL-03 | Bad slug | Visit `/p/does-not-exist` | Error card with "Go home" |
| PORTAL-04 | Iframe embed | Add `<script src="/api/embed/{slug}/widget.js" data-target="x"></script>` to a govt site | Widget loads; submission works from third-party domain |
| PORTAL-05 | Resolved feedback | After org marks one feedback resolved | Item appears in `/p/{slug}/feedback/public` list |

## Voice navigation (NEW)

| ID | Scenario | Steps | Expected |
|---|---|---|---|
| VOICE-01 | Bubble visibility | Sign in → land on tools hub | Mic bubble visible bottom-right |
| VOICE-02 | Pre-login hidden | On /auth/login | Bubble NOT visible |
| VOICE-03 | Inside wizard hidden | Open PRR step 3 | Bubble NOT visible |
| VOICE-04 | English voice command | Tap bubble → say "open goal setter" | Sheet closes, navigates to /tools/goal-setter |
| VOICE-05 | Hindi voice command | Switch to हिन्दी → say "लक्ष्य निर्धारण" | Navigates to /tools/goal-setter |
| VOICE-06 | Hint chip | Tap "goal setter" hint | Navigates immediately (no voice needed) |

## DPDP (NEW)

| ID | Scenario | Steps | Expected |
|---|---|---|---|
| DPDP-01 | Export my data | Profile → Privacy → Export | JSON file downloads with my data |
| DPDP-02 | Delete request | Profile → Privacy → Delete | 7-day grace warning; confirm |
| DPDP-03 | Cancel within grace | Profile → Privacy → Cancel deletion | Status returns to "none" |
| DPDP-04 | Grace expiry | (admin only) Wait 7 days, hit purge endpoint | User record tombstoned, all data purged |

## Performance / load (manual)

| ID | Scenario | Expected |
|---|---|---|
| PERF-01 | Open list of 100 matrices | < 2 s on 4G |
| PERF-02 | PDF for 60-cell matrix | < 3 s end-to-end |
| PERF-03 | YoY dashboard | < 2 s with k-anon-friendly data |
