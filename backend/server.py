"""
View Dezider API — Decision Intelligence by Venture Buddha
Slim entry point: app init, CORS, rate-limiting, routers, lifecycle.
All route logic lives in /routes/*.py
"""

import logging
import time
import uuid
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, APIRouter, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.cors import CORSMiddleware

# Load env BEFORE importing any module that reads os.environ at import time
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

# Ensure static dir exists
(ROOT_DIR / "static").mkdir(exist_ok=True)


# ========================
# LOGGING (early — so subsequent imports can log)
# ========================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# ========================
# APP + ROUTER SETUP
# ========================
app = FastAPI(
    title="View Dezider API",
    description="Decision Intelligence by Venture Buddha",
)
api_router = APIRouter(prefix="/api")


# ========================
# RATE LIMITING (slowapi)
# ========================
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from core.rate_limiting import limiter

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)


# ========================
# PRODUCTION HARDENING
# ========================
# Body cap, GZip, security headers, slow-request log, in-process metrics, PII
# redaction filter on all loggers. All knobs env-driven (DEZIDER_ENV / etc).
from core.hardening import install_hardening
install_hardening(app)


# ========================
# REQUEST LOGGING + REQUEST-ID MIDDLEWARE
# ========================
@app.middleware("http")
async def request_observability_middleware(request: Request, call_next):
    """Attach a per-request id, log latency, and surface slow queries.

    On unhandled exceptions we still produce a JSON 500 with the X-Request-ID
    header so clients can quote it when reporting bugs.
    """
    request_id = request.headers.get("X-Request-ID", uuid.uuid4().hex[:12])
    request.state.request_id = request_id
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception as e:
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.exception(
            f"req={request_id} {request.method} {request.url.path} "
            f"FAILED in {elapsed_ms:.0f}ms — {type(e).__name__}"
        )
        return JSONResponse(
            status_code=500,
            content={
                "detail": "Internal server error",
                "request_id": request_id,
                "error_type": type(e).__name__,
            },
            headers={
                "X-Request-ID": request_id,
                "X-Response-Time-MS": f"{elapsed_ms:.0f}",
            },
        )
    elapsed_ms = (time.perf_counter() - start) * 1000
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Response-Time-MS"] = f"{elapsed_ms:.0f}"
    # Only log slow requests / errors at INFO; keep success logs quiet to avoid noise
    if response.status_code >= 500 or elapsed_ms > 1500:
        logger.warning(
            f"req={request_id} {request.method} {request.url.path} "
            f"-> {response.status_code} in {elapsed_ms:.0f}ms"
        )
    return response


# ========================
# IMPORT ALL ROUTE MODULES
# ========================

# -- Core routes (extracted from monolith) --
from routes.auth_routes import router as auth_router
from routes.whatsapp_otp import router as whatsapp_otp_router
from routes.app_appearance import router as appearance_router
from routes.pii_admin import router as pii_admin_router
from routes.organizations import router as org_router
from routes.decisions import router as decisions_router
from routes.notifications import router as notif_router
from routes.analytics import router as analytics_router
from routes.ai_tools import router as ai_tools_router
from routes.video_calls import router as video_calls_router
from routes.decision_templates import router as decision_templates_router

