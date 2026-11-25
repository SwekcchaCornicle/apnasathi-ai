from fastapi import APIRouter, FastAPI, UploadFile, File, HTTPException
import os

router = APIRouter(tags=["health"])

UPLOAD_DIR = r"C:\audio_files"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.post("/upload-audio")
async def upload_audio(audio: UploadFile = File(...)):
    if not audio.content_type.startswith("audio/"):
        raise HTTPException(
            status_code=400,
            detail="Only audio files are allowed"
        )

    file_path = os.path.join(UPLOAD_DIR, audio.filename)

    with open(file_path, "wb") as f:
        content = await audio.read()
        f.write(content)

    return {
        "message": "Audio uploaded successfully",
        "filename": audio.filename,
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

app.include_router(router, prefix="/api/v1")