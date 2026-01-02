# View Dezider Runbook

## Prerequisites
- Java 17
- Maven 3.9+
- MySQL 8
- Node.js 18+ (frontend & mobile)

## Database Setup
```bash
cd db
./init.sh
```
Environment variables:
- `MYSQL_HOST` (default `127.0.0.1`)
- `MYSQL_PORT` (default `3306`)
- `MYSQL_USER` (default `root`)
- `MYSQL_PASSWORD` (default `password`)

## Backend
```bash
cd backend
mvn test
mvn spring-boot:run
```

## Web Frontend
```bash
cd frontend-web
./run.sh
```
Open `http://localhost:3000` and set `localStorage.viewdezider_token` to your JWT.

## Mobile App
See `/mobile-app/run.md`.

## Acceptance Test (Happy Path)
```bash
# Register and login
curl -X POST http://localhost:8080/api/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@viewdezider.local","password":"password","role":"ADMIN"}'

TOKEN=... # replace with token from response

# Seeded project results
curl -X POST http://localhost:8080/api/projects/1/compute \
  -H "Authorization: Bearer $TOKEN"

# Export JSON
curl http://localhost:8080/api/projects/1/export \
  -H "Authorization: Bearer $TOKEN"
```
Expected: one option is disqualified by the hard gate and results are ranked.

## Deployment Notes
- Set `jwt.secret` to a strong secret.
- Configure MySQL credentials in `backend/src/main/resources/application.yml`.
- Serve `/frontend-web` from a static host or CDN.
