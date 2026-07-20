# /app/mobile — deployer-compatibility stub

This directory exists ONLY to satisfy the Emergent deployment pipeline.

The base image (`expo_mongo_base_image`) declares a `mobile` supervisor service
pointing at `/app/mobile`, and the production deployer's PullSource stage
requires `mobile/.env` in the build context. This app does **not** have a
separate mobile codebase — web AND mobile are the single Expo app in
`/app/frontend`.

- `mobile/.env` here is a comment-only stub (no secrets, safe to commit).
- There is intentionally no `package.json` here: the `mobile` supervisor
  service simply stays FATAL/inactive (same as in the preview environment),
  which is harmless — health checks target the backend (8001) and web
  frontend (3000).

Do not add real configuration here. See `DEPLOYMENT_EMERGENT.md`.
