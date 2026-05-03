"""
Social Learning Engine — Upload Routes
Handles text, URL, file, and audio/video news uploads.
"""

import uuid
import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Request, Depends, UploadFile, File, Form
from core.database import db
from routes.auth_routes import get_current_user
from routes.audit_trail import log_audit_event

from .constants import (
    ALLOWED_FILE_TYPES, ALLOWED_AUDIO_TYPES, ALLOWED_VIDEO_TYPES, MAX_FILE_SIZE_MB,
)
from .models import NewsUploadRequest, UrlUploadRequest
from .helpers import get_client_ip, build_template_doc
from .ai_engine import classify_news, EMERGENT_LLM_KEY
from .file_extraction import extract_text_from_file
from .stt_engine import stt_engine

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/upload")
async def upload_news(data: NewsUploadRequest, request: Request, user: dict = Depends(get_current_user)):
    """Upload news content as text. AI classifies and generates Social Learning Template."""
    if not data.content or len(data.content.strip()) < 50:
        raise HTTPException(400, "News content must be at least 50 characters")

    if not EMERGENT_LLM_KEY:
        raise HTTPException(500, "AI engine not configured (EMERGENT_LLM_KEY missing)")

    try:
        classification = await classify_news(data.content)
    except Exception as e:
        logger.error(f"AI classification failed: {e}")
        raise HTTPException(500, f"AI classification failed: {str(e)}")

    template_id = f"SLT-{uuid.uuid4().hex[:10].upper()}"
    template = build_template_doc(
        template_id, classification, data.content, user,
        source_url=data.source_url, source_name=data.source_name,
        title=data.title, input_mode="text",
    )

    await db.social_learning_templates.insert_one(template)

    await log_audit_event(
        action="social_learning_created", entity_type="social_learning",
        entity_id=template_id, user_id=user["user_id"],
        details=f"News uploaded (text): {template['title'][:60]} [{template['category']}] lang={template['detected_language']}",
        ip_address=get_client_ip(request),
    )

    template.pop("original_content", None)
    template.pop("_id", None)
    return template


@router.post("/upload-url")
async def upload_news_url(data: UrlUploadRequest, request: Request, user: dict = Depends(get_current_user)):
    """Scrape a URL, extract text content, and classify it."""
    import httpx
    from bs4 import BeautifulSoup

    if not EMERGENT_LLM_KEY:
        raise HTTPException(500, "AI engine not configured (EMERGENT_LLM_KEY missing)")

    url = data.url.strip()
    if not url.startswith(("http://", "https://")):
        raise HTTPException(400, "URL must start with http:// or https://")

    # Fetch the page
    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
            }
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
    except httpx.HTTPStatusError as e:
        raise HTTPException(400, f"URL returned error: {e.response.status_code}")
    except httpx.ConnectError:
        raise HTTPException(400, "Could not connect to the URL. Please check the address.")
    except httpx.TimeoutException:
        raise HTTPException(400, "URL took too long to respond (>30s).")
    except Exception as e:
        raise HTTPException(400, f"Failed to fetch URL: {str(e)}")

    # Parse HTML and extract text
    soup = BeautifulSoup(resp.text, "html.parser")

    # Remove script, style, nav, footer, sidebar elements
    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "form", "noscript", "iframe"]):
        tag.decompose()

    # Try to get the main article content
    article_text = ""

    # Priority 1: <article> tag
    article = soup.find("article")
    if article:
        article_text = article.get_text(separator="\n", strip=True)

    # Priority 2: main content area
    if not article_text or len(article_text) < 100:
        main = soup.find("main") or soup.find("div", {"role": "main"})
        if main:
            article_text = main.get_text(separator="\n", strip=True)

    # Priority 3: largest text block
    if not article_text or len(article_text) < 100:
        paragraphs = soup.find_all("p")
        article_text = "\n".join(p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 30)

    # Priority 4: full body text
    if not article_text or len(article_text) < 100:
        body = soup.find("body")
        if body:
            article_text = body.get_text(separator="\n", strip=True)

    # Extract page title if not provided
    page_title = data.title
    if not page_title:
        title_tag = soup.find("title")
        if title_tag:
            page_title = title_tag.get_text(strip=True)

    # Extract source name from domain if not provided
    source_name = data.source_name
    if not source_name:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        source_name = parsed.netloc.replace("www.", "")

    # Clean up text
    lines = article_text.split("\n")
    cleaned_lines = [line.strip() for line in lines if len(line.strip()) > 10]
    extracted_text = "\n".join(cleaned_lines)

    if len(extracted_text) < 50:
        raise HTTPException(400, "Could not extract sufficient text from the URL. The page may require JavaScript or have restricted access.")

    # Truncate to reasonable length for AI
    if len(extracted_text) > 8000:
        extracted_text = extracted_text[:8000]

    # AI Classification
    try:
        classification = await classify_news(extracted_text)
    except Exception as e:
        logger.error(f"AI classification failed: {e}")
        raise HTTPException(500, f"AI classification failed: {str(e)}")

    template_id = f"SLT-{uuid.uuid4().hex[:10].upper()}"
    template = build_template_doc(
        template_id, classification, extracted_text, user,
        source_url=url, source_name=source_name,
        title=page_title, input_mode="url",
    )
    template["scraped_url"] = url
    template["scraped_title"] = page_title

    await db.social_learning_templates.insert_one(template)

    await log_audit_event(
        action="social_learning_created", entity_type="social_learning",
        entity_id=template_id, user_id=user["user_id"],
        details=f"News uploaded (URL): {template['title'][:60]} [{template['category']}] from {source_name}",
        ip_address=get_client_ip(request),
    )

    template.pop("original_content", None)
    template.pop("_id", None)
    return template


