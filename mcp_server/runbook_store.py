"""Carga y búsqueda semántica (RAG, embeddings locales) sobre el repo de runbooks."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from mcp_server import embeddings

RUNBOOKS_DIR = Path(__file__).resolve().parent.parent / "runbooks"

# Cache de embeddings por runbook.id — se recalcula por proceso (reiniciar el
# servidor MCP recoge cambios en los .md). Evita re-embeber en cada consulta.
_EMBEDDING_CACHE: dict[str, list[float]] = {}


@dataclass
class Runbook:
    id: str
    title: str
    category: str
    tags: list[str]
    summary: str
    related: list[str]
    body: str
    path: Path

    def to_summary_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "category": self.category,
            "tags": self.tags,
            "summary": self.summary,
        }

    def to_full_dict(self) -> dict:
        return {
            **self.to_summary_dict(),
            "related": self.related,
            "body": self.body,
        }

    def embedding_text(self) -> str:
        return f"{self.title}\n{' '.join(self.tags)}\n{self.summary}\n{self.body}"


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    _, raw_frontmatter, body = parts
    metadata = yaml.safe_load(raw_frontmatter) or {}
    return metadata, body.strip()


def load_all() -> list[Runbook]:
    runbooks = []
    for path in sorted(RUNBOOKS_DIR.glob("*.md")):
        if path.name.lower() == "readme.md":
            continue
        metadata, body = _parse_frontmatter(path.read_text(encoding="utf-8"))
        runbooks.append(
            Runbook(
                id=metadata.get("id", path.stem),
                title=metadata.get("title", path.stem),
                category=metadata.get("category", "otro"),
                tags=metadata.get("tags") or [],
                summary=metadata.get("summary", ""),
                related=metadata.get("related") or [],
                body=body,
                path=path,
            )
        )
    return runbooks


def get_by_id(runbook_id: str) -> Runbook | None:
    for rb in load_all():
        if rb.id == runbook_id:
            return rb
    return None


def _get_embeddings(runbooks: list[Runbook]) -> dict[str, list[float]]:
    missing = [rb for rb in runbooks if rb.id not in _EMBEDDING_CACHE]
    if missing:
        vectors = embeddings.embed([rb.embedding_text() for rb in missing])
        for rb, vector in zip(missing, vectors, strict=True):
            _EMBEDDING_CACHE[rb.id] = vector
    return _EMBEDDING_CACHE


def search(query: str, limit: int = 5) -> list[dict]:
    """Retrieval semántico: similitud coseno entre el embedding de la query y
    el de cada runbook (título+tags+resumen+cuerpo)."""
    runbooks = load_all()
    if not runbooks:
        return []

    doc_embeddings = _get_embeddings(runbooks)
    query_vector = embeddings.embed_one(query)

    scored = [
        (embeddings.cosine_similarity(query_vector, doc_embeddings[rb.id]), rb)
        for rb in runbooks
    ]
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [
        {**rb.to_summary_dict(), "score": round(score, 4)}
        for score, rb in scored[:limit]
        if score > 0
    ]
