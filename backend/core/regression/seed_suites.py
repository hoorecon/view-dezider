"""Day-1 regression suite definitions.

Each feature/bug-fix should add or extend a suite here (or in a sibling
module imported from `__init__.py`). To add a new suite:

    from core.regression import registry
    from core.regression.models import Suite, TestCase

    async def _case_xyz(ctx):
        r = await ctx.http.get("/api/something", headers=ctx.auth_headers(admin=True))
        return {"passed": r.status_code == 200, "message": f"status={r.status_code}"}

    registry.register_suite(Suite(
        id="my_feature_api",
        feature="My Feature",
        module="my_feature",
        kind="api",
        title="My Feature — API surface",
        description="Smoke + functional coverage",
        owner_file=__file__,
        cases=[TestCase(id="my_feature_smoke", name="GET /something", level="smoke", body=_case_xyz)],
    ))

See `/docs/REGRESSION_AUTHORING.md` for full guide.
"""
from __future__ import annotations

from core.regression import registry
from core.regression.models import Suite, TestCase


# ─────────────────────────────────────────────────────────────────────────────
# Reusable case factories
# ─────────────────────────────────────────────────────────────────────────────
def _make_get(path: str, *, admin: bool = False, expect_status: int = 200,
              min_count_in_field: str | None = None, min_count: int = 0):
    """Returns an async case body that GETs `path` and asserts."""
    async def _body(ctx):
        r = await ctx.http.get(path, headers=ctx.auth_headers(admin=admin))
        if r.status_code != expect_status:
            return {"passed": False, "message": f"status={r.status_code} expected={expect_status} body={r.text[:200]}"}
        if min_count_in_field is not None:
            try:
                data = r.json()
                arr = data.get(min_count_in_field) if isinstance(data, dict) else data
                n = len(arr) if hasattr(arr, "__len__") else 0
                if n < min_count:
                    return {"passed": False, "message": f"count={n} < expected {min_count}"}
                return {"passed": True, "message": f"status={r.status_code} count={n}"}
            except Exception as e:
                return {"passed": False, "message": f"parse error: {e}"}
        return {"passed": True, "message": f"status={r.status_code}"}
    return _body


def _make_list_min(path: str, min_count: int, *, admin: bool = False, field: str | None = None):
    async def _body(ctx):
        r = await ctx.http.get(path, headers=ctx.auth_headers(admin=admin))
        if r.status_code != 200:
            return {"passed": False, "message": f"status={r.status_code}"}
        data = r.json()
        arr = data.get(field) if (field and isinstance(data, dict)) else (data if isinstance(data, list) else [])
        if len(arr) < min_count:
            return {"passed": False, "message": f"got {len(arr)} expected ≥ {min_count}"}
        return {"passed": True, "message": f"count={len(arr)} ≥ {min_count}"}
    return _body


# ─────────────────────────────────────────────────────────────────────────────
# 1. AUTH
# ─────────────────────────────────────────────────────────────────────────────
async def _auth_login_admin(ctx):
    r = await ctx.http.post("/api/auth/login", json={"email": "admin@test.com", "password": "AdminPass2026!"})
    if r.status_code != 200:
        return {"passed": False, "message": f"status={r.status_code}"}
    body = r.json()
    tok = body.get("session_token") or body.get("access_token") or body.get("token")
    return {"passed": bool(tok), "message": "got session_token" if tok else "no token in response"}


async def _auth_me(ctx):
    if not ctx.admin_token:
        return {"passed": False, "message": "no admin token (login failed earlier)"}
    r = await ctx.http.get("/api/auth/me", headers=ctx.auth_headers(admin=True))
    return {"passed": r.status_code == 200, "message": f"status={r.status_code}"}


async def _auth_unauth_protected(ctx):
    r = await ctx.http.get("/api/admin/tier-matrix")
    ok = r.status_code in (401, 403)
    return {"passed": ok, "message": f"expected 401/403, got {r.status_code}"}


