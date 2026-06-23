"""Emotional Gatekeeper — Constants"""

# ============================================================
# LIFE AREAS (10 Key Areas of Life + Spirituality)
# ============================================================
LIFE_AREAS = [
    "holistic_health", "knowledge_skills", "emotional_relationships",
    "finance", "assets", "career",
    "personal_dreams", "hobbies_entertainment",
    "social_image", "social_contributions", "spirituality",
]

LIFE_AREA_LABELS = {
    # Labels MUST match the Central Catalog L0 names from
    # frontend/src/constants/lifeAreas.ts. Do NOT add parentheticals,
    # marketing copy, or rename anything here — drift causes the AIM /
    # Outlet UIs to show different words than the rest of Jelcos.ai.
    "holistic_health": "Holistic Health",
    "knowledge_skills": "Knowledge & Skills",
    "emotional_relationships": "Relationships",
    "finance": "Finance",
    "assets": "Assets",
    "career": "Career",
    "personal_dreams": "Personal Dreams Fulfillment",
    "hobbies_entertainment": "Hobbies & Entertainment",
    "social_image": "Social Image & Influence",
    "social_contributions": "Social Contributions",
    "spirituality": "Spirituality & Religion",
}

# ============================================================
# TRAP CONSTANTS
# ============================================================
TRAP_STAGES = ["landscaping", "linking", "looping"]

TRAP_CATEGORIES = [
    "career", "business", "relationship", "money", "family",
    "health", "self_worth", "spirituality", "other",
]

LANDSCAPING_PATTERNS = [
    "mistakes", "risks", "rejection", "loss", "failure",
    "betrayal", "delay", "uncertainty",
]

EXTERNAL_TRIGGERS = [
    "date", "person", "place", "event", "money", "action",
    "message", "silence", "work_situation", "relationship_situation", "other",
]

INTERNAL_TRIGGERS = [
    "thought", "memory", "emotion", "body_sensation", "dream",
    "imagination", "past_incident", "future_fear", "other",
]

# ============================================================
# LOOP CONSTANTS
# ============================================================
LOOP_METHODS = [
    {"id": "i_dont_know", "name": "I Don't Know", "description": "Accept uncertainty. Don't label good or bad yet."},
    {"id": "all_is_well", "name": "All Is Well", "description": "Trust life's goodness. This can work out."},
    {"id": "both_good_bad", "name": "Both Good and Bad", "description": "See duality. Every situation has both aspects."},
    {"id": "this_too_shall_pass", "name": "This Too Shall Pass", "description": "Recognize impermanence. Nothing is permanent."},
]

# ============================================================
# LIMITATION CONSTANTS
# ============================================================
LIMITATION_CATEGORIES = [
    {"id": "past_self", "name": "Past Experience of Self", "description": "Old failures define present capability."},
    {"id": "past_others", "name": "Past Experience of Others", "description": "Others' past shapes your decisions through their conditioning."},
    {"id": "external_inputs", "name": "External Inputs", "description": "Social media, news, ads, incomplete info mislead conclusions."},
    {"id": "fear_unknown", "name": "Fear of Unknown", "description": "Unknown ≠ difficult ≠ impossible ≠ impossible forever."},
]

EXTERNAL_INPUT_SOURCES = [
    "social_media", "news", "advertisement", "casual_conversation",
    "expert_opinion", "family", "friend", "competitor", "market_noise", "other",
]

# ============================================================
# EMOTIONAL OUTLET ANALYZER CONSTANTS
# ============================================================
OUTLET_FREQUENCIES = [
    {"id": "often", "label": "Often (6-7/week)", "value": 7},
    {"id": "sometimes", "label": "Sometimes (3-5/week)", "value": 4},
    {"id": "rarely", "label": "Rarely (1-2/week)", "value": 1},
    {"id": "not_at_all", "label": "Not at all (0)", "value": 0},
    {"id": "prefer_not_say", "label": "Prefer Not to Say", "value": -1},
]

# Nature: P=Physical, M=Mental, E=Emotional, En=Energy
OUTLET_NATURES = ["physical", "mental", "emotional", "energy"]

