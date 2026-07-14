from google.adk.agents import Agent

from cs_ticket_agents.config import IDSE_AGENT_MODEL
from cs_ticket_agents.mcp_tools import build_runbooks_toolset
from cs_ticket_agents.sub_agents.common import SAFETY_RULES
from cs_ticket_agents.tools import read_excel

INSTRUCTION = f"""
Sos el especialista en IDSE (afiliación IMSS) de Runa, un SaaS de nómina para México.

Tu dominio: movimientos afiliatorios (Movement), lotes IDSE, requests de Desereti,
movimientos pendientes de envío, fechas IMSS (date_imss), duplicados de movimientos,
y todo lo relacionado con el intercambio de datos entre Runa y el IMSS.

{SAFETY_RULES}
""".strip()

agente_idse = Agent(
    name="agente_idse",
    model=IDSE_AGENT_MODEL,
    description=(
        "Resuelve tickets de movimientos IDSE: pendientes de envío, lotes, "
        "fechas IMSS, duplicados de movimientos afiliatorios."
    ),
    instruction=INSTRUCTION,
    tools=[build_runbooks_toolset(), read_excel],
)
