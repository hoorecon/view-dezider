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
from core.blank_default import (
    get_user_blank_default, resolve_decision_blank_pct,
)
from .services import ordered_factors, apply_assessment_rows

router = APIRouter(tags=["Decisions"])


def _hasv(v: Any) -> bool:
    return v is not None and str(v).strip() != ""


def _apply_blank_default(decision: Dict[str, Any], results: list, blank_pct: int) -> int:
    """For each cell marked status='error' (AI couldn't extract / score), write
    a default percentage onto the decision's option assessment so the option's
    overall worth isn't silently dragged to 0 by one missing cell. The default
    is `blank_pct` (0..100); pass 0 to opt OUT entirely (keep legacy behaviour).
    Returns the count of cells that received the default.
    """
    if not blank_pct:
        return 0
    options_by_id = {o["id"]: o for o in decision.get("options", [])}
    factors_by_id = {f["id"]: f for f in decision.get("factors", [])}
    n_applied = 0
    for r in results:
        if r.get("status") != "error":
            continue
        oid = r.get("option_id"); fid = r.get("factor_id")
        option = options_by_id.get(oid)
        factor = factors_by_id.get(fid)
        if not option or not factor:
            continue
        assessments = option.setdefault("assessments", [])
        a = next((x for x in assessments if x.get("factor_id") == fid), None)
        if not a:
            a = {"factor_id": fid}
            assessments.append(a)
        # Only fill if the user / earlier passes haven't already set a value
        if a.get("percentage") is not None and a.get("percentage") != 0:
            continue
        a["percentage"] = int(blank_pct)
        a["assessment_mode"] = "blank_default"
        # Mark the result so the client can render it differently
        r["status"] = "blank_default"
        r["percentage"] = int(blank_pct)
        n_applied += 1
    return n_applied


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
    ai_unavailable = False
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
            # 502 = the underlying LLM service is unavailable (e.g. the Universal
            # LLM key balance/budget is exhausted). It's systemic — stop here so we
            # don't burn through the remaining chunks with the same failure, and
            # surface a clear, actionable message to the client.
            if he.status_code == 502:
                ai_unavailable = True
                break
            results.append({"option_id": oid, "factor_id": fid, "status": "error"}); continue

        pct, final_actual = _apply_assessment(factor, option, result)
        results.append({
            "option_id": oid, "factor_id": fid, "status": "done",
            "percentage": pct, "actual_value": final_actual,
        })

    # Default-fill any cell the AI flat-out couldn't score (status='error') so
    # one missing data-point doesn't silently drag the option's overall worth
    # to 0. Per-decision override > per-user preference > 5% global default.
    user_blank = await get_user_blank_default(user["user_id"])
    blank_pct = resolve_decision_blank_pct(decision, user_blank)
    # Allow a per-request override (the Step 7 "Blank cells default" knob)
    body_blank = body.get("blank_default_pct")
    if body_blank is not None:
        try:
            n = int(body_blank)
            if 0 <= n <= 100:
                blank_pct = n
        except (TypeError, ValueError):
            pass
    blanks_applied = _apply_blank_default(decision, results, blank_pct)

    if any(r["status"] == "done" for r in results) or blanks_applied:
        await db.decisions.update_one(
            {"id": decision_id, "user_id": user["user_id"]},
            {"$set": {
                "options": decision["options"],
                "factors": decision["factors"],
                "updated_at": datetime.now(timezone.utc),
            }},
        )
    return {"results": results, "out_of_credits": out_of_credits, "ai_unavailable": ai_unavailable,
            "blank_default_pct": blank_pct, "blanks_applied": blanks_applied}


