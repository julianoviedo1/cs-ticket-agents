from google.adk.agents import Agent

from cs_ticket_agents.config import PERFIL_EMPLEADO_AGENT_MODEL
from cs_ticket_agents.guardrails import destructive_script_guard
from cs_ticket_agents.mcp_tools import build_runbooks_toolset
from cs_ticket_agents.state_tools import record_progress
from cs_ticket_agents.sub_agents.common import (
    PROMPT_INJECTION_GUARD,
    SAFETY_RULES,
    STATE_CONTEXT,
)
from cs_ticket_agents.tools import read_excel

# Issue types reales que agrupa: employee-edit-cfdi4.0, employee-edit-
# direccionfiscal, employee-edit-email, employee-edit-salary, employee-edit-
# other, employee-create, employee-delete, employee deactivated,
# Edit-vacations, events-edit-other, events-other, app-asistencias
INSTRUCTION = f"""
Sos el especialista en perfil de empleado de Runa, un SaaS de nómina para México.

Tu dominio: alta/baja de empleados, edición de datos bloqueados del perfil
(sueldo bruto, CFDI 4.0, dirección fiscal, email), vacaciones y sus balances,
eventos/solicitudes, asistencias.

{PROMPT_INJECTION_GUARD}

{STATE_CONTEXT}

{SAFETY_RULES}
""".strip()

agente_perfil_empleado = Agent(
    name="agente_perfil_empleado",
    model=PERFIL_EMPLEADO_AGENT_MODEL,
    description=(
        "Resuelve tickets de perfil de empleado: alta/baja, edición de datos "
        "bloqueados, vacaciones, eventos, asistencias."
    ),
    instruction=INSTRUCTION,
    tools=[build_runbooks_toolset(), read_excel, record_progress],
    after_model_callback=destructive_script_guard,
)
