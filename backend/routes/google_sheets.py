"""Google Sheets OAuth routes (shared by My Dezider & Pros & Cons).

Endpoints (mounted under /api):
  GET  /oauth/sheets/login     → start OAuth (token + return_to via query, since
                                  this opens in a browser without auth headers)
  GET  /oauth/sheets/callback  → exchange code, store tokens, redirect back to app
  GET  /oauth/sheets/status    → {connected, email}
  POST /oauth/sheets/disconnect

The per-flow "create sheet" / "import sheet" endpoints live in the respective
routers (pros_cons.py, decisions.py) so they can assemble + persist their own data.
"""
import logging
from datetime import datetime, timezone
from urllib.parse import quote, urlencode

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from core import google_sheets as gs
from core.auth import get_current_user
from core.database import db

router = APIRouter()
log = logging.getLogger("google_sheets_routes")

DEFAULT_RETURN = "https://modal-responsive-fix.preview.emergentagent.com"


async def _user_from_token(token: str):
    if not token:
        return None
    sess = await db.user_sessions.find_one({"session_token": token}, {"_id": 0})
    if not sess:
        return None
    exp = sess.get("expires_at")
    if isinstance(exp, str):
        try:
            exp = datetime.fromisoformat(exp)
        except Exception:
            exp = None
    if isinstance(exp, datetime):
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if exp < datetime.now(timezone.utc):
            return None
    return sess.get("user_id")


def _close_page(message: str, ok: bool) -> HTMLResponse:
    color = "#16a34a" if ok else "#dc2626"
    return HTMLResponse(
        f"""<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1">
        <title>Google Sheets</title></head>
        <body style="font-family:-apple-system,Segoe UI,Roboto,sans-serif;display:flex;
        align-items:center;justify-content:center;height:100vh;margin:0;background:#0f172a;">
        <div style="text-align:center;color:#fff;max-width:340px;padding:24px;">
        <div style="font-size:40px;color:{color};">{'✓' if ok else '⚠'}</div>
        <h2 style="margin:12px 0;">{message}</h2>
        <p style="color:#94a3b8;">You can close this window and return to the app.</p>
        </div><script>try{{window.close();}}catch(e){{}}</script></body></html>"""
    )


def _redirect_uri_from_request(request: Request) -> str:
    """Build the callback URL from the public host so it works on BOTH preview
    and production automatically (both must be registered on the OAuth client).
    Falls back to the configured env value."""
    host = request.headers.get("x-forwarded-host") or request.url.netloc
    proto = request.headers.get("x-forwarded-proto") or request.url.scheme or "https"
    if host:
        return f"{proto}://{host}/api/oauth/sheets/callback"
    return gs.REDIRECT_URI


@router.get("/oauth/sheets/login")
async def sheets_login(request: Request, token: str = Query(...), return_to: str = Query(DEFAULT_RETURN)):
    if not gs.is_configured():
        raise HTTPException(status_code=500, detail="Google Sheets is not configured on the server.")
    user_id = await _user_from_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid or expired session.")
    redirect_uri = _redirect_uri_from_request(request)
    import uuid as _uuid
    state = _uuid.uuid4().hex
    auth_url, code_verifier = gs.build_auth_url(state, redirect_uri)
    await gs.save_state(state, user_id, return_to or DEFAULT_RETURN, redirect_uri, code_verifier)
    return RedirectResponse(auth_url)


@router.get("/oauth/sheets/callback")
async def sheets_callback(request: Request, code: str = Query(None), state: str = Query(None), error: str = Query(None)):
    if error:
        return _close_page("Google access was denied.", ok=False)
    if not code or not state:
        return _close_page("Missing authorization code.", ok=False)
    st = await gs.consume_state(state)
    if not st:
        return _close_page("This sign-in link expired. Please try again.", ok=False)
    redirect_uri = st.get("redirect_uri") or _redirect_uri_from_request(request)
    try:
        email = await gs.exchange_and_store(code, st["user_id"], redirect_uri, st.get("code_verifier"))
    except Exception as e:
        log.exception(f"sheets callback token exchange failed (redirect_uri={redirect_uri}): {e}")
        return _close_page(f"Could not connect Google Sheets: {str(e)[:200]}", ok=False)
    return_to = st.get("return_to") or DEFAULT_RETURN
    sep = "&" if "?" in return_to else "?"
    target = f"{return_to}{sep}{urlencode({'sheets': 'connected', 'email': email})}"
    # Redirect back to the app; the close-page is a fallback if redirect is blocked.
    try:
        return RedirectResponse(target)
    except Exception:
        return _close_page(f"Connected as {email}.", ok=True)


@router.get("/oauth/sheets/status")
async def sheets_status(user: dict = Depends(get_current_user)):
    return await gs.get_status(user["user_id"])


@router.post("/oauth/sheets/disconnect")
async def sheets_disconnect(user: dict = Depends(get_current_user)):
    await gs.disconnect(user["user_id"])
    return {"disconnected": True}
