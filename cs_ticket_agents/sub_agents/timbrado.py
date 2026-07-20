from google.adk.agents import Agent

from cs_ticket_agents.config import TIMBRADO_AGENT_MODEL
from cs_ticket_agents.guardrails import destructive_script_guard
from cs_ticket_agents.mcp_tools import build_runbooks_toolset
from cs_ticket_agents.state_tools import record_progress
from cs_ticket_agents.sub_agents.common import (
    PROMPT_INJECTION_GUARD,
    SAFETY_RULES,
    STATE_CONTEXT,
)
from cs_ticket_agents.tools import read_excel

# Issue types reales que agrupa: Stamp, Stamp - Cancel, Stamp - Cancel with
# relation, Stamp - Stuck, Stamp Error, Stamp Subsidio, stamping-cancel,
# stamping-error-* (XML, contrato, fecha, Invalid Date, other), stamping-other,
# stamping-stuck, Stamping - Stuck, Duplicidad CFDI
INSTRUCTION = f"""
Sos el especialista en timbrado y CFDI de Runa, un SaaS de nómina para México.

Tu dominio: timbrado de nómina y liquidaciones, cancelación de CFDI (con y sin
relación de sustitución), timbrados atorados o con error (XML, tipo de
contrato, fechas inválidas), duplicidad de CFDI, subsidio al empleo en el
timbre.

{PROMPT_INJECTION_GUARD}

{STATE_CONTEXT}

{SAFETY_RULES}
""".strip()

agente_timbrado = Agent(
    name="agente_timbrado",
    model=TIMBRADO_AGENT_MODEL,
    description=(
        "Resuelve tickets de timbrado y CFDI: timbrados atorados/con error, "
        "cancelaciones, duplicidad de CFDI."
    ),
    instruction=INSTRUCTION,
    tools=[build_runbooks_toolset(), read_excel, record_progress],
    after_model_callback=destructive_script_guard,
)