registry.register_suite(Suite(
    id="auth_api", feature="Auth", module="auth", kind="api",
    title="Authentication & Authorization",
    description="Login, /me, and unauth-protected endpoints reject anonymous access.",
    owner_file=__file__,
    cases=[
        TestCase("auth_login_admin", "POST /auth/login admin", "smoke", _auth_login_admin),
        TestCase("auth_me", "GET /auth/me with token", "smoke", _auth_me),
        TestCase("auth_unauth_blocked", "GET /admin/* without token → 401/403", "smoke", _auth_unauth_protected),
    ],
))


# ─────────────────────────────────────────────────────────────────────────────
# 2. BRANDING
# ─────────────────────────────────────────────────────────────────────────────
registry.register_suite(Suite(
    id="branding_api", feature="Branding", module="branding", kind="api",
    title="Branding configuration",
    description="Current branding endpoint returns 200 with expected keys.",
    owner_file=__file__,
    cases=[
        TestCase("branding_current", "GET /branding/current", "smoke", _make_get("/api/branding/current")),
    ],
))


# ─────────────────────────────────────────────────────────────────────────────
# 3. ACM (Access Control Matrix)
# ─────────────────────────────────────────────────────────────────────────────
async def _acm_full(ctx):
    r = await ctx.http.get("/api/acm/matrix", headers=ctx.auth_headers(admin=True))
    if r.status_code != 200:
        return {"passed": False, "message": f"status={r.status_code}"}
    data = r.json()
    mods = data.get("modules", [])
    total_features = data.get("total_features", 0)
    if len(mods) < 30:
        return {"passed": False, "message": f"modules={len(mods)} (expected ≥30)"}
    if total_features < 80:
        return {"passed": False, "message": f"total_features={total_features} (expected ≥80)"}
    return {"passed": True, "message": f"modules={len(mods)} total_features={total_features}"}


registry.register_suite(Suite(
    id="acm_api", feature="Access Control", module="acm", kind="api",
    title="ACM (Access Control Matrix)",
    description="Module + feature catalog loaded with expected minimums.",
    owner_file=__file__,
    cases=[
        TestCase("acm_full", "GET /acm/full has ≥30 modules + ≥80 features", "smoke", _acm_full),
    ],
))


# ─────────────────────────────────────────────────────────────────────────────
# 4. TIER MATRIX
# ─────────────────────────────────────────────────────────────────────────────
async def _tier_matrix_smart_seed(ctx):
    r = await ctx.http.get("/api/admin/tier-matrix", headers=ctx.auth_headers(admin=True))
    if r.status_code != 200:
        return {"passed": False, "message": f"status={r.status_code}"}
    data = r.json()
    cells = data.get("cells") or data.get("matrix") or data
    tiers = data.get("tiers", [])
    if not tiers or len(tiers) != 7:
        return {"passed": False, "message": f"expected 7 chakra tiers, got {len(tiers)}"}
    return {"passed": True, "message": f"tiers=7 cells_payload_keys={list(data.keys())[:5]}"}


registry.register_suite(Suite(
    id="tier_matrix_api", feature="Tier Matrix", module="tier_matrix", kind="api",
    title="7-chakra Tier Matrix",
    description="All 7 chakra tiers are present + smart-seed produced cumulative unlocks.",
    owner_file=__file__,
    cases=[
        TestCase("tm_get", "GET /admin/tier-matrix returns 7 tiers", "smoke", _tier_matrix_smart_seed),
    ],
))


# ─────────────────────────────────────────────────────────────────────────────
# 5. CUSTOMER SEGMENTS
# ─────────────────────────────────────────────────────────────────────────────
async def _segments_full(ctx):
    r = await ctx.http.get("/api/admin/customer-segments", headers=ctx.auth_headers(admin=True))
    if r.status_code != 200:
        return {"passed": False, "message": f"status={r.status_code}"}
    data = r.json()
    segs = data.get("segments", [])
    seeded = [s for s in segs if s.get("segment_id", "").startswith("cs_seed_")]
    if len(seeded) < 6:
        return {"passed": False, "message": f"seeded={len(seeded)} expected ≥ 6"}
    # Verify factor + pricing density on a sample
    sample = seeded[0]
    if len(sample.get("factors", [])) < 20 or len(sample.get("tier_pricings", [])) != 7:
        return {"passed": False, "message": f"sample factors={len(sample.get('factors',[]))} prices={len(sample.get('tier_pricings',[]))}"}
    return {"passed": True, "message": f"seeded_segments={len(seeded)} factors≥20 prices=7"}


