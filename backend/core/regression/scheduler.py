"""APScheduler weekly regression run.

Schedule: Sunday 02:00 UTC. Persists run + auto-prunes history > retention days.
Phase B.2 will add email-zipped result delivery once SMTP creds are in settings.
"""
from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from core.regression import runner

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


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
    _scheduler = AsyncIOScheduler(timezone="UTC")
    _scheduler.add_job(
        _weekly_job,
        CronTrigger(day_of_week="sun", hour=2, minute=0),
        id="weekly_regression",
        replace_existing=True,
    )
    _scheduler.start()
    logger.info("Regression scheduler started (Sun 02:00 UTC)")


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
