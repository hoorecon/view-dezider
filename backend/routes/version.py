"""
/api/version — public endpoint that surfaces the build stamp baked into
README.md. Used by deploy/sync.sh, ops dashboards, and end-users to verify
the running container actually has the code they expect AFTER a deploy.

Pairs with the BUILD_VERSION / BUILD_TAG / BUILD_TIMESTAMP markers in the
top-level README.md (HTML-comment block). Returns "unknown" if the markers
aren't present so the endpoint never breaks on first-time setups.

USAGE
-----
    curl -s https://api.jelcos.ai/api/version | jq
    # {
    #   "build_version": "2026.06.15.001",
    #   "build_tag": "v3.19.1-acm-editor+catalog-sweep+migration-fix",
    #   "build_timestamp": "2026-06-15T19:50:00Z",
    #   "git_sha": "abc1234"
    # }
"""
import os
import re
from pathlib import Path
from fastapi import APIRouter

router = APIRouter(prefix="/version", tags=["meta"])


def _project_root() -> Path:
    """Walk up from this file until we find README.md (works in both the
    docker container at /app and the EC2 host at /opt/dezider/backend)."""
    p = Path(__file__).resolve()
    for ancestor in [p.parent, p.parent.parent, p.parent.parent.parent]:
        if (ancestor / "README.md").exists():
            return ancestor
    return Path("/app")


_BUILD_KEY_RE = re.compile(r"(BUILD_VERSION|BUILD_TAG|BUILD_TIMESTAMP)=([A-Za-z0-9._+\-:T]+)")
_GIT_HEAD_RE = re.compile(r"^[0-9a-f]{40}$")


def _read_build_stamp() -> dict:
    """Parse the BUILD_* markers from README.md. Returns 'unknown' for any
    missing key so consumers always get a stable JSON shape."""
    out = {"build_version": "unknown", "build_tag": "unknown",
           "build_timestamp": "unknown", "git_sha": "unknown"}
    readme = _project_root() / "README.md"
    try:
        text = readme.read_text(encoding="utf-8", errors="replace")
        for m in _BUILD_KEY_RE.finditer(text):
            key, val = m.group(1).lower(), m.group(2)
            out[key.lower()] = val
    except OSError:
        pass

    # Best-effort git sha (works in dev container; on prod docker the .git
    # dir typically isn't copied — that's OK, we fall back to "unknown").
    git_head = _project_root() / ".git" / "HEAD"
    try:
        head = git_head.read_text().strip()
        if head.startswith("ref:"):
            ref = head.split(" ", 1)[1].strip()
            sha = (_project_root() / ".git" / ref).read_text().strip()
            if _GIT_HEAD_RE.match(sha):
                out["git_sha"] = sha[:7]
        elif _GIT_HEAD_RE.match(head):
            out["git_sha"] = head[:7]
    except OSError:
        pass

    # Override with explicit env vars if the deploy pipeline supplies them.
    out["build_version"] = os.getenv("BUILD_VERSION", out["build_version"])
    out["build_tag"] = os.getenv("BUILD_TAG", out["build_tag"])
    out["git_sha"] = os.getenv("GIT_SHA", out["git_sha"])
    return out


@router.get("")
async def get_version():
    """Public — no auth required. Always returns 200 with a stable shape."""
    return _read_build_stamp()
