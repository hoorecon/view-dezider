from fastapi import FastAPI, APIRouter, HTTPException, Request, Response, Depends
from fastapi.responses import JSONResponse, StreamingResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timezone, timedelta
import random
import httpx
from passlib.context import CryptContext
from jose import JWTError, jwt

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# JWT Configuration
SECRET_KEY = os.environ.get("SECRET_KEY", "view-dezider-secret-key-venture-buddha-2025")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 7

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Create the main app
app = FastAPI(title="View Dezider API", description="Decision Intelligence by Venture Buddha")

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# ========================
# MODELS
# ========================

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    name: str
    org_id: Optional[str] = None  # Multi-tenant: organization ID

class UserLogin(BaseModel):
    email: EmailStr
    password: str
    org_id: Optional[str] = None  # Multi-tenant: organization ID

class UserResponse(BaseModel):
    user_id: str
    email: str
    name: str
    picture: Optional[str] = None
    auth_method: str  # "google" or "email"
    created_at: datetime

class SessionRequest(BaseModel):
    session_id: str

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    email: EmailStr
    otp: str
    new_password: str

class SetPasswordRequest(BaseModel):
    new_password: str

# PRR Decision Models
class Factor(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    category: str  # "primary" or "secondary"
    rating: int  # 1-100 importance rating
    order: int
    unit: Optional[str] = None  # Measurement unit (e.g., "USD", "hours", "km")
    expected_value: Optional[Any] = None  # Benchmark value (numeric or text)
    data_type: Optional[str] = None  # 'numeric' or 'text' (auto-sensed)
    operator: Optional[str] = None  # >=, <=, >, <, =, !=, between, contains, starts_with, ends_with, equals, not_equals
    gap_multiplier: Optional[float] = 1.0  # Per-factor gap from the one below (default 1x = standard gap of 10)
    parent_id: Optional[str] = None  # ID of parent factor (null = top-level, set = sub-factor)
    weight: Optional[float] = None  # Sub-factor weight as % of parent (0-100, sub-factors must sum to 100)

class OptionAssessment(BaseModel):
    factor_id: str
    percentage: Optional[int] = None  # 0-100 how well option meets this factor
    unit_value: Optional[str] = None  # Legacy: combined value+unit string
    actual_value: Optional[float] = None  # Separated numeric value for AI/ML
    assessment_mode: Optional[str] = None  # 'L', 'M', 'H', or 'custom'

class MPPSActionItem(BaseModel):
    assignee_name: str = ""
    assignee_email: str = ""
    assignee_mobile: str = ""
    task: str = ""  # Does What?
    deadline: Optional[str] = None  # By When?

class MPPSImprovement(BaseModel):
    factor_id: str
    original_percentage: Optional[int] = None  # Original assessment %
    projected_percentage: Optional[int] = None  # Projected improved %
    delta_percentage: Optional[int] = None  # Auto: projected - original
    expected_value: Optional[str] = None  # Target value to achieve delta
    expected_unit: Optional[str] = None  # Unit for the expected value
    improvement_plan: str = ""  # How to improve this factor
    tepfi_elements: List[str] = []  # Multiple TEPFI: T, E, P, F, I
    tepfi_layer: Optional[str] = None  # self, micro, or macro
    action_items: List[MPPSActionItem] = []  # Who does what by when

class DecisionOption(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    assessments: List[OptionAssessment] = []
    worth_percentage: float = 0.0

class PRRDecision(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    title: str
    context: str
    factors: List[Factor] = []
    options: List[DecisionOption] = []
    chosen_option_id: Optional[str] = None
    decision_case: Optional[str] = None  # "obvious", "trial", "unavoidable"
    notes: str = ""
    reflection: str = ""
    final_notes: str = ""
    folder: str = ""
    life_area: Optional[str] = None  # Career, Finance, Health, Relationships, Education, etc.
    decision_type: Optional[str] = None  # problem, need, aspiration
    rating_gap_multiplier: float = 1.0  # Gap multiplier: 0.25, 0.5, 0.75, 1.0 (standard), 1.5, 2.0, 3.0, 4.0, 5.0
    mpps_option_id: Optional[str] = None  # Option being analyzed for MPPS
    mpps_improvements: List[MPPSImprovement] = []  # Factor improvement plans
    mpps_projected_worth: Optional[float] = None  # Projected worth after improvements
    mpps_timeframe: Optional[str] = None  # Common timeframe for MPPS (e.g., "3 months")
    status: str = "draft"  # "draft", "in_progress", "completed"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class PRRDecisionCreate(BaseModel):
    title: str
    context: str
    folder: str = ""
    life_area: Optional[str] = None  # Career, Finance, Health, Relationships, Education, etc.
    decision_type: Optional[str] = None  # problem, need, aspiration

class PRRDecisionUpdate(BaseModel):
    title: Optional[str] = None
    context: Optional[str] = None
    factors: Optional[List[Factor]] = None
    options: Optional[List[DecisionOption]] = None
    chosen_option_id: Optional[str] = None
    decision_case: Optional[str] = None
    notes: Optional[str] = None
    reflection: Optional[str] = None
    final_notes: Optional[str] = None
    folder: Optional[str] = None
    rating_gap_multiplier: Optional[float] = None
    mpps_option_id: Optional[str] = None
    mpps_improvements: Optional[List[MPPSImprovement]] = None
    mpps_projected_worth: Optional[float] = None
    mpps_timeframe: Optional[str] = None
    life_area: Optional[str] = None
    decision_type: Optional[str] = None
    status: Optional[str] = None

class CloneDecisionRequest(BaseModel):
    title: str
    clone_level: str  # "factors", "classification", "prioritization", "options", "assessment"

class SaveTemplateRequest(BaseModel):
    name: str
    template_type: str  # "options" or "assessment"
    visibility: str = "private"  # "private", "shared", "public"
    shared_with: List[str] = []  # list of email addresses for "shared" visibility

class UseTemplateRequest(BaseModel):
    title: str

# Step Sharing Models
class ShareStepRequest(BaseModel):
    decision_id: str
    step_number: int
    recipient_emails: List[str]
    merge_mode: str = "equal"  # "equal", "self_weighted", "custom"
    custom_weights: Optional[dict] = None  # { "user_id": weight_percent }
    message: str = ""

class ContributeStepRequest(BaseModel):
    factors: Optional[List[dict]] = None
    options: Optional[List[dict]] = None
    assessments: Optional[dict] = None
    note: str = ""

class MergeStepRequest(BaseModel):
    merge_mode: str = "equal"
    custom_weights: Optional[dict] = None

# Decision Folder Constants
DECISION_FOLDERS = [
    {"id": "holistic_health", "name": "Holistic Health", "icon": "fitness", "color": "#10B981"},
    {"id": "knowledge_skills", "name": "Knowledge & Skills", "icon": "book", "color": "#3B82F6"},
    {"id": "relationships", "name": "Relationships", "icon": "heart", "color": "#EC4899"},
    {"id": "finance", "name": "Finance", "icon": "cash", "color": "#F59E0B"},
    {"id": "assets", "name": "Assets", "icon": "home", "color": "#8B5CF6"},
    {"id": "career", "name": "Career", "icon": "briefcase", "color": "#6366F1"},
    {"id": "hobbies_entertainment", "name": "Hobbies & Entertainment", "icon": "game-controller", "color": "#14B8A6"},
    {"id": "social_image", "name": "Social Image & Influence", "icon": "star", "color": "#F97316"},
    {"id": "social_contributions", "name": "Social Contributions", "icon": "people", "color": "#06B6D4"},
    {"id": "spirituality_religion", "name": "Spirituality & Religion", "icon": "leaf", "color": "#A855F7"},
]

# Admin Models
ROLE_HIERARCHY = {"super_admin": 3, "co_admin": 2, "admin": 1, "user": 0}

# Org-level Role Hierarchy (mirrors global roles within an organization)
ORG_ROLE_HIERARCHY = {"org_super_admin": 3, "org_co_admin": 2, "org_admin": 1, "org_member": 0}
ORG_ADMIN_ROLES = ["org_admin", "org_co_admin", "org_super_admin"]

def get_org_role_level(role: str) -> int:
    return ORG_ROLE_HIERARCHY.get(role, 0)

# Notification Models
class NotificationCreate(BaseModel):
    user_id: str
    type: str  # "share_invite", "share_contributed", "share_merged", "system"
    title: str
    message: str
    data: Optional[dict] = None  # Extra data like share_id, decision_id

class PromoteUserRequest(BaseModel):
    email: EmailStr
    role: str  # "admin" or "co_admin"

class DemoteUserRequest(BaseModel):
    email: EmailStr

# Test123 Models
class Test123Session(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    situation: str
    is_emotional: Optional[bool] = None
    what_i_want: str = ""
    worst_case_scenario: str = ""
    ready_for_worst: Optional[bool] = None
    all_needs: List[str] = []
    important_needs: List[str] = []
    action_plan: str = ""
    final_decision: str = ""
    completed_test: int = 0  # 1, 2, or 3
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class Test123Create(BaseModel):
    situation: str

class Test123Update(BaseModel):
    is_emotional: Optional[bool] = None
    what_i_want: Optional[str] = None
    worst_case_scenario: Optional[str] = None
    ready_for_worst: Optional[bool] = None
    all_needs: Optional[List[str]] = None
    important_needs: Optional[List[str]] = None
    action_plan: Optional[str] = None
    final_decision: Optional[str] = None
    completed_test: Optional[int] = None

# Decision Mode Assessment Models
class ModeAssessmentResult(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    answers: Dict[str, int]  # question_id -> score
    dominant_mode: str  # "emotional", "logical", "intuitive", "awareness"
    mode_scores: Dict[str, float]
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class ModeAssessmentCreate(BaseModel):
    answers: Dict[str, int]

# Decision Journal Models
class JournalEntry(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    decision_title: str
    decision_description: str
    outcome: str = ""
    outcome_rating: int = 0  # 1-5
    lessons_learned: str = ""
    failure_reasons: List[str] = []  # from the 5 reasons in the book
    status: str = "pending"  # "pending", "completed"
    decision_date: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    outcome_date: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class JournalEntryCreate(BaseModel):
    decision_title: str
    decision_description: str
    decision_date: Optional[datetime] = None

class JournalEntryUpdate(BaseModel):
    decision_title: Optional[str] = None
    decision_description: Optional[str] = None
    outcome: Optional[str] = None
    outcome_rating: Optional[int] = None
    lessons_learned: Optional[str] = None
    failure_reasons: Optional[List[str]] = None
    status: Optional[str] = None
    outcome_date: Optional[datetime] = None

# ========================
# HELPER FUNCTIONS
# ========================

def generate_user_id():
    return f"user_{uuid.uuid4().hex[:12]}"

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(request: Request) -> dict:
    """Extract and validate user from session token (cookie or header)"""
    session_token = None
    
    # Try cookie first
    session_token = request.cookies.get("session_token")
    
    # Then try Authorization header
    if not session_token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            session_token = auth_header[7:]
    
    if not session_token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    # Check session in database
    session_doc = await db.user_sessions.find_one(
        {"session_token": session_token},
        {"_id": 0}
    )
    
    if not session_doc:
        raise HTTPException(status_code=401, detail="Invalid session")
    
    # Check expiry
    expires_at = session_doc["expires_at"]
    if isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Session expired")
    
    # Get user
    user_doc = await db.users.find_one(
        {"user_id": session_doc["user_id"]},
        {"_id": 0}
    )
    
    if not user_doc:
        raise HTTPException(status_code=401, detail="User not found")
    
    return user_doc

def get_user_role(user: dict) -> str:
    """Get user's role, defaulting to 'user'"""
    return user.get("role", "user")

def get_role_level(role: str) -> int:
    """Get numeric level for role comparison"""
    return ROLE_HIERARCHY.get(role, 0)

async def require_admin(user: dict = Depends(get_current_user)):
    """Require at least admin role"""
    role = get_user_role(user)
    if get_role_level(role) < 1:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user

async def require_co_admin(user: dict = Depends(get_current_user)):
    """Require at least co_admin role"""
    role = get_user_role(user)
    if get_role_level(role) < 2:
        raise HTTPException(status_code=403, detail="Co-Admin access required")
    return user

async def require_super_admin(user: dict = Depends(get_current_user)):
    """Require super_admin role"""
    role = get_user_role(user)
    if get_role_level(role) < 3:
        raise HTTPException(status_code=403, detail="Super Admin access required")
    return user

# ========================
# AUTH ROUTES
# ========================

@api_router.post("/auth/register")
async def register(user_data: UserCreate, response: Response):
    """Register a new user with email/password"""
    # Check if email already exists
    existing_user = await db.users.find_one({"email": user_data.email}, {"_id": 0})
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    user_id = generate_user_id()
    hashed_password = hash_password(user_data.password)
    
    user_doc = {
        "user_id": user_id,
        "email": user_data.email,
        "name": user_data.name,
        "password_hash": hashed_password,
        "picture": None,
        "auth_method": "email",
        "org_id": user_data.org_id,
        "org_role": "org_member" if user_data.org_id else None,
        "created_at": datetime.now(timezone.utc)
    }
    
    await db.users.insert_one(user_doc)
    
    # Create session
    session_token = f"session_{uuid.uuid4().hex}"
    session_doc = {
        "user_id": user_id,
        "session_token": session_token,
        "expires_at": datetime.now(timezone.utc) + timedelta(days=7),
        "created_at": datetime.now(timezone.utc)
    }
    await db.user_sessions.insert_one(session_doc)
    
    # Set cookie
    response.set_cookie(
        key="session_token",
        value=session_token,
        httponly=True,
        secure=True,
        samesite="none",
        path="/",
        max_age=7*24*60*60
    )
    
    return {
        "user_id": user_id,
        "email": user_data.email,
        "name": user_data.name,
        "picture": None,
        "auth_method": "email",
        "session_token": session_token
    }

@api_router.post("/auth/login")
async def login(user_data: UserLogin, response: Response):
    """Login with email/password"""
    user_doc = await db.users.find_one({"email": user_data.email}, {"_id": 0})
    
    if not user_doc:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    if user_doc.get("auth_method") == "google" and not user_doc.get("password_hash"):
        raise HTTPException(status_code=400, detail="This account uses Google Sign-In. Please login with Google.")
    
    if not verify_password(user_data.password, user_doc.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    # Create session
    session_token = f"session_{uuid.uuid4().hex}"
    session_doc = {
        "user_id": user_doc["user_id"],
        "session_token": session_token,
        "expires_at": datetime.now(timezone.utc) + timedelta(days=7),
        "created_at": datetime.now(timezone.utc)
    }
    await db.user_sessions.insert_one(session_doc)
    
    # Set cookie
    response.set_cookie(
        key="session_token",
        value=session_token,
        httponly=True,
        secure=True,
        samesite="none",
        path="/",
        max_age=7*24*60*60
    )
    
    return {
        "user_id": user_doc["user_id"],
        "email": user_doc["email"],
        "name": user_doc["name"],
        "picture": user_doc.get("picture"),
        "auth_method": user_doc["auth_method"],
        "org_id": user_doc.get("org_id"),
        "session_token": session_token
    }

@api_router.post("/auth/google/session")
async def google_session(session_data: SessionRequest, response: Response):
    """
    Exchange Google OAuth session_id for user data and create session
    REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
    """
    try:
        async with httpx.AsyncClient() as client_http:
            res = await client_http.get(
                "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data",
                headers={"X-Session-ID": session_data.session_id}
            )
            
            if res.status_code != 200:
                raise HTTPException(status_code=401, detail="Invalid session ID")
            
            google_data = res.json()
    except Exception as e:
        logging.error(f"Error fetching Google session: {e}")
        raise HTTPException(status_code=401, detail="Failed to validate Google session")
    
    email = google_data.get("email")
    name = google_data.get("name")
    picture = google_data.get("picture")
    
    # Check if user exists
    existing_user = await db.users.find_one({"email": email}, {"_id": 0})
    
    if existing_user:
        user_id = existing_user["user_id"]
        # Update user info if needed
        await db.users.update_one(
            {"email": email},
            {"$set": {"name": name, "picture": picture}}
        )
    else:
        user_id = generate_user_id()
        user_doc = {
            "user_id": user_id,
            "email": email,
            "name": name,
            "picture": picture,
            "auth_method": "google",
            "created_at": datetime.now(timezone.utc)
        }
        await db.users.insert_one(user_doc)
    
    # Create session
    session_token = f"session_{uuid.uuid4().hex}"
    session_doc = {
        "user_id": user_id,
        "session_token": session_token,
        "expires_at": datetime.now(timezone.utc) + timedelta(days=7),
        "created_at": datetime.now(timezone.utc)
    }
    await db.user_sessions.insert_one(session_doc)
    
    # Set cookie
    response.set_cookie(
        key="session_token",
        value=session_token,
        httponly=True,
        secure=True,
        samesite="none",
        path="/",
        max_age=7*24*60*60
    )
    
    return {
        "user_id": user_id,
        "email": email,
        "name": name,
        "picture": picture,
        "auth_method": "google",
        "session_token": session_token
    }

@api_router.get("/auth/me")
async def get_me(user: dict = Depends(get_current_user)):
    """Get current authenticated user"""
    return {
        "user_id": user["user_id"],
        "email": user["email"],
        "name": user["name"],
        "picture": user.get("picture"),
        "auth_method": user.get("auth_method", "email"),
        "has_password": bool(user.get("password_hash")),
        "role": user.get("role", "user"),
        "org_id": user.get("org_id"),
        "org_role": user.get("org_role"),
    }

@api_router.post("/auth/logout")
async def logout(request: Request, response: Response):
    """Logout user and clear session"""
    session_token = request.cookies.get("session_token")
    
    if session_token:
        await db.user_sessions.delete_one({"session_token": session_token})
    
    response.delete_cookie(key="session_token", path="/")
    return {"message": "Logged out successfully"}

@api_router.post("/auth/forgot-password")
async def forgot_password(data: ForgotPasswordRequest):
    """Generate OTP for password reset"""
    user_doc = await db.users.find_one({"email": data.email}, {"_id": 0})
    
    if not user_doc:
        raise HTTPException(status_code=404, detail="No account found with this email")
    
    if user_doc.get("auth_method") == "google" and not user_doc.get("password_hash"):
        raise HTTPException(status_code=400, detail="This account uses Google Sign-In. Please login with Google or set a password from your profile.")
    
    # Generate 6-digit OTP
    otp = str(random.randint(100000, 999999))
    
    # Store OTP with 10-minute expiry
    await db.password_resets.delete_many({"email": data.email})  # Remove old OTPs
    await db.password_resets.insert_one({
        "email": data.email,
        "otp": otp,
        "expires_at": datetime.now(timezone.utc) + timedelta(minutes=10),
        "created_at": datetime.now(timezone.utc),
    })
    
    # In production, send OTP via email. For MVP, return in response.
    return {
        "message": "OTP generated successfully",
        "otp": otp,  # MVP only - remove in production
        "expires_in_minutes": 10,
    }

@api_router.post("/auth/reset-password")
async def reset_password(data: ResetPasswordRequest):
    """Reset password using OTP"""
    # Find valid OTP
    reset_doc = await db.password_resets.find_one({
        "email": data.email,
        "otp": data.otp,
    })
    
    if not reset_doc:
        raise HTTPException(status_code=400, detail="Invalid OTP code")
    
    # Check expiry
    expires_at = reset_doc["expires_at"]
    if isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        await db.password_resets.delete_one({"_id": reset_doc["_id"]})
        raise HTTPException(status_code=400, detail="OTP has expired. Please request a new one.")
    
    if len(data.new_password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    
    # Update password
    hashed_password = hash_password(data.new_password)
    await db.users.update_one(
        {"email": data.email},
        {"$set": {"password_hash": hashed_password}}
    )
    
    # Clean up OTP
    await db.password_resets.delete_many({"email": data.email})
    
    return {"message": "Password reset successfully. You can now login with your new password."}

@api_router.post("/auth/set-password")
async def set_password(data: SetPasswordRequest, user: dict = Depends(get_current_user)):
    """Set password for Google-authenticated users (or change existing password)"""
    if len(data.new_password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    
    hashed_password = hash_password(data.new_password)
    
    # Update user with password and set auth_method to allow both
    update_fields = {"password_hash": hashed_password}
    
    # If user was Google-only, update auth_method to indicate both are available
    if user.get("auth_method") == "google":
        update_fields["auth_method"] = "google_and_email"
    
    await db.users.update_one(
        {"user_id": user["user_id"]},
        {"$set": update_fields}
    )
    
    return {"message": "Password set successfully. You can now also login with email and password."}

# ========================
# ORGANIZATION ROUTES (Multi-Tenant SaaS)
# ========================

@api_router.post("/organizations")
async def create_organization(request: Request, user: dict = Depends(get_current_user)):
    """Create a new organization (super_admin or any user creating their first org)"""
    body = await request.json()
    name = body.get("name", "").strip()
    slug = body.get("slug", "").strip().lower().replace(" ", "-")
    if not name or not slug:
        raise HTTPException(status_code=400, detail="Name and slug are required")
    # Check slug uniqueness
    existing = await db.organizations.find_one({"slug": slug})
    if existing:
        raise HTTPException(status_code=400, detail="Organization slug already taken")
    org_doc = {
        "id": str(uuid.uuid4()),
        "name": name,
        "slug": slug,
        "logo_url": body.get("logo_url", ""),
        "primary_color": body.get("primary_color", "#6C63FF"),
        "accent_color": body.get("accent_color", "#FF6584"),
        "tagline": body.get("tagline", ""),
        "created_by": user["user_id"],
        "created_at": datetime.now(timezone.utc),
    }
    await db.organizations.insert_one(org_doc)
    # Assign creator to org with org_super_admin role
    await db.users.update_one(
        {"user_id": user["user_id"]},
        {"$set": {"org_id": org_doc["id"], "org_role": "org_super_admin"}}
    )
    return {"id": org_doc["id"], "slug": slug, "message": "Organization created"}

@api_router.get("/organizations/{slug}")
async def get_organization_by_slug(slug: str):
    """Get organization branding by slug (public endpoint for login screen)"""
    org = await db.organizations.find_one({"slug": slug}, {"_id": 0})
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    # Return public branding info only
    return {
        "id": org["id"],
        "name": org["name"],
        "slug": org["slug"],
        "logo_url": org.get("logo_url", ""),
        "primary_color": org.get("primary_color", "#6C63FF"),
        "accent_color": org.get("accent_color", "#FF6584"),
        "tagline": org.get("tagline", ""),
    }

@api_router.put("/organizations/{org_id}")
async def update_organization(org_id: str, request: Request, user: dict = Depends(get_current_user)):
    """Update organization branding (org_admin+ or global admin)"""
    user_doc = await db.users.find_one({"user_id": user["user_id"]}, {"_id": 0})
    if user_doc.get("org_id") != org_id:
        raise HTTPException(status_code=403, detail="Not a member of this organization")
    org_role = user_doc.get("org_role", "org_member")
    global_role = get_user_role(user_doc)
    # Allow if org_admin+ or global admin
    if get_org_role_level(org_role) < 1 and get_role_level(global_role) < 1:
        raise HTTPException(status_code=403, detail="Org Admin access required")
    body = await request.json()
    update_fields = {k: v for k, v in body.items() if k in ["name", "logo_url", "primary_color", "accent_color", "tagline"]}
    if update_fields:
        await db.organizations.update_one({"id": org_id}, {"$set": update_fields})
    return {"message": "Organization updated"}

@api_router.get("/organizations/{org_id}/members")
async def get_org_members(org_id: str, user: dict = Depends(get_current_user)):
    """Get members of an organization with org roles"""
    user_doc = await db.users.find_one({"user_id": user["user_id"]}, {"_id": 0})
    if user_doc.get("org_id") != org_id:
        raise HTTPException(status_code=403, detail="Not a member of this organization")
    members = await db.users.find(
        {"org_id": org_id},
        {"_id": 0, "password_hash": 0}
    ).to_list(200)
    # Ensure each member has org_role
    for m in members:
        if not m.get("org_role"):
            # Check if creator
            org = await db.organizations.find_one({"id": org_id})
            if org and m.get("user_id") == org.get("created_by"):
                m["org_role"] = "org_super_admin"
                await db.users.update_one({"user_id": m["user_id"]}, {"$set": {"org_role": "org_super_admin"}})
            else:
                m["org_role"] = "org_member"
    return members

@api_router.put("/organizations/{org_id}/members/{target_user_id}/role")
async def update_org_member_role(org_id: str, target_user_id: str, request: Request, user: dict = Depends(get_current_user)):
    """Promote/demote org member role (org_admin+ only)"""
    # Verify promoter is in org and has admin level
    promoter = await db.users.find_one({"user_id": user["user_id"]}, {"_id": 0})
    if promoter.get("org_id") != org_id:
        raise HTTPException(status_code=403, detail="Not a member of this organization")

    promoter_org_role = promoter.get("org_role", "org_member")
    promoter_level = get_org_role_level(promoter_org_role)

    if promoter_level < 1:
        raise HTTPException(status_code=403, detail="Org Admin access required")

    # Get target user
    target = await db.users.find_one({"user_id": target_user_id, "org_id": org_id}, {"_id": 0})
    if not target:
        raise HTTPException(status_code=404, detail="User not found in this organization")

    body = await request.json()
    new_role = body.get("org_role", "").strip()
    if new_role not in ORG_ROLE_HIERARCHY:
        raise HTTPException(status_code=400, detail=f"Invalid org role. Must be one of: {list(ORG_ROLE_HIERARCHY.keys())}")

    new_role_level = get_org_role_level(new_role)
    target_current_level = get_org_role_level(target.get("org_role", "org_member"))

    # Can't modify yourself
    if target_user_id == user["user_id"]:
        raise HTTPException(status_code=400, detail="Cannot change your own org role")

    # Can't promote to equal or higher than own level
    if new_role_level >= promoter_level:
        raise HTTPException(status_code=403, detail="Cannot promote to a role equal or higher than your own")

    # Can't modify someone at equal or higher level
    if target_current_level >= promoter_level:
        raise HTTPException(status_code=403, detail="Cannot modify a user with equal or higher org role")

    # Only org_super_admin can create org_co_admin
    if new_role == "org_co_admin" and promoter_org_role != "org_super_admin":
        raise HTTPException(status_code=403, detail="Only Org Super Admin can assign Org Co-Admin role")

    await db.users.update_one(
        {"user_id": target_user_id},
        {"$set": {"org_role": new_role}}
    )
    return {"message": f"User org role updated to {new_role}"}

@api_router.delete("/organizations/{org_id}/members/{target_user_id}")
async def remove_org_member(org_id: str, target_user_id: str, user: dict = Depends(get_current_user)):
    """Remove a member from the organization (org_admin+ only)"""
    remover = await db.users.find_one({"user_id": user["user_id"]}, {"_id": 0})
    if remover.get("org_id") != org_id:
        raise HTTPException(status_code=403, detail="Not a member of this organization")

    remover_level = get_org_role_level(remover.get("org_role", "org_member"))
    if remover_level < 1:
        raise HTTPException(status_code=403, detail="Org Admin access required")

    target = await db.users.find_one({"user_id": target_user_id, "org_id": org_id}, {"_id": 0})
    if not target:
        raise HTTPException(status_code=404, detail="User not found in this organization")

    if target_user_id == user["user_id"]:
        raise HTTPException(status_code=400, detail="Cannot remove yourself from the organization")

    target_level = get_org_role_level(target.get("org_role", "org_member"))
    if target_level >= remover_level:
        raise HTTPException(status_code=403, detail="Cannot remove a user with equal or higher org role")

    await db.users.update_one(
        {"user_id": target_user_id},
        {"$set": {"org_id": None, "org_role": None}}
    )
    return {"message": "Member removed from organization"}


# ========================
# PRR DECISION ROUTES
# ========================

@api_router.post("/decisions", response_model=dict)
async def create_decision(decision: PRRDecisionCreate, user: dict = Depends(get_current_user)):
    """Create a new PRR decision"""
    # Get user's org_id for data isolation
    user_doc = await db.users.find_one({"user_id": user["user_id"]}, {"_id": 0})
    org_id = user_doc.get("org_id") if user_doc else None
    
    decision_doc = PRRDecision(
        user_id=user["user_id"],
        title=decision.title,
        context=decision.context,
        folder=decision.folder
    )
    doc_dict = decision_doc.dict()
    doc_dict["org_id"] = org_id  # Multi-tenant data isolation
    
    await db.decisions.insert_one(doc_dict)
    return {"id": decision_doc.id, "message": "Decision created successfully"}

@api_router.get("/decisions", response_model=List[dict])
async def get_decisions(user: dict = Depends(get_current_user), folder: str = None):
    """Get all decisions for the current user, optionally filtered by folder"""
    query = {"user_id": user["user_id"]}
    if folder:
        query["folder"] = folder
    decisions = await db.decisions.find(
        query,
        {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    return decisions

@api_router.get("/decisions/{decision_id}")
async def get_decision(decision_id: str, user: dict = Depends(get_current_user)):
    """Get a specific decision"""
    decision = await db.decisions.find_one(
        {"id": decision_id, "user_id": user["user_id"]},
        {"_id": 0}
    )
    if not decision:
        raise HTTPException(status_code=404, detail="Decision not found")
    return decision

@api_router.put("/decisions/{decision_id}")
async def update_decision(decision_id: str, update_data: PRRDecisionUpdate, user: dict = Depends(get_current_user)):
    """Update a decision"""
    # Check ownership
    existing = await db.decisions.find_one(
        {"id": decision_id, "user_id": user["user_id"]},
        {"_id": 0}
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Decision not found")
    
    update_dict = {k: v for k, v in update_data.dict().items() if v is not None}
    update_dict["updated_at"] = datetime.now(timezone.utc)
    
    # Calculate worth percentages if factors and options are provided
    if "options" in update_dict and "factors" in update_dict:
        factors = update_dict["factors"]
        options = update_dict["options"]
        
        total_rating = sum(f["rating"] for f in factors)
        
        for option in options:
            if total_rating > 0:
                worth = 0.0
                for assessment in option.get("assessments", []):
                    factor = next((f for f in factors if f["id"] == assessment["factor_id"]), None)
                    if factor:
                        # Clamp individual assessment percentage to 0-100
                        pct = assessment.get("percentage") or 0
                        clamped_pct = max(0, min(100, pct))
                        assessment["percentage"] = clamped_pct
                        worth += (factor["rating"] / total_rating) * clamped_pct
                # Cap total worth at 100%
                option["worth_percentage"] = round(min(100.0, max(0.0, worth)), 2)
            else:
                option["worth_percentage"] = 0.0
    
    await db.decisions.update_one(
        {"id": decision_id},
        {"$set": update_dict}
    )
    
    return {"message": "Decision updated successfully"}

@api_router.delete("/decisions/{decision_id}")
async def delete_decision(decision_id: str, user: dict = Depends(get_current_user)):
    """Delete a decision"""
    result = await db.decisions.delete_one(
        {"id": decision_id, "user_id": user["user_id"]}
    )
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Decision not found")
    return {"message": "Decision deleted successfully"}

@api_router.post("/decisions/{decision_id}/clone")
async def clone_decision(decision_id: str, data: CloneDecisionRequest, user: dict = Depends(get_current_user)):
    """Clone a decision from a specific level"""
    original = await db.decisions.find_one(
        {"id": decision_id, "user_id": user["user_id"]}, {"_id": 0}
    )
    if not original:
        raise HTTPException(status_code=404, detail="Decision not found")
    
    new_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    
    # Start with base fields
    cloned = {
        "id": new_id,
        "user_id": user["user_id"],
        "title": data.title,
        "context": original.get("context", ""),
        "factors": [],
        "options": [],
        "chosen_option_id": None,
        "decision_case": None,
        "notes": "",
        "reflection": "",
        "final_notes": "",
        "folder": original.get("folder", ""),
        "status": "draft",
        "created_at": now,
        "updated_at": now,
    }
    
    clone_level = data.clone_level
    
    # Copy Factors (names + order only, reset classification and rating)
    if clone_level in ("factors", "classification", "prioritization", "options", "assessment"):
        cloned["factors"] = []
        for f in original.get("factors", []):
            new_factor = {
                "id": str(uuid.uuid4()),
                "name": f["name"],
                "order": f.get("order", 0),
                "category": "primary",  # Reset classification
                "rating": 0,  # Reset rating
            }
            cloned["factors"].append(new_factor)
    
    # Copy Classification (keep primary/secondary)
    if clone_level in ("classification", "prioritization", "options", "assessment"):
        for i, f in enumerate(original.get("factors", [])):
            if i < len(cloned["factors"]):
                cloned["factors"][i]["category"] = f.get("category", "primary")
    
    # Copy Prioritization (keep ratings)
    if clone_level in ("prioritization", "options", "assessment"):
        for i, f in enumerate(original.get("factors", [])):
            if i < len(cloned["factors"]):
                cloned["factors"][i]["rating"] = f.get("rating", 0)
    
    # Copy Options (names only, no assessments)
    if clone_level in ("options", "assessment"):
        # Create factor ID mapping (old -> new)
        factor_id_map = {}
        for i, orig_f in enumerate(original.get("factors", [])):
            if i < len(cloned["factors"]):
                factor_id_map[orig_f["id"]] = cloned["factors"][i]["id"]
        
        cloned["options"] = []
        for opt in original.get("options", []):
            new_opt = {
                "id": str(uuid.uuid4()),
                "name": opt["name"],
                "assessments": [],
                "worth_percentage": 0.0,
            }
            cloned["options"].append(new_opt)
    
    # Copy Assessment (full clone with assessments)
    if clone_level == "assessment":
        factor_id_map = {}
        for i, orig_f in enumerate(original.get("factors", [])):
            if i < len(cloned["factors"]):
                factor_id_map[orig_f["id"]] = cloned["factors"][i]["id"]
        
        for i, opt in enumerate(original.get("options", [])):
            if i < len(cloned["options"]):
                new_assessments = []
                for asmt in opt.get("assessments", []):
                    new_factor_id = factor_id_map.get(asmt["factor_id"], asmt["factor_id"])
                    new_assessments.append({
                        "factor_id": new_factor_id,
                        "percentage": asmt.get("percentage"),
                        "unit_value": asmt.get("unit_value"),
                        "assessment_mode": asmt.get("assessment_mode"),
                    })
                cloned["options"][i]["assessments"] = new_assessments
                cloned["options"][i]["worth_percentage"] = opt.get("worth_percentage", 0.0)
    
    await db.decisions.insert_one(cloned)
    return {"id": new_id, "message": f"Decision cloned successfully (level: {clone_level})"}

# ========================
# TEMPLATE ROUTES
# ========================

@api_router.post("/decisions/{decision_id}/save-as-template")
async def save_as_template(decision_id: str, data: SaveTemplateRequest, user: dict = Depends(get_current_user)):
    """Save a decision as a shared template"""
    original = await db.decisions.find_one(
        {"id": decision_id, "user_id": user["user_id"]}, {"_id": 0}
    )
    if not original:
        raise HTTPException(status_code=404, detail="Decision not found")
    
    template_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    
    # Build template data based on type
    template = {
        "id": template_id,
        "name": data.name,
        "template_type": data.template_type,
        "visibility": data.visibility,  # "private", "shared", "public"
        "shared_with": [e.strip().lower() for e in data.shared_with if e.strip()],  # normalized emails
        "created_by": user["user_id"],
        "created_by_name": user.get("name", "Unknown"),
        "created_by_email": user.get("email", ""),
        "source_decision_title": original.get("title", ""),
        "context": original.get("context", ""),
        "factors": original.get("factors", []),
        "options": [],
        "created_at": now,
    }
    
    # Include options for both types
    if data.template_type in ("options", "assessment"):
        template["options"] = []
        for opt in original.get("options", []):
            new_opt = {
                "id": opt["id"],
                "name": opt["name"],
                "assessments": [],
                "worth_percentage": 0.0,
            }
            # Include assessments only for "assessment" type
            if data.template_type == "assessment":
                new_opt["assessments"] = opt.get("assessments", [])
                new_opt["worth_percentage"] = opt.get("worth_percentage", 0.0)
            template["options"].append(new_opt)
    
    await db.templates.insert_one(template)
    return {"id": template_id, "message": "Template saved successfully"}

@api_router.get("/templates")
async def get_templates(user: dict = Depends(get_current_user)):
    """Get templates categorized: my_templates, shared_with_me, public, authorized"""
    user_email = user.get("email", "").lower()
    user_id = user["user_id"]
    
    all_templates = await db.templates.find({}, {"_id": 0}).sort("created_at", -1).to_list(200)
    
    my_templates = []
    shared_templates = []
    public_templates = []
    authorized_templates = []
    
    for t in all_templates:
        visibility = t.get("visibility", "private")
        created_by = t.get("created_by", "")
        shared_with = [e.lower() for e in t.get("shared_with", [])]
        is_authorized = t.get("authorized", False)
        
        # Authorized templates (admin-approved public ones) - show to everyone
        if is_authorized and visibility == "public":
            authorized_templates.append(t)
        
        if created_by == user_id:
            my_templates.append(t)
        elif visibility == "shared" and user_email in shared_with:
            shared_templates.append(t)
        elif visibility == "public" and created_by != user_id and not is_authorized:
            # Only show non-authorized public templates in the public tab
            public_templates.append(t)
    
    return {
        "my_templates": my_templates,
        "shared_templates": shared_templates,
        "public_templates": public_templates,
        "authorized_templates": authorized_templates,
    }

@api_router.post("/templates/{template_id}/use")
async def use_template(template_id: str, data: UseTemplateRequest, user: dict = Depends(get_current_user)):
    """Create a new decision from a template"""
    template = await db.templates.find_one({"id": template_id}, {"_id": 0})
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    new_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    
    # Create factor ID mapping and new factors
    factor_id_map = {}
    new_factors = []
    for f in template.get("factors", []):
        new_factor_id = str(uuid.uuid4())
        factor_id_map[f["id"]] = new_factor_id
        new_factors.append({
            "id": new_factor_id,
            "name": f["name"],
            "category": f.get("category", "primary"),
            "rating": f.get("rating", 0),
            "order": f.get("order", 0),
        })
    
    # Create new options with mapped factor IDs
    new_options = []
    for opt in template.get("options", []):
        new_opt = {
            "id": str(uuid.uuid4()),
            "name": opt["name"],
            "assessments": [],
            "worth_percentage": 0.0,
        }
        # Map assessment factor IDs if template includes assessments
        if template.get("template_type") == "assessment":
            for asmt in opt.get("assessments", []):
                new_factor_id = factor_id_map.get(asmt["factor_id"], asmt["factor_id"])
                new_opt["assessments"].append({
                    "factor_id": new_factor_id,
                    "percentage": asmt.get("percentage"),
                    "unit_value": asmt.get("unit_value"),
                    "assessment_mode": asmt.get("assessment_mode"),
                })
            new_opt["worth_percentage"] = opt.get("worth_percentage", 0.0)
        new_options.append(new_opt)
    
    decision = {
        "id": new_id,
        "user_id": user["user_id"],
        "title": data.title,
        "context": template.get("context", ""),
        "factors": new_factors,
        "options": new_options,
        "chosen_option_id": None,
        "decision_case": None,
        "notes": "",
        "status": "draft",
        "created_at": now,
        "updated_at": now,
    }
    
    await db.decisions.insert_one(decision)
    return {"id": new_id, "message": "Decision created from template"}

@api_router.delete("/templates/{template_id}")
async def delete_template(template_id: str, user: dict = Depends(get_current_user)):
    """Delete a template (only by creator)"""
    result = await db.templates.delete_one(
        {"id": template_id, "created_by": user["user_id"]}
    )
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Template not found or not authorized")
    return {"message": "Template deleted successfully"}

@api_router.post("/templates/{template_id}/import")
async def import_template(template_id: str, user: dict = Depends(get_current_user)):
    """Import a shared/public template to my templates"""
    template = await db.templates.find_one({"id": template_id}, {"_id": 0})
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    user_email = user.get("email", "").lower()
    visibility = template.get("visibility", "private")
    shared_with = [e.lower() for e in template.get("shared_with", [])]
    
    # Check access: must be public or shared with this user
    if template["created_by"] == user["user_id"]:
        raise HTTPException(status_code=400, detail="This is already your template")
    if visibility == "private":
        raise HTTPException(status_code=403, detail="This template is private")
    if visibility == "shared" and user_email not in shared_with:
        raise HTTPException(status_code=403, detail="This template is not shared with you")
    
    # Create a copy under the current user
    new_template_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    
    imported = {
        "id": new_template_id,
        "name": f"{template['name']} (imported)",
        "template_type": template.get("template_type", "options"),
        "visibility": "private",  # Imported as private by default
        "shared_with": [],
        "created_by": user["user_id"],
        "created_by_name": user.get("name", "Unknown"),
        "created_by_email": user.get("email", ""),
        "source_decision_title": template.get("source_decision_title", ""),
        "imported_from": template.get("created_by_name", "Unknown"),
        "context": template.get("context", ""),
        "factors": template.get("factors", []),
        "options": template.get("options", []),
        "created_at": now,
    }
    
    await db.templates.insert_one(imported)
    return {"id": new_template_id, "message": "Template imported to your collection"}

@api_router.put("/templates/{template_id}")
async def update_template(template_id: str, data: SaveTemplateRequest, user: dict = Depends(get_current_user)):
    """Update template visibility and sharing settings"""
    template = await db.templates.find_one(
        {"id": template_id, "created_by": user["user_id"]}, {"_id": 0}
    )
    if not template:
        raise HTTPException(status_code=404, detail="Template not found or not authorized")
    
    update_fields = {
        "name": data.name,
        "visibility": data.visibility,
        "shared_with": [e.strip().lower() for e in data.shared_with if e.strip()],
    }
    
    await db.templates.update_one(
        {"id": template_id},
        {"$set": update_fields}
    )
    return {"message": "Template updated successfully"}

# ========================
# ADMIN ROUTES
# ========================

@api_router.post("/admin/setup")
async def admin_setup(user: dict = Depends(get_current_user)):
    """Bootstrap: Make current user Super Admin if no super admin exists"""
    existing_super = await db.users.find_one({"role": "super_admin"}, {"_id": 0})
    if existing_super:
        raise HTTPException(status_code=400, detail="Super Admin already exists")
    
    await db.users.update_one(
        {"user_id": user["user_id"]},
        {"$set": {"role": "super_admin"}}
    )
    return {"message": f"You are now Super Admin", "role": "super_admin"}

@api_router.post("/admin/promote")
async def promote_user(data: PromoteUserRequest, user: dict = Depends(get_current_user)):
    """Promote a user to admin or co_admin"""
    promoter_role = get_user_role(user)
    promoter_level = get_role_level(promoter_role)
    target_role = data.role
    target_level = get_role_level(target_role)
    
    # Validate target role
    if target_role not in ("admin", "co_admin"):
        raise HTTPException(status_code=400, detail="Can only promote to 'admin' or 'co_admin'")
    
    # Only Super Admin can create Co-Admins
    if target_role == "co_admin" and promoter_role != "super_admin":
        raise HTTPException(status_code=403, detail="Only Super Admin can create Co-Admins")
    
    # Co-Admin and above can create Admins
    if target_role == "admin" and promoter_level < 2:
        raise HTTPException(status_code=403, detail="Only Co-Admin or above can promote to Admin")
    
    # Find target user
    target_user = await db.users.find_one({"email": data.email.lower()}, {"_id": 0})
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found with this email")
    
    # Can't promote someone who already has equal or higher role
    current_target_level = get_role_level(get_user_role(target_user))
    if current_target_level >= target_level:
        raise HTTPException(status_code=400, detail=f"User already has role '{get_user_role(target_user)}'")
    
    await db.users.update_one(
        {"email": data.email.lower()},
        {"$set": {"role": target_role}}
    )
    return {"message": f"User {data.email} promoted to {target_role}"}

@api_router.post("/admin/demote")
async def demote_user(data: DemoteUserRequest, user: dict = Depends(get_current_user)):
    """Demote a user back to regular user"""
    demoter_role = get_user_role(user)
    demoter_level = get_role_level(demoter_role)
    
    # Find target user
    target_user = await db.users.find_one({"email": data.email.lower()}, {"_id": 0})
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found with this email")
    
    target_role = get_user_role(target_user)
    target_level = get_role_level(target_role)
    
    # Can't demote yourself
    if target_user["user_id"] == user["user_id"]:
        raise HTTPException(status_code=400, detail="Cannot demote yourself")
    
    # Super Admin cannot be demoted
    if target_role == "super_admin":
        raise HTTPException(status_code=403, detail="Super Admin cannot be demoted")
    
    # Co-Admin can only be demoted by Super Admin
    if target_role == "co_admin" and demoter_role != "super_admin":
        raise HTTPException(status_code=403, detail="Only Super Admin can demote Co-Admins")
    
    # Admin can be demoted by Co-Admin or Super Admin
    if target_role == "admin" and demoter_level < 2:
        raise HTTPException(status_code=403, detail="Only Co-Admin or above can demote Admins")
    
    await db.users.update_one(
        {"email": data.email.lower()},
        {"$set": {"role": "user"}}
    )
    return {"message": f"User {data.email} demoted to regular user"}

@api_router.get("/admin/users")
async def get_admin_users(user: dict = Depends(require_admin)):
    """Get all users with admin roles"""
    admin_users = await db.users.find(
        {"role": {"$in": ["super_admin", "co_admin", "admin"]}},
        {"_id": 0, "password_hash": 0}
    ).to_list(100)
    return admin_users

@api_router.post("/admin/templates/{template_id}/approve")
async def approve_template(template_id: str, user: dict = Depends(require_admin)):
    """Approve a public template as Authorized"""
    template = await db.templates.find_one({"id": template_id}, {"_id": 0})
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    if template.get("visibility") != "public":
        raise HTTPException(status_code=400, detail="Only public templates can be authorized")
    
    await db.templates.update_one(
        {"id": template_id},
        {"$set": {
            "authorized": True,
            "authorized_by": user["user_id"],
            "authorized_by_name": user.get("name", "Unknown"),
            "authorized_at": datetime.now(timezone.utc),
        }}
    )
    return {"message": "Template authorized successfully"}

@api_router.post("/admin/templates/{template_id}/revoke")
async def revoke_template(template_id: str, user: dict = Depends(require_admin)):
    """Revoke authorized status from a template"""
    template = await db.templates.find_one({"id": template_id}, {"_id": 0})
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    await db.templates.update_one(
        {"id": template_id},
        {"$set": {
            "authorized": False,
            "authorized_by": None,
            "authorized_by_name": None,
            "authorized_at": None,
        }}
    )
    return {"message": "Template authorization revoked"}

# ========================
# TEST123 ROUTES
# ========================

@api_router.post("/test123", response_model=dict)
async def create_test123(test_data: Test123Create, user: dict = Depends(get_current_user)):
    """Create a new Test123 instant decision session"""
    session = Test123Session(
        user_id=user["user_id"],
        situation=test_data.situation
    )
    
    await db.test123_sessions.insert_one(session.dict())
    return {"id": session.id, "message": "Test123 session created"}

@api_router.get("/test123", response_model=List[dict])
async def get_test123_sessions(user: dict = Depends(get_current_user)):
    """Get all Test123 sessions for the current user"""
    sessions = await db.test123_sessions.find(
        {"user_id": user["user_id"]},
        {"_id": 0}
    ).sort("created_at", -1).to_list(50)
    return sessions

@api_router.get("/test123/{session_id}")
async def get_test123_session(session_id: str, user: dict = Depends(get_current_user)):
    """Get a specific Test123 session"""
    session = await db.test123_sessions.find_one(
        {"id": session_id, "user_id": user["user_id"]},
        {"_id": 0}
    )
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session

@api_router.put("/test123/{session_id}")
async def update_test123_session(session_id: str, update_data: Test123Update, user: dict = Depends(get_current_user)):
    """Update a Test123 session"""
    existing = await db.test123_sessions.find_one(
        {"id": session_id, "user_id": user["user_id"]},
        {"_id": 0}
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Session not found")
    
    update_dict = {k: v for k, v in update_data.dict().items() if v is not None}
    update_dict["updated_at"] = datetime.now(timezone.utc)
    
    await db.test123_sessions.update_one(
        {"id": session_id},
        {"$set": update_dict}
    )
    
    return {"message": "Session updated successfully"}

# ========================
# MODE ASSESSMENT ROUTES
# ========================

ASSESSMENT_QUESTIONS = [
    {"id": "q1", "text": "When faced with a decision, I usually go with my gut feeling.", "mode": "intuitive"},
    {"id": "q2", "text": "I prefer to analyze all available data before deciding.", "mode": "logical"},
    {"id": "q3", "text": "My decisions are often influenced by how I feel at the moment.", "mode": "emotional"},
    {"id": "q4", "text": "I can detach myself from emotions when making important decisions.", "mode": "awareness"},
    {"id": "q5", "text": "I trust my instincts even when logic suggests otherwise.", "mode": "intuitive"},
    {"id": "q6", "text": "I create pros and cons lists for major decisions.", "mode": "logical"},
    {"id": "q7", "text": "I often regret decisions made when I was upset or excited.", "mode": "emotional"},
    {"id": "q8", "text": "I can observe my thoughts without being controlled by them.", "mode": "awareness"},
    {"id": "q9", "text": "I often know the right decision without knowing why.", "mode": "intuitive"},
    {"id": "q10", "text": "I need concrete evidence to make a decision.", "mode": "logical"},
    {"id": "q11", "text": "My mood significantly affects my decision-making.", "mode": "emotional"},
    {"id": "q12", "text": "I practice mindfulness or meditation regularly.", "mode": "awareness"},
]

@api_router.get("/assessment/questions")
async def get_assessment_questions():
    """Get all assessment questions"""
    return {"questions": ASSESSMENT_QUESTIONS}

@api_router.post("/assessment", response_model=dict)
async def submit_assessment(assessment: ModeAssessmentCreate, user: dict = Depends(get_current_user)):
    """Submit a mode assessment and get results"""
    answers = assessment.answers
    
    # Calculate scores for each mode
    mode_scores = {"emotional": 0.0, "logical": 0.0, "intuitive": 0.0, "awareness": 0.0}
    mode_counts = {"emotional": 0, "logical": 0, "intuitive": 0, "awareness": 0}
    
    for question in ASSESSMENT_QUESTIONS:
        if question["id"] in answers:
            mode = question["mode"]
            mode_scores[mode] += answers[question["id"]]
            mode_counts[mode] += 1
    
    # Calculate averages
    for mode in mode_scores:
        if mode_counts[mode] > 0:
            mode_scores[mode] = round(mode_scores[mode] / mode_counts[mode], 2)
    
    # Determine dominant mode
    dominant_mode = max(mode_scores, key=mode_scores.get)
    
    result = ModeAssessmentResult(
        user_id=user["user_id"],
        answers=answers,
        dominant_mode=dominant_mode,
        mode_scores=mode_scores
    )
    
    await db.assessments.insert_one(result.dict())
    
    return {
        "id": result.id,
        "dominant_mode": dominant_mode,
        "mode_scores": mode_scores
    }

@api_router.get("/assessment/history")
async def get_assessment_history(user: dict = Depends(get_current_user)):
    """Get assessment history for the current user"""
    assessments = await db.assessments.find(
        {"user_id": user["user_id"]},
        {"_id": 0}
    ).sort("created_at", -1).to_list(10)
    return assessments

# ========================
# DECISION JOURNAL ROUTES
# ========================

@api_router.post("/journal", response_model=dict)
async def create_journal_entry(entry: JournalEntryCreate, user: dict = Depends(get_current_user)):
    """Create a new journal entry"""
    journal_entry = JournalEntry(
        user_id=user["user_id"],
        decision_title=entry.decision_title,
        decision_description=entry.decision_description,
        decision_date=entry.decision_date or datetime.now(timezone.utc)
    )
    
    await db.journal.insert_one(journal_entry.dict())
    return {"id": journal_entry.id, "message": "Journal entry created"}

@api_router.get("/journal", response_model=List[dict])
async def get_journal_entries(user: dict = Depends(get_current_user)):
    """Get all journal entries for the current user"""
    entries = await db.journal.find(
        {"user_id": user["user_id"]},
        {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    return entries

@api_router.get("/journal/{entry_id}")
async def get_journal_entry(entry_id: str, user: dict = Depends(get_current_user)):
    """Get a specific journal entry"""
    entry = await db.journal.find_one(
        {"id": entry_id, "user_id": user["user_id"]},
        {"_id": 0}
    )
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    return entry

@api_router.put("/journal/{entry_id}")
async def update_journal_entry(entry_id: str, update_data: JournalEntryUpdate, user: dict = Depends(get_current_user)):
    """Update a journal entry"""
    existing = await db.journal.find_one(
        {"id": entry_id, "user_id": user["user_id"]},
        {"_id": 0}
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Entry not found")
    
    update_dict = {k: v for k, v in update_data.dict().items() if v is not None}
    update_dict["updated_at"] = datetime.now(timezone.utc)
    
    await db.journal.update_one(
        {"id": entry_id},
        {"$set": update_dict}
    )
    
    return {"message": "Entry updated successfully"}

@api_router.delete("/journal/{entry_id}")
async def delete_journal_entry(entry_id: str, user: dict = Depends(get_current_user)):
    """Delete a journal entry"""
    result = await db.journal.delete_one(
        {"id": entry_id, "user_id": user["user_id"]}
    )
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Entry not found")
    return {"message": "Entry deleted successfully"}

# ========================
# DASHBOARD STATS
# ========================

@api_router.get("/stats")
async def get_user_stats(user: dict = Depends(get_current_user)):
    """Get dashboard statistics for the current user"""
    user_id = user["user_id"]
    
    # Count decisions
    total_decisions = await db.decisions.count_documents({"user_id": user_id})
    completed_decisions = await db.decisions.count_documents({"user_id": user_id, "status": "completed"})
    
    # Count Test123 sessions
    total_test123 = await db.test123_sessions.count_documents({"user_id": user_id})
    
    # Count journal entries
    total_journal = await db.journal.count_documents({"user_id": user_id})
    completed_journal = await db.journal.count_documents({"user_id": user_id, "status": "completed"})
    
    # Get latest assessment
    latest_assessment = await db.assessments.find_one(
        {"user_id": user_id},
        {"_id": 0},
        sort=[("created_at", -1)]
    )
    
    return {
        "decisions": {
            "total": total_decisions,
            "completed": completed_decisions
        },
        "test123": {
            "total": total_test123
        },
        "journal": {
            "total": total_journal,
            "completed": completed_journal
        },
        "latest_assessment": latest_assessment
    }

# ========================
# HEALTH CHECK
# ========================

@api_router.get("/")
async def root():
    return {"message": "View Dezider API - Decision Intelligence by Venture Buddha"}

@api_router.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}

# ========================
# DECISION FOLDERS
# ========================

@api_router.get("/folders")
async def get_folders():
    """Get all available decision folders"""
    return DECISION_FOLDERS

# ========================
# STEP SHARING
# ========================

@api_router.post("/decisions/{decision_id}/share-step")
async def share_step(decision_id: str, data: ShareStepRequest, user: dict = Depends(get_current_user)):
    """Share a specific step of a decision with other users for collaborative input"""
    decision = await db.decisions.find_one(
        {"id": decision_id, "user_id": user["user_id"]}, {"_id": 0}
    )
    if not decision:
        raise HTTPException(status_code=404, detail="Decision not found")
    
    # Resolve recipient user IDs from emails
    recipients = []
    for email in data.recipient_emails:
        recipient_user = await db.users.find_one({"email": email}, {"_id": 0})
        if recipient_user:
            recipients.append({
                "user_id": recipient_user["user_id"],
                "email": email,
                "name": recipient_user.get("name", email),
                "status": "pending",
                "contribution": None,
            })
    
    if not recipients:
        raise HTTPException(status_code=400, detail="No valid recipients found")
    
    share_doc = {
        "id": str(uuid.uuid4()),
        "decision_id": decision_id,
        "owner_id": user["user_id"],
        "owner_name": user.get("name", user["email"]),
        "step_number": data.step_number,
        "merge_mode": data.merge_mode,
        "custom_weights": data.custom_weights or {},
        "message": data.message,
        "recipients": recipients,
        "decision_title": decision.get("title", ""),
        "decision_context": decision.get("context", ""),
        "step_data": {
            "factors": decision.get("factors", []),
            "options": [{"id": o["id"], "name": o["name"]} for o in decision.get("options", [])],
        },
        "status": "active",
        "created_at": datetime.now(timezone.utc),
        "merged_at": None,
    }
    
    await db.shared_steps.insert_one(share_doc)
    
    STEP_NAMES = {
        1: 'Context & Options', 2: 'List Factors', 3: 'Classify Factors',
        4: 'Prioritize Factors', 5: 'Calculate Ratings', 6: 'Define Options',
        7: 'Assess & Calculate', 8: 'Case-1 Results', 9: 'MPPS Analysis', 10: 'Final Decision',
    }
    step_name = STEP_NAMES.get(data.step_number, f'Step {data.step_number}')
    sender_name = user.get("name", user["email"])
    sender_email = user.get("email", "")
    decision_title = decision.get("title", "a decision")
    
    # Create notifications + push for each recipient
    for r in recipients:
        await create_notification(
            r["user_id"],
            "share_invite",
            f"Step {data.step_number}: {step_name}",
            f'{sender_name} ({sender_email}) shared Step {data.step_number} "{step_name}" of "{decision_title}" with you',
            {
                "share_id": share_doc["id"],
                "decision_id": decision_id,
                "step_number": data.step_number,
                "step_name": step_name,
                "sender_name": sender_name,
                "sender_email": sender_email,
                "decision_title": decision_title,
            }
        )
    
    return {"id": share_doc["id"], "message": f"Step {data.step_number} shared with {len(recipients)} users"}

@api_router.get("/shared-steps/received")
async def get_received_shared_steps(user: dict = Depends(get_current_user)):
    """Get all step shares where the current user is a recipient"""
    shares = await db.shared_steps.find(
        {"recipients.user_id": user["user_id"], "status": "active"},
        {"_id": 0}
    ).sort("created_at", -1).to_list(50)
    return shares

@api_router.get("/shared-steps/sent")
async def get_sent_shared_steps(user: dict = Depends(get_current_user)):
    """Get all step shares created by the current user"""
    shares = await db.shared_steps.find(
        {"owner_id": user["user_id"]},
        {"_id": 0}
    ).sort("created_at", -1).to_list(50)
    return shares

@api_router.get("/shared-steps/{share_id}")
async def get_shared_step(share_id: str, user: dict = Depends(get_current_user)):
    """Get a specific shared step"""
    share = await db.shared_steps.find_one({"id": share_id}, {"_id": 0})
    if not share:
        raise HTTPException(status_code=404, detail="Shared step not found")
    
    # Check access
    is_owner = share["owner_id"] == user["user_id"]
    is_recipient = any(r["user_id"] == user["user_id"] for r in share.get("recipients", []))
    if not is_owner and not is_recipient:
        raise HTTPException(status_code=403, detail="Access denied")
    
    return share

@api_router.post("/shared-steps/{share_id}/contribute")
async def contribute_to_shared_step(share_id: str, data: ContributeStepRequest, user: dict = Depends(get_current_user)):
    """Submit contribution to a shared step"""
    share = await db.shared_steps.find_one({"id": share_id}, {"_id": 0})
    if not share:
        raise HTTPException(status_code=404, detail="Shared step not found")
    
    is_recipient = any(r["user_id"] == user["user_id"] for r in share.get("recipients", []))
    if not is_recipient:
        raise HTTPException(status_code=403, detail="You are not a recipient of this share")
    
    contribution = {
        "factors": data.factors,
        "options": data.options,
        "assessments": data.assessments,
        "note": data.note,
        "submitted_at": datetime.now(timezone.utc).isoformat(),
    }
    
    await db.shared_steps.update_one(
        {"id": share_id, "recipients.user_id": user["user_id"]},
        {"$set": {
            "recipients.$.status": "contributed",
            "recipients.$.contribution": contribution,
        }}
    )
    
    # Notify the owner about the contribution
    contributor_name = user.get("name", user.get("email", "Someone"))
    await create_notification(
        share["owner_id"],
        "share_contributed",
        "New Contribution",
        f'{contributor_name} contributed to Step {share.get("step_number", "?")} of "{share.get("decision_title", "your decision")}"',
        {"share_id": share_id, "decision_id": share.get("decision_id")}
    )
    
    return {"message": "Contribution submitted successfully"}

@api_router.post("/shared-steps/{share_id}/merge")
async def merge_shared_step(share_id: str, data: MergeStepRequest, user: dict = Depends(get_current_user)):
    """Merge all contributions back into the decision with weighted calculation"""
    share = await db.shared_steps.find_one({"id": share_id}, {"_id": 0})
    if not share:
        raise HTTPException(status_code=404, detail="Shared step not found")
    
    if share["owner_id"] != user["user_id"]:
        raise HTTPException(status_code=403, detail="Only the owner can merge contributions")
    
    decision = await db.decisions.find_one(
        {"id": share["decision_id"], "user_id": user["user_id"]}, {"_id": 0}
    )
    if not decision:
        raise HTTPException(status_code=404, detail="Decision not found")
    
    # Collect all contributions
    contributions = []
    for r in share.get("recipients", []):
        if r.get("contribution"):
            contributions.append({
                "user_id": r["user_id"],
                "data": r["contribution"],
            })
    
    if not contributions:
        raise HTTPException(status_code=400, detail="No contributions to merge")
    
    # Calculate weights
    merge_mode = data.merge_mode or share.get("merge_mode", "equal")
    total_participants = len(contributions) + 1  # +1 for owner
    
    weights = {}
    if merge_mode == "equal":
        w = 1.0 / total_participants
        weights[user["user_id"]] = w
        for c in contributions:
            weights[c["user_id"]] = w
    elif merge_mode == "self_weighted":
        weights[user["user_id"]] = 0.5
        other_weight = 0.5 / len(contributions) if contributions else 0
        for c in contributions:
            weights[c["user_id"]] = other_weight
    elif merge_mode == "custom" and data.custom_weights:
        weights = data.custom_weights
        # Ensure owner has a weight
        if user["user_id"] not in weights:
            weights[user["user_id"]] = 0.5
    
    # Merge assessments (weighted average of percentages)
    step_number = share.get("step_number", 7)
    
    if step_number == 7 and decision.get("options"):
        merged_options = []
        for option in decision["options"]:
            merged_assessments = []
            for factor in decision.get("factors", []):
                # Owner's assessment
                owner_assessment = None
                for a in option.get("assessments", []):
                    if a.get("factor_id") == factor["id"]:
                        owner_assessment = a
                        break
                
                owner_pct = owner_assessment.get("percentage", 50) if owner_assessment else 50
                weighted_sum = owner_pct * weights.get(user["user_id"], 0.5)
                
                # Contributors' assessments
                for c in contributions:
                    c_assessments = c["data"].get("assessments", {})
                    c_key = f"{option['id']}_{factor['id']}"
                    c_pct = c_assessments.get(c_key, 50)
                    weighted_sum += c_pct * weights.get(c["user_id"], 0)
                
                merged_assessments.append({
                    "factor_id": factor["id"],
                    "percentage": min(100, max(0, round(weighted_sum))),
                    "assessment_mode": "custom",
                    "unit_value": "",
                })
            
            merged_options.append({
                **option,
                "assessments": merged_assessments,
            })
        
        # Update decision with merged data
        now = datetime.now(timezone.utc)
        await db.decisions.update_one(
            {"id": share["decision_id"]},
            {"$set": {"options": merged_options, "updated_at": now}}
        )
    
    # Mark share as merged
    await db.shared_steps.update_one(
        {"id": share_id},
        {"$set": {"status": "merged", "merged_at": datetime.now(timezone.utc)}}
    )
    
    # Notify contributors that merge happened
    for r in share.get("recipients", []):
        if r.get("contribution"):
            await create_notification(
                r["user_id"],
                "share_merged",
                "Contributions Merged",
                f'{user.get("name", "Someone")} merged your input for "{share.get("decision_title", "a decision")}"',
                {"share_id": share_id, "decision_id": share["decision_id"]}
            )
    
    return {"message": "Contributions merged successfully", "weights": weights}

# ========================
# NOTIFICATIONS
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

    # Send push notification
    user_doc = await db.users.find_one({"user_id": user_id}, {"_id": 0})
    if user_doc and user_doc.get("push_token"):
        await send_expo_push([user_doc["push_token"]], title, message, data)

    return notif

# Push token registration
@api_router.post("/auth/push-token")
async def register_push_token(request: Request, user: dict = Depends(get_current_user)):
    """Register Expo push token for the current user"""
    body = await request.json()
    token = body.get("push_token", "")
    if token:
        await db.users.update_one(
            {"user_id": user["user_id"]},
            {"$set": {"push_token": token}}
        )
    return {"message": "Push token registered"}

# User search for sharing
@api_router.get("/users/search")
async def search_users(q: str = "", user: dict = Depends(get_current_user)):
    """Search users by name or email for sharing"""
    if not q or len(q) < 2:
        return []
    query = {
        "$or": [
            {"name": {"$regex": q, "$options": "i"}},
            {"email": {"$regex": q, "$options": "i"}},
        ],
        "user_id": {"$ne": user["user_id"]},  # Exclude self
    }
    users = await db.users.find(query, {"_id": 0, "password_hash": 0, "push_token": 0}).to_list(20)
    return [{"user_id": u["user_id"], "name": u.get("name", ""), "email": u["email"]} for u in users]

# Authorized Experts (admin-managed)
ADMIN_ROLES = ["admin", "co_admin", "super_admin"]

@api_router.get("/experts")
async def get_experts(include_inactive: bool = False):
    """Get list of authorized experts. Admins can include_inactive=true to see all."""
    query = {} if include_inactive else {"is_active": True}
    experts = await db.experts.find(query, {"_id": 0}).sort("name", 1).to_list(100)
    return experts

@api_router.post("/experts")
async def create_expert(request: Request, user: dict = Depends(get_current_user)):
    """Create an authorized expert (admin only)"""
    if user.get("role") not in ADMIN_ROLES:
        raise HTTPException(status_code=403, detail="Admin access required")
    body = await request.json()
    expert = {
        "id": str(uuid.uuid4()),
        "name": body.get("name", ""),
        "email": body.get("email", ""),
        "specialization": body.get("specialization", ""),
        "bio": body.get("bio", ""),
        "is_active": True,
        "created_by": user["user_id"],
        "created_at": datetime.now(timezone.utc),
    }
    await db.experts.insert_one(expert)
    return {"id": expert["id"], "message": "Expert created"}

@api_router.put("/experts/{expert_id}")
async def update_expert(expert_id: str, request: Request, user: dict = Depends(get_current_user)):
    """Update an expert (admin only)"""
    if user.get("role") not in ADMIN_ROLES:
        raise HTTPException(status_code=403, detail="Admin access required")
    body = await request.json()
    update_fields = {k: v for k, v in body.items() if k in ["name", "email", "specialization", "bio", "is_active"]}
    result = await db.experts.update_one({"id": expert_id}, {"$set": update_fields})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Expert not found")
    return {"message": "Expert updated"}

@api_router.delete("/experts/{expert_id}")
async def delete_expert(expert_id: str, user: dict = Depends(get_current_user)):
    """Delete an expert (admin only)"""
    if user.get("role") not in ADMIN_ROLES:
        raise HTTPException(status_code=403, detail="Admin access required")
    result = await db.experts.delete_one({"id": expert_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Expert not found")
    return {"message": "Expert deleted"}

@api_router.get("/notifications")
async def get_notifications(user: dict = Depends(get_current_user)):
    """Get all notifications for the current user"""
    notifications = await db.notifications.find(
        {"user_id": user["user_id"]},
        {"_id": 0}
    ).sort("created_at", -1).to_list(50)
    return notifications

@api_router.get("/notifications/unread-count")
async def get_unread_count(user: dict = Depends(get_current_user)):
    """Get count of unread notifications"""
    count = await db.notifications.count_documents(
        {"user_id": user["user_id"], "read": False}
    )
    return {"count": count}

@api_router.post("/notifications/{notif_id}/read")
async def mark_notification_read(notif_id: str, user: dict = Depends(get_current_user)):
    """Mark a specific notification as read"""
    result = await db.notifications.update_one(
        {"id": notif_id, "user_id": user["user_id"]},
        {"$set": {"read": True}}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"message": "Notification marked as read"}

@api_router.post("/notifications/read-all")
async def mark_all_notifications_read(user: dict = Depends(get_current_user)):
    """Mark all notifications as read for the current user"""
    await db.notifications.update_many(
        {"user_id": user["user_id"], "read": False},
        {"$set": {"read": True}}
    )
    return {"message": "All notifications marked as read"}

@api_router.delete("/notifications/{notif_id}")
async def delete_notification(notif_id: str, user: dict = Depends(get_current_user)):
    """Delete a notification"""
    await db.notifications.delete_one({"id": notif_id, "user_id": user["user_id"]})
    return {"message": "Notification deleted"}

# ========================
# FOLDER ANALYTICS
# ========================

@api_router.get("/analytics/folders")
async def get_folder_analytics(user: dict = Depends(get_current_user)):
    """Get analytics broken down by decision folder"""
    decisions = await db.decisions.find(
        {"user_id": user["user_id"]},
        {"_id": 0}
    ).to_list(500)
    
    # Build analytics per folder
    folder_stats = {}
    for folder in DECISION_FOLDERS:
        folder_stats[folder["id"]] = {
            "id": folder["id"],
            "name": folder["name"],
            "icon": folder["icon"],
            "color": folder["color"],
            "total_decisions": 0,
            "completed": 0,
            "in_progress": 0,
            "draft": 0,
            "avg_factors": 0,
            "avg_options": 0,
            "total_factors": 0,
            "total_options": 0,
            "completion_rate": 0,
            "recent_decision": None,
        }
    
    # Add uncategorized
    folder_stats["uncategorized"] = {
        "id": "uncategorized",
        "name": "Uncategorized",
        "icon": "folder-open",
        "color": "#9CA3AF",
        "total_decisions": 0,
        "completed": 0,
        "in_progress": 0,
        "draft": 0,
        "avg_factors": 0,
        "avg_options": 0,
        "total_factors": 0,
        "total_options": 0,
        "completion_rate": 0,
        "recent_decision": None,
    }
    
    for d in decisions:
        folder_id = d.get("folder", "") or "uncategorized"
        if folder_id not in folder_stats:
            folder_id = "uncategorized"
        
        stats = folder_stats[folder_id]
        stats["total_decisions"] += 1
        stats["total_factors"] += len(d.get("factors", []))
        stats["total_options"] += len(d.get("options", []))
        
        status = d.get("status", "draft")
        if status == "completed":
            stats["completed"] += 1
        elif status == "in_progress":
            stats["in_progress"] += 1
        else:
            stats["draft"] += 1
        
        # Track most recent decision
        if not stats["recent_decision"] or d.get("updated_at", d.get("created_at")) > stats["recent_decision"].get("updated_at", stats["recent_decision"].get("created_at")):
            stats["recent_decision"] = {
                "id": d["id"],
                "title": d["title"],
                "status": d.get("status", "draft"),
                "updated_at": d.get("updated_at", d.get("created_at")),
            }
    
    # Calculate averages and rates
    for stats in folder_stats.values():
        total = stats["total_decisions"]
        if total > 0:
            stats["avg_factors"] = round(stats["total_factors"] / total, 1)
            stats["avg_options"] = round(stats["total_options"] / total, 1)
            stats["completion_rate"] = round(stats["completed"] / total * 100, 1)
        
        # Serialize recent decision datetime
        if stats["recent_decision"] and "updated_at" in stats["recent_decision"]:
            dt = stats["recent_decision"]["updated_at"]
            if isinstance(dt, datetime):
                stats["recent_decision"]["updated_at"] = dt.isoformat()
    
    # Return only folders that have decisions + summary
    active_folders = [s for s in folder_stats.values() if s["total_decisions"] > 0]
    all_folders = list(folder_stats.values())
    
    # Overall summary
    total_decisions = len(decisions)
    completed = sum(1 for d in decisions if d.get("status") == "completed")
    
    return {
        "folders": all_folders,
        "active_folders": active_folders,
        "summary": {
            "total_decisions": total_decisions,
            "total_completed": completed,
            "total_folders_used": len(active_folders),
            "overall_completion_rate": round(completed / total_decisions * 100, 1) if total_decisions > 0 else 0,
            "most_active_folder": max(active_folders, key=lambda x: x["total_decisions"])["name"] if active_folders else None,
        }
    }

@api_router.get("/analytics/folder/{folder_id}")
async def get_single_folder_analytics(folder_id: str, user: dict = Depends(get_current_user)):
    """Get detailed analytics for a specific folder"""
    decisions = await db.decisions.find(
        {"user_id": user["user_id"], "folder": folder_id},
        {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    
    total = len(decisions)
    completed = [d for d in decisions if d.get("status") == "completed"]
    in_progress = [d for d in decisions if d.get("status") == "in_progress"]
    
    # Factor frequency analysis
    factor_freq = {}
    for d in decisions:
        for f in d.get("factors", []):
            name = f.get("name", "Unknown")
            factor_freq[name] = factor_freq.get(name, 0) + 1
    
    top_factors = sorted(factor_freq.items(), key=lambda x: x[1], reverse=True)[:10]
    
    return {
        "folder_id": folder_id,
        "total_decisions": total,
        "completed": len(completed),
        "in_progress": len(in_progress),
        "draft": total - len(completed) - len(in_progress),
        "completion_rate": round(len(completed) / total * 100, 1) if total > 0 else 0,
        "top_factors": [{"name": name, "count": count} for name, count in top_factors],
        "recent_decisions": [
            {"id": d["id"], "title": d["title"], "status": d.get("status", "draft")}
            for d in decisions[:5]
        ],
    }


# ============= MPPS Action Plan Download =============

@api_router.get("/decisions/{decision_id}/mpps-action-plan")
async def download_mpps_action_plan(decision_id: str, user: dict = Depends(get_current_user)):
    """Download MPPS action plan as CSV"""
    import io, csv
    decision = await db.decisions.find_one({"id": decision_id, "user_id": user["user_id"]})
    if not decision:
        raise HTTPException(status_code=404, detail="Decision not found")
    
    improvements = decision.get("mpps_improvements", [])
    factors = decision.get("factors", [])
    options = decision.get("options", [])
    mpps_option_id = decision.get("mpps_option_id")
    mpps_timeframe = decision.get("mpps_timeframe", "Not specified")
    
    target_option = next((o for o in options if o.get("id") == mpps_option_id), options[0] if options else None)
    option_name = target_option.get("name", "Unknown") if target_option else "Unknown"
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    writer.writerow(["MPPS Action Plan"])
    writer.writerow(["Decision", decision.get("title", "")])
    writer.writerow(["Context", decision.get("context", "")])
    writer.writerow(["Option", option_name])
    writer.writerow(["Timeframe", mpps_timeframe])
    writer.writerow(["Projected Worth", f"{decision.get('mpps_projected_worth', 0)}%"])
    writer.writerow([])
    
    writer.writerow([
        "Factor", "Category", "Rating", "Current %", "Projected %", "Delta %",
        "Target Value", "Target Unit", "Improvement Plan",
        "TEPFI Elements", "Solution Layer",
        "Assignee Name", "Assignee Email", "Assignee Mobile", "Task", "Deadline"
    ])
    
    for imp in improvements:
        factor = next((f for f in factors if f.get("id") == imp.get("factor_id")), {})
        tepfi = ", ".join(imp.get("tepfi_elements", []))
        layer = imp.get("tepfi_layer", "")
        action_items = imp.get("action_items", [])
        
        base_row = [
            factor.get("name", ""), factor.get("category", ""), factor.get("rating", ""),
            imp.get("original_percentage", ""), imp.get("projected_percentage", ""),
            imp.get("delta_percentage", ""),
            imp.get("expected_value", ""), imp.get("expected_unit", ""),
            imp.get("improvement_plan", ""),
            tepfi, layer,
        ]
        
        if action_items:
            for ai in action_items:
                writer.writerow(base_row + [
                    ai.get("assignee_name", ""), ai.get("assignee_email", ""),
                    ai.get("assignee_mobile", ""), ai.get("task", ""), ai.get("deadline", "")
                ])
        else:
            writer.writerow(base_row + ["", "", "", "", ""])
    
    csv_content = output.getvalue()
    return StreamingResponse(
        io.BytesIO(csv_content.encode()),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="MPPS_Action_Plan_{decision_id[:8]}.csv"'}
    )

@api_router.get("/decisions/{decision_id}/mpps-action-plan-pdf")
async def download_mpps_action_plan_pdf(decision_id: str, user: dict = Depends(get_current_user)):
    """Download MPPS action plan as PDF"""
    import io
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.units import mm

    decision = await db.decisions.find_one({"id": decision_id, "user_id": user["user_id"]})
    if not decision:
        raise HTTPException(status_code=404, detail="Decision not found")

    improvements = decision.get("mpps_improvements", [])
    factors = decision.get("factors", [])
    options = decision.get("options", [])
    mpps_option_id = decision.get("mpps_option_id")
    mpps_timeframe = decision.get("mpps_timeframe", "Not specified")
    target_option = next((o for o in options if o.get("id") == mpps_option_id), options[0] if options else None)
    option_name = target_option.get("name", "Unknown") if target_option else "Unknown"

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=15*mm, bottomMargin=15*mm, leftMargin=12*mm, rightMargin=12*mm)
    styles = getSampleStyleSheet()
    story = []

    # Title
    title_style = ParagraphStyle('Title2', parent=styles['Title'], fontSize=16, spaceAfter=6)
    story.append(Paragraph("MPPS Action Plan", title_style))
    story.append(Spacer(1, 4*mm))

    # Summary table
    summary_data = [
        ["Decision", decision.get("title", "")],
        ["Context", decision.get("context", "")],
        ["Option", option_name],
        ["Timeframe", mpps_timeframe],
        ["Projected Worth", f"{decision.get('mpps_projected_worth', 0)}%"],
    ]
    summary_table = Table(summary_data, colWidths=[35*mm, 140*mm])
    summary_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 6*mm))

    # Factor improvements
    cell_style = ParagraphStyle('Cell', parent=styles['Normal'], fontSize=7, leading=9)
    header_style = ParagraphStyle('Header', parent=styles['Normal'], fontSize=7, leading=9, fontName='Helvetica-Bold', textColor=colors.white)

    for imp in improvements:
        factor = next((f for f in factors if f.get("id") == imp.get("factor_id")), {})
        tepfi = ", ".join(imp.get("tepfi_elements", []))
        layer = imp.get("tepfi_layer", "")
        action_items = imp.get("action_items", [])

        # Factor header
        factor_title = ParagraphStyle('FTitle', parent=styles['Heading3'], fontSize=11, spaceAfter=2, spaceBefore=4)
        orig = imp.get("original_percentage", "--")
        proj = imp.get("projected_percentage", "--")
        delta = imp.get("delta_percentage", "--")
        story.append(Paragraph(f"{factor.get('name', '')} — {factor.get('category', '')} (Rating: {factor.get('rating', '')})", factor_title))

        info_data = [
            [Paragraph("<b>Current %</b>", cell_style), Paragraph(f"{orig}%", cell_style),
             Paragraph("<b>Projected %</b>", cell_style), Paragraph(f"{proj}%", cell_style),
             Paragraph("<b>Delta</b>", cell_style), Paragraph(f"+{delta}%" if delta and str(delta) != '--' else str(delta), cell_style)],
            [Paragraph("<b>Target Value</b>", cell_style), Paragraph(str(imp.get("expected_value", "")), cell_style),
             Paragraph("<b>Unit</b>", cell_style), Paragraph(str(imp.get("expected_unit", "")), cell_style),
             Paragraph("<b>TEPFI</b>", cell_style), Paragraph(tepfi, cell_style)],
            [Paragraph("<b>Layer</b>", cell_style), Paragraph(layer, cell_style),
             Paragraph("<b>Plan</b>", cell_style), Paragraph(str(imp.get("improvement_plan", "")), cell_style), "", ""],
        ]
        info_table = Table(info_data, colWidths=[22*mm, 28*mm, 22*mm, 28*mm, 22*mm, 53*mm])
        info_table.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
            ('FONTSIZE', (0, 0), (-1, -1), 7),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
        ]))
        story.append(info_table)

        # Action items
        if action_items:
            story.append(Spacer(1, 2*mm))
            ai_header = [
                Paragraph("Who", header_style), Paragraph("Email", header_style),
                Paragraph("Mobile", header_style), Paragraph("Task", header_style),
                Paragraph("By When", header_style)
            ]
            ai_data = [ai_header]
            for ai in action_items:
                ai_data.append([
                    Paragraph(ai.get("assignee_name", ""), cell_style),
                    Paragraph(ai.get("assignee_email", ""), cell_style),
                    Paragraph(ai.get("assignee_mobile", ""), cell_style),
                    Paragraph(ai.get("task", ""), cell_style),
                    Paragraph(ai.get("deadline", ""), cell_style),
                ])
            ai_table = Table(ai_data, colWidths=[30*mm, 38*mm, 28*mm, 50*mm, 29*mm])
            ai_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#6366F1')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
                ('FONTSIZE', (0, 0), (-1, -1), 7),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                ('TOPPADDING', (0, 0), (-1, -1), 3),
            ]))
            story.append(ai_table)

        story.append(Spacer(1, 4*mm))

    doc.build(story)
    buffer.seek(0)
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="MPPS_Action_Plan_{decision_id[:8]}.pdf"'}
    )


# ============= TEPFI AI Auto-mapping =============

@api_router.post("/tepfi-auto-map")
async def tepfi_auto_map(request: Request, user: dict = Depends(get_current_user)):
    """AI auto-map factors to TEPFI elements and solution layers"""
    from emergentintegrations.llm.chat import LlmChat, UserMessage
    import json as json_module

    body = await request.json()
    context = body.get("context", "")
    decision_title = body.get("title", "")
    factors = body.get("factors", [])

    if not factors:
        return {"mappings": []}

    api_key = os.getenv("EMERGENT_LLM_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="LLM key not configured")

    factor_list = "\n".join([f"- {f.get('name', '')} (category: {f.get('category', '')}, unit: {f.get('unit', '')})" for f in factors])

    prompt = f"""You are an expert decision analyst using the TEPFI framework.

Decision: {decision_title}
Context: {context}

Factors to classify:
{factor_list}

For each factor, assign:
1. tepfi_elements: one or more from [T=Time, E=Effort, P=People, F=Finance, I=Infrastructure] — use the single letter codes
2. tepfi_layer: one from [self, micro, macro]
   - self = personal/individual control
   - micro = immediate environment (team, family, organization)
   - macro = external/systemic factors

Return ONLY valid JSON array, no markdown, no explanation:
[{{"factor_name": "...", "tepfi_elements": ["T","F"], "tepfi_layer": "self"}}]"""

    try:
        chat = LlmChat(
            api_key=api_key,
            session_id=f"tepfi_{user['user_id']}_{uuid.uuid4().hex[:8]}",
            system_message="You are a TEPFI framework classifier. Return only valid JSON."
        ).with_model("openai", "gpt-4.1-mini")

        response = await chat.send_message(UserMessage(text=prompt))

        # Parse JSON from response
        response_text = response.strip()
        if response_text.startswith("```"):
            response_text = response_text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

        mappings = json_module.loads(response_text)
        return {"mappings": mappings}
    except Exception as e:
        logger.error(f"TEPFI auto-map error: {str(e)}")
        return {"mappings": [], "error": str(e)}



# ============= Factor Data Source Auto-Fetch =============

@api_router.post("/factors/fetch-data")
async def fetch_factor_data(request: Request, user: dict = Depends(get_current_user)):
    """Fetch actual values for factors from configured data sources (webhook, web_surf, ai_llm).
    Supports both per-factor and grouped (by factor_type) fetching.
    
    Body: {
      decision_title: str,
      decision_context: str,
      option_name: str,
      factors: [{ id, name, factor_type, data_source: { type, config }, unit, expected_value, operator }]
    }
    Returns: { results: [{ factor_id, value, source_type, raw_response }] }
    """
    from emergentintegrations.llm.chat import LlmChat, UserMessage
    import json as json_module

    body = await request.json()
    decision_title = body.get("decision_title", "")
    decision_context = body.get("decision_context", "")
    option_name = body.get("option_name", "")
    factors = body.get("factors", [])

    if not factors:
        return {"results": []}

    results = []

    # Group factors by data source type for efficiency
    webhook_factors = [f for f in factors if f.get("data_source", {}).get("type") == "webhook"]
    web_surf_factors = [f for f in factors if f.get("data_source", {}).get("type") == "web_surf"]
    ai_llm_factors = [f for f in factors if f.get("data_source", {}).get("type") == "ai_llm"]

    # --- WEBHOOK FETCH ---
    for factor in webhook_factors:
        ds = factor.get("data_source", {})
        config = ds.get("config", {})
        url = config.get("url", "")
        if not url:
            results.append({"factor_id": factor["id"], "value": None, "source_type": "webhook", "error": "No URL configured"})
            continue
        try:
            headers_str = config.get("headers", "{}")
            try:
                custom_headers = json_module.loads(headers_str) if headers_str else {}
            except:
                custom_headers = {}
            payload = {
                "factor_name": factor.get("name", ""),
                "factor_type": factor.get("factor_type", ""),
                "option_name": option_name,
                "decision_title": decision_title,
                "unit": factor.get("unit", ""),
                "expected_value": factor.get("expected_value"),
            }
            async with httpx.AsyncClient(timeout=15.0) as client_http:
                resp = await client_http.post(url, json=payload, headers=custom_headers)
                data = resp.json()
                value = data.get("value", data.get("result", str(data)))
                results.append({"factor_id": factor["id"], "value": value, "source_type": "webhook", "raw_response": str(data)[:500]})
        except Exception as e:
            results.append({"factor_id": factor["id"], "value": None, "source_type": "webhook", "error": str(e)[:200]})

    # --- WEB SURF FETCH ---
    if web_surf_factors:
        api_key = os.getenv("EMERGENT_LLM_KEY")
        if not api_key:
            for f in web_surf_factors:
                results.append({"factor_id": f["id"], "value": None, "source_type": "web_surf", "error": "LLM key not configured"})
        else:
            for factor in web_surf_factors:
                ds = factor.get("data_source", {})
                config = ds.get("config", {})
                search_query = config.get("search_query", "")
                if not search_query:
                    search_query = f"{factor.get('name', '')} {option_name} {decision_title}"
                else:
                    # Template replacement
                    search_query = search_query.replace("{factor}", factor.get("name", ""))
                    search_query = search_query.replace("{option}", option_name)
                    search_query = search_query.replace("{title}", decision_title)
                try:
                    # Real web search using DuckDuckGo
                    search_results_text = ""
                    try:
                        from duckduckgo_search import DDGS
                        with DDGS() as ddgs:
                            ddg_results = list(ddgs.text(search_query, max_results=5))
                        for idx, r in enumerate(ddg_results, 1):
                            search_results_text += f"\n{idx}. {r.get('title', '')}: {r.get('body', '')[:300]}"
                            if r.get('href'):
                                search_results_text += f"\n   Source: {r['href']}"
                    except Exception as search_err:
                        search_results_text = f"(Web search unavailable: {str(search_err)[:100]})"

                    prompt = f"""Based on the following web search results, extract the current real-world value for:

Factor: {factor.get('name', '')}
Option/Subject: {option_name}
Decision Context: {decision_title} - {decision_context}
Expected Unit: {factor.get('unit', 'N/A')}
Data Type: {factor.get('factor_type', 'unknown')}

Web Search Results for "{search_query}":
{search_results_text}

Return ONLY a JSON object with:
- "value": the actual value (number for quantitative, text for qualitative)
- "confidence": "high", "medium", or "low"
- "source_note": brief note about the source of this data

Return ONLY valid JSON, no explanation."""

                    chat = LlmChat(
                        api_key=api_key,
                        session_id=f"websurf_{user['user_id']}_{uuid.uuid4().hex[:8]}",
                        system_message="You are a research assistant. Analyze web search results and extract factual data values. Return only valid JSON."
                    ).with_model("openai", "gpt-4.1-mini")
                    response = await chat.send_message(UserMessage(text=prompt))
                    response_text = response.strip()
                    if response_text.startswith("```"):
                        response_text = response_text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
                    data = json_module.loads(response_text)
                    results.append({
                        "factor_id": factor["id"],
                        "value": data.get("value"),
                        "source_type": "web_surf",
                        "confidence": data.get("confidence", "medium"),
                        "source_note": data.get("source_note", ""),
                    })
                except Exception as e:
                    results.append({"factor_id": factor["id"], "value": None, "source_type": "web_surf", "error": str(e)[:200]})

    # --- AI LLM FETCH ---
    if ai_llm_factors:
        api_key = os.getenv("EMERGENT_LLM_KEY")
        if not api_key:
            for f in ai_llm_factors:
                results.append({"factor_id": f["id"], "value": None, "source_type": "ai_llm", "error": "LLM key not configured"})
        else:
            for factor in ai_llm_factors:
                ds = factor.get("data_source", {})
                config = ds.get("config", {})
                custom_prompt = config.get("prompt", "")
                if not custom_prompt:
                    custom_prompt = f"What is the {factor.get('name', '')} for {option_name}?"
                else:
                    custom_prompt = custom_prompt.replace("{factor}", factor.get("name", ""))
                    custom_prompt = custom_prompt.replace("{option}", option_name)
                    custom_prompt = custom_prompt.replace("{title}", decision_title)
                try:
                    system_msg = f"""You are a decision-support AI. Provide data values for decision factors.
Decision: {decision_title}
Context: {decision_context}
Evaluating option: {option_name}

Return ONLY a JSON object:
- "value": the value ({factor.get('unit', 'appropriate unit')})
- "reasoning": brief explanation (1-2 sentences)

Return ONLY valid JSON, no markdown."""

                    chat = LlmChat(
                        api_key=api_key,
                        session_id=f"aillm_{user['user_id']}_{uuid.uuid4().hex[:8]}",
                        system_message=system_msg
                    ).with_model("openai", "gpt-4.1-mini")
                    response = await chat.send_message(UserMessage(text=custom_prompt))
                    response_text = response.strip()
                    if response_text.startswith("```"):
                        response_text = response_text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
                    data = json_module.loads(response_text)
                    results.append({
                        "factor_id": factor["id"],
                        "value": data.get("value"),
                        "source_type": "ai_llm",
                        "reasoning": data.get("reasoning", ""),
                    })
                except Exception as e:
                    results.append({"factor_id": factor["id"], "value": None, "source_type": "ai_llm", "error": str(e)[:200]})

    return {"results": results}


# ============= CLD (Causal Loop Diagram) Analysis =============

@api_router.post("/cld/analyze")
async def cld_analyze(request: Request, user: dict = Depends(get_current_user)):
    """Generate a Causal Loop Diagram from factors and auto-derive Steps 3-5 values.
    
    Body: { decision_title, decision_context, life_area, decision_type, factors: [{id, name}] }
    Returns: { cld: { nodes, links, loops }, classifications, priorities, ratings }
    """
    from emergentintegrations.llm.chat import LlmChat, UserMessage
    import json as json_module

    body = await request.json()
    title = body.get("decision_title", "")
    context = body.get("decision_context", "")
    life_area = body.get("life_area", "")
    decision_type = body.get("decision_type", "")
    factors = body.get("factors", [])

    if len(factors) < 2:
        raise HTTPException(status_code=400, detail="At least 2 factors required for CLD analysis")

    api_key = os.getenv("EMERGENT_LLM_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="LLM key not configured")

    factor_names = [f.get("name", "") for f in factors]
    factor_ids = [f.get("id", "") for f in factors]
    factor_list_str = "\n".join([f"  {i+1}. {name} (id: {fid})" for i, (name, fid) in enumerate(zip(factor_names, factor_ids))])

    prompt = f"""Analyze the following decision factors using Causal Loop Diagram (CLD) methodology from Systems Thinking.

Decision: {title}
Context: {context}
Life Area: {life_area}
Decision Type: {decision_type}

Factors:
{factor_list_str}

Perform the following analysis and return ONLY a valid JSON object:

1. **CLD Links**: Identify causal relationships between factors. For each link:
   - from_id: source factor id
   - to_id: target factor id  
   - type: "reinforcing" (same direction change) or "balancing" (opposite direction change)
   - strength: 1-5 (how strong the causal link is)
   - description: brief explanation of the causal relationship

2. **CLD Loops**: Identify feedback loops (reinforcing R or balancing B):
   - name: loop name (e.g., "R1: Growth Loop")
   - type: "reinforcing" or "balancing"
   - factor_ids: array of factor ids in the loop

3. **Centrality Scores**: For each factor, compute a centrality score (0.0 to 1.0) based on:
   - Number of incoming/outgoing links
   - Participation in feedback loops
   - Strength of connections

4. **Classifications**: Based on centrality:
   - centrality >= 0.5 → "primary" (essential, highly connected)
   - centrality < 0.5 → "secondary" (supporting, less connected)

5. **Priority Order**: Rank factors from most to least influential based on:
   - Centrality score
   - Number of reinforcing loops participated in
   - Total link strength

6. **Gap Multipliers**: For rating gaps (Step 5):
   - Factors with much higher centrality than the one below → gap_multiplier 2.0-3.0
   - Moderate difference → 1.0-1.5
   - Small difference → 0.5-1.0

Return this exact JSON structure:
{{
  "links": [
    {{"from_id": "...", "to_id": "...", "type": "reinforcing|balancing", "strength": 1-5, "description": "..."}}
  ],
  "loops": [
    {{"name": "R1: ...", "type": "reinforcing|balancing", "factor_ids": ["..."]}}
  ],
  "factor_analysis": [
    {{
      "factor_id": "...",
      "factor_name": "...",
      "centrality": 0.0-1.0,
      "classification": "primary|secondary",
      "priority_rank": 1,
      "gap_multiplier": 0.5-3.0,
      "reasoning": "brief explanation"
    }}
  ]
}}

Return ONLY valid JSON, no markdown fences, no explanation outside the JSON."""

    try:
        chat = LlmChat(
            api_key=api_key,
            session_id=f"cld_{user['user_id']}_{uuid.uuid4().hex[:8]}",
            system_message="You are an expert in Systems Thinking and Causal Loop Diagrams. Analyze factor relationships precisely."
        ).with_model("openai", "gpt-4.1-mini")
        
        response = await chat.send_message(UserMessage(text=prompt))
        response_text = response.strip()
        if response_text.startswith("```"):
            response_text = response_text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        
        cld_data = json_module.loads(response_text)
        
        # Build node positions (circular layout)
        import math
        n = len(factors)
        nodes = []
        for i, factor in enumerate(factors):
            angle = (2 * math.pi * i) / n
            fa = next((fa for fa in cld_data.get("factor_analysis", []) if fa["factor_id"] == factor["id"]), None)
            nodes.append({
                "factor_id": factor["id"],
                "name": factor["name"],
                "x": 200 + 140 * math.cos(angle),
                "y": 200 + 140 * math.sin(angle),
                "centrality": fa["centrality"] if fa else 0.5,
                "classification": fa["classification"] if fa else "secondary",
                "priority_rank": fa["priority_rank"] if fa else i + 1,
                "gap_multiplier": fa["gap_multiplier"] if fa else 1.0,
            })
        
        return {
            "cld": {
                "nodes": nodes,
                "links": cld_data.get("links", []),
                "loops": cld_data.get("loops", []),
            },
            "factor_analysis": cld_data.get("factor_analysis", []),
        }
    except json_module.JSONDecodeError as e:
        raise HTTPException(status_code=500, detail=f"AI returned invalid JSON: {str(e)[:100]}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"CLD analysis failed: {str(e)[:200]}")


# ============= Video Call Sessions (Expert Consultation) =============

# Admin-configurable call duration limits
DEFAULT_CALL_DURATION = 30  # minutes
MIN_CALL_DURATION = 5
MAX_CALL_DURATION = 120

@api_router.get("/call-config")
async def get_call_config():
    """Get admin-configured call settings"""
    config = await db.app_config.find_one({"key": "call_settings"}, {"_id": 0})
    if not config:
        return {
            "min_duration": MIN_CALL_DURATION,
            "max_duration": MAX_CALL_DURATION,
            "default_duration": DEFAULT_CALL_DURATION,
            "provider": "jitsi",
            "jitsi_domain": "meet.jit.si",
        }
    return config.get("value", {})

@api_router.put("/call-config")
async def update_call_config(request: Request, user: dict = Depends(get_current_user)):
    """Update call configuration (admin only)"""
    if user.get("role") not in ADMIN_ROLES:
        raise HTTPException(status_code=403, detail="Admin access required")
    body = await request.json()
    config_value = {
        "min_duration": max(5, min(body.get("min_duration", MIN_CALL_DURATION), 60)),
        "max_duration": max(15, min(body.get("max_duration", MAX_CALL_DURATION), 180)),
        "default_duration": body.get("default_duration", DEFAULT_CALL_DURATION),
        "provider": body.get("provider", "jitsi"),
        "jitsi_domain": body.get("jitsi_domain", "meet.jit.si"),
    }
    await db.app_config.update_one(
        {"key": "call_settings"},
        {"$set": {"key": "call_settings", "value": config_value}},
        upsert=True
    )
    return {"message": "Call config updated", "config": config_value}

@api_router.post("/call-sessions")
async def create_call_session(request: Request, user: dict = Depends(get_current_user)):
    """Create a new video call session with an expert.
    
    Body: {
      expert_id, decision_id, step_number, duration_minutes,
      step_name, share_screen_data (optional)
    }
    """
    body = await request.json()
    expert_id = body.get("expert_id")
    decision_id = body.get("decision_id")
    step_number = body.get("step_number", 0)
    duration_minutes = body.get("duration_minutes", DEFAULT_CALL_DURATION)
    
    # Get call config
    config = await db.app_config.find_one({"key": "call_settings"}, {"_id": 0})
    config_val = config.get("value", {}) if config else {}
    max_dur = config_val.get("max_duration", MAX_CALL_DURATION)
    min_dur = config_val.get("min_duration", MIN_CALL_DURATION)
    provider = config_val.get("provider", "jitsi")
    jitsi_domain = config_val.get("jitsi_domain", "meet.jit.si")
    
    duration_minutes = max(min_dur, min(duration_minutes, max_dur))
    
    # Validate expert exists
    if expert_id:
        expert = await db.experts.find_one({"id": expert_id, "is_active": True}, {"_id": 0})
        if not expert:
            raise HTTPException(status_code=404, detail="Expert not found or inactive")
    
    # Generate unique room
    room_id = f"prr-{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=duration_minutes)
    
    # Build provider-specific room URL
    if provider == "jitsi":
        room_url = f"https://{jitsi_domain}/{room_id}"
    else:
        room_url = f"https://{jitsi_domain}/{room_id}"  # Generic fallback
    
    # Get user info
    user_doc = await db.users.find_one({"user_id": user["user_id"]}, {"_id": 0, "password_hash": 0})
    
    session_doc = {
        "id": str(uuid.uuid4()),
        "room_id": room_id,
        "room_url": room_url,
        "provider": provider,
        "created_by": user["user_id"],
        "creator_name": user_doc.get("name", "User") if user_doc else "User",
        "expert_id": expert_id,
        "decision_id": decision_id,
        "step_number": step_number,
        "step_name": body.get("step_name", f"Step {step_number}"),
        "duration_minutes": duration_minutes,
        "status": "active",
        "created_at": now,
        "expires_at": expires_at,
        "ended_at": None,
        "share_context": {
            "decision_title": body.get("decision_title", ""),
            "step_data": body.get("step_data"),
        },
    }
    
    await db.call_sessions.insert_one(session_doc)
    
    # Send notification to expert if push token exists
    if expert_id:
        expert = await db.experts.find_one({"id": expert_id}, {"_id": 0})
        if expert and expert.get("email"):
            # Create a notification for the expert
            notif = {
                "id": str(uuid.uuid4()),
                "user_email": expert["email"],
                "type": "call_invitation",
                "title": f"Call Request from {session_doc['creator_name']}",
                "body": f"Step {step_number}: {body.get('step_name', '')} - {body.get('decision_title', '')}",
                "data": {
                    "room_url": room_url,
                    "session_id": session_doc["id"],
                    "duration_minutes": duration_minutes,
                    "expires_at": expires_at.isoformat(),
                },
                "read": False,
                "created_at": now,
            }
            await db.notifications.insert_one(notif)
    
    return {
        "session_id": session_doc["id"],
        "room_id": room_id,
        "room_url": room_url,
        "provider": provider,
        "duration_minutes": duration_minutes,
        "expires_at": expires_at.isoformat(),
    }

@api_router.get("/call-sessions/{session_id}")
async def get_call_session(session_id: str, user: dict = Depends(get_current_user)):
    """Get call session details"""
    session = await db.call_sessions.find_one({"id": session_id}, {"_id": 0})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    # Check if expired
    if session.get("expires_at"):
        expires_at = session["expires_at"]
        if isinstance(expires_at, str):
            expires_at = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
        elif expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        
        if datetime.now(timezone.utc) > expires_at:
            if session["status"] == "active":
                await db.call_sessions.update_one({"id": session_id}, {"$set": {"status": "expired"}})
                session["status"] = "expired"
    return session

@api_router.put("/call-sessions/{session_id}/end")
async def end_call_session(session_id: str, user: dict = Depends(get_current_user)):
    """End a call session"""
    result = await db.call_sessions.update_one(
        {"id": session_id},
        {"$set": {"status": "ended", "ended_at": datetime.now(timezone.utc)}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"message": "Call session ended"}

@api_router.get("/call-sessions")
async def list_call_sessions(user: dict = Depends(get_current_user), decision_id: str = None):
    """List call sessions for the current user"""
    query = {"created_by": user["user_id"]}
    if decision_id:
        query["decision_id"] = decision_id
    sessions = await db.call_sessions.find(query, {"_id": 0}).sort("created_at", -1).to_list(50)
    return sessions



# ============= Decision Templates (Admin-curated Context Library) =============

class DecisionTemplate(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    life_area: str
    decision_type: str
    description: str = ""
    factors: List[Factor] = []
    created_by: str = ""
    submitted_by: Optional[str] = None  # user_id who submitted for review
    submitted_by_name: Optional[str] = None
    is_approved: bool = False
    is_official: bool = False  # True for admin-created templates
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class DecisionTemplateCreate(BaseModel):
    name: str
    life_area: str
    decision_type: str
    description: str = ""
    factors: List[Factor] = []

@api_router.get("/decision-templates")
async def get_decision_templates(life_area: Optional[str] = None, decision_type: Optional[str] = None):
    query: dict = {"is_approved": True}
    if life_area:
        query["life_area"] = life_area
    if decision_type:
        query["decision_type"] = decision_type
    templates = await db.decision_templates.find(query).sort("name", 1).to_list(100)
    for t in templates:
        t.pop("_id", None)
    return templates

@api_router.get("/decision-templates/all")
async def get_all_templates(user: dict = Depends(get_current_user)):
    if user.get("role") not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Admin access required")
    templates = await db.decision_templates.find({}).sort("created_at", -1).to_list(200)
    for t in templates:
        t.pop("_id", None)
    return templates

@api_router.post("/decision-templates")
async def create_decision_template(template: DecisionTemplateCreate, user: dict = Depends(get_current_user)):
    """Create a decision template - admin creates approved + official, user creates pending"""
    is_admin = user.get("role") in ["admin", "super_admin"]
    template_dict = template.dict()
    template_dict["id"] = str(uuid.uuid4())
    template_dict["created_by"] = user["user_id"]
    template_dict["submitted_by"] = user["user_id"]
    template_dict["submitted_by_name"] = user.get("name", "")
    template_dict["is_approved"] = is_admin  # Auto-approve for admins
    template_dict["is_official"] = is_admin  # Mark as official if admin-created
    template_dict["created_at"] = datetime.now(timezone.utc)
    await db.decision_templates.insert_one(template_dict)
    return {"id": template_dict["id"], "message": "Template created successfully", "is_approved": is_admin}

@api_router.post("/decision-templates/{template_id}/approve")
async def approve_template(template_id: str, user: dict = Depends(get_current_user)):
    """Admin approves a user-submitted template (can edit before approving)"""
    if user.get("role") not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Admin access required")
    result = await db.decision_templates.update_one(
        {"id": template_id},
        {"$set": {"is_approved": True}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Template not found")
    return {"message": "Template approved"}

@api_router.post("/decision-templates/{template_id}/clone")
async def clone_template(template_id: str, user: dict = Depends(get_current_user)):
    """Admin clones a template for editing before approval"""
    if user.get("role") not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Admin access required")
    template = await db.decision_templates.find_one({"id": template_id})
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    template.pop("_id", None)
    template["id"] = str(uuid.uuid4())
    template["created_by"] = user["user_id"]
    template["is_official"] = True
    template["is_approved"] = False  # Not approved until explicitly done
    template["name"] = f"{template['name']} (Copy)"
    template["created_at"] = datetime.now(timezone.utc)
    await db.decision_templates.insert_one(template)
    return {"id": template["id"], "message": "Template cloned successfully"}

@api_router.put("/decision-templates/{template_id}")
async def update_decision_template(template_id: str, template: DecisionTemplateCreate, user: dict = Depends(get_current_user)):
    if user.get("role") not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Admin access required")
    update_dict = template.dict()
    result = await db.decision_templates.update_one({"id": template_id}, {"$set": update_dict})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Template not found")
    return {"message": "Template updated successfully"}

@api_router.delete("/decision-templates/{template_id}")
async def delete_decision_template(template_id: str, user: dict = Depends(get_current_user)):
    if user.get("role") not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Admin access required")
    result = await db.decision_templates.delete_one({"id": template_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Template not found")
    return {"message": "Template deleted successfully"}

@api_router.get("/decision-meta")
async def get_decision_meta():
    return {
        "life_areas": [
            {"id": "career", "name": "Career & Work", "icon": "briefcase"},
            {"id": "finance", "name": "Finance & Investment", "icon": "cash"},
            {"id": "health", "name": "Health & Wellness", "icon": "fitness"},
            {"id": "relationships", "name": "Relationships & Family", "icon": "people"},
            {"id": "education", "name": "Education & Learning", "icon": "school"},
            {"id": "personal", "name": "Personal Growth", "icon": "rocket"},
            {"id": "business", "name": "Business & Entrepreneurship", "icon": "trending-up"},
            {"id": "lifestyle", "name": "Lifestyle & Living", "icon": "home"},
        ],
        "decision_types": [
            {"id": "problem", "name": "Problem", "description": "Solving a current issue or challenge", "color": "#EF4444"},
            {"id": "need", "name": "Need", "description": "Fulfilling a requirement or necessity", "color": "#F59E0B"},
            {"id": "aspiration", "name": "Aspiration", "description": "Pursuing a goal or ambition", "color": "#10B981"},
        ]
    }


# ========================
# MODULAR ROUTES (Refactored)
# ========================
# Import and include modular route files
from routes.tools import router as tools_router
from routes.admin import router as admin_router

api_router.include_router(tools_router)
api_router.include_router(admin_router)


# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