@router.post("/decisions/{decision_id}/ai-assess-all-batched")
async def md_ai_assess_all_batched(
    decision_id: str, body: Dict[str, Any], user: dict = Depends(get_current_user),
):
    """Score EVERY requested cell using as FEW LLM calls as possible (~1 call per
    40 cells via core.ai_assess.batch_score_cells). This is the primary "AI
    Assess All" path — it keeps usage inside the free Gemini/Groq quotas instead
    of firing 1-2 calls per cell.

    Body: { cells: [{option_id, factor_id, actual_value?}], force_fill?: bool,
            allow_openai?: bool }   (allow_openai overrides the user's stored
            consent for THIS run, e.g. the in-the-moment "use OpenAI free" choice)
    Returns: { results: [...], out_of_credits, ai_unavailable }
    """
    from core.ai_assess import batch_score_cells

    decision = await db.decisions.find_one({"id": decision_id, "user_id": user["user_id"]}, {"_id": 0})
    if not decision:
        raise HTTPException(status_code=404, detail="Decision not found")

    cells = body.get("cells") or []
    if not isinstance(cells, list) or not cells:
        raise HTTPException(status_code=400, detail="No cells provided")

    allow_openai = body.get("allow_openai")  # None ⇒ use stored consent
    results, out_of_credits, ai_unavailable = await batch_score_cells(
        decision=decision, cells=cells, user_id=user["user_id"],
        force_fill=bool(body.get("force_fill")),
        allow_openai=(bool(allow_openai) if allow_openai is not None else None),
    )

    factors_by_id = {f["id"]: f for f in decision.get("factors", [])}
    options_by_id = {o["id"]: o for o in decision.get("options", [])}
    applied = []
    for r in results:
        if r.get("status") != "done":
            applied.append({k: r[k] for k in ("option_id", "factor_id", "status")})
            continue
        factor = factors_by_id.get(r["factor_id"]); option = options_by_id.get(r["option_id"])
        if not factor or not option:
            applied.append({"option_id": r["option_id"], "factor_id": r["factor_id"], "status": "error"})
            continue
        pct, final_actual = _apply_assessment(factor, option, r["result"])
        applied.append({"option_id": r["option_id"], "factor_id": r["factor_id"],
                        "status": "done", "percentage": pct, "actual_value": final_actual})

    if any(r["status"] == "done" for r in applied):
        await db.decisions.update_one(
            {"id": decision_id, "user_id": user["user_id"]},
            {"$set": {
                "options": decision["options"],
                "factors": decision["factors"],
                "updated_at": datetime.now(timezone.utc),
            }},
        )
    # Default-fill any AI-error cells (see _apply_blank_default for details).
    user_blank = await get_user_blank_default(user["user_id"])
    blank_pct = resolve_decision_blank_pct(decision, user_blank)
    body_blank = body.get("blank_default_pct")
    if body_blank is not None:
        try:
            n = int(body_blank)
            if 0 <= n <= 100:
                blank_pct = n
        except (TypeError, ValueError):
            pass
    blanks_applied = _apply_blank_default(decision, applied, blank_pct)
    if blanks_applied:
        await db.decisions.update_one(
            {"id": decision_id, "user_id": user["user_id"]},
            {"$set": {"options": decision["options"],
                      "updated_at": datetime.now(timezone.utc)}},
        )
    return {"results": applied, "out_of_credits": out_of_credits, "ai_unavailable": ai_unavailable,
            "blank_default_pct": blank_pct, "blanks_applied": blanks_applied}


# ── User-profile preference: default % to write for AI-blank cells ─────────
# Lives on the Decisions router because that's the only consumer today.
# Per-decision override = `decision.blank_default_pct`. Per-user default =
# this endpoint. Global fallback = 5% (constants.DEFAULT_BLANK_PCT).
from core.blank_default import set_user_blank_default  # noqa: E402


@router.get("/decisions/preferences/blank-default-pct")
async def get_blank_default_pct(user: dict = Depends(get_current_user)):
    pct = await get_user_blank_default(user["user_id"])
    return {"blank_default_pct": pct, "fallback": 5}


@router.put("/decisions/preferences/blank-default-pct")
async def set_blank_default_pct(body: Dict[str, Any], user: dict = Depends(get_current_user)):
    raw = body.get("blank_default_pct")
    try:
        pct = await set_user_blank_default(user["user_id"], int(raw))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="blank_default_pct must be an integer 0-100")
    return {"blank_default_pct": pct}
