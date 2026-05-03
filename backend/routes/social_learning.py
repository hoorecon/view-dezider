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
"""

import os
import io
import uuid
import json
import logging
import tempfile
from datetime import datetime, timezone
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Request, Depends, UploadFile, File, Form
from pydantic import BaseModel
from core.database import db
from routes.auth_routes import get_current_user
from routes.audit_trail import log_audit_event

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/social-learning", tags=["Social Learning"])

EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY", "")

# ========================
# CONSTANTS
# ========================

LIFE_AREAS = [
    "career_profession", "finance_wealth", "health_wellness",
    "relationships_family", "education_learning", "personal_growth",
    "social_community", "legal_governance", "technology_innovation",
    "environment_sustainability",
]

ORG_TYPES = ["family", "individual", "association", "company", "startup", "ngo", "govt", "cooperative", "trust"]

CATEGORIES = ["problem", "need", "aspiration"]

# Restricted to 6 languages as per user requirement
SUPPORTED_LANGUAGES = [
    "english", "hindi", "tamil", "telugu", "kannada", "malayalam",
]

TEMPLATE_STATUSES = ["draft", "submitted", "authorized", "rejected"]

# File upload constraints
MAX_FILE_SIZE_MB = 10
ALLOWED_FILE_TYPES = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "text/plain": "txt",
    "image/jpeg": "image",
    "image/jpg": "image",
    "image/png": "image",
    "image/webp": "image",
}
ALLOWED_AUDIO_TYPES = {
    "audio/wav": "wav",
    "audio/mpeg": "mp3",
    "audio/mp3": "mp3",
    "audio/x-wav": "wav",
    "audio/ogg": "ogg",
    "audio/webm": "webm",
    "audio/mp4": "mp4",
    "audio/x-m4a": "m4a",
}
ALLOWED_VIDEO_TYPES = {
    "video/mp4": "mp4",
    "video/mpeg": "mpeg",
    "video/quicktime": "mov",
    "video/x-msvideo": "avi",
    "video/webm": "webm",
    "video/x-matroska": "mkv",
    "video/3gpp": "3gp",
}


# ========================
# MODELS
# ========================

class NewsUploadRequest(BaseModel):
    content: str  # News text in any supported language
    source_url: Optional[str] = None
    source_name: Optional[str] = None
    title: Optional[str] = None


class AdminApprovalRequest(BaseModel):
    status: str  # "authorized" or "rejected"
    admin_notes: Optional[str] = ""


class SynthesizeRequest(BaseModel):
    template_ids: List[str]  # List of Authorized Social Learning Template IDs to synthesize
    target_region: Optional[str] = None
    target_org_type: Optional[str] = None
    target_life_area: Optional[str] = None


# ========================
# UTILITIES
# ========================

def get_client_ip(request: Request) -> str:
    """Extract client IP from request."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return ""


# ========================
# FILE TEXT EXTRACTION
# ========================

def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract text from PDF file."""
    from PyPDF2 import PdfReader
    reader = PdfReader(io.BytesIO(file_bytes))
    text_parts = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            text_parts.append(text)
    return "\n".join(text_parts)


def extract_text_from_docx(file_bytes: bytes) -> str:
    """Extract text from DOCX file."""
    from docx import Document
    doc = Document(io.BytesIO(file_bytes))
    text_parts = []
    for para in doc.paragraphs:
        if para.text.strip():
            text_parts.append(para.text)
    return "\n".join(text_parts)


def extract_text_from_image(file_bytes: bytes) -> str:
    """Extract text from image using OCR (Tesseract)."""
    from PIL import Image
    import pytesseract
    image = Image.open(io.BytesIO(file_bytes))
    text = pytesseract.image_to_string(image, lang='eng+hin+tam+tel+kan+mal')
    return text.strip()


def extract_text_from_file(file_bytes: bytes, file_type: str) -> str:
    """Route to appropriate text extraction based on file type."""
    if file_type == "pdf":
        return extract_text_from_pdf(file_bytes)
    elif file_type == "docx":
        return extract_text_from_docx(file_bytes)
    elif file_type == "txt":
        return file_bytes.decode("utf-8", errors="replace")
    elif file_type == "image":
        return extract_text_from_image(file_bytes)
    else:
        raise ValueError(f"Unsupported file type: {file_type}")


# ========================
# AUDIO TRANSCRIPTION (Modular STT Engine)
# ========================

class STTEngine:
    """
    Modular Speech-to-Text engine.
    Currently uses Google's free STT via SpeechRecognition library.
    To switch providers, replace the `transcribe` method.
    """

    @staticmethod
    def transcribe(audio_bytes: bytes, audio_format: str = "wav", language: str = "en-US") -> str:
        """
        Transcribe audio bytes to text.
        Currently supports: wav, mp3, ogg, webm, m4a, mp4
        Language: Only English for now (en-US)
        """
        import speech_recognition as sr

        recognizer = sr.Recognizer()

        # Convert audio to WAV format if needed
        wav_bytes = STTEngine._convert_to_wav(audio_bytes, audio_format)

        # Use SpeechRecognition with the WAV data
        audio_file = io.BytesIO(wav_bytes)
        with sr.AudioFile(audio_file) as source:
            audio_data = recognizer.record(source)

        try:
            # Google's free STT (no API key needed)
            text = recognizer.recognize_google(audio_data, language=language)
            return text
        except sr.UnknownValueError:
            raise ValueError("Could not understand the audio. Please speak clearly and try again.")
        except sr.RequestError as e:
            raise ValueError(f"Speech recognition service unavailable: {str(e)}")

    @staticmethod
    def extract_audio_from_video(video_bytes: bytes, video_format: str) -> bytes:
        """
        Extract audio track from a video file using ffmpeg.
        Returns WAV audio bytes.
        """
        import subprocess

        with tempfile.NamedTemporaryFile(suffix=f".{video_format}", delete=False) as tmp_video:
            tmp_video.write(video_bytes)
            tmp_video.flush()
            video_path = tmp_video.name

        wav_path = video_path + ".wav"
        try:
            result = subprocess.run(
                [
                    "ffmpeg", "-i", video_path,
                    "-vn",                  # No video
                    "-acodec", "pcm_s16le", # WAV codec
                    "-ar", "16000",         # 16kHz sample rate
                    "-ac", "1",             # Mono
                    "-y",                   # Overwrite
                    wav_path,
                ],
                capture_output=True, text=True, timeout=120,
            )
            if result.returncode != 0:
                raise ValueError(f"ffmpeg failed: {result.stderr[:300]}")

            with open(wav_path, "rb") as f:
                return f.read()
        finally:
            for p in [video_path, wav_path]:
                try:
                    os.unlink(p)
                except OSError:
                    pass

    @staticmethod
    def _convert_to_wav(audio_bytes: bytes, audio_format: str) -> bytes:
        """Convert audio to WAV format using pydub."""
        if audio_format == "wav":
            return audio_bytes

        from pydub import AudioSegment

        # Map format strings to pydub format names
        format_map = {
            "mp3": "mp3",
            "ogg": "ogg",
            "webm": "webm",
            "m4a": "mp4",
            "mp4": "mp4",
        }

        pydub_format = format_map.get(audio_format, audio_format)

        with tempfile.NamedTemporaryFile(suffix=f".{audio_format}", delete=True) as tmp_in:
            tmp_in.write(audio_bytes)
            tmp_in.flush()

            try:
                audio_segment = AudioSegment.from_file(tmp_in.name, format=pydub_format)
            except Exception as e:
                raise ValueError(f"Failed to process audio file ({audio_format}): {str(e)}")

            wav_buffer = io.BytesIO()
            audio_segment.export(wav_buffer, format="wav")
            return wav_buffer.getvalue()


# Singleton STT engine instance
stt_engine = STTEngine()


# ========================
# AI ENGINE
# ========================

async def get_hos_hierarchy_for_prompt() -> str:
    """Fetch the HOS Life Area → Sub Area hierarchy from DB for AI prompt context."""
    life_areas = await db.hos_life_areas.find({}, {"_id": 0}).sort("order", 1).to_list(20)
    sub_areas = await db.hos_sub_areas.find({}, {"_id": 0}).sort("order", 1).to_list(100)

    # Build a lookup
    sa_by_la: dict = {}
    for sa in sub_areas:
        la_id = sa["life_area_id"]
        if la_id not in sa_by_la:
            sa_by_la[la_id] = []
        sa_by_la[la_id].append(sa)

    lines = []
    for la in life_areas:
        subs = sa_by_la.get(la["id"], [])
        sub_names = ", ".join(s["name"] for s in subs)
        lines.append(f"- {la['name']} (id: {la['id']}): [{sub_names}]")

    return "\n".join(lines)


async def classify_news(content: str) -> dict:
    """Use GPT to classify news with full HOS hierarchy, enhanced factors, risks."""
    from emergentintegrations.llm.chat import LlmChat, UserMessage

    supported_langs = ", ".join(SUPPORTED_LANGUAGES)

    # Get the actual HOS hierarchy from DB
    hierarchy = await get_hos_hierarchy_for_prompt()

    prompt = f"""You are an expert analyst for View Dezider — a decision intelligence platform.
