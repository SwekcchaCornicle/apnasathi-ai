import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import HTTPException
from auth import google


class GoogleTokenVerificationTests(unittest.TestCase):
    def test_verified_token_is_returned_after_audience_validation(self):
        claims = {"iss": "https://accounts.google.com", "sub": "google-sub-123", "email": "person@example.com", "email_verified": True}
        with patch.dict(os.environ, {"GOOGLE_OAUTH_CLIENT_ID": "web-client-id"}, clear=True):
            with patch.object(google.id_token, "verify_oauth2_token", return_value=claims) as verify:
                self.assertEqual(google.verify_google_id_token("signed.jwt.token"), claims)
        self.assertEqual(verify.call_args.kwargs["audience"], "web-client-id")

    def test_rejects_unverified_email(self):
        claims = {"iss": "https://accounts.google.com", "sub": "google-sub-123", "email": "person@example.com", "email_verified": False}
        with patch.dict(os.environ, {"GOOGLE_OAUTH_CLIENT_ID": "web-client-id"}, clear=True):
            with patch.object(google.id_token, "verify_oauth2_token", return_value=claims):
                with self.assertRaises(HTTPException) as error:
                    google.verify_google_id_token("signed.jwt.token")
        self.assertEqual(error.exception.status_code, 403)

    def test_rejects_wrong_issuer(self):
        claims = {"iss": "https://attacker.example", "sub": "google-sub-123", "email": "person@example.com", "email_verified": True}
        with patch.dict(os.environ, {"GOOGLE_OAUTH_CLIENT_ID": "web-client-id"}, clear=True):
            with patch.object(google.id_token, "verify_oauth2_token", return_value=claims):
                with self.assertRaises(HTTPException) as error:
                    google.verify_google_id_token("signed.jwt.token")
        self.assertEqual(error.exception.status_code, 401)

    def test_missing_client_id_fails_closed(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(HTTPException) as error:
                google.verify_google_id_token("signed.jwt.token")
        self.assertEqual(error.exception.status_code, 503)

    def test_invalid_signature_or_expiry_is_rejected(self):
        with patch.dict(os.environ, {"GOOGLE_OAUTH_CLIENT_ID": "web-client-id"}, clear=True):
            with patch.object(google.id_token, "verify_oauth2_token", side_effect=ValueError("bad signature")):
                with self.assertRaises(HTTPException) as error:
                    google.verify_google_id_token("invalid.jwt.token")
        self.assertEqual(error.exception.status_code, 401)


if __name__ == "__main__":
    unittest.main()
