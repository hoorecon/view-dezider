"""APScheduler weekly regression run.

Schedule: Sunday 02:00 UTC. Persists run + auto-prunes history > retention days.
Phase B.2 will add email-zipped result delivery once SMTP creds are in settings.

Multi-worker safety
-------------------
When uvicorn runs with --workers N (e.g. 4 in prod Dockerfile), each worker
process imports this module and previously each one started its own
AsyncIOScheduler -> the weekly job fired N times.

We now gate startup behind an exclusive ``fcntl`` advisory lock on a small
file (default ``/tmp/dezider_regression_scheduler.lock``). Only the first
worker to grab the lock starts the scheduler; the others log a friendly
"skip" message and exit ``start_scheduler()`` immediately. The OS releases
the lock automatically when the leader process dies, so another worker can
take over on next boot without manual intervention.

Override flags
--------------
* ``REGRESSION_SCHEDULER_DISABLED=true``  -> never start (useful for CI / tests)
* ``REGRESSION_SCHEDULER_LOCK=/path/to/file`` -> custom lock path
"""
from __future__ import annotations

import logging
import os

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from core.regression import runner

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None
_lock_fd = None  # kept open for lifetime of leader process so the lock persists


def _try_acquire_singleton_lock() -> bool:
    """Return True iff this process is the elected scheduler leader.

    Uses a non-blocking ``fcntl`` exclusive lock on a sentinel file. The file
    descriptor is intentionally kept open in module-global state so the kernel
    keeps the lock for the lifetime of the process; when the process exits
    (graceful or crash) the OS releases it automatically and any remaining
    worker can pick it up on the next boot.
    """
    global _lock_fd
    try:
        import fcntl  # POSIX-only; Docker container is Linux so safe
    except ImportError:  # pragma: no cover - non-POSIX dev machines
        logger.warning("fcntl unavailable; falling back to unguarded scheduler start")
        return True

    lock_path = os.environ.get(
        "REGRESSION_SCHEDULER_LOCK", "/tmp/dezider_regression_scheduler.lock"
    )
    try:
        _lock_fd = open(lock_path, "w")
        fcntl.flock(_lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        _lock_fd.write(str(os.getpid()))
        _lock_fd.flush()
        return True
    except (BlockingIOError, OSError) as e:
        logger.info(
            f"Regression scheduler lock already held by another worker "
            f"(pid={os.getpid()}, reason={e}); skipping local scheduler start"
        )
        if _lock_fd is not None:
            try:
                _lock_fd.close()
            except Exception:
                pass
            _lock_fd = None
        return False


async def _weekly_job() -> None:
    logger.info("Weekly regression run starting (functional + smoke, api only)")
    try:
        result = await runner.run(level="both", kind="api", triggered_by="weekly")
        logger.info(
            f"Weekly regression done: status={result.overall_status} "
            f"totals={result.totals} duration={result.duration_ms}ms"
        )
        # TODO Phase B.2: zip + email result to admin list using settings hub SMTP creds.
    except Exception as e:
        logger.error(f"Weekly regression run failed: {e}", exc_info=True)


def start_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        return

    if os.environ.get("REGRESSION_SCHEDULER_DISABLED", "").lower() in ("1", "true", "yes"):
        logger.info("Regression scheduler disabled via REGRESSION_SCHEDULER_DISABLED env")
        return

    if not _try_acquire_singleton_lock():
        # Another worker holds the lock; this worker stays silent.
        return

    _scheduler = AsyncIOScheduler(timezone="UTC")
    _scheduler.add_job(
        _weekly_job,
        CronTrigger(day_of_week="sun", hour=2, minute=0),
        id="weekly_regression",
        replace_existing=True,
    )
    _scheduler.start()
    logger.info(
        f"Regression scheduler started (Sun 02:00 UTC) leader_pid={os.getpid()}"
    )


def stop_scheduler() -> None:
    global _scheduler, _lock_fd
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
    if _lock_fd is not None:
        try:
            _lock_fd.close()
        except Exception:
            pass
        _lock_fd = None
