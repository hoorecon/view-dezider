"""
Google Calendar Integration Router
- OAuth2 flow for connecting user's Google Calendar
- CRUD for calendar events (synced from CTT action items)
"""
import os
import uuid
import requests as http_requests
from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import APIRouter, Request, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from dotenv import load_dotenv

load_dotenv()

from core.database import db
from core.auth import get_current_user

router = APIRouter()

# Accept both naming conventions — production EC2 uses GOOGLE_OAUTH_CLIENT_ID /
# GOOGLE_OAUTH_CLIENT_SECRET while the dev pod uses GOOGLE_CLIENT_ID / _SECRET.
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID") or os.getenv("GOOGLE_OAUTH_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET") or os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", "")
SCOPES = ["https://www.googleapis.com/auth/calendar"]

# Determine redirect URI dynamically
BACKEND_BASE_URL = os.getenv("BACKEND_BASE_URL", "")


def get_redirect_uri(request: Request) -> str:
    """Build redirect URI from request headers or env."""
    # Try X-Forwarded headers first (behind proxy)
    forwarded_host = request.headers.get("x-forwarded-host", "")
    forwarded_proto = request.headers.get("x-forwarded-proto", "https")
    if forwarded_host:
        return f"{forwarded_proto}://{forwarded_host}/api/oauth/calendar/callback"
    if BACKEND_BASE_URL:
        return f"{BACKEND_BASE_URL}/api/oauth/calendar/callback"
    return f"{request.base_url}api/oauth/calendar/callback"


# ================================================================
# OAUTH FLOW
# ================================================================

@router.get("/oauth/calendar/start")
async def start_calendar_oauth(request: Request, user: dict = Depends(get_current_user)):
    """Start Google Calendar OAuth flow. Returns the authorization URL."""
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        raise HTTPException(
            status_code=503,
            detail=(
                "Google Calendar sync is not configured on this server. "
                "Ask the administrator to set GOOGLE_OAUTH_CLIENT_ID and "
                "GOOGLE_OAUTH_CLIENT_SECRET in the backend .env and restart."
            ),
        )

    redirect_uri = get_redirect_uri(request)

    # Store state to associate with user
    state = str(uuid.uuid4())
    await db.oauth_states.insert_one({
        "state": state,
        "user_id": user["user_id"],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "redirect_uri": redirect_uri,
    })

    auth_url = (
        f"https://accounts.google.com/o/oauth2/v2/auth?"
        f"client_id={GOOGLE_CLIENT_ID}"
        f"&redirect_uri={redirect_uri}"
        f"&response_type=code"
        f"&scope={'%20'.join(SCOPES)}%20https://www.googleapis.com/auth/userinfo.email"
        f"&access_type=offline"
        f"&prompt=consent"
        f"&state={state}"
    )

    return {"authorization_url": auth_url, "state": state}


