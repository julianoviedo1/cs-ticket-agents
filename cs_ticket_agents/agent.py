"""Orquestador de tickets de CS: clasifica y delega al subagente especializado."""

from google.adk.agents import Agent
from google.adk.apps import App

from cs_ticket_agents.config import ORCHESTRATOR_MODEL
from cs_ticket_agents.sub_agents.general import agente_general
from cs_ticket_agents.sub_agents.idse import agente_idse
from cs_ticket_agents.sub_agents.nomina import agente_nomina

INSTRUCTION = """
Sos el clasificador de tickets de soporte de Runa (SaaS de nómina para México).

Tu único trabajo es leer el ticket (asunto, cuerpo y adjuntos ya parseados, si
los hay) y transferir la conversación al subagente correcto. Vos no
diagnosticás ni proponés scripts — eso lo hace el subagente.

- agente_idse: movimientos afiliatorios, lotes IDSE, fechas IMSS, duplicados de movimientos.
- agente_nomina: cálculos de nómina, percepciones, vacaciones, variabilidad IMSS, ISN, timbrado/liquidaciones, PTU.
- agente_general: cualquier otro ticket que no encaje claramente en los anteriores.

Si dudás entre dos categorías, elegí la que mejor matchee — el subagente puede
escalar si se da cuenta que no es lo suyo.
""".strip()

root_agent = Agent(
    name="root_agent",
    model=ORCHESTRATOR_MODEL,
    instruction=INSTRUCTION,
    description="Orquestador: clasifica tickets de CS y delega al subagente especializado.",
    sub_agents=[agente_idse, agente_nomina, agente_general],
)

app = App(root_agent=root_agent, name="cs_ticket_agents")
