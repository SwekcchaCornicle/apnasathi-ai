"""Google sign-in and authenticated user profile endpoints."""
from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from auth.dependencies import get_current_user
from auth.google import verify_google_id_token
from database.models import User, UserProfile
from database.session import get_db

router = APIRouter(tags=["authentication"])


class GoogleSignInRequest(BaseModel):
    id_token: str = Field(min_length=20, max_length=12000)


class UserProfileUpdate(BaseModel):
    display_name: str | None = Field(default=None, max_length=120)
    preferred_language: str | None = Field(default=None, min_length=2, max_length=16)
    timezone: str | None = Field(default=None, min_length=1, max_length=64)
    preferences: dict = Field(default_factory=dict)


class UserResponse(BaseModel):
    id: UUID
    email: str | None
    email_verified: bool
    display_name: str | None = None
    preferred_language: str = "en"
    timezone: str = "Asia/Kolkata"
    preferences: dict = Field(default_factory=dict)

    model_config = ConfigDict(from_attributes=True)


def _user_response(user: User, profile: UserProfile | None) -> UserResponse:
    return UserResponse(
        id=user.id,
        email=user.email,
        email_verified=user.email_verified,
        display_name=profile.display_name if profile else None,
        preferred_language=profile.preferred_language if profile else "en",
        timezone=profile.timezone if profile else "Asia/Kolkata",
        preferences=profile.preferences if profile else {},
    )


@router.post("/auth/google", response_model=UserResponse)
def google_sign_in(payload: GoogleSignInRequest, db: Annotated[Session, Depends(get_db)]):
    """Exchange a verified Google ID token for a persisted ApnaSathi account."""
    claims = verify_google_id_token(payload.id_token)
    now = datetime.now(timezone.utc)
    statement = insert(User).values(
        auth_provider="google",
        auth_subject=claims["sub"],
        email=claims["email"],
        email_verified=True,
        is_active=True,
        last_seen_at=now,
    ).on_conflict_do_update(
        constraint="uq_users_provider_subject",
        set_={"email": claims["email"], "email_verified": True, "last_seen_at": now},
    ).returning(User)
    user = db.scalar(statement)
    if user is None:
        raise HTTPException(status_code=500, detail="Could not create the user account.")

    profile = db.scalar(select(UserProfile).where(UserProfile.user_id == user.id))
    if profile is None:
        profile = UserProfile(user_id=user.id)
        db.add(profile)
    if claims.get("name") and not profile.display_name:
        profile.display_name = claims["name"][:120]
    db.flush()
    return _user_response(user, profile)


@router.get("/users/me", response_model=UserResponse)
def read_current_user(user: Annotated[User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)]):
    profile = db.scalar(select(UserProfile).where(UserProfile.user_id == user.id))
    return _user_response(user, profile)


@router.patch("/users/me/profile", response_model=UserResponse)
def update_current_profile(
    payload: UserProfileUpdate,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    profile = db.scalar(select(UserProfile).where(UserProfile.user_id == user.id))
    if profile is None:
        profile = UserProfile(user_id=user.id)
        db.add(profile)
    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(profile, field, value)
    db.flush()
    return _user_response(user, profile)
