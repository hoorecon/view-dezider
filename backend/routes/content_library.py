"""Content Library — Admin CMS for verbatim coaching scripts.

Lets a non-engineer paste/edit module narratives (initially Tenses & Feels)
from the UI instead of touching `src/data/*.ts` files.

Collections
-----------
content_blocks
    {
      _id, id (uuid), module ("tenses_feels"|...), key ("clinging", "anger", ...),
      locale ("en"|"hi"|"ta"|...),
      title, short,
      fields: {  # free-form schema per module
         narrative_paraphrase, power_statement, instruction_for_user,
         resolution_quote, verbatim_script, healing_feeling,
         color, polarity, tense, category,
      },
      order, active, version, created_at, updated_at, updated_by
    }

Endpoints
---------
GET  /api/content-library/modules                       (public)  list modules + counts
GET  /api/content-library?module=&locale=&active=       (admin)  paginated list
GET  /api/content-library/render/{module}?locale=       (public)  merged emotion list
POST /api/content-library                               (admin)  create
PUT  /api/content-library/{id}                          (admin)  update
DELETE /api/content-library/{id}                        (admin)  soft-delete (active=False)
POST /api/content-library/seed/tenses_feels             (admin)  one-shot idempotent seed
"""
from __future__ import annotations
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, Request
from core.database import db
from core.auth import get_current_user, get_user_role, ADMIN_ROLES

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/content-library", tags=["Content Library — Admin CMS"])

SUPPORTED_MODULES = ["tenses_feels", "goals_feels", "emotional_gatekeeper",
                     "conflict_breaker", "solution_finder", "tepfi", "values"]
DEFAULT_LOCALES = ["en", "hi", "ta", "te", "mr", "kn"]


def _require_admin(user: dict):
    if get_user_role(user) not in ADMIN_ROLES:
        raise HTTPException(403, "Admin access required")


def _now():
    return datetime.now(timezone.utc)


