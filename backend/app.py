from fastapi import APIRouter, FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import os
from pathlib import Path
from uuid import uuid4

router = APIRouter(tags=["health"])

UPLOAD_DIR = r"C:\audio_files"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.post("/upload-audio")
async def upload_audio(audio: UploadFile = File(...)):
    if not (audio.content_type or "").startswith("audio/"):
        raise HTTPException(
            status_code=400,
            detail="Only audio files are allowed"
        )

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
        content = await audio.read()
        f.write(content)

    return {
        "message": "Audio uploaded successfully",
        "filename": filename,
        "content_type": audio.content_type,
        "saved_path": file_path,
    }


@router.get("/health")
def health():
    return {"status": "healthy", "service": "ingestion-service"}


app = FastAPI(
    title="Apna Sathi AI",
    version="0.1.0",
    description="use this to operate other apps",
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
