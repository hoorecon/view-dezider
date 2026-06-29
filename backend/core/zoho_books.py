"""Zoho Books integration — pull P&L + Balance Sheet historicals and map them
into the Financial Model's base-year assumptions.

Server-to-server (Self Client): a long-lived refresh token in the env is
exchanged for short-lived access tokens (cached in-memory).
"""
import os
import time
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

import httpx

ACCOUNTS_URL = os.environ.get("ZOHO_ACCOUNTS_URL", "https://accounts.zoho.in").rstrip("/")
API_URL = os.environ.get("ZOHO_API_URL", "https://www.zohoapis.in").rstrip("/")
CLIENT_ID = os.environ.get("ZOHO_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("ZOHO_CLIENT_SECRET", "")
REFRESH_TOKEN = os.environ.get("ZOHO_REFRESH_TOKEN", "")
ORG_ID = os.environ.get("ZOHO_ORGANIZATION_ID", "")

_token_cache: Dict[str, Any] = {"access_token": None, "expires_at": 0.0}


def is_configured() -> bool:
    return bool(CLIENT_ID and CLIENT_SECRET and REFRESH_TOKEN and ORG_ID)


async def _access_token() -> str:
    now = time.time()
    if _token_cache["access_token"] and _token_cache["expires_at"] > now + 30:
        return _token_cache["access_token"]
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{ACCOUNTS_URL}/oauth/v2/token", data={
            "grant_type": "refresh_token",
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "refresh_token": REFRESH_TOKEN,
        })
    data = r.json()
    tok = data.get("access_token")
    if not tok:
        raise RuntimeError(f"Zoho token refresh failed: {data.get('error') or data}")
    _token_cache["access_token"] = tok
    _token_cache["expires_at"] = now + int(data.get("expires_in", 3600))
    return tok


async def _get(path: str, params: Dict[str, Any]) -> Dict[str, Any]:
    tok = await _access_token()
    params = {**params, "organization_id": ORG_ID}
    async with httpx.AsyncClient(timeout=45) as client:
        r = await client.get(
            f"{API_URL}/books/v3/{path}", params=params,
            headers={"Authorization": f"Zoho-oauthtoken {tok}"})
    data = r.json()
    if data.get("code") not in (0, None):
        raise RuntimeError(data.get("message") or "Zoho API error")
    return data


def _last_fy() -> Tuple[str, str]:
    """Most recent completed Indian financial year (Apr 1 – Mar 31)."""
    today = date.today()
    fy_end_year = today.year if today.month >= 4 else today.year - 1
    # the last *completed* FY ended on Mar 31 of fy_end_year if we're past Apr,
    # else the previous one
    end = date(fy_end_year, 3, 31)
    if today < end:
        end = date(fy_end_year - 1, 3, 31)
    start = date(end.year - 1, 4, 1)
    return start.isoformat(), end.isoformat()


def _flatten(nodes: List[dict], out: Dict[str, float]) -> None:
    for n in nodes or []:
        tot = n.get("total")
        if isinstance(tot, (int, float)):
            for key in (n.get("name"), n.get("total_label")):
                k = (key or "").strip().lower()
                if k and k not in out:  # keep the outermost (section) value
                    out[k] = float(tot)
        _flatten(n.get("account_transactions"), out)


def _pick(flat: Dict[str, float], *needles: str) -> Optional[float]:
    for nd in needles:
        if nd in flat:
            return flat[nd]
    for nd in needles:
        for k, v in flat.items():
            if nd in k:
                return v
    return None


def map_to_assumptions(pnl: List[dict], bs: List[dict]) -> Tuple[Dict[str, Any], List[str]]:
    """Best-effort mapping of Zoho reports -> base-year assumptions patch."""
    flat: Dict[str, float] = {}
    _flatten(pnl, flat)
    _flatten(bs, flat)

    patch: Dict[str, Any] = {}
    found: List[str] = []

    def add(key, val):
        if val is not None:
            patch[key] = round(float(val), 2)
            found.append(key)

    revenue = _pick(flat, "total operating income", "operating income")
    gross_profit = _pick(flat, "gross profit")
    opex = _pick(flat, "total operating expense", "operating expense")
    if revenue and revenue > 0:
        add("year1_revenue", revenue)
        if gross_profit is not None:
            patch["gross_margin_pct"] = round(gross_profit / revenue * 100, 2)
            found.append("gross_margin_pct")
        if opex is not None:
            patch["opex_pct"] = round(abs(opex) / revenue * 100, 2)
            found.append("opex_pct")

    # Balance sheet
    cash = (_pick(flat, "total cash", "cash") or 0) + (_pick(flat, "total bank", "bank") or 0)
    if cash:
        add("opening_cash", cash)
    add("opening_debtors", _pick(flat, "total accounts receivable", "accounts receivable"))
    add("opening_inventory", _pick(flat, "total stock on hand", "inventory", "stock on hand"))
    add("opening_creditors", _pick(flat, "total accounts payable", "accounts payable"))
    add("opening_debt", _pick(flat, "total long term liabilities", "borrowings", "term loan"))
    add("opening_gross_block", _pick(flat, "total fixed assets", "fixed assets", "property plant and equipment"))
    add("opening_equity_capital", _pick(flat, "total equities", "total equity", "owner's equity"))
    return patch, found


async def fetch_and_map(from_date: Optional[str] = None,
                        to_date: Optional[str] = None,
                        as_of: Optional[str] = None) -> Dict[str, Any]:
    if not (from_date and to_date):
        from_date, to_date = _last_fy()
    as_of = as_of or to_date
    pnl_resp = await _get("reports/profitandloss", {"from_date": from_date, "to_date": to_date})
    bs_resp = await _get("reports/balancesheet", {"date": as_of})
    pnl = pnl_resp.get("profit_and_loss") or []
    bs = bs_resp.get("balance_sheet") or []
    patch, found = map_to_assumptions(pnl, bs)
    return {
        "organization_id": ORG_ID,
        "from_date": from_date, "to_date": to_date, "as_of": as_of,
        "patch": patch, "found": found,
    }
