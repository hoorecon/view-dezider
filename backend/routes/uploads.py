"""Chunked upload API.

Lets clients send large files (PDF/Excel/images) as many small base64 chunks so
they bypass any reverse-proxy body-size limit (which otherwise rejects a single
big JSON POST with HTTP 413). Consumers reassemble via core.chunk_upload.assemble.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from core.auth import get_current_user
from core import chunk_upload

router = APIRouter(prefix="/uploads", tags=["Uploads"])


class InitIn(BaseModel):
    filename: str = "upload"


@router.post("/init")
async def init_upload(body: InitIn, user: dict = Depends(get_current_user)):
    return {"upload_id": chunk_upload.init_upload(body.filename)}


class ChunkIn(BaseModel):
    upload_id: str
    index: int
    total: Optional[int] = None
    chunk_b64: str


@router.post("/chunk")
async def upload_chunk(body: ChunkIn, user: dict = Depends(get_current_user)):
    try:
        received = chunk_upload.save_chunk(body.upload_id, body.index, body.chunk_b64)
    except KeyError:
        raise HTTPException(404, "Upload session not found or expired — restart the upload.")
    return {"ok": True, "received_bytes": received}
