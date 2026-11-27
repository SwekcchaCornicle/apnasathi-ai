"""Local multilingual E5 embeddings via FastEmbed (CPU/ONNX, no hosted API)."""
import math
import os
from functools import lru_cache
from typing import Iterable

from fastembed import TextEmbedding
from fastembed.common.model_description import ModelSource, PoolingType

DEFAULT_MODEL_NAME = "Xenova/multilingual-e5-base"
MODEL_NAME = os.getenv("EMBEDDING_MODEL", DEFAULT_MODEL_NAME)
EXPECTED_DIMENSIONS = 768


@lru_cache(maxsize=1)
def _model() -> TextEmbedding:
    """Load model lazily so app startup does not download weights or block health checks."""
    if MODEL_NAME == DEFAULT_MODEL_NAME and not any(
        entry["model"] == MODEL_NAME for entry in TextEmbedding.list_supported_models()
    ):
        TextEmbedding.add_custom_model(
            model=MODEL_NAME,
            pooling=PoolingType.MEAN,
            normalization=True,
            sources=ModelSource(hf=MODEL_NAME),
            dim=EXPECTED_DIMENSIONS,
            model_file="onnx/model_quantized.onnx",
        )
    return TextEmbedding(model_name=MODEL_NAME, cache_dir=os.getenv("FASTEMBED_CACHE_PATH"), threads=2)


def _normalize(vector: Iterable[float]) -> list[float]:
    values = [float(value) for value in vector]
    if len(values) != EXPECTED_DIMENSIONS:
        raise RuntimeError(f"Embedding model returned {len(values)} dimensions; expected {EXPECTED_DIMENSIONS}.")
    norm = math.sqrt(sum(value * value for value in values))
    if not norm or not math.isfinite(norm):
        raise RuntimeError("Embedding model returned a zero or non-finite vector.")
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
