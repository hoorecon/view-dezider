"""
Social Learning Engine — Constants
Centralized constants for the Social Learning module.
"""

# Life Areas aligned with HOS hierarchy
LIFE_AREAS = [
    "career_profession", "finance_wealth", "health_wellness",
    "relationships_family", "education_learning", "personal_growth",
    "social_community", "legal_governance", "technology_innovation",
    "environment_sustainability",
]

ORG_TYPES = ["family", "individual", "association", "company", "startup", "ngo", "govt", "cooperative", "trust"]

CATEGORIES = ["problem", "need", "aspiration"]

# Restricted to 6 languages as per user requirement
SUPPORTED_LANGUAGES = [
    "english", "hindi", "tamil", "telugu", "kannada", "malayalam",
]

TEMPLATE_STATUSES = ["draft", "submitted", "authorized", "rejected"]

# File upload constraints
MAX_FILE_SIZE_MB = 10

ALLOWED_FILE_TYPES = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "text/plain": "txt",
    "image/jpeg": "image",
    "image/jpg": "image",
    "image/png": "image",
    "image/webp": "image",
}

ALLOWED_AUDIO_TYPES = {
    "audio/wav": "wav",
    "audio/mpeg": "mp3",
    "audio/mp3": "mp3",
    "audio/x-wav": "wav",
    "audio/ogg": "ogg",
    "audio/webm": "webm",
    "audio/mp4": "mp4",
    "audio/x-m4a": "m4a",
}

ALLOWED_VIDEO_TYPES = {
    "video/mp4": "mp4",
    "video/mpeg": "mpeg",
    "video/quicktime": "mov",
    "video/x-msvideo": "avi",
    "video/webm": "webm",
    "video/x-matroska": "mkv",
    "video/3gpp": "3gp",
}
