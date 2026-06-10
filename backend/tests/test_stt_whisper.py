"""Regression: voice transcription must NOT 500 (the old Google-STT/FLAC bug).

The previous Google free-STT raised an uncaught OSError ("FLAC conversion
utility not available") → HTTP 500. The engine now uses Groq Whisper (free)
→ OpenAI Whisper fallback via litellm, accepting wav/webm directly.
"""
import os
import urllib.request

import pytest

from routes.social_learning.stt_engine import stt_engine

SAMPLE_URL = "https://github.com/realpython/python-speech-recognition/raw/master/audio_files/harvard.wav"


def _sample_wav():
    path = "/tmp/harvard_test.wav"
    if not os.path.exists(path):
        try:
            urllib.request.urlretrieve(SAMPLE_URL, path)
        except Exception:
            return None
    return path


def test_transcribe_real_wav_via_whisper():
    """Real English speech transcribes to text (Groq Whisper free tier)."""
    if not os.getenv("GROQ_API_KEY") and not os.getenv("OPENAI_API_KEY"):
        pytest.skip("no STT provider configured")
    path = _sample_wav()
    if not path:
        pytest.skip("could not fetch sample audio")
    text = stt_engine.transcribe(open(path, "rb").read(), audio_format="wav", language="en-US")
    assert isinstance(text, str) and len(text) > 10
    # harvard.wav opens with "The stale smell of old beer lingers."
    assert "beer" in text.lower() or "smell" in text.lower()


def test_transcribe_no_provider_raises_valueerror(monkeypatch):
    """With no keys, raises ValueError (→ HTTP 400 'type instead'), never a 500."""
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ValueError):
        stt_engine.transcribe(b"RIFFxxxx", audio_format="wav", language="en-US")
