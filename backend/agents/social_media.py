"""Instagram photo posting helpers for a server-owned chat draft.

The caller owns uploads, OAuth callback routing, and per-user token storage.
Store OAuth state with the signed-in user's draft and consume it once at callback.
"""

from dataclasses import dataclass, field
from hmac import compare_digest
from secrets import token_urlsafe
from urllib.parse import urlencode, urlsplit

import requests

GRAPH = "https://graph.instagram.com"
SCOPES = "instagram_business_basic,instagram_business_content_publish"


class InstagramError(RuntimeError):
    """A safe error message that leaves credentials out of chat and logs."""


@dataclass(frozen=True)
class InstagramCredentials:
    user_id: str
    access_token: str = field(repr=False)
    expires_in: int


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
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": SCOPES,
            "state": state,
        })
        return f"https://www.instagram.com/oauth/authorize?{query}", state

    def exchange_code(self, code: str, state: str, expected_state: str) -> InstagramCredentials:
        if not code or not state or not expected_state or not compare_digest(
            state.encode(), expected_state.encode()
        ):
            raise InstagramError("Instagram authorization could not be verified.")
        short = _request(
            "code exchange", "POST", "https://api.instagram.com/oauth/access_token",
            data={
                "client_id": self.app_id, "client_secret": self.app_secret,
                "grant_type": "authorization_code", "redirect_uri": self.redirect_uri,
                "code": code,
            },
        )
        entries = short.get("data")
        if isinstance(entries, list) and len(entries) == 1 and isinstance(entries[0], dict):
            short = entries[0]
        if not short.get("user_id") or not short.get("access_token"):
            raise InstagramError("Instagram did not return the authorized account.")
        long = _request(
            "long-lived token exchange", "GET", f"{GRAPH}/access_token",
            params={
                "grant_type": "ig_exchange_token", "client_secret": self.app_secret,
                "access_token": short["access_token"],
            },
        )
        return self._credentials(str(short["user_id"]), long)

    def refresh(self, credentials: InstagramCredentials) -> InstagramCredentials:
        result = _request(
            "token refresh", "GET", f"{GRAPH}/refresh_access_token",
            params={"grant_type": "ig_refresh_token", "access_token": credentials.access_token},
        )
        return self._credentials(credentials.user_id, result)

    @staticmethod
    def _credentials(user_id, result):
        try:
            return InstagramCredentials(user_id, result["access_token"], int(result["expires_in"]))
        except (KeyError, ValueError, TypeError):
            raise InstagramError("Instagram did not return token expiry details.") from None

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

# Chat routes keep credentials in the backend and bind each draft to an HttpOnly cookie.
import os
from pathlib import Path
from threading import Lock
from time import monotonic
from typing import Annotated
from uuid import UUID

from dotenv import dotenv_values
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import PlainTextResponse

from auth.dependencies import get_current_user
from database.models import User

instagram_router = APIRouter(prefix="/instagram", tags=["instagram"])
COOKIE = "apnasathi_instagram_draft"
DRAFT_SECONDS = 30 * 60
MAX_IMAGE_BYTES = 8 * 1024 * 1024
_drafts = {}
_draft_lock = Lock()


@dataclass
class PhotoDraft:
    expires_at: float
    state: str
    authorization_url: str
    image_key: str
    image: bytes = field(repr=False)
    owner_id: UUID
    credentials: InstagramCredentials | None = field(default=None, repr=False)
    phase: str = "authorization"
    media_id: str | None = None


def _configured_agent():
    config = dotenv_values(Path(__file__).with_name(".env"))
    keys = ("INSTAGRAM_APP_ID", "INSTAGRAM_APP_SECRET", "INSTAGRAM_REDIRECT_URI", "INSTAGRAM_API_VERSION")
    values = [os.getenv(key) or config.get(key) for key in keys]
    if not all(values):
        raise HTTPException(503, "Your draft is ready. Instagram connection is unavailable until the app owner finishes the Meta setup.")
    agent = InstagramAgent(*values)
    redirect = urlsplit(agent.redirect_uri)
    if redirect.scheme != "https" or not redirect.hostname:
        raise HTTPException(503, "Instagram requires a public HTTPS callback.")
    return agent


def _active_drafts():
    now = monotonic()
    for expired in [key for key, draft in _drafts.items() if draft.expires_at <= now]:
        del _drafts[expired]
    return _drafts


def _get_draft(request: Request, owner_id: UUID | None = None):
    draft = _active_drafts().get(request.cookies.get(COOKIE))
    if draft is None or (owner_id is not None and draft.owner_id != owner_id):
        raise HTTPException(404, "This Instagram draft expired. Attach the photo again.")
    return draft


