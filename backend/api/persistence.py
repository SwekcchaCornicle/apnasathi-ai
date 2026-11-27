"""Authenticated conversation, message, search history and memory APIs."""
from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from auth.dependencies import get_current_user
from database.models import Conversation, Memory, Message, SearchHistory, User
from database.session import get_db
from services.answer_reuse import normalize_question

router = APIRouter(tags=["user-persistence"])
SUPPORTED_LANGUAGES = {"en", "hi"}
LANGUAGE_NOTICE = "We're about to launch support for this language. For now, please choose Hindi or English."


def require_supported_language(language: str) -> str:
    normalized = language.strip().lower().replace("_", "-").split("-")[0]
    if normalized not in SUPPORTED_LANGUAGES:
        raise HTTPException(status_code=422, detail={"code": "LANGUAGE_NOT_AVAILABLE", "message": LANGUAGE_NOTICE, "supported_languages": ["en", "hi"]})
    return normalized


class ConversationCreate(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    channel: str = Field(default="chat", min_length=1, max_length=32)
    language: str | None = Field(default=None, min_length=2, max_length=16)


class ConversationResponse(BaseModel):
    id: UUID
    title: str | None
    channel: str
    language: str
    is_archived: bool
    created_at: datetime
    updated_at: datetime


class MessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=20000)
    language: str | None = Field(default=None, max_length=16)
    intent: str | None = Field(default=None, max_length=80)
    metadata: dict = Field(default_factory=dict)


class MessageResponse(BaseModel):
    id: UUID
    conversation_id: UUID
    role: str
    content: str
    language: str | None
    intent: str | None
    created_at: datetime


class SearchCreate(BaseModel):
    query: str = Field(min_length=1, max_length=4000)
    conversation_id: UUID | None = None
    intent: str | None = Field(default=None, max_length=80)
    language: str | None = Field(default=None, max_length=16)
    result_source: str | None = Field(default=None, max_length=32)


class SearchResponse(BaseModel):
    id: UUID
    query: str
    intent: str | None
    language: str | None
    result_source: str | None
    created_at: datetime


class MemoryCreate(BaseModel):
    category: str = Field(min_length=1, max_length=64)
    key: str = Field(min_length=1, max_length=120)
    value: str = Field(min_length=1, max_length=4000)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    expires_at: datetime | None = None


class MemoryResponse(BaseModel):
    id: UUID
    category: str
    key: str
    value: str
    confidence: float
    expires_at: datetime | None
    created_at: datetime


class LanguageSelection(BaseModel):
    language: str = Field(min_length=2, max_length=16)


class LanguageSelectionResponse(BaseModel):
    supported: bool
    language: str | None = None
    message: str | None = None
    supported_languages: list[str] = ["en", "hi"]


def _owned_conversation(db: Session, user_id: UUID, conversation_id: UUID) -> Conversation:
    conversation = db.scalar(select(Conversation).where(Conversation.id == conversation_id, Conversation.user_id == user_id))
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return conversation


@router.post("/users/me/language", response_model=LanguageSelectionResponse)
def select_language(payload: LanguageSelection, user: Annotated[User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)]):
    language = payload.language.strip().lower().replace("_", "-").split("-")[0]
    if language not in SUPPORTED_LANGUAGES:
        return LanguageSelectionResponse(supported=False, message=LANGUAGE_NOTICE)
    profile = user.profile
    if profile is None:
        from database.models import UserProfile
        profile = UserProfile(user_id=user.id)
        db.add(profile)
    profile.preferred_language = language
    db.flush()
    return LanguageSelectionResponse(supported=True, language=language)


@router.post("/conversations", response_model=ConversationResponse, status_code=201)
def create_conversation(payload: ConversationCreate, user: Annotated[User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)]):
    language = require_supported_language(payload.language or (user.profile.preferred_language if user.profile else "en"))
    conversation = Conversation(user_id=user.id, title=payload.title, channel=payload.channel, language=language)
    db.add(conversation)
    db.flush()
    return conversation


@router.get("/conversations", response_model=list[ConversationResponse])
def list_conversations(user: Annotated[User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)], limit: int = Query(30, ge=1, le=100), before: datetime | None = None):
    statement = select(Conversation).where(Conversation.user_id == user.id).order_by(Conversation.updated_at.desc()).limit(limit)
    if before is not None:
        statement = statement.where(Conversation.updated_at < before)
    return list(db.scalars(statement))


