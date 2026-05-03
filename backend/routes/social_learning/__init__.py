"""
Social Learning Engine — View Dezider
Converts real-world news into proactive decision guardrails.

3-Tier Knowledge Pyramid:
  Tier 1: Social Learning Template (user's personal, from news upload)
  Tier 2: Authorized Social Learning Template (admin-approved, public as-is)
  Tier 3: Social Solution Template (AI-synthesized from multiple Tier 2s, subscription-gated)

Pipeline: News → Language Detection → AI Classification → Factor Extraction → Template Generation

Input Modes:
  - Text (any of 6 supported languages)
  - File Upload (PDF, DOCX, TXT, Images with OCR)
  - Audio Upload (English only, modular STT engine)
  - URL Scraping (BeautifulSoup)

Architecture:
  This package was refactored from a single 1800-line file into clean modules:
  - constants.py     : Shared constants (life areas, org types, etc.)
  - models.py        : Pydantic request/response models
  - helpers.py       : Utility functions (IP extraction, admin check, template builder)
  - file_extraction.py : PDF/DOCX/Image text extraction
  - stt_engine.py    : Speech-to-Text engine with video audio extraction
  - ai_engine.py     : LLM classification and synthesis
  - upload_routes.py : Text, URL, file, audio/video upload endpoints
  - template_routes.py : Template CRUD, approval, re-analysis
  - admin_routes.py  : Admin approval workflow, Tier 3 synthesis
  - integration_routes.py : 3-tier factor/risk integration for decision & solution finder
  - stats_routes.py  : Statistics and filter options
"""

from fastapi import APIRouter

from .upload_routes import router as upload_router
from .template_routes import router as template_router
from .admin_routes import router as admin_router
from .integration_routes import router as integration_router
from .stats_routes import router as stats_router

# Main router — preserves the same prefix as the original monolith
router = APIRouter(prefix="/social-learning", tags=["Social Learning"])

# Include all sub-routers (no extra prefix, each route is defined relative to /social-learning)
router.include_router(upload_router)
router.include_router(template_router)
router.include_router(admin_router)
router.include_router(integration_router)
router.include_router(stats_router)

# Expose router for server.py import compatibility
__all__ = ["router"]
