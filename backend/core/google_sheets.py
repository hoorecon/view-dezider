"""Google Sheets integration — OAuth + create/read assessment spreadsheets.

Powers the "Import Filled (Google Sheet)" option in My Dezider & Pros & Cons.
Flow (model a): the user connects their own Google account once; the app then
CREATES an assessment Google Sheet *in the user's own Drive* (so they already
have edit access), the user fills it in, and the app READS it back to import.

No API key is needed — this reuses the app's existing Google OAuth client
(GOOGLE_CLIENT_ID/SECRET). Tokens (incl. refresh token) are stored per user in
db.google_sheet_tokens. All blocking google-api calls run in a worker thread.
"""
from __future__ import annotations

import asyncio
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import httpx
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

from core.database import db

log = logging.getLogger("google_sheets")

# Dedicated Sheets OAuth client (falls back to the app's main Google client).
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_SHEETS_CLIENT_ID") or os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_SHEETS_CLIENT_SECRET") or os.getenv("GOOGLE_CLIENT_SECRET", "")
TOKEN_URI = "https://oauth2.googleapis.com/token"
AUTH_URI = "https://accounts.google.com/o/oauth2/auth"

# Must EXACTLY match the redirect URI registered in the Google Cloud Console.
REDIRECT_URI = os.getenv(
    "GOOGLE_SHEETS_REDIRECT_URI",
    "https://dashboard-rewire.preview.emergentagent.com/api/oauth/sheets/callback",
)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
]
REQUIRED_SCOPE = "https://www.googleapis.com/auth/spreadsheets"


def is_configured() -> bool:
    return bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET)


def _client_config() -> dict:
    return {
        "web": {
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "auth_uri": AUTH_URI,
            "token_uri": TOKEN_URI,
        }
    }


# ─────────────────────────────────────────────────────────────
# OAuth
# ─────────────────────────────────────────────────────────────
def build_auth_url(state: str, redirect_uri: str) -> str:
    flow = Flow.from_client_config(_client_config(), scopes=SCOPES, redirect_uri=redirect_uri)
    url, _ = flow.authorization_url(access_type="offline", prompt="consent", include_granted_scopes="true", state=state)
    return url


def _exchange_code(code: str, redirect_uri: str) -> Credentials:
    flow = Flow.from_client_config(_client_config(), scopes=SCOPES, redirect_uri=redirect_uri)
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        flow.fetch_token(code=code)
    return flow.credentials


async def exchange_and_store(code: str, user_id: str, redirect_uri: str) -> str:
    """Exchange the auth code, fetch the Google account email, persist tokens.
    Returns the connected Google email."""
    creds = await asyncio.to_thread(_exchange_code, code, redirect_uri)
    granted = set(creds.scopes or [])
    if REQUIRED_SCOPE not in granted:
        raise ValueError("The Google Sheets permission was not granted. Please retry and allow Sheets access.")

    email = ""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(
                "https://www.googleapis.com/oauth2/v2/userinfo",
                headers={"Authorization": f"Bearer {creds.token}"},
            )
            if r.status_code == 200:
                email = r.json().get("email", "")
    except Exception:
        pass

    expires_at = creds.expiry
    if expires_at and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    await db.google_sheet_tokens.update_one(
        {"user_id": user_id},
        {"$set": {
            "user_id": user_id,
            "access_token": creds.token,
            "refresh_token": creds.refresh_token,
            "token_uri": creds.token_uri,
            "client_id": creds.client_id or GOOGLE_CLIENT_ID,
            "client_secret": creds.client_secret or GOOGLE_CLIENT_SECRET,
            "scopes": list(creds.scopes or SCOPES),
            "email": email,
            "expires_at": expires_at,
            "updated_at": datetime.now(timezone.utc),
        }},
        upsert=True,
    )
    return email


async def get_status(user_id: str) -> dict:
    tok = await db.google_sheet_tokens.find_one({"user_id": user_id}, {"_id": 0, "email": 1, "refresh_token": 1})
    if not tok:
        return {"connected": False}
    return {"connected": True, "email": tok.get("email") or "", "can_refresh": bool(tok.get("refresh_token"))}


async def disconnect(user_id: str) -> None:
    await db.google_sheet_tokens.delete_one({"user_id": user_id})


async def _get_creds(user_id: str) -> Credentials:
    tok = await db.google_sheet_tokens.find_one({"user_id": user_id}, {"_id": 0})
    if not tok:
        raise PermissionError("Google account not connected. Connect Google to use Sheets import.")
    creds = Credentials(
        token=tok.get("access_token"),
        refresh_token=tok.get("refresh_token"),
        token_uri=tok.get("token_uri", TOKEN_URI),
        client_id=tok.get("client_id", GOOGLE_CLIENT_ID),
        client_secret=tok.get("client_secret", GOOGLE_CLIENT_SECRET),
        scopes=tok.get("scopes", SCOPES),
    )
    expires = tok.get("expires_at")
    if isinstance(expires, str):
        expires = datetime.fromisoformat(expires)
    if expires and expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    needs_refresh = (not creds.token) or (expires is not None and datetime.now(timezone.utc) >= (expires - timedelta(seconds=60)))
    if needs_refresh:
        if not creds.refresh_token:
            raise PermissionError("Google session expired. Please reconnect your Google account.")
        await asyncio.to_thread(creds.refresh, GoogleRequest())
        new_exp = creds.expiry
        if new_exp and new_exp.tzinfo is None:
            new_exp = new_exp.replace(tzinfo=timezone.utc)
        await db.google_sheet_tokens.update_one(
            {"user_id": user_id},
            {"$set": {"access_token": creds.token, "expires_at": new_exp, "updated_at": datetime.now(timezone.utc)}},
        )
    return creds