@router.post("/upload-file")
async def upload_news_file(
    request: Request,
    file: UploadFile = File(...),
    source_url: Optional[str] = Form(None),
    source_name: Optional[str] = Form(None),
    title: Optional[str] = Form(None),
    user: dict = Depends(get_current_user),
):
    """Upload a file (PDF, DOCX, TXT, Image) and extract text for classification."""
    if not EMERGENT_LLM_KEY:
        raise HTTPException(500, "AI engine not configured (EMERGENT_LLM_KEY missing)")

    # Validate file type
    content_type = file.content_type or ""
    file_type = ALLOWED_FILE_TYPES.get(content_type)

    if not file_type:
        # Try by extension
        ext = (file.filename or "").rsplit(".", 1)[-1].lower() if file.filename else ""
        ext_map = {"pdf": "pdf", "docx": "docx", "txt": "txt", "jpg": "image", "jpeg": "image", "png": "image", "webp": "image"}
        file_type = ext_map.get(ext)

    if not file_type:
        raise HTTPException(400, f"Unsupported file type: {content_type}. Allowed: PDF, DOCX, TXT, JPG, PNG, WEBP")

    # Read file
    file_bytes = await file.read()
    if len(file_bytes) > MAX_FILE_SIZE_MB * 1024 * 1024:
        raise HTTPException(400, f"File too large. Maximum size: {MAX_FILE_SIZE_MB}MB")

    # Extract text
    try:
        extracted_text = extract_text_from_file(file_bytes, file_type)
    except Exception as e:
        logger.error(f"Text extraction failed: {e}")
        raise HTTPException(400, f"Failed to extract text from file: {str(e)}")

    if not extracted_text or len(extracted_text.strip()) < 30:
        raise HTTPException(400, "Could not extract sufficient text from the file. Please try a different file or use text input.")

    # AI Classification
    try:
        classification = await classify_news(extracted_text)
    except Exception as e:
        logger.error(f"AI classification failed: {e}")
        raise HTTPException(500, f"AI classification failed: {str(e)}")

    template_id = f"SLT-{uuid.uuid4().hex[:10].upper()}"
    template = build_template_doc(
        template_id, classification, extracted_text, user,
        source_url=source_url, source_name=source_name or file.filename,
        title=title, input_mode=f"file_{file_type}",
    )
    template["original_filename"] = file.filename

    await db.social_learning_templates.insert_one(template)

    await log_audit_event(
        action="social_learning_created", entity_type="social_learning",
        entity_id=template_id, user_id=user["user_id"],
        details=f"News uploaded (file:{file_type}): {template['title'][:60]} [{template['category']}]",
        ip_address=get_client_ip(request),
    )

    template.pop("original_content", None)
    template.pop("_id", None)
    return template


