"""Emotional Gatekeeper — Effective Outlets Advisor Routes

A prescriptive guide with 9 constructive emotional outlets that replace
destructive habits. Includes guided practices, audio affirmations, forgiveness
templates, practice logging, and AI-personalised recommendations.
"""

import uuid
import logging
from datetime import datetime, timezone
from typing import Optional, List
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException, Depends
from core.database import db
from routes.auth_routes import get_current_user

from .ai_engine import EMERGENT_LLM_KEY

logger = logging.getLogger(__name__)
router = APIRouter()


# ============================================================
# DATA: 9 Effective Outlets + Forgiveness Affirmations
# ============================================================

EFFECTIVE_OUTLETS = [
    {
        "id": "joint_exercise",
        "number": "1A",
        "name": "Joint Activation Exercise",
        "category": "physical",
        "relief_type": "Physical Relief",
        "duration": "5-10 mins",
        "icon": "fitness",
        "color": "#EF4444",
        "description": "Simple 5-10 minute physical exercise activating all joints — neck, shoulders, elbows, wrists, hips, knees, ankles.",
        "instructions": [
            "Stand straight with feet shoulder-width apart",
            "Start from top: Rotate neck gently — 5 times each direction",
            "Shoulder rotations — 10 times forward, 10 backward",
            "Elbow bends and rotations — 10 each arm",
            "Wrist circles — 10 times each",
            "Hip circles — 10 times each direction",
            "Knee bends (half squats) — 10 times",
            "Ankle rotations — 10 times each foot",
            "Finish with 5 deep breaths — inhale 4 sec, hold 4, exhale 6",
        ],
        "tip": "Focus on releasing tension from each joint. Imagine stress leaving with each rotation.",
    },
    {
        "id": "super_brain_yoga",
        "number": "1B",
        "name": "Super Brain Yoga (Thoppukaranam)",
        "category": "physical",
        "relief_type": "Physical Relief",
        "duration": "3-5 mins (14 reps)",
        "icon": "body",
        "color": "#F97316",
        "description": "Thoppukaranam — an ancient brain-body synchronisation exercise. Cross your arms to hold opposite earlobes and perform 14 squats.",
        "instructions": [
            "Stand facing East (morning) or North",
            "Cross your left arm over the right to reach the opposite earlobes",
            "Left hand holds right earlobe, right hand holds left earlobe",
            "Thumbs should be in front, fingers behind the earlobes",
            "Inhale as you go down into a squat",
            "Exhale as you come back up",
            "Repeat 14 times without stopping",
            "Release earlobes and stand still — feel the energy shift",
        ],
        "tip": "This activates both brain hemispheres. You may feel a clarity 'buzz' after completing all 14 reps.",
    },
    {
        "id": "sun_moon_connect",
        "number": "2A",
        "name": "Sun/Moon Heart Connection",
        "category": "energy",
        "relief_type": "Energy Gain",
        "duration": "5 mins minimum",
        "icon": "sunny",
        "color": "#F59E0B",
        "description": "Heart-fully connect to the Sun (morning & afternoon) or Moon (night) with gratitude for giving us life energy. Do this from a terrace or open area.",
        "instructions": [
            "Go to an open area — terrace, balcony, or garden",
            "Face the Sun (morning/afternoon) or Moon (night)",
            "Place both hands over your heart",
            "Close your eyes gently and take 3 deep breaths",
            "Visualise a warm golden (sun) or silver (moon) light entering your heart",
            "Speak silently: 'Thank you for the life energy you give me every day'",
            "Stay in this grateful state for at least 5 minutes",
            "Feel the warmth and energy filling your entire body",
            "End with 3 deep breaths and open your eyes slowly",
        ],
        "tip": "Morning sun connection is most powerful within the first hour of sunrise. Moon connection works best under a visible moon.",
    },
    {
        "id": "rock_salt_bath",
        "number": "2B",
        "name": "Rock Salt Head Bath",
        "category": "energy",
        "relief_type": "Energy Relief",
        "duration": "10-15 mins",
        "icon": "water",
        "color": "#06B6D4",
        "description": "A head bath with rock salt to cleanse accumulated negative energy from your aura and body.",
        "instructions": [
            "Dissolve 2-3 tablespoons of rock salt in a bucket of warm water",
            "You can also add a pinch of turmeric for additional purification",
            "Pour the water over your head and body during a bath",
            "As the water runs down, visualise all negative energy draining away",
            "Stay mindful — feel the heaviness leaving your body",
            "After the bath, stand still for a moment and feel the lightness",
            "Dry yourself and sit in silence for 2 minutes",
        ],
        "tip": "Especially effective after emotionally draining days, arguments, or visiting crowded/negative environments.",
    },
    {
        "id": "gibberish",
        "number": "3",
        "name": "Gibberish",
        "category": "mental",
        "relief_type": "Mental Relief",
        "duration": "5-10 mins",
        "icon": "chatbubbles",
        "color": "#8B5CF6",
        "description": "Speak nonsensical sounds loudly to release mental clutter. The mind cannot hold structured thoughts while producing random sounds.",
        "instructions": [
            "Find a private space where you won't be disturbed",
            "Set a timer for 5-10 minutes",
            "Start making random, nonsensical sounds — any language-like noise",
            "Move your body freely while doing this — shake hands, stomp feet",
            "Let out ALL frustration, confusion, and mental noise through these sounds",
            "Don't try to make sense — the point is non-sense",
            "When the timer ends, sit in complete silence for 2 minutes",
            "Notice the sudden mental clarity and stillness",
        ],
        "tip": "Osho's Gibberish Meditation technique. The contrast between chaos and silence afterwards creates profound mental clarity.",
    },
    {
        "id": "pillow_hitting",
        "number": "4",
        "name": "Pillow Hitting",
        "category": "physical",
        "relief_type": "Physical + Emotional Relief",
        "duration": "3-5 mins",
        "icon": "flash",
        "color": "#EC4899",
        "description": "Physically release pent-up anger and frustration by hitting a pillow or cushion. Safe, effective, and immediately cathartic.",
        "instructions": [
            "Take a large, firm pillow or cushion",
            "Kneel on the floor or bed in front of it",
            "Start hitting the pillow with both fists — alternate or together",
            "Let out sounds — shout, scream, growl if needed",
            "Don't hold back — this is your safe release",
            "Continue for 3-5 minutes or until you feel the intensity subside",
            "When done, hug the pillow gently and take 5 deep breaths",
            "Notice how the anger has transformed into calm",
        ],
        "tip": "This is one of the most effective immediate anger management techniques recommended by therapists worldwide.",
    },
    {
        "id": "release_technique",
        "number": "5",
        "name": "Release Technique",
        "category": "emotional",
        "relief_type": "Emotional Release",
        "duration": "2 mins",
        "icon": "arrow-undo-circle",
        "color": "#10B981",
        "description": "A powerful verbal release — repeat this affirmation for 2 minutes to clear emotional blocks. Use audio playback for guided practice.",
        "affirmation_text": "I release and let go of all the grievances, misfortunes, fears, doubts, delays, difficulties and desperations from my life — RIGHT NOW. Anything stopping that, I delete, destroy, un-create, de-story and cancel all of them RIGHT NOW.",
        "instructions": [
            "Find a quiet space and close your eyes",
            "Take 3 deep breaths to centre yourself",
            "Begin repeating the affirmation aloud or in your heart",
            "Feel each word — especially 'RIGHT NOW'",
            "Continue for 2 minutes without stopping",
            "After finishing, sit in silence and feel the lightness",
        ],
        "has_audio_play": True,
        "tip": "The power is in the emotional conviction. Mean every word. The more you feel it, the more it releases.",
    },
    {
        "id": "forgiveness_affirmations",
        "number": "6",
        "name": "Forgiveness Affirmations",
        "category": "spiritual",
        "relief_type": "Spiritual Healing",
        "duration": "5-10 mins per affirmation",
        "icon": "heart-half",
        "color": "#7C3AED",
        "description": "Structured forgiveness affirmations from Prana Violet Healing. 7 categories covering all relationships — friends, ex-partners, karmic cords, self, family, in-laws, and spouse.",
        "instructions": [
            "Choose the affirmation category that resonates with your current need",
            "Find a quiet, peaceful space",
            "Read the invocation and affirmation aloud with sincerity",
            "Repeat the forgiveness phrases 3 times as instructed",
            "Feel the release and lightness after each repetition",
            "End with gratitude",
        ],
        "has_affirmation_browser": True,
        "tip": "Courtesy: Prana Violet Healing (pranaviolethealing.com). Read daily for spouse; as required for others; lifelong for karmic cords.",
    },
    {
        "id": "sms_redirect",
        "number": "7",
        "name": "Personalized SMS (Stress Management Styles)",
        "category": "behavioral",
        "relief_type": "Behavioral Redirection",
        "duration": "Varies",
        "icon": "git-compare",
        "color": "#3B82F6",
        "description": "Redirects to your personalised Stress Management Styles from the Outlet Analyzer's AI-recommended constructive behaviours — to restore emotional balance.",
        "instructions": [
            "Review your Outlet Analyzer results",
            "AI has identified your destructive patterns and recommended replacements",
            "Follow the recommended constructive behaviours",
            "Track your progress in switching from destructive to constructive outlets",
        ],
        "is_redirect": True,
        "redirect_to": "outlet_analyzer",
        "tip": "This connects your self-awareness from the Outlet Analyzer to actionable constructive habits.",
    },
    {
        "id": "gratitude_journaling",
        "number": "8",
        "name": "Gratitude Journaling",
        "category": "mental",
        "relief_type": "Mental + Emotional Rebalance",
        "duration": "5-10 mins",
        "icon": "book",
        "color": "#059669",
        "description": "Write 3-5 things you're grateful for right now. Gratitude rewires the brain away from negativity and towards appreciation.",
        "instructions": [
            "Take a moment to pause and breathe",
            "Think of 3-5 things you're genuinely grateful for TODAY",
            "Write each one down — be specific, not generic",
            "For each item, write WHY you're grateful for it",
            "Read them aloud once after writing",
            "Close your eyes and feel the warmth of gratitude",
        ],
        "has_journal_entry": True,
        "tip": "Research shows 21 days of daily gratitude journaling physically rewires neural pathways towards positivity.",
    },
    {
        "id": "hoorecon_o_pono",
        "number": "9",
        "name": "HOORECON-o-Pono",
        "category": "spiritual",
        "relief_type": "Spiritual + Emotional Healing",
        "duration": "2 mins",
        "icon": "prism",
        "color": "#6366F1",
        "description": "An enhanced version of Ho'oponopono. Repeat this healing affirmation for 2 minutes to cleanse emotional blocks and restore inner peace.",
        "affirmation_text": "I'm extremely Sorry, Please forgive me, I love you, I thank you, I forgive you, I trust you, I cherish your presence in my life so much.",
        "instructions": [
            "Close your eyes and bring to mind the person or situation",
            "Place your hand on your heart",
            "Begin repeating the affirmation slowly and meaningfully",
            "Feel each phrase: Sorry, Forgive, Love, Thank, Forgive, Trust, Cherish",
            "Continue for 2 minutes — let tears flow if they come",
            "End with 3 deep breaths and sit in silence",
        ],
        "has_audio_play": True,
        "tip": "Ho'oponopono is an ancient Hawaiian practice of reconciliation and forgiveness. HOORECON-o-Pono adds Trust and Cherish for deeper healing.",
    },
    {
        "id": "emotional_reception",
        "number": "10",
        "name": "Emotional Reception",
        "category": "emotional",
        "relief_type": "Inner Stability (EQ Builder)",
        "duration": "5 mins",
        "icon": "leaf",
        "color": "#0EA5E9",
        "description": "Just Be in the Here and Now — a guided 5-minute practice to simply BE with your pain without doing anything. This builds your Emotional Quotient (EQ) dramatically.",
        "instructions": [
            "Acknowledge what burden you are carrying right now",
            "Accept the inevitability of this moment — do not resist",
            "Follow the 7 DON'Ts for 5 minutes",
            "Simply BE with the feeling — no action, no escape, no analysis",
            "After 5 minutes, notice the shift in your inner stability",
        ],
        "has_guided_flow": True,
        "tip": "Nobody on earth can change the reality of this very moment. If we're against this moment, we're against the whole Universe. Be wise and realize this inevitability.",
    },
]


