#!/usr/bin/env bash
# =============================================================================
# deploy/sync.sh — One-command EC2 deployment for jelcos.ai / dezider
# =============================================================================
#
# USAGE (on EC2):
#   cd /opt/dezider
#
#   # 1) Simple sync (default branch = emergent-v3, no commit amend)
#   ./deploy/sync.sh
#
#   # 2) Specific branch
#   ./deploy/sync.sh main
#
#   # 3) Sync AND amend the latest commit message from a file
#   ./deploy/sync.sh emergent-v3 /tmp/msg.txt
#
#   # 4) Sync AND amend the latest commit message from STDIN (heredoc)
#   ./deploy/sync.sh emergent-v3 - <<'COMMIT_MSG'
#   feat(scope): one-line headline
#
#   - bullet 1
#   - bullet 2
#   COMMIT_MSG
#
# WHAT THIS DOES (in order):
#   1. git fetch + hard-reset to origin/<branch> (discards local commits)
#   2. Rebuilds the backend Docker image (so Python changes from the pull
#      actually make it into the running container).        ← critical
#   3. Recreates the container with the new image.
#   4. Health-checks /api/health (and /api/health/ready) using a Python urllib
#      probe from INSIDE the container — slim images don't have curl.
#   5. (Optional) git commit --amend -F <msg> && git push --force-with-lease
#      ONLY runs if (a) a message was supplied and (b) backend is healthy.
#
# WHY THIS EXISTS:
#   Three deployment cycles in a row had the symptom "frontend deployed but
#   backend behaves like the old code". Root cause: `up -d --force-recreate`
#   does NOT rebuild the image. Since docker-compose builds the image with a
#   COPY of the backend source, the new Python code only reaches the
#   container after `docker compose build` or `up --build`.
#
# SAFE TO RE-RUN: idempotent. Will not destroy DB volumes, .env files, or
# anything under deploy/.env (which is gitignored).
# =============================================================================

set -euo pipefail

BRANCH="${1:-emergent-v3}"
MSG_SRC="${2:-}"                    # optional: file path, "-" for stdin, or empty
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

# Hash of THIS script *before* we pull. Used to detect whether `git reset`
# rewrites sync.sh underneath us (see the self-update guard after Step 1).
SELF_PATH="$(cd "$(dirname "$0")" && pwd)/$(basename "$0")"
SELF_HASH="$(sha256sum "$SELF_PATH" 2>/dev/null | awk '{print $1}')"

log "Branch target: ${YELLOW}${BRANCH}${NC}"
log "Repo dir:      ${YELLOW}$(pwd)${NC}"

# ── BUILD STAMP VERIFICATION ─────────────────────────────────────────────────
# Capture the OLD build stamp from README.md BEFORE the pull, so we can
# compare it against the NEW one after the pull. If they're identical AND
# this isn't the first deploy, that's a STRONG signal the latest changes
# never reached this branch on GitHub — the exact "Save-to-GitHub silently
# dropped my files" failure mode we hit on 2026-06-14 and 2026-06-15.
extract_build() {
  # $1 = key, e.g. BUILD_VERSION
  # Use ^ANCHOR so we only match lines that START with the key (the real
  # value lines), NOT the documentation line "Format: BUILD_VERSION=..."
  # which appears inside the marker comment.
  grep -E "^$1=" README.md 2>/dev/null | head -1 | cut -d= -f2- || echo "MISSING"
}
OLD_BUILD_VERSION="$(extract_build BUILD_VERSION)"
OLD_BUILD_TAG="$(extract_build BUILD_TAG)"
log "Pre-pull build stamp: ${YELLOW}${OLD_BUILD_VERSION}${NC}  (${OLD_BUILD_TAG})"

# ── Loud reminder: this script is BACKEND-ONLY ──────────────────────────────
echo -e "${YELLOW}┌──────────────────────────────────────────────────────────────┐${NC}"
echo -e "${YELLOW}│  NOTE: sync.sh deploys the BACKEND (API) only.                 │${NC}"
echo -e "${YELLOW}│  The FRONTEND is hosted on Cloudflare Pages and auto-builds     │${NC}"
echo -e "${YELLOW}│  from a GitHub push to '${BRANCH}'. If you changed UI, make sure  │${NC}"
echo -e "${YELLOW}│  the code was pushed (Emergent → Save to GitHub) so Cloudflare  │${NC}"
echo -e "${YELLOW}│  rebuilds it. Running this script does NOT update the frontend. │${NC}"
echo -e "${YELLOW}│  See deploy guide: ./DEPLOY.md                                  │${NC}"
echo -e "${YELLOW}└──────────────────────────────────────────────────────────────┘${NC}"

