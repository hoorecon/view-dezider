"""Pydantic models + dataclasses for the regression suite."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict, List, Optional

# Type alias: a test case body is an async callable receiving a TestContext
# and returning a dict {passed: bool, message: str, ...}
TestCallable = Callable[["TestContext"], Awaitable[Dict[str, Any]]]


@dataclass
class TestCase:
    id: str
    name: str
    level: str  # "smoke" | "functional"
    body: TestCallable
    description: str = ""

    def to_meta(self) -> Dict[str, Any]:
        return {"id": self.id, "name": self.name, "level": self.level, "description": self.description}


@dataclass
class Suite:
    id: str
    feature: str          # human group: "Auth", "Public Pulse", "Solution Matrix"
    module: str           # internal module key matching admin nav: "auth", "pp_org_portal"
    kind: str             # "api" | "ui"
    title: str
    description: str
    owner_file: str       # source path of the registering file (for traceability)
    cases: List[TestCase] = field(default_factory=list)
    ui_spec_path: Optional[str] = None  # for kind=="ui"

    def to_meta(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "feature": self.feature,
            "module": self.module,
            "kind": self.kind,
            "title": self.title,
            "description": self.description,
            "owner_file": self.owner_file,
            "case_count": len(self.cases),
            "smoke_count": sum(1 for c in self.cases if c.level == "smoke"),
            "functional_count": sum(1 for c in self.cases if c.level == "functional"),
            "ui_spec_path": self.ui_spec_path,
            "cases": [c.to_meta() for c in self.cases],
        }


@dataclass
class CaseResult:
    case_id: str
    name: str
    level: str
    status: str           # "passed" | "failed" | "skipped" | "manual_pending"
    message: str = ""
    latency_ms: int = 0
    traceback: Optional[str] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "case_id": self.case_id,
            "name": self.name,
            "level": self.level,
            "status": self.status,
            "message": self.message,
            "latency_ms": self.latency_ms,
            "traceback": self.traceback,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }


@dataclass
class SuiteResult:
    suite_id: str
    feature: str
    module: str
    kind: str
    title: str
    cases: List[CaseResult] = field(default_factory=list)

    @property
    def passed(self) -> int:
        return sum(1 for c in self.cases if c.status == "passed")

    @property
    def failed(self) -> int:
        return sum(1 for c in self.cases if c.status == "failed")

    @property
    def skipped(self) -> int:
        return sum(1 for c in self.cases if c.status == "skipped")

    @property
    def manual(self) -> int:
        return sum(1 for c in self.cases if c.status == "manual_pending")

    @property
    def status(self) -> str:
        if self.failed:
            return "failed"
        if self.passed == 0 and (self.skipped + self.manual) > 0:
            return "skipped"
        return "passed"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "suite_id": self.suite_id,
            "feature": self.feature,
            "module": self.module,
            "kind": self.kind,
            "title": self.title,
            "status": self.status,
            "passed": self.passed,
            "failed": self.failed,
            "skipped": self.skipped,
            "manual_pending": self.manual,
            "cases": [c.to_dict() for c in self.cases],
        }


@dataclass
class RunResult:
    run_id: str
    triggered_at: str
    triggered_by: str         # "manual" | "weekly"
    triggered_by_user: Optional[str] = None
    level_filter: str = "smoke"  # "smoke" | "functional" | "both"
    kind_filter: str = "api"     # "api" | "ui" | "both"
    suite_ids: List[str] = field(default_factory=list)  # empty = all
    suites: List[SuiteResult] = field(default_factory=list)
    duration_ms: int = 0
    finished_at: Optional[str] = None

    @property
    def overall_status(self) -> str:
        if not self.suites:
            return "skipped"
        if any(s.status == "failed" for s in self.suites):
            return "failed"
        if all(s.status == "passed" for s in self.suites):
            return "passed"
        return "partial"

    @property
    def totals(self) -> Dict[str, int]:
        return {
            "passed": sum(s.passed for s in self.suites),
            "failed": sum(s.failed for s in self.suites),
            "skipped": sum(s.skipped for s in self.suites),
            "manual_pending": sum(s.manual for s in self.suites),
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "triggered_at": self.triggered_at,
            "triggered_by": self.triggered_by,
            "triggered_by_user": self.triggered_by_user,
            "level_filter": self.level_filter,
            "kind_filter": self.kind_filter,
            "suite_ids": self.suite_ids,
            "overall_status": self.overall_status,
            "totals": self.totals,
            "duration_ms": self.duration_ms,
            "finished_at": self.finished_at,
            "suites": [s.to_dict() for s in self.suites],
        }


@dataclass
class TestContext:
    """Passed to every TestCase. Provides an httpx async client, base URL,
    pre-fetched admin token, helper assert, and a scratchpad dict to share
    state between cases inside the same suite (rarely needed)."""
    http: Any                 # httpx.AsyncClient
    base_url: str
    admin_token: Optional[str]
    user_token: Optional[str]
    scratch: Dict[str, Any] = field(default_factory=dict)

    def auth_headers(self, admin: bool = False) -> Dict[str, str]:
        tok = self.admin_token if admin else self.user_token
        return {"Authorization": f"Bearer {tok}"} if tok else {}
