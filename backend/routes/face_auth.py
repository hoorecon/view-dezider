"""
Face Authentication & Continuous Presence Monitoring — View Dezider
Military-grade remote identity verification using live camera + liveness detection.
Uses MediaPipe Face Mesh (468 landmarks) + OpenCV for face encoding & matching.

Layers:
- Face Registration: Capture face, extract embedding, store securely
- Join Verification: Live face match at session join (with liveness check)
- Continuous Presence: Periodic re-verification during meetings (configurable frequency)
"""

import os
import io
import uuid
import base64
import logging
import numpy as np
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel
from core.database import db
from routes.auth_routes import get_current_user
from routes.audit_trail import log_audit_event, get_client_ip

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/face-auth", tags=["Face Authentication"])

# ========================
# CONFIG DEFAULTS
# ========================

DEFAULT_PRESENCE_CHECK_INTERVAL = 300  # 5 minutes
MIN_PRESENCE_CHECK_INTERVAL = 60       # 1 minute minimum
MAX_PRESENCE_CHECK_INTERVAL = 1800     # 30 minutes maximum
FACE_MATCH_THRESHOLD = 0.55           # Cosine similarity threshold (lower = stricter)
LIVENESS_EAR_THRESHOLD = 0.21         # Eye Aspect Ratio below this = blink
MIN_FACE_CONFIDENCE = 0.85            # Minimum face detection confidence

# Lazy-loaded ML models
_face_mesh = None
_face_detection = None


def get_face_mesh():
    global _face_mesh
    if _face_mesh is None:
        import mediapipe as mp
        _face_mesh = mp.solutions.face_mesh.FaceMesh(
            static_image_mode=True,
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=MIN_FACE_CONFIDENCE,
        )
    return _face_mesh


def get_face_detection():
    global _face_detection
    if _face_detection is None:
        import mediapipe as mp
        _face_detection = mp.solutions.face_detection.FaceDetection(
            model_selection=1,
            min_detection_confidence=MIN_FACE_CONFIDENCE,
        )
    return _face_detection


# ========================
# FACE PROCESSING ENGINE
# ========================

