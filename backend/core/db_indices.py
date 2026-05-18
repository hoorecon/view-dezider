"""Declarative MongoDB index registry — applied at app startup.

Why this file exists:
- Production read latencies blow up without proper indexes on user-scoped queries.
- Putting all index specs in ONE place makes it trivial to audit / extend.
- `pymongo`/`motor` create_index() is idempotent — running on every boot is safe and cheap.

Format:
    "<collection_name>": [
        ("field", direction),                       # single-field index
        [("field1", 1), ("field2", -1)],            # compound index
        {"keys": [("field", 1)], "unique": True},   # advanced opts
    ]
"""

# Hot-path indexes for ~10k concurrent users.
# Coverage focus: auth/session lookups, user-scoped reads, time-sorted lists.

INDEX_SPECS: dict[str, list] = {
    # ─── Auth & Sessions ─────────────────────────────────────────
    "users": [
        {"keys": [("email", 1)], "unique": True, "sparse": True},
        ("user_id", 1),
        ("role", 1),
        ("org_id", 1),
    ],
    "user_sessions": [
        {"keys": [("session_token", 1)], "unique": True},
        ("user_id", 1),
        ("expires_at", 1),
    ],
    "password_resets": [("email", 1), ("expires_at", 1)],
    "whatsapp_otp_verifications": [("phone", 1), ("expires_at", 1)],
    "oauth_states": [{"keys": [("state", 1)], "unique": True}, ("expires_at", 1)],
    "google_calendar_tokens": [{"keys": [("user_id", 1)], "unique": True}],
    "user_biometrics": [("user_id", 1)],
    "user_totp": [{"keys": [("user_id", 1)], "unique": True}],
    "face_registrations": [("user_id", 1)],
    "user_kyc": [{"keys": [("user_id", 1)], "unique": True}],
    "digilocker_states": [{"keys": [("state", 1)], "unique": True}, ("expires_at", 1)],

    # ─── Core Decision Engine ────────────────────────────────────
    "decisions": [
        ("user_id", 1),
        [("user_id", 1), ("created_at", -1)],
        [("user_id", 1), ("folder", 1)],
        ("decision_id", 1),
    ],
    "prr_decisions": [
        ("user_id", 1),
        [("user_id", 1), ("created_at", -1)],
    ],
    "decision_templates": [
        ("created_by", 1),
        ("is_approved", 1),
        ("life_area", 1),
        ("decision_type", 1),
    ],
    "templates": [
        ("user_id", 1),
        ("visibility", 1),
        [("visibility", 1), ("created_at", -1)],
    ],
    "shared_steps": [
        ("share_id", 1),
        ("sharer_id", 1),
        ("recipient_emails", 1),
    ],
    "decision_modes": [{"keys": [("user_id", 1)], "unique": True}],

    # ─── Lightweight Decision Tools ──────────────────────────────
    "test": [("user_id", 1), [("user_id", 1), ("created_at", -1)]],
    "pros_cons": [("user_id", 1), [("user_id", 1), ("created_at", -1)]],
    "swot_analyses": [("user_id", 1), [("user_id", 1), ("created_at", -1)]],
    "assessments": [("user_id", 1)],
    "journal": [("user_id", 1), [("user_id", 1), ("created_at", -1)]],
    "ctt_tasks": [
        ("user_id", 1),
        [("user_id", 1), ("status", 1)],
        [("user_id", 1), ("due_date", 1)],
    ],

    # ─── GEM / Goals ─────────────────────────────────────────────
    "gem_goals": [("user_id", 1), [("user_id", 1), ("status", 1)]],
    "smart_goals": [("user_id", 1)],
    "manifestation_journeys": [("user_id", 1), ("goal_id", 1)],
    "flight_projects": [("user_id", 1)],
    "flight_events": [("project_id", 1)],

    # ─── AALA / LEE / Lifestyle ─────────────────────────────────
    "aala_assessments": [("user_id", 1), [("user_id", 1), ("created_at", -1)]],
    "aala_records": [("user_id", 1), ("life_area", 1)],
    "lifestyle_eval_logs": [("user_id", 1), ("date", -1)],
    "lifestyle_plans": [("user_id", 1), ("is_active", 1)],
    "lifestyle_routines": [("user_id", 1)],
    "lifestyle_overrides": [("user_id", 1), ("date", -1)],
    "routine_completions": [("user_id", 1), ("routine_id", 1), ("date", -1)],

    # ─── Happiness & Meditation ──────────────────────────────────
    "happiness_sessions": [("user_id", 1), ("date", -1)],
    "happiness_stats": [{"keys": [("user_id", 1)], "unique": True}],
    "unconditional_happiness": [("user_id", 1)],
    "meditation_sessions": [("user_id", 1), ("date", -1)],
    "meditation_preferences": [{"keys": [("user_id", 1)], "unique": True}],

    # ─── PNA / Lifestyle Designer ───────────────────────────────
    "pna_items": [
        ("user_id", 1),
        [("user_id", 1), ("life_area", 1), ("item_type", 1)],
    ],

    # ─── CLD ────────────────────────────────────────────────────
    "cld_diagrams": [
        ("user_id", 1),
        [("user_id", 1), ("module_type", 1)],
        ("decision_id", 1),
    ],

    # ─── Conflict Breaker (9 stages) ─────────────────────────────
    "conflict_breaker_sessions": [("user_id", 1), ("session_id", 1)],
    "conflict_crucial_check": [("session_id", 1)],
    "conflict_motive_clarity": [("session_id", 1)],
    "conflict_safety_diagnosis": [("session_id", 1)],
    "conflict_make_safe": [("session_id", 1)],
    "conflict_story_map": [("session_id", 1)],
    "conflict_script_builder": [("session_id", 1)],
    "conflict_listening_plan": [("session_id", 1)],
    "conflict_action_plan": [("session_id", 1)],
    "conflict_followup_reminders": [("user_id", 1), ("trigger_at", 1)],
    "conflict_journal": [("user_id", 1)],

    # ─── Emotional Gatekeeper ───────────────────────────────────
    "trap_reflections": [("user_id", 1)],
    "loop_reflections": [("user_id", 1)],
    "limitation_reflections": [("user_id", 1)],
    "aim_reflections": [("user_id", 1)],
    "outlet_reflections": [("user_id", 1)],
    "emotional_reception_logs": [("user_id", 1), ("created_at", -1)],
    "advisor_practice_logs": [("user_id", 1)],
    "breakthrough_sessions": [("user_id", 1)],
    "breakthrough_reports": [("user_id", 1)],
    "breakthrough_journal": [("user_id", 1)],
    "breakthrough_commitments": [("user_id", 1)],
    "self_awareness": [("user_id", 1)],

    # ─── AI Assistant ───────────────────────────────────────────
    "ai_assistant_conversations": [
        ("user_id", 1),
        [("user_id", 1), ("updated_at", -1)],
        ("conversation_id", 1),
    ],

    # ─── Solutions Store / DEO ──────────────────────────────────
    "solutions_store": [
        ("life_area", 1),
        ("decision_type", 1),
        ("status", 1),
        [("life_area", 1), ("status", 1)],
    ],
    "solution_finders": [("user_id", 1)],
    "solution_matrices": [("user_id", 1)],
    "solution_reviews": [("solution_id", 1), ("user_id", 1)],
    "deo_api_keys": [{"keys": [("api_key", 1)], "unique": True}, ("user_id", 1)],
    "deo_mappings": [("user_id", 1)],
    "deo_scrape_logs": [("user_id", 1), ("created_at", -1)],
    "deo_usage": [("api_key", 1), ("date", -1)],

    # ─── Notifications & Audit ──────────────────────────────────
    "notifications": [
        ("user_id", 1),
        [("user_id", 1), ("read", 1)],
        [("user_id", 1), ("created_at", -1)],
    ],
    "user_notifications": [("user_id", 1), [("user_id", 1), ("created_at", -1)]],
    "audit_trail": [("user_id", 1), [("user_id", 1), ("created_at", -1)]],
    "incidents": [("user_id", 1), ("status", 1)],

    # ─── Org / Multi-tenant ─────────────────────────────────────
    "organizations": [
        {"keys": [("slug", 1)], "unique": True},
        {"keys": [("org_id", 1)], "unique": True},
    ],
    "org_settings": [{"keys": [("org_id", 1)], "unique": True}],

    # ─── Payments / Credits ─────────────────────────────────────
    "payment_orders": [("user_id", 1), ("razorpay_order_id", 1)],
    "credit_wallets": [{"keys": [("user_id", 1)], "unique": True}],
    "credit_transactions": [("user_id", 1), [("user_id", 1), ("created_at", -1)]],

    # ─── ACM ────────────────────────────────────────────────────
    "acm_modules": [{"keys": [("module_id", 1)], "unique": True}],
    "acm_user_types": [{"keys": [("id", 1)], "unique": True}],
    "acm_subscription_plans": [{"keys": [("id", 1)], "unique": True}],
    "acm_usage": [
        [("user_id", 1), ("feature_id", 1)],
        [("user_id", 1), ("date", -1)],
    ],

    # ─── Calls / Collaboration ──────────────────────────────────
    "call_sessions": [("session_id", 1), ("user_id", 1)],
    "collab_calls": [("call_id", 1)],
    "collaboration_sessions": [("user_id", 1)],
    "experts": [("is_active", 1), ("specialization", 1)],
    "contacts": [("user_id", 1)],

    # ─── Time / TEPFI ───────────────────────────────────────────
    "time_dezider_entries": [("user_id", 1), ("date", -1)],
    "time_blocks_unplanned": [("user_id", 1), ("date", -1)],
    "time_preferences": [{"keys": [("user_id", 1)], "unique": True}],
    "tepfi_entries": [("user_id", 1)],
    "unplanned_tasks": [("user_id", 1)],

    # ─── Misc ───────────────────────────────────────────────────
    "consciousness_diary": [("user_id", 1), ("date", -1)],
    "gratitude_journals": [("user_id", 1), ("date", -1)],
    "presence_logs": [("user_id", 1), ("created_at", -1)],
    "user_preferences": [{"keys": [("user_id", 1)], "unique": True}],
    "social_learning_templates": [("life_area", 1)],
    "social_solution_templates": [("life_area", 1)],
    "admin_docs": [{"keys": [("doc_type", 1)], "unique": True}],
    "app_settings": [{"keys": [("key", 1)], "unique": True}],
    "app_config": [{"keys": [("key", 1)], "unique": True}],

    # ─── Public Pulse ───────────────────────────────────────────
    "pp_consent_records": [
        ("user_id", 1),
        [("user_id", 1), ("withdrawn", 1), ("timestamp", -1)],
    ],
    "pp_demographic_profiles": [{"keys": [("user_id", 1)], "unique": True}],
    "pp_tool_sessions": [
        ("user_id", 1),
        ("session_id", 1),
        [("tool_slug", 1), ("completed", 1), ("contributed_to_research", 1)],
        [("answers.district", 1), ("answers.age_group", 1)],
        ("started_at", -1),
    ],
    "pp_feedback_items": [
        ("user_id", 1),
        ("status", 1),
        [("user_id", 1), ("created_at", -1)],
    ],
    "pp_audit_logs": [
        ("user_id", 1),
        ("timestamp", -1),
    ],
    "pp_config": [{"keys": [("key", 1)], "unique": True}],

    # ─── Public Pulse Phase 2: Orgs ─────────────────────────────
    "pp_org_applications": [
        ("user_id", 1),
        ("status", 1),
        [("user_id", 1), ("org_type", 1), ("status", 1)],
        [("status", 1), ("submitted_at", 1)],
    ],
    "pp_orgs": [
        {"keys": [("org_id", 1)], "unique": True},
        {"keys": [("slug", 1)], "unique": True, "sparse": True},
        ("status", 1),
        ("district", 1),
        [("status", 1), ("org_type", 1)],
    ],
    "pp_org_members": [
        [("org_id", 1), ("user_id", 1)],
        ("user_id", 1),
        [("org_id", 1), ("role", 1)],
    ],
    "pp_admin_config": [{"keys": [("key", 1)], "unique": True}],

    # ─── Public Pulse File Storage ─────────────────────────────
    "pp_files": [
        {"keys": [("file_id", 1)], "unique": True},
        ("owner_user_id", 1),
        ("category", 1),
        ("created_at", -1),
    ],

    # ─── Tier Matrix (7-chakra subscription gating) ────────────
    "tier_matrix": [
        {"keys": [("module_id", 1), ("feature_id", 1), ("tier_key", 1)], "unique": True},
        ("tier_key", 1),
        [("tier_key", 1), ("allowed", 1)],
    ],

    # ─── Customer Segments (TG master) ─────────────────────────
    "customer_segments": [
        {"keys": [("segment_id", 1)], "unique": True},
        ("created_at", -1),
        ("chakra_tier_link", 1),
    ],
}


async def apply_indexes(db) -> dict:
    """Create all declared indexes. Returns per-collection result counts.

    Idempotent — safe to call on every startup. Errors on any single
    collection are isolated so one bad spec doesn't block the rest.
    """
    results = {"created": 0, "skipped": 0, "errors": []}
    for coll_name, specs in INDEX_SPECS.items():
        for spec in specs:
            try:
                if isinstance(spec, dict):
                    keys = spec.pop("keys")
                    await db[coll_name].create_index(keys, background=True, **spec)
                elif isinstance(spec, list):
                    await db[coll_name].create_index(spec, background=True)
                else:  # tuple
                    await db[coll_name].create_index([spec], background=True)
                results["created"] += 1
            except Exception as e:
                # Most failures are "index already exists with different options" — log & continue
                msg = f"{coll_name}: {str(e)[:120]}"
                results["errors"].append(msg)
                results["skipped"] += 1
    return results
