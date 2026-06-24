"""
Goal Manifestation Module — CAB-FAME 7-Stage Wish Fulfillment Process
C=Cosmic Consciousness, A=Awakening, B=Believing, F=Feeling, A=Actions, M=Manifestation, E=Effect
"""
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request, Depends
from core.database import db
from core.auth import get_current_user, require_admin

router = APIRouter(prefix="/goal-manifestation", tags=["Goal Manifestation"])

# ═══════════════════════════════════════════════════════════════
# CAB-FAME 7 STAGES (Complete from PDF)
# ═══════════════════════════════════════════════════════════════

CABFAME_STAGES = [
    {
        "stage_number": 1,
        "letter": "C",
        "name": "Cosmic Consciousness",
        "chakra": "Sahasrara",
        "color": "#7C3AED",
        "icon": "sunny",
        "summary": "Connect to Absolute Stillness through Meditation",
        "steps": [
            {
                "id": "1.1",
                "title": "Invoke the blessings of all your Gurus",
                "instruction": "Chant the following mantra:",
                "content": "GururBrahma GururVishnu GururDevo Maheshwaraha\nGuru Saakshaat ParaBrahma Tasmai Sri Gurave Namaha",
                "link": "https://isha.sadhguru.org/in/en/blog/article/mystic-chants-guru-paduka-stotram",
                "link_label": "Listen: Guru Paduka Stotram",
            },
            {
                "id": "1.2",
                "title": "Affirmation #1",
                "instruction": "Repeat 2 times, or more until you feel it.",
                "content": "How come I could instantly release and let go of all the grievances, misfortunes, fears, doubts and desperations from my life right now?",
                "followup": "Anything stopping that, I delete, destroy, uncreate and de-story all of that",
            },
            {
                "id": "1.3",
                "title": "Affirmation #2",
                "instruction": "Repeat 2 times, or more until you feel it.",
                "content": "I choose minute by minute miracles and all-around-abundance all the time, from now on!",
                "followup": "Anything stopping that, I delete, destroy, uncreate and de-story all of that",
            },
            {
                "id": "1.4",
                "title": "Energy Cleansing",
                "instruction": "Using Sandalwood / Agarbatti, perform Anti-clockwise rotation 3 times.",
                "content": "Set intention: \"Remove ALL the energies from my Environment, Aura & Chakras obstructing me in accomplishing << My Wish >>\"",
            },
            {
                "id": "1.5",
                "title": "Energizing",
                "instruction": "Using Sandalwood / Agarbatti, perform Clockwise rotation 3 times.",
                "content": "Set intention: \"Let Golden Energies flow and shower with ALL the energies on my Environment, Aura & Chakras supporting me in accomplishing << My Wish >>\"",
            },
            {
                "id": "1.6",
                "title": "Connect to Absolute Stillness through Meditation",
                "instruction": "Access and follow the meditation:",
                "link": "https://www.youtube.com/watch?v=hs0rnDhOU-I",
                "link_label": "Play: Stillness Meditation (YouTube)",
            },
            {
                "id": "1.7",
                "title": "Attain the Tantric Bliss of Ultimate Oneness",
                "instruction": "Chant until you feel, and feel until you become that being. Rejoice in the state of Oneness:",
                "content": "Sthree Yoni Purusha Linga Spandhana\nVishwa Yoni Vishwa Linga Bandhana",
            },
        ],
    },
    {
        "stage_number": 2,
        "letter": "A",
        "name": "Awakening of New Possibility / Desire",
        "chakra": "Ajna",
        "color": "#3B82F6",
        "icon": "eye",
        "summary": "Awaken the desire from Cosmic Consciousness",
        "steps": [
            {
                "id": "2.1",
                "title": "Connect to your highest potential",
                "instruction": "Chant:",
                "content": "Irrespective of my past, I have the power to create my future the way I want, from now onwards!",
            },
            {
                "id": "2.2",
                "title": "Design the possibility",
                "instruction": "Look at the area/aspect of life you want to design and create it as a possibility.",
                "content": "WHO I AM is the Possibility of << ___ >>\nE.g., Leadership & Support",
                "has_input": True,
                "input_label": "My Possibility",
            },
            {
                "id": "2.3",
                "title": "Declare and enroll",
                "instruction": "Declare that possibility to relevant people who are directly or indirectly involved. Enroll them into your vision with inclusive growth for all.",
            },
        ],
    },
    {
        "stage_number": 3,
        "letter": "B",
        "name": "Believing it 100% from Mind",
        "chakra": "Vishuddi",
        "color": "#0EA5E9",
        "icon": "bulb",
        "summary": "Believe more powerfully than subconscious fears and doubts",
        "steps": [
            {
                "id": "3.1",
                "title": "Affirmation #1 (repeat as needed)",
                "content": "How come I could instantly release and let go of all the grievances, misfortunes, fears, doubts and desperations from my life right now?\n\nAnything stopping that, I delete, destroy, uncreate and de-story all of that",
            },
            {
                "id": "3.2",
                "title": "Affirmation #2 (repeat as needed)",
                "content": "I choose minute by minute miracles and all-around-abundance all the time, from now on!\n\nAnything stopping that, I delete, destroy, uncreate and de-story all of that",
            },
            {
                "id": "3.3",
                "title": "Energy Cleansing",
                "instruction": "Anti-clockwise rotation 3 times with Sandalwood/Agarbatti.",
                "content": "Remove ALL obstructing energies from Environment, Aura & Chakras for << My Goal >>",
            },
            {
                "id": "3.4",
                "title": "Energizing",
                "instruction": "Clockwise rotation 3 times.",
                "content": "Let Golden Energies flow supporting << My Goal >>",
            },
            {
                "id": "3.5",
                "title": "Express Gratitude in Advance",
                "instruction": "Recall your goal and express gratitude to God with faith:",
                "content": "Thank you, Thank you, Thank you!!",
            },
            {
                "id": "3.6",
                "title": "Visualize the Manifested Goal",
                "instruction": "Keep chanting 'Thank you' and additionally add Visualization of your manifested goal, until you start feeling it.",
            },
        ],
    },
    {
        "stage_number": 4,
        "letter": "F",
        "name": "Feeling it Experientially",
        "chakra": "Anahata",
        "color": "#10B981",
        "icon": "heart",
        "summary": "Vibrate at the frequency of your desired outcome",
        "audio_url": "https://customer-assets.emergentagent.com/job_a7a2d7ec-9ce2-470b-8ff8-d26638aa4277/artifacts/4evzh8fa_KalphaVriksha%20Meditation.mp3",
        "audio_title": "KalphaVriksha Meditation — Feeling as if Already Achieved",
        "steps": [
            {
                "id": "4.1",
                "title": "Submerge into Feeling with all 5 Senses",
                "instruction": "Engage See, Hear, Touch, Smell & Taste — until you become the State of Being when the goal was already manifested.",
            },
            {
                "id": "4.2",
                "title": "Experience as part of Ultimate Oneness",
                "instruction": "Experience this new state of being (energy of your goal) as part of your state of Ultimate Oneness, so that it's part of you already!",
            },
            {
                "id": "4.3",
                "title": "Rejoice in Oneness with Goal's Energy",
                "instruction": "Play the KalphaVriksha Meditation and rejoice in this state as long as you feel needed.",
                "is_meditation": True,
            },
            {
                "id": "4.4",
                "title": "Conclude with Gratitude to Guru",
                "content": "GururBrahma GururVishnu GururDevo Maheshwaraha\nGuru Saakshaat ParaBrahma Tasmai Sri Gurave Namaha",
                "link": "https://isha.sadhguru.org/in/en/blog/article/mystic-chants-guru-paduka-stotram",
                "link_label": "Listen: Guru Paduka Stotram",
            },
        ],
    },
    {
        "stage_number": 5,
        "letter": "A",
        "name": "Actions from State of Oneness",
        "chakra": "Manipuraka",
        "color": "#F59E0B",
        "icon": "flash",
        "summary": "Take aligned actions from this energy state",
        "steps": [
            {
                "id": "5.1",
                "title": "Take One Advanced Action",
                "instruction": "From this state of Oneness, immediately take any one action you would do AFTER the goal actually manifested.",
                "has_input": True,
                "input_label": "My Advanced Action",
            },
            {
                "id": "5.2",
                "title": "Ensure Balanced Lifestyle",
                "instruction": "Ensure alignment with all areas of life and overall destiny for your highest good and highest happiness.",
            },
            {
                "id": "5.3",
                "title": "Eliminate Negative Action Habits",
                "instruction": "Identify habits against this goal. Remove their 7 aspects: Attractiveness, Ease, Faster Availability, Social Influence, Reward to Inner Child, Positive Intention, Strong Why to quit.",
                "has_input": True,
                "input_label": "Negative Habits to Eliminate",
            },
            {
                "id": "5.4",
                "title": "Add Positive Action Habits",
                "instruction": "Identify habits most supportive to this goal. Ensure their 7 aspects: Attractiveness, Ease, Faster Availability, Social Influence, Reward to Inner Child, Positive Intention, Strong Why to continue.",
                "has_input": True,
                "input_label": "Positive Habits to Add",
            },
            {
                "id": "5.5",
                "title": "Set Up Conducive Environment",
                "instruction": "Ensure required People, Finance and Infrastructure for faster Manifestation.",
            },
            {
                "id": "5.6",
                "title": "Plan CCCC Actions",
                "instruction": "Plan and take Immediate practical Action Items as CCCC (Consistently Constructive Actions, with Complete Conviction).",
                "has_input": True,
                "input_label": "My CCCC Action Items",
            },
        ],
    },
    {
        "stage_number": 6,
        "letter": "M",
        "name": "Manifestation",
        "chakra": "Swadhisthana",
        "color": "#EC4899",
        "icon": "sparkles",
        "summary": "Patience, faith, and continuous aligned action",
        "steps": [
            {
                "id": "6.1",
                "title": "Accept and Be Patient",
                "content": "The only way to go out is, go through. Accept this moment and be patient. When any being yearns, existence answers; he cannot go unanswered. Patience from your side and time from existence's side are needed!",
            },
            {
                "id": "6.2",
                "title": "Be in Gratitude",
                "content": "Be in Gratitude for Past, Present & Future. Take all Actions & Interactions with Love and 100% Faith on God to land you on your Desired Destiny.",
            },
            {
                "id": "6.3",
                "title": "Beware of Breath, Thoughts & Body",
                "content": "Be pure awareness above your BMW — Body, Mind and World.",
            },
            {
                "id": "6.4",
                "title": "Own the Destiny",
                "instruction": "Own with 100% Responsibility. Keep reviewing progress, assessing preparedness, revising strategy, competence, resources and action plan until reaching your goal.",
                "has_input": True,
                "input_label": "Progress Review Notes",
            },
            {
                "id": "6.5",
                "title": "Keep Chanting",
                "content": "During CCCC and Positive Action Habits chant: \"I'm so lucky and 100% on-time from now on!\"",
            },
        ],
    },
    {
        "stage_number": 7,
        "letter": "E",
        "name": "Effect on External Environment",
        "chakra": "Moolaadhaara",
        "color": "#EF4444",
        "icon": "globe",
        "summary": "After Manifestation — celebrate and restore balance",
        "steps": [
            {"id": "7.1", "title": "Contentment", "content": "Embrace contentment with what has been achieved."},
            {"id": "7.2", "title": "Celebration", "content": "Celebrate the manifestation with joy and gratitude."},
            {"id": "7.3", "title": "Restore Life Balance", "content": "Restore the overall life balance across all areas."},
            {"id": "7.4", "title": "Wholehearted Gratitude", "content": "Express wholehearted Gratitude for whatever was already blessed into your life!"},
        ],
    },
]


