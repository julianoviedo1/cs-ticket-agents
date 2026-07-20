"""Bridge HTTP local para desarrollo: expone el orquestador a cs-tickets-web (Rails).

Deliberadamente separado de cs_ticket_agents/fast_api_app.py (el entrypoint de
Cloud Run, que exige credenciales de GCP para Cloud Logging/artefactos). Este
módulo no tiene dependencias de nube — solo envuelve listener/ticket_runner.py
en un endpoint HTTP mínimo para que Rails no tenga que hablar el protocolo
nativo de sesiones de ADK.

Uso: uv run uvicorn api.local_bridge:app --port 8001 --reload
"""

from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel

from listener.ticket_runner import run_ticket_async

app = FastAPI(title="cs-ticket-agents (local bridge)")


class ProcessTicketRequest(BaseModel):
    ticket_text: str
    session_id: str | None = None


class ProcessTicketResponse(BaseModel):
    response: str
    session_id: str | None = None


@app.post("/process_ticket", response_model=ProcessTicketResponse)
async def process_ticket(req: ProcessTicketRequest) -> ProcessTicketResponse:
    """Corre el orquestador sobre un ticket y devuelve la respuesta final.

    Si se pasa session_id, continúa esa conversación (por ejemplo, para
    responderle al agente con el output de una consulta de consola que pidió).
    Si se omite, arranca una sesión nueva; su id siempre vuelve en la
    respuesta para que el caller pueda continuar la conversación después.
    """
    response, session_id = await run_ticket_async(
        req.ticket_text, session_id=req.session_id
    )
    return ProcessTicketResponse(response=response, session_id=session_id)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
