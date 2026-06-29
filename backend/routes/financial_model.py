"""
Financial Model API — Phase 1 of the "Financial Model" branch on L1 (Financial)
of an Org's 6 LeGS tree.

A model is owned by a user + scoped to one of their Orgs (user_org_id) and can be
linked to an L1 six_legs goal (leg_goal_id). It stores assumptions; the 3-statement
forecast + ratios + DCF valuation are computed on the fly by core.fin_model.
"""
import asyncio
import base64
import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from core.database import db
from core.auth import get_current_user
from core import ai_wallet
from core.fin_model import compute_model, default_assumptions, compute_cma_extras
from core.url_crawl import has_any_llm, metered_chat
from core import fin_export
from core import chunk_upload
from core import fin_template
from core import matrix_import as mx
from core import google_sheets as gs
from fastapi.responses import Response
from routes.file_import import _extract_text, _detect_type

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
PDF_MIME = "application/pdf"

router = APIRouter(prefix="/financial-models", tags=["Financial Model"])

UNITS = [
    {"id": "absolute", "name": "Absolute", "divisor": 1, "suffix": ""},
    {"id": "thousands", "name": "Thousands (K)", "divisor": 1_000, "suffix": "K"},
    {"id": "lakhs", "name": "Lakhs", "divisor": 100_000, "suffix": "L"},
    {"id": "millions", "name": "Millions (M)", "divisor": 1_000_000, "suffix": "M"},
    {"id": "crores", "name": "Crores", "divisor": 10_000_000, "suffix": "Cr"},
]
HISTORICAL_STAGES = [
    {"id": "pre_revenue", "name": "Pre-revenue (0 months)"},
    {"id": "3m", "name": "3 months actuals"},
    {"id": "6m", "name": "6 months actuals"},
    {"id": "9m", "name": "9 months actuals"},
    {"id": "1y", "name": "1 year actuals"},
    {"id": "2y", "name": "2 years actuals"},
]
CURRENCIES = ["INR", "USD", "EUR", "GBP", "AED", "SGD"]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _own_org(user: dict, user_org_id: str) -> dict:
    org = await db.user_orgs.find_one({"id": user_org_id, "owner_user_id": user["user_id"]})
    if not org:
        raise HTTPException(404, "Org not found or not yours")
    return org


def _with_computed(model: dict) -> dict:
    model = dict(model)
    model.pop("_id", None)
    try:
        model["computed"] = compute_model(
            model.get("assumptions") or {}, model.get("projection_years", 5))
    except Exception as e:  # noqa: BLE001
        model["computed"] = None
        model["compute_error"] = str(e)[:200]
    return model


@router.get("/meta")
async def get_meta(user: dict = Depends(get_current_user)):
    return {
        "default_assumptions": default_assumptions(),
        "units": UNITS,
        "currencies": CURRENCIES,
        "historical_stages": HISTORICAL_STAGES,
        "max_projection_years": 10,
    }


class ComputeIn(BaseModel):
    assumptions: Dict[str, Any]
    projection_years: int = 5


@router.post("/compute")
async def compute_preview(body: ComputeIn, user: dict = Depends(get_current_user)):
    """Stateless compute for live preview (no save)."""
    return {"computed": compute_model(body.assumptions or {}, body.projection_years)}


class ModelIn(BaseModel):
    user_org_id: str
    leg_goal_id: Optional[str] = None
    name: str = "Financial Model"
    currency: str = "INR"
    units: str = "absolute"
    historical_stage: str = "pre_revenue"
    projection_years: int = 5
    assumptions: Optional[Dict[str, Any]] = None


