"""
Emotional Gatekeeper — View Dezider
Break the Trap. Break the Loop. Break the Limitation.
Analyze Outlets. Manage Addictions & Irritations.

Architecture:
  - constants.py         : Shared constants
  - models.py            : Pydantic models
  - ai_engine.py         : LLM-powered analysis
  - session_routes.py    : Session CRUD, commitments, journal, report, dashboard
  - trap_routes.py       : Breaking the Trap wizard endpoints
  - loop_routes.py       : Breaking the Loop wizard endpoints
  - limitation_routes.py : Breaking the Limitations wizard endpoints
  - outlet_aim_routes.py : Emotional Outlet Analyzer + AIM endpoints
"""

from fastapi import APIRouter

from .session_routes import router as session_router
from .trap_routes import router as trap_router
from .loop_routes import router as loop_router
from .limitation_routes import router as limitation_router
from .outlet_aim_routes import router as outlet_aim_router

router = APIRouter(prefix="/emotional-gatekeeper", tags=["Emotional Gatekeeper"])

router.include_router(session_router)
router.include_router(trap_router)
router.include_router(loop_router)
router.include_router(limitation_router)
router.include_router(outlet_aim_router)

__all__ = ["router"]
