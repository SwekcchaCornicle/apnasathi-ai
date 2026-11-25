import os
from pathlib import Path
from shutil import copyfileobj
from uuid import uuid4

from fastapi import APIRouter, FastAPI, File, HTTPException, UploadFile
from faster_whisper import WhisperModel

from agents.speech import generate_voice
from llm_model.classify_intent_action import intent_action
from llm_model.llm_model import vertex_model

VOICE_INTENTS = {"GREETING", "GENERAL_QUESTION", "GENERAL_CONVERSATION"}

router = APIRouter(tags=["health"])

UPLOAD_DIR = r"C:\Users\singh\OneDrive\Desktop\apnasathi-ai\audio_files"
os.makedirs(UPLOAD_DIR, exist_ok=True)


model = WhisperModel("base")

@router.post("/upload-audio")
def upload_audio(audio: UploadFile = File(...)):
    extension = Path(audio.filename or "").suffix
    file_path = os.path.join(UPLOAD_DIR, f"{uuid4().hex}{extension}")
    with open(file_path, "wb") as output:
        copyfileobj(audio.file, output)

    segments, _ = model.transcribe(file_path)
    transcription = " ".join(segment.text for segment in segments)
    result = vertex_model(transcription)
    if result is None:
        raise HTTPException(status_code=502, detail="The AI returned no structured response.")

    payload = {**result.model_dump(mode="json"), "text": transcription, "voice": None}
    if result.intent in VOICE_INTENTS:
        action = intent_action(result)
        payload["response"] = action["response"]
        payload["voice"] = generate_voice(action["response"], result.response_language)
    return payload


@router.get("/health")
def health():
    return {"status": "healthy", "service": "ingestion-service"}


app = FastAPI(
    title="Apna Sathi AI",
    version="0.1.0",
    description="use this to operate other app",
)

app.include_router(router, prefix="/api/v1")