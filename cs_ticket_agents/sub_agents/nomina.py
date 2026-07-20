from google.adk.agents import Agent

from cs_ticket_agents.config import NOMINA_AGENT_MODEL
from cs_ticket_agents.guardrails import destructive_script_guard
from cs_ticket_agents.mcp_tools import build_runbooks_toolset
from cs_ticket_agents.state_tools import record_progress
from cs_ticket_agents.sub_agents.common import (
    PROMPT_INJECTION_GUARD,
    SAFETY_RULES,
    STATE_CONTEXT,
)
from cs_ticket_agents.tools import read_excel

# Issue types reales que agrupa: payroll-create, payroll-edit ISN,
# payroll-edit-other, payroll-error-other, payroll-error-stuck-other,
# payroll-other, payroll-ptu, payroll-receipt-generate, payroll-receipt-other,
# payroll-stuck, payroll-edit-concepts, nominista - calculation/review/meet,
# Payroll Review - ISR, Payroll Review - Cuotas IMSS, Reporte CEP,
# report-error, Rastreo
INSTRUCTION = f"""
Sos el especialista en nómina de Runa, un SaaS de nómina para México.

Tu dominio: cálculo y percepciones de nómina, "planchado" de conceptos,
variabilidad IMSS (SDI/SBC/SVAR, VariableProcess), ISN, PTU (reparto de
utilidades), recibos de nómina, reportes fiscales (CEP, Rastreo), y revisión
de nóminas atoradas o con errores de cálculo.

{PROMPT_INJECTION_GUARD}

{STATE_CONTEXT}

{SAFETY_RULES}
""".strip()

agente_nomina = Agent(
    name="agente_nomina",
    model=NOMINA_AGENT_MODEL,
    description=(
        "Resuelve tickets de nómina: cálculos, percepciones, ISN, PTU, "
        "recibos, reportes fiscales, nóminas atoradas."
    ),
    instruction=INSTRUCTION,
    tools=[build_runbooks_toolset(), read_excel, record_progress],
    after_model_callback=destructive_script_guard,
)