# ─────────────────────────────────────────────────────────────
# Spreadsheet create / read
# ─────────────────────────────────────────────────────────────
def _create_sheet_sync(creds: Credentials, title: str, matrix: List[List[Any]]) -> dict:
    service = build("sheets", "v4", credentials=creds, cache_discovery=False)
    created = service.spreadsheets().create(
        body={"properties": {"title": title}, "sheets": [{"properties": {"title": "Assessment"}}]},
        fields="spreadsheetId,spreadsheetUrl,sheets.properties.sheetId",
    ).execute()
    sid = created["spreadsheetId"]
    url = created.get("spreadsheetUrl") or f"https://docs.google.com/spreadsheets/d/{sid}/edit"
    sheet_id = created["sheets"][0]["properties"]["sheetId"]

    service.spreadsheets().values().update(
        spreadsheetId=sid, range="Assessment!A1",
        valueInputOption="RAW", body={"values": matrix},
    ).execute()

    ncols = max((len(r) for r in matrix), default=6)
    requests = [
        {"updateDimensionProperties": {
            "range": {"sheetId": sheet_id, "dimension": "ROWS", "startIndex": 0, "endIndex": 1},
            "properties": {"hiddenByUser": True}, "fields": "hiddenByUser"}},
        {"repeatCell": {
            "range": {"sheetId": sheet_id, "startRowIndex": 1, "endRowIndex": 2},
            "cell": {"userEnteredFormat": {"textFormat": {"bold": True},
                     "backgroundColor": {"red": 0.12, "green": 0.16, "blue": 0.27},
                     "horizontalAlignment": "CENTER"}},
            "fields": "userEnteredFormat(textFormat,backgroundColor,horizontalAlignment)"}},
        {"repeatCell": {
            "range": {"sheetId": sheet_id, "startRowIndex": 1, "endRowIndex": 2},
            "cell": {"userEnteredFormat": {"textFormat": {"foregroundColor": {"red": 1, "green": 1, "blue": 1}, "bold": True}}},
            "fields": "userEnteredFormat.textFormat.foregroundColor"}},
        {"updateSheetProperties": {
            "properties": {"sheetId": sheet_id, "gridProperties": {"frozenRowCount": 2, "frozenColumnCount": 3}},
            "fields": "gridProperties.frozenRowCount,gridProperties.frozenColumnCount"}},
        {"autoResizeDimensions": {
            "dimensions": {"sheetId": sheet_id, "dimension": "COLUMNS", "startIndex": 0, "endIndex": ncols}}},
    ]
    service.spreadsheets().batchUpdate(spreadsheetId=sid, body={"requests": requests}).execute()
    return {"spreadsheet_id": sid, "url": url}


async def create_assessment_sheet(user_id: str, title: str, matrix: List[List[Any]]) -> dict:
    creds = await _get_creds(user_id)
    safe_title = (title or "Assessment").strip()[:90] or "Assessment"
    return await asyncio.to_thread(_create_sheet_sync, creds, f"{safe_title} — Assessment", matrix)


def _read_sheet_sync(creds: Credentials, spreadsheet_id: str) -> List[List[Any]]:
    service = build("sheets", "v4", credentials=creds, cache_discovery=False)
    res = service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id, range="Assessment", valueRenderOption="UNFORMATTED_VALUE",
    ).execute()
    return res.get("values", [])


async def read_assessment_sheet(user_id: str, spreadsheet_id: str) -> List[List[Any]]:
    creds = await _get_creds(user_id)
    return await asyncio.to_thread(_read_sheet_sync, creds, spreadsheet_id)


# ─────────────────────────────────────────────────────────────
# OAuth state (CSRF) — short-lived
# ─────────────────────────────────────────────────────────────
async def create_state(user_id: str, return_to: str, redirect_uri: str) -> str:
    state = uuid.uuid4().hex
    await db.google_oauth_state.update_one(
        {"state": state},
        {"$set": {"state": state, "user_id": user_id, "return_to": return_to,
                  "redirect_uri": redirect_uri, "created_at": datetime.now(timezone.utc)}},
        upsert=True,
    )
    return state


async def consume_state(state: str) -> Optional[dict]:
    doc = await db.google_oauth_state.find_one({"state": state}, {"_id": 0})
    if not doc:
        return None
    await db.google_oauth_state.delete_one({"state": state})
    created = doc.get("created_at")
    if isinstance(created, datetime):
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) - created > timedelta(minutes=10):
            return None
    return doc
