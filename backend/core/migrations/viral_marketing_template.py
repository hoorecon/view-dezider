"""Boot-time idempotent seed for the "Viral Marketing Campaign Planner"
decision template.

Wraps `scripts/seed_viral_marketing_template.py` so production containers
always have the template available (no manual `docker exec` needed after
deploy). Safe to call on every boot — the seeder upserts by fixed id.
"""
import logging

logger = logging.getLogger(__name__)


async def migrate_viral_marketing_template() -> None:
    try:
        # Import lazily so app boot never fails if the module has an issue.
        import sys, os
        scripts_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "scripts")
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)
        from seed_viral_marketing_template import main as seed_main  # type: ignore
        await seed_main()
    except Exception as e:  # pragma: no cover — never break boot on seed error
        logger.error(f"Viral-marketing template seed failed: {e}")
