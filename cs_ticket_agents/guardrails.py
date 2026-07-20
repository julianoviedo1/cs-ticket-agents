"""Guardrail de salida: defensa en profundidad además de la regla en el
prompt ("nunca ejecutes, solo proponés"). v1 no tiene ninguna tool que
ejecute nada en producción — el riesgo real es que el sistema le entregue a
un humano un script de corrección con patrones evidentemente peligrosos sin
una advertencia explícita antes de que lo pegue en la consola.

Calibrado para no bloquear patrones legítimos que ya usamos en nuestros
propios runbooks (ej. `movement.mexico_movements_imss_reports.destroy_all`,
un destroy_all scoped a una asociación — está bien, es limpieza acotada).
Lo que sí bloquea:
- Escapes a shell/SO disfrazados de Ruby (backticks, system(), exec, etc.) —
  ningún runbook real los usa, cero falsos positivos esperados.
- destroy_all/delete_all sobre una CONSTANTE (Modelo.destroy_all) — barre
  toda la tabla, muy distinto de un destroy_all scoped a una asociación.
- DDL crudo (DROP TABLE, TRUNCATE) — nunca aparece en un one-liner legítimo
  de diagnóstico/corrección de nuestro dominio.
"""

from __future__ import annotations

import re

from google.adk.agents.callback_context import CallbackContext
from google.adk.models.llm_response import LlmResponse
from google.genai import types

_DESTRUCTIVE_PATTERNS = {
    "shell exec (backticks)": re.compile(r"`[^`]+`"),
    "shell exec (system/exec/popen)": re.compile(
        r"\b(system|exec|IO\.popen|Kernel\.system|%x)\s*[\(\{]", re.IGNORECASE
    ),
    "destroy_all/delete_all sin scope (Modelo.destroy_all)": re.compile(
        r"\b[A-Z][A-Za-z0-9_]*\.(destroy_all|delete_all)\b"
    ),
    "DDL crudo (DROP/TRUNCATE)": re.compile(
        r"\b(DROP\s+TABLE|DROP\s+DATABASE|TRUNCATE)\b", re.IGNORECASE
    ),
}


def _response_text(llm_response: LlmResponse) -> str:
    if not llm_response.content or not llm_response.content.parts:
        return ""
    return "".join(part.text or "" for part in llm_response.content.parts)


def destructive_script_guard(
    callback_context: CallbackContext, llm_response: LlmResponse
) -> LlmResponse | None:
    """after_model_callback: bloquea respuestas con patrones destructivos sin scope."""
    text = _response_text(llm_response)
    if not text:
        return None

    matches = [
        name for name, pattern in _DESTRUCTIVE_PATTERNS.items() if pattern.search(text)
    ]
    if not matches:
        return None

    warning = (
        "⚠️ GUARDRAIL: esta respuesta fue bloqueada automáticamente porque el "
        f"texto propuesto contiene patrones potencialmente destructivos sin "
        f"acotar ({', '.join(matches)}). No se muestra el contenido original — "
        "un humano tiene que revisar el diagnóstico manualmente antes de "
        "continuar. Si esto es un falso positivo (un patrón legítimo mal "
        "detectado), avisar para ajustar el guardrail."
    )
    return LlmResponse(
        content=types.Content(role="model", parts=[types.Part(text=warning)])
    )
