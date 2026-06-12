# Security posture & threat model — Dezider

_metadata: { "version": "3.16.0", "updated": "2026-06-12" }

## Identity & sessions

- **Storage**: Argon2-rated bcrypt passwords (`passlib`). Salted; cost auto-tuned.
- **Sessions**: 32-byte random tokens, server-side state in `user_sessions` (we do *not* use stateless JWTs so we can revoke immediately on logout / DPDP delete).
- **TTL**: 7 days; refreshable via `/auth/refresh`.
- **Cookies**: `Secure`, `HttpOnly`, `SameSite=Lax` (in prod — `SameSite=None; Secure` if you cross-origin embed).
- **Brute force**: `RATE_LIMIT_AUTH=10/minute` per user/IP, slowapi-backed.

## Network posture

| Layer | Posture |
|---|---|
| TLS | Terminated by NGINX / k8s ingress; HSTS 2y in prod |
| CORS | Wide-open (`*`) on `/api/*` because of public sub-portal embeds; tighten via NGINX if needed |
| CSP | `frame-ancestors *` for embed routes; restrictive default elsewhere |
| iframes | `X-Frame-Options: ALLOWALL` only on `/api/embed/*`; `SAMEORIGIN` everywhere else |
| Body cap | 10 MB per request |
| Method cap | None (FastAPI rejects unknown verbs with 405) |

## Headers applied to every response

```
X-Content-Type-Options: nosniff
Referrer-Policy: strict-origin-when-cross-origin
X-DNS-Prefetch-Control: off
Permissions-Policy: camera=(self), microphone=(self), geolocation=(self), interest-cohort=(), payment=(self), accelerometer=(), gyroscope=()
Cross-Origin-Opener-Policy: same-origin-allow-popups
Cross-Origin-Resource-Policy: cross-origin
X-Frame-Options: SAMEORIGIN     (embed routes override to ALLOWALL)
Content-Security-Policy: default-src 'self'; ...
Strict-Transport-Security: max-age=63072000; includeSubDomains; preload  (prod only)
```

## Data protection

| Concern | Mitigation |
|---|---|
| Passwords | bcrypt, never logged, never returned |
| Email/Phone in logs | regex-redacted by `_PiiRedactingFilter` on root logger |
| Aadhaar / PAN in logs | regex-redacted |
| Backups | mongodump nightly; 5-min replica oplog |
| Encryption at rest | mongo storage-engine encryption (Atlas: on by default; self-host: enable wiredtiger encrypted storage) |
| Encryption in transit | TLS at the ingress; mongo connections use TLS |

## DPDP / GDPR

- **Right to data portability**: `GET /api/dpdp/export` returns full JSON.
- **Right to erasure**: `POST /api/dpdp/delete-request` → 7-day grace → `POST /api/dpdp/admin/purge-pending` (cron).
- **Audit log**: `audit_log` collection is append-only (no update/delete in code paths).
- **Consent**: `pp_consents` collection records purpose-by-purpose consent + withdrawal time.
- **Anonymisation**: research data is bucketed (district + age-group) and only released past k-anonymity thresholds.

## Threat model (top 10 STRIDE)

| # | Threat | Vector | Mitigation |
|---|---|---|---|
| 1 | Spoofing | stolen session token | Session is server-side; revoke on logout, on DPDP delete, on password change |
| 2 | Spoofing | iframe phishing | `frame-ancestors *` only on read-only embed routes; submit endpoints CORS-protected by ingress |
| 3 | Tampering | request body manipulation | Pydantic strict models, server-side authoritative ids, bcrypt+jwt for state-mutation APIs |
| 4 | Repudiation | user denies action | `audit_log` + IP hash + request_id |
| 5 | Info disclosure | mongo direct access | network-level (private VPC) + auth + TLS |
| 6 | Info disclosure | log scraping | PII redaction filter on root logger |
| 7 | DoS | huge bodies | 10 MB cap + ingress max-body |
| 8 | DoS | brute force | slowapi 10/min on auth |
| 9 | EoP | SQL/NoSQL injection | Pydantic + motor parameterised queries |
| 10 | EoP | LLM prompt injection | Server treats LLM output as untrusted; never `eval`/`exec`; whitelisted JSON schema |

