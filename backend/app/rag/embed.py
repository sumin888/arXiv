from __future__ import annotations

import json
import logging
import threading
from typing import Any

from app.config import settings

# Transformers 4.50+ logs a verbose "BertModel LOAD REPORT" table for benign
# unexpected keys (e.g. embeddings.position_ids). It is noise for our use case.
logging.getLogger("transformers.utils.loading_report").setLevel(logging.ERROR)

_model_lock = threading.Lock()
_model: Any = None


def get_model():
    global _model
    with _model_lock:
        if _model is None:
            from sentence_transformers import SentenceTransformer

            _model = SentenceTransformer(settings.embedding_model)
        return _model


def embed_texts(texts: list[str], batch_size: int = 32) -> list[list[float]]:
    model = get_model()
    vectors = model.encode(
        texts,
        batch_size=batch_size,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    return [v.tolist() for v in vectors]


def embed_query(text: str) -> list[float]:
    return embed_texts([text])[0]


def embedding_to_json(vec: list[float]) -> str:
    return json.dumps(vec)
