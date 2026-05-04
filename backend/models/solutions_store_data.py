"""Static seed data + reference enums for /routes/solutions_store.py.

Type whitelists, qualitative-factor list, supported countries / languages.
Lifted out of the route file so non-developers can localise / extend
without touching code paths.
"""

SOLUTION_TYPES = ["PRODUCT", "SERVICE", "EVENT", "PROJECT", "PERSON_CONTACT"]
VISIBILITY_LEVELS = ["PRIVATE", "ORG", "PUBLIC"]
APPROVAL_STATUSES = ["pending", "approved", "rejected"]

# Type-specific field definitions
TYPE_SPECIFIC_FIELDS = {
    "PRODUCT": ["brand", "model", "warranty_months", "specifications", "sku"],
    "SERVICE": ["duration", "frequency", "delivery_mode", "availability"],
    "EVENT": ["event_date", "event_end_date", "location", "venue", "capacity", "registration_url"],
    "PROJECT": ["timeline_months", "team_size", "budget", "milestones"],
    "PERSON_CONTACT": ["phone", "email", "designation", "organization", "expertise"],
}

# Default qualitative factor names for ReviewNet
DEFAULT_QUALITATIVE_FACTORS = [
    "Trustworthiness",
    "Quality",
    "Reliability",
    "Value for Money",
    "User Experience",
    "Customer Support",
    "Innovation",
    "Accessibility",
]

SUPPORTED_COUNTRIES = [
    {"code": "IN", "name": "India", "flag": "🇮🇳"},
    {"code": "US", "name": "United States", "flag": "🇺🇸"},
    {"code": "GB", "name": "United Kingdom", "flag": "🇬🇧"},
    {"code": "SG", "name": "Singapore", "flag": "🇸🇬"},
    {"code": "AE", "name": "UAE", "flag": "🇦🇪"},
    {"code": "AU", "name": "Australia", "flag": "🇦🇺"},
    {"code": "CA", "name": "Canada", "flag": "🇨🇦"},
]

SUPPORTED_LANGUAGES = [
    {"code": "en", "name": "English"},
    {"code": "ta", "name": "Tamil"},
    {"code": "hi", "name": "Hindi"},
    {"code": "te", "name": "Telugu"},
    {"code": "kn", "name": "Kannada"},
    {"code": "ml", "name": "Malayalam"},
    {"code": "mr", "name": "Marathi"},
    {"code": "bn", "name": "Bengali"},
    {"code": "gu", "name": "Gujarati"},
]
