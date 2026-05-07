"""Channel auto-tagging rules and category map for the API Catalog.

Splitting this out keeps the route file focused on HTTP handling and lets
non-developers (PMs / docs team) edit taxonomy without touching code paths.
"""

CHANNEL_RULES = {
    "/auth": ["internal", "chatbot", "ivr", "partner"],
    "/health": ["internal", "chatbot", "ivr", "partner"],
    "/decisions": ["internal", "chatbot", "partner"],
    "/test123": ["internal", "chatbot", "ivr"],
    "/pros-cons": ["internal", "chatbot"],
    "/swot": ["internal", "chatbot"],
    "/assessment": ["internal", "chatbot"],
    "/ctt": ["internal", "chatbot"],
    "/gem": ["internal", "chatbot"],
    "/journal": ["internal", "chatbot"],
    "/stats": ["internal", "chatbot"],
    "/notifications": ["internal", "ivr"],
    "/solutions-store": ["internal", "chatbot", "partner"],
    "/deo": ["internal", "partner"],
    "/payments": ["internal", "partner"],
    "/organizations": ["internal", "partner"],
    "/shared-steps": ["internal", "chatbot", "partner"],
    "/decision-templates": ["internal", "partner"],
    "/feature-flags": ["internal"],
    "/admin": ["internal"],
    "/search": ["internal", "chatbot", "partner"],
    "/folders": ["internal", "chatbot"],
    "/lifestyle": ["internal", "chatbot"],
    "/consciousness-diary": ["internal", "chatbot"],
    "/time-dezider": ["internal", "chatbot"],
    "/time-store": ["internal", "chatbot"],
    "/google-calendar": ["internal"],
    "/cld": ["internal", "chatbot"],
    "/gem-flight": ["internal", "chatbot"],
    "/hos": ["internal", "chatbot"],
    "/org-auth": ["internal", "partner"],
    "/video-calls": ["internal"],
    "/experts": ["internal"],
    "/tepfi": ["internal", "chatbot"],
    "/factor-data": ["internal", "chatbot"],
    "/reviews": ["internal", "chatbot", "partner"],
    "/contacts": ["internal", "chatbot", "partner"],
    "/collaboration": ["internal", "chatbot", "partner"],
    "/digilocker": ["internal"],
    "/biometric": ["internal"],
    "/aala": ["internal", "chatbot"],
    "/lifestyle-eval": ["internal", "chatbot"],
    "/goal-setter": ["internal", "chatbot"],
    "/goal-manifestation": ["internal", "chatbot"],
    "/unconditional-happiness": ["internal", "chatbot"],
    "/meditation-settings": ["internal"],
    "/conflict-breaker": ["internal", "chatbot"],
    "/pna": ["internal", "chatbot"],
    "/lifestyle-designer": ["internal", "chatbot"],
    "/ai-assistant": ["internal", "chatbot"],
    "/admin/customer-segments": ["internal"],
    "/admin/tier-matrix": ["internal"],
    "/customer-segments": ["internal", "chatbot", "partner"],
    "/pricing": ["internal", "chatbot", "partner"],
    "/tiers": ["internal", "chatbot", "partner"],
    "/tier-matrix": ["internal", "chatbot", "partner"],
    "/me/tier-access": ["internal", "chatbot"],
}

CATEGORY_MAP = {
    "/auth": "Authentication & User Management",
    "/health": "System",
    "/decisions": "PRR Decision Engine",
    "/test123": "Test123 Quick Decisions",
    "/pros-cons": "Pros & Cons Analysis",
    "/swot": "SWOT Analysis",
    "/assessment": "Decision Mode Assessment",
    "/ctt": "Centralized Task Tracker",
    "/gem": "Goals Execution Manager",
    "/gem-flight": "GEM Flight Model",
    "/journal": "Decision Journal",
    "/stats": "Analytics & Stats",
    "/notifications": "Notifications & Alerts",
    "/solutions-store": "Solutions Store",
    "/deo": "DEO Engine (Import & API)",
    "/payments": "Payments & Subscriptions",
    "/organizations": "Organizations",
    "/shared-steps": "Collaboration & Sharing",
    "/decision-templates": "Decision Templates",
    "/feature-flags": "Feature Configuration",
    "/admin": "Admin Management",
    "/search": "Search",
    "/folders": "Folder Management",
    "/lifestyle": "Lifestyle Dezider",
    "/consciousness-diary": "Consciousness Diary",
    "/time-dezider": "Time Dezider",
    "/time-store": "Time Store",
    "/google-calendar": "Google Calendar Integration",
    "/cld": "CLD (Causal Loop Diagrams)",
    "/hos": "HOS Decision Intake",
    "/org-auth": "Organization Auth",
    "/video-calls": "Video Call Sessions",
    "/experts": "Expert Management",
    "/tepfi": "TEPFI Matrix",
    "/factor-data": "Factor Data Sources",
    "/reviews": "Solution Reviews",
    "/contacts": "Contact List Management",
    "/collaboration": "Multi-User Collaboration",
    "/digilocker": "DigiLocker eKYC (India)",
    "/biometric": "Biometric Authentication",
    "/aala": "AALA (Accrued Assets & Liabilities Analysis)",
    "/lifestyle-eval": "LEE (Lifestyle Effectiveness Evaluation)",
    "/goal-setter": "Goal Setter (SMART Framework)",
    "/goal-manifestation": "Goal Manifestation (CAB-FAME)",
    "/unconditional-happiness": "Unconditional Happiness Tracker",
    "/meditation-settings": "Meditation Audio Settings",
    "/conflict-breaker": "Conflict Breaker (Crucial Conversations)",
    "/pna": "PNA (Problems / Needs / Aspirations)",
    "/lifestyle-designer": "Lifestyle Designer",
    "/ai-assistant": "AI Solution Assistant",
    "/admin/customer-segments": "Customer Segments — TG Master",
    "/admin/tier-matrix": "Tier Matrix — 7 Chakras (Admin)",
    "/customer-segments": "Customer Segments (Public)",
    "/pricing": "Pricing — 7 Chakras",
    "/tiers": "Subscription Tiers (Public)",
    "/tier-matrix": "Tier Matrix (Public)",
    "/me/tier-access": "My Tier Access",
}


def _longest_prefix_match(path: str, table: dict):
    """Pick the entry whose key is the longest prefix match for `path`."""
    clean = path.replace("/api", "", 1) if path.startswith("/api") else path
    best_key = None
    for prefix in table:
        if clean.startswith(prefix) and (best_key is None or len(prefix) > len(best_key)):
            best_key = prefix
    return table[best_key] if best_key else None


def get_channels(path: str) -> list:
    """Auto-tag an endpoint path with consumer channels (longest-prefix wins)."""
    return _longest_prefix_match(path, CHANNEL_RULES) or ["internal"]


def get_category(path: str) -> str:
    """Get category name for a path (longest-prefix wins)."""
    return _longest_prefix_match(path, CATEGORY_MAP) or "Other"
