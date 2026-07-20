# Test Credentials (Emergent migration environment — updated 2026-07-20, Phase 3)

Auth type: email + password → POST /api/auth/login returns `session_token`
(Bearer token, 7-day expiry). Send as `Authorization: Bearer <token>`.
DB: local MongoDB, DB_NAME=dezider (restored prod Atlas snapshot + local test fixtures).

## Super Admin (prod account from restored Atlas snapshot — WORKS)
- Email: veales.vedic.decisions@gmail.com
- Password: Jelcos@Admin2026
- role: super_admin, is_admin: true

## Super Admin (local test fixture — WORKS)
- Email: super@test.com
- Password: SuperPass2026!
- role: super_admin

## Admin (local test fixture — WORKS)
- Email: admin@test.com
- Password: AdminPass2026!
- role: admin

## Regular users (local test fixtures — WORK)
- migration.tester@test.com / MigTest2026! (role: user)
- harden_1777921741@example.com / HardenPass2026! (role: user — used by backend_test.py / v372 / admin_seed suites)

## Rate limits (active): RATE_LIMIT_AUTH=10/minute — space out login attempts during testing.