Analyze the news content below. Detect language, translate to English, and extract structured intelligence.
Supported languages: {supported_langs}

LIFE AREA HIERARCHY (from our database):
{hierarchy}

ORG TYPES: {', '.join(ORG_TYPES)}

NEWS CONTENT:
\"\"\"
{content[:5000]}
\"\"\"

Respond ONLY with valid JSON (no markdown, no explanation):
{{
  "detected_language": "<one of: {supported_langs}>",
  "english_summary": "<2-3 sentence summary in English>",
  "original_title": "<title extracted or generated from the content>",
  "category": "<exactly one of: problem, need, aspiration>",
  "category_reasoning": "<1 sentence why this category>",

  "region_hierarchy": {{
    "level": "<global/continent/country/state/city/area>",
    "global_region": "<e.g. Asia, Europe, Global>",
    "continent": "<e.g. Asia>",
    "country": "<e.g. India>",
    "state": "<state name if applicable, else null>",
    "city": "<city name if applicable, else null>",
    "area": "<specific locality if applicable, else null>"
  }},

  "org_types": ["<list of applicable org types from: {', '.join(ORG_TYPES)}>"],

  "life_area_mapping": {{
    "primary_life_area_id": "<life area ID from hierarchy above, e.g. la_finance>",
    "primary_life_area_name": "<full name>",
    "sub_area_1": "<most specific sub-area name from hierarchy>",
    "sub_area_2": "<second-level specificity if applicable, else null>"
  }},
  "secondary_life_areas": ["<additional applicable life area IDs>"],

  "scenario_mapping": {{
    "matches_predefined": <true if this maps to a common/known scenario>,
    "predefined_scenario_title": "<title of matching known scenario, or null>",
    "suggested_new_scenario": {{
      "title": "<suggested new scenario title for this sub-area>",
      "description": "<what this scenario represents>",
      "who_is_affected": "<who typically faces this>",
      "typical_trigger": "<what triggers this situation>"
    }}
  }},

  "learnings_for_mydezider": {{
    "factors": [
      {{
        "name": "<factor name>",
        "description": "<what this factor means in this context>",
        "practical_priority": "<P1 to P10, P1=highest situational priority>",
        "practical_priority_num": <1-10 integer>,
        "classification": "<mandatory or optional>",
        "expected_value": "<expected value or benchmark>",
        "expected_value_pct": <0-100 integer>,
        "factor_type": "<quantitative or qualitative>",
        "unit": "<unit of measurement if quantitative, else null>",
        "reasoning": "<why this factor matters in this scenario>"
      }}
    ],
    "summary": "<brief summary of what a decision-maker should evaluate>"
  }},

  "learnings_for_solution_finder": {{
    "risks": [
      {{
        "risk_name": "<risk name>",
        "description": "<what this risk means>",
        "probability": <1-10 integer, likelihood of occurrence>,
        "impact": <1-10 integer, severity of impact>,
        "risk_index": <probability x impact, 1-100>,
        "mitigation_plan": "<actionable mitigation strategy>",
        "contingency_plan": "<backup plan if risk materializes>",
        "personalization_note": "<how to adapt this to current times>"
      }}
    ],
    "summary": "<brief summary of risk landscape for this scenario>"
  }},

  "root_causes": ["<list of root causes identified>"],
  "lessons_learned": ["<key takeaways from this event>"],
  "what_could_prevent": "<how this situation could have been prevented>",

  "tags": ["<relevant tags>"],
  "severity_score": <1-10, how severe/impactful is this>
}}"""

    chat = LlmChat(
        api_key=EMERGENT_LLM_KEY,
        session_id=f"social_learning_{uuid.uuid4().hex[:8]}",
        system_message="You are a social learning classifier. Analyze news content and extract structured information. Return only valid JSON."
    ).with_model("openai", "gpt-4.1-mini")
    response = await chat.send_message(UserMessage(text=prompt))

    # Parse JSON from response
    text = response.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(text[start:end])
        raise ValueError(f"Failed to parse AI response as JSON: {text[:200]}")


async def synthesize_templates(templates: list, target_context: dict) -> dict:
    """AI synthesis of multiple Authorized templates into a Social Solution Template."""
    from emergentintegrations.llm.chat import LlmChat, UserMessage

    templates_text = ""
    for i, t in enumerate(templates, 1):
        templates_text += f"\n--- Template {i} ---\n"
        templates_text += f"Title: {t.get('title', 'N/A')}\n"
        templates_text += f"Category: {t.get('category', 'N/A')}\n"
        templates_text += f"Summary: {t.get('english_summary', 'N/A')}\n"
        templates_text += f"Life Areas: {', '.join(t.get('life_areas', []))}\n"
        templates_text += f"Scenario: {json.dumps(t.get('life_scenario_template', {}))}\n"
        templates_text += f"Factors: {json.dumps(t.get('factors', [])[:5])}\n"
        templates_text += f"Concerns: {json.dumps(t.get('concerns', [])[:5])}\n"
        templates_text += f"Lessons: {json.dumps(t.get('lessons_learned', []))}\n"
        templates_text += f"Root Causes: {json.dumps(t.get('root_causes', []))}\n"

    context_str = ""
    if target_context.get("target_region"):
        context_str += f"Target Region: {target_context['target_region']}\n"
    if target_context.get("target_org_type"):
        context_str += f"Target Org Type: {target_context['target_org_type']}\n"
    if target_context.get("target_life_area"):
        context_str += f"Target Life Area: {target_context['target_life_area']}\n"

    prompt = f"""You are the View Dezider Social Intelligence Synthesizer. 
