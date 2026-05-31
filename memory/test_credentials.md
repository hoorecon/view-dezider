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