FORGIVENESS_AFFIRMATIONS = [
    {
        "id": "friends_colleagues",
        "title": "Friends, Classmates, Colleagues, Neighbours & Others",
        "icon": "people",
        "frequency": "Read as required",
        "sections": [
            {"type": "invocation", "text": "To the Supreme God, Divine Father, Divine Mother, To my Higher Soul, To (Name of person) Higher Soul, To all our Spiritual Guides and Helpers, To all the Healing Angels, To the Great Karmic Board,"},
            {"type": "declaration", "text": "I am that I am"},
            {"type": "seeking", "text": "(Name of person) please forgive me for all my wrongdoings and deep hurt which I may have committed knowingly and unknowingly to you and your family."},
            {"type": "granting", "text": "I am forgiving you for all your wrongdoings committed towards me and my family."},
            {"type": "blessing", "text": "Let God's love and blessing be with you always (×3)\nPlease go in peace (×3)\nLet there be peace and harmony between us always (×3)"},
            {"type": "gratitude", "text": "God, Thank you, Thank you, Thank you."},
        ],
    },
    {
        "id": "ex_partners",
        "title": "Ex-Partners, Ex-Spouse",
        "icon": "heart-dislike",
        "frequency": "Read lifelong or as instructed",
        "sections": [
            {"type": "invocation", "text": "To the Supreme God, Divine Father, Divine Mother, To my Higher Soul, To (Name of person) Higher Soul, To all the Spiritual Guides, Helpers and Teachers, To all the Healing Angels, To the Great Karmic Board,"},
            {"type": "declaration", "text": "I am that I am"},
            {"type": "acknowledgement", "text": "God thank you for bringing us together. Thank you for balancing our karma. I am accepting this divine direction and plan."},
            {"type": "seeking", "text": "(Name) I am asking for forgiveness for all my wrongdoings and deep hurt which I may have committed knowingly and unknowingly to you and your family in my past lives and present life."},
            {"type": "granting", "text": "I am forgiving you for all your wrongdoings committed towards me and my family.\nI am forgiving and forgetting (×3)"},
            {"type": "blessing", "text": "Let there be peace and harmony between us always (×3)\nLet God's love and blessing be with you and your family always (×3)\nPlease go in peace (×3)"},
            {"type": "manifestation", "text": "I am consciously accepting this manifest, manifest, manifest."},
            {"type": "gratitude", "text": "God, Thank you, Thank you, Thank you."},
        ],
    },
    {
        "id": "karmic_cords",
        "title": "Karmic Cords, Black/White Magic, Curses",
        "icon": "link",
        "frequency": "Read lifelong or as instructed",
        "note": "If done to the family, the whole family needs to read.",
        "sections": [
            {"type": "invocation", "text": "To the Supreme God, Divine Father, Divine Mother, To my Higher Soul, To (Name of person) Higher Soul, To all the Spiritual Guides, Helpers and Teachers, To all the Healing Angels, To the Great Karmic Board,"},
            {"type": "declaration", "text": "I am that I am"},
            {"type": "acknowledgement", "text": "God thank you for bringing us together. Thank you for allowing us to balance our karma. I am accepting this divine direction and plan."},
            {"type": "seeking", "text": "I am asking for forgiveness for all my wrongdoings and deep hurt which I may have committed knowingly and unknowingly to you and your family in my past lives or present life. This has caused you to take some very wrong action towards me and my family. We ask for forgiveness again."},
            {"type": "granting", "text": "I am forgiving you for all your wrong actions done towards me and my family.\nI am forgiving and forgetting (×3)"},
            {"type": "blessing", "text": "Let there be peace and harmony between us always.\nLet God's light, love and blessing be with you and your family always.\nPlease go in peace (×3)"},
            {"type": "manifestation", "text": "I am consciously accepting this manifest, manifest, manifest."},
            {"type": "gratitude", "text": "God, Thank you, Thank you, Thank you."},
        ],
    },
    {
        "id": "forgiving_yourself",
        "title": "Forgiving Yourself",
        "icon": "person",
        "frequency": "Read lifelong or as instructed",
        "sections": [
            {"type": "invocation", "text": "To the Supreme God, Divine Father, Divine Mother, To my Higher Soul, To my Spiritual Guides, To all the Spiritual Guides, To my Spiritual Helpers, To all the Spiritual Helpers, To all the Healing Angels, To the Great Karmic Board,"},
            {"type": "declaration", "text": "I am that I am"},
            {"type": "seeking", "text": "I am humbly invoking for Divine Forgiveness for all my wrongdoings committed knowingly or unknowingly in my past lives and present life."},
            {"type": "granting", "text": "I am forgiving everyone for all their wrongdoings towards me and my family.\nPlease cast out all fear and doubts in me."},
            {"type": "release", "text": "I am forgiving and forgetting.\nI am forgiving and forgetting.\nI am forgiving and forgetting."},
            {"type": "manifestation", "text": "I am consciously accepting this manifest, manifest, manifest."},
            {"type": "gratitude", "text": "God, Thank you, Thank you, Thank you."},
        ],
    },
    {
        "id": "family_members",
        "title": "Family Members (Parents, Siblings, Children)",
        "icon": "home",
        "frequency": "Read as required",
        "sections": [
            {"type": "invocation", "text": "To the Supreme God, Divine Father, Divine Mother, To my Higher Soul, To my (Family member names) Higher Soul, To our Spiritual Guides and Helpers, To all the Healing Angels, To the Great Karmic Board,"},
            {"type": "acknowledgement", "text": "God thank you for bringing us together. I am accepting this divine direction and plan."},
            {"type": "seeking", "text": "(Family Member names) please forgive me for all my wrongdoings and deep hurt which I may have committed knowingly and unknowingly to you in my past lives and present life."},
            {"type": "granting", "text": "I am humbly invoking for forgiveness for all your wrongdoings committed towards me."},
            {"type": "blessing", "text": "Let God's love and blessing be with you always (×3)\nLet there be peace and harmony between us always (×3)"},
            {"type": "gratitude", "text": "God, Thank you, Thank you, Thank you."},
        ],
    },
    {
        "id": "in_laws",
        "title": "In-laws (Father/Mother/Brother/Sister-in-law)",
        "icon": "people-circle",
        "frequency": "Read as required",
        "sections": [
            {"type": "invocation", "text": "To the Supreme God, Divine Father, Divine Mother, To my Higher Soul, To my (In-law's Family member names) Higher Soul, To our Spiritual Guides and Helpers, To all the Healing Angels, To the Great Karmic Board,"},
            {"type": "acknowledgement", "text": "God thank you for bringing us together. I am accepting this divine direction and plan."},
            {"type": "seeking", "text": "(In-law's Family Member names) please forgive me for all my wrongdoings and deep hurt which I may have committed knowingly and unknowingly to you in my past lives and present life."},
            {"type": "granting", "text": "I am humbly invoking for forgiveness for all your wrongdoings committed towards me and my family."},
            {"type": "blessing", "text": "Let God's love and blessing be with you always (×3)\nPlease go in peace (×3)\nLet there be peace and harmony between us always (×3)"},
            {"type": "gratitude", "text": "God, Thank you, Thank you, Thank you."},
        ],
    },
    {
        "id": "spouse",
        "title": "Forgiving Husband / Wife",
        "icon": "heart",
        "frequency": "Read daily",
        "sections": [
            {"type": "invocation", "text": "To the Supreme God, Divine Father, Divine Mother, To my Higher Soul, To my (Husband/Wife Name) Higher Soul, To all our Spiritual Guides and Teachers, To all our Spiritual Helpers, To all the Healing Angels, To the Great Karmic Board,"},
            {"type": "declaration", "text": "I am that I am"},
            {"type": "acknowledgement", "text": "God thank you for bringing us together. Thank you for balancing our karma. I am accepting this divine direction and plan."},
            {"type": "seeking", "text": "I am asking for forgiveness for all my wrongdoings committed knowingly or unknowingly to you and your family."},
            {"type": "granting", "text": "I am forgiving you for all the wrongdoings and deep hurt."},
            {"type": "blessing", "text": "I am blessing my (Husband/Wife name) with divine love, divine kindness and divine compassion.\nLet the divine light protect and guide them always in God's direction.\nLet the God's light blaze and transmute all negative energies and discords from them.\nMy (Husband/Wife) is God's perfection made manifest in Body, Mind and Soul."},
            {"type": "gratitude", "text": "God, Thank you, Thank you, Thank you."},
        ],
    },
]


