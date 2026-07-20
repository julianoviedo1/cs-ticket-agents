from google.adk.agents import Agent

from cs_ticket_agents.config import STP_AGENT_MODEL
from cs_ticket_agents.guardrails import destructive_script_guard
from cs_ticket_agents.mcp_tools import build_runbooks_toolset
from cs_ticket_agents.state_tools import record_progress
from cs_ticket_agents.sub_agents.common import (
    PROMPT_INJECTION_GUARD,
    SAFETY_RULES,
    STATE_CONTEXT,
)
from cs_ticket_agents.tools import read_excel

# Issue types reales que agrupa: stp - statements, stp-other,
# stp-stuck-payment, devolucion-stp, Payment - Stuck
INSTRUCTION = f"""
Sos el especialista en STP (dispersión de pagos) de Runa, un SaaS de nómina para México.

Tu dominio: statements de STP, pagos atorados o no dispersados, devoluciones
de STP.

{PROMPT_INJECTION_GUARD}

{STATE_CONTEXT}

{SAFETY_RULES}
""".strip()

agente_stp = Agent(
    name="agente_stp",
    model=STP_AGENT_MODEL,
    description="Resuelve tickets de STP: statements, pagos atorados, devoluciones.",
    instruction=INSTRUCTION,
    tools=[build_runbooks_toolset(), read_excel, record_progress],
    after_model_callback=destructive_script_guard,
)
