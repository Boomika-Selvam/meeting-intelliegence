"""
models/transcriber.py
Speech-to-text transcription using OpenAI Whisper.
Handles audio/video files with chunking for long recordings.
"""

import os
import re
import tempfile
import logging

logger = logging.getLogger(__name__)

# ── Lazy-load Whisper to avoid startup delay ──────────────────────────────────
_whisper_model = None


def _get_whisper_model(model_size: str = "base"):
    """Load Whisper model (cached after first load)."""
    global _whisper_model
    if _whisper_model is None:
        try:
            import whisper
            logger.info(f"[Transcriber] Loading Whisper model: {model_size}")
            _whisper_model = whisper.load_model(model_size)
            logger.info("[Transcriber] Whisper model loaded.")
        except ImportError:
            raise RuntimeError("openai-whisper is not installed. Run: pip install openai-whisper")
    return _whisper_model


def extract_audio(input_path: str) -> str:
    """
    Extract audio from video file or return audio path directly.
    Uses ffmpeg to convert to WAV format for Whisper.
    Returns path to a temporary WAV file.
    """
    import ffmpeg

    _, ext = os.path.splitext(input_path.lower())
    video_extensions = {".mp4", ".avi", ".mov", ".mkv", ".webm", ".flv"}

    # Create a temporary WAV file
    tmp_wav = tempfile.mktemp(suffix=".wav")

    if ext in video_extensions:
        logger.info(f"[Transcriber] Extracting audio from video: {input_path}")
        (
            ffmpeg
            .input(input_path)
            .output(tmp_wav, acodec="pcm_s16le", ac=1, ar="16000")
            .overwrite_output()
            .run(quiet=True)
        )
    else:
        # Audio file — convert to 16kHz mono WAV for Whisper
        logger.info(f"[Transcriber] Converting audio to WAV: {input_path}")
        (
            ffmpeg
            .input(input_path)
            .output(tmp_wav, acodec="pcm_s16le", ac=1, ar="16000")
            .overwrite_output()
            .run(quiet=True)
        )

    return tmp_wav


def clean_transcript(text: str) -> str:
    """
    Clean raw transcript text:
    - Remove filler words (um, uh, hmm, etc.)
    - Collapse extra whitespace
    - Fix sentence spacing
    """
    # Remove common filler words (case-insensitive, whole words)
    fillers = r'\b(um+|uh+|hmm+|uhh+|err+|ah+|like uh|you know|i mean|sort of|kind of)\b'
    text = re.sub(fillers, '', text, flags=re.IGNORECASE)

    # Collapse multiple spaces
    text = re.sub(r' {2,}', ' ', text)

    # Fix spacing after punctuation
    text = re.sub(r'\s+([.,!?;:])', r'\1', text)

    # Remove leading/trailing whitespace per line
    lines = [line.strip() for line in text.splitlines()]
    text = ' '.join(line for line in lines if line)

    return text.strip()


def transcribe(file_path: str, model_size: str = "base") -> str:
    """
    Full transcription pipeline:
    1. Extract/convert audio
    2. Run Whisper transcription
    3. Clean the transcript
    4. Return cleaned text

    Args:
        file_path: Path to audio or video file
        model_size: Whisper model size ('tiny', 'base', 'small', 'medium', 'large')
                    Use 'base' for speed; 'small' or 'medium' for better accuracy.
    Returns:
        Cleaned transcript string
    """
    tmp_wav = None
    try:
        # Step 1: Convert to WAV
        tmp_wav = extract_audio(file_path)

        # Step 2: Load model and transcribe
        model = _get_whisper_model(model_size)
        logger.info("[Transcriber] Starting transcription...")

        result = model.transcribe(
            tmp_wav,
            language=None,          # Auto-detect language
            verbose=False,
            condition_on_previous_text=True,
            fp16=False              # CPU-safe; set True if CUDA available
        )

        raw_transcript = result.get("text", "").strip()
        logger.info(f"[Transcriber] Raw transcript length: {len(raw_transcript)} chars")

        # Step 3: Clean
        cleaned = clean_transcript(raw_transcript)
        logger.info("[Transcriber] Transcription complete.")
        return cleaned

    except Exception as e:
        logger.error(f"[Transcriber] Error during transcription: {e}")
        raise

    finally:
        # Clean up temporary WAV file
        if tmp_wav and os.path.exists(tmp_wav):
            os.remove(tmp_wav)
