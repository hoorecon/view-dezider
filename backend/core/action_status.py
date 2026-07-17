"""Canonical Action-Item status vocabulary shared across modules.

One source of truth for the 8 statuses used by Action Center, CTT, Lifestyle
and the Action-Plan steps of Pros & Cons / My Dezider / Solution Finder.
Legacy values ('open', 'in_progress', 'completed') are transparently aliased so
older documents keep rendering correctly.
"""

CANONICAL_STATUSES = [
    "pending", "wip_25", "wip_50", "wip_75",
    "done", "deferred", "blocked", "cancelled",
]

# Only the progress-bearing states carry a numeric % (the rest are terminal/other).
STATUS_PROGRESS = {
    "pending": 0, "wip_25": 25, "wip_50": 50, "wip_75": 75, "done": 100,
}

STATUS_LABELS = {
    "pending": "Pending",
    "wip_25": "WIP 25%",
    "wip_50": "WIP 50%",
    "wip_75": "WIP 75%",
    "done": "Done",
    "deferred": "Deferred",
    "blocked": "Blocked",
    "cancelled": "Cancelled",
}

_ALIASES = {
    "open": "pending",
    "in_progress": "wip_50",
    "in progress": "wip_50",
    "completed": "done",
    "complete": "done",
    "": "pending",
}

_VALID = set(CANONICAL_STATUSES)


def normalize_status(s) -> str:
    """Coerce any incoming status string to a canonical value (default pending)."""
    if s is None:
        return "pending"
    v = str(s).strip().lower()
    if v in _VALID:
        return v
    return _ALIASES.get(v, "pending")


def status_label(s) -> str:
    return STATUS_LABELS.get(normalize_status(s), "Pending")


def progress_for(s) -> int:
    return STATUS_PROGRESS.get(normalize_status(s), 0)
