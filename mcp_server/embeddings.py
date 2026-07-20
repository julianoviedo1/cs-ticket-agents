"""Embeddings locales (fastembed) para las tools de RAG.

Corre en CPU, sin llamar a ninguna API externa — evita sumar otro consumidor
más a la cuota de la API de Gemini solo para indexar/recuperar contexto.
Modelo multilingüe chico (0.22GB): nuestro contenido es en español.
"""

from __future__ import annotations

import numpy as np
from fastembed import TextEmbedding

_MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
_model: TextEmbedding | None = None


def _get_model() -> TextEmbedding:
    global _model
    if _model is None:
        _model = TextEmbedding(model_name=_MODEL_NAME)
    return _model


def embed(texts: list[str]) -> list[list[float]]:
    """Embebe una lista de textos. Determinista, sin llamadas de red."""
    return [vec.tolist() for vec in _get_model().embed(texts)]


def embed_one(text: str) -> list[float]:
    return embed([text])[0]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    a_arr, b_arr = np.array(a), np.array(b)
    denom = np.linalg.norm(a_arr) * np.linalg.norm(b_arr)
    if denom == 0:
        return 0.0
    return float(np.dot(a_arr, b_arr) / denom)
