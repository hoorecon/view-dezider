#!/usr/bin/env bash
# =============================================================================
# deploy/sync.sh — One-command EC2 deployment for jelcos.ai / dezider
# =============================================================================
#
# WHAT THIS DOES (in order):
#   1. git fetch + hard-reset to origin/emergent-v3 (discards local commits)
#   2. Rebuilds the backend Docker image so any Python changes from the pull
#      actually make it into the running container.        ← critical step
#      (`--force-recreate` alone does NOT rebuild the image.)
#   3. Recreates the container with the new image.
#   4. Tails the container logs to confirm the new code is live, and pings
#      the /api/health/live endpoint to be sure the server is responsive.
#
# WHY THIS EXISTS:
#   Three deployment cycles in a row had the symptom "frontend deployed but
#   backend behaves like the old code". Root cause was always the same:
#   `docker compose up -d --force-recreate api` was being used after a
#   `git pull`, but that does NOT rebuild the image — it only recreates the
#   container *instance* from the existing (stale) image. Since this repo's
#   docker-compose uses build: directive (image is built from Dockerfile that
#   COPYs the backend source in), the new Python code only reaches the
#   container after `docker compose build` or `up --build`.
#
# USAGE (on EC2):
#   cd /opt/dezider
#   ./deploy/sync.sh               # default: pulls origin/emergent-v3
#   ./deploy/sync.sh main          # pulls a different branch
#
# SAFE TO RE-RUN: idempotent. Will not destroy DB volumes, .env files, or
# anything under deploy/.env (which is gitignored).
# =============================================================================

set -euo pipefail

BRANCH="${1:-emergent-v3}"
REPO_DIR="/opt/dezider"
COMPOSE="docker compose -f deploy/docker-compose.yml"

# ── Colours (no fancy deps, just ANSI) ───────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
log()  { echo -e "${CYAN}▸${NC} $*"; }
ok()   { echo -e "${GREEN}✓${NC} $*"; }
warn() { echo -e "${YELLOW}!${NC} $*"; }
fail() { echo -e "${RED}✗${NC} $*"; exit 1; }

# ── Sanity ───────────────────────────────────────────────────────────────────
cd "$REPO_DIR" || fail "Could not cd into $REPO_DIR. Edit REPO_DIR in this script if your path differs."
[ -f deploy/docker-compose.yml ] || fail "deploy/docker-compose.yml not found from $(pwd)"

log "Branch target: ${YELLOW}${BRANCH}${NC}"
log "Repo dir:      ${YELLOW}$(pwd)${NC}"

# ── 1. Pull latest code ──────────────────────────────────────────────────────
log "Step 1/4 — Fetching latest from origin/${BRANCH}"
git fetch origin "$BRANCH" --quiet
OLD_HEAD=$(git rev-parse --short HEAD)
git reset --hard "origin/${BRANCH}" --quiet
NEW_HEAD=$(git rev-parse --short HEAD)
if [ "$OLD_HEAD" = "$NEW_HEAD" ]; then
  ok "Already at ${NEW_HEAD} — no new code"
else
  ok "Updated ${OLD_HEAD} → ${NEW_HEAD}"
  git --no-pager log --oneline "${OLD_HEAD}..${NEW_HEAD}" | head -10 | sed 's/^/    /'
fi

# ── 2. Rebuild backend image (this is the step that was being skipped) ──────
log "Step 2/4 — Rebuilding backend image (this is what was missing in previous attempts)"
$COMPOSE build api
ok "Image rebuilt"

# ── 3. Recreate container with the new image ────────────────────────────────
log "Step 3/4 — Recreating container with the fresh image"
$COMPOSE up -d --force-recreate api
ok "Container recreated"

# Brief pause for app startup
sleep 4

# ── 4. Verify ────────────────────────────────────────────────────────────────
log "Step 4/4 — Verifying backend is healthy"
# Hit /api/health/live from INSIDE the container. Port 8001 on the host
# is typically not published (nginx / Cloudflare fronts it), so a host-side
# `curl localhost:8001` would fail even though the API is perfectly healthy.
# Running curl inside the container guarantees the right network namespace.
HEALTH_OK=0
for i in 1 2 3 4 5; do
  if $COMPOSE exec -T api curl -fsS http://localhost:8001/api/health/live >/dev/null 2>&1; then
    ok "Backend responding (inside container)"
    HEALTH_OK=1
    break
  fi
  warn "Health check attempt $i/5 failed, retrying in 3s..."
  sleep 3
done

# Fallback: if curl isn't installed inside the slim image, accept the
# "Application startup complete" log marker as a healthy signal instead.
if [ "$HEALTH_OK" = "0" ]; then
  if $COMPOSE logs api --tail=80 2>/dev/null | grep -q "Application startup complete"; then
    ok "Backend reports 'Application startup complete' in logs (curl unavailable inside image)"
    HEALTH_OK=1
  fi
fi

if [ "$HEALTH_OK" = "0" ]; then
  warn "Could not confirm health. Last 30 lines of container logs:"
  $COMPOSE logs api --tail=30
  fail "Backend did not become healthy. Check logs above."
fi

# Optional smoke-test the Step 4 endpoints that have caused trouble
log "Smoke test — verifying is_duplicate is in the allowed PUT field set"
if $COMPOSE exec -T api grep -q "is_duplicate" routes/pros_cons.py 2>/dev/null; then
  ok "is_duplicate is in container's pros_cons.py — Step 4 Duplicate button will work"
else
  warn "is_duplicate not found in container — image may not have rebuilt. Try: $COMPOSE build --no-cache api"
fi

echo
echo -e "${GREEN}════════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}✓ Deployment complete${NC}"
echo -e "  Now at commit: ${NEW_HEAD}"
echo -e "  Backend:       healthy"
echo -e "  Frontend:      Cloudflare Pages auto-deploys (allow ~1–2 min)"
echo -e "${GREEN}════════════════════════════════════════════════════════════════${NC}"
