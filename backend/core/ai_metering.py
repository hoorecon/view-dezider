"""Metered LLM calls for the per-user AI-credits wallet.

Used ONLY by the metered AI features (AI Assist, AI auto-fetch, AI subjective
scoring). Routing for these features is **Gemini-first** using the developer's
own GEMINI_API_KEY (free daily tier) and **falls back to Emergent** when the
Gemini key is missing or the free quota/rate limit is exhausted. Other AI
features are untouched (they keep using the global Emergent default).

Each call:
  1. gates on the user's wallet balance (raises InsufficientCredits at 0),
  2. runs the LLM and reads the REAL token usage (Gemini) or estimates it
     (Emergent fallback),
  3. charges the wallet by actual tokens (credits = tokens / tokens_per_credit).
"""
from __future__ import annotations

import logging
import os
import uuid
from typing import Optional, Tuple

from core import ai_wallet

log = logging.getLogger("ai_metering")

GEMINI_MODEL = os.getenv("METERED_GEMINI_MODEL", "gemini-2.5-flash")


def _estimate_tokens(*texts: str) -> int:
    chars = sum(len(t or "") for t in texts)
    return max(1, chars // 4)  # ~4 chars/token heuristic


async def _gemini_call(system_message: str, prompt: str) -> Tuple[str, int]:
    """Direct Gemini via litellm using the user's own key. Returns (text, tokens).
    Raises on quota/rate/auth errors so the caller can fall back to Emergent."""
    from litellm import acompletion

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not set")
    resp = await acompletion(
        model=f"gemini/{GEMINI_MODEL}",
        messages=[{"role": "system", "content": system_message}, {"role": "user", "content": prompt}],
        api_key=api_key,
        timeout=60,
    )
    text = (resp.choices[0].message.content or "").strip()
    usage = getattr(resp, "usage", None)
    tokens = 0
    if usage is not None:
        tokens = int(getattr(usage, "total_tokens", 0) or 0)
    if tokens <= 0:
        tokens = _estimate_tokens(system_message, prompt, text)
    return text, tokens


async def _emergent_call(system_message: str, prompt: str, session_prefix: str) -> Tuple[str, int]:
    """Emergent fallback (universal key). emergentintegrations doesn't surface
    token counts here, so we estimate from text length."""
    from core.llm_compat import LlmChat, UserMessage

    chat = LlmChat(
        api_key=os.getenv("EMERGENT_LLM_KEY"),
        session_id=f"{session_prefix}_{uuid.uuid4().hex[:8]}",
        system_message=system_message,
        provider_override="emergent",
    ).with_model("gemini", GEMINI_MODEL)
    text = await chat.send_message(UserMessage(text=prompt))
    return (text or "").strip(), _estimate_tokens(system_message, prompt, text or "")


async def metered_chat(
    user_id: str, *, system_message: str, prompt: str,
    feature: str, session_prefix: str = "metered",
) -> str:
    """Gate → Gemini-first → Emergent fallback → charge the wallet.

    Raises ai_wallet.InsufficientCredits when the user has no credits.
    Returns the model's text response.
    """
    await ai_wallet.ensure_can_spend(user_id)

    text: str
    tokens: int
    provider: str
    try:
        text, tokens = await _gemini_call(system_message, prompt)
        provider = "gemini"
    except ai_wallet.InsufficientCredits:
        raise
    except Exception as e:
        log.warning(f"metered gemini call failed ({type(e).__name__}: {str(e)[:120]}); falling back to emergent")
        text, tokens = await _emergent_call(system_message, prompt, session_prefix)
        provider = "emergent"

    try:
        await ai_wallet.charge(user_id, tokens=tokens, feature=feature, provider=provider)
    except Exception as e:
        log.error(f"wallet charge failed (non-fatal): {e}")
    return text


def has_any_llm() -> bool:
    return bool(os.getenv("GEMINI_API_KEY") or os.getenv("EMERGENT_LLM_KEY"))