@router.post("")
async def create_model(p: ModelIn, user: dict = Depends(get_current_user)):
    await _own_org(user, p.user_org_id)
    doc = {
        "id": str(uuid.uuid4()),
        "user_id": user["user_id"],
        "user_org_id": p.user_org_id,
        "leg_goal_id": p.leg_goal_id,
        "name": (p.name or "Financial Model").strip(),
        "currency": p.currency or "INR",
        "units": p.units or "absolute",
        "historical_stage": p.historical_stage or "pre_revenue",
        "projection_years": max(1, min(int(p.projection_years or 5), 10)),
        "assumptions": p.assumptions or default_assumptions(),
        "created_at": _now(),
        "updated_at": _now(),
    }
    await db.financial_models.insert_one(doc)
    return _with_computed(doc)


@router.get("")
async def list_models(user_org_id: str, user: dict = Depends(get_current_user)):
    await _own_org(user, user_org_id)
    rows = await db.financial_models.find(
        {"user_org_id": user_org_id, "user_id": user["user_id"]},
        {"_id": 0, "assumptions": 0},
    ).sort("created_at", -1).to_list(200)
    return {"models": rows}


@router.get("/{model_id}")
async def get_model(model_id: str, user: dict = Depends(get_current_user)):
    doc = await db.financial_models.find_one(
        {"id": model_id, "user_id": user["user_id"]})
    if not doc:
        raise HTTPException(404, "Financial model not found")
    return _with_computed(doc)


@router.put("/{model_id}")
async def update_model(model_id: str, request: Request, user: dict = Depends(get_current_user)):
    existing = await db.financial_models.find_one(
        {"id": model_id, "user_id": user["user_id"]})
    if not existing:
        raise HTTPException(404, "Financial model not found")
    body = await request.json()
    allowed = ["name", "currency", "units", "historical_stage", "assumptions", "leg_goal_id"]
    update: Dict[str, Any] = {k: body[k] for k in allowed if k in body}
    if "projection_years" in body:
        update["projection_years"] = max(1, min(int(body["projection_years"] or 5), 10))
    update["updated_at"] = _now()
    await db.financial_models.update_one({"id": model_id}, {"$set": update})
    doc = await db.financial_models.find_one({"id": model_id})
    return _with_computed(doc)


@router.delete("/{model_id}")
async def delete_model(model_id: str, user: dict = Depends(get_current_user)):
    res = await db.financial_models.delete_one(
        {"id": model_id, "user_id": user["user_id"]})
    if not res.deleted_count:
        raise HTTPException(404, "Financial model not found")
    return {"ok": True}


# ────────────────────────── Exports (Phase 2) ──────────────────────────

def _unit_ctx(model: dict):
    uid = model.get("units", "absolute")
    u = next((x for x in UNITS if x["id"] == uid), UNITS[0])
    label = f"{model.get('currency', 'INR')} · {u['name']}"
    return u["divisor"], label


def _slug(model: dict) -> str:
    base = (model.get("name") or "financial-model").strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", base).strip("-")
    return s or "financial-model"