You have {len(templates)} verified 'Authorized Social Learning Templates' from real-world incidents.
Your job: Synthesize these into ONE comprehensive 'Social Solution Template' — the distilled wisdom.

AUTHORIZED TEMPLATES:
{templates_text}

TARGET CONTEXT:
{context_str if context_str else "General / Pan-India"}

Respond ONLY with valid JSON:
{{
  "title": "<synthesized template title>",
  "description": "<comprehensive description of the pattern/situation>",
  "category": "<problem/need/aspiration>",
  "life_areas": ["<applicable life areas>"],
  "primary_life_area": "<single most relevant>",
  "life_area_sub_area": "<sub-area>",
  "org_types": ["<applicable org types>"],
  "geo_relevance": "<region relevance>",
  "pattern_identified": "<the common pattern across all templates>",
  "synthesized_factors": [
    {{
      "name": "<factor>",
      "priority": <1-10>,
      "expected_value_pct": <0-100>,
      "confidence": "<high/medium/low>",
      "supporting_template_count": <number>
    }}
  ],
  "synthesized_concerns": [
    {{
      "concern": "<synthesized concern>",
      "severity": "<high/medium/low>",
      "frequency": "<how often this appeared across templates>",
      "mitigation_consensus": "<best mitigation from all templates>"
    }}
  ],
  "combined_lessons": ["<distilled lessons>"],
  "combined_root_causes": ["<common root causes>"],
  "premium_life_scenario": {{
    "scenario_title": "<generalized scenario title>",
    "scenario_description": "<what this pattern means for decision-makers>",
    "decision_entry_point": {{
      "problem_statement": "<generalized problem statement>",
      "key_factors": ["<prioritized factors>"],
      "options_to_evaluate": ["<recommended options>"],
      "risk_checkpoints": ["<critical risk checks>"]
    }},
    "solution_finder_entry_point": {{
      "smart_goal": "<preventive goal>",
      "main_concerns": ["<top concerns>"],
      "risk_management_questions": ["<proactive Q4 questions>"],
      "recommended_actions": ["<preventive actions>"]
    }}
  }},
  "accuracy_notes": "<how confident is this synthesis>",
  "source_template_count": {len(templates)},
  "tags": ["<tags>"]
}}"""

    chat = LlmChat(
        api_key=EMERGENT_LLM_KEY,
        session_id=f"synthesize_{uuid.uuid4().hex[:8]}",
        system_message="You are a social solution synthesizer. Combine multiple templates into a comprehensive solution. Return only valid JSON."
    ).with_model("openai", "gpt-4.1-mini")
    response = await chat.send_message(UserMessage(text=prompt))

    text = response.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(text[start:end])
        raise ValueError("Failed to parse synthesis response")


# ========================
# HELPERS
# ========================

async def require_admin(user: dict):
    u = await db.users.find_one({"user_id": user["user_id"]})
    if not u or u.get("role") not in ["admin", "org_admin", "super_admin"]:
        raise HTTPException(403, "Admin access required")
    return u


def build_template_doc(template_id: str, classification: dict, content: str,
                       user: dict, source_url: str = None, source_name: str = None,
                       title: str = None, input_mode: str = "text") -> dict:
    """Build a template document from enhanced AI classification."""
    now = datetime.now(timezone.utc).isoformat()

    # Extract the new structured data
    la_mapping = classification.get("life_area_mapping", {})
    region = classification.get("region_hierarchy", {})
    scenario = classification.get("scenario_mapping", {})
    mydezider = classification.get("learnings_for_mydezider", {})
    solution_finder = classification.get("learnings_for_solution_finder", {})

    # Backward-compatible life_areas list
    life_areas = [la_mapping.get("primary_life_area_id", "")]
    life_areas += classification.get("secondary_life_areas", [])
    life_areas = [la for la in life_areas if la]

    # Factors: enrich with approval status
    factors = mydezider.get("factors", [])
    for f in factors:
        f["approved"] = False  # User must review and approve
        f["modified_by_user"] = False

    # Risks: enrich with approval status
    risks = solution_finder.get("risks", [])
    for r in risks:
        r["approved"] = False
        r["modified_by_user"] = False
        # Ensure risk_index is computed
        if "risk_index" not in r:
            r["risk_index"] = (r.get("probability", 5)) * (r.get("impact", 5))

    return {
        "id": template_id,
        "tier": 1,
        "status": "draft",
        "created_by": user["user_id"],
        "created_at": now,
        "updated_at": now,
        "input_mode": input_mode,

        # Source
        "original_content": content[:5000],
        "source_url": source_url,
        "source_name": source_name,
        "user_title": title,

        # AI Classification
        "detected_language": classification.get("detected_language", "english"),
        "english_summary": classification.get("english_summary", ""),
        "title": classification.get("original_title", title or "Untitled"),
        "category": classification.get("category", "problem"),
        "category_reasoning": classification.get("category_reasoning", ""),

        # Region Hierarchy
        "region_hierarchy": region,
        "geo_level": region.get("level", "global"),

        # Life Area Mapping (enhanced)
        "life_area_mapping": la_mapping,
        "life_areas": life_areas,
        "primary_life_area": la_mapping.get("primary_life_area_id", ""),
        "life_area_sub_area": la_mapping.get("sub_area_1", ""),
        "life_area_sub_area_2": la_mapping.get("sub_area_2"),
        "secondary_life_areas": classification.get("secondary_life_areas", []),

        # Org Types
        "org_types": classification.get("org_types", []),

        # Scenario Mapping
        "scenario_mapping": scenario,

        "severity_score": classification.get("severity_score", 5),

        # Learnings for My Dezider (Factors)
        "learnings_mydezider": {
            "factors": factors,
            "summary": mydezider.get("summary", ""),
        },
        # Backward compat
        "factors": factors,

        # Learnings for Solution Finder (Risks)
        "learnings_solution_finder": {
            "risks": risks,
            "summary": solution_finder.get("summary", ""),
        },
        # Backward compat
        "concerns": [{"concern": r.get("risk_name", ""), "severity": "high" if r.get("risk_index", 0) >= 50 else "medium" if r.get("risk_index", 0) >= 25 else "low", "mitigation": r.get("mitigation_plan", "")} for r in risks],

        "root_causes": classification.get("root_causes", []),
        "lessons_learned": classification.get("lessons_learned", []),
        "what_could_prevent": classification.get("what_could_prevent", ""),

        "tags": classification.get("tags", []),

        # Admin fields
        "admin_notes": "",
        "authorized_at": None,
        "authorized_by": None,
    }


# ========================
# TIER 1: Social Learning Templates (User Upload)
# ========================

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


class UrlUploadRequest(BaseModel):
    url: str
    title: Optional[str] = None
    source_name: Optional[str] = None


@router.post("/upload-url")
async def upload_news_url(data: UrlUploadRequest, request: Request, user: dict = Depends(get_current_user)):
    """Scrape a URL, extract text content, and classify it. English only for now."""
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


# ========================
# TEMPLATE CRUD
# ========================

@router.get("/my-templates")
async def get_my_templates(
    status: Optional[str] = None,
    category: Optional[str] = None,
    life_area: Optional[str] = None,
    limit: int = 30,
    skip: int = 0,
    user: dict = Depends(get_current_user),
):
    """Get current user's Social Learning Templates."""
    query: dict = {"created_by": user["user_id"]}
    if status:
        query["status"] = status
    if category:
        query["category"] = category
    if life_area:
        query["life_areas"] = life_area

    total = await db.social_learning_templates.count_documents(query)
    templates = await db.social_learning_templates.find(
        query, {"_id": 0, "original_content": 0}
    ).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)

    return {"total": total, "templates": templates}