# ============================================================
# MODELS
# ============================================================

class PracticeLogEntry(BaseModel):
    outlet_id: str
    duration_seconds: Optional[int] = None
    notes: Optional[str] = None
    affirmation_category: Optional[str] = None  # for forgiveness
    gratitude_entries: Optional[List[str]] = None  # for gratitude journaling


class GratitudeEntry(BaseModel):
    entries: List[str]
    session_id: Optional[str] = None


# ============================================================
# ROUTES
# ============================================================

@router.get("/advisor/outlets")
async def get_effective_outlets(user: dict = Depends(get_current_user)):
    """Get all 9 effective outlet techniques with full instructions."""
    return {
        "outlets": EFFECTIVE_OUTLETS,
        "forgiveness_affirmations": FORGIVENESS_AFFIRMATIONS,
        "total_outlets": len(EFFECTIVE_OUTLETS),
        "categories": ["physical", "energy", "mental", "emotional", "spiritual", "behavioral"],
    }


@router.post("/advisor/practice-log")
async def log_practice(data: PracticeLogEntry, user: dict = Depends(get_current_user)):
    """Log a practice session for any of the 9 outlets."""
    valid_ids = [o["id"] for o in EFFECTIVE_OUTLETS]
    if data.outlet_id not in valid_ids:
        raise HTTPException(400, f"Invalid outlet_id. Valid: {valid_ids}")

    now = datetime.now(timezone.utc).isoformat()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    log = {
        "id": f"PL-{uuid.uuid4().hex[:8].upper()}",
        "user_id": user["user_id"],
        "outlet_id": data.outlet_id,
        "duration_seconds": data.duration_seconds,
        "notes": data.notes,
        "affirmation_category": data.affirmation_category,
        "gratitude_entries": data.gratitude_entries,
        "date": today,
        "created_at": now,
    }

    await db.advisor_practice_logs.insert_one(log)

    # Update streak
    yesterday = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    existing_today = await db.advisor_practice_logs.count_documents({
        "user_id": user["user_id"], "date": today,
    })

    log.pop("_id", None)
    return {
        "logged": log,
        "practices_today": existing_today,
    }