@router.get("/oauth/calendar/callback")
async def calendar_oauth_callback(request: Request, code: str = "", state: str = "", error: str = ""):
    """Handle Google OAuth callback."""
    if error:
        return RedirectResponse(f"/?calendar_error={error}")

    if not code or not state:
        return RedirectResponse("/?calendar_error=missing_params")

    # Lookup state
    state_doc = await db.oauth_states.find_one({"state": state})
    if not state_doc:
        return RedirectResponse("/?calendar_error=invalid_state")

    user_id = state_doc["user_id"]
    redirect_uri = state_doc.get("redirect_uri", get_redirect_uri(request))

    # Exchange code for tokens
    token_resp = http_requests.post("https://oauth2.googleapis.com/token", data={
        "code": code,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    })

    if token_resp.status_code != 200:
        return RedirectResponse(f"/?calendar_error=token_exchange_failed")

    tokens = token_resp.json()

    # Get user info
    userinfo = http_requests.get(
        "https://www.googleapis.com/oauth2/v2/userinfo",
        headers={"Authorization": f"Bearer {tokens['access_token']}"}
    ).json()

    # Store tokens
    await db.google_calendar_tokens.update_one(
        {"user_id": user_id},
        {"$set": {
            "user_id": user_id,
            "access_token": tokens["access_token"],
            "refresh_token": tokens.get("refresh_token"),
            "token_type": tokens.get("token_type", "Bearer"),
            "expires_in": tokens.get("expires_in"),
            "scope": tokens.get("scope"),
            "google_email": userinfo.get("email", ""),
            "connected_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }},
        upsert=True
    )

    # Clean up state
    await db.oauth_states.delete_one({"state": state})

    # Redirect back to app with success
    return RedirectResponse("/?calendar_connected=true")


@router.get("/oauth/calendar/status")
async def calendar_connection_status(user: dict = Depends(get_current_user)):
    """Check if user has connected their Google Calendar."""
    token_doc = await db.google_calendar_tokens.find_one(
        {"user_id": user["user_id"]},
        {"_id": 0, "access_token": 0, "refresh_token": 0}
    )
    if token_doc:
        return {
            "connected": True,
            "google_email": token_doc.get("google_email", ""),
            "connected_at": token_doc.get("connected_at", ""),
        }
    return {"connected": False}


@router.delete("/oauth/calendar/disconnect")
async def disconnect_calendar(user: dict = Depends(get_current_user)):
    """Disconnect Google Calendar."""
    await db.google_calendar_tokens.delete_one({"user_id": user["user_id"]})
    return {"message": "Google Calendar disconnected"}


# ================================================================
# HELPER: Get valid credentials
# ================================================================

async def get_google_credentials(user_id: str):
    """Get valid Google credentials, refreshing if needed."""
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request as GoogleRequest

    token_doc = await db.google_calendar_tokens.find_one({"user_id": user_id})
    if not token_doc:
        return None

    creds = Credentials(
        token=token_doc["access_token"],
        refresh_token=token_doc.get("refresh_token"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
    )

    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(GoogleRequest())
            await db.google_calendar_tokens.update_one(
                {"user_id": user_id},
                {"$set": {
                    "access_token": creds.token,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }}
            )
        except Exception as e:
            print(f"Token refresh failed: {e}")
            return None

    return creds


# ================================================================
# CALENDAR EVENT ENDPOINTS
# ================================================================

@router.get("/google-calendar/events")
async def list_calendar_events(
    days: int = Query(default=30, ge=1, le=365),
    user: dict = Depends(get_current_user),
):
    """List upcoming Google Calendar events."""
    from googleapiclient.discovery import build

    creds = await get_google_credentials(user["user_id"])
    if not creds:
        raise HTTPException(status_code=401, detail="Google Calendar not connected. Please connect first.")

    try:
        service = build("calendar", "v3", credentials=creds)
        now = datetime.now(timezone.utc).isoformat()
        end = (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()

        events_result = service.events().list(
            calendarId="primary",
            timeMin=now,
            timeMax=end,
            maxResults=100,
            singleEvents=True,
            orderBy="startTime",
        ).execute()

        events = events_result.get("items", [])
        return {
            "events": [
                {
                    "id": e.get("id"),
                    "summary": e.get("summary", ""),
                    "description": e.get("description", ""),
                    "start": e.get("start", {}).get("dateTime") or e.get("start", {}).get("date"),
                    "end": e.get("end", {}).get("dateTime") or e.get("end", {}).get("date"),
                    "html_link": e.get("htmlLink", ""),
                    "status": e.get("status", ""),
                    "location": e.get("location", ""),
                }
                for e in events
            ],
            "total": len(events),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Calendar API error: {str(e)}")


@router.post("/google-calendar/events")
async def create_calendar_event(request: Request, user: dict = Depends(get_current_user)):
    """Create a Google Calendar event (e.g., from a CTT task)."""
    from googleapiclient.discovery import build

    creds = await get_google_credentials(user["user_id"])
    if not creds:
        raise HTTPException(status_code=401, detail="Google Calendar not connected")

    body = await request.json()
    summary = body.get("summary", body.get("title", ""))
    if not summary:
        raise HTTPException(status_code=400, detail="Event summary/title is required")

    description = body.get("description", "")
    start_str = body.get("start")
    end_str = body.get("end")
    all_day = body.get("all_day", False)
    location = body.get("location", "")
    timezone_str = body.get("timezone", "Asia/Kolkata")

    # Link to CTT task if provided
    ctt_task_id = body.get("ctt_task_id")
    if ctt_task_id:
        description += f"\n\n[View Dezider CTT Task: {ctt_task_id}]"

    event_body = {
        "summary": summary,
        "description": description,
        "location": location,
    }

    if all_day:
        event_body["start"] = {"date": start_str[:10]}
        event_body["end"] = {"date": end_str[:10] if end_str else start_str[:10]}
    else:
        if not start_str:
            raise HTTPException(status_code=400, detail="Start time is required")
        event_body["start"] = {"dateTime": start_str, "timeZone": timezone_str}
        if end_str:
            event_body["end"] = {"dateTime": end_str, "timeZone": timezone_str}
        else:
            # Default 1 hour duration
            start_dt = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
            end_dt = start_dt + timedelta(hours=1)
            event_body["end"] = {"dateTime": end_dt.isoformat(), "timeZone": timezone_str}

    # Add reminders
    event_body["reminders"] = {
        "useDefault": False,
        "overrides": [
            {"method": "popup", "minutes": 30},
            {"method": "popup", "minutes": 10},
        ]
    }

    try:
        service = build("calendar", "v3", credentials=creds)
        event = service.events().insert(calendarId="primary", body=event_body).execute()

        # If linked to CTT, save the calendar event ID on the task
        if ctt_task_id:
            await db.ctt_tasks.update_one(
                {"task_id": ctt_task_id},
                {"$set": {
                    "google_calendar_event_id": event.get("id"),
                    "google_calendar_link": event.get("htmlLink", ""),
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }}
            )

        return {
            "message": "Event created",
            "event_id": event.get("id"),
            "html_link": event.get("htmlLink", ""),
            "summary": event.get("summary", ""),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Calendar API error: {str(e)}")


@router.put("/google-calendar/events/{event_id}")
async def update_calendar_event(event_id: str, request: Request, user: dict = Depends(get_current_user)):
    """Update a Google Calendar event."""
    from googleapiclient.discovery import build

    creds = await get_google_credentials(user["user_id"])
    if not creds:
        raise HTTPException(status_code=401, detail="Google Calendar not connected")

    body = await request.json()
    updates = {}
    if "summary" in body:
        updates["summary"] = body["summary"]
    if "description" in body:
        updates["description"] = body["description"]
    if "location" in body:
        updates["location"] = body["location"]
    if "start" in body:
        updates["start"] = {"dateTime": body["start"], "timeZone": body.get("timezone", "Asia/Kolkata")}
    if "end" in body:
        updates["end"] = {"dateTime": body["end"], "timeZone": body.get("timezone", "Asia/Kolkata")}

    try:
        service = build("calendar", "v3", credentials=creds)
        event = service.events().patch(
            calendarId="primary", eventId=event_id, body=updates
        ).execute()
        return {"message": "Event updated", "event_id": event.get("id")}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Calendar API error: {str(e)}")


@router.delete("/google-calendar/events/{event_id}")
async def delete_calendar_event(event_id: str, user: dict = Depends(get_current_user)):
    """Delete a Google Calendar event."""
    from googleapiclient.discovery import build

    creds = await get_google_credentials(user["user_id"])
    if not creds:
        raise HTTPException(status_code=401, detail="Google Calendar not connected")

    try:
        service = build("calendar", "v3", credentials=creds)
        service.events().delete(calendarId="primary", eventId=event_id).execute()

        # Also clear the reference from any CTT task
        await db.ctt_tasks.update_many(
            {"google_calendar_event_id": event_id},
            {"$unset": {"google_calendar_event_id": "", "google_calendar_link": ""}}
        )

        return {"message": "Event deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Calendar API error: {str(e)}")


@router.post("/google-calendar/sync-ctt-task")
async def sync_ctt_task_to_calendar(request: Request, user: dict = Depends(get_current_user)):
    """Sync a CTT task to Google Calendar as an event."""
    body = await request.json()
    task_id = body.get("task_id")

    if not task_id:
        raise HTTPException(status_code=400, detail="task_id is required")

    task = await db.ctt_tasks.find_one({"task_id": task_id, "user_id": user["user_id"]})
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Build event from task
    summary = task.get("title", "CTT Task")
    description = task.get("description", "")
    due_date = task.get("due_date")

    if not due_date:
        raise HTTPException(status_code=400, detail="Task has no due date set. Please set a due date first.")

    # Create event with due date
    event_data = {
        "summary": f"[CTT] {summary}",
        "description": f"{description}\n\nPriority: {task.get('priority', 'medium')}\nLife Area: {task.get('life_area', '')}\nSource: {task.get('source_type', '')}",
        "start": due_date,
        "end": due_date,
        "all_day": True if len(due_date) <= 10 else False,
        "ctt_task_id": task_id,
        "timezone": body.get("timezone", "Asia/Kolkata"),
    }

    # Forward to create event endpoint (reuse logic)
    from googleapiclient.discovery import build

    creds = await get_google_credentials(user["user_id"])
    if not creds:
        raise HTTPException(status_code=401, detail="Google Calendar not connected")

    event_body = {
        "summary": event_data["summary"],
        "description": event_data["description"],
        "reminders": {
            "useDefault": False,
            "overrides": [{"method": "popup", "minutes": 60}]
        },
    }

    if event_data["all_day"]:
        event_body["start"] = {"date": due_date[:10]}
        event_body["end"] = {"date": due_date[:10]}
    else:
        tz = event_data["timezone"]
        event_body["start"] = {"dateTime": due_date, "timeZone": tz}
        start_dt = datetime.fromisoformat(due_date.replace("Z", "+00:00"))
        end_dt = start_dt + timedelta(hours=1)
        event_body["end"] = {"dateTime": end_dt.isoformat(), "timeZone": tz}

    try:
        service = build("calendar", "v3", credentials=creds)
        event = service.events().insert(calendarId="primary", body=event_body).execute()

        # Link event to task
        await db.ctt_tasks.update_one(
            {"task_id": task_id},
            {"$set": {
                "google_calendar_event_id": event.get("id"),
                "google_calendar_link": event.get("htmlLink", ""),
                "synced_to_calendar": True,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }}
        )

        return {
            "message": "Task synced to Google Calendar",
            "event_id": event.get("id"),
            "html_link": event.get("htmlLink", ""),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Calendar sync error: {str(e)}")
