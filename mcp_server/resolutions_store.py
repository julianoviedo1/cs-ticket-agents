"""Índice append-only de tickets resueltos (JSONL) y búsqueda simple sobre él."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from mcp_server.runbook_store import tokenize  # reutiliza el mismo tokenizer

INDEX_PATH = Path(__file__).resolve().parent.parent / "resolutions" / "index.jsonl"

VALID_CATEGORIES = {"idse", "nomina", "variabilidad", "otro"}


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
    query_tokens = tokenize(query)
    if not query_tokens:
        return []
    scored = []
    for entry in load_all():
        haystack = " ".join(
            [
                entry.get("ticket_id", ""),
                entry.get("diagnosis", ""),
                entry.get("category", ""),
            ]
        )
        entry_tokens = tokenize(haystack)
        score = len(query_tokens & entry_tokens)
        if score > 0:
            scored.append((score, entry))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [entry for _, entry in scored[:limit]]
