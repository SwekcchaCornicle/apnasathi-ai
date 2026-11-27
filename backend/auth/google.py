"""Verification of Google OpenID Connect ID tokens."""
import os
from typing import Any

from fastapi import HTTPException
from google.auth.exceptions import GoogleAuthError
from google.auth.transport.requests import Request
from google.oauth2 import id_token

GOOGLE_ISSUERS = {"accounts.google.com", "https://accounts.google.com"}


def verify_google_id_token(encoded_token: str) -> dict[str, Any]:
    """Verify signature, expiry, issuer and configured audience with Google's library."""
    audience = os.getenv("GOOGLE_OAUTH_CLIENT_ID", "").strip()
    if not audience:
        raise HTTPException(status_code=503, detail="Google sign-in is not configured.")
    if not encoded_token or len(encoded_token) > 12000:
        raise HTTPException(status_code=401, detail="Invalid Google ID token.")
    try:
        claims = id_token.verify_oauth2_token(encoded_token, Request(), audience=audience)
    except (ValueError, GoogleAuthError):
        raise HTTPException(status_code=401, detail="Google sign-in token is invalid or expired.") from None
    if claims.get("iss") not in GOOGLE_ISSUERS:
        raise HTTPException(status_code=401, detail="Google sign-in token has an invalid issuer.")
    if not claims.get("sub"):
        raise HTTPException(status_code=401, detail="Google sign-in token is missing its account identifier.")
    email = claims.get("email")
    verified = claims.get("email_verified") is True or claims.get("email_verified") == "true"
    if not email or not verified:
        raise HTTPException(status_code=403, detail="A verified Google email address is required.")
    return claims