@router.get("/template/{template_id}")
async def get_template(template_id: str, user: dict = Depends(get_current_user)):
    """Get a specific Social Learning Template with full details."""
    template = await db.social_learning_templates.find_one({"id": template_id}, {"_id": 0})
    if not template:
        raise HTTPException(404, "Template not found")

    if template["status"] == "draft" and template["created_by"] != user["user_id"]:
        u = await db.users.find_one({"user_id": user["user_id"]})
        if not u or u.get("role") not in ["admin", "org_admin", "super_admin"]:
            raise HTTPException(403, "Access denied")

    return template


@router.post("/template/{template_id}/submit")
async def submit_template(template_id: str, user: dict = Depends(get_current_user)):
    """Submit a draft template for admin review."""
    template = await db.social_learning_templates.find_one({"id": template_id})
    if not template:
        raise HTTPException(404, "Template not found")
    if template["created_by"] != user["user_id"]:
        raise HTTPException(403, "Only the creator can submit")
    if template["status"] != "draft":
        raise HTTPException(400, f"Template is already '{template['status']}', cannot submit")

    now = datetime.now(timezone.utc).isoformat()
    await db.social_learning_templates.update_one(
        {"id": template_id},
        {"$set": {"status": "submitted", "updated_at": now}}
    )

    return {"id": template_id, "status": "submitted", "message": "Template submitted for admin review"}


@router.delete("/template/{template_id}")
async def delete_template(template_id: str, user: dict = Depends(get_current_user)):
    """Delete a user's own draft template."""
    template = await db.social_learning_templates.find_one({"id": template_id})
    if not template:
        raise HTTPException(404, "Template not found")
    if template["created_by"] != user["user_id"]:
        u = await db.users.find_one({"user_id": user["user_id"]})
        if not u or u.get("role") not in ["admin", "org_admin", "super_admin"]:
            raise HTTPException(403, "Only the creator or admin can delete")
    if template["status"] == "authorized":
        raise HTTPException(400, "Cannot delete authorized templates")

    await db.social_learning_templates.delete_one({"id": template_id})
    return {"message": "Template deleted", "id": template_id}


# ========================
# FACTOR/RISK REVIEW & APPROVAL
# ========================

class FactorApprovalRequest(BaseModel):
    approved_factor_indices: List[int] = []  # indices of factors user approves
    modified_factors: Optional[List[dict]] = None  # user-modified factors


class RiskApprovalRequest(BaseModel):
    approved_risk_indices: List[int] = []
    modified_risks: Optional[List[dict]] = None


