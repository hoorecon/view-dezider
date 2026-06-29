"""Disk-backed chunked-upload store.

Large files (PDFs, Excel sheets, images) sent as a single base64 JSON body can be
rejected by a reverse proxy with HTTP 413 (Request Entity Too Large) before they
ever reach FastAPI. To bypass any proxy body-size limit, clients upload the file
as many small base64 chunks; we persist them on disk and reassemble on demand.

Single-pod safe: chunks live on the shared filesystem, so concatenation works the
same regardless of the number of uvicorn workers or hot-reloads.
"""
import base64
import json
import os
import shutil
import tempfile
import time
import uuid

_ROOT = os.path.join(tempfile.gettempdir(), "jelcos_uploads")
_TTL_SECONDS = 60 * 60                  # discard abandoned sessions after 1 hour
_MAX_TOTAL_BYTES = 105 * 1024 * 1024    # hard cap on the assembled raw file (~100 MB)


def _dir(upload_id: str) -> str:
    return os.path.join(_ROOT, upload_id)


def _sweep() -> None:
    """Best-effort cleanup of stale upload sessions."""
    try:
        if not os.path.isdir(_ROOT):
            return
        now = time.time()
        for name in os.listdir(_ROOT):
            p = os.path.join(_ROOT, name)
            try:
                if now - os.path.getmtime(p) > _TTL_SECONDS:
                    shutil.rmtree(p, ignore_errors=True)
            except OSError:
                pass
    except OSError:
        pass


def init_upload(filename: str) -> str:
    """Create a new upload session and return its id."""
    _sweep()
    upload_id = uuid.uuid4().hex
    d = _dir(upload_id)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "meta.json"), "w") as f:
        json.dump({"filename": filename or "upload", "created": time.time()}, f)
    return upload_id


def save_chunk(upload_id: str, index: int, chunk_b64: str) -> int:
    """Persist one base64 chunk. Raises KeyError if the session is unknown."""
    d = _dir(upload_id)
    if not os.path.isdir(d):
        raise KeyError("upload session not found")
    with open(os.path.join(d, f"{int(index):06d}.part"), "w") as f:
        f.write(chunk_b64 or "")
    return len(chunk_b64 or "")


def assemble(upload_id: str):
    """Return (filename, raw_bytes) for a completed session.

    Raises KeyError if the session is missing, ValueError on bad/oversized data.
    """
    d = _dir(upload_id)
    if not os.path.isdir(d):
        raise KeyError("upload session not found")
    filename = "upload"
    meta_path = os.path.join(d, "meta.json")
    if os.path.exists(meta_path):
        try:
            with open(meta_path) as f:
                filename = json.load(f).get("filename", "upload")
        except (OSError, ValueError):
            pass
    parts = sorted(p for p in os.listdir(d) if p.endswith(".part"))
    if not parts:
        raise ValueError("no chunks received")
    pieces = []
    for p in parts:
        with open(os.path.join(d, p)) as f:
            pieces.append(f.read())
    b64 = "".join(pieces).split(",")[-1]  # strip any data: prefix defensively
    raw = base64.b64decode(b64)
    if len(raw) > _MAX_TOTAL_BYTES:
        raise ValueError("assembled file too large")
    return filename, raw


def discard(upload_id: str) -> None:
    """Delete an upload session's chunks (best effort)."""
    shutil.rmtree(_dir(upload_id), ignore_errors=True)
