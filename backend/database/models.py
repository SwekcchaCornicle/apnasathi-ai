"""Tenant-aware persistence models for users, conversations and reusable guidance."""
import uuid
from datetime import datetime
from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, CheckConstraint, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database.base import Base

class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

class User(TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("auth_provider", "auth_subject", name="uq_users_provider_subject"), Index("ix_users_email", "email"))
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    auth_provider: Mapped[str] = mapped_column(String(32), nullable=False)
    auth_subject: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(320))
    email_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    profile: Mapped["UserProfile | None"] = relationship(back_populates="user", uselist=False, cascade="all, delete-orphan")
    conversations: Mapped[list["Conversation"]] = relationship(back_populates="user", cascade="all, delete-orphan")

class UserProfile(TimestampMixin, Base):
    __tablename__ = "user_profiles"
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    display_name: Mapped[str | None] = mapped_column(String(120))
    preferred_language: Mapped[str] = mapped_column(String(16), nullable=False, default="en", server_default="en")
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="Asia/Kolkata", server_default="Asia/Kolkata")
    preferences: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    user: Mapped[User] = relationship(back_populates="profile")

class Conversation(TimestampMixin, Base):
    __tablename__ = "conversations"
    __table_args__ = (Index("ix_conversations_user_updated", "user_id", "updated_at"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str | None] = mapped_column(String(200))
    channel: Mapped[str] = mapped_column(String(32), nullable=False, default="chat", server_default="chat")
    language: Mapped[str] = mapped_column(String(16), nullable=False, default="en", server_default="en")
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    user: Mapped[User] = relationship(back_populates="conversations")
    messages: Mapped[list["Message"]] = relationship(back_populates="conversation", cascade="all, delete-orphan", order_by="Message.created_at")

class Message(TimestampMixin, Base):
    __tablename__ = "messages"
    __table_args__ = (CheckConstraint("role IN ('user', 'assistant', 'system', 'tool')", name="ck_messages_role"), Index("ix_messages_conversation_created", "conversation_id", "created_at"), Index("ix_messages_user_created", "user_id", "created_at"))
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str | None] = mapped_column(String(16))
    intent: Mapped[str | None] = mapped_column(String(80))
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict, server_default="{}")
    conversation: Mapped[Conversation] = relationship(back_populates="messages")

class SearchHistory(TimestampMixin, Base):
    __tablename__ = "search_history"
    __table_args__ = (Index("ix_search_history_user_created", "user_id", "created_at"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="SET NULL"))
    query: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_query: Mapped[str] = mapped_column(Text, nullable=False)
    intent: Mapped[str | None] = mapped_column(String(80))
    language: Mapped[str | None] = mapped_column(String(16))
    result_source: Mapped[str | None] = mapped_column(String(32))

class Memory(TimestampMixin, Base):
    __tablename__ = "memories"
    __table_args__ = (Index("ix_memories_user_active", "user_id", "is_active"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    memory_key: Mapped[str] = mapped_column(String(120), nullable=False)
    memory_value: Mapped[str] = mapped_column(Text, nullable=False)
    source_message_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("messages.id", ondelete="SET NULL"))
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0, server_default="1.0")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

class KnowledgeEmbedding(TimestampMixin, Base):
    __tablename__ = "knowledge_embeddings"
    __table_args__ = (CheckConstraint("visibility IN ('private', 'shared')", name="ck_knowledge_visibility"), Index("ix_knowledge_user_active", "user_id", "is_active"), Index("ix_knowledge_intent_language", "intent", "language"))
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    source_message_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("messages.id", ondelete="SET NULL"))
    question: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    intent: Mapped[str | None] = mapped_column(String(80))
    language: Mapped[str] = mapped_column(String(16), nullable=False, default="en", server_default="en")
    embedding_model: Mapped[str] = mapped_column(String(120), nullable=False, default="intfloat/multilingual-e5-base", server_default="intfloat/multilingual-e5-base")
    embedding: Mapped[list[float]] = mapped_column(Vector(768), nullable=False)
    visibility: Mapped[str] = mapped_column(String(16), nullable=False, default="private", server_default="private")
    quality_score: Mapped[float | None] = mapped_column(Float)
    reuse_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")

class AgentExecution(TimestampMixin, Base):
    __tablename__ = "agent_executions"
    __table_args__ = (Index("ix_agent_executions_user_created", "user_id", "created_at"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="SET NULL"))
    message_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("messages.id", ondelete="SET NULL"))
    agent_name: Mapped[str] = mapped_column(String(80), nullable=False)
    action_name: Mapped[str | None] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    input_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    output_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    error_code: Mapped[str | None] = mapped_column(String(80))
