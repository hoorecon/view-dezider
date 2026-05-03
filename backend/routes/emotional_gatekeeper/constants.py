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
    "holistic_health": "Holistic Health (Physical, Mental, Emotional)",
    "knowledge_skills": "Knowledge & Skills",
    "emotional_relationships": "Emotional Relationships",
    "finance": "Finance",
    "assets": "Assets (Moveable, Immovable & Intellectual)",
    "career": "Career",
    "personal_dreams": "Personal Dreams Fulfillment",
    "hobbies_entertainment": "Hobbies & Entertainment",
    "social_image": "Social Image & Influence",
    "social_contributions": "Social Contributions",
    "spirituality": "Spirituality",
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

COPING_STRATEGIES = [
    {"id": "watching_news", "name": "Watching the Live News", "nature": "mental", "default_constructive": False},
    {"id": "swimming_sports", "name": "Swimming / Dancing / Sports", "nature": "physical", "default_constructive": True},
    {"id": "movies", "name": "Movies", "nature": "emotional", "default_constructive": True},
    {"id": "speak_friends", "name": "Speak to your Best Friends", "nature": "emotional", "default_constructive": True},
    {"id": "letter_divine", "name": "Heartfully Speaking/Writing Letter to the Life Source / Universe / God", "nature": "energy", "default_constructive": True},
    {"id": "hobbies", "name": "Pursuing your Favorite Hobbies", "nature": "emotional", "default_constructive": True},
    {"id": "yoga_meditation", "name": "Yoga / Meditation", "nature": "energy", "default_constructive": True},
    {"id": "head_bath_salt", "name": "Taking Head Bath with Rock Salt", "nature": "physical", "default_constructive": True},
    {"id": "nature_time", "name": "Unplug yourself — spend time in Nature / looking at the Sky", "nature": "energy", "default_constructive": True},
    {"id": "writing_burning", "name": "Writing to Yourself / Divine / Concerned Person and tear/burn the paper", "nature": "emotional", "default_constructive": True},
    {"id": "sex", "name": "Sex", "nature": "physical", "default_constructive": True},
    {"id": "nap_sleeping", "name": "Nap / Sleeping", "nature": "physical", "default_constructive": True},
    {"id": "physical_exercise", "name": "Physical Exercises", "nature": "physical", "default_constructive": True},
    {"id": "helping_family", "name": "Helping Family Members on Household Activities", "nature": "emotional", "default_constructive": True},
    {"id": "reading_podcasts", "name": "Reading Books / Listening to Podcasts", "nature": "mental", "default_constructive": True},
    {"id": "social_media", "name": "Social Media", "nature": "mental", "default_constructive": False},
    {"id": "speak_expert", "name": "Speaking to an Expert in Solving your Challenge", "nature": "mental", "default_constructive": True},
    {"id": "listening_music", "name": "Listening to Music", "nature": "emotional", "default_constructive": True},
    {"id": "guiding_others", "name": "Guiding Others from your Experience / Professional Consulting", "nature": "mental", "default_constructive": True},
    {"id": "attending_webinars", "name": "Attending Webinars", "nature": "mental", "default_constructive": True},
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

SESSION_TYPES = ["trap", "loop", "limitation", "outlet", "aim", "integrated"]
SESSION_STATUSES = ["draft", "in_progress", "completed", "resolved"]
COMMITMENT_TYPES = ["immediate", "7_day", "30_day"]
COMMITMENT_STATUSES = ["pending", "completed", "missed"]