# ============================================================
# DEFAULT SEED — Tenses & Feels (mirrors src/data/tensesFeelsContent.ts)
# Pre-populates the CMS on first /seed/tenses_feels call so admins have
# a starting point instead of an empty form.
# ============================================================
TENSES_FEELS_DEFAULT_SEED: List[Dict[str, Any]] = [
    # PAST
    {"key": "clinging", "title": "Clinging", "short": "Can't let go of a bad past experience",
     "tense": "past", "polarity": "negative", "category": "none", "color": "#DC2626",
     "narrative_paraphrase": "A bad experience from the past — recent or long ago — that you cannot still forget.",
     "power_statement": "Irrespective of my reactions, the reality is fixed. I accept the unchangeable.",
     "instruction_for_user": "Bring up one bad experience from your past you have not let go yet. Close your eyes and feel it for 30 seconds.",
     "resolution_quote": "Accept the Unchangeable and choose the response most appropriate to the situation — instead of reacting with whatever you feel like.",
     "healing_feeling": "gratefulness", "order": 1},
    {"key": "longing", "title": "Longing", "short": "Still longing for a good past you've lost",
     "tense": "past", "polarity": "positive", "category": "none", "color": "#F97316",
     "narrative_paraphrase": "A good experience from the past you cannot still forget — and are still longing for.",
     "power_statement": "Anything can be taken away at any time, in any way. I'm grateful it lasted as long as it did.",
     "instruction_for_user": "Bring up one good experience from your past for which you are still longing. Close your eyes for 30 seconds.",
     "resolution_quote": "Life and everything we experience is temporary. Thank life for blessing you with that beautiful experience instead of mourning its absence.",
     "healing_feeling": "gratefulness", "order": 2},
    # FUTURE
    {"key": "fear", "title": "Fear", "short": "Fearful something negative may happen",
     "tense": "future", "polarity": "negative", "category": "none", "color": "#7C3AED",
     "narrative_paraphrase": "Fear about the future that something negative may happen.",
     "power_statement": "As per Nature's Law, fear attracts what I don't want. I acknowledge it and take constructive action.",
     "instruction_for_user": "Bring up one possible bad experience that can happen in your future about which you are fearful. Close your eyes for 30 seconds.",
     "resolution_quote": "Acknowledge the Fear without resistance and take 'Consistently Constructive' actions with Complete Conviction (CCCC). If you must imagine, IMAGINE POSITIVELY.",
     "healing_feeling": "faith", "order": 3},
    {"key": "anxiety", "title": "Anxiety / Desperation", "short": "Desperate for a positive future",
     "tense": "future", "polarity": "positive", "category": "none", "color": "#8B5CF6",
     "narrative_paraphrase": "Anxiety or desperation about the future that some positive thing must happen.",
     "power_statement": "As per Nature's Law, anxiety chases away what I desperately want. I acknowledge it and act with faith.",
     "instruction_for_user": "Bring up one possible good experience that you desperately want in your future. Close your eyes for 30 seconds.",
     "resolution_quote": "Acknowledge the Anxiety without resistance and take 'Consistently Constructive' actions with Complete Conviction (CCCC). When you imagine, IMAGINE POSITIVELY.",
     "healing_feeling": "faith", "order": 4},
    # PRESENT · Self · Emotional
    {"key": "anger", "title": "Anger", "short": "You see others as the cause",
     "tense": "present", "polarity": "negative", "category": "self_emotional", "color": "#EF4444",
     "narrative_paraphrase": "Anger arises when you perceive other person or situation as the reason for your disappointment or failure.",
     "power_statement": "Even if it wasn't my fault, I take 100% responsibility for the lesson — that's where my power lives.",
     "instruction_for_user": "Bring up one person you are so angry with right now. Close your eyes and feel it for 30 seconds.",
     "resolution_quote": "Assume 100% responsibility (just for self-empowerment) and find the precautionary step you could have taken. Transform anger into intense commitment to apply that life lesson.",
     "healing_feeling": "happily_active", "order": 5},
    {"key": "sadness", "title": "Sadness", "short": "You see yourself as the cause",
     "tense": "present", "polarity": "negative", "category": "self_emotional", "color": "#3B82F6",
     "narrative_paraphrase": "Sadness arises when you perceive yourself as the reason for your disappointment or failure — hidden anger on your own self.",
     "power_statement": "I forgive myself for any ignorance or incapability. The lesson is the gift.",
     "instruction_for_user": "Bring up one problem that is making you sad. Close your eyes for 30 seconds.",
     "resolution_quote": "Find the precautionary step that could have avoided this. Transform sadness into intense commitment to apply that life lesson. Self-forgiveness heals.",
     "healing_feeling": "happily_active", "order": 6},
    # PRESENT · Self · Mental
    {"key": "over_cautious", "title": "Over-Cautiousness / Urgency (Stress)",
     "short": "Restless to get from where you are to where you want to be",
     "tense": "present", "polarity": "negative", "category": "self_mental", "color": "#F59E0B",
     "narrative_paraphrase": "You are at Point A but want to be at Point B, and you are restless and impatient about the journey. That's 'Responsibly Urgent' overdone — stress.",
     "power_statement": "I am happily active in the present — that's where Point B actually approaches me from.",
     "instruction_for_user": "Notice one area where stress is pushing you to skip the present. Sit with it for 30 seconds.",
     "resolution_quote": "Be Happily Active in the Present — that is the bridge from Point A to Point B.",
     "healing_feeling": "happily_active", "order": 7},
    {"key": "over_careless", "title": "Over-Carelessness / Complacency", "short": "Boredom and least-bothered-ness",
     "tense": "present", "polarity": "negative", "category": "self_mental", "color": "#CA8A04",
     "narrative_paraphrase": "Opposite of stress — complacency WITHOUT responsibility. Simply careless and least bothered.",
     "power_statement": "I choose engagement with responsibility — that's real contentment, not numbness.",
     "instruction_for_user": "Notice one area you have been ignoring or dismissing. Sit with it for 30 seconds.",
     "resolution_quote": "True complacency requires responsibility to protect what you have accomplished. Engage with the present.",
     "healing_feeling": "happily_active", "order": 8},
    # PRESENT · Others (yours)
    {"key": "jealousy", "title": "Jealousy on Others", "short": "Pain when on-par/below others surpass you",
     "tense": "present", "polarity": "negative", "category": "others_yours", "color": "#16A34A",
     "narrative_paraphrase": "Pain when others whom you consider on-par or below you excel in an area where you lack capability, resources, or success.",
     "power_statement": "Their success is proof it is possible. I focus on my own next step.",
     "instruction_for_user": "Bring up one person who triggers jealousy. Close your eyes for 30 seconds.",
     "resolution_quote": "Convert the comparison into inspiration. Find the specific capability or resource you can build next.",
     "healing_feeling": "happily_active", "order": 9},
    {"key": "disgraceful", "title": "Treating Others Disgracefully",
     "short": "Urge to belittle someone below your self-identity",
     "tense": "present", "polarity": "negative", "category": "others_yours", "color": "#0EA5E9",
     "narrative_paraphrase": "Subtle pain of not being able to accept someone you consider below you to deal equally with you in a common situation.",
     "power_statement": "Every person carries a story I have not seen. I choose dignity for them — and for myself.",
     "instruction_for_user": "Recall one moment you belittled someone (even subtly). Close your eyes for 30 seconds.",
     "resolution_quote": "Self-identity that needs others to be 'below' is fragile. True confidence treats every person with equal dignity.",
     "healing_feeling": "happily_active", "order": 10},
    # PRESENT · Others (theirs)
    {"key": "aggression", "title": "Aggression on Enemies", "short": "Rage when you think of your enemies",
     "tense": "present", "polarity": "negative", "category": "others_theirs", "color": "#991B1B",
     "narrative_paraphrase": "Accumulated or intensified state of Anger that explodes into rage whenever you think of your enemies.",
     "power_statement": "I redirect the rage energy into building, not destroying.",
     "instruction_for_user": "Bring up one enemy. Close your eyes for 30 seconds.",
     "resolution_quote": "Aggression is just intensified anger. The same anger-resolution practice applies — extract the lesson, take constructive action.",
     "healing_feeling": "happily_active", "order": 11},
    {"key": "heartbroken", "title": "Heartbroken on Betrayals", "short": "Depression when you think of cheaters",
     "tense": "present", "polarity": "negative", "category": "others_theirs", "color": "#7E22CE",
     "narrative_paraphrase": "Accumulated or intensified state of Sadness — explodes into depression at times when you think of those who betrayed you.",
     "power_statement": "My heart heals. The betrayal taught me discernment.",
     "instruction_for_user": "Bring up one person who betrayed you. Close your eyes for 30 seconds.",
     "resolution_quote": "Heartbreak is intensified sadness. Apply the sadness-resolution practice with self-forgiveness for trusting blindly.",
     "healing_feeling": "happily_active", "order": 12},
]

