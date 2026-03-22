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

class UserLogin(BaseModel):
    email: EmailStr
    password: str

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
# PRR DECISION ROUTES
# ========================

@api_router.post("/decisions", response_model=dict)
async def create_decision(decision: PRRDecisionCreate, user: dict = Depends(get_current_user)):
    """Create a new PRR decision"""
    decision_doc = PRRDecision(
        user_id=user["user_id"],
        title=decision.title,
        context=decision.context,
        folder=decision.folder
    )
    
    await db.decisions.insert_one(decision_doc.dict())
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
    
    # Create notifications for each recipient
    for r in recipients:
        await create_notification(
            r["user_id"],
            "share_invite",
            "Step Shared With You",
            f'{user.get("name", user["email"])} shared Step {data.step_number} of "{decision.get("title", "a decision")}" with you',
            {"share_id": share_doc["id"], "decision_id": decision_id, "step_number": data.step_number}
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

async def create_notification(user_id: str, notif_type: str, title: str, message: str, data: dict = None):
    """Helper function to create a notification"""
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
    return notif

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

# ============= Decision Templates (Admin-curated Context Library) =============

class DecisionTemplate(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    life_area: str
    decision_type: str
    description: str = ""
    factors: List[Factor] = []
    created_by: str = ""
    is_approved: bool = False
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
    if user.get("role") not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Admin access required")
    template_dict = template.dict()
    template_dict["id"] = str(uuid.uuid4())
    template_dict["created_by"] = user["user_id"]
    template_dict["is_approved"] = True
    template_dict["created_at"] = datetime.now(timezone.utc)
    await db.decision_templates.insert_one(template_dict)
    return {"id": template_dict["id"], "message": "Template created successfully"}

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