# ── If a commit message source was provided, capture it BEFORE git reset ─────
# (because reset would not lose the temp file, but we want to fail fast if the
#  file is missing / stdin is empty.)
MSG_FILE=""
if [ -n "$MSG_SRC" ]; then
  if [ "$MSG_SRC" = "-" ]; then
    MSG_FILE="$(mktemp -t sync-commit-msg.XXXXXX)"
    # Save the heredoc / piped input to a temp file
    cat > "$MSG_FILE"
    if [ ! -s "$MSG_FILE" ]; then
      rm -f "$MSG_FILE"; MSG_FILE=""
      warn "STDIN was empty — skipping commit message amend"
    else
      ok  "Captured commit message from STDIN ($(wc -l < "$MSG_FILE") lines)"
    fi
  elif [ -f "$MSG_SRC" ]; then
    MSG_FILE="$MSG_SRC"
    ok  "Using commit message file: $MSG_FILE"
  else
    fail "Commit message source '$MSG_SRC' is not '-' and not a readable file"
  fi
fi

# Cleanup temp file on exit
trap '[ -n "${MSG_FILE_TMP:-}" ] && rm -f "$MSG_FILE_TMP"' EXIT
[ "$MSG_SRC" = "-" ] && MSG_FILE_TMP="$MSG_FILE"

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

# ── 1b. Self-update guard ───────────────────────────────────────────────────
# The `git reset --hard` above may have rewritten THIS very script on disk.
# Bash reads scripts incrementally from the file, so if sync.sh changed length
# mid-run, every line AFTER this point could execute a corrupted old/new byte
# mix — the classic cause of phantom "Backend did not become healthy" failures
# even when the app is perfectly fine. If the script content changed, re-exec
# the fresh copy exactly once (guarded by SYNC_REEXECED to avoid a loop).
if [ "${SYNC_REEXECED:-0}" != "1" ]; then
  NEW_SELF_HASH="$(sha256sum "$SELF_PATH" 2>/dev/null | awk '{print $1}')"
  if [ -n "$NEW_SELF_HASH" ] && [ "$SELF_HASH" != "$NEW_SELF_HASH" ]; then
    ok "deploy/sync.sh was updated by the pull — re-executing the fresh script"
    exec env SYNC_REEXECED=1 bash "$SELF_PATH" "$@"
  fi
fi

# ── 1c. Post-pull build-stamp verification ───────────────────────────────────
# Read README.md's BUILD_VERSION/BUILD_TAG AFTER the pull. If you provided
# an expected value via env (EXPECT_BUILD=2026.06.15.001), we fail-fast if
# the remote doesn't match — proves the "Save-to-GitHub" actually pushed
# what you intended before we touch the running container.
NEW_BUILD_VERSION="$(extract_build BUILD_VERSION)"
NEW_BUILD_TAG="$(extract_build BUILD_TAG)"
NEW_BUILD_TS="$(extract_build BUILD_TIMESTAMP)"
log "Post-pull build stamp: ${YELLOW}${NEW_BUILD_VERSION}${NC}  (${NEW_BUILD_TAG})  @  ${NEW_BUILD_TS}"

if [ -n "${EXPECT_BUILD:-}" ]; then
  if [ "$NEW_BUILD_VERSION" = "$EXPECT_BUILD" ]; then
    ok "Remote BUILD_VERSION matches expected: ${EXPECT_BUILD}"
  else
    fail "Remote BUILD_VERSION is '${NEW_BUILD_VERSION}' but EXPECT_BUILD='${EXPECT_BUILD}'. The Save-to-GitHub push almost certainly DROPPED your changes. Re-push from Emergent and re-run."
  fi
fi

# Even without EXPECT_BUILD, warn if the version DIDN'T change after a pull
# that DID change HEAD — suggests a partial push (the README bump was lost
# even though other files landed). This is the early-warning signal we
# needed during the 2026-06-14/15 incidents.
if [ "$OLD_HEAD" != "$NEW_HEAD" ] && [ "$OLD_BUILD_VERSION" = "$NEW_BUILD_VERSION" ]; then
  warn "HEAD moved (${OLD_HEAD} → ${NEW_HEAD}) but BUILD_VERSION did NOT change."
  warn "  Possible causes:"
  warn "    1. The agent forgot to bump README BUILD_VERSION before Save-to-GitHub."
  warn "    2. The Save-to-GitHub partially dropped README.md from the commit."
  warn "  Inspect:  git log -1 --stat | head -30"
fi

# ── 2. Rebuild backend image (this is the step that was being skipped) ──────
log "Step 2/4 — Rebuilding backend image (this is what was missing in previous attempts)"
$COMPOSE build api
ok "Image rebuilt"