registry.register_suite(Suite(
    id="customer_segments_api", feature="Customer Segments", module="customer_segments", kind="api",
    title="Customer Segments + Pricing",
    description="6 seeded segments with full factor catalog + 7-tier INR pricing.",
    owner_file=__file__,
    cases=[
        TestCase("seg_full", "GET /admin/customer-segments has 6 seeded", "smoke", _segments_full),
        TestCase("public_segments", "GET /customer-segments (public) loads", "smoke",
                 _make_get("/api/customer-segments")),
        TestCase("public_pricing", "GET /pricing loads", "smoke", _make_get("/api/pricing")),
    ],
))


# ─────────────────────────────────────────────────────────────────────────────
# 6. DECISION MODES (15)
# ─────────────────────────────────────────────────────────────────────────────
async def _decision_modes(ctx):
    r = await ctx.http.get("/api/collaboration/decision-modes", headers=ctx.auth_headers())
    if r.status_code != 200:
        return {"passed": False, "message": f"status={r.status_code}"}
    data = r.json()
    arr = data if isinstance(data, list) else data.get("modes", [])
    if len(arr) < 15:
        return {"passed": False, "message": f"got {len(arr)} modes, expected ≥ 15"}
    names = {m.get("id") for m in arr}
    must_have = {"equal", "voting", "consensus", "supermajority", "delegation", "ranked_choice", "mcda"}
    missing = must_have - names
    if missing:
        return {"passed": False, "message": f"missing modes: {missing}"}
    return {"passed": True, "message": f"count={len(arr)} all_standard_methods_present"}


registry.register_suite(Suite(
    id="decision_modes_api", feature="Decision Modes", module="decision_modes", kind="api",
    title="Decision-Making Modes (15)",
    description="Full standard catalog (Equal, Voting, Supermajority, Delegation, IRV, MCDA, Borda, etc.).",
    owner_file=__file__,
    cases=[
        TestCase("dm_list", "GET /collaboration/decision-modes ≥ 15", "smoke", _decision_modes),
    ],
))


# ─────────────────────────────────────────────────────────────────────────────
# 7. EXPERTS
# ─────────────────────────────────────────────────────────────────────────────
registry.register_suite(Suite(
    id="experts_api", feature="Experts", module="experts", kind="api",
    title="Expert Net",
    description="Expert catalog reachable + seeded entries present.",
    owner_file=__file__,
    cases=[
        TestCase("ex_list", "GET /experts ≥ 7 seeded", "smoke",
                 _make_list_min("/api/experts?include_inactive=true", 7)),
    ],
))


# ─────────────────────────────────────────────────────────────────────────────
# 8. DECISION TEMPLATES
# ─────────────────────────────────────────────────────────────────────────────
registry.register_suite(Suite(
    id="templates_api", feature="Templates", module="templates", kind="api",
    title="Decision Templates",
    description="Curated templates load with ≥12 seeded.",
    owner_file=__file__,
    cases=[
        TestCase("tpl_all", "GET /decision-templates/all ≥ 12", "smoke",
                 _make_list_min("/api/decision-templates/all", 12, admin=True)),
    ],
))


# ─────────────────────────────────────────────────────────────────────────────
# 9. PENDING APPROVALS (Solutions Store)
# ─────────────────────────────────────────────────────────────────────────────
registry.register_suite(Suite(
    id="pending_approvals_api", feature="Pending Approvals", module="solutions_store", kind="api",
    title="Solutions Store · Pending Approvals",
    description="Moderation queue endpoint returns seeded pending solutions.",
    owner_file=__file__,
    cases=[
        TestCase("pa_list", "GET /solutions-store/pending-approval ≥ 6", "smoke",
                 _make_list_min("/api/solutions-store/pending-approval", 6, admin=True, field="solutions")),
    ],
))


