from fastapi import APIRouter, FastAPI, UploadFile, File, HTTPException
import os
from faster_whisper import WhisperModel

from llm_model.llm_model import vertex_model

router = APIRouter(tags=["health"])

UPLOAD_DIR = r"C:\Users\singh\OneDrive\Desktop\apnasathi-ai\audio_files"
os.makedirs(UPLOAD_DIR, exist_ok=True)


model = WhisperModel("base")

@router.post("/upload-audio")
async def upload_audio(audio: UploadFile = File(...)):

    file_path = os.path.join(UPLOAD_DIR, audio.filename)

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

app.include_router(router, prefix="/api/v1")