# ── 3. Recreate container with the new image ────────────────────────────────
log "Step 3/4 — Recreating container with the fresh image"
$COMPOSE up -d --force-recreate api
ok "Container recreated"

# Pause for app startup. This app runs MULTIPLE uvicorn workers and each one
# re-runs the full boot sequence (DB indexes + ACM + seeds + migrations), so a
# cold multi-worker boot can take 20-30s before any worker accepts connections.
sleep 8

# ── 4. Verify ────────────────────────────────────────────────────────────────
log "Step 4/4 — Verifying backend is healthy"
# Hit /api/health (then /api/health/ready as fallback) from INSIDE the
# container using Python urllib (always present in our Python-slim image).
# curl is NOT in the slim image, so we deliberately avoid it.
HEALTH_OK=0
PY_PROBE='import sys, urllib.request, urllib.error
URLS = [
    "http://localhost:8001/api/health",
    "http://localhost:8001/api/health/live",
    "http://localhost:8001/api/health/ready",
]
for u in URLS:
    try:
        body = urllib.request.urlopen(u, timeout=3).read().decode()
        sys.stdout.write(body)
        sys.exit(0)
    except urllib.error.HTTPError as e:
        # The server answered with an HTTP status (e.g. 404/500/503). That
        # still proves uvicorn is listening = the process is ALIVE, which is
        # all this liveness probe needs to confirm. Treat as success.
        sys.stdout.write("http_status=%s (server is listening)" % e.code)
        sys.exit(0)
    except Exception as e:
        # Connection refused / timeout / DNS = server NOT reachable. Try next.
        sys.stderr.write(u + " -> " + str(e) + "\n")
        continue
sys.exit(1)
'
for i in 1 2 3 4 5 6 7 8 9 10 11 12; do
  if $COMPOSE exec -T api python -c "$PY_PROBE" >/dev/null 2>&1; then
    ok "Backend responding on /api/health (inside-container Python probe)"
    HEALTH_OK=1
    break
  fi
  warn "Health check attempt $i/12 failed (workers may still be booting), retrying in 3s..."
  sleep 3
done

# Fallback: if uvicorn logged "Application startup complete" at least once in
# the last 200 lines, the app IS running, even if our HTTP probe couldn't
# reach it (network namespace quirks, etc.).
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

# ── 5. (Optional) Amend the latest commit with a clean message and push ─────
if [ -n "$MSG_FILE" ]; then
  log "Step 5/5 — Amending latest commit message and force-pushing to origin/${BRANCH}"

  # Snapshot the current HEAD in case we need to roll back
  PRE_AMEND_HEAD="$(git rev-parse HEAD)"

  # Configure a sensible identity if one isn't set on EC2 (idempotent)
  git config user.email >/dev/null 2>&1 || git config user.email "deploy@jelcos.ai"
  git config user.name  >/dev/null 2>&1 || git config user.name  "EC2 Deploy Bot"

  if git commit --amend -F "$MSG_FILE" --no-verify --allow-empty >/dev/null 2>&1; then
    AMENDED_HEAD="$(git rev-parse --short HEAD)"
    ok "Commit amended locally → ${AMENDED_HEAD}"

    if git push --force-with-lease="${BRANCH}:${PRE_AMEND_HEAD}" origin "HEAD:${BRANCH}" 2>/dev/null; then
      ok "Force-pushed amended commit to origin/${BRANCH}"
      echo "    First line of new message:"
      echo "    $(head -n1 "$MSG_FILE")"
    else
      warn "Push failed (someone else may have pushed since pull). Local amend kept."
      warn "Manual recovery: git push --force-with-lease origin ${BRANCH}"
    fi
  else
    warn "git commit --amend failed — message file may be malformed. Skipping push."
  fi
else
  log "Step 5/5 — No commit message provided (skipping amend & push)"
fi

echo
echo -e "${GREEN}════════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}✓ Backend deployment complete${NC}"
echo -e "  Now at commit: $(git rev-parse --short HEAD)"
echo -e "  Backend:       healthy"
echo -e "${YELLOW}  Frontend:      NOT deployed by this script.${NC}"
echo -e "${YELLOW}                 → Cloudflare Pages auto-builds from a push to '${BRANCH}'.${NC}"
echo -e "${YELLOW}                 → If your UI fix isn't live, push it (Save to GitHub)${NC}"
echo -e "${YELLOW}                   and wait ~1–2 min, then HARD-REFRESH the site.${NC}"
echo -e "${GREEN}════════════════════════════════════════════════════════════════${NC}"
