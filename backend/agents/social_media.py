"""Instagram photo posting helpers for a server-owned chat draft.

The caller owns uploads, OAuth callback routing, and per-user token storage.
Store OAuth state with the signed-in user's draft and consume it once at callback.
"""

from dataclasses import dataclass, field
from secrets import token_urlsafe
from urllib.parse import urlencode, urlsplit

import requests

GRAPH = "https://graph.facebook.com"
META_APP_ID = "1176321671633524"
META_CONFIG_ID = "1439662974983454"
META_CALLBACK = "https://d03k1owznd.execute-api.ap-south-1.amazonaws.com/"


class InstagramError(RuntimeError):
    """A safe error message that leaves credentials out of chat and logs."""


@dataclass(frozen=True)
class InstagramCredentials:
    user_id: str
    access_token: str = field(repr=False)


def _request(operation, method, url, **kwargs):
    try:
        response = requests.request(method, url, timeout=20, allow_redirects=False, **kwargs)
        if not 200 <= response.status_code < 300:
            raise InstagramError(f"Instagram {operation} failed (HTTP {response.status_code}).")
        result = response.json()
    except (requests.RequestException, ValueError):
        raise InstagramError(f"Instagram {operation} returned no usable response.") from None
    if not isinstance(result, dict) or result.get("error"):
        raise InstagramError(f"Instagram {operation} returned an error.")
    return result


@dataclass(frozen=True)
class InstagramAgent:
    app_id: str
    app_secret: str = field(repr=False)
    redirect_uri: str
    api_version: str

    def begin_authorization(self) -> tuple[str, str]:
        state = token_urlsafe(32)
        query = urlencode({
            "client_id": self.app_id,
            "config_id": META_CONFIG_ID,
            "display": "popup",
            "override_default_response_type": "true",
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "state": state,
            "prompt": "login",
        })
        return f"https://www.facebook.com/dialog/oauth?{query}", state

    def exchange_code(self, code: str) -> InstagramCredentials:
        if not code:
            raise InstagramError("Instagram authorization was cancelled.")
        token = _request(
            "code exchange", "GET", f"{GRAPH}/{self.api_version}/oauth/access_token",
            params={
                "client_id": self.app_id, "client_secret": self.app_secret,
                "redirect_uri": self.redirect_uri, "code": code,
            },
        ).get("access_token")
        if not token:
            raise InstagramError("Meta did not return an access token.")
        accounts = _request(
            "account lookup", "GET", f"{GRAPH}/{self.api_version}/me/accounts",
            headers={"Authorization": f"Bearer {token}"},
            params={"fields": "instagram_business_account", "limit": 100},
        )
        linked = {
            str(page["instagram_business_account"]["id"])
            for page in accounts.get("data", [])
            if page.get("instagram_business_account", {}).get("id")
        }
        if len(linked) != 1 or accounts.get("paging", {}).get("next"):
            raise InstagramError("Authorize exactly one Facebook Page linked to a professional Instagram account.")
        return InstagramCredentials(linked.pop(), token)

    def _media_request(self, credentials, edge, data) -> str:
        if not credentials.user_id.isascii() or not credentials.user_id.isdecimal():
            raise InstagramError("Invalid Instagram account ID.")
        result = _request(
            edge, "POST", f"{GRAPH}/{self.api_version}/{credentials.user_id}/{edge}",
            headers={"Authorization": f"Bearer {credentials.access_token}"},
            data=data,
        )
        if not result.get("id"):
            raise InstagramError(f"Instagram did not return an ID for {edge}.")
        return str(result["id"])

    def create_photo(self, credentials: InstagramCredentials, image_url: str, caption: str) -> str:
        """Create a container using a temporary public HTTPS URL for the uploaded JPEG."""
        image = urlsplit(image_url)
        if image.scheme != "https" or not image.hostname or image.username is not None:
            raise InstagramError("Instagram needs an HTTPS image URL from the upload service.")
        return self._media_request(credentials, "media", {"image_url": image_url, "caption": caption})

    def publish_photo(self, credentials: InstagramCredentials, container_id: str) -> str:
        """Publish the prepared container once the user submits the caption to post."""
        return self._media_request(credentials, "media_publish", {"creation_id": container_id})


def next_photo_step(upload_url: str, *, image_uploaded: bool = False,
                    authorization_url: str | None = None, connected: bool = False) -> dict:
    """Build the next chat message from the server-owned draft state."""
    if not image_uploaded:
        return {"step": "image", "response": "Attach the photo you want to post.",
                "action": {"label": "Attach photo", "url": upload_url}}
    if not connected:
        if not authorization_url:
            raise InstagramError("Instagram authorization must be initialized for this draft.")
        return {"step": "authorization", "response": "Connect Instagram to continue.",
                "action": {"label": "Connect Instagram", "url": authorization_url}}
    return {"step": "caption", "response": "What caption should I post with this photo?"}

import os
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import PlainTextResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from auth.dependencies import get_current_user
from database.models import User
from database.session import get_db

instagram_router = APIRouter(prefix="/instagram", tags=["instagram"])
COOKIE = "apnasathi_instagram_draft"
DRAFT_SECONDS = 30 * 60
MAX_IMAGE_BYTES = 8 * 1024 * 1024
CurrentUser = Annotated[User, Depends(get_current_user)]
Database = Annotated[Session, Depends(get_db)]


