"""Structured intent schema for Hindi/English daily assistant commands."""
from typing import Any, Literal
from pydantic import BaseModel, Field

DailyIntent = Literal[
    "SET_REMINDER", "CREATE_TODO", "DRAFT_MESSAGE",
    "CREATE_SHOPPING_LIST", "ADD_SHOPPING_ITEM",
    "TRACK_EXPENSE", "PLAN_MEAL", "CREATE_CALENDAR_EVENT", "GENERAL_QUESTION",
    "GENERAL_CONVERSATION", "UNKNOWN"
]

class PlannedDailyAction(BaseModel):
    intent: DailyIntent
    entities: dict[str, Any] = Field(default_factory=dict)
    requires_confirmation: bool = True

class DailyActionPlan(BaseModel):
    language: Literal["hi", "en"] = "hi"
    response: str
    actions: list[PlannedDailyAction] = Field(default_factory=list)
    needs_clarification: bool = False
    clarification_question: str | None = None
    confidence: float = Field(ge=0, le=1)
