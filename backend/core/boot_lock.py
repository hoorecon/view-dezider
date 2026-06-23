"""
Single-flight advisory locks for multi-worker (uvicorn --workers N) safety.

PROBLEM this solves: in production the API runs several uvicorn workers in one
container. The FastAPI @app.on_event("startup") handler runs heavy, BLOCKING
boot work — index creation + data seeds + migrations. When all N workers run it
simultaneously (e.g. right after a SEED_VERSION bump) they race on
drop/create-index operations and collectively overload Mongo, pushing startup
past the deployment health-check window → the container is killed before
"Application startup complete".

FIX: gate the heavy boot work behind a per-host fcntl advisory lock. Exactly ONE
worker (the lock owner) performs the seeds/indexes; the other workers skip them
and start serving (and answering health checks) immediately. Because indexes and
seeds are global in Mongo, the non-owner workers benefit as soon as the owner
finishes — and seeds are version-guarded so subsequent boots are no-ops anyway.

The lock fd is kept open for the process lifetime (released automatically on
exit), mirroring the existing pattern in core/notification_engine.py.
"""
from __future__ import annotations

import os
import logging

logger = logging.getLogger("boot_lock")

_boot_lock_fd = None
_named_fds: dict = {}


def try_acquire_boot_seed_lock() -> bool:
    """Return True for exactly one worker per host (the one that should run the
    heavy boot seeds/index creation). Other workers get False and must skip."""
    global _boot_lock_fd
    try:
        import fcntl
    except ImportError:  # non-POSIX / single worker — assume owner
        return True
    lock_path = os.environ.get("BOOT_SEED_LOCK", "/tmp/dezider_boot_seed.lock")
    try:
        _boot_lock_fd = open(lock_path, "w")
        fcntl.flock(_boot_lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        _boot_lock_fd.write(str(os.getpid()))
        _boot_lock_fd.flush()
        return True
    except (BlockingIOError, OSError):
        if _boot_lock_fd is not None:
            try:
                _boot_lock_fd.close()
            except Exception:
                pass
            _boot_lock_fd = None
        return False


def try_acquire_named_lock(name: str) -> bool:
    """Generic per-host single-flight lock by name. Use to ensure a background
    scheduler runs in only ONE worker (e.g. weekly payout sweep) so it doesn't
    fire N times. Returns True for the first worker, False for the rest."""
    try:
        import fcntl
    except ImportError:
        return True
    if name in _named_fds:
        return True
    lock_path = os.environ.get(f"{name.upper()}_LOCK", f"/tmp/dezider_{name}.lock")
    try:
        fd = open(lock_path, "w")
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fd.write(str(os.getpid()))
        fd.flush()
        _named_fds[name] = fd
        return True
    except (BlockingIOError, OSError):
        return False
