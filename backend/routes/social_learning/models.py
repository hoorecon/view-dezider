"""
Social Learning Engine — Pydantic Models
Request/response models for the Social Learning API.
"""

from typing import Optional, List
from pydantic import BaseModel


class NewsUploadRequest(BaseModel):
    content: str  # News text in any supported language
    source_url: Optional[str] = None
    source_name: Optional[str] = None
    title: Optional[str] = None


class UrlUploadRequest(BaseModel):
    url: str
    title: Optional[str] = None
    source_name: Optional[str] = None


class AdminApprovalRequest(BaseModel):
    status: str  # "authorized" or "rejected"
    admin_notes: Optional[str] = ""


class SynthesizeRequest(BaseModel):
    template_ids: List[str]  # List of Authorized Social Learning Template IDs to synthesize
    target_region: Optional[str] = None
    target_org_type: Optional[str] = None
    target_life_area: Optional[str] = None


class FactorApprovalRequest(BaseModel):
    approved_factor_indices: List[int] = []  # indices of factors user approves
    modified_factors: Optional[List[dict]] = None  # user-modified factors


class RiskApprovalRequest(BaseModel):
    approved_risk_indices: List[int] = []
    modified_risks: Optional[List[dict]] = None


class ReAnalyzeRequest(BaseModel):
    additional_context: str
    focus_area: Optional[str] = None  # "factors", "risks", "both"
