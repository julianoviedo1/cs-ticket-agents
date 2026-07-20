"""Genera traces localmente (bypass de `agents-cli eval generate`).

El SDK de evaluación de Vertex AI intenta introspeccionar cada tool del agente
como si fuera una función Python simple (para armar `agent_data.agents`), y
no sabe manejar `McpToolset` — rompe con
`TypeError: McpToolset object is not a callable object` en cualquiera de
nuestros 7 subagentes. Este script corre el mismo Runner que usa
listener/ticket_runner.py, capturando el trace completo (incluye
function_call/function_response) en el formato que espera
`agents-cli eval grade --traces ...` — que sí opera solo sobre el JSON, sin
volver a tocar el agente en vivo.

Uso: uv run python tests/eval/scripts/generate_traces.py
"""

from __future__ import annotations

import asyncio
import json
import uuid
from pathlib import Path

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from cs_ticket_agents.agent import root_agent

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
DATASET_PATH = PROJECT_ROOT / "tests" / "eval" / "datasets" / "basic-dataset.json"
OUTPUT_PATH = PROJECT_ROOT / "artifacts" / "traces" / "manual_trace.json"

APP_NAME = "cs_ticket_agents"
USER_ID = "eval_runner"


def _content_to_dict(content: types.Content) -> dict:
    return content.model_dump(exclude_none=True, mode="json")


async def _run_case(
    case: dict, session_service: InMemorySessionService, runner: Runner
) -> dict:
    session_id = str(uuid.uuid4())
    await session_service.create_session(
        app_name=APP_NAME, user_id=USER_ID, session_id=session_id
    )

    prompt_content = types.Content.model_validate(case["prompt"])
    events = [{"author": "user", "content": _content_to_dict(prompt_content)}]

    async for event in runner.run_async(
        user_id=USER_ID,
        session_id=session_id,
        new_message=prompt_content,
    ):
        if event.content is None:
            continue
        events.append(
            {"author": event.author, "content": _content_to_dict(event.content)}
        )

    graded_case: dict = {
        "eval_case_id": case["eval_case_id"],
        "agent_data": {"turns": [{"turn_index": 0, "events": events}]},
    }
    if "reference" in case:
        graded_case["reference"] = case["reference"]
    return graded_case


async def main() -> None:
    dataset = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    session_service = InMemorySessionService()
    runner = Runner(
        agent=root_agent, app_name=APP_NAME, session_service=session_service
    )

    graded_cases = []
    for case in dataset["eval_cases"]:
        print(f"Generando traza para {case['eval_case_id']}...")
        graded_cases.append(await _run_case(case, session_service, runner))

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps({"eval_cases": graded_cases}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Trazas escritas en {OUTPUT_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
