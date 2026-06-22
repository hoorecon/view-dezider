#!/usr/bin/env python3
"""One-off sweep: replace bare `router.back()` with `safeBack(router)` and
ensure `safeBack` is imported (with the correct relative path per file)."""
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # frontend/
TARGET_MOD = os.path.join(ROOT, "src", "utils", "navigation")
SCAN_DIRS = [os.path.join(ROOT, "app"), os.path.join(ROOT, "src")]
SKIP = {os.path.join(ROOT, "src", "utils", "navigation.ts")}

changed = []
for base in SCAN_DIRS:
    for dirpath, _, files in os.walk(base):
        for fn in files:
            if not fn.endswith((".tsx", ".ts")):
                continue
            path = os.path.join(dirpath, fn)
            if path in SKIP:
                continue
            with open(path, "r", encoding="utf-8") as f:
                src = f.read()
            if "router.back()" not in src:
                continue
            new = src.replace("router.back()", "safeBack(router)")
            # Ensure import present.
            if "safeBack" not in src or "from" not in src:
                pass
            if not re.search(r"import\s*\{[^}]*\bsafeBack\b[^}]*\}\s*from", new):
                rel = os.path.relpath(TARGET_MOD, os.path.dirname(path)).replace(os.sep, "/")
                if not rel.startswith("."):
                    rel = "./" + rel
                imp = f"import {{ safeBack }} from '{rel}';\n"
                # Insert after the last top-level import line in the first 80 lines.
                lines = new.split("\n")
                last_imp = -1
                for i, ln in enumerate(lines[:80]):
                    if ln.startswith("import ") or (ln.startswith("} from ") ):
                        last_imp = i
                if last_imp == -1:
                    new = imp + new
                else:
                    lines.insert(last_imp + 1, imp.rstrip("\n"))
                    new = "\n".join(lines)
            if new != src:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(new)
                changed.append(os.path.relpath(path, ROOT))

print(f"Files changed: {len(changed)}")
for c in changed:
    print(c)