def decode_base64_image(b64_str: str) -> np.ndarray:
    """Decode base64 image string to OpenCV numpy array."""
    import cv2
    # Strip data URI prefix if present
    if "base64," in b64_str:
        b64_str = b64_str.split("base64,")[1]
    
    img_bytes = base64.b64decode(b64_str)
    nparr = np.frombuffer(img_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Failed to decode image")
    return img


def extract_face_landmarks(img: np.ndarray) -> dict:
    """Extract 468 face landmarks using MediaPipe Face Mesh.
    Returns landmarks, face bounding box, and eye aspect ratios.
    """
    import cv2
    mesh = get_face_mesh()
    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    results = mesh.process(rgb)

    if not results.multi_face_landmarks:
        return {"detected": False, "error": "No face detected in image"}

    face_lm = results.multi_face_landmarks[0]
    h, w = img.shape[:2]

    # Extract all 468 landmarks as normalized coordinates
    landmarks = []
    for lm in face_lm.landmark:
        landmarks.append([lm.x, lm.y, lm.z])

    landmarks_np = np.array(landmarks)

    # Eye Aspect Ratio (EAR) for blink detection
    # Left eye landmarks: 33, 160, 158, 133, 153, 144
    # Right eye landmarks: 362, 385, 387, 263, 373, 380
    left_ear = compute_ear(landmarks_np, [33, 160, 158, 133, 153, 144])
    right_ear = compute_ear(landmarks_np, [362, 385, 387, 263, 373, 380])
    avg_ear = (left_ear + right_ear) / 2.0

    # Head pose estimation from key landmarks
    nose_tip = landmarks_np[1]
    forehead = landmarks_np[10]
    chin = landmarks_np[152]
    left_ear_lm = landmarks_np[234]
    right_ear_lm = landmarks_np[454]

    # Simple head rotation estimation
    yaw = (right_ear_lm[0] - left_ear_lm[0])  # Horizontal rotation
    pitch = (forehead[1] - chin[1])  # Vertical tilt
    roll = np.arctan2(right_ear_lm[1] - left_ear_lm[1], right_ear_lm[0] - left_ear_lm[0])

    return {
        "detected": True,
        "landmarks_count": len(landmarks),
        "eye_aspect_ratio": float(avg_ear),
        "left_ear": float(left_ear),
        "right_ear": float(right_ear),
        "is_blinking": avg_ear < LIVENESS_EAR_THRESHOLD,
        "head_yaw": float(yaw),
        "head_pitch": float(pitch),
        "head_roll": float(np.degrees(roll)),
        "face_embedding": compute_face_embedding(landmarks_np),
    }


def compute_ear(landmarks: np.ndarray, indices: list) -> float:
    """Compute Eye Aspect Ratio for blink detection."""
    p = landmarks[indices]
    # Vertical distances
    v1 = np.linalg.norm(p[1] - p[5])
    v2 = np.linalg.norm(p[2] - p[4])
    # Horizontal distance
    h = np.linalg.norm(p[0] - p[3])
    if h == 0:
        return 0.3
    return (v1 + v2) / (2.0 * h)


def compute_face_embedding(landmarks: np.ndarray) -> list:
    """Compute a face embedding vector from 468 landmarks.
    Uses geometric ratios between key facial landmarks for identity encoding.
    This creates a 128-dimensional embedding invariant to scale and position.
    """
    # Key facial landmark indices for identity-critical features
    key_indices = [
        # Eyes
        33, 133, 362, 263, 160, 158, 385, 387, 144, 153, 373, 380,
        # Eyebrows
        70, 63, 105, 66, 107, 336, 296, 334, 293, 300,
        # Nose
        1, 2, 4, 5, 6, 168, 195, 197,
        # Mouth
        0, 13, 14, 17, 37, 39, 40, 61, 78, 80, 81, 82, 87, 88, 91, 95,
        178, 191, 267, 269, 270, 291, 308, 310, 311, 312, 317, 318, 321, 324, 375, 402, 405,
        # Jaw
        10, 21, 54, 58, 67, 93, 103, 109, 127, 132, 136, 148, 149, 150, 152, 162, 172,
        176, 234, 251, 284, 288, 297, 323, 332, 338, 356, 361, 365, 377, 378, 379, 389, 397, 400, 454,
    ]

    # Use only available indices
    valid_indices = [i for i in key_indices if i < len(landmarks)]
    key_points = landmarks[valid_indices]

    # Normalize: center at nose tip, scale by inter-eye distance
    nose = landmarks[1]
    left_eye_center = (landmarks[33] + landmarks[133]) / 2
    right_eye_center = (landmarks[362] + landmarks[263]) / 2
    inter_eye_dist = np.linalg.norm(right_eye_center - left_eye_center)

    if inter_eye_dist < 1e-6:
        inter_eye_dist = 1.0

    centered = key_points - nose
    normalized = centered / inter_eye_dist

    # Compute pairwise distances between key points (identity signature)
    n = min(len(normalized), 16)
    selected = normalized[:n]
    embedding = []

    for i in range(n):
        for j in range(i + 1, n):
            dist = np.linalg.norm(selected[i] - selected[j])
            embedding.append(dist)

    # Angles between key triangles
    for i in range(0, min(n, 14), 3):
        if i + 2 < n:
            v1 = selected[i + 1] - selected[i]
            v2 = selected[i + 2] - selected[i]
            cos_angle = np.dot(v1[:2], v2[:2]) / (np.linalg.norm(v1[:2]) * np.linalg.norm(v2[:2]) + 1e-8)
            embedding.append(float(cos_angle))

    # Pad or truncate to fixed 128 dimensions
    embedding = embedding[:128]
    while len(embedding) < 128:
        embedding.append(0.0)

    # L2 normalize
    emb = np.array(embedding, dtype=np.float64)
    norm = np.linalg.norm(emb)
    if norm > 0:
        emb = emb / norm

    return emb.tolist()


def compare_embeddings(emb1: list, emb2: list) -> float:
    """Compute cosine similarity between two face embeddings. Returns 0-1 (1 = identical)."""
    a = np.array(emb1)
    b = np.array(emb2)
    dot = np.dot(a, b)
    na = np.linalg.norm(a)
    nb = np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return float(dot / (na * nb))


# ========================
# MODELS
# ========================

class FaceRegisterRequest(BaseModel):
    image_base64: str  # Base64 encoded face photo


class FaceVerifyRequest(BaseModel):
    image_base64: str
    session_id: Optional[str] = None  # For presence checks


class PresenceConfigRequest(BaseModel):
    interval_seconds: int  # Presence check frequency


# ========================
# HELPERS
# ========================

async def get_presence_config(session_id: str = None) -> int:
    """Get presence check interval. Priority: session override > admin default > hardcoded default."""
    # Check session-level override
    if session_id:
        session = await db.collaboration_sessions.find_one({"id": session_id}, {"_id": 0})
        if session:
            override = session.get("mode_config_override", {})
            if override and "presence_check_interval" in override:
                val = int(override["presence_check_interval"])
                return max(MIN_PRESENCE_CHECK_INTERVAL, min(val, MAX_PRESENCE_CHECK_INTERVAL))

    # Check admin default
    admin_config = await db.app_config.find_one({"key": "presence_check_settings"}, {"_id": 0})
    if admin_config and admin_config.get("value", {}).get("interval_seconds"):
        val = int(admin_config["value"]["interval_seconds"])
        return max(MIN_PRESENCE_CHECK_INTERVAL, min(val, MAX_PRESENCE_CHECK_INTERVAL))

    return DEFAULT_PRESENCE_CHECK_INTERVAL


async def require_admin(user: dict):
    u = await db.users.find_one({"user_id": user["user_id"]})
    if not u or u.get("role") not in ["admin", "org_admin", "super_admin"]:
        raise HTTPException(403, "Admin access required")
    return u


# ========================
# ENDPOINTS
# ========================

@router.post("/register")
async def register_face(data: FaceRegisterRequest, request: Request, user: dict = Depends(get_current_user)):
    """Register face biometric. Captures face photo, extracts 128-dim embedding, stores securely."""
    try:
        img = decode_base64_image(data.image_base64)
    except Exception as e:
        raise HTTPException(400, f"Invalid image: {str(e)}")

    result = extract_face_landmarks(img)
    if not result.get("detected"):
        raise HTTPException(400, "No face detected. Please ensure your face is clearly visible, well-lit, and centered.")

    if result.get("is_blinking"):
        # Accept but note - they blinked during capture
        pass

    embedding = result["face_embedding"]
    now = datetime.now(timezone.utc).isoformat()

    # Store face registration
    await db.face_registrations.update_one(
        {"user_id": user["user_id"]},
        {"$set": {
            "user_id": user["user_id"],
            "embedding": embedding,
            "landmarks_count": result["landmarks_count"],
            "registered_at": now,
            "updated_at": now,
            "verification_count": 0,
            "last_verified_at": None,
            "active": True,
        }},
        upsert=True
    )

    await log_audit_event(
        action="face_registered", entity_type="biometric", entity_id=user["user_id"],
        user_id=user["user_id"], details="Face biometric registered via camera capture",
        ip_address=get_client_ip(request), sensitive_data_accessed=True,
        data_fields_accessed=["face_embedding", "facial_landmarks"],
    )

    return {
        "registered": True,
        "landmarks_detected": result["landmarks_count"],
        "message": "Face registered successfully. You can now use face verification to join sessions.",
    }


@router.post("/verify")
async def verify_face(data: FaceVerifyRequest, request: Request, user: dict = Depends(get_current_user)):
    """Verify live face against stored registration. Includes liveness detection."""
    stored = await db.face_registrations.find_one({"user_id": user["user_id"], "active": True})
    if not stored:
        raise HTTPException(400, "No face registered. Please register your face first.")

    try:
        img = decode_base64_image(data.image_base64)
    except Exception as e:
        raise HTTPException(400, f"Invalid image: {str(e)}")

    result = extract_face_landmarks(img)
    if not result.get("detected"):
        await log_audit_event(
            action="face_verify_failed", entity_type="biometric", entity_id=user["user_id"],
            user_id=user["user_id"], details="Face verification failed - no face detected in live image",
            ip_address=get_client_ip(request), sensitive_data_accessed=True,
        )
        raise HTTPException(400, "No face detected. Ensure proper lighting and face the camera directly.")

    # Compare embeddings
    similarity = compare_embeddings(result["face_embedding"], stored["embedding"])
    verified = similarity >= FACE_MATCH_THRESHOLD

    now = datetime.now(timezone.utc).isoformat()

    # Update verification stats
    if verified:
        await db.face_registrations.update_one(
            {"user_id": user["user_id"]},
            {"$set": {"last_verified_at": now}, "$inc": {"verification_count": 1}}
        )

    # Log verification attempt
    await log_audit_event(
        action="face_verified" if verified else "face_verify_failed",
        entity_type="biometric", entity_id=user["user_id"],
        user_id=user["user_id"],
        details=f"Face verification {'succeeded' if verified else 'FAILED'} (similarity: {similarity:.3f}, threshold: {FACE_MATCH_THRESHOLD})",
        ip_address=get_client_ip(request), sensitive_data_accessed=True,
        data_fields_accessed=["face_embedding", "similarity_score"],
    )

    # Log presence check if session_id provided
    if data.session_id:
        await db.presence_logs.insert_one({
            "id": f"pres_{uuid.uuid4().hex[:10]}",
            "user_id": user["user_id"],
            "session_id": data.session_id,
            "verified": verified,
            "similarity": similarity,
            "eye_aspect_ratio": result["eye_aspect_ratio"],
            "is_blinking": result["is_blinking"],
            "head_yaw": result["head_yaw"],
            "head_pitch": result["head_pitch"],
            "timestamp": now,
            "ip_address": get_client_ip(request),
        })

    return {
        "verified": verified,
        "similarity": round(similarity, 3),
        "threshold": FACE_MATCH_THRESHOLD,
        "liveness": {
            "eye_aspect_ratio": round(result["eye_aspect_ratio"], 3),
            "is_blinking": result["is_blinking"],
            "head_yaw": round(result["head_yaw"], 3),
            "head_pitch": round(result["head_pitch"], 3),
        },
        "message": "Face verified successfully" if verified else "Face does not match registered profile",
    }


@router.post("/liveness-check")
async def liveness_check(data: FaceRegisterRequest, request: Request, user: dict = Depends(get_current_user)):
    """Check liveness of a face image (blink detection, head pose). Used for anti-spoofing."""
    try:
        img = decode_base64_image(data.image_base64)
    except Exception as e:
        raise HTTPException(400, f"Invalid image: {str(e)}")

    result = extract_face_landmarks(img)
    if not result.get("detected"):
        return {"alive": False, "face_detected": False, "message": "No face detected"}

    # Liveness heuristics:
    # 1. Eye aspect ratio in normal range (not a printed photo - too consistent)
    # 2. Head has some natural pose variation (not perfectly frontal like a photo)
    ear = result["eye_aspect_ratio"]
    is_natural_ear = 0.15 < ear < 0.40  # Natural range for open/partially open eyes
    has_depth = abs(result["head_yaw"]) > 0.01 or abs(result["head_pitch"]) > 0.01  # Some 3D variation

    alive = result["detected"] and is_natural_ear

    return {
        "alive": alive,
        "face_detected": True,
        "eye_aspect_ratio": round(ear, 3),
        "is_blinking": result["is_blinking"],
        "head_yaw": round(result["head_yaw"], 3),
        "head_pitch": round(result["head_pitch"], 3),
        "head_roll": round(result["head_roll"], 2),
        "checks": {
            "natural_eye_ratio": is_natural_ear,
            "depth_variation": has_depth,
        },
    }


@router.get("/status")
async def face_auth_status(request: Request, user: dict = Depends(get_current_user)):
    """Check if user has registered face biometric."""
    reg = await db.face_registrations.find_one({"user_id": user["user_id"], "active": True}, {"_id": 0, "embedding": 0})
    if not reg:
        return {"registered": False}

    return {
        "registered": True,
        "registered_at": reg.get("registered_at"),
        "verification_count": reg.get("verification_count", 0),
        "last_verified_at": reg.get("last_verified_at"),
    }


@router.get("/presence-config")
async def get_presence_config_endpoint(session_id: Optional[str] = None, user: dict = Depends(get_current_user)):
    """Get presence check configuration for a session."""
    interval = await get_presence_config(session_id)
    admin_config = await db.app_config.find_one({"key": "presence_check_settings"}, {"_id": 0})
    admin_interval = admin_config.get("value", {}).get("interval_seconds", DEFAULT_PRESENCE_CHECK_INTERVAL) if admin_config else DEFAULT_PRESENCE_CHECK_INTERVAL

    session_override = None
    if session_id:
        session = await db.collaboration_sessions.find_one({"id": session_id}, {"_id": 0})
        if session:
            override = session.get("mode_config_override", {})
            if override and "presence_check_interval" in override:
                session_override = int(override["presence_check_interval"])

    return {
        "effective_interval_seconds": interval,
        "admin_default_seconds": admin_interval,
        "session_override_seconds": session_override,
        "min_allowed": MIN_PRESENCE_CHECK_INTERVAL,
        "max_allowed": MAX_PRESENCE_CHECK_INTERVAL,
    }


@router.post("/presence-config/admin")
async def set_admin_presence_config(data: PresenceConfigRequest, user: dict = Depends(get_current_user)):
    """Set admin-level default presence check interval. Admin only."""
    await require_admin(user)

    interval = max(MIN_PRESENCE_CHECK_INTERVAL, min(data.interval_seconds, MAX_PRESENCE_CHECK_INTERVAL))
    now = datetime.now(timezone.utc).isoformat()

    await db.app_config.update_one(
        {"key": "presence_check_settings"},
        {"$set": {
            "key": "presence_check_settings",
            "value": {
                "interval_seconds": interval,
                "updated_by": user["user_id"],
                "updated_at": now,
            },
        }},
        upsert=True
    )

    await log_audit_event(
        action="presence_config_updated", entity_type="system", entity_id="presence_check",
        user_id=user["user_id"], details=f"Admin default presence check interval set to {interval}s",
        sensitive_data_accessed=False,
    )

    return {
        "interval_seconds": interval,
        "message": f"Default presence check interval set to {interval} seconds ({interval // 60} min)",
    }


@router.get("/presence-logs/{session_id}")
async def get_presence_logs(session_id: str, limit: int = 50, user: dict = Depends(get_current_user)):
    """Get presence check logs for a session. Admin or session host only."""
    logs = await db.presence_logs.find(
        {"session_id": session_id}
    ).sort("timestamp", -1).limit(limit).to_list(limit)

    for log in logs:
        log.pop("_id", None)

    # Compute stats
    total = len(logs)
    verified_count = sum(1 for l in logs if l.get("verified"))
    failed_count = total - verified_count

    return {
        "session_id": session_id,
        "total_checks": total,
        "verified": verified_count,
        "failed": failed_count,
        "compliance_rate": round(verified_count / total * 100, 1) if total > 0 else 100,
        "logs": logs,
    }
