"""
Regression Suite — feature-mapped API + UI regression tests for the platform.

Public API:
    from core.regression import registry, runner, seed_suites
    registry.list_suites() -> [Suite, ...]
    await runner.run(level, kind, suite_ids) -> RunResult

New features should register their suites in `seed_suites.py` (or a sibling
module) using `registry.register_suite(...)`. The registry is the single
source of truth; UI + scheduler discover suites at runtime.
"""

from core.regression import registry, runner, seed_suites  # noqa: F401