# -- Pre-existing modular routes --
from routes.tools import router as tools_router
from routes.admin import router as admin_router
from routes.ctt_gem import router as ctt_gem_router
from routes.lifestyle import router as lifestyle_router
from routes.decision_intake import router as decision_intake_router
from routes.org_auth import router as org_auth_router
from routes.partner_embed import router as partner_embed_router
from routes.partner_embed_widget import router as partner_embed_widget_router
from routes.solutions_store import router as solutions_store_router
from routes.store_ingestion import router as store_ingestion_router
from routes.google_calendar import router as google_calendar_router
from routes.google_sheets import router as google_sheets_router
from routes.deo import router as deo_router
from routes.cld import router as cld_router
from routes.time_dezider import router as time_dezider_router
from routes.payments import router as payments_router
from routes.payment_admin import router as payment_admin_router
from routes.action_items import router as action_items_router
from routes.sku_store import router as sku_store_router
from routes.decision_reports import router as decision_reports_router
from routes.gem_flight import router as gem_flight_router
from routes.consciousness_diary import router as consciousness_diary_router
from routes.pros_cons import router as pros_cons_router
from routes.swot import router as swot_router
from routes.trash import router as trash_router
from routes.solution_box import router as solution_box_router
from routes.report_shares import router as report_shares_router
from routes.admin_docs import router as admin_docs_router
from routes.contacts import router as contacts_router
from routes.collaboration import router as collaboration_router
from routes.incident_response import router as incident_router
from routes.audit_trail import router as audit_trail_router
from routes.face_auth import router as face_auth_router
from routes.social_learning import router as social_learning_router
from routes.acm import router as acm_router
from routes.emotional_gatekeeper import router as emotional_gatekeeper_router
from routes.aala import router as aala_router
from routes.lifestyle_eval import router as lee_router
from routes.goal_setter import router as goal_setter_router
from routes.goal_manifestation import router as goal_manifestation_router
from routes.unconditional_happiness import router as uh_router
from routes.meditation_settings import router as meditation_settings_router
from routes.conflict_breaker import router as conflict_breaker_router
from routes.pna import router as pna_router
from routes.lifestyle_designer import router as lifestyle_designer_router
from routes.ai_assistant import router as ai_assistant_router
from routes.public_pulse import router as public_pulse_router
from routes.public_pulse_org import router as public_pulse_org_router
from routes.public_pulse_portal import router as public_pulse_portal_router
from routes.dpdp import router as dpdp_router
from routes.observability import router as observability_router
from routes.admin_docs_viewer import router as admin_docs_viewer_router
from routes.daily_time_log import router as daily_time_log_router
from routes.time_dezider_guide import router as time_dezider_guide_router
from routes.time_store_engine import router as time_store_engine_router
from routes.catalog import router as catalog_router
from routes.catalog_explorer import router as catalog_explorer_router
from routes.admin_quota import router as admin_quota_router
from routes.review_net import router as review_net_router
from routes.expert_net import router as expert_net_router
from routes.org_surveys import router as org_surveys_router
from routes.branding import router as branding_router
from routes.life_directions import router as life_directions_router
from routes.aala import router as aala_router
from routes.daily_tracker import router as daily_tracker_router
from routes.time_allocation import router as time_allocation_router
from routes.tier_matrix import router as tier_matrix_router
from routes.customer_segments import router as customer_segments_router
from routes.decision_linking import router as decision_linking_router
from routes.integrations import router as integrations_router
from routes.ai_wallet import router as ai_wallet_router
from routes.subscriptions import router as subscriptions_router


# ========================
# MOUNT ALL ROUTERS
# ========================

# Core routes (no extra prefix — paths defined in each router)
api_router.include_router(auth_router)
api_router.include_router(whatsapp_otp_router)
api_router.include_router(appearance_router)
api_router.include_router(pii_admin_router)
api_router.include_router(org_router)
api_router.include_router(decisions_router)
api_router.include_router(notif_router)
api_router.include_router(analytics_router)
api_router.include_router(ai_tools_router)
api_router.include_router(video_calls_router)
api_router.include_router(decision_templates_router)

