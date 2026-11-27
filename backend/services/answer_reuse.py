"""User-scoped semantic answer lookup and explicitly approved cache writes."""
import os
import re
import uuid
from dataclasses import dataclass
from typing import Sequence

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from database.models import KnowledgeEmbedding
from embeddings.e5 import MODEL_NAME, embed_passage, embed_query

# Only stable informational guidance can be reused. Never cache actions or workflows.
REUSABLE_INTENTS = frozenset({"GENERAL_QUESTION"})
DEFAULT_SIMILARITY_THRESHOLD = 0.88
MIN_QUALITY_SCORE = 0.80


@dataclass(frozen=True)
class ReusableAnswer:
    id: uuid.UUID
    answer: str
    question: str
    similarity: float
    intent: str | None
    language: str


def normalize_question(question: str) -> str:
    return re.sub(r"\\s+", " ", question).strip().casefold()


def _threshold() -> float:
    try:
        value = float(os.getenv("ANSWER_CACHE_SIMILARITY_THRESHOLD", str(DEFAULT_SIMILARITY_THRESHOLD)))
    except ValueError as error:
        raise RuntimeError("ANSWER_CACHE_SIMILARITY_THRESHOLD must be a number from 0 to 1.") from error
    if not 0.0 <= value <= 1.0:
        raise RuntimeError("ANSWER_CACHE_SIMILARITY_THRESHOLD must be between 0 and 1.")
    return value


def find_reusable_answer(
    db: Session,
    *,
    user_id: uuid.UUID,
    question: str,
    intent: str,
    language: str | None = None,
    limit: int = 5,
) -> ReusableAnswer | None:
    """Return a high-quality same-user answer only when intent and similarity pass."""
    if intent not in REUSABLE_INTENTS:
        return None
    normalized = normalize_question(question)
    if not normalized:
        return None

    vector = embed_query(normalized)
    distance = KnowledgeEmbedding.embedding.cosine_distance(vector)
    statement = (
        select(KnowledgeEmbedding, distance.label("distance"))
        .where(
            KnowledgeEmbedding.is_active.is_(True),
            KnowledgeEmbedding.quality_score.is_not(None),
            KnowledgeEmbedding.quality_score >= MIN_QUALITY_SCORE,
            KnowledgeEmbedding.intent == intent,
            *([KnowledgeEmbedding.language == language] if language else []),
            or_(
                (KnowledgeEmbedding.visibility == "private") & (KnowledgeEmbedding.user_id == user_id),
                (KnowledgeEmbedding.visibility == "shared") & (KnowledgeEmbedding.user_id.is_(None)),
            ) if os.getenv("ENABLE_SHARED_KNOWLEDGE", "false").lower() == "true" else (
                (KnowledgeEmbedding.visibility == "private") & (KnowledgeEmbedding.user_id == user_id)
            ),
        )
        .order_by(distance.asc())
        .limit(max(1, min(limit, 10)))
    )
    result = db.execute(statement).first()
    if result is None:
        return None

    entry, raw_distance = result
    similarity = max(-1.0, min(1.0, 1.0 - float(raw_distance)))
    if similarity < _threshold():
        return None

    entry.reuse_count += 1
    db.flush()
    return ReusableAnswer(
        id=entry.id,
        answer=entry.answer,
        question=entry.question,
        similarity=similarity,
        intent=entry.intent,
        language=entry.language,
    )


def store_approved_answer(
    db: Session,
    *,
    user_id: uuid.UUID,
    question: str,
    answer: str,
    intent: str,
    language: str = "en",
    quality_score: float,
    source_message_id: uuid.UUID | None = None,
) -> KnowledgeEmbedding:
    """Store a reviewed, stable informational answer; never call from an untrusted client."""
    if intent not in REUSABLE_INTENTS:
        raise ValueError(f"Intent {intent!r} is not eligible for semantic answer reuse.")
    if not question.strip() or not answer.strip():
        raise ValueError("Question and answer must not be empty.")
    if not MIN_QUALITY_SCORE <= quality_score <= 1.0:
        raise ValueError(f"quality_score must be between {MIN_QUALITY_SCORE} and 1.0.")
    normalized = normalize_question(question)
    embedding = embed_passage(f"Question: {normalized}\\nAnswer: {answer.strip()}")
    record = KnowledgeEmbedding(
        user_id=user_id,
        source_message_id=source_message_id,
        question=question.strip(),
        normalized_question=normalized,
        answer=answer.strip(),
        intent=intent,
        language=language,
        embedding_model=MODEL_NAME,
        embedding=embedding,
        visibility="private",
        quality_score=quality_score,
        is_active=True,
    )
    db.add(record)
    db.flush()
    return record
