"""
Provider-agnostic LLM compatibility shim.
============================================

Drop-in replacement for ``emergentintegrations.llm.chat`` so the 14 route
files that previously hard-imported Emergent's package don't have to change
their call-site code. They only swap the import line:

   # OLD (Emergent-locked)
   from core.llm_compat import LlmChat, UserMessage  # provider-agnostic shim (Emergent | direct via litellm)

   # NEW (platform-agnostic)
   from core.llm_compat import LlmChat, UserMessage

Routing logic (driven by `LLM_PROVIDER_MODE` env var):

   • ``LLM_PROVIDER_MODE=emergent`` (or unset + EMERGENT_LLM_KEY present)
     → uses the original ``emergentintegrations`` package under the hood.
     Zero behavioural change. Keeps you on Emergent's universal key.

   • ``LLM_PROVIDER_MODE=direct`` (or unset + any of OPENAI / ANTHROPIC /
     GOOGLE_API_KEY present)
     → uses ``litellm`` directly with your own provider keys.
     No Emergent middleman. Bring-your-own-key.

   • ``LLM_PROVIDER_MODE=auto`` (default)
     → picks ``direct`` if any direct provider key is set, else
     ``emergent`` if EMERGENT_LLM_KEY is set, else raises.

Why this matters
----------------
This shim is the **single point of contact** with whichever LLM backend
you choose. To migrate this codebase to Cursor / Claude Code / Lovable /
Replit / a custom self-hosted setup, you simply set the provider env
vars on the target platform. No code changes required anywhere else.

Hybrid mode
-----------
Set ``LLM_PROVIDER_MODE=direct`` globally but selectively call the
emergent backend for a specific feature by passing
``provider_override="emergent"`` to ``LlmChat(..., provider_override=...)``.
The reverse also works.

Interface preserved
-------------------
   chat = LlmChat(
       api_key=<unused-when-direct>,
       session_id="…",
       system_message="…",
   ).with_model("openai", "gpt-4.1-mini")

   resp_text: str = await chat.send_message(UserMessage(text="…"))

Both ``LlmChat`` and ``UserMessage`` keep the EXACT same shape as
emergentintegrations exposes, so no caller code needs editing.
"""
from __future__ import annotations

import os
import logging
from dataclasses import dataclass
from typing import Optional, List, Dict, Any

log = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# Mode detection
# -----------------------------------------------------------------------------
def _detect_mode() -> str:
    mode = (os.getenv("LLM_PROVIDER_MODE") or "auto").lower().strip()
    if mode in ("emergent", "direct"):
        return mode
    # auto-pick
    if any(os.getenv(k) for k in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY", "GEMINI_API_KEY")):
        return "direct"
    if os.getenv("EMERGENT_LLM_KEY"):
        return "emergent"
    return "direct"  # fall through so users see a clear "missing key" error


# -----------------------------------------------------------------------------
# UserMessage — minimal value object, matches emergentintegrations shape
# -----------------------------------------------------------------------------
@dataclass
class UserMessage:
    text: str
    image_url: Optional[str] = None  # kept for forward-compat; not used by callers today

    def to_litellm(self) -> Dict[str, Any]:
        if self.image_url:
            return {
                "role": "user",
                "content": [
                    {"type": "text", "text": self.text},
                    {"type": "image_url", "image_url": {"url": self.image_url}},
                ],
            }
        return {"role": "user", "content": self.text}


# -----------------------------------------------------------------------------
# LlmChat — same fluent builder shape as emergentintegrations
# -----------------------------------------------------------------------------
class LlmChat:
    def __init__(
        self,
        api_key: Optional[str] = None,
        session_id: Optional[str] = None,
        system_message: Optional[str] = None,
        provider_override: Optional[str] = None,
    ):
        self._api_key = api_key
        self._session_id = session_id
        self._system_message = system_message
        self._provider: str = "openai"
        self._model: str = "gpt-4o-mini"
        self._mode_override = provider_override
        self._history: List[Dict[str, Any]] = []
        if system_message:
            self._history.append({"role": "system", "content": system_message})

    # Fluent setter — mirrors emergentintegrations API
    def with_model(self, provider: str, model: str) -> "LlmChat":
        self._provider = (provider or "openai").lower()
        self._model = model
        return self

    # Public coroutine — preserves return-shape (string) of the original.
    # Adds an automatic fallback chain: try the primary backend first; on
    # auth/quota/network failure, transparently retry against Emergent (or
    # whatever LLM_FALLBACK_PROVIDER is set to). This keeps your app alive
    # when one provider has an outage / your key expired / your quota ran
    # out — at the cost of one extra retry.
    #
    # Disable by setting LLM_FALLBACK_DISABLED=true.
    async def send_message(self, msg: UserMessage) -> str:
        active_mode = (self._mode_override or _detect_mode()).lower()
        fallback_disabled = (os.getenv("LLM_FALLBACK_DISABLED") or "").lower() in ("1", "true", "yes")
        fallback_provider = (os.getenv("LLM_FALLBACK_PROVIDER") or "emergent").lower()

        # Don't fallback to the same provider we're already trying
        if fallback_provider == active_mode:
            fallback_disabled = True

        try:
            if active_mode == "emergent":
                return await self._send_via_emergent(msg)
            return await self._send_via_litellm(msg)
        except Exception as primary_err:
            if fallback_disabled:
                raise
            # Only auto-fallback for transient / vendor / key issues — NOT for
            # programmer errors like malformed prompts. The shim treats any
            # exception conservatively as "primary failed, try fallback".
            log.warning(
                f"LLM primary '{active_mode}' failed ({type(primary_err).__name__}: "
                f"{str(primary_err)[:120]}). Falling back to '{fallback_provider}'."
            )
            try:
                if fallback_provider == "emergent":
                    return await self._send_via_emergent(msg)
                # else fallback to direct via litellm; re-detect with override
                self._mode_override = "direct"
                return await self._send_via_litellm(msg)
            except Exception as fallback_err:
                log.error(
                    f"LLM fallback '{fallback_provider}' ALSO failed "
                    f"({type(fallback_err).__name__}: {str(fallback_err)[:120]}). "
                    "Re-raising original primary error."
                )
                raise primary_err

    # -----------------------------------------------------------------
    # Backend 1 — Emergent's existing wrapper (unchanged behaviour)
    # -----------------------------------------------------------------
    async def _send_via_emergent(self, msg: UserMessage) -> str:
        try:
            from emergentintegrations.llm.chat import (
                LlmChat as _EmergentChat,
                UserMessage as _EmergentMsg,
            )
        except ImportError as e:
            raise RuntimeError(
                "LLM_PROVIDER_MODE=emergent but emergentintegrations is not "
                "installed. Add it back to requirements.txt, OR switch to "
                "LLM_PROVIDER_MODE=direct and set OPENAI_API_KEY etc."
            ) from e

        key = self._api_key or os.getenv("EMERGENT_LLM_KEY")
        if not key:
            raise RuntimeError("EMERGENT_LLM_KEY is not set")

        chat = _EmergentChat(
            api_key=key,
            session_id=self._session_id,
            system_message=self._system_message,
        ).with_model(self._provider, self._model)
        return await chat.send_message(_EmergentMsg(text=msg.text))

    # -----------------------------------------------------------------
    # Backend 2 — Direct via litellm (multi-provider)
    # -----------------------------------------------------------------
    async def _send_via_litellm(self, msg: UserMessage) -> str:
        try:
            from litellm import acompletion
        except ImportError as e:
            raise RuntimeError(
                "litellm is not installed. Run: pip install litellm"
            ) from e

        # Map (provider, model) → litellm-prefixed model string + api_key env
        provider_key_env = {
            "openai":    "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "google":    "GOOGLE_API_KEY",
            "gemini":    "GEMINI_API_KEY",
        }
        # litellm expects "<provider>/<model>" for non-OpenAI; for OpenAI it accepts
        # just "<model>". We normalise:
        if self._provider == "openai":
            model_str = self._model
        elif self._provider == "anthropic":
            model_str = f"anthropic/{self._model}"
        elif self._provider in ("google", "gemini"):
            # google-genai uses "gemini/<model>" in litellm
            model_str = f"gemini/{self._model}"
        else:
            model_str = f"{self._provider}/{self._model}"

        key_env = provider_key_env.get(self._provider)
        api_key = os.getenv(key_env) if key_env else None
        if not api_key:
            raise RuntimeError(
                f"LLM provider '{self._provider}' selected but {key_env} env var "
                "is not set. Set it in your .env or switch LLM_PROVIDER_MODE."
            )

        messages = list(self._history) + [msg.to_litellm()]
        try:
            resp = await acompletion(
                model=model_str,
                messages=messages,
                api_key=api_key,
                timeout=60,
            )
            # litellm returns ModelResponse with choices[0].message.content
            content = (resp.choices[0].message.content or "").strip()
            # Append assistant turn for any follow-up calls on same instance
            self._history.append({"role": "assistant", "content": content})
            return content
        except Exception:
            # Re-raise so callers' existing try/except + llm_errors mapping still works
            raise


# -----------------------------------------------------------------------------
# Helpful one-liners for callers who want to know the current mode
# (used by /api/health/llm-provider if someone wires a route to it)
# -----------------------------------------------------------------------------
def current_mode() -> str:
    return _detect_mode()


def healthcheck_keys() -> Dict[str, bool]:
    return {
        "EMERGENT_LLM_KEY": bool(os.getenv("EMERGENT_LLM_KEY")),
        "OPENAI_API_KEY":   bool(os.getenv("OPENAI_API_KEY")),
        "ANTHROPIC_API_KEY":bool(os.getenv("ANTHROPIC_API_KEY")),
        "GOOGLE_API_KEY":   bool(os.getenv("GOOGLE_API_KEY")),
        "GEMINI_API_KEY":   bool(os.getenv("GEMINI_API_KEY")),
        "active_mode":      current_mode(),  # type: ignore
    }