# 40 statements — 10 per Outlet Group (nature). Each group mixes healthy
# (default_constructive=True) and unhealthy (default_constructive=False) habits.
# Statements are shown MIXED (shuffled, no category headers) on the frontend;
# the nature is only used for color-coding and the % group breakdown.
COPING_STRATEGIES = [
    # ---------- PHYSICAL (10) ----------
    {"id": "swimming_sports", "name": "Swimming / Dancing / Sports", "nature": "physical", "default_constructive": True},
    {"id": "physical_exercise", "name": "Physical Exercises / Gym Workout", "nature": "physical", "default_constructive": True},
    {"id": "yoga_stretching", "name": "Yoga Asanas / Stretching", "nature": "physical", "default_constructive": True},
    {"id": "nap_sleeping", "name": "A Short Nap / Adequate Sleep", "nature": "physical", "default_constructive": True},
    {"id": "head_bath_salt", "name": "Taking a Head Bath with Rock Salt", "nature": "physical", "default_constructive": True},
    {"id": "sex", "name": "Sex / Physical Intimacy", "nature": "physical", "default_constructive": True},
    {"id": "binge_eating", "name": "Binge Eating / Junk Food", "nature": "physical", "default_constructive": False},
    {"id": "smoking_vaping", "name": "Smoking / Vaping", "nature": "physical", "default_constructive": False},
    {"id": "excessive_alcohol", "name": "Excessive Alcohol", "nature": "physical", "default_constructive": False},
    {"id": "oversleeping_avoid", "name": "Oversleeping to Avoid Things", "nature": "physical", "default_constructive": False},

    # ---------- MENTAL (10) ----------
    {"id": "reading_podcasts", "name": "Reading Books / Educational Podcasts", "nature": "mental", "default_constructive": True},
    {"id": "speak_expert", "name": "Speaking to an Expert about your Challenge", "nature": "mental", "default_constructive": True},
    {"id": "attending_webinars", "name": "Attending Webinars / Courses", "nature": "mental", "default_constructive": True},
    {"id": "guiding_others", "name": "Guiding Others from your Experience", "nature": "mental", "default_constructive": True},
    {"id": "journaling_planning", "name": "Journaling your Thoughts / Planning", "nature": "mental", "default_constructive": True},
    {"id": "watching_news", "name": "Watching the Live News Obsessively", "nature": "mental", "default_constructive": False},
    {"id": "social_media", "name": "Doomscrolling Social Media", "nature": "mental", "default_constructive": False},
    {"id": "overthinking", "name": "Overthinking / Analysis Paralysis", "nature": "mental", "default_constructive": False},
    {"id": "binge_watching", "name": "Binge-watching to Numb the Mind", "nature": "mental", "default_constructive": False},
    {"id": "gossiping", "name": "Gossiping / Complaining", "nature": "mental", "default_constructive": False},

    # ---------- EMOTIONAL (10) ----------
    {"id": "speak_friends", "name": "Speaking to your Best Friends", "nature": "emotional", "default_constructive": True},
    {"id": "hobbies", "name": "Pursuing your Favorite Hobbies", "nature": "emotional", "default_constructive": True},
    {"id": "listening_music", "name": "Listening to Uplifting Music", "nature": "emotional", "default_constructive": True},
    {"id": "movies", "name": "Watching Movies", "nature": "emotional", "default_constructive": True},
    {"id": "writing_burning", "name": "Writing a Letter and tearing/burning it", "nature": "emotional", "default_constructive": True},
    {"id": "helping_family", "name": "Helping Family with Household Activities", "nature": "emotional", "default_constructive": True},
    {"id": "crying_out", "name": "Crying it Out to Release", "nature": "emotional", "default_constructive": True},
    {"id": "suppressing_feelings", "name": "Suppressing / Bottling up Feelings", "nature": "emotional", "default_constructive": False},
    {"id": "lashing_out", "name": "Lashing Out / Venting Anger on Others", "nature": "emotional", "default_constructive": False},
    {"id": "comfort_shopping", "name": "Emotional Eating / Comfort Shopping", "nature": "emotional", "default_constructive": False},

    # ---------- ENERGY (10) ----------
    {"id": "meditation_breathwork", "name": "Meditation / Pranayama (Breathwork)", "nature": "energy", "default_constructive": True},
    {"id": "letter_divine", "name": "Writing/Speaking a Letter to the Life Source / Universe / God", "nature": "energy", "default_constructive": True},
    {"id": "nature_time", "name": "Unplug — Time in Nature / Looking at the Sky", "nature": "energy", "default_constructive": True},
    {"id": "chanting_prayer", "name": "Chanting / Prayer", "nature": "energy", "default_constructive": True},
    {"id": "gratitude_practice", "name": "Gratitude Practice", "nature": "energy", "default_constructive": True},
    {"id": "energy_arguments", "name": "Energy-draining Arguments / Conflicts", "nature": "energy", "default_constructive": False},
    {"id": "restless_multitask", "name": "Constant Multitasking / Restlessness", "nature": "energy", "default_constructive": False},
    {"id": "caffeine_dependence", "name": "Caffeine / Energy-drink Dependence", "nature": "energy", "default_constructive": False},
    {"id": "late_night_screen", "name": "Late-night Screen Stimulation", "nature": "energy", "default_constructive": False},
    {"id": "procrastination", "name": "Avoidance / Procrastination", "nature": "energy", "default_constructive": False},

    {"id": "other", "name": "Others (Please Specify)", "nature": "other", "default_constructive": None},
]

