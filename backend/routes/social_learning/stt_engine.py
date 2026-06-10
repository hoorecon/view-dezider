"""
Social Learning Engine — Speech-to-Text Engine
Whisper-based STT via litellm: Groq whisper-large-v3-turbo (free) PRIMARY,
OpenAI whisper-1 FALLBACK. Both accept webm/wav/mp3/m4a natively, so NO server
ffmpeg/flac/pydub transcoding is required.
"""

import io
import os
import tempfile
import logging

log = logging.getLogger("stt_engine")


class STTEngine:
    """Speech-to-Text via hosted Whisper (Groq → OpenAI fallback).

    The previous implementation used Google's unofficial free STT, which needs
    the `flac` CLI (raising an uncaught OSError → HTTP 500) and `ffmpeg` for
    non-WAV input. Whisper providers ingest the raw audio bytes directly.
    """

    # Provider chain: (litellm model, env key name). Free Groq first.
    _PROVIDERS = (
        ("groq/whisper-large-v3-turbo", "GROQ_API_KEY"),
        ("whisper-1", "OPENAI_API_KEY"),
    )

    @staticmethod
    def transcribe(audio_bytes: bytes, audio_format: str = "wav", language: str = "en-US") -> str:
        """Transcribe audio bytes to text. Accepts wav/mp3/ogg/webm/m4a directly.

        Tries Groq Whisper (free) first, then OpenAI Whisper. Raises ValueError
        (→ HTTP 400, "please type instead") only when EVERY provider fails or
        none is configured — never an uncaught 500.
        """
        import litellm

        ext = (audio_format or "wav").lower()
        if ext == "m4a":
            ext = "m4a"
        lang = (language or "en").split("-")[0] or "en"  # 'en-US' → 'en'

        providers = [(m, os.getenv(k)) for m, k in STTEngine._PROVIDERS if os.getenv(k)]
        if not providers:
            raise ValueError("Speech-to-text is not configured. Please type your response.")

        last_err: Exception | None = None
        for model, api_key in providers:
            try:
                buf = io.BytesIO(audio_bytes)
                buf.name = f"audio.{ext}"  # Whisper infers the format from the name
                resp = litellm.transcription(
                    model=model, file=buf, api_key=api_key, language=lang,
                )
                text = (getattr(resp, "text", None) or "").strip()
                if text:
                    return text
                last_err = ValueError("empty transcription")
            except Exception as e:  # advance to the next provider
                last_err = e
                log.warning(f"STT {model} failed: {type(e).__name__}: {str(e)[:160]}")
                continue

        raise ValueError(
            f"Could not transcribe the audio ({str(last_err)[:120]}). Please type your response."
        )

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
