"""
Shared Pydantic models, constants, and helper functions
used across all route modules in View Dezider.
"""

import uuid
import random
import os
import logging
import httpx
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, EmailStr
from passlib.context import CryptContext
from jose import jwt
from core.database import db

logger = logging.getLogger(__name__)

# JWT Configuration
SECRET_KEY = os.environ.get("SECRET_KEY", "view-dezider-secret-key-venture-buddha-2025")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 7

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ========================
# HELPER FUNCTIONS
# ========================

def generate_user_id():
    return f"user_{uuid.uuid4().hex[:12]}"

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


# ========================
# ROLE HIERARCHY
# ========================

ROLE_HIERARCHY = {
    "user": 0,
    "admin": 1,
    "co_admin": 2,
    "super_admin": 3,
}

ORG_ROLE_HIERARCHY = {
    "org_member": 0,
    "org_admin": 1,
    "org_co_admin": 2,
    "org_super_admin": 3,
}

def get_user_role(user: dict) -> str:
    return user.get("role", "user")

def get_role_level(role: str) -> int:
    return ROLE_HIERARCHY.get(role, 0)

def get_org_role_level(role: str) -> int:
    return ORG_ROLE_HIERARCHY.get(role, 0)


# ========================
# NOTIFICATION HELPERS
# ========================

async def send_expo_push(push_tokens: list, title: str, body: str, data: dict = None):
    """Send push notification via Expo Push API"""
    if not push_tokens:
        return
    messages = []
    for token in push_tokens:
        if not token or not token.startswith('ExponentPushToken'):
            continue
        messages.append({
            "to": token,
            "sound": "default",
            "title": title,
            "body": body,
            "data": data or {},
        })
    if not messages:
        return
    try:
        async with httpx.AsyncClient() as client:
            await client.post(
                "https://exp.host/--/api/v2/push/send",
                json=messages,
                headers={"Content-Type": "application/json"},
                timeout=10
            )
    except Exception as e:
        logger.error(f"Push notification error: {e}")


async def create_notification(user_id: str, notif_type: str, title: str, message: str, data: dict = None):
    """Helper function to create a notification and send push"""
    notif = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "type": notif_type,
        "title": title,
        "message": message,
        "data": data or {},
        "read": False,
        "created_at": datetime.now(timezone.utc),
    }
    await db.notifications.insert_one(notif)
    user_doc = await db.users.find_one({"user_id": user_id}, {"_id": 0})
    if user_doc and user_doc.get("push_token"):
        await send_expo_push([user_doc["push_token"]], title, message, data)
    return notif


# ========================
# DECISION FOLDERS (shared constant)
# ========================

DECISION_FOLDERS = [
    {"id": "career", "name": "Career & Business", "icon": "briefcase", "color": "#6C63FF"},
    {"id": "finance", "name": "Finance", "icon": "cash", "color": "#10B981"},
    {"id": "relationships", "name": "Relationships", "icon": "heart", "color": "#EF4444"},
    {"id": "health", "name": "Health & Wellness", "icon": "fitness", "color": "#F59E0B"},
    {"id": "education", "name": "Education", "icon": "school", "color": "#3B82F6"},
    {"id": "personal", "name": "Personal Growth", "icon": "rocket", "color": "#8B5CF6"},
    {"id": "lifestyle", "name": "Lifestyle", "icon": "home", "color": "#06B6D4"},
]


# Valid linked modules for journal entries
VALID_LINKED_MODULES = ["decision", "solution_finder", "solution_matrix", "gem", "ctt", "lifestyle"]
VALID_ENTRY_TYPES = ["reflection", "lesson_learned", "outcome_review", "decision_review", "general"]


# ========================
# PYDANTIC MODELS
# ========================

# --- Auth ---
class UserCreate(BaseModel):
    email: str
    password: str
    name: str
    org_id: Optional[str] = None

class UserLogin(BaseModel):
    email: str
    password: str

class SessionRequest(BaseModel):
    session_id: str

class ForgotPasswordRequest(BaseModel):
    email: str

class ResetPasswordRequest(BaseModel):
    email: str
    otp: str
    new_password: str

class SetPasswordRequest(BaseModel):
    new_password: str


# --- RBAC ---
class PromoteUserRequest(BaseModel):
    email: str
    role: str

class DemoteUserRequest(BaseModel):
    email: str


