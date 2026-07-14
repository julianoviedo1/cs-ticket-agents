"""Carga y búsqueda simple (keyword) sobre el repo de runbooks en markdown."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

RUNBOOKS_DIR = Path(__file__).resolve().parent.parent / "runbooks"

_WORD_RE = re.compile(r"[a-záéíóúñ0-9_]+", re.IGNORECASE)


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


def tokenize(text: str) -> set[str]:
    return {tok.lower() for tok in _WORD_RE.findall(text)}


def _score(runbook: Runbook, query_tokens: set[str]) -> int:
    # Título y tags pesan más que el cuerpo — coincidencias ahí son más específicas.
    title_tokens = tokenize(runbook.title) | {t.lower() for t in runbook.tags}
    body_tokens = tokenize(runbook.body) | tokenize(runbook.summary)
    score = 3 * len(query_tokens & title_tokens) + len(query_tokens & body_tokens)
    return score


def search(query: str, limit: int = 5) -> list[dict]:
    query_tokens = tokenize(query)
    if not query_tokens:
        return []
    scored = [(_score(rb, query_tokens), rb) for rb in load_all()]
    scored = [(score, rb) for score, rb in scored if score > 0]
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [{**rb.to_summary_dict(), "score": score} for score, rb in scored[:limit]]
