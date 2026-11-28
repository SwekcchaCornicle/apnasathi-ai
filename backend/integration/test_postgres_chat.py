import os
import sys
from pathlib import Path
from time import perf_counter
from unittest.mock import patch
from urllib.parse import urlsplit
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from api import assistant, auth
from app import app
from auth import dependencies
from database.models import KnowledgeEmbedding
from database.session import get_session_factory
from llm_model.intent_classifier import IntentSchema


def test_isolated_accounts_chat_voice_history_and_real_vector_cache():
    database = urlsplit(os.environ["DATABASE_URL"])
    assert database.hostname in {"localhost", "127.0.0.1"}
    assert (database.port, database.path) in {(55432, "/apnasathi_qa"), (55433, "/postgres")}

    def claims(token):
        return {"sub": token, "email": f"{token}@qa.example.test"}

    run_id = uuid4().hex
    scopes = [{"Authorization": f"Bearer local-integration-{run_id}-{letter}"} for letter in ("a", "b")]
    answer = IntentSchema(
        intent="GENERAL_QUESTION", response="Plants use light to convert water and carbon dioxide into sugars.",
        response_language="en", confidence=0.99, requires_confirmation=False,
    )
    shopping = IntentSchema(
        intent="ORDER_GROCERIES", response="Review your basket.",
        response_language="en", confidence=0.99, requires_confirmation=True,
        shopping_items=["2 apples", "1 litre milk"],
    )

    with (
        patch.object(auth, "verify_cognito_id_token", side_effect=claims),
        patch.object(dependencies, "verify_cognito_id_token", side_effect=claims),
        patch.object(assistant, "vertex_model", return_value=answer) as llm,
        patch("app.transcribe_audio", return_value="How does photosynthesis work?"),
        TestClient(app) as client,
    ):
        for headers in scopes:
            token = headers["Authorization"].split()[1]
            assert client.post("/api/v1/auth/cognito", json={"id_token": token}).status_code == 200
        a, b = scopes
        assert client.patch("/api/v1/users/me/profile", json={"preferred_language": "hi"}, headers=a).json()["preferred_language"] == "hi"
        assert client.post("/api/v1/users/me/language", json={"language": "fr"}, headers=a).json()["message"] == "We are about to launch support for this language."
        assert client.post("/api/v1/conversations", json={"language": "fr"}, headers=a).status_code == 422
        conversation = client.post("/api/v1/conversations", json={"language": "en"}, headers=a).json()
        cid = conversation["id"]
        memory = client.post("/api/v1/memories", json={"category": "test", "key": "sample", "value": "local fixture"}, headers=a).json()
        assert client.get("/api/v1/memories", headers=b).json() == []
        assert client.delete(f"/api/v1/memories/{memory['id']}", headers=b).status_code == 404
        assert client.get(f"/api/v1/conversations/{cid}", headers=b).status_code == 404
        assert client.get(f"/api/v1/conversations/{cid}/messages", headers=b).status_code == 404
        assert client.post(f"/api/v1/conversations/{cid}/messages", json={"content": "fixture"}, headers=b).status_code == 404
        assert client.post("/api/v1/search-history", json={"query": "fixture", "conversation_id": cid}, headers=b).status_code == 404

        question = "How does photosynthesis work?"
        payload = {"conversation_id": cid, "message": question}
        assert client.post("/api/v1/assistant/chat", json=payload, headers=b).status_code == 404
        started = perf_counter()
        first = client.post("/api/v1/assistant/chat", json=payload, headers=a)
        print(f"First request {1000 * (perf_counter() - started):.1f} ms")
        assert first.status_code == 200
        assert first.json()["source"] == "gemini"
        assert llm.call_count == 1
        with get_session_factory()() as db:
            entry = db.scalar(select(KnowledgeEmbedding).where(KnowledgeEmbedding.source_message_id == first.json()["user_message_id"]))
            assert entry is not None and len(entry.embedding) == 768
        started = perf_counter()
        second = client.post("/api/v1/assistant/chat", json=payload, headers=a)
        print(f"Cache hit {1000 * (perf_counter() - started):.1f} ms")
        assert second.json()["source"] == "semantic_cache"
        assert llm.call_count == 1
        paraphrase = client.post("/api/v1/assistant/chat", json=payload | {"message": "How does the process of photosynthesis work?"}, headers=a)
        assert paraphrase.json()["source"] == "semantic_cache"
        assert llm.call_count == 1
        near_miss = client.post("/api/v1/assistant/chat", json=payload | {"message": "What is the chemical formula for photosynthesis?"}, headers=a)
        assert near_miss.json()["source"] == "gemini"
        assert llm.call_count == 2
        assert client.post("/api/v1/knowledge/lookup", json={"question": question, "intent": "GENERAL_QUESTION", "language": "en"}, headers=b).json()["found"] is False
        assert client.post("/api/v1/assistant/chat", json=payload | {"message": "Explain black holes."}, headers=a).json()["source"] == "gemini"
        assert llm.call_count == 3

        audio = client.post(f"/api/v1/assistant/audio?conversation_id={cid}", files={"audio": ("test.webm", b"\x1a\x45\xdf\xa3recording", "audio/webm")}, headers=a)
        assert audio.status_code == 200
        assert audio.json()["transcription"] == question
        messages = client.get(f"/api/v1/conversations/{cid}/messages", headers=a).json()
        assert [message["role"] for message in messages] == ["user", "assistant"] * 6
        assert client.get("/api/v1/search-history", headers=b).json() == []

        llm.return_value = shopping
        order = client.post("/api/v1/assistant/chat", json=payload | {"message": "Order 2 apples and 1 litre milk from Blinkit."}, headers=a).json()
        assert order["intent"] == "ORDER_GROCERIES"
        assert order["shopping"]["step"] == "item" and len(order["shopping"]["actions"]) == 2
        assert order["shopping"]["session"]["store"] == "Blinkit"
        guide_calls = llm.call_count
        add = client.post("/api/v1/assistant/chat", json=payload | {"message": "Yes"}, headers=a).json()
        assert add["shopping"]["step"] == "item" and llm.call_count == guide_calls
        correction = client.post("/api/v1/assistant/chat", json=payload | {"message": "Change items to 2 apples, 1 litre milk, bananas"}, headers=a).json()
        assert correction["shopping"]["session"]["items"] == ["2 apples", "1 litre milk", "bananas"]
        cancel = client.post("/api/v1/assistant/chat", json=payload | {"message": "Cancel"}, headers=a).json()
        assert cancel["shopping"]["done"] and llm.call_count == guide_calls
        history = client.get(f"/api/v1/conversations/{cid}/messages", headers=a).json()
        assert history[-1]["shopping"]["done"]
        next_cid = client.post("/api/v1/conversations", json={"language": "en"}, headers=a).json()["id"]
        shopping_llm_calls = llm.call_count
        previous_order = "What did I order from Blinkit last time?"
        reply = client.post("/api/v1/assistant/chat", json={"conversation_id": next_cid, "message": previous_order}, headers=a)
        assert reply.status_code == 200
        assert "2 apples" in reply.json()["response"]
        assert "1 litre milk" in reply.json()["response"]
        assert "bananas" in reply.json()["response"]
        assert reply.json()["source"] == "saved_history"
        assert llm.call_count == shopping_llm_calls
        other_cid = client.post("/api/v1/conversations", json={"language": "en"}, headers=b).json()["id"]
        other_reply = client.post("/api/v1/assistant/chat", json={"conversation_id": other_cid, "message": previous_order}, headers=b)
        assert other_reply.status_code == 200
        assert "2 apples" not in other_reply.json()["response"]
        assert other_reply.json()["source"] == "saved_history"
        assert client.get(f"/api/v1/conversations/{next_cid}/messages", headers=b).status_code == 404


