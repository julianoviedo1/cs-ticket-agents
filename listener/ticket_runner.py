"""Invoca el orquestador ADK con un ticket normalizado, vía Runner API en proceso.

No usamos el endpoint HTTP /run de ADK a propósito: el listener corre en el
mismo proceso Python que el paquete de agentes, así que invocar el Runner
directamente evita levantar y mantener un segundo servidor.
"""

from __future__ import annotations

import asyncio
import uuid

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from cs_ticket_agents.agent import root_agent

APP_NAME = "cs_ticket_agents"
USER_ID = "cs_ticket_listener"

_session_service = InMemorySessionService()
_runner = Runner(agent=root_agent, app_name=APP_NAME, session_service=_session_service)


async def run_ticket_async(ticket_text: str, session_id: str | None = None) -> str:
    """Corre el orquestador sobre un ticket; devuelve la respuesta final concatenada."""
    session_id = session_id or str(uuid.uuid4())
    await _session_service.create_session(
        app_name=APP_NAME, user_id=USER_ID, session_id=session_id
    )

    final_text_parts = []
    async for event in _runner.run_async(
        user_id=USER_ID,
        session_id=session_id,
        new_message=types.Content(
            role="user", parts=[types.Part.from_text(text=ticket_text)]
        ),
    ):
        if event.is_final_response() and event.content and event.content.parts:
            final_text_parts.append(event.content.parts[0].text or "")

    return "\n".join(final_text_parts)


def run_ticket(ticket_text: str, session_id: str | None = None) -> str:
    return asyncio.run(run_ticket_async(ticket_text, session_id=session_id))
