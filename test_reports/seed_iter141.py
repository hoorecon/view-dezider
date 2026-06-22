"""Seed a fresh test user + a decision with deep_import_pending_rank=true.

Prints: EMAIL PASSWORD DECISION_ID for the playwright runner to consume.
"""
import os
import sys
import time
import uuid
import asyncio
import requests

sys.path.insert(0, "/app/backend")

BASE = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "http://localhost:8001").rstrip("/")
API = f"{BASE}/api"

EMAIL = f"iter141ui_{int(time.time())}@example.com"
PWD = "TestPass2026!"

r = requests.post(f"{API}/auth/register",
                  json={"email": EMAIL, "password": PWD, "name": "Iter141UI"},
                  timeout=30)
assert r.status_code in (200, 201), r.text
tok = r.json()["session_token"]
me = requests.get(f"{API}/auth/me",
                  headers={"Authorization": f"Bearer {tok}"}, timeout=10).json()
uid = me["user_id"]

# Seed decision via direct Mongo insert with pending flag = true
from core.database import db
DID = str(uuid.uuid4())
factors = [
    {"id": "f1", "name": "Performance", "rating": 9, "category": "primary",
     "expected_value": "fast", "operator": ">=", "order": 0},
    {"id": "f2", "name": "Price", "rating": 7, "category": "primary",
     "expected_value": "low", "operator": ">=", "order": 1},
]
options = [
    {"id": "oa", "name": "ScreenerCoA", "assessments": [
        {"factor_id": "f1", "percentage": 80},
        {"factor_id": "f2", "percentage": 70}]},
    {"id": "ob", "name": "ScreenerCoB", "assessments": [
        {"factor_id": "f1", "percentage": 60},
        {"factor_id": "f2", "percentage": 90}]},
]
asyncio.get_event_loop().run_until_complete(
    db.decisions.insert_one({
        "id": DID, "user_id": uid, "title": "TEST_ScreenerDeepImport",
        "context": "Pick a screener stock",
        "status": "draft",
        "current_step": 5,
        "factors": factors,
        "options": options,
        "deep_import_pending_rank": True,
    })
)
print(f"EMAIL={EMAIL}")
print(f"PWD={PWD}")
print(f"DID={DID}")