def _configured_agent():
    secret = os.getenv("INSTAGRAM_APP_SECRET")
    version = os.getenv("INSTAGRAM_API_VERSION")
    origin = os.getenv("INSTAGRAM_IMAGE_ORIGIN", "").rstrip("/")
    parsed = urlsplit(origin)
    if not secret or not version or parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.path or parsed.query or parsed.fragment:
        raise HTTPException(503, "Instagram publishing is unavailable until the app owner finishes the Meta setup.")
    return InstagramAgent(META_APP_ID, secret, META_CALLBACK, version), origin


def _digest(value):
    return sha256(value.encode()).hexdigest()


@instagram_router.post("/photo", max_body_size=MAX_IMAGE_BYTES + 65536)
def attach_photo(
    response: Response, user: CurrentUser, db: Database, image: UploadFile = File(...),
    caption: str = Form("", max_length=2200), confirmed: bool = Form(False),
):
    if not confirmed:
        raise HTTPException(422, "Confirm the photo and caption before connecting Instagram.")
    agent, _ = _configured_agent()
    jpeg = image.file.read(MAX_IMAGE_BYTES + 1)
    if len(jpeg) > MAX_IMAGE_BYTES:
        raise HTTPException(413, "Choose a JPEG photo smaller than 8 MB.")
    if not (jpeg.startswith(b"\xff\xd8\xff") and jpeg.endswith(b"\xff\xd9")):
        raise HTTPException(415, "Choose a JPEG photo.")
    url, state = agent.begin_authorization()
    session = token_urlsafe(32)
    now = datetime.now(timezone.utc)
    db.execute(text("DELETE FROM instagram_drafts WHERE expires_at <= :now"), {"now": now})
    db.execute(text("""
        INSERT INTO instagram_drafts (id, owner_id, state_hash, image_key, image, caption, phase, expires_at)
        VALUES (:id, :owner, :state, :image_key, :image, :caption, 'authorization', :expires)
    """), {
        "id": _digest(session), "owner": user.id, "state": _digest(state),
        "image_key": _digest(token_urlsafe(32)), "image": jpeg, "caption": caption,
        "expires": now + timedelta(seconds=DRAFT_SECONDS),
    })
    response.set_cookie(COOKIE, session, max_age=DRAFT_SECONDS, httponly=True, secure=True, samesite="lax", path="/api/v1/instagram")
    return next_photo_step("", image_uploaded=True, authorization_url=url)


@instagram_router.post("/callback", response_class=PlainTextResponse)
def instagram_callback(
    request: Request, db: Database, state: str = Form("", max_length=128),
    code: str = Form("", max_length=4096),
):
    session = request.cookies.get(COOKIE)
    if not session or not state:
        raise HTTPException(400, "This Instagram authorization request is invalid or expired.")
    agent, origin = _configured_agent()
    draft = db.execute(text("""
        UPDATE instagram_drafts SET phase = 'publishing', state_hash = NULL
        WHERE id = :id AND state_hash = :state AND phase = 'authorization' AND expires_at > now()
        RETURNING id, image_key, caption
    """), {"id": _digest(session), "state": _digest(state)}).mappings().one_or_none()
    if draft is None:
        raise HTTPException(400, "This Instagram authorization request is invalid or expired.")
    db.commit()

    try:
        token = agent.exchange_code(code)
        container = agent.create_photo(token, f"{origin}/api/v1/instagram/image/{draft['image_key']}", draft["caption"])
    except InstagramError as error:
        _finish(db, draft["id"], "failed", str(error))
        return "Instagram could not publish the photo. Return to ApnaSathi for details."
    try:
        media_id = agent.publish_photo(token, container)
    except InstagramError:
        _finish(db, draft["id"], "uncertain", "Instagram did not confirm publication. Check your profile before trying again.")
        return "Instagram did not confirm publication. Check your profile before trying again."
    _finish(db, draft["id"], "published", "Your photo was posted to Instagram.", media_id)
    return "Your photo was posted to Instagram. You can return to ApnaSathi."


def _finish(db, draft_id, phase, notice, media_id=None):
    db.execute(text("""
        UPDATE instagram_drafts SET phase = :phase, notice = :notice, media_id = :media_id,
        image = NULL, caption = ''
        WHERE id = :id
    """), {"id": draft_id, "phase": phase, "notice": notice, "media_id": media_id})


@instagram_router.get("/status")
def instagram_status(request: Request, user: CurrentUser, db: Database):
    draft = db.execute(text("""
        SELECT phase AS step, notice AS response, media_id FROM instagram_drafts
        WHERE id = :id AND owner_id = :owner AND expires_at > now()
    """), {"id": _digest(request.cookies.get(COOKIE, "")), "owner": user.id}).mappings().one_or_none()
    if draft is None:
        raise HTTPException(404, "This Instagram draft expired. Attach the photo again.")
    return dict(draft)


@instagram_router.get("/image/{image_key}")
def instagram_image(image_key: str, db: Database):
    image = db.scalar(text("""
        SELECT image FROM instagram_drafts
        WHERE image_key = :key AND phase = 'publishing' AND expires_at > now()
    """), {"key": image_key})
    if image is None:
        raise HTTPException(404, "Image unavailable.")
    return Response(bytes(image), media_type="image/jpeg", headers={
        "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
    })


@instagram_router.delete("/draft", status_code=204)
def cancel_instagram_draft(request: Request, response: Response, user: CurrentUser, db: Database):
    result = db.execute(text("""
        DELETE FROM instagram_drafts WHERE id = :id AND owner_id = :owner AND phase <> 'publishing'
    """), {"id": _digest(request.cookies.get(COOKIE, "")), "owner": user.id})
    if not result.rowcount:
        raise HTTPException(409, "This draft is unavailable or Instagram is processing it.")
    response.delete_cookie(COOKIE, path="/api/v1/instagram", secure=True, httponly=True)
