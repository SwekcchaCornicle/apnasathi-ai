"""Private S3 storage for the recordings submitted to the voice API."""

import os
import re
from contextlib import closing
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import BinaryIO
from uuid import uuid4

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

MAX_AUDIO_BYTES = 25 * 1024 * 1024
MAX_AUDIO_REQUEST_BYTES = MAX_AUDIO_BYTES + 64 * 1024
AUDIO_PREFIX = "audio/"
_OBJECT_KEY = re.compile(r"audio/anonymous/\d{4}/(?:0[1-9]|1[0-2])/[0-9a-f]{32}\.(?:webm|ogg|m4a|wav|mp3|flac)")
_FORMATS = {
    "audio/webm": ("webm", "audio/webm"),
    "video/webm": ("webm", "video/webm"),
    "audio/ogg": ("ogg", "audio/ogg"),
    "application/ogg": ("ogg", "audio/ogg"),
    "audio/mp4": ("m4a", "audio/mp4"),
    "audio/x-m4a": ("m4a", "audio/mp4"),
    "video/mp4": ("m4a", "video/mp4"),
    "audio/wav": ("wav", "audio/wav"),
    "audio/x-wav": ("wav", "audio/wav"),
    "audio/mpeg": ("mp3", "audio/mpeg"),
    "audio/mp3": ("mp3", "audio/mpeg"),
    "audio/flac": ("flac", "audio/flac"),
    "audio/x-flac": ("flac", "audio/flac"),
}


class AudioStorageError(Exception):
    """A safe message and an HTTP status for an upload or storage failure."""

    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


def validate_audio(file: BinaryIO, content_type: str | None) -> tuple[int, str, str]:
    file.seek(0, os.SEEK_END)
    size = file.tell()
    file.seek(0)
    if not size:
        raise AudioStorageError(400, "The audio file is empty.")
    if size > MAX_AUDIO_BYTES:
        raise AudioStorageError(413, "Audio recordings must be 25 MiB or smaller.")

    media_type = (content_type or "").split(";", 1)[0].strip().lower()
    if media_type not in _FORMATS:
        raise AudioStorageError(415, "Unsupported audio type. Use WebM, Ogg, MP4, WAV, MP3, or FLAC.")

    extension, normalized_type = _FORMATS[media_type]
    header = file.read(16)
    file.seek(0)
    matches = {
        "webm": header.startswith(b"\x1a\x45\xdf\xa3"),
        "ogg": header.startswith(b"OggS"),
        "m4a": header[4:8] == b"ftyp",
        "wav": header[:4] in {b"RIFF", b"RF64", b"RIFX"} and header[8:12] == b"WAVE",
        "mp3": header.startswith(b"ID3") or (
            len(header) >= 2 and header[0] == 0xFF and header[1] & 0xE0 == 0xE0
        ),
        "flac": header.startswith(b"fLaC"),
    }
    if not matches[extension]:
        raise AudioStorageError(415, "The audio file does not match its declared type.")
    return size, extension, normalized_type


def _storage_error(error: Exception, operation: str) -> AudioStorageError:
    if isinstance(error, ClientError):
        code = error.response.get("Error", {}).get("Code")
        if operation == "download" and code in {"NoSuchKey", "NotFound", "404"}:
            return AudioStorageError(404, "The stored recording could not be found.")
    # AWS details may include bucket names, keys, or account information.
    return AudioStorageError(503, f"Audio storage is unavailable during {operation}. Try again later.")


class S3AudioStorage:
    def __init__(self, bucket: str, client):
        self.bucket = bucket
        self.client = client

    def upload_audio(self, file: BinaryIO, content_type: str | None) -> str:
        size, extension, normalized_type = validate_audio(file, content_type)
        month = datetime.now(timezone.utc).strftime("%Y/%m")
        # The app has no authenticated user ID. Do not trust a client-provided identity.
        key = f"{AUDIO_PREFIX}anonymous/{month}/{uuid4().hex}.{extension}"
        try:
            self.client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=file,
                ContentLength=size,
                ContentType=normalized_type,
                ServerSideEncryption="AES256",
                Metadata={"purpose": "voice-recording"},
            )
        except (ClientError, BotoCoreError, OSError) as error:
            raise _storage_error(error, "upload") from None
        return key

    def download_audio(self, key: str, destination: Path) -> None:
        if not _OBJECT_KEY.fullmatch(key):
            raise AudioStorageError(400, "Invalid audio object identifier.")
        try:
            result = self.client.get_object(Bucket=self.bucket, Key=key)
            with closing(result["Body"]) as body:
                size = result["ContentLength"]
                if not 0 < size <= MAX_AUDIO_BYTES:
                    raise AudioStorageError(503, "The stored recording has an unexpected size.")
                with destination.open("xb") as output:
                    remaining = size
                    while remaining:
                        chunk = body.read(min(remaining, 1024 * 1024))
                        if not chunk:
                            raise AudioStorageError(503, "The stored recording was incomplete.")
                        output.write(chunk)
                        remaining -= len(chunk)
        except (ClientError, BotoCoreError, OSError) as error:
            raise _storage_error(error, "download") from None


@lru_cache(maxsize=1)
def get_audio_storage() -> S3AudioStorage:
    bucket = os.getenv("AUDIO_S3_BUCKET", "").strip()
    if not bucket:
        raise AudioStorageError(503, "Audio storage is not configured.")
    try:
        client = boto3.client(
            "s3",
            region_name=os.getenv("AWS_REGION") or None,
            config=Config(connect_timeout=5, read_timeout=20, retries={"mode": "standard", "total_max_attempts": 3}),
        )
    except BotoCoreError:
        raise AudioStorageError(503, "Audio storage credentials or configuration are unavailable.") from None
    return S3AudioStorage(bucket, client)
