"""My Dezider assessment template routes — XLS export/import, Google Sheet
export/import, and per-cell AI satisfaction assessment (parity with Pros & Cons).
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from fastapi.responses import Response
from core.database import db
from core.assessment_xlsx import build_template, parse_template, build_value_matrix, parse_rows
from core import google_sheets as gs
from core.auth import get_current_user
from .services import ordered_factors, apply_assessment_rows

router = APIRouter(tags=["Decisions"])


def _hasv(v: Any) -> bool:
    return v is not None and str(v).strip() != ""


def _apply_assessment(factor: dict, option: dict, result: dict):
    """Mutate `factor` (AI-generated Expected/Operator/Unit) and upsert the
    option's assessment cell in-place. Shared by the single-cell and batch
    AI-assess endpoints. Returns (pct, final_actual)."""
    pct = result["assessment_pct"]
    final_actual = result.get("actual_value")
    unit = factor.get("unit") or ""
    generated = result.get("generated") or {}
    if generated:
        if _hasv(generated.get("expected_value")):
            factor["expected_value"] = generated["expected_value"]
        if _hasv(generated.get("operator")):
            factor["operator"] = generated["operator"]
        if _hasv(generated.get("unit")):
            factor["unit"] = generated["unit"]
            unit = factor["unit"]
    unit_value = (
        f"{final_actual}{(' ' + unit) if (unit and unit not in str(final_actual)) else ''}"
        if final_actual not in (None, "") else ""
    )
    assessments = option.setdefault("assessments", [])
    a = next((x for x in assessments if x.get("factor_id") == factor["id"]), None)
    if not a:
        a = {"factor_id": factor["id"]}
        assessments.append(a)
    a["percentage"] = pct
    if unit_value:
        a["unit_value"] = unit_value
    a["assessment_mode"] = "custom"
    return pct, final_actual


@router.get("/decisions/{decision_id}/assessment-template")
async def md_download_assessment_template(decision_id: str, user: dict = Depends(get_current_user)):
    decision = await db.decisions.find_one({"id": decision_id, "user_id": user["user_id"]}, {"_id": 0})
    if not decision:
        raise HTTPException(status_code=404, detail="Decision not found")
    factors = ordered_factors(decision)
    options = [{"id": o["id"], "name": o.get("name") or "Option"} for o in decision.get("options", [])]
    # cell lookup: option.assessments[].{percentage, unit_value}
    cell_index: Dict[str, Dict[str, dict]] = {}
    for o in decision.get("options", []):
        cell_index[o["id"]] = {a["factor_id"]: a for a in o.get("assessments", []) if a.get("factor_id")}

    def get_cell(oid: str, fid: str) -> Dict[str, Any]:
        a = (cell_index.get(oid) or {}).get(fid) or {}
        return {"actual": a.get("unit_value") or "", "pct": a.get("percentage")}

    title = decision.get("title") or "Decision"
    data = build_template(title, factors, options, get_cell)
    safe = "".join(ch for ch in title if ch.isalnum() or ch in (" ", "-", "_")).strip()[:40] or "assessment"
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{safe}-assessment.xlsx"'},
    )


@router.post("/decisions/{decision_id}/assessment-import")
async def md_import_assessment_template(
    decision_id: str, file: UploadFile = File(...), user: dict = Depends(get_current_user),
):
    decision = await db.decisions.find_one({"id": decision_id, "user_id": user["user_id"]}, {"_id": 0})
    if not decision:
        raise HTTPException(status_code=404, detail="Decision not found")
    try:
        raw = await file.read()
        rows = parse_template(raw)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not read the file: {e}")

    applied = await apply_assessment_rows(decision, rows, decision_id, user["user_id"])
    return {"applied": applied, "rows": len(rows)}


@router.post("/decisions/{decision_id}/assessment-gsheet")
async def md_create_assessment_gsheet(decision_id: str, user: dict = Depends(get_current_user)):
    """Create a Google Sheet (in the user's own Drive) pre-filled with the
    assessment template. Returns {url, spreadsheet_id}."""
    decision = await db.decisions.find_one({"id": decision_id, "user_id": user["user_id"]}, {"_id": 0})
    if not decision:
        raise HTTPException(status_code=404, detail="Decision not found")
    factors = ordered_factors(decision)
    options = [{"id": o["id"], "name": o.get("name") or "Option"} for o in decision.get("options", [])]
    cell_index: Dict[str, Dict[str, dict]] = {}
    for o in decision.get("options", []):
        cell_index[o["id"]] = {a["factor_id"]: a for a in o.get("assessments", []) if a.get("factor_id")}

    def get_cell(oid: str, fid: str) -> Dict[str, Any]:
        a = (cell_index.get(oid) or {}).get(fid) or {}
        return {"actual": a.get("unit_value") or "", "pct": a.get("percentage")}

    title = decision.get("title") or "Decision"
    matrix = build_value_matrix(factors, options, get_cell)
    try:
        res = await gs.create_assessment_sheet(user["user_id"], title, matrix)
    except PermissionError as e:
        raise HTTPException(status_code=428, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Could not create the Google Sheet: {e}")
    await db.decisions.update_one(
        {"id": decision_id, "user_id": user["user_id"]},
        {"$set": {"gsheet_id": res["spreadsheet_id"], "gsheet_url": res["url"], "updated_at": datetime.now(timezone.utc)}},
    )
    return res


@router.post("/decisions/{decision_id}/assessment-gsheet/import")
async def md_import_assessment_gsheet(decision_id: str, body: Optional[Dict[str, Any]] = None, user: dict = Depends(get_current_user)):
    """Read back the linked (or provided) Google Sheet and apply filled values."""
    decision = await db.decisions.find_one({"id": decision_id, "user_id": user["user_id"]}, {"_id": 0})
    if not decision:
        raise HTTPException(status_code=404, detail="Decision not found")
    spreadsheet_id = (body or {}).get("spreadsheet_id") or decision.get("gsheet_id")
    if not spreadsheet_id:
        raise HTTPException(status_code=400, detail="No Google Sheet linked. Create one first.")
    try:
        values = await gs.read_assessment_sheet(user["user_id"], spreadsheet_id)
        rows = parse_rows(values)
    except PermissionError as e:
        raise HTTPException(status_code=428, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not read the Google Sheet: {e}")
    applied = await apply_assessment_rows(decision, rows, decision_id, user["user_id"])
    return {"applied": applied, "rows": len(rows)}


@router.post("/decisions/{decision_id}/factors/{factor_id}/ai-assess")
async def md_ai_assess(
    decision_id: str, factor_id: str,
    body: Dict[str, Any], user: dict = Depends(get_current_user),
):
    """LLM-scored satisfaction % (0-100) for a factor/sub-factor.

    Validation + actual-value resolution are delegated to core.ai_assess
    (shared with Pros & Cons for parity):
      * Quantitative → needs Expected + Operator + Actual (Unit optional).
      * Qualitative  → needs Expected only; AI fetches/infers the Actual.
      * Actual resolution: Data Source → linked Solution Store / ReviewNet → AI guess.
    """
    from core.ai_assess import ai_assess_factor

    decision = await db.decisions.find_one({"id": decision_id, "user_id": user["user_id"]}, {"_id": 0})
    if not decision:
        raise HTTPException(status_code=404, detail="Decision not found")
    factor = next((f for f in decision.get("factors", []) if f["id"] == factor_id), None)
    if not factor:
        raise HTTPException(status_code=404, detail="Factor not found")
    option_id = body.get("option_id")
    option = next((o for o in decision.get("options", []) if o["id"] == option_id), None)
    if not option:
        raise HTTPException(status_code=404, detail="Option not found")

    provided_actual = body.get("actual_value")
    if provided_actual is None or str(provided_actual).strip() == "":
        existing = next((a for a in option.get("assessments", []) if a.get("factor_id") == factor_id), None)
        provided_actual = (existing or {}).get("unit_value")

    result = await ai_assess_factor(
        factor=factor,
        option=option,
        decision_title=decision.get("title") or "",
        decision_context=decision.get("context") or "",
        user_id=user["user_id"],
        provided_actual=provided_actual,
        force_fill=bool(body.get("force_fill")),
    )

    pct, final_actual = _apply_assessment(factor, option, result)
    # Persist factors too — force_fill may have mutated factor.expected_value /
    # operator / unit in-place on decision["factors"], and those changes must
    # reach MongoDB so a subsequent GET returns the standardised target.
    await db.decisions.update_one(
        {"id": decision_id, "user_id": user["user_id"]},
        {"$set": {
            "options": decision["options"],
            "factors": decision["factors"],
            "updated_at": datetime.now(timezone.utc),
        }},
    )
    return {"percentage": pct, "actual_value": final_actual, "source": result.get("source")}


@router.post("/decisions/{decision_id}/ai-assess-batch")
async def md_ai_assess_batch(
    decision_id: str, body: Dict[str, Any], user: dict = Depends(get_current_user),
):
    """Assess a SMALL batch of (option, factor) cells in ONE request.

    Powers "AI Assess All": the client chunks all empty cells into batches and
    calls this once per chunk. This replaces firing dozens of individual POSTs
    (which some production edges/CDNs reject as a burst with 405), while keeping
    each request short enough to avoid gateway timeouts.

    Body: { cells: [{option_id, factor_id, actual_value?}], force_fill?: bool }
    Returns: { results: [{option_id, factor_id, status, percentage?, actual_value?}],
               out_of_credits: bool }   (status ∈ done|skipped|error)
    """
    from core.ai_assess import ai_assess_factor

    decision = await db.decisions.find_one({"id": decision_id, "user_id": user["user_id"]}, {"_id": 0})
    if not decision:
        raise HTTPException(status_code=404, detail="Decision not found")

    cells = body.get("cells") or []
    if not isinstance(cells, list) or not cells:
        raise HTTPException(status_code=400, detail="No cells provided")
    if len(cells) > 12:
        raise HTTPException(status_code=400, detail="Batch too large — send ≤ 12 cells per request")
    force_fill = bool(body.get("force_fill"))

    factors_by_id = {f["id"]: f for f in decision.get("factors", [])}
    options_by_id = {o["id"]: o for o in decision.get("options", [])}

    results: list = []
    out_of_credits = False
    for c in cells:
        oid = c.get("option_id"); fid = c.get("factor_id")
        factor = factors_by_id.get(fid); option = options_by_id.get(oid)
        if not factor or not option:
            results.append({"option_id": oid, "factor_id": fid, "status": "error"}); continue

        provided_actual = c.get("actual_value")
        if provided_actual is None or str(provided_actual).strip() == "":
            existing = next((a for a in option.get("assessments", []) if a.get("factor_id") == fid), None)
            provided_actual = (existing or {}).get("unit_value")

        is_qual = factor.get("data_type") == "text" or factor.get("factor_type") in ("subjective", "qualitative")
        incomplete = (not _hasv(factor.get("expected_value"))) or (
            (not is_qual) and (not _hasv(factor.get("operator")) or not _hasv(provided_actual))
        )
        if incomplete and not force_fill:
            results.append({"option_id": oid, "factor_id": fid, "status": "skipped"}); continue

        try:
            result = await ai_assess_factor(
                factor=factor, option=option,
                decision_title=decision.get("title") or "",
                decision_context=decision.get("context") or "",
                user_id=user["user_id"], provided_actual=provided_actual, force_fill=force_fill,
            )
        except HTTPException as he:
            if he.status_code == 402:
                out_of_credits = True
                break
            results.append({"option_id": oid, "factor_id": fid, "status": "error"}); continue

        pct, final_actual = _apply_assessment(factor, option, result)
        results.append({
            "option_id": oid, "factor_id": fid, "status": "done",
            "percentage": pct, "actual_value": final_actual,
        })

    if any(r["status"] == "done" for r in results):
        await db.decisions.update_one(
            {"id": decision_id, "user_id": user["user_id"]},
            {"$set": {
                "options": decision["options"],
                "factors": decision["factors"],
                "updated_at": datetime.now(timezone.utc),
            }},
        )
    return {"results": results, "out_of_credits": out_of_credits}