# Pre-existing modular routes
api_router.include_router(tools_router)
api_router.include_router(admin_router)
api_router.include_router(ctt_gem_router)
api_router.include_router(lifestyle_router)
api_router.include_router(decision_intake_router)
api_router.include_router(org_auth_router)
api_router.include_router(partner_embed_router)
api_router.include_router(partner_embed_widget_router)
api_router.include_router(solutions_store_router)
api_router.include_router(store_ingestion_router)
api_router.include_router(google_calendar_router)
api_router.include_router(google_sheets_router)
api_router.include_router(deo_router)
api_router.include_router(cld_router)
api_router.include_router(time_dezider_router)
api_router.include_router(payments_router)
api_router.include_router(sku_store_router)
api_router.include_router(decision_reports_router)
api_router.include_router(gem_flight_router)
api_router.include_router(consciousness_diary_router)
api_router.include_router(pros_cons_router)
api_router.include_router(swot_router)
api_router.include_router(trash_router)
api_router.include_router(solution_box_router)
api_router.include_router(report_shares_router)
api_router.include_router(admin_docs_router)
api_router.include_router(contacts_router)
api_router.include_router(collaboration_router)
api_router.include_router(incident_router)
api_router.include_router(audit_trail_router)
api_router.include_router(face_auth_router)
api_router.include_router(social_learning_router)
api_router.include_router(acm_router)
api_router.include_router(emotional_gatekeeper_router)
api_router.include_router(aala_router)
api_router.include_router(lee_router)
api_router.include_router(goal_setter_router)
api_router.include_router(goal_manifestation_router)
api_router.include_router(uh_router)
api_router.include_router(meditation_settings_router)
api_router.include_router(conflict_breaker_router)
api_router.include_router(pna_router)
api_router.include_router(lifestyle_designer_router)
api_router.include_router(ai_assistant_router)
api_router.include_router(public_pulse_router)
api_router.include_router(public_pulse_org_router)
api_router.include_router(public_pulse_portal_router)
api_router.include_router(dpdp_router)
api_router.include_router(observability_router)
api_router.include_router(admin_docs_viewer_router)
api_router.include_router(daily_time_log_router)
api_router.include_router(time_dezider_guide_router)
api_router.include_router(time_store_engine_router)
api_router.include_router(catalog_router)
api_router.include_router(catalog_explorer_router)
api_router.include_router(admin_quota_router)
api_router.include_router(review_net_router)
api_router.include_router(expert_net_router)
api_router.include_router(org_surveys_router)
api_router.include_router(branding_router)
api_router.include_router(life_directions_router)
api_router.include_router(aala_router)
api_router.include_router(daily_tracker_router)
api_router.include_router(time_allocation_router)
api_router.include_router(tier_matrix_router)
api_router.include_router(customer_segments_router)
api_router.include_router(decision_linking_router)
api_router.include_router(integrations_router)
api_router.include_router(ai_wallet_router)
api_router.include_router(subscriptions_router)
api_router.include_router(payment_admin_router)
api_router.include_router(action_items_router)
from routes.masters import router as masters_router  # noqa: E402
api_router.include_router(masters_router)
from routes.regression import router as regression_router  # noqa: E402
api_router.include_router(regression_router)


# ========================
# HEALTH CHECK + INFRA STATUS
# ========================

@api_router.get("/health")
async def health_check():
    return {"status": "ok", "service": "View Dezider API"}


@api_router.get("/health/ready")
async def readiness_check():
    """Probes upstream dependencies. Returns 503 if anything is down."""
    from core.database import client as mongo_client
    try:
        # ping is cheap — confirms motor connection is alive
        await mongo_client.admin.command("ping")
        mongo_status = "ok"
        mongo_ok = True
    except Exception as e:
        mongo_status = f"error: {str(e)[:80]}"
        mongo_ok = False

    payload = {
        "status": "ok" if mongo_ok else "degraded",
        "checks": {"mongodb": mongo_status},
    }
    return JSONResponse(payload, status_code=200 if mongo_ok else 503)


# Mount the api_router onto the app
app.include_router(api_router)


# ========================
# CORS
# ========================
app.add_middleware(
    CORSMiddleware,
    # Auth uses Bearer tokens (Authorization header), NOT cookies, so credentials
    # must be False. Combining allow_credentials=True with allow_origins=["*"]
    # makes Starlette emit "Access-Control-Allow-Origin: *" together with
    # "Access-Control-Allow-Credentials: true" on cookie-less responses — an
    # illegal combination that browsers reject with a NetworkError (this broke
    # cross-origin login from jelcos.ai → api.jelcos.ai). With credentials=False
    # the response is a clean "ACAO: *" which every browser accepts.
    allow_credentials=False,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "X-Response-Time-MS", "X-RateLimit-Limit",
                    "X-RateLimit-Remaining", "X-RateLimit-Reset"],
)


