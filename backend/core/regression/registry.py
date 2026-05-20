"""Central registry for regression test suites."""
from __future__ import annotations

import logging
from typing import Dict, List, Optional

from core.regression.models import Suite, TestCase

logger = logging.getLogger(__name__)

_SUITES: Dict[str, Suite] = {}


def register_suite(suite: Suite) -> Suite:
    """Register a suite. Idempotent — re-registering replaces the previous one
    (useful during dev/hot-reload). Suite ids must be globally unique."""
    if suite.id in _SUITES:
        logger.debug(f"Replacing regression suite {suite.id}")
    _SUITES[suite.id] = suite
    return suite


def register_case(suite_id: str, case: TestCase) -> None:
    if suite_id not in _SUITES:
        raise KeyError(f"Suite {suite_id} not registered yet")
    _SUITES[suite_id].cases.append(case)


def get(suite_id: str) -> Optional[Suite]:
    return _SUITES.get(suite_id)


def list_suites() -> List[Suite]:
    return sorted(_SUITES.values(), key=lambda s: (s.feature, s.title))


def list_features() -> List[str]:
    return sorted({s.feature for s in _SUITES.values()})


def reset() -> None:
    """Used by tests only."""
    _SUITES.clear()
