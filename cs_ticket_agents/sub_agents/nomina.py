from google.adk.agents import Agent

from cs_ticket_agents.config import NOMINA_AGENT_MODEL
from cs_ticket_agents.mcp_tools import build_runbooks_toolset
from cs_ticket_agents.sub_agents.common import SAFETY_RULES
from cs_ticket_agents.tools import read_excel

INSTRUCTION = f"""
Sos el especialista en nómina de Runa, un SaaS de nómina para México.

Tu dominio: cálculo y percepciones de nómina, vacaciones y sus balances
(request_balances), variabilidad IMSS (SDI/SBC/SVAR, VariableProcess),
ISN y otros reportes fiscales, timbrado de CFDI y liquidaciones, y PTU
(reparto de utilidades).

{SAFETY_RULES}
""".strip()

agente_nomina = Agent(
    name="agente_nomina",
    model=NOMINA_AGENT_MODEL,
    description=(
        "Resuelve tickets de nómina: cálculos, percepciones, vacaciones, "
        "variabilidad IMSS, ISN, timbrado/liquidaciones, PTU."
    ),
    instruction=INSTRUCTION,
    tools=[build_runbooks_toolset(), read_excel],
)
