"""Verify Amazon Cognito User Pool ID tokens."""
import logging
import os
from functools import lru_cache
from typing import Any

import jwt
from fastapi import HTTPException
from jwt import PyJWKClient

logger = logging.getLogger(__name__)

AWS_REGION = os.getenv("COGNITO_REGION", "ap-south-1")
USER_POOL_ID = os.getenv("COGNITO_USER_POOL_ID", "ap-south-1_qxfax5y4B")
APP_CLIENT_ID = os.getenv("COGNITO_CLIENT_ID", "").strip()
ISSUER = f"https://cognito-idp.{AWS_REGION}.amazonaws.com/{USER_POOL_ID}"
JWKS_URL = f"{ISSUER}/.well-known/jwks.json"
CLOCK_SKEW_SECONDS = 5

@lru_cache(maxsize=1)
def _jwks_client() -> PyJWKClient:
    return PyJWKClient(JWKS_URL, cache_keys=True, lifespan=3600)

def verify_cognito_id_token(encoded_token: str) -> dict[str, Any]:
    if not APP_CLIENT_ID:
        raise HTTPException(status_code=503, detail="Amazon Cognito authentication is not configured.")
    if not encoded_token or len(encoded_token) > 16000:
        raise HTTPException(status_code=401, detail="Invalid Cognito ID token.")
    try:
        signing_key = _jwks_client().get_signing_key_from_jwt(encoded_token)
        claims = jwt.decode(
            encoded_token,
            signing_key.key,
            algorithms=["RS256"],
            audience=APP_CLIENT_ID,
            issuer=ISSUER,
            leeway=CLOCK_SKEW_SECONDS,
            options={"require": ["exp", "iat", "sub", "iss", "aud"]},
        )
    except jwt.PyJWKClientConnectionError:
        logger.warning("Cognito signing key endpoint could not be reached.")
        raise HTTPException(status_code=503, detail="Cognito verification is temporarily unavailable.") from None
    except jwt.PyJWTError as error:
        logger.warning("Cognito token validation rejected the request (%s).", type(error).__name__)
        raise HTTPException(status_code=401, detail="Cognito sign-in token is invalid or expired.") from None
    if claims.get("token_use") != "id" or not claims.get("sub"):
        raise HTTPException(status_code=401, detail="A valid Cognito ID token is required.")
    if not claims.get("email"):
        raise HTTPException(status_code=403, detail="A verified email address is required.")
    if claims.get("email_verified") not in (True, "true"):
        raise HTTPException(status_code=403, detail="Please verify your email address first.")
    return claims
