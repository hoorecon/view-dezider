# Product Requirements Document — Dezider

_metadata: { "version": "3.4", "updated": "2026-05-04", "author": "engineering" }

## 1. Vision

Dezider is a decision-intelligence platform pairing personal decision tools
(PRR, Solution Matrix, Goal Setter…) with a civic feedback rail (Public
Pulse) that lets organisations and government departments listen to the
public at scale, while preserving DPDP / GDPR compliance.

## 2. Personas

| Persona | Daily volume | Primary surfaces |
|---|---|---|
| Individual user | 5–20 sessions/week | PRR flow, Goal Setter, Journal, Solution Matrix |
| Org admin (NGO/SMB/Govt dept) | 1–3 dashboards/day | Public Pulse Org dashboards, Sub-Portal config |
| Govt department | Long horizon | Sub-Portal embedded on dept website, district-demand heatmaps |
| Internal admin | Continuous | ACM, audit logs, system metrics |

## 3. Modules / scope (as of v3.4)

### 3.1 Decision tools (individual)
- **PRR (10-step decision flow)** — voice-enabled, multilingual
- **Test123** quick-decision
- **Solution Finder** (simple)
- **Solution Matrix (advanced)** — NEW: two modes
   - Standard 15-cell (5 TEPFI × 3 layers)
   - Accurate 60-cell (5 TEPFI × 12 layer-orgtype combos)
   - Per-cell positive/negative influence annotations
   - 4 starter templates + PDF export
- **Goal Setter / Goal Manifestation**
- **TEPFI matrix**
- **SWOT, Pros & Cons**
- **CLD engine** (causal-loop simulation, AI-assisted)
- **AALA** (advanced action / life alignment)
- **AAAA** (Action / Awareness / Acceptance / Aspiration)
- **Conflict Breaker, Emotional Gatekeeper, PNA**
- **Lifestyle Designer / Evaluator**
- **GEM Flight, GEM Goal, Time Dezider**
- **Unconditional Happiness, Consciousness Diary, Meditation**

### 3.2 Solutions Store
- 9-language store of human-vetted solution playbooks
- Search by life-area / country / tags
- Voice-driven browsing (English subset)

### 3.3 Public Pulse (civic rail)
- **Phase 1**: anonymous demographic intake + per-tool sessions
- **Phase 2**: research dashboards (district demand, youth job, marriage support, scheme demand, rectification tracker) — all k-anonymity gated
- **Phase 2.5**: Org enrolment, member roles, feedback routing
- **Phase 3** (current): YoY trend analytics + white-labelled Org sub-portals
   - `/p/{slug}` branded public page (no auth)
   - `/embed/{slug}` iframe-safe widget for hosting on org/govt websites
   - `/embed/{slug}/widget.js` auto-iframe injector

### 3.4 Cross-cutting platform
- **Auth**: email/password + (planned) DigiLocker eKYC + (planned) Exotel SMS OTP + WhatsApp OTP via UltraMsg
- **ACM** (Access Control Matrix): 32 modules, 89 features, 10 release stages, per-tier full/locked/hidden access
- **DPDP / GDPR**: data export, soft-delete with 7-day grace, audit log, PII redaction in logs
- **Voice**: 6-language global navigation bubble + per-flow voice input (PRR for now)
- **Subscription**: free / trial / starter / pro / enterprise / api tiers, Razorpay-backed
- **Collaboration**: live video calls, document sharing
- **Notifications**: in-app + push + email
- **Admin**: feature gates, audit logs, system metrics, ACM seeding

## 4. Non-functional requirements (v3.4)

| Concern | Target |
|---|---|
| Concurrent users | 10,000 (4-pod baseline, autoscale to 40 pods) |
| Total users | 1,000,000 |
| API p95 latency | < 300 ms (cache-hot reads); < 1.5 s (uncached) |
| Availability SLO | 99.9% monthly |
| Error budget | 43 minutes/month |
| RTO / RPO | RTO 30 min, RPO 5 min (mongo replica + 5-min snapshots) |
| Cold-start | < 30 s including index check + ACM seed verification |
| Body cap | 10 MB request (configurable via `MAX_BODY_BYTES`) |
| Rate limits | 120/min default, 10/min auth, 10/min AI, 60/min public |
| Data retention | 7-day soft-delete, indefinite for analytics anonymous aggregates |
| Compliance | DPDP (India), GDPR data-portability + erasure, audit-trail immutability |

## 5. Out of scope (v3.4)

- iOS / Android native builds (using Expo over-the-air for now)
- Chat / messaging between users
- Payment for org dashboards (paid tier exists but billing is on the user side)
- Kannada / Malayalam keyboard input optimisations beyond voice
- Real-time collaboration on Solution Matrix entries

## 6. Open / blocked items

| Item | Owner | Status |
|---|---|---|
| DigiLocker eKYC integration | Backend | BLOCKED — awaiting API Setu keys |
| Exotel SMS OTP integration | Backend | BLOCKED — awaiting DLT template approval |
| LLM budget reset | Platform | BLOCKED — budget cap; AI endpoints serve 503 gracefully |
| Public Pulse Phase 3 AI clustering | Backend | DEFERRED — builds on LLM budget reset |
| Multi-language voice for Solutions Store | Frontend | PARTIAL — 9 languages exist for content, voice currently EN-only |

## 7. Changelog

- **3.4 (2026-05-04)**: Solution Matrix dual-mode + influences + PDF + templates; global voice nav (6 lang); Public Pulse YoY analytics; white-label sub-portals; production hardening (sec headers, body cap, gzip, metrics, DPDP, idempotency).
- **3.3 (2026-04-15)**: Solution Matrix OrgType nested schema, Public Pulse Phase 2.5 (org members + feedback routing).
- **3.2 (2026-03-30)**: Public Pulse Phase 2 dashboards + k-anonymity floors.
- **3.1 (2026-03-10)**: Public Pulse Phase 1 + 4 research tools.
- **3.0 (2026-02-20)**: ACM v2 with 89-feature matrix.
