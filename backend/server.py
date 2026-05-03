"""
View Dezider API — Decision Intelligence by Venture Buddha
Slim entry point: app init, CORS, and router mounting.
All route logic is in /routes/*.py
"""

import logging
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI, APIRouter
from fastapi.staticfiles import StaticFiles
from starlette.middleware.cors import CORSMiddleware

# Load env
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# Ensure static dir exists
(ROOT_DIR / 'static').mkdir(exist_ok=True)

# ========================
# APP + ROUTER SETUP
# ========================

app = FastAPI(title="View Dezider API", description="Decision Intelligence by Venture Buddha")
api_router = APIRouter(prefix="/api")


# ========================
# IMPORT ALL ROUTE MODULES
# ========================

# -- Core routes (extracted from monolith) --
from routes.auth_routes import router as auth_router
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
from routes.solutions_store import router as solutions_store_router
from routes.google_calendar import router as google_calendar_router
from routes.deo import router as deo_router
from routes.cld import router as cld_router
from routes.time_dezider import router as time_dezider_router
from routes.payments import router as payments_router
from routes.gem_flight import router as gem_flight_router
from routes.consciousness_diary import router as consciousness_diary_router
from routes.pros_cons import router as pros_cons_router
from routes.swot import router as swot_router
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


# ========================
# MOUNT ALL ROUTERS
# ========================

# Core routes (no extra prefix — paths defined in each router)
api_router.include_router(auth_router)
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
api_router.include_router(solutions_store_router)
api_router.include_router(google_calendar_router)
api_router.include_router(deo_router)
api_router.include_router(cld_router)
api_router.include_router(time_dezider_router)
api_router.include_router(payments_router)
api_router.include_router(gem_flight_router)
api_router.include_router(consciousness_diary_router)
api_router.include_router(pros_cons_router)
api_router.include_router(swot_router)
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

# ========================
# HEALTH CHECK
# ========================

@api_router.get("/health")
async def health_check():
    return {"status": "ok", "service": "View Dezider API"}


# Mount the api_router onto the app
app.include_router(api_router)


# ========================
# MIDDLEWARE
# ========================

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ========================
# HEALTH CHECK
# ========================

@api_router.get("/health")
async def health_check():
    return {"status": "ok", "service": "View Dezider API"}


# ========================
# LIFECYCLE EVENTS
# ========================

from core.database import client

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()

# Mount static files for document downloads
app.mount("/api/static", StaticFiles(directory=str(ROOT_DIR / "static")), name="static")


# ========================
# LOGGING
# ========================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
