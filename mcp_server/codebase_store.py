"""RAG sobre una porción acotada del código fuente de saas-rails-api.

Indexa (embeddings locales) modelos, servicios, controllers, queries e
interactors del namespace Mexico::, más el schema de la base de datos
(chunkeado por tabla). Asume que ambos repos son hermanos en el mismo
filesystem — cierto en desarrollo local; en producción/CI esto necesitaría
un mecanismo distinto (repo clonado en el mismo host, o un índice
pre-generado y versionado).
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

from mcp_server import embeddings

DEFAULT_SAAS_PATH = Path(__file__).resolve().parent.parent.parent / "saas-rails-api"
SAAS_RAILS_API_PATH = Path(
    os.environ.get("SAAS_RAILS_API_PATH", str(DEFAULT_SAAS_PATH))
)

# Namespace Mexico:: — acotado a lógica de negocio relevante para diagnóstico
# de tickets de CS. Se excluye deliberadamente spec/, views/, javascript/,
# decorators/serializers/validators (presentación/validación, menos
# relevantes) para mantener el corpus enfocado y rápido de indexar.
INCLUDE_DIRS = [
    "app/models/mexico",
    "app/services/mexico",
    "app/controllers/v1/mexico",
    "app/queries/mexico",
    "app/interactors/mexico",
]
SCHEMA_FILE = "db/schema.rb"

CHUNK_LINES = 60
OVERLAP_LINES = 10

_INDEX_CACHE: list[CodeChunk] | None = None
_EMBEDDING_CACHE: list[list[float]] | None = None


@dataclass
class CodeChunk:
    file_path: str  # relativo a la raíz de saas-rails-api
    start_line: int
    end_line: int
    text: str

    def to_dict(self) -> dict:
        return {
            "file_path": self.file_path,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "snippet": self.text,
        }


def _chunk_ruby_file(path: Path, rel_path: str) -> list[CodeChunk]:
    """Ventanas de líneas con solapamiento — no parseamos Ruby, es simple y
    suficiente para retrieval; el solapamiento evita cortar una definición
    justo en el borde del chunk."""
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    if not lines:
        return []

    chunks = []
    step = CHUNK_LINES - OVERLAP_LINES
    start = 0
    while start < len(lines):
        end = min(start + CHUNK_LINES, len(lines))
        text = "\n".join(lines[start:end])
        if text.strip():
            chunks.append(CodeChunk(rel_path, start + 1, end, text))
        if end == len(lines):
            break
        start += step
    return chunks


def _chunk_schema(path: Path) -> list[CodeChunk]:
    """Un chunk por tabla (create_table ... do |t| ... end) — cada bloque es
    una unidad semántica natural, a diferencia de una ventana de líneas fija."""
    text = path.read_text(encoding="utf-8", errors="ignore")
    chunks = []
    pattern = re.compile(r' {2}create_table "([a-zA-Z0-9_]+)".*?\n {2}end\n', re.DOTALL)
    for match in pattern.finditer(text):
        table_name = match.group(1)
        start_line = text[: match.start()].count("\n") + 1
        end_line = start_line + match.group(0).count("\n")
        chunks.append(
            CodeChunk(
                f"db/schema.rb#{table_name}", start_line, end_line, match.group(0)
            )
        )
    return chunks


def _build_index() -> list[CodeChunk]:
    chunks: list[CodeChunk] = []

    for include_dir in INCLUDE_DIRS:
        base = SAAS_RAILS_API_PATH / include_dir
        if not base.exists():
            continue
        for rb_file in sorted(base.rglob("*.rb")):
            rel = str(rb_file.relative_to(SAAS_RAILS_API_PATH))
            chunks.extend(_chunk_ruby_file(rb_file, rel))

    schema_path = SAAS_RAILS_API_PATH / SCHEMA_FILE
    if schema_path.exists():
        chunks.extend(_chunk_schema(schema_path))

    return chunks


def _get_index() -> tuple[list[CodeChunk], list[list[float]]]:
    global _INDEX_CACHE, _EMBEDDING_CACHE
    if _INDEX_CACHE is None:
        _INDEX_CACHE = _build_index()
        _EMBEDDING_CACHE = (
            embeddings.embed([chunk.text for chunk in _INDEX_CACHE])
            if _INDEX_CACHE
            else []
        )
    return _INDEX_CACHE, _EMBEDDING_CACHE


def warm_index() -> int:
    """Fuerza la construcción del índice ahora (~1 min para ~1800 chunks).

    Llamar al arrancar el servidor MCP, no esperar al primer search(): el
    cliente MCP (McpToolset) tiene un timeout corto para llamadas a tools —
    la primera búsqueda real fallaría por timeout si el índice se construye
    de forma perezosa en esa misma llamada.

    Returns:
        Cantidad de chunks indexados.
    """
    chunks, _ = _get_index()
    return len(chunks)


def search(query: str, limit: int = 5) -> list[dict]:
    chunks, vectors = _get_index()
    if not chunks:
        return []

    query_vector = embeddings.embed_one(query)
    scored = [
        (embeddings.cosine_similarity(query_vector, vector), chunk)
        for vector, chunk in zip(vectors, chunks, strict=True)
    ]
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [
        {**chunk.to_dict(), "score": round(score, 4)}
        for score, chunk in scored[:limit]
        if score > 0
    ]
