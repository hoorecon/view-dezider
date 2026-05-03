"""
Social Learning Engine — Speech-to-Text Engine
Modular STT engine with audio/video processing.
"""

import io
import os
import tempfile


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