## Vulnerability disclosure

- security@dezider.app  (PGP key in DEPLOYMENT.md)
- 90-day coordinated disclosure window

## Periodic review (calendarised)

- Quarterly: dependency `pip-audit` + `npm audit`
- Quarterly: rotate `METRICS_TOKEN`, `JWT_SIGNING_KEY` (when added), DB user passwords
- Quarterly: tabletop: "What if an admin token leaks?"
- Annual: external pentest

---
## v3.16.0 — PostHog Privacy & Recon Hardening (2026-06-12)

### PostHog (analytics + session replay)
- **Project**: EU cloud (`https://eu.i.posthog.com`), project ID 199570 — no data leaves EU.
- **Identity**: `identify(user_id)` only. We never send `email`, `phone`, `name`, `aadhaar`, `pan`, or any PII through PostHog properties.
- **Session replay (web only)** uses `posthog-js@1.386` with:
  - `maskAllInputs: true` — all form inputs masked at the DOM level.
  - `capture_performance: false` — network request bodies are NOT recorded (no risk of JWT/OTP/payment payload leakage in replays).
  - `person_profiles: 'identified_only'` — no anonymous-only profiles created.
  - `capture_pageview: false` — we emit `$pageview` manually per expo-router change.
- **Native (Android/iOS)** uses `posthog-react-native`: events-only, NO replay capability by SDK design.
- **Bot detection caveat** (operational, not user-facing): `posthog-js` silently blocks captures when UA / `userAgentData.brands` / `webdriver` flags indicate headless automation; affects Playwright CI but not real users.

### Revenue Reconciliation
- All `/api/admin/recon/*` routes gated by `require_super_admin` (not just `require_admin`).
- GCP Service-Account JSON stored **base64-encoded in `recon_config` collection** — never written to disk, never returned by `GET /admin/recon/gcp-config` (only a presence flag is returned).
- BigQuery queries capped at **2 GB `maximum_bytes_billed`** to bound cost and prevent runaway scans.
- CSV export is streamed via `PlainTextResponse` — no full in-memory materialisation.
- Razorpay webhook (`/ai-wallet/refill/webhook`) is idempotent (dedupes on `razorpay_payment_id`).

### AI Wallet
- Wallet config writes require `require_super_admin`.
- `precise_usd_per_mtok` validated `> 0` (prevents zero-multiplier exploit that would let users run Claude for free).
- Provider consent stored per-user; defaults to "opt-in for all" with explicit consent on first paid call.

### Threat-model additions (v3.16)
| # | Threat | Vector | Mitigation |
|---|---|---|---|
| 11 | Replay disclosure | Replay snapshots leak DOM inputs | maskAllInputs + capture_performance:false + person_profiles:identified_only |
| 12 | GCP cost runaway | Malicious admin runs unbounded BigQuery | 2 GB max-bytes-billed cap + super-admin gating |
| 13 | SA JSON exfiltration | Browser-side reflection of GCP credentials | Never returned by GET; only `has_gcp_config=true` flag |
| 14 | Free LLM exploit | Zero or negative price multiplier | Server-side `> 0` validation on `precise_usd_per_mtok` |
| 15 | Recon write spoof | Non-admin attempts to backfill recon collections | `require_super_admin` on every route + `audit_log` entry on writes |

### Periodic review additions (calendarised)
- Monthly: review `recon_runs.at_risk` count; if non-zero raise `markup_user_pct`.
- Monthly: rotate Razorpay webhook secret if any 4xx spike observed.
- Quarterly: rotate ScraperAPI + Resend + UltraMsg keys.