# Field schema metadata for the admin UI (renders correct controls per module)
MODULE_SCHEMA: Dict[str, Dict[str, Any]] = {
    "tenses_feels": {
        "label": "Tenses & Feels",
        "fields": [
            {"key": "title", "label": "Emotion Label", "type": "text", "required": True},
            {"key": "short", "label": "1-line definition", "type": "text"},
            {"key": "tense", "label": "Tense", "type": "select", "options": ["past", "future", "present"]},
            {"key": "polarity", "label": "Polarity", "type": "select", "options": ["negative", "positive"]},
            {"key": "category", "label": "Category", "type": "select",
             "options": ["self_emotional", "self_mental", "others_yours", "others_theirs", "none"]},
            {"key": "color", "label": "Color (hex)", "type": "text"},
            {"key": "healing_feeling", "label": "Healing Feeling", "type": "select",
             "options": ["gratefulness", "faith", "happily_active"]},
            {"key": "narrative_paraphrase", "label": "Narrative Paraphrase", "type": "textarea"},
            {"key": "power_statement", "label": "Power Statement", "type": "textarea"},
            {"key": "instruction_for_user", "label": "Instruction for User", "type": "textarea"},
            {"key": "resolution_quote", "label": "Resolution Quote", "type": "textarea"},
            {"key": "verbatim_script", "label": "Verbatim Coach Script (full)", "type": "textarea_large"},
        ],
    },
    # Generic schema for other modules until they get bespoke ones
    "_default": {
        "label": "Generic",
        "fields": [
            {"key": "title", "label": "Title", "type": "text", "required": True},
            {"key": "body", "label": "Body", "type": "textarea_large"},
            {"key": "verbatim_script", "label": "Verbatim Script", "type": "textarea_large"},
        ],
    },
}