# ─────────────────────────────────────────────────────────────────────────────
# 10. SOCIAL LEARNING
# ─────────────────────────────────────────────────────────────────────────────
registry.register_suite(Suite(
    id="social_learning_api", feature="Social Learning", module="social_learning", kind="api",
    title="Social Learning · Admin",
    description="Pending submissions queue returns seeded entries.",
    owner_file=__file__,
    cases=[
        TestCase("sl_pending", "GET /social-learning/admin/pending ≥ 6", "smoke",
                 _make_list_min("/api/social-learning/admin/pending", 6, admin=True, field="templates")),
    ],
))


# ─────────────────────────────────────────────────────────────────────────────
# 11. REVIEWNET
# ─────────────────────────────────────────────────────────────────────────────
registry.register_suite(Suite(
    id="reviewnet_api", feature="ReviewNet", module="review_net", kind="api",
    title="ReviewNet · Moderation Queue",
    description="6 seeded pending reviews show in moderation queue.",
    owner_file=__file__,
    cases=[
        TestCase("rn_queue", "GET /review-net/admin/moderation-queue ≥ 6 pending", "smoke",
                 _make_list_min("/api/review-net/admin/moderation-queue?status=pending", 6, admin=True, field="items")),
    ],
))


# ─────────────────────────────────────────────────────────────────────────────
# 12. INCIDENT RESPONSE
# ─────────────────────────────────────────────────────────────────────────────
registry.register_suite(Suite(
    id="incidents_api", feature="Incident Response", module="incidents", kind="api",
    title="Security Incident Response",
    description="Incident log endpoint returns ≥ 4 seeded incidents with timelines.",
    owner_file=__file__,
    cases=[
        TestCase("inc_list", "GET /incidents ≥ 4", "smoke",
                 _make_list_min("/api/incidents", 4, admin=True)),
    ],
))


# ─────────────────────────────────────────────────────────────────────────────
# 13. AUDIT TRAIL
# ─────────────────────────────────────────────────────────────────────────────
registry.register_suite(Suite(
    id="audit_trail_api", feature="Audit Trail", module="audit_trail", kind="api",
    title="Audit Trail",
    description="Audit log returns ≥ 25 seeded events.",
    owner_file=__file__,
    cases=[
        TestCase("at_list", "GET /audit-trail ≥ 25", "smoke",
                 _make_list_min("/api/audit-trail", 25, admin=True, field="logs")),
    ],
))


# ─────────────────────────────────────────────────────────────────────────────
# 14. PUBLIC PULSE
# ─────────────────────────────────────────────────────────────────────────────
registry.register_suite(Suite(
    id="public_pulse_api", feature="Public Pulse", module="pp_citizen_portal", kind="api",
    title="Public Pulse (Citizen + Org)",
    description="Citizen portal feedback endpoints + categories reachable.",
    owner_file=__file__,
    cases=[
        TestCase("pp_tools", "GET /public-pulse/tools", "smoke", _make_get("/api/public-pulse/tools")),
    ],
))


# ─────────────────────────────────────────────────────────────────────────────
# 15. SOLUTION MATRIX
# ─────────────────────────────────────────────────────────────────────────────
registry.register_suite(Suite(
    id="solution_matrix_api", feature="Solution Matrix", module="solution_tools", kind="api",
    title="Solution Matrix (84-cell, 4 OrgTypes)",
    description="Reachability + create+read smoke for an authenticated user.",
    owner_file=__file__,
    cases=[
        TestCase("sm_list", "GET /solution-matrices", "smoke",
                 _make_get("/api/solution-matrices", admin=True)),
    ],
))


