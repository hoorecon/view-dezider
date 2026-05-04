"""Static seed data for /routes/collaboration.py.

DEFAULT_MODES describes the 6 supported decision-making modes.
Extracted out of the route file so PMs / config can edit without
touching FastAPI handlers.
"""

DEFAULT_MODES = [
    {
        "id": "equal",
        "name": "Equal Weightage",
        "description": "All participants get exactly equal weight in the final outcome.",
        "icon": "people",
        "color": "#3B82F6",
        "weight_logic": "equal_split",
        "config": {},
        "active": True,
        "order": 1,
    },
    {
        "id": "voting",
        "name": "Voting",
        "description": "Majority or custom minimum percentage threshold must be met.",
        "icon": "hand-left",
        "color": "#10B981",
        "weight_logic": "voting",
        "config": {"threshold_type": "majority", "custom_threshold_pct": 51},
        "active": True,
        "order": 2,
    },
    {
        "id": "command",
        "name": "Command (Leader-Driven)",
        "description": "Main user holds 50% weightage. Remaining 50% shared equally among others.",
        "icon": "shield",
        "color": "#F59E0B",
        "weight_logic": "command",
        "config": {"leader_weight_pct": 50},
        "active": True,
        "order": 3,
    },
    {
        "id": "sme",
        "name": "Subject Matter Expert(s)",
        "description": "Designated SMEs hold 50% combined weightage. Rest shared equally among others.",
        "icon": "school",
        "color": "#8B5CF6",
        "weight_logic": "sme",
        "config": {"sme_total_weight_pct": 50},
        "active": True,
        "order": 4,
    },
    {
        "id": "custom",
        "name": "Custom Weightage",
        "description": "Manually assign specific weight percentages to each participant.",
        "icon": "options",
        "color": "#EC4899",
        "weight_logic": "custom",
        "config": {},
        "active": True,
        "order": 5,
    },
    {
        "id": "consensus",
        "name": "Consensus",
        "description": "100% acceptance from all participants required. No partial outcomes.",
        "icon": "checkmark-done-circle",
        "color": "#059669",
        "weight_logic": "consensus",
        "config": {"require_unanimous": True},
        "active": True,
        "order": 6,
    },
]
