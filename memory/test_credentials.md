# Test Credentials (Emergent migration environment — updated 2026-07-20)

Auth type: email + password → POST /api/auth/login returns `session_token`
(Bearer token, 7-day expiry). Send as `Authorization: Bearer <token>`.
DB: local MongoDB, DB_NAME=dezider (restored snapshot of prod Atlas, 198 collections / 3875 docs).

## Super Admin (prod account from restored Atlas snapshot — WORKS)
- Email: veales.vedic.decisions@gmail.com
- Password: Jelcos@Admin2026
- role: super_admin, is_admin: true

## Regular test user (created in local DB during migration — WORKS)
- Email: migration.tester@test.com
- Password: MigTest2026!
- role: user

## ⚠️ Stale credentials (do NOT use — existed only in old preview DB, absent from prod snapshot)
- super@test.com / SuperPass2026! → "Invalid email or password"
- admin@test.com / AdminPass2026! → "Invalid email or password"

## Rate limits (active): RATE_LIMIT_AUTH=10/minute — space out login attempts during testing.