@instagram_router.post("/photo", max_body_size=MAX_IMAGE_BYTES + 65536)
def attach_photo(request: Request, response: Response, user: Annotated[User, Depends(get_current_user)], image: UploadFile = File(...)):
    agent = _configured_agent()
    jpeg = image.file.read(MAX_IMAGE_BYTES + 1)
    if len(jpeg) > MAX_IMAGE_BYTES:
        raise HTTPException(413, "Choose a JPEG photo smaller than 8 MB.")
    if not (jpeg.startswith(b"\xff\xd8\xff") and jpeg.endswith(b"\xff\xd9")):
        raise HTTPException(415, "Choose a JPEG photo.")

    url, state = agent.begin_authorization()
    session = token_urlsafe(32)
    with _draft_lock:
        drafts = _active_drafts()
        previous = request.cookies.get(COOKIE)
        if previous in drafts and drafts[previous].owner_id == user.id:
            if drafts[previous].phase == "publishing":
                raise HTTPException(409, "Wait for the current Instagram post to finish.")
            del drafts[previous]
        if len(drafts) >= 16:
            raise HTTPException(503, "Too many active Instagram drafts. Try again later.")
        drafts[session] = PhotoDraft(monotonic() + DRAFT_SECONDS, state, url, token_urlsafe(32), jpeg, user.id)
    response.set_cookie(COOKIE, session, max_age=DRAFT_SECONDS, httponly=True, secure=True, samesite="lax", path="/api/v1/instagram")
    return next_photo_step("", image_uploaded=True, authorization_url=url)


@instagram_router.get("/callback", response_class=PlainTextResponse)
def instagram_callback(request: Request, state: str = "", code: str = ""):
    agent = _configured_agent()
    with _draft_lock:
        draft = _get_draft(request)
        if draft.phase != "authorization" or not state or not compare_digest(state.encode(), draft.state.encode()):
            raise HTTPException(400, "This Instagram authorization request is invalid or expired.")
        expected_state, draft.state = draft.state, ""
        draft.phase = "connecting"
    try:
        token = agent.exchange_code(code, state, expected_state)
    except InstagramError:
        with _draft_lock:
            draft.phase = "failed"
        raise HTTPException(400, "Instagram authorization failed. You can return to the chat.") from None
    with _draft_lock:
        draft.credentials = token
        draft.phase = "caption"
    return "Instagram connected. Return to the ApnaSathi chat to enter your caption."


@instagram_router.get("/status")
def instagram_status(request: Request, user: Annotated[User, Depends(get_current_user)]):
    with _draft_lock:
        draft = _get_draft(request, user.id)
        if draft.phase == "caption":
            return next_photo_step("", image_uploaded=True, connected=True)
        return {"step": draft.phase, "media_id": draft.media_id}


@instagram_router.get("/image/{image_key}")
def instagram_image(image_key: str):
    # Instagram fetches this short-lived JPEG without sending the browser's draft cookie.
    with _draft_lock:
        for draft in _active_drafts().values():
            if draft.image_key == image_key and draft.phase == "publishing":
                return Response(draft.image, media_type="image/jpeg", headers={
                    "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
                })
    raise HTTPException(404, "Image unavailable.")


@instagram_router.post("/publish")
def publish_instagram_photo(
    request: Request, user: Annotated[User, Depends(get_current_user)],
    caption: str = Form("", max_length=2200), confirmed: bool = Form(False),
):
    if not confirmed:
        raise HTTPException(422, "Review and confirm the post before publishing.")
    agent = _configured_agent()
    with _draft_lock:
        draft = _get_draft(request, user.id)
        if draft.phase == "published":
            return {"step": "published", "media_id": draft.media_id, "response": "Your photo was posted to Instagram."}
        if draft.phase != "caption" or draft.credentials is None:
            raise HTTPException(409, "Connect Instagram before publishing this draft.")
        token = draft.credentials
        draft.phase = "publishing"
    origin = urlsplit(agent.redirect_uri)
    image_url = f"{origin.scheme}://{origin.netloc}/api/v1/instagram/image/{draft.image_key}"
    try:
        container = agent.create_photo(token, image_url, caption)
    except InstagramError as error:
        with _draft_lock:
            draft.phase = "caption"
        raise HTTPException(502, str(error)) from None
    try:
        media_id = agent.publish_photo(token, container)
    except InstagramError:
        with _draft_lock:
            draft.phase = "failed"
            draft.image = b""
            draft.credentials = None
        raise HTTPException(502, "Instagram did not confirm the post. Check Instagram before trying again.") from None
    with _draft_lock:
        draft.media_id = media_id
        draft.phase = "published"
        draft.image = b""
        draft.credentials = None
    return {"step": "published", "media_id": media_id, "response": "Your photo was posted to Instagram."}


@instagram_router.delete("/draft", status_code=204)
def cancel_instagram_draft(request: Request, response: Response, user: Annotated[User, Depends(get_current_user)]):
    with _draft_lock:
        draft = _get_draft(request, user.id)
        if draft.phase == "publishing":
            raise HTTPException(409, "Wait for the current Instagram post to finish.")
        del _drafts[request.cookies[COOKIE]]
    response.delete_cookie(COOKIE, path="/api/v1/instagram", secure=True, httponly=True)
