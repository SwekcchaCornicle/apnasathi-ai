import io
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from botocore.exceptions import ClientError, NoCredentialsError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from storage.s3_audio_storage import AudioStorageError, S3AudioStorage, get_audio_storage

WEBM = b"\x1a\x45\xdf\xa3recording"


class S3AudioStorageTests(unittest.TestCase):
    def setUp(self):
        self.client = Mock()
        self.storage = S3AudioStorage("private-audio", self.client)

    def test_upload_generates_unique_keys_and_safe_metadata(self):
        key = self.storage.upload_audio(io.BytesIO(WEBM), "video/webm;codecs=opus")
        another = self.storage.upload_audio(io.BytesIO(WEBM), "audio/webm")
        self.assertRegex(key, r"^audio/anonymous/\d{4}/\d{2}/[0-9a-f]{32}\.webm$")
        self.assertNotEqual(key, another)
        args = self.client.put_object.call_args_list[0].kwargs
        self.assertEqual(args["ContentType"], "video/webm")
        self.assertEqual(args["ContentLength"], len(WEBM))
        self.assertEqual(args["ServerSideEncryption"], "AES256")
        self.assertNotIn("ACL", args)

    def test_invalid_uploads_never_reach_s3(self):
        for data, mime, expected in [
            (b"", "audio/webm", 400),
            (WEBM, "image/jpeg", 415),
            (b"html", "audio/webm", 415),
        ]:
            with self.subTest(mime=mime, status=expected), self.assertRaises(AudioStorageError) as error:
                self.storage.upload_audio(io.BytesIO(data), mime)
            self.assertEqual(error.exception.status, expected)
        with patch("storage.s3_audio_storage.MAX_AUDIO_BYTES", 4), self.assertRaises(AudioStorageError) as error:
            self.storage.upload_audio(io.BytesIO(WEBM), "audio/webm")
        self.assertEqual(error.exception.status, 413)
        self.client.put_object.assert_not_called()

    def test_upload_errors_are_safe(self):
        for failure in [NoCredentialsError(), ClientError({"Error": {
            "Code": "AccessDenied", "Message": "private bucket identifier",
        }}, "PutObject")]:
            with self.subTest(failure=type(failure)), self.assertRaises(AudioStorageError) as error:
                self.client.put_object.side_effect = failure
                self.storage.upload_audio(io.BytesIO(WEBM), "audio/webm")
            self.assertEqual(error.exception.status, 503)
            self.assertNotIn("private bucket identifier", str(error.exception))

    def test_download_and_key_validation(self):
        key = self.storage.upload_audio(io.BytesIO(WEBM), "audio/webm")
        body = io.BytesIO(WEBM)
        self.client.get_object.return_value = {"Body": body, "ContentLength": len(WEBM)}
        with TemporaryDirectory() as directory:
            file = Path(directory) / "recording"
            self.storage.download_audio(key, file)
            self.assertEqual(file.read_bytes(), WEBM)
            self.assertTrue(body.closed)
            with self.assertRaises(AudioStorageError):
                self.storage.download_audio("audio/../outside", file)
        self.client.get_object.assert_called_once_with(Bucket="private-audio", Key=key)

    def test_missing_object_is_safe(self):
        key = self.storage.upload_audio(io.BytesIO(WEBM), "audio/webm")
        self.client.get_object.side_effect = ClientError(
            {"Error": {"Code": "NoSuchKey", "Message": "sensitive key"}}, "GetObject"
        )
        with self.assertRaises(AudioStorageError) as error:
            self.storage.download_audio(key, Path("unused"))
        self.assertEqual(error.exception.status, 404)
        self.assertNotIn("sensitive key", str(error.exception))

    def test_missing_bucket_and_cached_client(self):
        get_audio_storage.cache_clear()
        self.addCleanup(get_audio_storage.cache_clear)
        with patch.dict("os.environ", {"AUDIO_S3_BUCKET": ""}):
            with self.assertRaises(AudioStorageError) as error:
                get_audio_storage()
        self.assertEqual(error.exception.status, 503)
        with patch.dict("os.environ", {"AUDIO_S3_BUCKET": "private-audio"}):
            with patch("storage.s3_audio_storage.boto3.client") as factory:
                self.assertIs(get_audio_storage(), get_audio_storage())
                factory.assert_called_once()
                self.assertEqual(factory.call_args.args, ("s3",))
