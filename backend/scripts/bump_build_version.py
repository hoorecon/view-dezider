#!/usr/bin/env python3
"""
bump_build_version.py — bump the BUILD_VERSION / BUILD_TIMESTAMP / BUILD_TAG
markers in README.md so each Save-to-GitHub push carries a fresh, verifiable
build stamp.

This is the human-readable shield against the "Save-to-GitHub silently
dropped my files" failure mode that bit us on 2026-06-14 / 06-15. After this
script runs:
    1. README.md has a new BUILD_VERSION ≥ the previous one.
    2. `deploy/sync.sh` will refuse to deploy if the remote BUILD_VERSION
       didn't actually advance (when invoked with EXPECT_BUILD=…).
    3. `/api/version` reflects whatever's in README on the running container.

USAGE
    # Auto-bump (most common — just run it before Save-to-GitHub):
    python3 backend/scripts/bump_build_version.py

    # Explicit version + tag (for releases):
    python3 backend/scripts/bump_build_version.py --version 2026.06.16.001 \
                                                  --tag v3.20-some-feature
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import sys
from pathlib import Path


def _project_root() -> Path:
    p = Path(__file__).resolve()
    for anc in [p.parent, p.parent.parent, p.parent.parent.parent]:
        if (anc / "README.md").exists():
            return anc
    sys.exit("Could not locate README.md walking up from this script")


def _next_version(current: str | None) -> str:
    today = dt.datetime.utcnow().strftime("%Y.%m.%d")
    if current and current.startswith(today):
        # bump the trailing sequence number
        try:
            seq = int(current.rsplit(".", 1)[-1]) + 1
        except ValueError:
            seq = 1
        return f"{today}.{seq:03d}"
    return f"{today}.001"


def _replace_or_add(text: str, key: str, value: str) -> str:
    pattern = re.compile(rf"^{key}=.*$", re.MULTILINE)
    if pattern.search(text):
        return pattern.sub(f"{key}={value}", text, count=1)
    # if the key is missing, add it before the closing `-->` of the marker
    return text.replace(
        "BUILD_TAG=",
        f"{key}={value}\nBUILD_TAG=",
        1,
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", help="explicit BUILD_VERSION (default: auto-bump)")
    ap.add_argument("--tag",     help="explicit BUILD_TAG (default: keep existing)")
    ap.add_argument("--dry-run", action="store_true", help="print what would change")
    args = ap.parse_args()

    root = _project_root()
    readme = root / "README.md"
    src = readme.read_text(encoding="utf-8")

    cur_version_m = re.search(r"^BUILD_VERSION=([A-Za-z0-9._+\-]+)$", src, re.MULTILINE)
    cur_version = cur_version_m.group(1) if cur_version_m else None
    new_version = args.version or _next_version(cur_version)

    cur_tag_m = re.search(r"^BUILD_TAG=([A-Za-z0-9._+\-]+)$", src, re.MULTILINE)
    cur_tag = cur_tag_m.group(1) if cur_tag_m else "untagged"
    new_tag = args.tag or cur_tag

    new_ts = dt.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    out = src
    out = _replace_or_add(out, "BUILD_VERSION", new_version)
    out = _replace_or_add(out, "BUILD_TIMESTAMP", new_ts)
    out = _replace_or_add(out, "BUILD_TAG", new_tag)

    print(f"BUILD_VERSION:  {cur_version}  →  {new_version}")
    print(f"BUILD_TAG:      {cur_tag}  →  {new_tag}")
    print(f"BUILD_TIMESTAMP: now → {new_ts}")

    if args.dry_run:
        print("\n(dry-run only — README.md NOT written.)")
        return

    readme.write_text(out, encoding="utf-8")
    print(f"\n✓ README.md updated. Next: Save to GitHub on emergent-v3, then on EC2:")
    print(f"    cd /opt/dezider && EXPECT_BUILD={new_version} ./deploy/sync.sh emergent-v3")


if __name__ == "__main__":
    main()
