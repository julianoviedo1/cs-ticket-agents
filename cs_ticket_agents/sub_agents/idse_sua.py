from google.adk.agents import Agent

from cs_ticket_agents.config import IDSE_SUA_AGENT_MODEL
from cs_ticket_agents.guardrails import destructive_script_guard
from cs_ticket_agents.mcp_tools import build_runbooks_toolset
from cs_ticket_agents.state_tools import record_progress
from cs_ticket_agents.sub_agents.common import (
    PROMPT_INJECTION_GUARD,
    SAFETY_RULES,
    STATE_CONTEXT,
)
from cs_ticket_agents.tools import read_excel

# Issue types reales que agrupa (ver Desarrollo Customer Support - IssueTypes.csv):
# IDSE-edit, IDSE-Movimientos, IDSE-other, SUA - Other, Stuck - Sod,
# edit kardex - employee, edit-sdi, employee-edit-sbc, employee-edit-status,
# employee-edit-infonavit
INSTRUCTION = f"""
Sos el especialista en IDSE / SUA / Kardex de Runa, un SaaS de nómina para México.

Tu dominio: afiliación IMSS (movimientos, lotes IDSE, requests de Desereti,
pendientes de envío, fechas IMSS/date_imss, duplicados de movimientos),
SUA, ediciones de kardex (SDI, SBC, status del empleado, infonavit).

{PROMPT_INJECTION_GUARD}

{STATE_CONTEXT}

{SAFETY_RULES}
""".strip()

agente_idse_sua = Agent(
    name="agente_idse_sua",
    model=IDSE_SUA_AGENT_MODEL,
    description=(
        "Resuelve tickets de IDSE, SUA y kardex: movimientos afiliatorios, "
        "lotes, SDI/SBC, status del empleado, infonavit."
    ),
    instruction=INSTRUCTION,
    tools=[build_runbooks_toolset(), read_excel, record_progress],
    after_model_callback=destructive_script_guard,
)