# ========================
# LIFECYCLE EVENTS
# ========================
from core.database import client, ensure_indexes


@app.on_event("startup")
async def startup_db_client():
    """Ensure all production indexes exist + ACM seed is up to date before serving traffic."""
    try:
        await ensure_indexes()
    except Exception as e:
        # Don't crash boot — index creation is idempotent and self-healing
        logger.error(f"Index initialization failed: {e}")
    try:
        from core.acm_engine import ensure_acm_seeded_on_boot
        await ensure_acm_seeded_on_boot()
    except Exception as e:
        logger.error(f"ACM boot seed failed: {e}")
    try:
        from core.admin_data_seed import ensure_admin_data_seeded_on_boot
        await ensure_admin_data_seeded_on_boot()
    except Exception as e:
        logger.error(f"Admin data seed at boot failed: {e}")
    try:
        from core.masters_seed import ensure_masters_seeded_on_boot, dedup_masters_on_boot
        await ensure_masters_seeded_on_boot()
        await dedup_masters_on_boot()
    except Exception as e:
        logger.error(f"Masters seed at boot failed: {e}")

    # One-shot, idempotent migration — SWOT-converted Decisions need at least
    # one "Current Scenario" option so Steps 6/7/9/10 of /prr/[id] render.
    try:
        from core.migrations.swot_decisions_single_option import (
            migrate_swot_decisions_single_option,
        )
        await migrate_swot_decisions_single_option()
    except Exception as e:
        logger.error(f"SWOT-decisions single-option migration failed: {e}")

    # Idempotent — adds applies_to_modules/org_types/decision_types/swot_flag to
    # templates AND org_types/decision_types/scenario_ids to solutions_store.
    try:
        from core.migrations.template_taxonomy_v2 import (
            migrate_template_taxonomy_v2,
        )
        await migrate_template_taxonomy_v2()
    except Exception as e:
        logger.error(f"Template-taxonomy v2 migration failed: {e}")
    try:
        # If tier_matrix smart-seed was previously applied with stale module ids
        # (where root tier ended up with < 5 modules), auto-reset to apply the
        # corrected SMART_SEED_MIN_TIER mapping. One-shot, idempotent.
        from core.database import db as _db
        from routes.tier_matrix import _smart_seed as _tm_smart_seed
        from models.tier_models import SMART_SEED_MIN_TIER as _SS
        root_y = await _db.tier_matrix.count_documents(
            {"tier_key": "root", "allowed": True, "feature_id": None}
        )
        expected_root = sum(1 for v in _SS.values() if v == 1)
        if root_y < max(3, expected_root - 1):
            logger.warning(
                f"Tier-matrix root tier has only {root_y} modules enabled "
                f"(expected ~{expected_root}). Auto-resetting smart-seed."
            )
            await _db.tier_matrix.delete_many({})
            res = await _tm_smart_seed()
            logger.info(f"Tier-matrix reseeded: {res}")
    except Exception as e:
        logger.error(f"Tier-matrix auto-reset at boot failed: {e}")

    # Register regression suites + start weekly scheduler. Importing the
    # seed_suites modules triggers @register_suite side-effects. The ACM
    # auto-coverage registration is async (queries db.acm_modules), so we
    # await it after the static imports.
    try:
        from core.regression import seed_suites as _rs  # noqa: F401
        from core.regression import seed_suites_user_app as _rs_ua  # noqa: F401
        from core.regression.seed_suites_acm_coverage import register_acm_coverage
        await register_acm_coverage()
        from core.regression.scheduler import start_scheduler as _start_reg
        _start_reg()
    except Exception as e:
        logger.error(f"Regression suite/scheduler boot failed: {e}", exc_info=True)

    # Start subscription dunning sweep (downgrade after grace expiry)
    try:
        from routes.subscriptions import start_dunning_task
        start_dunning_task()
    except Exception as e:
        logger.error(f"Subscription dunning task boot failed: {e}", exc_info=True)


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()


# Mount static files for document downloads
app.mount("/api/static", StaticFiles(directory=str(ROOT_DIR / "static")), name="static")
