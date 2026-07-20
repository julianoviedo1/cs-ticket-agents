"""Índice append-only de tickets resueltos (JSONL) y búsqueda semántica (RAG) sobre él."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from mcp_server import embeddings

INDEX_PATH = Path(__file__).resolve().parent.parent / "resolutions" / "index.jsonl"

# Debe coincidir con las categorías que usa el orquestador en
# cs_ticket_agents/agent.py (ver set_ticket_context).
VALID_CATEGORIES = {
    "idse_sua",
    "nomina",
    "timbrado",
    "stp",
    "perfil_empleado",
    "config_accesos",
    "otro",
}


@dataclass
class Resolution:
    ticket_id: str
    runbook_id: str | None
    diagnosis: str
    script_proposed: str | None
    category: str
    logged_at: str


def append(
    ticket_id: str,
    diagnosis: str,
    category: str,
    runbook_id: str | None = None,
    script_proposed: str | None = None,
) -> Resolution:
    if category not in VALID_CATEGORIES:
        raise ValueError(
            f"category debe ser una de {sorted(VALID_CATEGORIES)}, recibido: {category!r}"
        )
    resolution = Resolution(
        ticket_id=ticket_id,
        runbook_id=runbook_id,
        diagnosis=diagnosis,
        script_proposed=script_proposed,
        category=category,
        logged_at=datetime.now(UTC).isoformat(),
    )
    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    with INDEX_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(resolution.__dict__, ensure_ascii=False) + "\n")
    return resolution


def load_all() -> list[dict]:
    if not INDEX_PATH.exists():
        return []
    resolutions = []
    with INDEX_PATH.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                resolutions.append(json.loads(line))
    return resolutions


def search(query: str, limit: int = 5) -> list[dict]:
    """Retrieval semántico sobre el índice de resoluciones.

    Nota: recalcula embeddings de todas las entradas en cada llamada — bien
    para el volumen actual (v1), pero si el índice crece mucho conviene
    cachear como se hizo en runbook_store.py (ver "trabajo futuro" del informe).
    """
    entries = load_all()
    if not entries:
        return []

    texts = [
        f"{e.get('ticket_id', '')} {e.get('diagnosis', '')} {e.get('category', '')}"
        for e in entries
    ]
    vectors = embeddings.embed(texts)
    query_vector = embeddings.embed_one(query)

    scored = [
        (embeddings.cosine_similarity(query_vector, vector), entry)
        for vector, entry in zip(vectors, entries, strict=True)
    ]
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [entry for score, entry in scored[:limit] if score > 0]