_CABFAME_CFG_KEY = "cabfame_framework"


async def _effective_framework() -> list:
    """Admin override (db.app_config) if present, else the built-in default."""
    doc = await db.app_config.find_one({"key": _CABFAME_CFG_KEY}, {"_id": 0})
    if doc and isinstance(doc.get("stages"), list) and doc["stages"]:
        return doc["stages"]
    return CABFAME_STAGES


@router.get("/framework")
async def get_cabfame_framework():
    """Return the complete CAB-FAME 7-stage framework (admin-overridable)."""
    stages = await _effective_framework()
    return {"stages": stages, "total_stages": len(stages)}


@router.get("/admin/framework")
async def admin_get_framework(_: dict = Depends(require_admin)):
    doc = await db.app_config.find_one({"key": _CABFAME_CFG_KEY}, {"_id": 0})
    is_override = bool(doc and isinstance(doc.get("stages"), list) and doc["stages"])
    return {"stages": await _effective_framework(), "is_override": is_override}


@router.put("/admin/framework")
async def admin_put_framework(request: Request, _: dict = Depends(require_admin)):
    body = await request.json()
    stages = body.get("stages")
    if not isinstance(stages, list) or not stages:
        raise HTTPException(status_code=400, detail="stages must be a non-empty list")
    for st in stages:
        if not isinstance(st, dict) or "stage_number" not in st or "name" not in st or "steps" not in st:
            raise HTTPException(status_code=400, detail="each stage needs stage_number, name and steps")
        if not isinstance(st.get("steps"), list):
            raise HTTPException(status_code=400, detail=f"stage {st.get('stage_number')} steps must be a list")
    await db.app_config.update_one(
        {"key": _CABFAME_CFG_KEY},
        {"$set": {"key": _CABFAME_CFG_KEY, "stages": stages,
                  "updated_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True,
    )
    return {"saved": True, "total_stages": len(stages)}


@router.post("/admin/framework/reset")
async def admin_reset_framework(_: dict = Depends(require_admin)):
    await db.app_config.delete_one({"key": _CABFAME_CFG_KEY})
    return {"reset": True, "stages": CABFAME_STAGES, "total_stages": len(CABFAME_STAGES)}


# ═══════════════════════════════════════════════════════════════
# CRUD — Manifestation Journeys
# ═══════════════════════════════════════════════════════════════

@router.post("/journeys")
async def create_journey(request: Request, user: dict = Depends(get_current_user)):
    body = await request.json()
    journey_id = f"MAN-{uuid.uuid4().hex[:10].upper()}"
    now = datetime.now(timezone.utc).isoformat()

    doc = {
        "journey_id": journey_id,
        "user_id": user["user_id"],
        "org_id": user.get("org_id"),
        "wish": body.get("wish", ""),
        "life_area": body.get("life_area", ""),
        "current_stage": body.get("current_stage", 1),
        "stage_inputs": body.get("stage_inputs", {}),
        # stage_inputs: { "2.2": "Leadership", "5.1": "Called the investor", ... }
        "status": body.get("status", "active"),
        "notes": body.get("notes", ""),
        "created_at": now,
        "updated_at": now,
    }
    await db.manifestation_journeys.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.get("/journeys")
async def list_journeys(request: Request, user: dict = Depends(get_current_user)):
    query = {"user_id": user["user_id"]}
    params = request.query_params
    if params.get("status"):
        query["status"] = params["status"]
    docs = await db.manifestation_journeys.find(query, {"_id": 0}).sort("created_at", -1).to_list(100)
    return docs


@router.get("/journeys/{journey_id}")
async def get_journey(journey_id: str, user: dict = Depends(get_current_user)):
    doc = await db.manifestation_journeys.find_one(
        {"journey_id": journey_id, "user_id": user["user_id"]}, {"_id": 0}
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Journey not found")
    return doc


@router.put("/journeys/{journey_id}")
async def update_journey(journey_id: str, request: Request, user: dict = Depends(get_current_user)):
    body = await request.json()
    now = datetime.now(timezone.utc).isoformat()
    update = {"updated_at": now}
    for f in ["wish", "life_area", "current_stage", "stage_inputs", "status", "notes"]:
        if f in body:
            update[f] = body[f]
    result = await db.manifestation_journeys.update_one(
        {"journey_id": journey_id, "user_id": user["user_id"]}, {"$set": update}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Journey not found")
    doc = await db.manifestation_journeys.find_one({"journey_id": journey_id}, {"_id": 0})
    return doc


@router.delete("/journeys/{journey_id}")
async def delete_journey(journey_id: str, user: dict = Depends(get_current_user)):
    result = await db.manifestation_journeys.delete_one(
        {"journey_id": journey_id, "user_id": user["user_id"]}
    )
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Journey not found")
    return {"deleted": True}


@router.get("/dashboard")
async def manifestation_dashboard(user: dict = Depends(get_current_user)):
    journeys = await db.manifestation_journeys.find(
        {"user_id": user["user_id"]}, {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    active = [j for j in journeys if j.get("status") == "active"]
    manifested = [j for j in journeys if j.get("status") == "manifested"]
    return {
        "total_journeys": len(journeys),
        "active": len(active),
        "manifested": len(manifested),
        "recent": journeys[:5],
    }
