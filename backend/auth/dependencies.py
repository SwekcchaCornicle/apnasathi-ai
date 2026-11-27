"""Authentication dependencies shared by protected API routes."""
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from auth.google import verify_google_id_token
from database.models import User
from database.session import get_db

bearer_scheme = HTTPBearer(auto_error=False, scheme_name="Google ID token")


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Sign in with Google to continue.", headers={"WWW-Authenticate": "Bearer"})
    claims = verify_google_id_token(credentials.credentials)
    user = db.scalar(select(User).where(User.auth_provider == "google", User.auth_subject == claims["sub"]))
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="User account is not available. Sign in again.")
    return user