@router.post("/template/{template_id}/approve-factors")
async def approve_factors(template_id: str, data: FactorApprovalRequest, user: dict = Depends(get_current_user)):
    """User reviews and approves specific factors (with or without modifications)."""
    template = await db.social_learning_templates.find_one({"id": template_id})
    if not template:
        raise HTTPException(404, "Template not found")
    if template["created_by"] != user["user_id"]:
        raise HTTPException(403, "Only the creator can approve factors")

    factors = template.get("factors", [])
    learnings = template.get("learnings_mydezider", {})
    lm_factors = learnings.get("factors", factors)

    # Mark approved indices
    for i, f in enumerate(lm_factors):
        f["approved"] = i in data.approved_factor_indices

    # Apply user modifications
    if data.modified_factors:
        for mf in data.modified_factors:
            idx = mf.get("index")
            if idx is not None and 0 <= idx < len(lm_factors):
                for key in ["name", "expected_value", "expected_value_pct", "classification", "practical_priority", "practical_priority_num"]:
                    if key in mf:
                        lm_factors[idx][key] = mf[key]
                lm_factors[idx]["modified_by_user"] = True
                lm_factors[idx]["approved"] = True

    now = datetime.now(timezone.utc).isoformat()
    await db.social_learning_templates.update_one(
        {"id": template_id},
        {"$set": {
            "learnings_mydezider.factors": lm_factors,
            "factors": lm_factors,
            "updated_at": now,
        }}
    )
    return {"id": template_id, "approved_count": sum(1 for f in lm_factors if f.get("approved")), "total": len(lm_factors)}


@router.post("/template/{template_id}/approve-risks")
async def approve_risks(template_id: str, data: RiskApprovalRequest, user: dict = Depends(get_current_user)):
    """User reviews and approves specific risks (with or without modifications)."""
    template = await db.social_learning_templates.find_one({"id": template_id})
    if not template:
        raise HTTPException(404, "Template not found")
    if template["created_by"] != user["user_id"]:
        raise HTTPException(403, "Only the creator can approve risks")

    learnings = template.get("learnings_solution_finder", {})
    risks = learnings.get("risks", [])

    for i, r in enumerate(risks):
        r["approved"] = i in data.approved_risk_indices

    if data.modified_risks:
        for mr in data.modified_risks:
            idx = mr.get("index")
            if idx is not None and 0 <= idx < len(risks):
                for key in ["risk_name", "probability", "impact", "mitigation_plan", "contingency_plan"]:
                    if key in mr:
                        risks[idx][key] = mr[key]
                if "probability" in mr or "impact" in mr:
                    risks[idx]["risk_index"] = risks[idx].get("probability", 5) * risks[idx].get("impact", 5)
                risks[idx]["modified_by_user"] = True
                risks[idx]["approved"] = True

    now = datetime.now(timezone.utc).isoformat()
    await db.social_learning_templates.update_one(
        {"id": template_id},
        {"$set": {
            "learnings_solution_finder.risks": risks,
            "updated_at": now,
        }}
    )
    return {"id": template_id, "approved_count": sum(1 for r in risks if r.get("approved")), "total": len(risks)}


class ReAnalyzeRequest(BaseModel):
    additional_context: str
    focus_area: Optional[str] = None  # "factors", "risks", "both"


@router.post("/template/{template_id}/re-analyze")
async def re_analyze_template(template_id: str, data: ReAnalyzeRequest, request: Request, user: dict = Depends(get_current_user)):
    """Re-analyze a template with additional user context."""
    template = await db.social_learning_templates.find_one({"id": template_id})
    if not template:
        raise HTTPException(404, "Template not found")
    if template["created_by"] != user["user_id"]:
        raise HTTPException(403, "Only the creator can re-analyze")

    original_content = template.get("original_content", "")
    if not original_content:
        raise HTTPException(400, "No original content available for re-analysis")

    # Re-classify with additional context
    enhanced_content = f"""{original_content}

--- ADDITIONAL USER CONTEXT ---
{data.additional_context}
{f"Focus on: {data.focus_area}" if data.focus_area else ""}"""

    try:
        classification = await classify_news(enhanced_content)
    except Exception as e:
        logger.error(f"Re-analysis failed: {e}")
        raise HTTPException(500, f"Re-analysis failed: {str(e)}")

    # Build updated fields
    la_mapping = classification.get("life_area_mapping", {})
    region = classification.get("region_hierarchy", {})
    scenario = classification.get("scenario_mapping", {})
    mydezider = classification.get("learnings_for_mydezider", {})
    solution_finder = classification.get("learnings_for_solution_finder", {})

    factors = mydezider.get("factors", [])
    for f in factors:
        f["approved"] = False
        f["modified_by_user"] = False

    risks = solution_finder.get("risks", [])
    for r in risks:
        r["approved"] = False
        r["modified_by_user"] = False
        if "risk_index" not in r:
            r["risk_index"] = r.get("probability", 5) * r.get("impact", 5)

    life_areas = [la_mapping.get("primary_life_area_id", "")]
    life_areas += classification.get("secondary_life_areas", [])
    life_areas = [la for la in life_areas if la]

    now = datetime.now(timezone.utc).isoformat()
    update = {
        "english_summary": classification.get("english_summary", template.get("english_summary", "")),
        "title": classification.get("original_title", template.get("title", "")),
        "category": classification.get("category", template.get("category", "")),
        "region_hierarchy": region,
        "geo_level": region.get("level", "global"),
        "life_area_mapping": la_mapping,
        "life_areas": life_areas,
        "primary_life_area": la_mapping.get("primary_life_area_id", ""),
        "life_area_sub_area": la_mapping.get("sub_area_1", ""),
        "life_area_sub_area_2": la_mapping.get("sub_area_2"),
        "scenario_mapping": scenario,
        "learnings_mydezider": {"factors": factors, "summary": mydezider.get("summary", "")},
        "factors": factors,
        "learnings_solution_finder": {"risks": risks, "summary": solution_finder.get("summary", "")},
        "root_causes": classification.get("root_causes", []),
        "lessons_learned": classification.get("lessons_learned", []),
        "severity_score": classification.get("severity_score", 5),
        "tags": classification.get("tags", []),
        "updated_at": now,
        "re_analysis_context": data.additional_context,
        "re_analysis_count": template.get("re_analysis_count", 0) + 1,
    }

    await db.social_learning_templates.update_one({"id": template_id}, {"$set": update})

    updated = await db.social_learning_templates.find_one({"id": template_id}, {"_id": 0, "original_content": 0})
    return updated


# ========================
# TIER 2: Admin Approval → Authorized Social Learning Templates
# ========================

@router.get("/admin/pending")
async def get_pending_templates(
    category: Optional[str] = None,
    life_area: Optional[str] = None,
    limit: int = 30,
    skip: int = 0,
    user: dict = Depends(get_current_user),
):
    """List submitted templates pending admin approval."""
    await require_admin(user)
    query: dict = {"status": "submitted"}
    if category:
        query["category"] = category
    if life_area:
        query["life_areas"] = life_area

    total = await db.social_learning_templates.count_documents(query)
    templates = await db.social_learning_templates.find(
        query, {"_id": 0}
    ).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)

    return {"total": total, "templates": templates}


