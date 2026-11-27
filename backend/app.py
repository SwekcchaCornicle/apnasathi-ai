import logging
import re
from dataclasses import asdict
from pathlib import Path
from shutil import copyfileobj
from tempfile import TemporaryDirectory

from av.error import FFmpegError
from fastapi import APIRouter, FastAPI, File, Form, HTTPException, UploadFile
from faster_whisper import WhisperModel
from pydantic import TypeAdapter, ValidationError

from api.auth import router as auth_router
from agents.shoaping import PROMPTS, STORES, ShoppingSession, shopping_message, shopping_reply, start_shopping
from agents.social_media import instagram_router, next_photo_step
from agents.speech import generate_voice
from agents.watch_show.troubleshoot import NEXT_STEP, guide_reply
from llm_model.classify_intent_action import intent_action
from llm_model.llm_model import VertexUnavailable, extract_shopping_items, vertex_model
from storage.s3_audio_storage import (
    AudioStorageError,
    MAX_AUDIO_REQUEST_BYTES,
    get_audio_storage,
    validate_audio,
)

REPLY_INTENTS = {"GREETING", "GENERAL_QUESTION", "GENERAL_CONVERSATION", "WATCH_SHOW"}

router = APIRouter(tags=["health"])

logger = logging.getLogger(__name__)

model = WhisperModel("base")

SHOPPING_SESSION = TypeAdapter(ShoppingSession)
SHOPPING_REQUEST = re.compile(
    r"\b(?:want|would like|need) to (?:buy|shop|order)\b|"
    r"\b(?:open|use) (?:blinkit|amazon|swiggy(?: instamart)?)\b", re.IGNORECASE
)


def shopping_payload(session: ShoppingSession, language: str, *, launch: bool = False):
    message = shopping_message(session)
    return {
        **message,
        "shopping": {**message, "session": asdict(session), "language": language, "launch": launch},
        "voice": generate_voice(message["response"], "en"),
    }


@router.post("/shopping/reply")
def handle_shopping_reply(
    session: str = Form(..., max_length=16000),
    language: str = Form("en"),
    answer: str = Form(..., max_length=4000),
):
    try:
        previous = SHOPPING_SESSION.validate_json(session)
    except ValidationError:
        raise HTTPException(400, "Invalid shopping session.") from None
    if (previous.step not in PROMPTS
        or (previous.step not in {"store", "done"} and previous.store not in STORES)
        or (previous.step == "item" and not 0 <= previous.item_index < len(previous.items))):
        raise HTTPException(400, "Invalid shopping step.")
    current = shopping_reply(previous, answer, extract_items=extract_shopping_items)
    return {
        **shopping_payload(current, language, launch=previous.step == "store" and current.step == "login"),
        "text": answer,
    }


@router.post("/upload-audio", max_body_size=MAX_AUDIO_REQUEST_BYTES)
def upload_audio(
    audio: UploadFile = File(...),
    shopping_session: str | None = Form(None, max_length=16000),
    shopping_language: str = Form("en"),
):
    try:
        storage = get_audio_storage()
        key = storage.upload_audio(audio.file, audio.content_type)
        with TemporaryDirectory(prefix="apnasathi-audio-") as directory:
            file_path = Path(directory) / "recording"
            storage.download_audio(key, file_path)
            transcription = transcribe_audio(file_path)
    except AudioStorageError as error:
        raise HTTPException(error.status, str(error)) from None

    if isinstance(shopping_session, str):
        return handle_shopping_reply(shopping_session, shopping_language, transcription)
    try:
        result = vertex_model(transcription)
    except VertexUnavailable as error:
        raise HTTPException(503, str(error)) from None
    if result is None:
        raise HTTPException(status_code=502, detail="The AI returned no structured response.")

    payload = {**result.model_dump(mode="json"), "text": transcription, "voice": None}
    is_shopping = result.intent == "ORDER_GROCERIES" or (
        result.intent in {"GENERAL_QUESTION", "GENERAL_CONVERSATION", "GREETING", "OPEN_APP", "UNKNOWN"}
        and SHOPPING_REQUEST.search(transcription)
    )
    if is_shopping:
        session = start_shopping(result.application or "", result.shopping_items)
        if session.store is None:
            session = start_shopping(transcription, result.shopping_items)
        payload.update(shopping_payload(session, result.response_language, launch=session.step == "login"))
        payload["intent"] = "ORDER_GROCERIES"
        payload["application"] = session.store
        return payload
    if result.intent in REPLY_INTENTS:
        action = intent_action(result)
        payload["response"] = action["response"]
        payload["voice"] = action.get("voice")
        if result.intent == "WATCH_SHOW":
            payload.update({key: action[key] for key in ("playback_status", "playback_url", "playback_platform", "response_language")})
    if result.intent == "POST_PHOTO":
        payload.update(next_photo_step("/api/v1/instagram/photo"))
    if payload["voice"] is None:
        payload["voice"] = generate_voice(payload["response"], result.response_language)
    return payload


def transcribe_audio(file_path: Path, *, strip: bool = False) -> str:
    try:
        segments, _ = model.transcribe(str(file_path))
        # Whisper's segments are lazy, so decoding must finish before the temp file closes.
        text = " ".join(segment.text.strip() if strip else segment.text for segment in segments)
    except FFmpegError:
        raise HTTPException(422, "The recording could not be decoded as audio.") from None
    except Exception:
        logger.warning("Whisper transcription failed.")
        raise HTTPException(503, "Transcription is temporarily unavailable.") from None
    return text.strip() if strip else text


def transcribe_temporary_audio(audio: UploadFile) -> str:
    # Guide replies and captions are transient and never become stored recordings.
    try:
        validate_audio(audio.file, audio.content_type)
    except AudioStorageError as error:
        raise HTTPException(error.status, str(error)) from None
    with TemporaryDirectory(prefix="apnasathi-reply-") as directory:
        file_path = Path(directory) / "input"
        with file_path.open("wb") as output:
            copyfileobj(audio.file, output)
        return transcribe_audio(file_path, strip=True)


@router.post("/instagram/caption", max_body_size=MAX_AUDIO_REQUEST_BYTES)
def transcribe_instagram_caption(audio: UploadFile = File(...)):
    text = transcribe_temporary_audio(audio)
    if not text:
        raise HTTPException(422, "No caption speech was detected. Try recording it again.")
    return {"text": text}


@router.post("/watch-show/troubleshoot", max_body_size=MAX_AUDIO_REQUEST_BYTES)
def troubleshoot_watch_show(
    step: str = Form(...),
    language: str = Form("en"),
    platform: str = Form("the streaming service", min_length=1, max_length=80),
    audio: UploadFile | None = File(None),
):
    if audio is None:
        if step not in {"opened", "playing", "tab"}:
            raise HTTPException(status_code=400, detail="Choose a valid initial guide step.")
        return guide_reply(step, language, platform=platform)
    if step not in NEXT_STEP:
        raise HTTPException(status_code=400, detail="Choose an active guide step.")

    transcript = transcribe_temporary_audio(audio)
    return {**guide_reply(step, language, transcript, platform=platform), "text": transcript}


@router.get("/health")
def health():
    return {"status": "healthy", "service": "ingestion-service"}


app = FastAPI(
    title="Apna Sathi AI",
    version="0.1.0",
    description="use this to operate other app",
)

app.include_router(auth_router, prefix="/api/v1")
app.include_router(router, prefix="/api/v1")
app.include_router(instagram_router, prefix="/api/v1")