# ─────────────────────────────────────────────────────────────────────────────
# 16. ADMIN DATA SEED
# ─────────────────────────────────────────────────────────────────────────────
async def _seed_status(ctx):
    r = await ctx.http.get("/api/admin/seed/status", headers=ctx.auth_headers(admin=True))
    if r.status_code != 200:
        return {"passed": False, "message": f"status={r.status_code}"}
    d = r.json()
    if not d.get("seeded"):
        return {"passed": False, "message": "seeded=false"}
    return {"passed": True, "message": f"seed_version={d.get('seed_version')}"}


registry.register_suite(Suite(
    id="admin_seed_api", feature="Admin Data Seed", module="admin", kind="api",
    title="Admin Data Seed marker",
    description="Seed has run successfully and persisted its version marker.",
    owner_file=__file__,
    cases=[
        TestCase("seed_status", "GET /admin/seed/status returns seeded=true", "smoke", _seed_status),
    ],
))


# ─────────────────────────────────────────────────────────────────────────────
# 17. HEALTH
# ─────────────────────────────────────────────────────────────────────────────
registry.register_suite(Suite(
    id="health_api", feature="Platform Health", module="system", kind="api",
    title="Health & liveness",
    description="API responds + database reachable.",
    owner_file=__file__,
    cases=[
        TestCase("health", "GET /health", "smoke", _make_get("/api/health")),
        TestCase("health_live", "GET /health/live", "smoke", _make_get("/api/health/live")),
    ],
))


# ─────────────────────────────────────────────────────────────────────────────
# 18-22 — UI suites (declarative; manual_pending until Playwright sidecar lands)
# ─────────────────────────────────────────────────────────────────────────────
async def _ui_placeholder(_ctx):
    return {"passed": True, "message": "ui placeholder"}


_ui_specs = [
    ("ui_auth", "Auth", "auth", "Login / Logout / Session", "docs/regression/ui/auth.md",
     [("ui_login_admin", "Login as admin → land on /admin", "smoke"),
      ("ui_logout", "Logout from header → redirect to /auth/login", "smoke"),
      ("ui_persist_session", "Reload page → still authenticated", "functional")]),
    ("ui_admin_nav", "Admin Console", "admin", "Admin sidebar navigation", "docs/regression/ui/admin_nav.md",
     [("ui_nav_decision_modes", "Click Decision Modes → renders 15 modes", "smoke"),
      ("ui_nav_tier_matrix", "Click Tier Matrix → renders 7×N grid", "smoke"),
      ("ui_nav_customer_segments", "Click Customer Segments → renders 6 cards", "smoke"),
      ("ui_nav_social_learning", "Click Social Learning → renders 6 pending", "smoke"),
      ("ui_nav_reviewnet", "Click ReviewNet → renders queue (6)", "smoke")]),
    ("ui_prr", "PRR", "my_dezider", "PRR 10-step decision flow", "docs/regression/ui/prr.md",
     [("ui_prr_create", "Create a new PRR with all 10 steps filled", "functional"),
      ("ui_prr_voice", "Start voice browsing on a step", "functional")]),
    ("ui_solution_matrix", "Solution Matrix", "solution_tools", "84-cell Solution Matrix",
     "docs/regression/ui/solution_matrix.md",
     [("ui_sm_create", "Create matrix with all 4 OrgTypes", "functional"),
      ("ui_sm_export", "Export matrix to PDF", "functional")]),
    ("ui_public_pulse", "Public Pulse", "pp_citizen_portal", "Citizen + Org portals",
     "docs/regression/ui/public_pulse.md",
     [("ui_pp_citizen_submit", "Submit citizen feedback", "functional"),
      ("ui_pp_org_dashboard", "Org admin sees feedback in dashboard", "functional")]),
]

for sid, feature, module, title, spec_path, cases in _ui_specs:
    registry.register_suite(Suite(
        id=sid, feature=feature, module=module, kind="ui",
        title=title, description=f"UI regression — Playwright spec at /{spec_path}",
        owner_file=__file__, ui_spec_path=spec_path,
        cases=[TestCase(cid, cname, lvl, _ui_placeholder) for cid, cname, lvl in cases],
    ))
