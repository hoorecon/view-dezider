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


async def user_consent(user_id: str) -> dict:
    """Full AI-provider consent doc (allow_openai + openai_free_tier).
    Keeps a single round-trip even when callers need both flags."""
    try:
        from core.database import db
        u = await db.users.find_one({"user_id": user_id}, {"_id": 0, "ai_provider_consent": 1})
        return (u or {}).get("ai_provider_consent") or {}
    except Exception:
        return {}


async def user_allows_openai(user_id: str) -> bool:
    """Read the user's consent to use their data with OpenAI's free tier."""
    return bool((await user_consent(user_id)).get("allow_openai"))


def _build_chain(allow_openai: bool, openai_before_groq: bool = False,
                 openai_first: bool = False) -> list:
    """Ordered list of (provider_name) using only configured keys.
    `openai_before_groq=True` is used by the precise tier's fallback path
    (user-mandated order: Claude → Gemini → OpenAI → Groq).
    `openai_first=True` (set when the user has confirmed OpenAI free-tier
    data-sharing is enabled) puts OpenAI at the FRONT of the chain — so
    every call goes through their FREE OpenAI bucket before touching the
    paid wallet at all."""
    chain: list = []
    if allow_openai and os.getenv("OPENAI_API_KEY") and openai_first:
        chain.append("openai")
    if os.getenv("GEMINI_API_KEY"):
        chain.append("gemini")
    if allow_openai and os.getenv("OPENAI_API_KEY") and openai_before_groq and not openai_first:
        chain.append("openai")
    if os.getenv("GROQ_API_KEY"):
        chain.append("groq")
    if allow_openai and os.getenv("OPENAI_API_KEY") and not openai_before_groq and not openai_first:
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
    # Resolve consent UP-FRONT so we can decide whether the wallet matters.
    # When the user has confirmed they enabled OpenAI's data-sharing free
    # tier (`openai_free_tier=true`) AND the server has an OPENAI_API_KEY,
    # the call costs $0 → wallet balance is irrelevant and we MUST NOT gate
    # on it. Previously `ensure_can_spend()` ran first and rejected users
    # with a negative balance even after they opted into the free tier.
    consent = await user_consent(user_id)
    openai_first = bool(consent.get("openai_free_tier")) and bool(os.getenv("OPENAI_API_KEY"))
    if not openai_first:
        await ai_wallet.ensure_can_spend(user_id)

    # ── "Costly & Precise" tier — Claude via the Emergent universal key ──
    if tier == "precise" and os.getenv("EMERGENT_LLM_KEY") and not openai_first:
        cfg = await ai_wallet.get_config()
        model = str(cfg.get("precise_model") or "claude-sonnet-4-6")
        try:
            text, tokens = await _emergent_call(
                system_message, prompt, session_prefix, provider="anthropic", model=model)
        except Exception as e:  # noqa: BLE001 — fall through to the fast chain
            log.warning(f"precise tier ({model}) failed ({type(e).__name__}: {str(e)[:120]}); "
                        "falling back to the standard chain")
        else:
            charged = 0.0
            try:
                res = await ai_wallet.charge(
                    user_id, tokens=tokens, feature=feature, provider="emergent_precise",
                    session_id=session_id, credit_multiplier=ai_wallet.precise_multiplier(cfg))
                charged = float(res.get("charged") or 0)
            except Exception as e:  # noqa: BLE001
                log.error(f"wallet charge failed (non-fatal): {e}")
            if meta is not None:
                meta.update(provider="emergent_precise", model=model,
                            tokens=tokens, credits=charged)
            return text

    if allow_openai is None:
        allow_openai = await user_allows_openai(user_id)
    # When the user has confirmed they enabled OpenAI's data-sharing free tier
    # on their org (`openai_free_tier=true`), route OpenAI FIRST and zero out
    # the wallet charge for those calls (OpenAI bills $0 — passing on the
    # saving is the entire point of the toggle).
    consent = await user_consent(user_id)
    openai_first = bool(consent.get("openai_free_tier")) and bool(os.getenv("OPENAI_API_KEY"))
    if openai_first:
        allow_openai = True  # implied — we can't route OpenAI without consent

    chain = _build_chain(allow_openai, openai_first=openai_first,
                         openai_before_groq=(tier == "precise"))
    last_err: Optional[Exception] = None
    for provider in chain:
        try:
            if provider == "gemini":
                model_used = GEMINI_MODEL
                text, tokens = await _direct_call(f"gemini/{GEMINI_MODEL}", os.getenv("GEMINI_API_KEY"), system_message, prompt)
            elif provider == "groq":
                model_used = GROQ_MODEL
                text, tokens = await _direct_call(f"groq/{GROQ_MODEL}", os.getenv("GROQ_API_KEY"), system_message, prompt)
            elif provider == "openai":
                model_used = OPENAI_MODEL
                text, tokens = await _direct_call(OPENAI_MODEL, os.getenv("OPENAI_API_KEY"), system_message, prompt)
            else:
                model_used = GEMINI_MODEL
                text, tokens = await _emergent_call(system_message, prompt, session_prefix)
        except ai_wallet.InsufficientCredits:
            raise
        except Exception as e:  # noqa: BLE001
            last_err = e
            log.warning(f"metered {provider} call failed ({type(e).__name__}: {str(e)[:120]}); advancing chain")
            continue

        charged = 0.0
        try:
            # Free-tier short-circuit — OpenAI bills $0 on the data-sharing
            # programme, so we don't charge the user wallet either. The ledger
            # still gets a zero-credit "audit" row so admin Recon shows the
            # provider hit & token count.
            if provider == "openai" and openai_first:
                from core.database import db as _db
                from datetime import datetime, timezone
                try:
                    await _db.ai_wallet_ledger.insert_one({
                        "user_id": user_id, "kind": "debit",
                        "credits": 0.0, "tokens": int(tokens or 0),
                        "feature": feature, "provider": "openai_free_tier",
                        "session_id": session_id, "ts": datetime.now(timezone.utc),
                        "meta": {"note": "free-tier data-sharing"},
                    })
                except Exception:  # noqa: BLE001 — audit row is best-effort
                    pass
            else:
                res = await ai_wallet.charge(user_id, tokens=tokens, feature=feature,
                                             provider=provider, session_id=session_id)
                charged = float(res.get("charged") or 0)
        except Exception as e:  # noqa: BLE001
            log.error(f"wallet charge failed (non-fatal): {e}")
        if meta is not None:
            meta.update(provider=provider, model=model_used,
                        tokens=tokens, credits=charged)
        return text

    raise last_err or RuntimeError("All LLM providers failed")


def has_any_llm() -> bool:
    return bool(
        os.getenv("GEMINI_API_KEY") or os.getenv("GROQ_API_KEY")
        or os.getenv("OPENAI_API_KEY") or os.getenv("EMERGENT_LLM_KEY")
    )