# ============================================================
# Schema discovery
# ============================================================
@router.get("/modules")
async def list_modules():
    """Public — list supported modules + counts."""
    out = []
    for m in SUPPORTED_MODULES:
        c = await db.content_blocks.count_documents({"module": m, "active": True})
        out.append({
            "module": m,
            "label": (MODULE_SCHEMA.get(m) or MODULE_SCHEMA["_default"])["label"],
            "blocks": c,
        })
    return {"modules": out, "locales": DEFAULT_LOCALES}


@router.get("/schema/{module}")
async def get_schema(module: str):
    """Return the field schema for a module so admin UI can render dynamic forms."""
    return {
        "module": module,
        "schema": MODULE_SCHEMA.get(module) or MODULE_SCHEMA["_default"],
    }


# ============================================================
# CRUD
# ============================================================
@router.get("")
async def list_blocks(
    module: Optional[str] = None,
    locale: Optional[str] = None,
    active: Optional[bool] = None,
    user: dict = Depends(get_current_user),
):
    _require_admin(user)
    q: Dict[str, Any] = {}
    if module:
        q["module"] = module
    if locale:
        q["locale"] = locale
    if active is not None:
        q["active"] = active
    rows = await db.content_blocks.find(q, {"_id": 0}).sort(
        [("module", 1), ("locale", 1), ("order", 1), ("key", 1)]
    ).to_list(2000)
    return {"items": rows, "count": len(rows)}


@router.post("")
async def create_block(request: Request, user: dict = Depends(get_current_user)):
    _require_admin(user)
    body = await request.json()
    module = body.get("module")
    key = body.get("key")
    locale = (body.get("locale") or "en").lower()
    if not module or not key:
        raise HTTPException(400, "module and key are required")
    if module not in SUPPORTED_MODULES:
        raise HTTPException(400, f"Unsupported module. Choose from: {SUPPORTED_MODULES}")
    # Reject duplicates (module, key, locale) — use PUT to update
    exists = await db.content_blocks.find_one({"module": module, "key": key, "locale": locale})
    if exists:
        raise HTTPException(409, "A block with this (module,key,locale) already exists. Use PUT.")
    doc = {
        "id": str(uuid.uuid4()),
        "module": module,
        "key": key,
        "locale": locale,
        "title": body.get("title", ""),
        "short": body.get("short", ""),
        "fields": body.get("fields") or {k: v for k, v in body.items()
                                          if k not in ("module", "key", "locale", "id", "title", "short")},
        "order": int(body.get("order", 100)),
        "active": bool(body.get("active", True)),
        "version": 1,
        "created_at": _now(), "updated_at": _now(),
        "updated_by": user.get("email") or user["user_id"],
    }
    await db.content_blocks.insert_one(doc.copy())
    doc.pop("_id", None)
    return doc


@router.put("/{block_id}")
async def update_block(block_id: str, request: Request, user: dict = Depends(get_current_user)):
    _require_admin(user)
    body = await request.json()
    existing = await db.content_blocks.find_one({"id": block_id})
    if not existing:
        raise HTTPException(404, "Block not found")
    update = {"updated_at": _now(), "updated_by": user.get("email") or user["user_id"]}
    for k in ("title", "short", "order", "active", "locale"):
        if k in body:
            update[k] = body[k]
    if "fields" in body and isinstance(body["fields"], dict):
        update["fields"] = body["fields"]
    update["version"] = (existing.get("version") or 1) + 1
    await db.content_blocks.update_one({"id": block_id}, {"$set": update})
    row = await db.content_blocks.find_one({"id": block_id}, {"_id": 0})
    return row


