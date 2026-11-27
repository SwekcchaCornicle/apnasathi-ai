"""Trusted persistence helpers for messages and user-scoped history."""
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import Session
from database.models import Conversation, Message, SearchHistory
from services.answer_reuse import normalize_question


def persist_assistant_reply(db: Session, *, user_id: UUID, conversation_id: UUID, content: str, language: str, intent: str | None = None, metadata: dict | None = None) -> Message:
    conversation = db.scalar(select(Conversation).where(Conversation.id == conversation_id, Conversation.user_id == user_id))
    if conversation is None:
        raise LookupError("Conversation not found for this user.")
    message = Message(user_id=user_id, conversation_id=conversation_id, role="assistant", content=content, language=language, intent=intent, metadata_json=metadata or {})
    db.add(message)
    db.flush()
    return message


def persist_search(db: Session, *, user_id: UUID, query: str, conversation_id: UUID | None = None, intent: str | None = None, language: str | None = None, result_source: str | None = None) -> SearchHistory:
    record = SearchHistory(user_id=user_id, conversation_id=conversation_id, query=query, normalized_query=normalize_question(query), intent=intent, language=language, result_source=result_source)
    db.add(record)
    db.flush()
    return record
