"""Authenticated chat orchestration: history -> semantic cache -> Gemini fallback."""
from datetime import datetime, timezone
import re
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from auth.dependencies import get_current_user
from database.models import Conversation, Message, SearchHistory, User
from database.session import get_db
from llm_model.classify_intent_action import intent_action
from llm_model.llm_model import VertexUnavailable, vertex_model
from services.answer_reuse import find_reusable_answer, normalize_question, store_approved_answer
from api.persistence import require_supported_language

router = APIRouter(tags=["assistant"])
AUTO_CACHE_MIN_CONFIDENCE = 0.90
ACTION_REQUEST = re.compile(r"\b(open|launch|call|phone|send|message|text|post|upload|share|order|buy|purchase|book|play|watch|navigate|install|delete|cancel)\b|(खोलो|खोलना|कॉल|फोन|भेजो|मैसेज|पोस्ट|ऑर्डर|मंगाओ|खरीदो|चलाओ|देखो)", re.IGNORECASE)

def is_action_request(message: str) -> bool:
    return bool(ACTION_REQUEST.search(message))


class AssistantChatRequest(BaseModel):
    conversation_id: UUID
    message: str = Field(min_length=1, max_length=4000)


class AssistantChatResponse(BaseModel):
    conversation_id: UUID
    user_message_id: UUID
    assistant_message_id: UUID
    intent: str
    response: str
    language: str
    source: str
    similarity: float | None = None
    requires_confirmation: bool = False


@router.post("/assistant/chat", response_model=AssistantChatResponse)
def assistant_chat(
    payload: AssistantChatRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Answer a text message using private semantic reuse before invoking Gemini."""
    conversation = db.scalar(select(Conversation).where(
        Conversation.id == payload.conversation_id,
        Conversation.user_id == user.id,
        Conversation.is_archived.is_(False),
    ))
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")

    language = require_supported_language(conversation.language)
    question = payload.message.strip()
    if not question:
        raise HTTPException(status_code=422, detail="Message cannot be empty.")

    user_message = Message(
        user_id=user.id,
        conversation_id=conversation.id,
        role="user",
        content=question,
        language=language,
    )
    db.add(user_message)
    conversation.updated_at = datetime.now(timezone.utc)
    db.flush()

    # Cache lookup happens before Gemini intent classification. Only GENERAL_QUESTION
    # entries can match; action workflows are never cached or replayed.
    source = "gemini"
    similarity = None
    intent = "GENERAL_QUESTION"
    requires_confirmation = False
    try:
        match = None if is_action_request(question) else find_reusable_answer(
            db,
            user_id=user.id,
            question=question,
            intent="GENERAL_QUESTION",
            language=language,
        )
    except Exception:
        db.rollback()
        # Re-establish the user message after rolling back a failed optional cache query.
        conversation = db.scalar(select(Conversation).where(
            Conversation.id == payload.conversation_id, Conversation.user_id == user.id
        ))
        if conversation is None:
            raise HTTPException(status_code=404, detail="Conversation not found.") from None
        user_message = Message(user_id=user.id, conversation_id=conversation.id, role="user", content=question, language=language)
        db.add(user_message)
        db.flush()
        match = None

    if match is not None:
        response_text = match.answer
        source = "semantic_cache"
        similarity = round(match.similarity, 4)
    else:
        try:
            classified = vertex_model(question)
        except VertexUnavailable:
            raise HTTPException(status_code=503, detail="The AI service is temporarily unavailable.") from None
        if classified is None:
            raise HTTPException(status_code=502, detail="The AI returned no structured response.")
        intent = classified.intent
        language = require_supported_language(classified.response_language if classified.response_language and classified.response_language != "und" else language)
        action = intent_action(classified)
        response_text = action.get("response") or classified.response
        requires_confirmation = bool(action.get("requires_confirmation", classified.requires_confirmation))

        # Cache only high-confidence, stable informational answers for this user.
        # Never cache action intents, transient results, or general conversation.
        if intent == "GENERAL_QUESTION" and classified.confidence >= AUTO_CACHE_MIN_CONFIDENCE and response_text.strip():
            try:
                store_approved_answer(
                    db,
                    user_id=user.id,
                    question=question,
                    answer=response_text,
                    intent=intent,
                    language=language,
                    quality_score=float(classified.confidence),
                    source_message_id=user_message.id,
                )
            except Exception:
                # Failure to cache must not discard a valid Gemini answer.
                db.rollback()
                conversation = db.scalar(select(Conversation).where(
                    Conversation.id == payload.conversation_id, Conversation.user_id == user.id
                ))
                user_message = Message(user_id=user.id, conversation_id=conversation.id, role="user", content=question, language=language)
                db.add(user_message)
                db.flush()

    assistant_message = Message(
        user_id=user.id,
        conversation_id=conversation.id,
        role="assistant",
        content=response_text,
        language=language,
        intent=intent,
        metadata_json={"source": source, "similarity": similarity},
    )
    db.add(assistant_message)
    db.add(SearchHistory(
        user_id=user.id,
        conversation_id=conversation.id,
        query=question,
        normalized_query=normalize_question(question),
        intent=intent,
        language=language,
        result_source=source,
    ))
    conversation.updated_at = datetime.now(timezone.utc)
    db.flush()

    return AssistantChatResponse(
        conversation_id=conversation.id,
        user_message_id=user_message.id,
        assistant_message_id=assistant_message.id,
        intent=intent,
        response=response_text,
        language=language,
        source=source,
        similarity=similarity,
        requires_confirmation=requires_confirmation,
    )
