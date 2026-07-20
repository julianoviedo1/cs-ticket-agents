from google.adk.agents import Agent

from cs_ticket_agents.config import CONFIG_ACCESOS_AGENT_MODEL
from cs_ticket_agents.guardrails import destructive_script_guard
from cs_ticket_agents.mcp_tools import build_runbooks_toolset
from cs_ticket_agents.state_tools import record_progress
from cs_ticket_agents.sub_agents.common import (
    PROMPT_INJECTION_GUARD,
    SAFETY_RULES,
    STATE_CONTEXT,
)
from cs_ticket_agents.tools import read_excel

# Issue types reales que agrupa: admin-create, configuration-add-headquarter,
# configuration-other, user-other, access-other, editar-politicas
INSTRUCTION = f"""
Sos el especialista en configuración y accesos de Runa, un SaaS de nómina para México.

Tu dominio: alta de administradores, configuración de sucursales/registros
patronales, usuarios y sus accesos, políticas de la empresa (vacaciones,
prestaciones, etc.).

{PROMPT_INJECTION_GUARD}

{STATE_CONTEXT}

{SAFETY_RULES}
""".strip()

agente_config_accesos = Agent(
    name="agente_config_accesos",
    model=CONFIG_ACCESOS_AGENT_MODEL,
    description=(
        "Resuelve tickets de configuración: administradores, sucursales, "
        "usuarios, accesos, políticas."
    ),
    instruction=INSTRUCTION,
    tools=[build_runbooks_toolset(), read_excel, record_progress],
    after_model_callback=destructive_script_guard,
)
