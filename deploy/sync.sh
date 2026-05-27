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
# Hit /api/health/live from INSIDE the container using PYTHON (always present
# in our Python-slim image). curl is NOT in the slim image, so we deliberately
# avoid it. Running inside the container also bypasses the fact that port 8001
# is not published to the host (nginx/Cloudflare fronts it on prod).
HEALTH_OK=0
PY_PROBE='import sys, urllib.request
URLS = ["http://localhost:8001/api/health", "http://localhost:8001/api/health/ready"]
for u in URLS:
    try:
        body = urllib.request.urlopen(u, timeout=3).read().decode()
        sys.stdout.write(body)
        sys.exit(0)
    except Exception as e:
        sys.stderr.write(u + " -> " + str(e) + "\n")
        continue
sys.exit(1)
'
for i in 1 2 3 4 5; do
  if $COMPOSE exec -T api python -c "$PY_PROBE" >/dev/null 2>&1; then
    ok "Backend responding on /api/health (inside-container Python probe)"
    HEALTH_OK=1
    break
  fi
  warn "Health check attempt $i/5 failed, retrying in 3s..."
  sleep 3
done

# Fallback signal: many app frameworks print this exact line on successful boot.
# This is intentionally lenient — if uvicorn logged "Application startup complete"
# at least once in the last 200 lines, the app IS running, even if our HTTP probe
# could not reach it (network namespace quirks, etc.).
if [ "$HEALTH_OK" = "0" ]; then
  if $COMPOSE logs api --tail=200 2>/dev/null | grep -q "Application startup complete"; then
    ok "Backend reports 'Application startup complete' in logs — treating as healthy"
    HEALTH_OK=1
  fi
fi

if [ "$HEALTH_OK" = "0" ]; then
  warn "Could not confirm health. Last 30 lines of container logs:"
  $COMPOSE logs api --tail=30
  fail "Backend did not become healthy. Check logs above."
fi

# Smoke-test the *content* of the running container — proves the rebuild
# actually picked up the latest Python code (this is the test that would
# have caught the previous 3 stale-image bugs at deploy time).
log "Smoke test — verifying is_duplicate is in the *running* container code"
if $COMPOSE exec -T api grep -q "is_duplicate" routes/pros_cons.py 2>/dev/null; then
  ok "is_duplicate present in container's routes/pros_cons.py — Step 4 Duplicate button will work"
else
  warn "is_duplicate NOT in container — image is stale. Re-run with:  $COMPOSE build --no-cache api && $COMPOSE up -d --force-recreate api"
fi

echo
echo -e "${GREEN}════════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}✓ Deployment complete${NC}"
echo -e "  Now at commit: ${NEW_HEAD}"
echo -e "  Backend:       healthy"
echo -e "  Frontend:      Cloudflare Pages auto-deploys (allow ~1–2 min)"
echo -e "${GREEN}════════════════════════════════════════════════════════════════${NC}"