# --- Decisions ---
class Factor(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    category: str = "primary"
    rating: int = 0
    order: int = 0

class OptionAssessment(BaseModel):
    factor_id: str
    percentage: Optional[float] = None
    unit_value: Optional[str] = None
    assessment_mode: Optional[str] = None

class Option(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    assessments: List[OptionAssessment] = []
    worth_percentage: float = 0.0

class PRRDecisionCreate(BaseModel):
    title: str
    context: str = ""
    folder: str = ""
    life_area: str = ""
    decision_type: str = ""
    implementation_review_date: Optional[datetime] = None

class PRRDecisionUpdate(BaseModel):
    title: Optional[str] = None
    context: Optional[str] = None
    factors: Optional[List[Factor]] = None
    options: Optional[List[Option]] = None
    chosen_option_id: Optional[str] = None
    decision_case: Optional[int] = None
    notes: Optional[str] = None
    reflection: Optional[str] = None
    final_notes: Optional[str] = None
    status: Optional[str] = None
    folder: Optional[str] = None
    life_area: Optional[str] = None
    decision_type: Optional[str] = None
    implementation_review_date: Optional[datetime] = None
    mpps_option_id: Optional[str] = None
    mpps_improvements: Optional[List[dict]] = None
    mpps_timeframe: Optional[str] = None
    mpps_projected_worth: Optional[float] = None

class PRRDecision(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    title: str
    context: str = ""
    factors: List[Factor] = []
    options: List[Option] = []
    chosen_option_id: Optional[str] = None
    decision_case: Optional[int] = None
    notes: str = ""
    reflection: str = ""
    final_notes: str = ""
    status: str = "draft"
    folder: str = ""
    life_area: str = ""
    decision_type: str = ""
    implementation_review_date: Optional[datetime] = None
    mpps_option_id: Optional[str] = None
    mpps_improvements: List[dict] = []
    mpps_timeframe: Optional[str] = None
    mpps_projected_worth: Optional[float] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CloneDecisionRequest(BaseModel):
    title: str
    clone_level: str  # "factors", "classification", "prioritization", "options", "assessment"


# --- Templates ---
class SaveTemplateRequest(BaseModel):
    name: str
    template_type: str = "options"
    visibility: str = "private"
    shared_with: List[str] = []

class UseTemplateRequest(BaseModel):
    title: str


# --- Test123 ---
class Test123Create(BaseModel):
    situation: str

class Test123Update(BaseModel):
    options: Optional[List[str]] = None
    chosen_option: Optional[str] = None
    confidence: Optional[int] = None
    notes: Optional[str] = None

class Test123Session(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    situation: str
    options: List[str] = []
    chosen_option: Optional[str] = None
    confidence: Optional[int] = None
    notes: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# --- Mode Assessment ---
class ModeAssessmentCreate(BaseModel):
    answers: Dict[str, float]

class ModeAssessmentResult(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    answers: Dict[str, float]
    dominant_mode: str
    mode_scores: Dict[str, float]
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# --- Journal ---
class JournalEntryCreate(BaseModel):
    decision_title: str
    decision_description: str = ""
    linked_module: Optional[str] = None
    linked_id: Optional[str] = None
    linked_title: Optional[str] = None
    entry_type: Optional[str] = None
    decision_date: Optional[datetime] = None

class JournalEntryUpdate(BaseModel):
    decision_title: Optional[str] = None
    decision_description: Optional[str] = None
    outcome: Optional[str] = None
    lessons_learned: Optional[str] = None
    satisfaction_rating: Optional[int] = None
    status: Optional[str] = None
    updated_at: Optional[datetime] = None

class JournalEntry(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    decision_title: str
    decision_description: str = ""
    outcome: str = ""
    lessons_learned: str = ""
    satisfaction_rating: Optional[int] = None
    linked_module: Optional[str] = None
    linked_id: Optional[str] = None
    linked_title: Optional[str] = None
    entry_type: Optional[str] = None
    decision_date: Optional[datetime] = None
    status: str = "active"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# --- Sharing ---
class ShareStepRequest(BaseModel):
    step_number: int
    recipient_emails: List[str]
    merge_mode: str = "equal"
    custom_weights: Optional[Dict[str, float]] = None
    message: str = ""

class ContributeStepRequest(BaseModel):
    factors: Optional[List[dict]] = None
    options: Optional[List[dict]] = None
    assessments: Optional[Dict[str, Any]] = None
    note: str = ""

class MergeStepRequest(BaseModel):
    merge_mode: Optional[str] = None
    custom_weights: Optional[Dict[str, float]] = None


# --- Decision Templates (admin-curated) ---
class DecisionTemplate(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    life_area: str
    decision_type: str
    description: str = ""
    factors: List[Factor] = []
    created_by: str = ""
    submitted_by: Optional[str] = None
    submitted_by_name: Optional[str] = None
    is_approved: bool = False
    is_official: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class DecisionTemplateCreate(BaseModel):
    name: str
    life_area: str
    decision_type: str
    description: str = ""
    factors: List[Factor] = []
