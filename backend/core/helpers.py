"""Shared helper functions used across multiple route modules."""
import uuid
import logging
import httpx
from datetime import datetime, timezone
from .database import db

logger = logging.getLogger(__name__)


def generate_user_id():
    return f"user_{uuid.uuid4().hex[:12]}"


async def send_expo_push(push_tokens: list, title: str, body: str, data: dict = None):
    """Send push notification via Expo Push API"""
    if not push_tokens:
        return
    messages = []
    for token in push_tokens:
        if not token or not token.startswith('ExponentPushToken'):
            continue
        messages.append({
            "to": token,
            "sound": "default",
            "title": title,
            "body": body,
            "data": data or {},
        })
    if not messages:
        return
    try:
        async with httpx.AsyncClient() as client:
            await client.post(
                "https://exp.host/--/api/v2/push/send",
                json=messages,
                headers={"Content-Type": "application/json"},
                timeout=10
            )
    except Exception as e:
        logger.error(f"Push notification error: {e}")


async def create_notification(user_id: str, notif_type: str, title: str, message: str, data: dict = None):
    """Helper function to create a notification and send push"""
    notif = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "type": notif_type,
        "title": title,
        "message": message,
        "data": data or {},
        "read": False,
        "created_at": datetime.now(timezone.utc),
    }
    await db.notifications.insert_one(notif)
    user_doc = await db.users.find_one({"user_id": user_id}, {"_id": 0})
    if user_doc and user_doc.get("push_token"):
        await send_expo_push([user_doc["push_token"]], title, message, data)
    return notif
