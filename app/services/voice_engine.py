import io
import asyncio
import tempfile
import logging
from pathlib import Path
from faster_whisper import WhisperModel
from gtts import gTTS
from app.config import settings
from app.utils.file_storage import storage

logger = logging.getLogger(__name__)


class VoiceEngine:

    def __init__(self):
        logger.info(f"Loading faster-whisper model: {settings.WHISPER_MODEL_SIZE}")
        self._whisper_model = None   # lazy load on first use

    @property
    def whisper_model(self) -> WhisperModel:
        """Lazily load the faster-whisper model on first use."""
        if self._whisper_model is None:
            self._whisper_model = WhisperModel(
                settings.WHISPER_MODEL_SIZE,
                device="cpu",
                compute_type="int8",   # efficient CPU inference
            )
            logger.info("faster-whisper model loaded")
        return self._whisper_model

    # ─── Speech-to-Text (faster-whisper) ─────────────────────────────────────

    async def transcribe_audio(self, audio_bytes: bytes, filename: str = "audio.webm") -> dict:
        """
        Convert audio bytes → text using faster-whisper.
        Runs in thread pool to avoid blocking the event loop.
        Returns: {text, language, duration, segments}
        """
        suffix = Path(filename).suffix or ".webm"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: self._run_transcription(tmp_path),
            )
            return result
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def _run_transcription(self, audio_path: str) -> dict:
        """
        Synchronous transcription using faster-whisper.
        Called inside a thread-pool executor.
        """
        segments, info = self.whisper_model.transcribe(
            audio_path,
            language="en",
            beam_size=5,
            vad_filter=True,       # skip silence automatically
        )
        # faster-whisper returns a generator — collect all segments
        segment_list = []
        full_text_parts = []
        for seg in segments:
            full_text_parts.append(seg.text)
            segment_list.append({
                "start": round(seg.start, 2),
                "end": round(seg.end, 2),
                "text": seg.text.strip(),
            })

        return {
            "text": " ".join(full_text_parts).strip(),
            "language": info.language,
            "duration": round(info.duration, 2),
            "segments": segment_list,
        }

    # ─── Text-to-Speech ──────────────────────────────────────────────────────

    async def synthesize_speech(self, text: str, session_id: str, q_num) -> str:
        """
        Convert text → audio file in MinIO/S3.
        Uses ElevenLabs if API key configured, else falls back to gTTS (free).
        Returns: S3 key of uploaded audio file.
        """
        if settings.ELEVENLABS_API_KEY:
            audio_bytes = await self._elevenlabs_tts(text)
            ext = "mp3"
        else:
            audio_bytes = self._gtts_tts(text)
            ext = "mp3"

        s3_key = f"audio/questions/{session_id}/q_{q_num}.{ext}"
        await storage.upload(audio_bytes, s3_key, content_type="audio/mpeg")
        logger.debug(f"TTS audio uploaded: {s3_key}")
        return s3_key

    def _gtts_tts(self, text: str) -> bytes:
        """Free Google Text-to-Speech fallback."""
        tts = gTTS(text=text, lang="en", slow=False)
        buf = io.BytesIO()
        tts.write_to_fp(buf)
        return buf.getvalue()

    async def _elevenlabs_tts(self, text: str) -> bytes:
        """Premium ElevenLabs TTS."""
        try:
            from elevenlabs.client import AsyncElevenLabs
            client = AsyncElevenLabs(api_key=settings.ELEVENLABS_API_KEY)
            audio_generator = await client.generate(
                text=text,
                voice="Rachel",
                model="eleven_monolingual_v1",
            )
            return b"".join(audio_generator)
        except Exception as e:
            logger.warning(f"ElevenLabs failed ({e}), falling back to gTTS")
            return self._gtts_tts(text)


voice_engine = VoiceEngine()
