import base64
import io
import logging
import threading
import wave
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)
VOICE_DIRECTORY = Path(__file__).resolve().parents[1] / "voices"
VOICE_MODELS = {"hi": "hi_IN-priyamvada-medium", "en": "en_US-hfc_female-medium"}
_synthesis_lock = threading.Lock()


@lru_cache(maxsize=len(VOICE_MODELS))
def load_voice(model_path: Path):
    from piper import PiperVoice

    return PiperVoice.load(model_path)


def generate_voice(text: str, language: str) -> dict:
    if not text.strip():
        return {"status": "unavailable", "reason": "empty_response"}

    voice_name = VOICE_MODELS.get(language.strip().lower().split("-", 1)[0])
    if voice_name is None:
        return {"status": "unavailable", "reason": "unsupported_language"}

    model_path = VOICE_DIRECTORY / f"{voice_name}.onnx"
    if not model_path.is_file() or not model_path.with_suffix(".onnx.json").is_file():
        return {"status": "unavailable", "reason": "voice_not_installed"}

    buffer = io.BytesIO()
    try:
        with _synthesis_lock, wave.open(buffer, "wb") as output:
            load_voice(model_path).synthesize_wav(text, output)
    except ImportError:
        return {"status": "unavailable", "reason": "piper_not_installed"}
    except Exception:
        logger.exception("Piper speech generation failed for language %s", language)
        return {"status": "unavailable", "reason": "tts_request_failed"}

    return {
        "status": "ready",
        "mime_type": "audio/wav",
        "encoding": "base64",
        "data": base64.b64encode(buffer.getvalue()).decode("ascii"),
        "disclosure": "AI-generated voice",
    }
