# Dezider — Roadmap / Prioritized Backlog
_Split out of PRD.md on 12 Jun 2026. Cross-check CHANGELOG.md before picking up items._

## P1 — Upcoming
- **CLD Engine Phase B & C** — Rules Engine + AI Suggestions
- **PRR Enhancement #4 & #5** — configurable timing fields & decision-linking bypass
- **DigiLocker eKYC Integration** — BLOCKED pending API Setu keys from user

## P2 — Future
- Webhook API Integration
- Org-Type Master Migration
- Dashboard cluttered with empty "Draft" sessions — lazy session creation or filter
  `status="draft"` from Recent Sessions (user paused this; resume only on explicit ask)
- Notification Engine: register additional trigger events as needs emerge
  (e.g. wallet-low-balance, weekly revenue digest) — one builder function each

## Refactoring
- `Step2.tsx` (>1200 lines) — component breakdown
- `eg-*.tsx` screens — extract shared custom hook for AI execution/state setup