@router.get("/conversations/{conversation_id}/messages", response_model=list[MessageResponse])
def list_messages(conversation_id: UUID, user: Annotated[User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)], limit: int = Query(100, ge=1, le=200)):
    _owned_conversation(db, user.id, conversation_id)
    statement = select(Message).where(Message.user_id == user.id, Message.conversation_id == conversation_id).order_by(Message.created_at.asc()).limit(limit)
    return list(db.scalars(statement))


@router.post("/conversations/{conversation_id}/messages", response_model=MessageResponse, status_code=201)
def add_user_message(conversation_id: UUID, payload: MessageCreate, user: Annotated[User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)]):
    conversation = _owned_conversation(db, user.id, conversation_id)
    language = require_supported_language(payload.language or conversation.language)
    message = Message(user_id=user.id, conversation_id=conversation.id, role="user", content=payload.content.strip(), language=language, intent=payload.intent, metadata_json=payload.metadata)
    db.add(message)
    conversation.updated_at = datetime.now(timezone.utc)
    db.flush()
    return message


@router.post("/search-history", response_model=SearchResponse, status_code=201)
def record_search(payload: SearchCreate, user: Annotated[User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)]):
    language = require_supported_language(payload.language or (user.profile.preferred_language if user.profile else "en"))
    if payload.conversation_id is not None:
        _owned_conversation(db, user.id, payload.conversation_id)
    record = SearchHistory(user_id=user.id, conversation_id=payload.conversation_id, query=payload.query.strip(), normalized_query=normalize_question(payload.query), intent=payload.intent, language=language, result_source=payload.result_source)
    db.add(record)
    db.flush()
    return record


@router.get("/search-history", response_model=list[SearchResponse])
def list_search_history(user: Annotated[User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)], limit: int = Query(50, ge=1, le=200), before: datetime | None = None):
    statement = select(SearchHistory).where(SearchHistory.user_id == user.id).order_by(SearchHistory.created_at.desc()).limit(limit)
    if before is not None:
        statement = statement.where(SearchHistory.created_at < before)
    return list(db.scalars(statement))


@router.post("/memories", response_model=MemoryResponse, status_code=201)
def create_memory(payload: MemoryCreate, user: Annotated[User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)]):
    memory = Memory(user_id=user.id, category=payload.category, memory_key=payload.key, memory_value=payload.value.strip(), confidence=payload.confidence, expires_at=payload.expires_at)
    db.add(memory)
    db.flush()
    return {"id": memory.id, "category": memory.category, "key": memory.memory_key, "value": memory.memory_value, "confidence": memory.confidence, "expires_at": memory.expires_at, "created_at": memory.created_at}


@router.get("/memories", response_model=list[MemoryResponse])
def list_memories(user: Annotated[User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)]):
    now = datetime.now(timezone.utc)
    rows = db.scalars(select(Memory).where(Memory.user_id == user.id, Memory.is_active.is_(True), (Memory.expires_at.is_(None) | (Memory.expires_at > now))).order_by(Memory.updated_at.desc()))
    return [{"id": m.id, "category": m.category, "key": m.memory_key, "value": m.memory_value, "confidence": m.confidence, "expires_at": m.expires_at, "created_at": m.created_at} for m in rows]


@router.delete("/memories/{memory_id}", status_code=204)
def delete_memory(memory_id: UUID, user: Annotated[User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)]):
    memory = db.scalar(select(Memory).where(Memory.id == memory_id, Memory.user_id == user.id))
    if memory is None:
        raise HTTPException(status_code=404, detail="Memory not found.")
    memory.is_active = False
    db.flush()
    return None


# Internal helper for trusted orchestration to persist assistant replies; no public route.
def persist_assistant_message(db: Session, *, user_id: UUID, conversation_id: UUID, content: str, language: str, intent: str | None = None, metadata: dict | None = None) -> Message:
    conversation = _owned_conversation(db, user_id, conversation_id)
    message = Message(user_id=user_id, conversation_id=conversation.id, role="assistant", content=content, language=require_supported_language(language), intent=intent, metadata_json=metadata or {})
    db.add(message)
    conversation.updated_at = datetime.now(timezone.utc)
    db.flush()
    return message
