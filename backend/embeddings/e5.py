"""Local multilingual E5 embeddings via FastEmbed (CPU/ONNX, no hosted API)."""
import math
import os
from functools import lru_cache
from typing import Iterable

from fastembed import TextEmbedding

MODEL_NAME = os.getenv("EMBEDDING_MODEL", "intfloat/multilingual-e5-base")
EXPECTED_DIMENSIONS = 768


@lru_cache(maxsize=1)
def _model() -> TextEmbedding:
    """Load model lazily so app startup does not download weights or block health checks."""
    return TextEmbedding(model_name=MODEL_NAME, cache_dir=os.getenv("FASTEMBED_CACHE_PATH"))


def _normalize(vector: Iterable[float]) -> list[float]:
    values = [float(value) for value in vector]
    if len(values) != EXPECTED_DIMENSIONS:
        raise RuntimeError(f"Embedding model returned {len(values)} dimensions; expected {EXPECTED_DIMENSIONS}.")
    norm = math.sqrt(sum(value * value for value in values))
    if not norm:
        raise RuntimeError("Embedding model returned a zero vector.")
    return [value / norm for value in values]


def embed_query(text: str) -> list[float]:
    """Encode a search query using the E5 query instruction prefix."""
    cleaned = text.strip()
    if not cleaned:
        raise ValueError("Query cannot be empty.")
    vector = next(_model().embed([f"query: {cleaned}"]))
    return _normalize(vector)


def embed_passage(text: str) -> list[float]:
    """Encode a reusable question/answer passage using the E5 passage prefix."""
    cleaned = text.strip()
    if not cleaned:
        raise ValueError("Passage cannot be empty.")
    vector = next(_model().embed([f"passage: {cleaned}"]))
    return _normalize(vector)
