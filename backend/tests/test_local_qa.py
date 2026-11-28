from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
import sys
from unittest.mock import patch

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from auth import cognito
from database.session import get_db

with patch("faster_whisper.WhisperModel"):
    from app import app


@pytest.fixture(scope="module")
def signing_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.mark.parametrize(("changes", "status"), [
    ({}, 200),
    ({"aud": "other-client"}, 401),
    ({"iss": "https://other.invalid"}, 401),
    ({"token_use": "access"}, 401),
    ({"email_verified": False}, 403),
    ({"exp": 1}, 401),
    ({"iat": timedelta(seconds=2)}, 200),
    ({"iat": timedelta(minutes=1)}, 401),
])
def test_cognito_claims_are_verified(signing_key, changes, status):
    now = datetime.now(timezone.utc)
    claims = {
        "aud": "test-public-client", "iss": cognito.ISSUER, "sub": "sample-user",
        "exp": now + timedelta(minutes=5), "iat": now, "token_use": "id",
        "email": "qa@example.test", "email_verified": True,
    }
    timed_changes = {key: now + value if isinstance(value, timedelta) else value for key, value in changes.items()}
    token = jwt.encode(claims | timed_changes, signing_key, algorithm="RS256")
    with patch.object(cognito, "APP_CLIENT_ID", "test-public-client"), patch.object(cognito, "_jwks_client") as factory:
        factory.return_value.get_signing_key_from_jwt.return_value = SimpleNamespace(key=signing_key.public_key())
        if status == 200:
            assert cognito.verify_cognito_id_token(token)["sub"] == "sample-user"
        else:
            with pytest.raises(HTTPException) as error:
                cognito.verify_cognito_id_token(token)
            assert error.value.status_code == status


@pytest.mark.parametrize(("method", "path", "body"), [
    ("GET", "/conversations", None),
    ("GET", "/users/me", None),
    ("GET", "/search-history", None),
    ("GET", "/memories", None),
    ("POST", "/assistant/chat", {"conversation_id": "f18ab244-4c98-4937-a2a2-8175ad523891", "message": "Hello"}),
])
def test_chat_and_private_routes_are_registered_and_reject_missing_auth(method, path, body):
    with patch.dict(app.dependency_overrides, {get_db: lambda: None}):
        with TestClient(app) as client:
            response = client.request(method, f"/api/v1{path}", json=body)
    assert response.status_code == 401


def test_vite_preflight_allows_configured_local_origin():
    with TestClient(app) as client:
        response = client.options("/api/v1/assistant/chat", headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        })
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_invalid_auth_body_does_not_echo_token():
    token_fixture = "dummy-short-token"
    with patch.dict(app.dependency_overrides, {get_db: lambda: None}):
        with TestClient(app) as client:
            response = client.post("/api/v1/auth/cognito", json={"id_token": token_fixture})
    assert response.status_code == 422
    assert token_fixture not in response.text


def test_missing_auth_is_rejected_before_database_configuration():
    with TestClient(app) as client:
        response = client.get("/api/v1/conversations")
    assert response.status_code == 401


def test_instagram_draft_is_private_and_publish_requires_confirmation():
    from unittest.mock import Mock
    from uuid import uuid4
    from agents import social_media
    from auth.dependencies import get_current_user

    owner = SimpleNamespace(id=uuid4())
    db = Mock()
    posted = {"id": "fixture-draft", "image_key": "fixture-image", "caption": "review"}
    db.execute.return_value.mappings.return_value.one_or_none.side_effect = [None, posted, None]
    with (
        patch.dict(app.dependency_overrides, {get_current_user: lambda: owner, get_db: lambda: db}),
        patch.object(social_media, "_configured_agent") as configured,
        TestClient(app, base_url="https://local.test") as client,
    ):
        agent = Mock()
        configured.return_value = (agent, "https://local.test")
        agent.begin_authorization.return_value = ("https://www.facebook.com/dialog/oauth", "fixture-state")
        agent.create_photo.return_value = "fixture-container"
        agent.publish_photo.return_value = "fixture-media"
        files = {"image": ("fixture.jpg", bytes.fromhex("ffd8ff00ffd9"), "image/jpeg")}
        callback = {"state": "fixture-state", "code": "fixture-code"}
        assert client.post("/api/v1/instagram/callback", data=callback).status_code == 400
        assert client.post("/api/v1/instagram/photo", files=files).status_code == 422
        db.execute.assert_not_called()
        photo = client.post("/api/v1/instagram/photo", files=files, data={"caption": "review", "confirmed": "true"})
        assert photo.status_code == 200
        assert "HttpOnly" in photo.headers["set-cookie"]
        assert client.get("/api/v1/instagram/status").status_code == 404
        agent.publish_photo.assert_not_called()
        result = client.post("/api/v1/instagram/callback", data=callback)
        assert result.status_code == 200
        assert "was posted" in result.text
        assert client.post("/api/v1/instagram/callback", data=callback).status_code == 400
        agent.exchange_code.assert_called_once_with("fixture-code")
        agent.create_photo.assert_called_once_with(agent.exchange_code.return_value, "https://local.test/api/v1/instagram/image/fixture-image", "review")
        agent.publish_photo.assert_called_once_with(agent.exchange_code.return_value, "fixture-container")


