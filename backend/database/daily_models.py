"""Tenant-scoped daily assistant records."""
import uuid
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from database.base import Base

class DailyAction(Base):
    __tablename__ = "daily_actions"
    __table_args__ = (Index("ix_daily_actions_user_status", "user_id", "status"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    intent: Mapped[str] = mapped_column(String(48), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="awaiting_confirmation")
    result: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

class Reminder(Base):
    __tablename__ = "reminders"
    __table_args__ = (Index("ix_reminders_user_due", "user_id", "status", "scheduled_at"), Index("ix_reminders_due_worker", "status", "scheduled_at", "next_attempt_at"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    scheduled_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="Asia/Kolkata")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="scheduled")

class DailyTask(Base):
    __tablename__ = "daily_tasks"
    __table_args__ = (Index("ix_daily_tasks_user_status", "user_id", "status"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    priority: Mapped[str] = mapped_column(String(12), nullable=False, default="medium")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    due_at: Mapped[object | None] = mapped_column(DateTime(timezone=True))

class ShoppingList(Base):
    __tablename__ = "shopping_lists"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False, default="My shopping list")
    items: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

class Expense(Base):
    __tablename__ = "expenses"
    __table_args__ = (Index("ix_expenses_user_date", "user_id", "spent_at"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str] = mapped_column(String(240), nullable=False)
    spent_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)

class MealPlan(Base):
    __tablename__ = "meal_plans"
    __table_args__ = (Index("ix_meal_plans_user_date", "user_id", "plan_date"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    plan_date: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    meal_type: Mapped[str] = mapped_column(String(20), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    ingredients: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

class MessageDraft(Base):
    __tablename__ = "message_drafts"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    channel: Mapped[str] = mapped_column(String(24), nullable=False, default="whatsapp")
    recipient: Mapped[str | None] = mapped_column(String(160))
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

class GoogleCalendarCredential(Base):
    __tablename__ = "google_calendar_credentials"
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    refresh_token_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    connected_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

class GoogleOAuthState(Base):
    __tablename__ = "google_oauth_states"
    state_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    expires_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[object | None] = mapped_column(DateTime(timezone=True))
