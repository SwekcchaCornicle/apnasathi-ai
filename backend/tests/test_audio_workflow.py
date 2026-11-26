import asyncio
import io
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi import HTTPException, UploadFile
from starlette.datastructures import Headers

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
with patch("faster_whisper.WhisperModel"), patch("google.genai.Client"):
    import app

from llm_model.intent_classifier import IntentSchema
from storage.s3_audio_storage import AudioStorageError, S3AudioStorage

WEBM = b"\x1a\x45\xdf\xa3recording"


class AudioWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.client = Mock()
        self.client.get_object.return_value = {"Body": io.BytesIO(WEBM), "ContentLength": len(WEBM)}
        storage_patch = patch.object(app, "get_audio_storage", return_value=S3AudioStorage("private-audio", self.client))
        self.storage = storage_patch.start()
        self.addCleanup(storage_patch.stop)
        model_patch = patch.object(app, "model")
        self.model = model_patch.start()
        self.addCleanup(model_patch.stop)
        self.audio = UploadFile(io.BytesIO(WEBM), filename="../../private.webm", headers=Headers({"content-type": "audio/webm"}))
        self.addCleanup(self.audio.file.close)
        self.transcribed = None

    def transcribe(self, filename):
        self.transcribed = Path(filename)
        def segments():
            self.assertEqual(self.transcribed.read_bytes(), WEBM)
            yield SimpleNamespace(text="Hello")
        return segments(), None

    def test_upload_then_download_and_cleanup_before_intent(self):
        self.model.transcribe.side_effect = self.transcribe

        def classify(text):
            self.assertEqual(text, "Hello")
            self.assertFalse(self.transcribed.parent.exists())
            return IntentSchema(intent="UNKNOWN", response="Reply", response_language="en",
                                confidence=.9, requires_confirmation=False)

        with patch.object(app, "vertex_model", side_effect=classify), patch.object(app, "generate_voice", return_value={}):
            result = app.upload_audio(self.audio)
        self.assertEqual(result["text"], "Hello")
        self.assertEqual(result["response"], "Reply")
        self.assertNotIn("audio_key", result)
        key = self.client.put_object.call_args.kwargs["Key"]
        self.assertNotIn("private.webm", key)
        self.client.get_object.assert_called_once_with(Bucket="private-audio", Key=key)
        self.assertEqual([call[0] for call in self.client.method_calls], ["put_object", "get_object"])

    def test_multipart_contract_and_http_body_limit(self):
        content_type = b"multipart/form-data; boundary=voice"
        body = (
            b"--voice\r\nContent-Disposition: form-data; name=\"audio\"; filename=\"sample.webm\"\r\n"
            b"Content-Type: audio/webm\r\n\r\n" + WEBM + b"\r\n--voice--\r\n"
        )

        async def post(content_length):
            events = []
            async def receive():
                return {"type": "http.request", "body": body, "more_body": False}

            async def send(event):
                events.append(event)

            await app.app({
                "type": "http", "method": "POST", "path": "/api/v1/upload-audio",
                "scheme": "http", "query_string": b"", "headers": [
                    (b"content-type", content_type),
                    (b"content-length", str(content_length).encode()),
                ],
            }, receive, send)
            return events[0]["status"], b"".join(e.get("body", b"") for e in events)

        self.model.transcribe.side_effect = self.transcribe
        intent = IntentSchema(intent="UNKNOWN", response="Reply", response_language="en",
                              confidence=.9, requires_confirmation=False)
        with patch.object(app, "vertex_model", return_value=intent), patch.object(app, "generate_voice", return_value={}):
            status, payload = asyncio.run(post(len(body)))
        self.assertEqual(status, 200, payload)
        self.assertEqual(json.loads(payload)["text"], "Hello")
        status, payload = asyncio.run(post(app.MAX_AUDIO_REQUEST_BYTES + 1))
        self.assertEqual(status, 413, payload)
        self.client.put_object.assert_called_once()

    def test_transcription_failure_cleans_up(self):
        def broken(filename):
            self.transcribed = Path(filename)
            def segments():
                self.assertTrue(self.transcribed.exists())
                raise RuntimeError("private internal data")
                yield
            return segments(), None

        self.model.transcribe.side_effect = broken
        with patch.object(app, "vertex_model") as classify, self.assertRaises(HTTPException) as error:
            app.upload_audio(self.audio)
        self.assertEqual(error.exception.status_code, 503)
        self.assertNotIn("internal", error.exception.detail)
        self.assertFalse(self.transcribed.parent.exists())
        classify.assert_not_called()

    def test_failed_download_cleans_up(self):
        def broken(key, path):
            self.transcribed = path
            path.write_bytes(WEBM[:4])
            raise AudioStorageError(503, "Audio storage temporarily unavailable.")

        self.storage.return_value = Mock(download_audio=broken)
        with self.assertRaises(HTTPException):
            app.upload_audio(self.audio)
        self.assertFalse(self.transcribed.parent.exists())
        self.model.transcribe.assert_not_called()

    def test_caption_stays_temporary_and_does_not_access_s3(self):
        self.model.transcribe.side_effect = self.transcribe
        self.assertEqual(app.transcribe_instagram_caption(self.audio), {"text": "Hello"})
        self.storage.assert_not_called()
        self.assertFalse(self.transcribed.parent.exists())