# ============================================================
# AIM (Addictions & Irritations Manager) CONSTANTS
# ============================================================
AIM_OCCURRENCE_OPTIONS = [
    "any_day", "weekdays", "weekends", "specific_days",
    "morning", "afternoon", "evening", "night",
    "under_stress", "under_boredom", "after_conflict",
    "social_situations", "alone_time", "other",
]

SESSION_TYPES = ["trap", "loop", "limitation", "outlet", "aim", "integrated", "eft"]

# ============================================================
# EFT TAPPING FOR STRESS RELIEF
# ============================================================
# Built-in defaults. Admin can override any of these via app_config
# {key: "eft_config"} from the Admin → EFT Tapping config screen.
EFT_DEFAULTS = {
    "enabled": True,
    "title": "EFT Tapping for Stress Relief",
    "description": "A gentle guided tapping practice to reduce emotional intensity and return to inner calm.",
    # Affirmation templates. "{input}" is replaced with the user's emotion or problem text.
    # Emotion-type uses the "feel" phrasing; problem-type drops "feel".
    "affirmation_template_emotion": "Even though I feel {input}, I deeply and completely love and accept myself.",
    "affirmation_template_problem": "Even though {input}, I deeply and completely love and accept myself.",
    "alt_affirmation_template_emotion": "Even though I feel {input}, I choose to feel calm and at peace.",
    "alt_affirmation_template_problem": "Even though {input}, I choose to feel calm and at peace.",
    "tapping_instructions": "Use two fingertips of one hand. Tap gently, not forcefully. Tap around 5–7 times on each point. Breathe slowly while tapping. You can speak the reminder phrase aloud or silently.",
    # 9 tapping points in the EXACT order required by the SRS.
    "tapping_points": [
        {"id": "karate_chop", "name": "Karate Chop Point", "instruction": "Tap the fleshy side of your hand (below the little finger). Repeat your setup affirmation 3 times.", "is_setup": True},
        {"id": "eyebrow", "name": "Eyebrow Point", "instruction": "Tap gently on the beginning of your eyebrow, near the bridge of your nose."},
        {"id": "side_of_eye", "name": "Side of Eye", "instruction": "Tap gently on the bone at the outer corner of your eye."},
        {"id": "under_eye", "name": "Under Eye", "instruction": "Tap gently on the bone just under your eye."},
        {"id": "under_nose", "name": "Under Nose", "instruction": "Tap gently on the area between your nose and upper lip."},
        {"id": "chin", "name": "Chin Point", "instruction": "Tap gently on the crease between your lower lip and chin."},
        {"id": "collarbone", "name": "Collarbone Point", "instruction": "Tap gently just below the hard ridge of your collarbone."},
        {"id": "under_arm", "name": "Under Arm", "instruction": "Tap gently about four inches below your armpit."},
        {"id": "top_of_head", "name": "Top of Head", "instruction": "Tap gently on the crown of your head."},
    ],
    "diagram_image_url": "/api/static/eft/default_tapping_points.png",
    "video_url": "https://vimeo.com/1184450823/11b05769d7?fl=pl&fe=cm",
    "disclaimer": "This practice is for emotional self-regulation and stress relief. It is not a substitute for medical, psychological, or emergency care. If you feel unsafe, overwhelmed, or have thoughts of self-harm, please contact a qualified professional or emergency support immediately.",
    # Words that trigger the gentle safety support message (case-insensitive substring match).
    "safety_keywords": [
        "suicide", "suicidal", "kill myself", "end my life", "self harm", "self-harm",
        "hurt myself", "cutting myself", "want to die", "no reason to live",
        "panic attack", "abuse", "abused", "being beaten", "in danger", "overdose",
    ],
    "safety_message": "This sounds serious and you deserve immediate support. EFT may help you calm down, but please also reach out to a trusted person, mental health professional, or emergency support near you.",
}

SESSION_STATUSES = ["draft", "in_progress", "completed", "resolved"]
COMMITMENT_TYPES = ["immediate", "7_day", "30_day"]
COMMITMENT_STATUSES = ["pending", "completed", "missed"]
