"""Servidor MCP propio: base de conocimiento de runbooks + índice de resoluciones.

Se ejecuta como subproceso vía stdio (McpToolset + StdioConnectionParams desde
los agentes ADK). Ver runbooks/README.md y resolutions/README.md para el
formato de datos.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from mcp_server import resolutions_store, runbook_store

mcp = FastMCP("cs-ticket-runbooks")


@mcp.tool()
def search_runbooks(query: str, limit: int = 5) -> list[dict]:
    """Busca runbooks relevantes por palabras clave (título, tags, cuerpo).

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
    """Busca tickets ya resueltos con patrón similar en el índice de resoluciones.

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
        category: una de "idse", "nomina", "variabilidad", "otro".
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
    mcp.run(transport="stdio")