def _stream(data: bytes, filename: str, media: str) -> StreamingResponse:
    return StreamingResponse(
        iter([data]), media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'})


async def _load_for_export(model_id: str, user: dict):
    doc = await db.financial_models.find_one({"id": model_id, "user_id": user["user_id"]})
    if not doc:
        raise HTTPException(404, "Financial model not found")
    doc.pop("_id", None)
    computed = compute_model(doc.get("assumptions") or {}, doc.get("projection_years", 5))
    return doc, computed


@router.get("/{model_id}/export/investor.xlsx")
async def export_investor_xlsx(model_id: str, user: dict = Depends(get_current_user)):
    doc, computed = await _load_for_export(model_id, user)
    div, label = _unit_ctx(doc)
    data = fin_export.build_investor_xlsx(doc, computed, div, label)
    return _stream(data, f"{_slug(doc)}-investor.xlsx", XLSX_MIME)


@router.get("/{model_id}/export/investor.pdf")
async def export_investor_pdf(model_id: str, user: dict = Depends(get_current_user)):
    doc, computed = await _load_for_export(model_id, user)
    div, label = _unit_ctx(doc)
    data = fin_export.build_investor_pdf(doc, computed, div, label)
    return _stream(data, f"{_slug(doc)}-investor.pdf", PDF_MIME)


@router.get("/{model_id}/export/cma.xlsx")
async def export_cma_xlsx(model_id: str, user: dict = Depends(get_current_user)):
    doc, computed = await _load_for_export(model_id, user)
    extras = compute_cma_extras(doc.get("assumptions") or {}, computed)
    div, label = _unit_ctx(doc)
    data = fin_export.build_cma_xlsx(doc, computed, extras, div, label)
    return _stream(data, f"{_slug(doc)}-cma.xlsx", XLSX_MIME)


@router.get("/{model_id}/export/cma.pdf")
async def export_cma_pdf(model_id: str, user: dict = Depends(get_current_user)):
    doc, computed = await _load_for_export(model_id, user)
    extras = compute_cma_extras(doc.get("assumptions") or {}, computed)
    div, label = _unit_ctx(doc)
    data = fin_export.build_cma_pdf(doc, computed, extras, div, label)
    return _stream(data, f"{_slug(doc)}-cma.pdf", PDF_MIME)


# ────────────────── Seed base year from an uploaded Excel (Phase 1 add-on) ──────────────────

_SEED_KEYS = [
    "opening_gross_block", "opening_debt", "opening_equity_capital", "opening_cash",
    "opening_debtors", "opening_inventory", "opening_creditors",
    "year1_revenue", "gross_margin_pct", "opex_pct", "tax_rate_pct",
    "interest_rate_pct", "shares_outstanding",
]
_SEED_SYS = (
    "You read a company's financial statements (P&L + Balance Sheet) and seed a "
    "forecast's OPENING balances from the MOST RECENT period's closing figures. "
    "Reply with ONLY compact JSON using these numeric keys (absolute units, omit a "
    "key if it cannot be determined): "
    "opening_gross_block (gross fixed assets), opening_debt (total borrowings), "
    "opening_equity_capital (share capital), opening_cash, opening_debtors (receivables), "
    "opening_inventory, opening_creditors (payables), year1_revenue (latest revenue), "
    "gross_margin_pct, opex_pct (% of revenue), tax_rate_pct, interest_rate_pct, "
    "shares_outstanding. No prose, no commentary."
)


class SeedIn(BaseModel):
    filename: str
    file_b64: Optional[str] = None
    upload_id: Optional[str] = None
    ai_tier: Optional[str] = "fast"


@router.post("/seed-from-file")
async def seed_from_file(body: SeedIn, user: dict = Depends(get_current_user)):
    """Parse an uploaded financial statements file and return an assumptions patch
    that pre-fills the opening balances. Metered via the AI wallet."""
    if not has_any_llm():
        raise HTTPException(400, "AI is not configured on this server.")
    ftype = _detect_type(body.filename or "")
    if ftype in ("unknown", "doc_legacy"):
        raise HTTPException(400, "Use an Excel/CSV/PDF/text financial statements file.")
    if body.upload_id:
        try:
            _fn, raw = await asyncio.to_thread(chunk_upload.assemble, body.upload_id)
        except KeyError:
            raise HTTPException(404, "Upload session expired — please re-pick the file and retry.")
        except Exception:
            raise HTTPException(400, "Could not assemble the uploaded file.")
        finally:
            chunk_upload.discard(body.upload_id)
    else:
        try:
            raw = base64.b64decode((body.file_b64 or "").split(",")[-1])
        except Exception:
            raise HTTPException(400, "Could not decode the uploaded file.")
    if not raw:
        raise HTTPException(400, "The uploaded file is empty.")
    try:
        text = await asyncio.to_thread(_extract_text, raw, ftype)
    except Exception:
        raise HTTPException(422, "Couldn't read this file. Try a clearer Excel/PDF.")
    if len(text.strip()) < 20:
        raise HTTPException(422, "No readable financial data found in the file.")

    tier = "precise" if (body.ai_tier or "").lower() == "precise" else "fast"
    try:
        out = await metered_chat(
            user["user_id"], system_message=_SEED_SYS, prompt=text[:16000],
            feature="fin_seed", session_prefix="finseed", tier=tier)
    except ai_wallet.InsufficientCredits as e:
        raise HTTPException(402, f"Out of AI credits (balance {round(e.balance, 2)}).")
    m = re.search(r"\{.*\}", out, re.S)
    data = json.loads(m.group(0)) if m else {}
    patch: Dict[str, Any] = {}
    for k in _SEED_KEYS:
        if k in data and data[k] not in (None, ""):
            try:
                patch[k] = float(data[k])
            except (TypeError, ValueError):
                continue
    if not patch:
        raise HTTPException(422, "Couldn't extract opening balances from this file.")
    return {"patch": patch, "found": list(patch.keys())}



# ── Template download + deterministic Excel / Google-Sheet import ────────────
@router.get("/templates/inputs.xlsx")
async def download_template(user: dict = Depends(get_current_user)):
    data = fin_template.build_template_xlsx()
    return Response(
        content=data, media_type=XLSX_MIME,
        headers={"Content-Disposition": 'attachment; filename="financial-model-template.xlsx"'},
    )


class ImportFileIn(BaseModel):
    filename: str
    upload_id: Optional[str] = None
    file_b64: Optional[str] = None


def _rows_from_bytes(filename: str, raw: bytes):
    name = (filename or "").lower()
    if name.endswith(".csv"):
        return mx.extract_rows_from_csv(raw)
    return mx.extract_rows_from_xlsx(raw)


@router.post("/import-file")
async def import_template_file(body: ImportFileIn, user: dict = Depends(get_current_user)):
    """Parse a filled template (.xlsx/.csv) into an assumptions patch — no AI."""
    if body.upload_id:
        try:
            fn, raw = await asyncio.to_thread(chunk_upload.assemble, body.upload_id)
        except KeyError:
            raise HTTPException(404, "Upload session expired — please re-pick the file.")
        except Exception:
            raise HTTPException(400, "Could not assemble the uploaded file.")
        finally:
            chunk_upload.discard(body.upload_id)
        filename = body.filename or fn
    else:
        try:
            raw = base64.b64decode((body.file_b64 or "").split(",")[-1])
        except Exception:
            raise HTTPException(400, "Could not decode the uploaded file.")
        filename = body.filename
    try:
        rows = await asyncio.to_thread(_rows_from_bytes, filename, raw)
    except Exception:
        raise HTTPException(422, "Could not read the file. Use the provided .xlsx/.csv template.")
    patch, matched = fin_template.parse_rows_to_assumptions(rows)
    if not patch:
        raise HTTPException(422, "No template rows matched. Keep the labels in column A unchanged.")
    return {"patch": patch, "found": matched}


class ImportSheetIn(BaseModel):
    sheet_url: str


@router.post("/import-sheet")
async def import_template_sheet(body: ImportSheetIn, user: dict = Depends(get_current_user)):
    """Parse a filled template from a Google Sheet link (public, else the user's
    own connected Google account) into an assumptions patch — no AI."""
    url = (body.sheet_url or "").strip()
    sid, _ = mx.gsheet_id_and_gid(url)
    if not sid:
        raise HTTPException(422, "Paste a valid Google Sheets link.")
    try:
        rows = await mx.fetch_public_gsheet_rows(url)
    except PermissionError:
        try:
            rows = await gs.read_first_sheet(user["user_id"], sid)
        except PermissionError as e:
            raise HTTPException(403, str(e) or "Connect your Google account to import this private sheet.")
        except Exception:
            raise HTTPException(422, "Could not read this Google Sheet via your account.")
    except ValueError as e:
        raise HTTPException(422, str(e))
    if not rows:
        raise HTTPException(422, "The Google Sheet appears to be empty.")
    patch, matched = fin_template.parse_rows_to_assumptions(rows)
    if not patch:
        raise HTTPException(422, "No template rows matched. Keep the labels in column A unchanged.")
    return {"patch": patch, "found": matched}