@router.get("/advisor/my-practices")
async def get_my_practices(
    days: int = 30,
    user: dict = Depends(get_current_user),
):
    """Get user's practice history and stats."""
    from datetime import timedelta
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    logs = await db.advisor_practice_logs.find(
        {"user_id": user["user_id"], "created_at": {"$gte": since}},
        {"_id": 0},
    ).sort("created_at", -1).to_list(500)

    # Compute stats
    outlet_counts: dict = {}
    practice_dates: set = set()
    for log in logs:
        oid = log.get("outlet_id", "unknown")
        outlet_counts[oid] = outlet_counts.get(oid, 0) + 1
        practice_dates.add(log.get("date", ""))

    # Calculate streak
    streak = 0
    check_date = datetime.now(timezone.utc).date()
    while True:
        ds = check_date.strftime("%Y-%m-%d")
        if ds in practice_dates:
            streak += 1
            check_date -= timedelta(days=1)
        else:
            break

    return {
        "logs": logs,
        "stats": {
            "total_practices": len(logs),
            "unique_days": len(practice_dates),
            "streak": streak,
            "outlet_counts": outlet_counts,
            "most_practiced": max(outlet_counts, key=outlet_counts.get) if outlet_counts else None,
        },
    }


@router.post("/advisor/gratitude")
async def save_gratitude_journal(data: GratitudeEntry, user: dict = Depends(get_current_user)):
    """Save a gratitude journal entry and log the practice."""
    if not data.entries or len(data.entries) == 0:
        raise HTTPException(400, "Provide at least one gratitude entry.")

    now = datetime.now(timezone.utc).isoformat()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    doc = {
        "id": f"GJ-{uuid.uuid4().hex[:8].upper()}",
        "user_id": user["user_id"],
        "entries": data.entries,
        "session_id": data.session_id,
        "date": today,
        "created_at": now,
    }

    await db.gratitude_journals.insert_one(doc)

    # Also log as practice
    practice = {
        "id": f"PL-{uuid.uuid4().hex[:8].upper()}",
        "user_id": user["user_id"],
        "outlet_id": "gratitude_journaling",
        "gratitude_entries": data.entries,
        "date": today,
        "created_at": now,
    }
    await db.advisor_practice_logs.insert_one(practice)

    doc.pop("_id", None)
    return {"saved": doc, "entries_count": len(data.entries)}


