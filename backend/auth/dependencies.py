"""Authentication dependencies shared by protected API routes."""
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from auth.cognito import verify_cognito_id_token
from database.models import User
from database.session import get_db

bearer_scheme = HTTPBearer(auto_error=False, scheme_name="Cognito ID token")


def verified_claims(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> dict:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Sign in with ApnaSathi to continue.", headers={"WWW-Authenticate": "Bearer"})
    return verify_cognito_id_token(credentials.credentials)


def get_current_user(
    claims: Annotated[dict, Depends(verified_claims)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    user = db.scalar(select(User).where(User.auth_provider == "cognito", User.auth_subject == claims["sub"]))
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="User account is not available. Sign in again.")
    return user
