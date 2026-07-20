"""Tools compartidas para escribir en session.state (uso de state entre agentes).

El orquestador clasifica el ticket y registra el contexto antes de delegar
(set_ticket_context). Cada subagente registra su progreso en cada turno de
diagnóstico (record_progress), así si el humano responde con un dato de
consola en el siguiente turno, el subagente retoma con contexto ya armado
en vez de arrancar de cero.
"""

from google.adk.tools import ToolContext


def set_ticket_context(
    category: str,
    issue_type: str,
    detected_entities: dict,
    tool_context: ToolContext,
) -> dict:
    """Registra la clasificación del ticket en el state compartido antes de delegar.

    Llamar SIEMPRE antes de transferir el ticket al subagente correspondiente.

    Args:
        category: una de las categorías de subagente (idse_sua, nomina,
            timbrado, stp, perfil_empleado, config_accesos, otro).
        issue_type: el issue_type específico si se pudo inferir del texto del
            ticket (ej. "payroll-ptu", "Stamp - Cancel"), o "" si no aplica.
        detected_entities: entidades detectadas en el texto del ticket (ej.
            {"company_subdomain": "...", "employee_id": "...", "sub_company_id": "..."}).
            Usar claves vacías/omitir las que no se detectaron, no inventar valores.

    Returns:
        Confirmación de lo que quedó guardado en el state.
    """
    tool_context.state["category"] = category
    tool_context.state["issue_type"] = issue_type
    tool_context.state["detected_entities"] = detected_entities
    return {
        "status": "ok",
        "category": category,
        "issue_type": issue_type,
        "detected_entities": detected_entities,
    }


def record_progress(
    runbook_id: str,
    diagnosis_so_far: str,
    pending_question: str,
    tool_context: ToolContext,
) -> dict:
    """Registra el progreso del diagnóstico en el state, al final de cada turno.

    Llamar SIEMPRE al final de tu respuesta, tanto si el diagnóstico sigue en
    curso como si ya se resolvió.

    Args:
        runbook_id: id del runbook que se está usando, o "" si no hay ninguno aplicable.
        diagnosis_so_far: resumen acumulado de lo diagnosticado hasta ahora.
        pending_question: el dato de consola que le pediste al usuario y
            estás esperando, o "" si no hay ninguna pregunta pendiente.

    Returns:
        Confirmación de lo que quedó guardado en el state.
    """
    tool_context.state["runbook_id"] = runbook_id
    tool_context.state["diagnosis_so_far"] = diagnosis_so_far
    tool_context.state["pending_question"] = pending_question
    return {
        "status": "ok",
        "runbook_id": runbook_id,
        "pending_question": pending_question,
    }
