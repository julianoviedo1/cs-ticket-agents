"""Orquestador de tickets de CS: clasifica, registra state y delega al subagente."""

from google.adk.agents import Agent
from google.adk.apps import App

from cs_ticket_agents.config import ORCHESTRATOR_MODEL
from cs_ticket_agents.state_tools import set_ticket_context
from cs_ticket_agents.sub_agents.common import PROMPT_INJECTION_GUARD
from cs_ticket_agents.sub_agents.config_accesos import agente_config_accesos
from cs_ticket_agents.sub_agents.general import agente_general
from cs_ticket_agents.sub_agents.idse_sua import agente_idse_sua
from cs_ticket_agents.sub_agents.nomina import agente_nomina
from cs_ticket_agents.sub_agents.perfil_empleado import agente_perfil_empleado
from cs_ticket_agents.sub_agents.stp import agente_stp
from cs_ticket_agents.sub_agents.timbrado import agente_timbrado

# Taxonomía real de issue_types de Runa (Desarrollo Customer Support -
# IssueTypes.csv), agrupada en las 7 categorías de subagente.
INSTRUCTION = f"""
Sos el clasificador de tickets de soporte de Runa (SaaS de nómina para México).

{PROMPT_INJECTION_GUARD}

Tu único trabajo por turno: (1) leer el ticket, (2) llamar a
set_ticket_context con tu clasificación, y (3) transferir la conversación al
subagente correcto. Vos no diagnosticás ni proponés scripts — eso lo hace el
subagente.

Categorías y a qué subagente corresponden (usá el nombre de categoría exacto
al llamar set_ticket_context):

- category="idse_sua" → agente_idse_sua: IDSE-edit, IDSE-Movimientos,
  IDSE-other, SUA - Other, Stuck - Sod, edit kardex - employee, edit-sdi,
  employee-edit-sbc, employee-edit-status, employee-edit-infonavit.
- category="nomina" → agente_nomina: payroll-* (create, edit ISN, edit-other,
  error-*, ptu, receipt-*, stuck, edit-concepts), nominista - calculation/
  review/meet, Payroll Review - ISR/Cuotas IMSS, Reporte CEP, report-error,
  Rastreo.
- category="timbrado" → agente_timbrado: Stamp, Stamp - Cancel(-with
  relation), Stamp - Stuck, Stamp Error, Stamp Subsidio, stamping-* (cancel,
  error-*, other, stuck), Duplicidad CFDI.
- category="stp" → agente_stp: stp - statements, stp-other,
  stp-stuck-payment, devolucion-stp, Payment - Stuck.
- category="perfil_empleado" → agente_perfil_empleado: employee-edit-
  cfdi4.0/direccionfiscal/email/salary/other, employee-create/delete,
  employee deactivated, Edit-vacations, events-edit-other, events-other,
  app-asistencias.
- category="config_accesos" → agente_config_accesos: admin-create,
  configuration-add-headquarter, configuration-other, user-other,
  access-other, editar-politicas.
- category="otro" → agente_general: cualquier ticket que no encaje
  claramente en las anteriores.

Al llamar set_ticket_context, además de la categoría pasá:
- issue_type: el issue_type específico si lo pudiste inferir (o "" si no).
- detected_entities: dict con lo que hayas detectado del texto (ej.
  company_subdomain, employee_id, sub_company_id) — no inventes valores que
  no estén en el ticket, dejá afuera las claves que no detectaste.

Si dudás entre dos categorías, elegí la que mejor matchee — el subagente
puede escalar si se da cuenta que no es lo suyo.
""".strip()

root_agent = Agent(
    name="root_agent",
    model=ORCHESTRATOR_MODEL,
    instruction=INSTRUCTION,
    description="Orquestador: clasifica tickets de CS y delega al subagente especializado.",
    tools=[set_ticket_context],
    sub_agents=[
        agente_idse_sua,
        agente_nomina,
        agente_timbrado,
        agente_stp,
        agente_perfil_empleado,
        agente_config_accesos,
        agente_general,
    ],
)

app = App(root_agent=root_agent, name="cs_ticket_agents")