@router.post("/admin/approve/{template_id}")
async def approve_template(template_id: str, data: AdminApprovalRequest, request: Request, user: dict = Depends(get_current_user)):
    """Approve or reject a submitted template. Approved = Tier 2."""
    await require_admin(user)

    template = await db.social_learning_templates.find_one({"id": template_id})
    if not template:
        raise HTTPException(404, "Template not found")
    if template["status"] != "submitted":
        raise HTTPException(400, f"Template status is '{template['status']}', expected 'submitted'")

    if data.status not in ["authorized", "rejected"]:
        raise HTTPException(400, "Status must be 'authorized' or 'rejected'")

    now = datetime.now(timezone.utc).isoformat()
    update = {
        "status": data.status,
        "admin_notes": data.admin_notes or "",
        "updated_at": now,
    }
    if data.status == "authorized":
        update["tier"] = 2
        update["authorized_at"] = now
        update["authorized_by"] = user["user_id"]

    await db.social_learning_templates.update_one({"id": template_id}, {"$set": update})

    await log_audit_event(
        action=f"social_learning_{data.status}", entity_type="social_learning",
        entity_id=template_id, user_id=user["user_id"],
        details=f"Template {data.status}: {template.get('title', '')[:60]}. Notes: {data.admin_notes or 'N/A'}",
        ip_address=get_client_ip(request),
    )

    return {"id": template_id, "status": data.status, "tier": 2 if data.status == "authorized" else 1}


@router.get("/authorized")
async def get_authorized_templates(
    category: Optional[str] = None,
    life_area: Optional[str] = None,
    org_type: Optional[str] = None,
    region: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 30,
    skip: int = 0,
    user: dict = Depends(get_current_user),
):
    """Browse Authorized Social Learning Templates (Tier 2). Available to all users."""
    query: dict = {"status": "authorized", "tier": 2}
    if category:
        query["category"] = category
    if life_area:
        query["life_areas"] = life_area
    if org_type:
        query["org_types"] = org_type
    if region:
        query["geo_regions"] = region
    if search:
        query["$or"] = [
            {"title": {"$regex": search, "$options": "i"}},
            {"english_summary": {"$regex": search, "$options": "i"}},
            {"tags": {"$regex": search, "$options": "i"}},
        ]

    total = await db.social_learning_templates.count_documents(query)
    templates = await db.social_learning_templates.find(
        query, {"_id": 0, "original_content": 0}
    ).sort("severity_score", -1).skip(skip).limit(limit).to_list(limit)

    return {"total": total, "templates": templates}


# ========================
# TIER 3: Social Solution Templates (AI Synthesis)
# ========================

@router.post("/admin/synthesize")
async def synthesize_social_solution(data: SynthesizeRequest, request: Request, user: dict = Depends(get_current_user)):
    """Synthesize multiple Authorized templates into a Social Solution Template (Tier 3). Admin-only."""
    await require_admin(user)

    if len(data.template_ids) < 2:
        raise HTTPException(400, "At least 2 Authorized templates required for synthesis")

    templates = await db.social_learning_templates.find(
        {"id": {"$in": data.template_ids}, "status": "authorized", "tier": 2}, {"_id": 0}
    ).to_list(100)

    if len(templates) < 2:
        raise HTTPException(400, f"Only {len(templates)} authorized templates found. Need at least 2.")

    try:
        synthesis = await synthesize_templates(templates, {
            "target_region": data.target_region,
            "target_org_type": data.target_org_type,
            "target_life_area": data.target_life_area,
        })
    except Exception as e:
        logger.error(f"Synthesis failed: {e}")
        raise HTTPException(500, f"AI synthesis failed: {str(e)}")

    now = datetime.now(timezone.utc).isoformat()
    solution_id = f"SST-{uuid.uuid4().hex[:10].upper()}"

    solution = {
        "id": solution_id,
        "tier": 3,
        "status": "active",
        "created_by": user["user_id"],
        "created_at": now,

        "source_template_ids": data.template_ids,
        "source_count": len(templates),
        "target_region": data.target_region,
        "target_org_type": data.target_org_type,
        "target_life_area": data.target_life_area,

        "title": synthesis.get("title", "Synthesized Template"),
        "description": synthesis.get("description", ""),
        "category": synthesis.get("category", "problem"),
        "life_areas": synthesis.get("life_areas", []),
        "primary_life_area": synthesis.get("primary_life_area", ""),
        "life_area_sub_area": synthesis.get("life_area_sub_area", ""),
        "org_types": synthesis.get("org_types", []),
        "geo_relevance": synthesis.get("geo_relevance", ""),
        "pattern_identified": synthesis.get("pattern_identified", ""),

        "synthesized_factors": synthesis.get("synthesized_factors", []),
        "synthesized_concerns": synthesis.get("synthesized_concerns", []),
        "combined_lessons": synthesis.get("combined_lessons", []),
        "combined_root_causes": synthesis.get("combined_root_causes", []),
        "accuracy_notes": synthesis.get("accuracy_notes", ""),

        "premium_life_scenario": synthesis.get("premium_life_scenario", {}),

        "tags": synthesis.get("tags", []),
        "access_tier": "premium",
    }

    await db.social_solution_templates.insert_one(solution)

    await log_audit_event(
        action="social_solution_synthesized", entity_type="social_solution",
        entity_id=solution_id, user_id=user["user_id"],
        details=f"Social Solution Template synthesized from {len(templates)} sources: {solution['title'][:60]}",
        ip_address=get_client_ip(request),
    )

    solution.pop("_id", None)
    return solution


@router.get("/solutions")
async def get_social_solutions(
    category: Optional[str] = None,
    life_area: Optional[str] = None,
    org_type: Optional[str] = None,
    region: Optional[str] = None,
    access_tier: Optional[str] = None,
    limit: int = 30,
    skip: int = 0,
    user: dict = Depends(get_current_user),
):
    """Browse Social Solution Templates (Tier 3)."""
    query: dict = {"status": "active", "tier": 3}
    if category:
        query["category"] = category
    if life_area:
        query["life_areas"] = life_area
    if org_type:
        query["org_types"] = org_type
    if region:
        query["geo_relevance"] = {"$regex": region, "$options": "i"}
    if access_tier:
        query["access_tier"] = access_tier

    total = await db.social_solution_templates.count_documents(query)
    solutions = await db.social_solution_templates.find(
        query, {"_id": 0}
    ).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)

    return {"total": total, "solutions": solutions}


