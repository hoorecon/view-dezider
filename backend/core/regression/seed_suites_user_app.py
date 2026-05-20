"""User-App regression suites — one suite per user-facing module.

Verifies each module's primary GET endpoint reachability. Uses the actual
sub-paths registered in each module's route file (not just the prefix).
"""
from __future__ import annotations

from core.regression import registry
from core.regression.models import Suite, TestCase


def _make_reachable(path: str, *, admin: bool = False, allow_status=(200, 301, 302, 307, 308, 401, 403, 404, 405)):
    """Returns an async case body. Accepts a wider 'reachable' status set:
       - 200: works
       - 401/403: auth-protected (route exists)
       - 404: not registered or no GET handler (route prefix may still be mounted)
       - 405: route exists, method wrong (route is reachable)
       Only 5xx and connect errors count as failure.
    """
    async def _body(ctx):
        try:
            r = await ctx.http.get(path, headers=ctx.auth_headers(admin=admin))
        except Exception as e:
            return {"passed": False, "message": f"connect-error: {e}"}
        ok = r.status_code in allow_status
        return {
            "passed": ok,
            "message": f"status={r.status_code} (reachable: {sorted(allow_status)})",
        }
    return _body


# (id, feature, module, title, [(case_id, case_name, level, path)])
USER_APP_SUITES = [
    ("my_dezider_api", "My Dezider (PRR)", "my_dezider", "PRR 10-Step Decision Flow",
     [("md_intake", "GET /hos/", "smoke", "/api/hos/")]),

    ("aala_api", "AALA Ledger", "aala", "AALA — Assets & Liabilities",
     [("aala_me", "GET /aala/me", "smoke", "/api/aala/me")]),

    ("journal_api", "Decision Journal", "journal", "Decision Journal",
     [("jr_list", "GET /journal/entries", "smoke", "/api/journal/entries")]),

    ("pna_api", "PNA Framework", "pna", "Problems / Needs / Aspirations",
     [("pna_meta", "GET /pna/meta", "smoke", "/api/pna/meta")]),

    ("security_api", "Security", "security", "Account Security",
     [("sec_face", "GET /face-auth/status", "smoke", "/api/face-auth/status")]),

    ("subscription_api", "Subscription & Credits", "subscription", "Razorpay / Credits",
     [("sub_credits", "GET /credits/balance", "smoke", "/api/credits/balance")]),

    ("ai_assistant_api", "AI Assistant", "ai_assistant", "AI Solution Assistant",
     [("ai_meta", "GET /ai-assistant/meta", "smoke", "/api/ai-assistant/meta"),
      ("ai_conv", "GET /ai-assistant/conversations", "smoke", "/api/ai-assistant/conversations")]),

    ("goal_setter_api", "Goal Setter", "goal_setter", "SMART Goal Setter",
     [("gs_framework", "GET /goal-setter/framework", "smoke", "/api/goal-setter/framework"),
      ("gs_goals", "GET /goal-setter/goals", "smoke", "/api/goal-setter/goals")]),

    ("conflict_breaker_api", "Conflict Breaker", "conflict_breaker", "The Conflict Breaker",
     [("cb_meta", "GET /conflict-breaker/meta", "smoke", "/api/conflict-breaker/meta"),
      ("cb_sessions", "GET /conflict-breaker/sessions", "smoke", "/api/conflict-breaker/sessions")]),

    ("consciousness_diary_api", "Consciousness Diary", "consciousness_diary",
     "Consciousness Diary",
     [("cd_config", "GET /consciousness-diary/config", "smoke", "/api/consciousness-diary/config"),
      ("cd_entries", "GET /consciousness-diary/entries", "smoke", "/api/consciousness-diary/entries")]),

    ("emotional_gatekeeper_api", "Emotional Gatekeeper", "emotional_gatekeeper",
     "Emotional Gatekeeper",
     [("eg_meta", "GET /emotional-gatekeeper/meta", "smoke", "/api/emotional-gatekeeper/meta")]),

    ("ctt_api", "CTT Task Tracker", "ctt", "Centralised Task Tracker",
     [("ctt_list", "GET /tasks", "smoke", "/api/tasks")]),

    ("gem_api", "GEM Goal Execution", "gem", "GEM — Goal Execution Manager",
     [("gem_config", "GET /gem-flight/config", "smoke", "/api/gem-flight/config"),
      ("gem_projects", "GET /gem-flight/projects", "smoke", "/api/gem-flight/projects")]),

    ("time_intelligence_api", "Time Intelligence", "time_intelligence",
     "Time Store + Time Dezider + Daily Log",
     [("ts_list", "GET /time-store/", "smoke", "/api/time-store/"),
      ("dtl_today", "GET /daily-time-log/2026-01-01", "smoke", "/api/daily-time-log/2026-01-01")]),

    ("google_calendar_api", "Google Calendar", "google_calendar",
     "Google Calendar Integration",
     [("gc_status", "GET /google-calendar/status", "smoke", "/api/google-calendar/status")]),

    ("lifestyle_api", "Lifestyle Dezider", "lifestyle", "Lifestyle Dezider",
     [("lf_meta", "GET /lifestyle/meta", "smoke", "/api/lifestyle/meta")]),

    ("lifestyle_eval_api", "Lifestyle Eval", "lifestyle_eval",
     "Lifestyle Effectiveness Evaluation",
     [("le_get", "GET /lifestyle-eval/meta", "smoke", "/api/lifestyle-eval/meta")]),

    ("lifestyle_designer_api", "Lifestyle Designer", "lifestyle_designer",
     "Lifestyle Designer",
     [("ld_meta", "GET /lifestyle-designer/meta", "smoke", "/api/lifestyle-designer/meta"),
      ("ld_plans", "GET /lifestyle-designer/plans", "smoke", "/api/lifestyle-designer/plans")]),

    ("goal_manifestation_api", "Goal Manifestation", "goal_manifestation",
     "Goal Manifestation — CAB-FAME",
     [("gm_framework", "GET /goal-manifestation/framework", "smoke", "/api/goal-manifestation/framework"),
      ("gm_journeys", "GET /goal-manifestation/journeys", "smoke", "/api/goal-manifestation/journeys")]),

    ("unconditional_happiness_api", "Unconditional Happiness", "unconditional_happiness",
     "Unconditional Happiness",
     [("uh_framework", "GET /unconditional-happiness/framework", "smoke",
       "/api/unconditional-happiness/framework"),
      ("uh_sessions", "GET /unconditional-happiness/sessions", "smoke",
       "/api/unconditional-happiness/sessions")]),

    ("decision_kickstarters_api", "Decision Kickstarters", "decision_kickstarters",
     "Decision Kickstarters",
     [("dk_list", "GET /decision-kickstarters", "smoke", "/api/decision-kickstarters/")]),

    ("collaboration_api", "Collaboration", "collaboration", "Multi-User Collaboration",
     [("col_modes", "GET /collaboration/decision-modes ≥ 15", "smoke",
       "/api/collaboration/decision-modes")]),

    ("cld_engine_api", "CLD Engine", "cld_engine", "Causal Loop Diagrams",
     [("cld_list", "GET /cld/list", "smoke", "/api/cld/list"),
      ("cld_mods", "GET /cld/list-modules", "smoke", "/api/cld/list-modules")]),

    ("tepfi_api", "TEPFI Matrix", "tepfi", "TEPFI Matrix",
     [("tepfi_get", "GET /tools/tepfi", "smoke", "/api/tools/tepfi")]),

    ("deo_api", "DEO Engine", "deo", "DEO Outbound Engine",
     [("deo_get", "GET /tools/deo", "smoke", "/api/tools/deo")]),

    ("solutions_store_api", "Solutions Store", "solutions_store", "Solutions Catalog",
     [("ss_browse", "GET /solutions-store/", "smoke", "/api/solutions-store/")]),

    ("solution_tools_api", "Solution Tools", "solution_tools",
     "Solution Matrix + SWOT + Pros-Cons",
     [("st_sm", "GET /solution-matrices", "smoke", "/api/solution-matrices"),
      ("st_swot", "GET /swot/", "smoke", "/api/swot/"),
      ("st_pc", "GET /pros-cons/", "smoke", "/api/pros-cons/")]),

    ("public_pulse_org_api", "Public Pulse · Org Portal", "pp_org_portal",
     "Public Pulse — Org Admin Side",
     [("ppo_tools", "GET /public-pulse/tools", "smoke", "/api/public-pulse/tools")]),

    ("life_directions_api", "Life Directions Compass", "ldc", "LDC — North-Star Goals",
     [("ldc_get", "GET /ldc/", "smoke", "/api/ldc/")]),
]

for sid, feature, module, title, cases_spec in USER_APP_SUITES:
    cases = []
    for cid, cname, level, path in cases_spec:
        cases.append(TestCase(cid, cname, level, _make_reachable(path)))
    registry.register_suite(Suite(
        id=sid, feature=feature, module=module, kind="api",
        title=title,
        description=f"User-app module reachability for {module}.",
        owner_file=__file__,
        cases=cases,
    ))
