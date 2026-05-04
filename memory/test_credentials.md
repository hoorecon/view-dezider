# Test Credentials — Dezider Backend

These are test credentials maintained by the main agent for use by the
testing agent and any fork agents. They are refreshed when stale.

## Primary test user (regular user role)
- **Email**: `harden_1777921741@example.com`
- **Password**: `HardenPass2026!`
- **Token (Bearer)**: `session_0009d555be6b4e5fba9161afb526b463`
- **Created**: 2026-05-04 18:29 UTC
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