def test_instagram_draft_is_shared_and_callback_claims_it_once():
    from unittest.mock import Mock

    from agents import social_media
    from database.models import User

    database = urlsplit(os.environ["DATABASE_URL"])
    assert database.hostname in {"localhost", "127.0.0.1"}
    assert (database.port, database.path) in {(55432, "/apnasathi_qa"), (55433, "/postgres")}
    subject = f"instagram-integration-{uuid4().hex}"
    email = f"{subject}@example.test"
    with get_session_factory()() as db:
        user = User(auth_provider="cognito", auth_subject=subject, email=email)
        db.add(user)
        db.commit()

    jpeg = bytes.fromhex("ffd8ff00ffd9")
    agent = Mock()
    oauth_state = uuid4().hex
    agent.begin_authorization.return_value = ("https://www.facebook.com/dialog/oauth", oauth_state)
    agent.publish_photo.return_value = "fixture-media-id"

    try:
        with (
            patch.dict(app.dependency_overrides, {dependencies.get_current_user: lambda: user}),
            patch.object(social_media, "_configured_agent", return_value=(agent, "https://local.test")),
            TestClient(app, base_url="https://local.test") as chat_client,
            TestClient(app, base_url="https://local.test") as callback_client,
            TestClient(app, base_url="https://local.test") as image_client,
        ):
            def load_image(credentials, image_url, caption):
                assert caption == "A confirmed caption"
                image = image_client.get(urlsplit(image_url).path)
                assert image.status_code == 200
                assert image.content == jpeg
                return "fixture-container"

            agent.create_photo.side_effect = load_image
            draft = chat_client.post(
                "/api/v1/instagram/photo",
                files={"image": ("fixture.jpg", jpeg, "image/jpeg")},
                data={"caption": "A confirmed caption", "confirmed": "true"},
            )
            assert draft.status_code == 200, draft.text
            callback = {"state": oauth_state, "code": "fixture-code"}
            callback_route = "/api/v1/instagram/callback"
            assert callback_client.post(callback_route, data=callback).status_code == 400
            callback_client.cookies.update(chat_client.cookies)
            assert callback_client.post(callback_route, data=callback).status_code == 200
            assert callback_client.post(callback_route, data=callback).status_code == 400
            assert chat_client.get("/api/v1/instagram/status").json()["media_id"] == "fixture-media-id"
            agent.publish_photo.assert_called_once_with(agent.exchange_code.return_value, "fixture-container")
            image_path = urlsplit(agent.create_photo.call_args.args[1]).path
            assert image_client.get(image_path).status_code == 404
    finally:
        with get_session_factory()() as db:
            db.delete(db.get(User, user.id))
            db.commit()
