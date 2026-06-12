"""Metered LLM calls for the per-user AI-credits wallet.

Used ONLY by the metered AI features (AI Assist, AI auto-fetch, AI subjective
scoring). Routing is a FREE-FIRST fallback chain so the underlying spend stays
as low as possible:

    Gemini (free daily tier)  →  Groq (free tier)  →  OpenAI (user-key, only if
    the user has consented to share data with OpenAI)  →  Emergent (universal key)

Each provider is tried in order; on a rate-limit / quota / budget error we
retry with a short back-off, then advance to the next provider. Only the FIRST
provider that returns text is charged to the user's wallet.

Each call:
  1. gates on the user's wallet balance (raises InsufficientCredits at 0),
  2. runs the provider chain, reading REAL token usage when the provider
     surfaces it (litellm) or estimating it (Emergent),
  3. charges the wallet by actual tokens (credits = tokens / tokens_per_credit).
"""
from __future__ import annotations

import asyncio
import logging
import os
import uuid
from typing import Optional, Tuple

from core import ai_wallet

log = logging.getLogger("ai_metering")

GEMINI_MODEL = os.getenv("METERED_GEMINI_MODEL", "gemini-2.5-flash")
GROQ_MODEL = os.getenv("METERED_GROQ_MODEL", "llama-3.3-70b-versatile")
OPENAI_MODEL = os.getenv("METERED_OPENAI_MODEL", "gpt-4o-mini")

# Per-provider retry/back-off for transient rate limits (429). Free tiers are
# rate-limited per-minute, so a short pause often clears the limit before we
# give up on that (free) provider and advance to the next.
_MAX_RETRIES = 2
_BACKOFF_BASE = 1.2  # seconds; multiplied by (attempt + 1)


def _estimate_tokens(*texts: str) -> int:
    chars = sum(len(t or "") for t in texts)
    return max(1, chars // 4)  # ~4 chars/token heuristic


def _is_rate_limit(exc: Exception) -> bool:
    """True for transient rate-limit/quota errors worth a back-off retry."""
    try:
        import litellm
        if isinstance(exc, getattr(litellm, "RateLimitError", ())):
            return True
    except Exception:
        pass
    s = f"{type(exc).__name__}: {exc}".lower()
    return "429" in s or "rate limit" in s or "ratelimit" in s or "resource_exhausted" in s


async def _direct_call(model: str, api_key: str, system_message: str, prompt: str) -> Tuple[str, int]:
    """Direct provider call via litellm (Gemini / Groq / OpenAI) using the given
    key. Retries with back-off on 429, then raises so the caller can advance to
    the next provider. Returns (text, tokens)."""
    from litellm import acompletion

    if not api_key:
        raise RuntimeError(f"missing api key for {model}")
    last: Optional[Exception] = None
    for attempt in range(_MAX_RETRIES + 1):
        try:
            resp = await acompletion(
                model=model,
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": prompt},
                ],
                api_key=api_key,
                timeout=30,
            )
            text = (resp.choices[0].message.content or "").strip()
            usage = getattr(resp, "usage", None)
            tokens = int(getattr(usage, "total_tokens", 0) or 0) if usage is not None else 0
            if tokens <= 0:
                tokens = _estimate_tokens(system_message, prompt, text)
            return text, tokens
        except Exception as e:  # noqa: BLE001 — classify below
            last = e
            if _is_rate_limit(e) and attempt < _MAX_RETRIES:
                await asyncio.sleep(_BACKOFF_BASE * (attempt + 1))
                continue
            raise
    raise last  # pragma: no cover


async def _emergent_call(system_message: str, prompt: str, session_prefix: str,
                         provider: str = "gemini", model: str = "") -> Tuple[str, int]:
    """Emergent universal-key call (Gemini fallback by default; Claude for the
    precise tier). emergentintegrations doesn't surface token counts here, so
    we estimate from text length."""
    from core.llm_compat import LlmChat, UserMessage

    chat = LlmChat(
        api_key=os.getenv("EMERGENT_LLM_KEY"),
        session_id=f"{session_prefix}_{uuid.uuid4().hex[:8]}",
        system_message=system_message,
        provider_override="emergent",
    ).with_model(provider, model or GEMINI_MODEL)
    text = await chat.send_message(UserMessage(text=prompt))
    return (text or "").strip(), _estimate_tokens(system_message, prompt, text or "")


async def user_allows_openai(user_id: str) -> bool:
    """Read the user's consent to use their data with OpenAI's free tier."""
    try:
        from core.database import db
        u = await db.users.find_one({"user_id": user_id}, {"_id": 0, "ai_provider_consent": 1})
        return bool(((u or {}).get("ai_provider_consent") or {}).get("allow_openai"))
    except Exception:
        return False


