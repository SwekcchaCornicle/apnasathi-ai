import os
import re
from dataclasses import asdict
from pathlib import Path
from shutil import copyfileobj
from tempfile import TemporaryDirectory
from uuid import uuid4

from fastapi import APIRouter, FastAPI, File, Form, HTTPException, UploadFile
from faster_whisper import WhisperModel
from pydantic import TypeAdapter, ValidationError

from agents.shoaping import PROMPTS, STORES, ShoppingSession, shopping_message, shopping_reply, start_shopping
from agents.social_media import instagram_router, next_photo_step
from agents.speech import generate_voice
from agents.watch_show.troubleshoot import NEXT_STEP, guide_reply
from llm_model.classify_intent_action import intent_action
from llm_model.llm_model import extract_shopping_items, vertex_model

REPLY_INTENTS = {"GREETING", "GENERAL_QUESTION", "GENERAL_CONVERSATION", "WATCH_SHOW"}

router = APIRouter(tags=["health"])

UPLOAD_DIR = r"C:\Users\singh\OneDrive\Desktop\apnasathi-ai\audio_files"
os.makedirs(UPLOAD_DIR, exist_ok=True)


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


@router.post("/upload-audio")
def upload_audio(
    audio: UploadFile = File(...),
    shopping_session: str | None = Form(None, max_length=16000),
    shopping_language: str = Form("en"),
):
    extension = Path(audio.filename or "").suffix
    file_path = os.path.join(UPLOAD_DIR, f"{uuid4().hex}{extension}")
    with open(file_path, "wb") as output:
        copyfileobj(audio.file, output)

    segments, _ = model.transcribe(file_path)
    transcription = " ".join(segment.text for segment in segments)
    if isinstance(shopping_session, str):
        return handle_shopping_reply(shopping_session, shopping_language, transcription)
    result = vertex_model(transcription)
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


def transcribe_temporary_audio(audio: UploadFile) -> str:
    # Short guide replies and captions go only to Whisper and are removed afterward.
    with TemporaryDirectory() as directory:
        file_path = Path(directory) / "input"
        with file_path.open("wb") as output:
            copyfileobj(audio.file, output)
        segments, _ = model.transcribe(str(file_path))
        return " ".join(segment.text.strip() for segment in segments).strip()


@router.post("/instagram/caption")
def transcribe_instagram_caption(audio: UploadFile = File(...)):
    text = transcribe_temporary_audio(audio)
    if not text:
        raise HTTPException(422, "No caption speech was detected. Try recording it again.")
    return {"text": text}


@router.post("/watch-show/troubleshoot")
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

app.include_router(router, prefix="/api/v1")
app.include_router(instagram_router, prefix="/api/v1")