@router.delete("/{block_id}")
async def delete_block(block_id: str, user: dict = Depends(get_current_user)):
    _require_admin(user)
    res = await db.content_blocks.update_one(
        {"id": block_id},
        {"$set": {"active": False, "updated_at": _now(),
                  "updated_by": user.get("email") or user["user_id"]}},
    )
    if res.matched_count == 0:
        raise HTTPException(404, "Block not found")
    return {"ok": True, "deactivated_id": block_id}


# ============================================================
# RENDER (public) — used by mobile clients to fetch resolved content
# ============================================================
@router.get("/render/{module}")
async def render_module(module: str, locale: str = "en"):
    """Public — return all active blocks for a module, locale-aware with English fallback."""
    locale = locale.lower()
    rows = await db.content_blocks.find(
        {"module": module, "active": True}, {"_id": 0}
    ).sort([("order", 1), ("key", 1)]).to_list(2000)
    # Group by key, prefer requested locale then en
    by_key: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        loc = (r.get("locale") or "en").lower()
        k = r["key"]
        cur = by_key.get(k)
        if not cur:
            by_key[k] = r
            continue
        cur_loc = (cur.get("locale") or "en").lower()
        if loc == locale and cur_loc != locale:
            by_key[k] = r
        elif loc == "en" and cur_loc != locale and cur_loc != "en":
            by_key[k] = r
    blocks = sorted(by_key.values(), key=lambda x: (x.get("order", 999), x.get("key", "")))
    return {"module": module, "locale": locale, "blocks": blocks, "count": len(blocks)}


# ============================================================
# Idempotent seed for tenses_feels
# ============================================================
@router.post("/seed/tenses_feels")
async def seed_tenses_feels(force: bool = False, user: dict = Depends(get_current_user)):
    """Idempotently seed the 12 tenses_feels emotions in English.
    If `force=true`, overwrite existing blocks.
    """
    _require_admin(user)
    inserted = 0
    updated = 0
    for entry in TENSES_FEELS_DEFAULT_SEED:
        key = entry["key"]
        existing = await db.content_blocks.find_one(
            {"module": "tenses_feels", "key": key, "locale": "en"}
        )
        doc_fields = {k: v for k, v in entry.items() if k not in ("key", "title", "short", "order")}
        common = {
            "module": "tenses_feels",
            "key": key,
            "locale": "en",
            "title": entry["title"],
            "short": entry.get("short", ""),
            "order": entry["order"],
            "fields": doc_fields,
            "active": True,
            "updated_at": _now(),
            "updated_by": user.get("email") or user["user_id"],
        }
        if existing and not force:
            continue
        if existing and force:
            common["version"] = (existing.get("version") or 1) + 1
            await db.content_blocks.update_one({"id": existing["id"]}, {"$set": common})
            updated += 1
        else:
            doc = {**common, "id": str(uuid.uuid4()), "version": 1, "created_at": _now()}
            await db.content_blocks.insert_one(doc.copy())
            inserted += 1
    return {"ok": True, "inserted": inserted, "updated": updated,
            "total_seed_entries": len(TENSES_FEELS_DEFAULT_SEED)}


# ============================================================
# Index ensure (called from server.py boot)
# ============================================================
async def ensure_indexes():
    try:
        await db.content_blocks.create_index(
            [("module", 1), ("key", 1), ("locale", 1)], unique=True
        )
        await db.content_blocks.create_index([("module", 1), ("active", 1), ("order", 1)])
        await db.content_blocks.create_index([("id", 1)], unique=True)
        logger.info("Content Library indexes ensured")
    except Exception as e:
        logger.warning(f"Content Library index creation skipped: {e}")
