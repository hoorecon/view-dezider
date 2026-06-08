# Test Credentials — Dezider Backend

These are test credentials maintained by the main agent for use by the
testing agent and any fork agents. They are refreshed when stale.

## 🌐 PRODUCTION (AWS EC2 + MongoDB Atlas) — `https://api.jelcos.ai`
- **Email**: `veales.vedic.decisions@gmail.com`
- **Password**: `Jelcos@Admin2026`
- **Role**: `admin`
- **user_id**: `user_920f13fca2ca`
- **Reset path**: No SMTP gateway — `/api/auth/forgot-password` returns OTP directly in JSON.
- ⚠️ NEVER reuse these on dev — they only work against the prod EC2.


## 🔓 WhatsApp gate bypass for UI testing (dev/preview)
- A Super-Admin flag `skip_whatsapp_gate` (Admin → Settings, or `PUT /api/admin/security-config {"skip_whatsapp_gate": true}`) bypasses the post-login `/whatsapp-verify` gate for ALL users.
- It is currently **ON in dev/preview** so login lands straight in the app. Turn OFF for production.
- Fallback if ever OFF: `POST /api/auth/whatsapp/send-otp {"phone_number":"+919876543210"}` (response echoes `dev_code`), then `POST /api/auth/whatsapp/verify-otp {"code":"<dev_code>"}`.

---

## 🧪 DEV / Emergent workspace (local backend at port 8001)

## Admin user (role=admin) — ACTIVE
- **Email**: `admin@test.com`
- **Password**: `AdminPass2026!`
- **Role**: `admin`
- **Use for**: admin-only endpoints (DPDP audit log, /api/admin-docs, /api/metrics/json, ACM seed)
- **NOTE (security lockdown)**: This account is NOT the root super-admin, so it MUST receive 403 on `/api/admin/promote`, `/api/admin/demote`, `/api/admin/setup`.

## Root Super Admin (role=super_admin) — DEV mirror of prod root — ACTIVE
- **Email**: `veales.vedic.decisions@gmail.com`
- **Password**: `Jelcos@Admin2026`
- **Role**: `super_admin`
- **user_id**: `user_87819d8c4fd3`
- **Use for**: the ONLY account allowed to grant/revoke admin roles (`/api/admin/promote`, `/api/admin/demote`). Positive-path role-management tests.

## Primary test user (regular user role)
- **Email**: `harden_1777921741@example.com`
- **Password**: `HardenPass2026!`
- **Role**: `user`
- ⚠️ **NOTE (SKU entitlements):** this user OWNS an `L1` entitlement (balance>0). So for "locked solution" tests (SKU↔Solution mapping) this user will appear UNLOCKED via L1. To test the LOCKED view, register a fresh throwaway user (see below) which has no L1-L4 entitlements.

## How to login fresh (if token expired)
```
curl -X POST http://localhost:8001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"harden_1777921741@example.com","password":"HardenPass2026!"}'
```

## Or register a new throwaway account
```
EMAIL="auto_$(date +%s)@example.com"
curl -X POST http://localhost:8001/api/auth/register \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$EMAIL\",\"password\":\"AutoPass2026!\",\"name\":\"Auto Tester\"}"
```
The response will contain `session_token` for Bearer header use.

## Public routes that DON'T require auth
- `GET  /api/health`, `/api/health/ready`
- `GET  /api/p/{slug}` and `/api/embed/{slug}` (public org sub-portals)
- `GET  /api/public-pulse/analytics/yoy/*`
- `GET  /api/public-pulse/dashboards/*`
- `GET  /api/feature-flags/public`

## Real org slug for portal-flow tests
- `coimbatore-skills-foundation-5b9c19` (status=approved in pp_orgs)

## Notes
- Email domains using `.test`/`.example`/`.localhost` are REJECTED by Pydantic email validation. Use `@example.com`, `@test.com`, or any real-looking domain.
- Tokens expire after 7 days; re-issue via `/api/auth/login` if `/api/auth/me` returns 401.

## Embed Partner Demo (P0 — PMSBazaar pitch) — DEV
- Tool/APIs: org login `/api/org-auth/*`, embed config `/api/embed/*`
- **Org slug**: `pmsbazaar-demo` (BUSINESS, maroon #7B1E3B brand)
- **Org member**: `analyst@pmsbazaar-demo.com` / `PmsAnalyst2026!` (org_member, whatsapp 919000000001)
- **Org admin**: `admin@pmsbazaar-demo.com` / `PmsAdmin2026!` (org_super_admin, whatsapp 919000000002)
- Embed config is **frictionless** by default (otp_required=false, expose_dev_code=true) so org login returns a session_token directly. Toggle OTP via admin `PUT /api/embed/config/pmsbazaar-demo {otp_required:true}` → org login returns `dev_code` for testing.
- Re-seed anytime: `cd /app/backend && python -m scripts.seed_embed_partner_demo` (idempotent).
- Public widget config (no auth): `GET /api/embed/public-config/pmsbazaar-demo`.
- Admin config CRUD (platform admin only): `GET/PUT /api/embed/config/{slug}`, `GET /api/embed/partners`.

## WhatsApp verification gate (NEW — June 2026)
- After login, the app routes any user with `whatsapp_verified != true` to `/whatsapp-verify` before they can use the in-app tabs.
- To pass the gate during testing: `POST /api/auth/whatsapp/send-otp` with `{ "phone_number": "+919876543210" }`. The JSON response echoes `dev_code` (since live WhatsApp delivery may be unconfigured). Then `POST /api/auth/whatsapp/verify-otp` with `{ "code": "<dev_code>" }`.
- `GET /api/auth/whatsapp/status` returns `{ whatsapp_number, whatsapp_verified }`.
- The `/store` route and `/admin` area are NOT behind this gate.


## Quota Editor (Admin) test data — DEV
- Tool: /admin/quota-editor  · APIs under /api/admin/quota/*
- Super admin with WhatsApp set (OTP recipient): super@test.com (whatsapp 918888800000). Also veales super admin works.
- can_edit_quota grant test: admin@test.com starts WITHOUT the permission (expect 403 on lookup until super admin grants via POST /api/admin/quota/grant {email, grant:true}).
- Target user for lookup: email ad.shezhiyanraj@gmail.com + mobile 919999900000 (seeded L1 entitlement balance=1,000,000 consumed=3 to simulate the over-allocation).
- WA_OTP_EXPOSE_DEV_CODE=true in dev → POST /api/admin/quota/request-otp returns dev_code for automated testing (hidden in prod).
