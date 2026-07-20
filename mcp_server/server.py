"""Servidor MCP propio: RAG sobre runbooks, resoluciones y código fuente.

Se ejecuta como subproceso vía stdio (McpToolset + StdioConnectionParams desde
los agentes ADK). Ver runbooks/README.md y resolutions/README.md para el
formato de datos, y mcp_server/codebase_store.py para el alcance del índice
de código.
"""

from __future__ import annotations

import sys

from mcp.server.fastmcp import FastMCP

from mcp_server import codebase_store, resolutions_store, runbook_store

mcp = FastMCP("cs-ticket-runbooks")


@mcp.tool()
def search_runbooks(query: str, limit: int = 5) -> list[dict]:
    """Busca runbooks relevantes por similitud semántica (RAG, embeddings).

    Args:
        query: texto o palabras clave del ticket (ej. "movimientos IDSE pendientes lote enviado").
        limit: máximo de resultados a devolver.

    Returns:
        Lista de runbooks candidatos (id, title, category, tags, summary, score),
        ordenados por relevancia descendente. Lista vacía si no hay coincidencias
        — en ese caso no inventar un runbook, escalar el ticket.
    """
    return runbook_store.search(query, limit=limit)


@mcp.tool()
def get_runbook(runbook_id: str) -> dict:
    """Devuelve el contenido completo de un runbook por id.

    Args:
        runbook_id: id exacto devuelto por search_runbooks.

    Returns:
        Runbook completo (incluye el cuerpo en markdown con diagnóstico y
        corrección propuesta) o un dict con "error" si no existe ese id.
    """
    runbook = runbook_store.get_by_id(runbook_id)
    if runbook is None:
        return {"error": f"No existe un runbook con id {runbook_id!r}"}
    return runbook.to_full_dict()


@mcp.tool()
def find_similar_tickets(query: str, limit: int = 5) -> list[dict]:
    """Busca tickets ya resueltos con patrón similar (RAG sobre el índice de resoluciones).

    Útil para tickets sin runbook aplicable: puede existir un caso previo
    similar aunque nunca se haya formalizado como runbook.

    Args:
        query: texto o palabras clave del ticket actual.
        limit: máximo de resultados a devolver.

    Returns:
        Lista de resoluciones pasadas (ticket_id, runbook_id, diagnosis,
        script_proposed, category, logged_at), ordenadas por relevancia.
    """
    return resolutions_store.search(query, limit=limit)


@mcp.tool()
def search_codebase(query: str, limit: int = 5) -> list[dict]:
    """Busca fragmentos relevantes del código fuente de saas-rails-api (RAG).

    Indexa modelos, servicios, controllers, queries e interactors del
    namespace Mexico::, más el schema de la base de datos. Útil cuando el
    runbook no alcanza y hace falta entender el comportamiento real de un
    modelo/servicio (ej. qué hace un callback, qué columnas tiene una tabla).

    Args:
        query: descripción de lo que se busca (ej. "callback que recalcula
            SDI al guardar un movement de kardex", "columnas de la tabla
            employee_payrolls").
        limit: máximo de fragmentos a devolver.

    Returns:
        Lista de fragmentos (file_path, start_line, end_line, snippet, score),
        ordenados por relevancia descendente. El código es de solo lectura —
        nunca asumas que un fragmento retornado está actualizado al segundo,
        podría haber cambiado desde que se indexó.
    """
    return codebase_store.search(query, limit=limit)


@mcp.tool()
def log_resolution(
    ticket_id: str,
    diagnosis: str,
    category: str,
    runbook_id: str | None = None,
    script_proposed: str | None = None,
) -> dict:
    """Registra la resolución de un ticket en el índice (aprendizaje continuo).

    Llamar siempre al final del diagnóstico, incluso si no se encontró un
    runbook aplicable (en ese caso runbook_id=None) — así el ticket queda
    disponible para find_similar_tickets y como semilla de un futuro runbook.

    Args:
        ticket_id: identificador del ticket (asunto del mail o ID interno).
        diagnosis: resumen del diagnóstico llegado.
        category: una de "idse_sua", "nomina", "timbrado", "stp",
            "perfil_empleado", "config_accesos", "otro".
        runbook_id: id del runbook usado, si hubo uno aplicable.
        script_proposed: one-liners propuestos para consola, si corresponde.

    Returns:
        La entrada registrada, con logged_at (timestamp UTC).
    """
    resolution = resolutions_store.append(
        ticket_id=ticket_id,
        diagnosis=diagnosis,
        category=category,
        runbook_id=runbook_id,
        script_proposed=script_proposed,
    )
    return resolution.__dict__


if __name__ == "__main__":
    # Indexar ANTES de levantar el transporte stdio: el cliente MCP tiene un
    # timeout corto por tool call, y la primera búsqueda real fallaría si el
    # índice (~1 min) se construyera recién ahí. Log a stderr — stdout es el
    # canal del protocolo MCP, no se puede ensuciar con prints.
    chunk_count = codebase_store.warm_index()
    print(
        f"[cs-ticket-runbooks] código indexado: {chunk_count} chunks", file=sys.stderr
    )
    mcp.run(transport="stdio")