@router.get("/advisor/gratitude-history")
async def get_gratitude_history(days: int = 30, user: dict = Depends(get_current_user)):
    """Get gratitude journal history."""
    from datetime import timedelta
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    journals = await db.gratitude_journals.find(
        {"user_id": user["user_id"], "created_at": {"$gte": since}},
        {"_id": 0},
    ).sort("created_at", -1).to_list(100)

    return {"journals": journals, "total": len(journals)}


@router.get("/advisor/sms-recommendations")
async def get_sms_recommendations(user: dict = Depends(get_current_user)):
    """Get personalised SMS (Stress Management Styles) from the user's latest Outlet Analyzer results."""
    # Find the user's latest outlet analysis
    latest = await db.outlet_reflections.find_one(
        {"user_id": user["user_id"]},
        {"_id": 0},
        sort=[("created_at", -1)],
    )

    if not latest or not latest.get("ai_analysis"):
        return {
            "has_analysis": False,
            "message": "Complete the Outlet Analyzer first to get personalised recommendations.",
            "recommendations": [],
        }

    analysis = latest["ai_analysis"]
    recommendations = []
    if isinstance(analysis, dict):
        for item in analysis.get("analysis", []):
            if item.get("recommended_alternative"):
                recommendations.append({
                    "destructive_habit": item.get("strategy"),
                    "nature": item.get("nature"),
                    "assessment": item.get("assessment"),
                    "alternative": item.get("recommended_alternative"),
                    "why": item.get("why_alternative"),
                })

    return {
        "has_analysis": True,
        "session_id": latest.get("session_id"),
        "recommendations": recommendations,
        "overall_pattern": analysis.get("overall_pattern") if isinstance(analysis, dict) else None,
        "top_recommendations": analysis.get("top_recommendations") if isinstance(analysis, dict) else None,
    }


