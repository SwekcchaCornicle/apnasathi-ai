"""Authenticated semantic answer lookup endpoint (cache miss is handled by LLM orchestration)."""
import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from auth.dependencies import get_current_user
from database.models import User
from database.session import get_db
from services.answer_reuse import REUSABLE_INTENTS, find_reusable_answer

router = APIRouter(tags=["semantic-retrieval"])
logger = logging.getLogger(__name__)


class KnowledgeLookupRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    intent: str = Field(min_length=1, max_length=80)
    language: str | None = Field(default=None, max_length=16)


class KnowledgeLookupResponse(BaseModel):
    found: bool
    answer: str | None = None
    matched_question: str | None = None
    similarity: float | None = None
    knowledge_id: UUID | None = None
    source: str = "llm_required"


@router.post("/knowledge/lookup", response_model=KnowledgeLookupResponse)
def lookup_knowledge(
    payload: KnowledgeLookupRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    if payload.intent not in REUSABLE_INTENTS:
        return KnowledgeLookupResponse(found=False, source="llm_required")
    try:
        match = find_reusable_answer(
            db,
            user_id=user.id,
            question=payload.question,
            intent=payload.intent,
            language=payload.language,
        )
    except Exception:
        # Semantic retrieval is an optimization: fail open to the normal Gemini path.
        db.rollback()
        logger.warning("Semantic lookup unavailable; falling back to LLM.", exc_info=True)
        return KnowledgeLookupResponse(found=False, source="llm_required")
    if match is None:
        return KnowledgeLookupResponse(found=False, source="llm_required")
    return KnowledgeLookupResponse(
        found=True,
        answer=match.answer,
        matched_question=match.question,
        similarity=round(match.similarity, 4),
        knowledge_id=match.id,
        source="semantic_cache",
    )
