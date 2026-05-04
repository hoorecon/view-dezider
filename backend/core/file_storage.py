"""Pluggable file storage backend for View Dezider.

Design:
- Abstract interface `StorageBackend` → `save()` returns an opaque `storage_uri`
  which is saved in MongoDB instead of raw base64.
- Retrieval via `get()` fetches from whichever backend stored it.
- Default backend = Mongo collection `pp_files` (works out-of-the-box, no env
  config needed). Swap to S3 or GCS via `pp_admin_config[storage_backend]`
  and the corresponding env vars.

Admin-configurable via `pp_admin_config` Mongo collection:
- `storage_backend`:  "mongo" (default) | "s3" | "gcs"
- `upload_limits`:   per-upload-category caps + allowed MIME types

Upload categories (extensible — just add a key to DEFAULT_UPLOAD_LIMITS):
- pp_org_verification_doc
- pp_org_authorized_id
- pp_org_brand_logo
- pp_org_general_attachment
- profile_photo (future)
- decision_attachment (future)
"""

import os
import uuid
import base64
import logging
import hashlib
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from core.database import db

logger = logging.getLogger(__name__)


# ============================================================
# DEFAULTS (admin-overridable via pp_admin_config)
# ============================================================

DEFAULT_UPLOAD_LIMITS = {
    "pp_org_verification_doc": {
        "max_size_mb": 5,
        "allowed_mime_types": ["application/pdf", "image/jpeg", "image/png", "image/webp"],
        "label": "Registration certificate (PDF or image)",
    },
    "pp_org_authorized_id": {
        "max_size_mb": 3,
        "allowed_mime_types": ["application/pdf", "image/jpeg", "image/png", "image/webp"],
        "label": "Authorized applicant ID",
    },
    "pp_org_brand_logo": {
        "max_size_mb": 2,
        "allowed_mime_types": ["image/jpeg", "image/png", "image/webp", "image/svg+xml"],
        "label": "Brand logo",
    },
    "pp_org_general_attachment": {
        "max_size_mb": 10,
        "allowed_mime_types": ["application/pdf", "image/jpeg", "image/png", "image/webp", "application/msword", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"],
        "label": "General attachment",
    },
    "profile_photo": {
        "max_size_mb": 2,
        "allowed_mime_types": ["image/jpeg", "image/png", "image/webp"],
        "label": "Profile photo",
    },
    "decision_attachment": {
        "max_size_mb": 10,
        "allowed_mime_types": ["application/pdf", "image/jpeg", "image/png", "image/webp", "application/msword", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "application/vnd.ms-excel", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"],
        "label": "Decision attachment",
    },
}

DEFAULT_STORAGE_BACKEND = "mongo"


# ============================================================
# CONFIG ACCESSORS
# ============================================================

async def get_upload_limit(category: str) -> Dict[str, Any]:
    """Returns the active {max_size_mb, allowed_mime_types, label} for a category."""
    cfg = await db.pp_admin_config.find_one({"key": "upload_limits"}, {"_id": 0})
    overrides = (cfg or {}).get("value", {})
    merged = {**(DEFAULT_UPLOAD_LIMITS.get(category) or {}), **(overrides.get(category) or {})}
    if not merged:
        return {"max_size_mb": 5, "allowed_mime_types": ["*/*"], "label": category}
    return merged


async def get_storage_backend_name() -> str:
    cfg = await db.pp_admin_config.find_one({"key": "storage_backend"}, {"_id": 0})
    return (cfg or {}).get("value") or DEFAULT_STORAGE_BACKEND


# ============================================================
# VALIDATION
# ============================================================

class UploadValidationError(Exception):
    pass


def _estimate_base64_size(b64: str) -> int:
    """Actual byte count of base64-decoded payload."""
    padding = b64.count("=")
    return (len(b64) * 3) // 4 - padding


async def validate_upload(b64: str, mime: str, filename: str, category: str) -> Dict[str, Any]:
    """Validate an upload against admin-configured limits for its category.

    Returns resolved limits dict on success, raises UploadValidationError otherwise.
    """
    limits = await get_upload_limit(category)
    max_bytes = int(limits.get("max_size_mb", 5)) * 1024 * 1024
    size = _estimate_base64_size(b64)
    if size > max_bytes:
        raise UploadValidationError(
            f"File exceeds max size of {limits['max_size_mb']} MB (got {size / 1024 / 1024:.1f} MB)"
        )

    allowed = limits.get("allowed_mime_types") or ["*/*"]
    if "*/*" not in allowed and mime not in allowed:
        raise UploadValidationError(
            f"File type '{mime}' not allowed. Allowed: {', '.join(allowed)}"
        )
    return limits


# ============================================================
# BACKEND INTERFACE
# ============================================================

class StorageBackend:
    name: str = "abstract"

    async def save(self, b64: str, filename: str, mime: str, category: str, owner_user_id: str) -> Dict[str, Any]:
        """Persist a file; return {"storage_uri": "...", "size_bytes": int, "mime": str, "filename": str, "checksum": str}."""
        raise NotImplementedError

    async def get(self, storage_uri: str) -> Optional[Dict[str, Any]]:
        """Fetch a file; return {"b64": str, "mime": str, "filename": str} or None."""
        raise NotImplementedError

    async def delete(self, storage_uri: str) -> bool:
        raise NotImplementedError


# ============================================================
# MONGO BACKEND (default — works out of the box)
# ============================================================

class MongoStorageBackend(StorageBackend):
    name = "mongo"

    async def save(self, b64: str, filename: str, mime: str, category: str, owner_user_id: str) -> Dict[str, Any]:
        file_id = str(uuid.uuid4())
        size = _estimate_base64_size(b64)
        checksum = hashlib.sha256(b64.encode()).hexdigest()[:16]
        doc = {
            "file_id": file_id,
            "category": category,
            "owner_user_id": owner_user_id,
            "filename": filename,
            "mime": mime,
            "size_bytes": size,
            "checksum": checksum,
            "b64": b64,
            "backend": "mongo",
            "created_at": datetime.now(timezone.utc),
        }
        await db.pp_files.insert_one(doc)
        return {
            "storage_uri": f"mongo://pp_files/{file_id}",
            "file_id": file_id,
            "size_bytes": size,
            "mime": mime,
            "filename": filename,
            "checksum": checksum,
        }

    async def get(self, storage_uri: str) -> Optional[Dict[str, Any]]:
        if not storage_uri.startswith("mongo://pp_files/"):
            return None
        file_id = storage_uri.replace("mongo://pp_files/", "")
        doc = await db.pp_files.find_one({"file_id": file_id}, {"_id": 0})
        if not doc:
            return None
        return {"b64": doc["b64"], "mime": doc["mime"], "filename": doc["filename"]}

    async def delete(self, storage_uri: str) -> bool:
        if not storage_uri.startswith("mongo://pp_files/"):
            return False
        file_id = storage_uri.replace("mongo://pp_files/", "")
        result = await db.pp_files.delete_one({"file_id": file_id})
        return result.deleted_count > 0


# ============================================================
# S3 BACKEND (AWS — requires env keys + boto3)
# ============================================================

class S3StorageBackend(StorageBackend):
    name = "s3"

    def __init__(self):
        self.bucket = os.environ.get("AWS_S3_BUCKET", "")
        self.region = os.environ.get("AWS_S3_REGION", "ap-south-1")
        self.prefix = os.environ.get("AWS_S3_PREFIX", "view-dezider/")
        self.access_key = os.environ.get("AWS_ACCESS_KEY_ID", "")
        self.secret_key = os.environ.get("AWS_SECRET_ACCESS_KEY", "")

    def _client(self):
        try:
            import boto3  # type: ignore
        except ImportError:
            raise UploadValidationError("S3 backend requires `boto3`. Install via `pip install boto3`.")
        if not self.bucket or not self.access_key:
            raise UploadValidationError("S3 backend not configured. Set AWS_S3_BUCKET + AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY.")
        return boto3.client(
            "s3",
            region_name=self.region,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
        )

    async def save(self, b64: str, filename: str, mime: str, category: str, owner_user_id: str) -> Dict[str, Any]:
        file_id = str(uuid.uuid4())
        size = _estimate_base64_size(b64)
        checksum = hashlib.sha256(b64.encode()).hexdigest()[:16]
        key = f"{self.prefix}{category}/{file_id}/{filename}"
        body = base64.b64decode(b64)

        client = self._client()
        # boto3 is sync — for true async, user should switch to aioboto3. Acceptable for MVP.
        client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=body,
            ContentType=mime,
            Metadata={
                "owner_user_id": owner_user_id,
                "category": category,
                "checksum": checksum,
            },
            ServerSideEncryption="AES256",
        )
        # Index record in Mongo so we can list/delete without hitting S3
        await db.pp_files.insert_one({
            "file_id": file_id,
            "category": category,
            "owner_user_id": owner_user_id,
            "filename": filename,
            "mime": mime,
            "size_bytes": size,
            "checksum": checksum,
            "s3_bucket": self.bucket,
            "s3_key": key,
            "backend": "s3",
            "created_at": datetime.now(timezone.utc),
        })
        return {
            "storage_uri": f"s3://{self.bucket}/{key}",
            "file_id": file_id,
            "size_bytes": size,
            "mime": mime,
            "filename": filename,
            "checksum": checksum,
        }

    async def get(self, storage_uri: str) -> Optional[Dict[str, Any]]:
        if not storage_uri.startswith("s3://"):
            return None
        without_scheme = storage_uri.replace("s3://", "", 1)
        bucket, key = without_scheme.split("/", 1)
        client = self._client()
        try:
            obj = client.get_object(Bucket=bucket, Key=key)
            body_bytes = obj["Body"].read()
            mime = obj.get("ContentType", "application/octet-stream")
            filename = key.rsplit("/", 1)[-1]
            return {"b64": base64.b64encode(body_bytes).decode(), "mime": mime, "filename": filename}
        except Exception as e:
            logger.error(f"S3 get failed {storage_uri}: {e}")
            return None

    async def delete(self, storage_uri: str) -> bool:
        if not storage_uri.startswith("s3://"):
            return False
        without_scheme = storage_uri.replace("s3://", "", 1)
        bucket, key = without_scheme.split("/", 1)
        client = self._client()
        try:
            client.delete_object(Bucket=bucket, Key=key)
            await db.pp_files.delete_one({"s3_bucket": bucket, "s3_key": key})
            return True
        except Exception as e:
            logger.error(f"S3 delete failed {storage_uri}: {e}")
            return False


# ============================================================
# GCS BACKEND (Google Cloud Storage — requires env keys + google-cloud-storage)
# ============================================================

class GCSStorageBackend(StorageBackend):
    name = "gcs"

    def __init__(self):
        self.bucket_name = os.environ.get("GCS_BUCKET", "")
        self.prefix = os.environ.get("GCS_PREFIX", "view-dezider/")
        # GCS client picks up GOOGLE_APPLICATION_CREDENTIALS env var automatically

    def _client(self):
        try:
            from google.cloud import storage  # type: ignore
        except ImportError:
            raise UploadValidationError("GCS backend requires `google-cloud-storage`. Install via `pip install google-cloud-storage`.")
        if not self.bucket_name:
            raise UploadValidationError("GCS backend not configured. Set GCS_BUCKET + GOOGLE_APPLICATION_CREDENTIALS.")
        return storage.Client()

    async def save(self, b64: str, filename: str, mime: str, category: str, owner_user_id: str) -> Dict[str, Any]:
        file_id = str(uuid.uuid4())
        size = _estimate_base64_size(b64)
        checksum = hashlib.sha256(b64.encode()).hexdigest()[:16]
        key = f"{self.prefix}{category}/{file_id}/{filename}"
        body = base64.b64decode(b64)

        client = self._client()
        bucket = client.bucket(self.bucket_name)
        blob = bucket.blob(key)
        blob.metadata = {"owner_user_id": owner_user_id, "category": category, "checksum": checksum}
        blob.upload_from_string(body, content_type=mime)

        await db.pp_files.insert_one({
            "file_id": file_id,
            "category": category,
            "owner_user_id": owner_user_id,
            "filename": filename,
            "mime": mime,
            "size_bytes": size,
            "checksum": checksum,
            "gcs_bucket": self.bucket_name,
            "gcs_key": key,
            "backend": "gcs",
            "created_at": datetime.now(timezone.utc),
        })
        return {
            "storage_uri": f"gcs://{self.bucket_name}/{key}",
            "file_id": file_id,
            "size_bytes": size,
            "mime": mime,
            "filename": filename,
            "checksum": checksum,
        }

    async def get(self, storage_uri: str) -> Optional[Dict[str, Any]]:
        if not storage_uri.startswith("gcs://"):
            return None
        without_scheme = storage_uri.replace("gcs://", "", 1)
        bucket_name, key = without_scheme.split("/", 1)
        client = self._client()
        try:
            bucket = client.bucket(bucket_name)
            blob = bucket.blob(key)
            body_bytes = blob.download_as_bytes()
            blob.reload()
            mime = blob.content_type or "application/octet-stream"
            filename = key.rsplit("/", 1)[-1]
            return {"b64": base64.b64encode(body_bytes).decode(), "mime": mime, "filename": filename}
        except Exception as e:
            logger.error(f"GCS get failed {storage_uri}: {e}")
            return None

    async def delete(self, storage_uri: str) -> bool:
        if not storage_uri.startswith("gcs://"):
            return False
        without_scheme = storage_uri.replace("gcs://", "", 1)
        bucket_name, key = without_scheme.split("/", 1)
        try:
            client = self._client()
            bucket = client.bucket(bucket_name)
            bucket.blob(key).delete()
            await db.pp_files.delete_one({"gcs_bucket": bucket_name, "gcs_key": key})
            return True
        except Exception as e:
            logger.error(f"GCS delete failed {storage_uri}: {e}")
            return False


# ============================================================
# FACTORY
# ============================================================

_BACKENDS = {
    "mongo": MongoStorageBackend,
    "s3": S3StorageBackend,
    "gcs": GCSStorageBackend,
}


async def get_backend() -> StorageBackend:
    """Return the configured storage backend instance."""
    name = await get_storage_backend_name()
    cls = _BACKENDS.get(name, MongoStorageBackend)
    return cls()


# ============================================================
# HIGH-LEVEL HELPERS (used by routes)
# ============================================================

async def save_upload(
    b64: str,
    filename: str,
    mime: str,
    category: str,
    owner_user_id: str,
) -> Dict[str, Any]:
    """One-stop: validate + save. Raises UploadValidationError on invalid input."""
    await validate_upload(b64, mime, filename, category)
    backend = await get_backend()
    result = await backend.save(b64, filename, mime, category, owner_user_id)
    result["backend"] = backend.name
    return result


async def load_upload(storage_uri: str) -> Optional[Dict[str, Any]]:
    """Fetch a file by its storage_uri. Auto-routes to correct backend by URI scheme."""
    if not storage_uri:
        return None
    if storage_uri.startswith("mongo://"):
        backend: StorageBackend = MongoStorageBackend()
    elif storage_uri.startswith("s3://"):
        backend = S3StorageBackend()
    elif storage_uri.startswith("gcs://"):
        backend = GCSStorageBackend()
    else:
        return None
    return await backend.get(storage_uri)


async def delete_upload(storage_uri: str) -> bool:
    if not storage_uri:
        return False
    if storage_uri.startswith("mongo://"):
        backend: StorageBackend = MongoStorageBackend()
    elif storage_uri.startswith("s3://"):
        backend = S3StorageBackend()
    elif storage_uri.startswith("gcs://"):
        backend = GCSStorageBackend()
    else:
        return False
    return await backend.delete(storage_uri)