@router.get("/solution/{solution_id}")
async def get_social_solution(solution_id: str, user: dict = Depends(get_current_user)):
    """Get a specific Social Solution Template."""
    solution = await db.social_solution_templates.find_one({"id": solution_id}, {"_id": 0})
    if not solution:
        raise HTTPException(404, "Social Solution Template not found")
    return solution


# ========================
# INTEGRATION: Templates for PRR & Solution Finder
# ========================

@router.get("/templates-for-decision")
async def get_templates_for_decision(
    life_area: Optional[str] = None,
    sub_area: Optional[str] = None,
    category: Optional[str] = None,
    org_type: Optional[str] = None,
    region: Optional[str] = None,
    include_personal: bool = False,
    limit: int = 20,
    user: dict = Depends(get_current_user),
):
    """Get factor suggestions for My Dezider decision flow.
    Returns 3-tier structure: Personal (Tier 1), Admin-Authorized (Tier 2), AI-Derived (Tier 3).
    Filters by OrgType, Region, LifeArea, SubArea, Scenario.
    """
    tier_1 = []
    tier_2 = []
    tier_3 = []

    # Helper to build factor suggestion from template
    def extract_factors(t, source_tier, source_label):
        factors = t.get("factors", [])
        learnings = t.get("learnings_mydezider", {})
        if learnings.get("factors"):
            factors = learnings["factors"]

        scenario = t.get("scenario_mapping", {})
        return {
            "id": t.get("id", ""),
            "tier": source_tier,
            "source": source_label,
            "title": t.get("title", ""),
            "category": t.get("category", ""),
            "life_areas": t.get("life_areas", []),
            "primary_life_area": t.get("primary_life_area", ""),
            "sub_area": t.get("life_area_sub_area", ""),
            "sub_area_2": t.get("life_area_sub_area_2"),
            "region_hierarchy": t.get("region_hierarchy", {}),
            "org_types": t.get("org_types", []),
            "scenario_title": scenario.get("suggested_new_scenario", {}).get("title", "") or scenario.get("predefined_scenario_title", ""),
            "severity_score": t.get("severity_score", 5),
            "factors": [
                {
                    "name": f.get("name", ""),
                    "description": f.get("description", ""),
                    "practical_priority": f.get("practical_priority", "P5"),
                    "practical_priority_num": f.get("practical_priority_num", 5),
                    "classification": f.get("classification", "optional"),
                    "expected_value": f.get("expected_value", ""),
                    "expected_value_pct": f.get("expected_value_pct", 50),
                    "factor_type": f.get("factor_type", "qualitative"),
                    "unit": f.get("unit"),
                    "approved": f.get("approved", False),
                }
                for f in factors
            ],
            "factor_summary": learnings.get("summary", ""),
        }

    # Build base query filters
    base_filter: dict = {}
    if life_area:
        base_filter["$or"] = [{"life_areas": life_area}, {"primary_life_area": life_area}]
    if sub_area:
        base_filter["life_area_sub_area"] = {"$regex": sub_area, "$options": "i"}
    if category:
        base_filter["category"] = category
    if org_type:
        base_filter["org_types"] = org_type
    if region:
        base_filter["$or"] = base_filter.get("$or", []) + [
            {"region_hierarchy.country": {"$regex": region, "$options": "i"}},
            {"region_hierarchy.state": {"$regex": region, "$options": "i"}},
        ]

    # Tier 1: User's own templates (personal)
    if include_personal:
        t1_query = {**base_filter, "created_by": user["user_id"]}
        t1_query.setdefault("status", {"$in": ["draft", "submitted", "authorized"]})
        t1_templates = await db.social_learning_templates.find(
            t1_query, {"_id": 0, "original_content": 0}
        ).sort("severity_score", -1).limit(limit).to_list(limit)
        for t in t1_templates:
            tier_1.append(extract_factors(t, 1, "personal"))

    # Tier 2: Admin-authorized templates
    t2_query = {**base_filter, "status": "authorized", "tier": 2}
    t2_templates = await db.social_learning_templates.find(
        t2_query, {"_id": 0, "original_content": 0}
    ).sort("severity_score", -1).limit(limit).to_list(limit)
    for t in t2_templates:
        tier_2.append(extract_factors(t, 2, "authorized"))

    # Tier 3: AI-derived Social Solution Templates
    t3_query: dict = {"status": "active", "tier": 3}
    if life_area:
        t3_query["$or"] = [{"life_areas": life_area}, {"primary_life_area": life_area}]
    t3_solutions = await db.social_solution_templates.find(
        t3_query, {"_id": 0}
    ).sort("created_at", -1).limit(limit // 2).to_list(limit // 2)
    for s in t3_solutions:
        synth_factors = s.get("synthesized_factors", [])
        tier_3.append({
            "id": s["id"],
            "tier": 3,
            "source": "ai_derived",
            "title": s.get("title", ""),
            "category": s.get("category", ""),
            "life_areas": s.get("life_areas", []),
            "primary_life_area": s.get("primary_life_area", ""),
            "sub_area": s.get("life_area_sub_area", ""),
            "severity_score": 8,
            "scenario_title": s.get("pattern_identified", ""),
            "source_count": s.get("source_count", 0),
            "factors": [
                {
                    "name": f.get("name", ""),
                    "description": "",
                    "practical_priority_num": f.get("priority", 5),
                    "practical_priority": f"P{f.get('priority', 5)}",
                    "classification": "mandatory" if f.get("priority", 5) >= 7 else "optional",
                    "expected_value_pct": f.get("expected_value_pct", 50),
                    "factor_type": "qualitative",
                    "confidence": f.get("confidence", "medium"),
                    "supporting_template_count": f.get("supporting_template_count", 1),
                }
                for f in synth_factors
            ],
            "factor_summary": s.get("accuracy_notes", ""),
        })

    return {
        "tier_1_personal": tier_1,
        "tier_2_authorized": tier_2,
        "tier_3_ai_derived": tier_3,
        "total": len(tier_1) + len(tier_2) + len(tier_3),
    }


@router.get("/templates-for-solution-finder")
async def get_templates_for_solution_finder(
    life_area: Optional[str] = None,
    sub_area: Optional[str] = None,
    category: Optional[str] = None,
    org_type: Optional[str] = None,
    region: Optional[str] = None,
    include_personal: bool = False,
    limit: int = 20,
    user: dict = Depends(get_current_user),
):
    """Get risk suggestions for Solution Finder Q4.
    Returns 3-tier structure: Personal (Tier 1), Admin-Authorized (Tier 2), AI-Derived (Tier 3).
    """
    tier_1 = []
    tier_2 = []
    tier_3 = []

    def extract_risks(t, source_tier, source_label):
        learnings = t.get("learnings_solution_finder", {})
        risks = learnings.get("risks", [])
        scenario = t.get("scenario_mapping", {})
        return {
            "id": t.get("id", ""),
            "tier": source_tier,
            "source": source_label,
            "title": t.get("title", ""),
            "category": t.get("category", ""),
            "life_areas": t.get("life_areas", []),
            "primary_life_area": t.get("primary_life_area", ""),
            "sub_area": t.get("life_area_sub_area", ""),
            "region_hierarchy": t.get("region_hierarchy", {}),
            "org_types": t.get("org_types", []),
            "scenario_title": scenario.get("suggested_new_scenario", {}).get("title", "") or scenario.get("predefined_scenario_title", ""),
            "severity_score": t.get("severity_score", 5),
            "risks": [
                {
                    "risk_name": r.get("risk_name", ""),
                    "description": r.get("description", ""),
                    "probability": r.get("probability", 5),
                    "impact": r.get("impact", 5),
                    "risk_index": r.get("risk_index", 25),
                    "mitigation_plan": r.get("mitigation_plan", ""),
                    "contingency_plan": r.get("contingency_plan", ""),
                    "personalization_note": r.get("personalization_note", ""),
                    "approved": r.get("approved", False),
                }
                for r in risks
            ],
            "risk_summary": learnings.get("summary", ""),
        }

    base_filter: dict = {}
    if life_area:
        base_filter["$or"] = [{"life_areas": life_area}, {"primary_life_area": life_area}]
    if sub_area:
        base_filter["life_area_sub_area"] = {"$regex": sub_area, "$options": "i"}
    if category:
        base_filter["category"] = category
    if org_type:
        base_filter["org_types"] = org_type

    # Tier 1: Personal
    if include_personal:
        t1_query = {**base_filter, "created_by": user["user_id"]}
        t1_query.setdefault("status", {"$in": ["draft", "submitted", "authorized"]})
        t1_templates = await db.social_learning_templates.find(
            t1_query, {"_id": 0, "original_content": 0}
        ).sort("severity_score", -1).limit(limit).to_list(limit)
        for t in t1_templates:
            tier_1.append(extract_risks(t, 1, "personal"))

    # Tier 2: Authorized
    t2_query = {**base_filter, "status": "authorized", "tier": 2}
    t2_templates = await db.social_learning_templates.find(
        t2_query, {"_id": 0, "original_content": 0}
    ).sort("severity_score", -1).limit(limit).to_list(limit)
    for t in t2_templates:
        tier_2.append(extract_risks(t, 2, "authorized"))

    # Tier 3: AI-derived
    t3_query: dict = {"status": "active", "tier": 3}
    if life_area:
        t3_query["$or"] = [{"life_areas": life_area}, {"primary_life_area": life_area}]
    t3_solutions = await db.social_solution_templates.find(
        t3_query, {"_id": 0}
    ).sort("created_at", -1).limit(limit // 2).to_list(limit // 2)
    for s in t3_solutions:
        synth_concerns = s.get("synthesized_concerns", [])
        tier_3.append({
            "id": s["id"],
            "tier": 3,
            "source": "ai_derived",
            "title": s.get("title", ""),
            "category": s.get("category", ""),
            "life_areas": s.get("life_areas", []),
            "primary_life_area": s.get("primary_life_area", ""),
            "severity_score": 8,
            "source_count": s.get("source_count", 0),
            "risks": [
                {
                    "risk_name": c.get("concern", ""),
                    "description": "",
                    "probability": 6,
                    "impact": 7 if c.get("severity") == "high" else 5 if c.get("severity") == "medium" else 3,
                    "risk_index": 6 * (7 if c.get("severity") == "high" else 5 if c.get("severity") == "medium" else 3),
                    "mitigation_plan": c.get("mitigation_consensus", ""),
                    "contingency_plan": "",
                    "frequency": c.get("frequency", ""),
                }
                for c in synth_concerns
            ],
            "risk_summary": s.get("accuracy_notes", ""),
        })

    return {
        "tier_1_personal": tier_1,
        "tier_2_authorized": tier_2,
        "tier_3_ai_derived": tier_3,
        "total": len(tier_1) + len(tier_2) + len(tier_3),
    }


# ========================
# STATS & FILTERS
# ========================

@router.get("/stats")
async def get_social_learning_stats(user: dict = Depends(get_current_user)):
    """Get overall social learning statistics."""
    total_t1 = await db.social_learning_templates.count_documents({"tier": 1})
    total_t2 = await db.social_learning_templates.count_documents({"tier": 2, "status": "authorized"})
    total_t3 = await db.social_solution_templates.count_documents({"tier": 3})
    pending = await db.social_learning_templates.count_documents({"status": "submitted"})
    my_count = await db.social_learning_templates.count_documents({"created_by": user["user_id"]})

    pipeline = [
        {"$match": {"status": "authorized"}},
        {"$group": {"_id": "$category", "count": {"$sum": 1}}},
    ]
    cat_breakdown = await db.social_learning_templates.aggregate(pipeline).to_list(10)

    pipeline_la = [
        {"$match": {"status": "authorized"}},
        {"$unwind": "$life_areas"},
        {"$group": {"_id": "$life_areas", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ]
    la_breakdown = await db.social_learning_templates.aggregate(pipeline_la).to_list(20)

    return {
        "tier_1_user_templates": total_t1,
        "tier_2_authorized": total_t2,
        "tier_3_solutions": total_t3,
        "pending_review": pending,
        "my_templates": my_count,
        "category_breakdown": [{**c, "category": c["_id"]} for c in cat_breakdown],
        "life_area_breakdown": [{**la, "life_area": la["_id"]} for la in la_breakdown],
    }


@router.get("/filter-options")
async def get_filter_options(user: dict = Depends(get_current_user)):
    """Get available filter options for browsing templates."""
    return {
        "categories": CATEGORIES,
        "life_areas": LIFE_AREAS,
        "org_types": ORG_TYPES,
        "languages": SUPPORTED_LANGUAGES,
        "template_statuses": TEMPLATE_STATUSES,
    }
