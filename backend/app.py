from fastapi import APIRouter, FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import os
from faster_whisper import WhisperModel

from llm_model.llm_model import vertex_model

router = APIRouter(tags=["health"])

UPLOAD_DIR = r"C:\Users\singh\OneDrive\Desktop\apnasathi-ai\audio_files"
os.makedirs(UPLOAD_DIR, exist_ok=True)


model = WhisperModel("base")

@router.post("/upload-audio")
async def upload_audio(audio: UploadFile = File(...)):

    extension_by_type = {
        "audio/webm": ".webm",
        "audio/ogg": ".ogg",
        "audio/mp4": ".m4a",
        "audio/wav": ".wav",
        "audio/mpeg": ".mp3",
    }
    media_type = audio.content_type.split(";", 1)[0].lower()
    extension = extension_by_type.get(media_type, Path(audio.filename or "recording.webm").suffix or ".audio")
    filename = f"{uuid4().hex}{extension}"
    file_path = os.path.join(UPLOAD_DIR, filename)

    with open(file_path, "wb") as f:
        f.write(await audio.read())

    # Convert speech to text
    segments, info = model.transcribe(file_path)

    transcription = " ".join(
        segment.text for segment in segments
    )
    vertex_model(transcription)

    return {
        "text": transcription
    }


@router.get("/health")
def health():
    return {"status": "healthy", "service": "ingestion-service"}


app = FastAPI(
    title="Apna Sathi AI",
    version="0.1.0",
    description="use this to operate other app",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:5180",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:5180",
        "http://192.168.1.4:5173",
        "http://192.168.1.4:5174",
        "http://192.168.1.4:5180",
    ],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1")