def test_video_troubleshooting_accepts_text_and_keeps_selected_language():
    from auth.dependencies import get_current_user

    with (
        patch.dict(app.dependency_overrides, {get_current_user: lambda: object()}),
        patch("agents.watch_show.troubleshoot.generate_voice", return_value={}),
        TestClient(app) as client,
    ):
        response = client.post("/api/v1/watch-show/troubleshoot", data={
            "step": "playing", "language": "hi", "platform": "Netflix", "reply": "हाँ",
        })
    assert response.status_code == 200
    assert response.json()["step"] == "confirmed"
    assert response.json()["response"] == "वीडियो चल रहा है।"


def test_trace_header_matches_safe_cloudwatch_stages(caplog):
    from logging import INFO

    fixture = "deliberately-invalid-fixture"
    with caplog.at_level(INFO, logger="uvicorn.error"), TestClient(app) as client:
        response = client.post("/api/v1/auth/cognito", json={"id_token": fixture})
    identifier = response.headers["x-request-id"]
    assert f"request_id={identifier} stage=request.start" in caplog.text
    assert f"request_id={identifier} stage=request.complete" in caplog.text
    assert fixture not in caplog.text


def test_video_uses_provider_search_when_direct_lookup_is_unavailable():
    from agents.watch_show.watch_show import watch_show

    with (
        patch("agents.watch_show.watch_show.get_streaming_platforms", side_effect=RuntimeError),
        patch("agents.watch_show.watch_show.generate_voice", return_value={}),
    ):
        result = watch_show("Panchayat", "en", "Amazon Prime Video")
    assert result["playback_status"] == "search"
    assert result["playback_platform"] == "Prime Video"
    assert result["playback_url"] == "https://www.primevideo.com/search?phrase=Panchayat"


def test_dhindora_spelling_offers_verified_links():
    from agents.watch_show.watch_show import watch_show
    with patch("agents.watch_show.watch_show.generate_voice", return_value={}):
        result = watch_show("Dindora", "en", "Netflix")
    assert result["playback_status"] == "choices"
    assert result["playback_url"] is None
    assert result["playback_options"][0]["url"] == "https://www.netflix.com/in/title/82643833"


def test_blinkit_exact_pack_uses_product_link():
    from agents.shoaping import retailer_item_links
    direct, fallback = retailer_item_links("Blinkit", ("i kg patto", "2 kg potato"))
    assert direct["url"] == "https://blinkit.com/prn/new-potato/prid/199435"
    assert fallback["url"] == "https://blinkit.com/s/?q=2+kg+potato"


def test_similar_title_choices_keep_direct_and_search_links():
    from agents.watch_show.watch_show import SimilarTitles, watch_show
    with (
        patch("agents.watch_show.watch_show.generate_voice", return_value={}),
        patch("agents.watch_show.watch_show.get_streaming_platforms",
              side_effect=SimilarTitles([("Interstellar", 1), ("Interstellar Wars", 2)], "IN")),
        patch("agents.watch_show.watch_show.watchmode_headers", return_value={}),
        patch("agents.watch_show.watch_show.title_sources", side_effect=lambda title_id, *_: (
            [{"platform": "Netflix", "web_url": "https://www.netflix.com/title/123", "access_type": "sub"}]
            if title_id == 1 else []
        )),
    ):
        result = watch_show("Intersteler", "en", "Netflix")
    assert [choice["kind"] for choice in result["playback_options"]] == ["ready", "search"]


def test_empty_video_search_retries_a_spelling_prefix():
    from agents.watch_show.watch_show import SimilarTitles, get_streaming_platforms
    with (
        patch("agents.watch_show.watch_show.watchmode_headers", return_value={}),
        patch("agents.watch_show.watch_show.search_titles", side_effect=[
            [], [{"name": "Interstellar", "id": 1}],
        ]) as search,
        pytest.raises(SimilarTitles) as error,
    ):
        get_streaming_platforms("Intersteler")
    assert error.value.matches == [("Interstellar", 1)]
    assert search.call_args.args[0] == "Interste"