@router.post("/upload-audio")
async def upload_news_audio(
    request: Request,
    audio: UploadFile = File(...),
    source_name: Optional[str] = Form(None),
    title: Optional[str] = Form(None),
    user: dict = Depends(get_current_user),
):
    """Upload audio or video file (English only). Extracts audio from video, transcribes, then classifies."""
    if not EMERGENT_LLM_KEY:
        raise HTTPException(500, "AI engine not configured (EMERGENT_LLM_KEY missing)")

    # Determine if audio or video
    content_type = audio.content_type or ""
    audio_format = ALLOWED_AUDIO_TYPES.get(content_type)
    video_format = ALLOWED_VIDEO_TYPES.get(content_type)
    is_video = False

    if not audio_format and not video_format:
        ext = (audio.filename or "").rsplit(".", 1)[-1].lower() if audio.filename else ""
        audio_ext_map = {"wav": "wav", "mp3": "mp3", "ogg": "ogg", "webm": "webm", "m4a": "m4a"}
        video_ext_map = {"mp4": "mp4", "mov": "mov", "avi": "avi", "mkv": "mkv", "mpeg": "mpeg", "3gp": "3gp"}
        audio_format = audio_ext_map.get(ext)
        if not audio_format:
            video_format = video_ext_map.get(ext)

    if not audio_format and not video_format:
        raise HTTPException(
            400,
            f"Unsupported media type: {content_type}. "
            "Allowed audio: WAV, MP3, OGG, WEBM, M4A. "
            "Allowed video: MP4, MOV, AVI, MKV, WEBM, 3GP"
        )

    is_video = video_format is not None

    # Read file
    file_bytes = await audio.read()
    max_size = 50 if is_video else MAX_FILE_SIZE_MB  # 50MB for video, 10MB for audio
    if len(file_bytes) > max_size * 1024 * 1024:
        raise HTTPException(400, f"File too large. Maximum size: {max_size}MB")

    # If video, extract audio track first
    if is_video:
        try:
            audio_bytes = stt_engine.extract_audio_from_video(file_bytes, video_format)
            audio_format = "wav"  # ffmpeg outputs WAV
        except ValueError as e:
            raise HTTPException(400, f"Video audio extraction failed: {str(e)}")
        except Exception as e:
            logger.error(f"Video audio extraction failed: {e}")
            raise HTTPException(500, f"Could not extract audio from video: {str(e)}")
    else:
        audio_bytes = file_bytes

    # Transcribe (English only)
    try:
        transcribed_text = stt_engine.transcribe(audio_bytes, audio_format=audio_format, language="en-US")
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.error(f"Audio transcription failed: {e}")
        raise HTTPException(500, f"Audio transcription failed: {str(e)}")

    if not transcribed_text or len(transcribed_text.strip()) < 20:
        raise HTTPException(400, "Could not transcribe sufficient text from audio. Please speak clearly and try again.")

    # AI Classification
    try:
        classification = await classify_news(transcribed_text)
    except Exception as e:
        logger.error(f"AI classification failed: {e}")
        raise HTTPException(500, f"AI classification failed: {str(e)}")

    input_mode = "video" if is_video else "audio"
    template_id = f"SLT-{uuid.uuid4().hex[:10].upper()}"
    template = build_template_doc(
        template_id, classification, transcribed_text, user,
        source_name=source_name or audio.filename,
        title=title, input_mode=input_mode,
    )
    template["transcribed_text"] = transcribed_text

    await db.social_learning_templates.insert_one(template)

    await log_audit_event(
        action="social_learning_created", entity_type="social_learning",
        entity_id=template_id, user_id=user["user_id"],
        details=f"News uploaded ({input_mode}): {template['title'][:60]} [{template['category']}]",
        ip_address=get_client_ip(request),
    )

    template.pop("original_content", None)
    template.pop("_id", None)
    return template