# ============================================================
# EMOTIONAL RECEPTION — Guided Flow Endpoint
# ============================================================

class EmotionalReceptionLog(BaseModel):
    burden: str  # What burden they're carrying
    wants_settled: bool = True
    accepted_donts: bool = True
    chose_to_be: bool  # True = "Yes I can wait 5 mins", False = "No I can't"
    completed_5_min: Optional[bool] = None  # Did they complete the timer?
    intensity_before: Optional[int] = None  # 1-10
    intensity_after: Optional[int] = None  # 1-10
    reflection: Optional[str] = None  # Post-practice reflection


@router.post("/advisor/emotional-reception/log")
async def log_emotional_reception(data: EmotionalReceptionLog, user: dict = Depends(get_current_user)):
    """Log a complete Emotional Reception session with all guided flow data."""
    now = datetime.now(timezone.utc).isoformat()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    doc = {
        "id": f"ER-{uuid.uuid4().hex[:8].upper()}",
        "user_id": user["user_id"],
        "burden": data.burden,
        "wants_settled": data.wants_settled,
        "accepted_donts": data.accepted_donts,
        "chose_to_be": data.chose_to_be,
        "completed_5_min": data.completed_5_min,
        "intensity_before": data.intensity_before,
        "intensity_after": data.intensity_after,
        "reflection": data.reflection,
        "date": today,
        "created_at": now,
    }

    await db.emotional_reception_logs.insert_one(doc)

    # Also log as advisor practice
    practice = {
        "id": f"PL-{uuid.uuid4().hex[:8].upper()}",
        "user_id": user["user_id"],
        "outlet_id": "emotional_reception",
        "duration_seconds": 300 if data.completed_5_min else 0,
        "notes": f"Burden: {data.burden}" + (f" | Reflection: {data.reflection}" if data.reflection else ""),
        "date": today,
        "created_at": now,
    }
    await db.advisor_practice_logs.insert_one(practice)

    # Compute EQ growth
    completed_count = await db.emotional_reception_logs.count_documents({
        "user_id": user["user_id"], "completed_5_min": True,
    })
    total_count = await db.emotional_reception_logs.count_documents({
        "user_id": user["user_id"],
    })

    doc.pop("_id", None)
    return {
        "logged": doc,
        "eq_stats": {
            "total_attempts": total_count,
            "successful_completions": completed_count,
            "eq_score": min(10, round(completed_count * 0.5 + 1, 1)),  # Simple EQ growth metric
        },
    }


@router.get("/advisor/emotional-reception/history")
async def get_emotional_reception_history(user: dict = Depends(get_current_user)):
    """Get Emotional Reception practice history with EQ growth."""
    logs = await db.emotional_reception_logs.find(
        {"user_id": user["user_id"]},
        {"_id": 0},
    ).sort("created_at", -1).to_list(100)

    completed = sum(1 for l in logs if l.get("completed_5_min"))
    total = len(logs)

    return {
        "logs": logs,
        "eq_stats": {
            "total_attempts": total,
            "successful_completions": completed,
            "completion_rate": round(completed / total * 100, 1) if total > 0 else 0,
            "eq_score": min(10, round(completed * 0.5 + 1, 1)),
        },
    }
