"""MongoDB connection — pooled for ~10k concurrent users.

Pool sizing rationale:
- maxPoolSize=200 supports a high-concurrency burst per FastAPI worker.
- minPoolSize=10 keeps a warm pool to avoid cold-start latency.
- maxIdleTimeMS=60000 reaps stale connections after 60s.
- waitQueueTimeoutMS=5000 fast-fails clients waiting on a saturated pool.
- serverSelectionTimeoutMS=5000 fast-fails when MongoDB is unreachable.
- retryWrites + retryReads are MongoDB defaults — re-stated for clarity.
"""

import os
import logging
from pathlib import Path

from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).parent.parent
load_dotenv(ROOT_DIR / ".env")

mongo_url = os.environ["MONGO_URL"]

client = AsyncIOMotorClient(
    mongo_url,
    maxPoolSize=int(os.environ.get("MONGO_MAX_POOL_SIZE", "200")),
    minPoolSize=int(os.environ.get("MONGO_MIN_POOL_SIZE", "10")),
    maxIdleTimeMS=int(os.environ.get("MONGO_MAX_IDLE_TIME_MS", "60000")),
    waitQueueTimeoutMS=int(os.environ.get("MONGO_WAIT_QUEUE_TIMEOUT_MS", "5000")),
    serverSelectionTimeoutMS=int(os.environ.get("MONGO_SERVER_SELECTION_TIMEOUT_MS", "5000")),
    retryWrites=True,
    retryReads=True,
)

db = client[os.environ["DB_NAME"]]


async def ensure_indexes() -> dict:
    """Create all hot-path indexes. Called once at app startup."""
    from .db_indices import apply_indexes
    result = await apply_indexes(db)
    logger.info(
        f"DB indexes applied — created/verified: {result['created']}, "
        f"skipped: {result['skipped']}, errors: {len(result['errors'])}"
    )
    if result["errors"]:
        # Most errors are benign "index exists with different options" — log first 5
        for err in result["errors"][:5]:
            logger.debug(f"Index spec issue: {err}")
    return result