def _build_chain(allow_openai: bool, openai_before_groq: bool = False) -> list:
    """Ordered list of (provider_name) using only configured keys.
    `openai_before_groq=True` is used by the precise tier's fallback path
    (user-mandated order: Claude → Gemini → OpenAI → Groq)."""
    chain: list = []
    if os.getenv("GEMINI_API_KEY"):
        chain.append("gemini")
    if allow_openai and os.getenv("OPENAI_API_KEY") and openai_before_groq:
        chain.append("openai")
    if os.getenv("GROQ_API_KEY"):
        chain.append("groq")
    if allow_openai and os.getenv("OPENAI_API_KEY") and not openai_before_groq:
        chain.append("openai")
    if os.getenv("EMERGENT_LLM_KEY"):
        chain.append("emergent")
    return chain


async def metered_chat(
    user_id: str, *, system_message: str, prompt: str,
    feature: str, session_prefix: str = "metered",
    allow_openai: Optional[bool] = None, session_id: str = "",
    tier: str = "fast", meta: Optional[dict] = None,
) -> str:
    """Gate → free-first provider chain → charge the wallet.

    `allow_openai`: None ⇒ resolve from the user's stored consent; True/False ⇒
    explicit override (used by the in-the-moment "use OpenAI free" choice).

    `tier`: "fast" (default) = free-first Gemini chain. "precise" = Claude
    (admin-configured `precise_model`) via the Emergent universal key first,
    charged at the configured cost multiplier; falls back to the fast chain
    when unavailable.

    Raises ai_wallet.InsufficientCredits when the user has no credits.
    Raises the last provider error when EVERY provider in the chain fails
    (caller can treat that as "AI temporarily unavailable").
    Returns the model's text response.
    """
    await ai_wallet.ensure_can_spend(user_id)

    # ── "Costly & Precise" tier — Claude via the Emergent universal key ──
    if tier == "precise" and os.getenv("EMERGENT_LLM_KEY"):
        cfg = await ai_wallet.get_config()
        model = str(cfg.get("precise_model") or "claude-sonnet-4-6")
        try:
            text, tokens = await _emergent_call(
                system_message, prompt, session_prefix, provider="anthropic", model=model)
        except Exception as e:  # noqa: BLE001 — fall through to the fast chain
            log.warning(f"precise tier ({model}) failed ({type(e).__name__}: {str(e)[:120]}); "
                        "falling back to the standard chain")
        else:
            try:
                await ai_wallet.charge(
                    user_id, tokens=tokens, feature=feature, provider="emergent_precise",
                    session_id=session_id, credit_multiplier=ai_wallet.precise_multiplier(cfg))
            except Exception as e:  # noqa: BLE001
                log.error(f"wallet charge failed (non-fatal): {e}")
            if meta is not None:
                meta["provider"] = "emergent_precise"
            return text

    if allow_openai is None:
        allow_openai = await user_allows_openai(user_id)

    chain = _build_chain(allow_openai, openai_before_groq=(tier == "precise"))
    last_err: Optional[Exception] = None
    for provider in chain:
        try:
            if provider == "gemini":
                text, tokens = await _direct_call(f"gemini/{GEMINI_MODEL}", os.getenv("GEMINI_API_KEY"), system_message, prompt)
            elif provider == "groq":
                text, tokens = await _direct_call(f"groq/{GROQ_MODEL}", os.getenv("GROQ_API_KEY"), system_message, prompt)
            elif provider == "openai":
                text, tokens = await _direct_call(OPENAI_MODEL, os.getenv("OPENAI_API_KEY"), system_message, prompt)
            else:
                text, tokens = await _emergent_call(system_message, prompt, session_prefix)
        except ai_wallet.InsufficientCredits:
            raise
        except Exception as e:  # noqa: BLE001
            last_err = e
            log.warning(f"metered {provider} call failed ({type(e).__name__}: {str(e)[:120]}); advancing chain")
            continue

        try:
            await ai_wallet.charge(user_id, tokens=tokens, feature=feature,
                                   provider=provider, session_id=session_id)
        except Exception as e:  # noqa: BLE001
            log.error(f"wallet charge failed (non-fatal): {e}")
        if meta is not None:
            meta["provider"] = provider
        return text

    raise last_err or RuntimeError("All LLM providers failed")


def has_any_llm() -> bool:
    return bool(
        os.getenv("GEMINI_API_KEY") or os.getenv("GROQ_API_KEY")
        or os.getenv("OPENAI_API_KEY") or os.getenv("EMERGENT_LLM_KEY")
    )
