"""Listener: pull de la suscripción de Pub/Sub, parsea eventos de Chat, corre el orquestador.

Uso: uv run python -m listener.main
Requiere en .env: PUBSUB_PROJECT_ID, PUBSUB_SUBSCRIPTION_ID.
Opcional: CHAT_SERVICE_ACCOUNT_FILE (para descargar adjuntos).

Ver docs/chat_listener_setup.md para el setup de GCP + la Chat app.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

from dotenv import load_dotenv
from google.cloud import pubsub_v1

from listener.attachments import download_attachments
from listener.event_parser import build_ticket_text, parse_chat_event
from listener.ticket_runner import run_ticket

# Ruta explícita al .env de la raíz del proyecto, sin importar desde dónde se
# invoque este módulo (mismo motivo que en cs_ticket_agents/config.py).
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

POLL_INTERVAL_SECONDS = 5
MAX_MESSAGES_PER_PULL = 10


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(
            f"Falta la variable de entorno {name}. Ver docs/chat_listener_setup.md."
        )
    return value


def handle_message(data: bytes) -> None:
    ticket = parse_chat_event(data)
    if ticket is None:
        return  # evento que no es un mensaje nuevo (ADDED_TO_SPACE, CARD_CLICKED, etc.)

    service_account_file = os.environ.get("CHAT_SERVICE_ACCOUNT_FILE")
    attachment_paths: list[str] = []
    if ticket["attachments"] and service_account_file:
        attachment_paths = download_attachments(
            ticket["attachments"], service_account_file
        )

    ticket_text = build_ticket_text(ticket, attachment_paths)
    print(f"--- Nuevo ticket ({ticket.get('message_name')}) ---")
    response, _session_id = run_ticket(ticket_text)
    print(response)
    print("--- fin del ticket ---\n")


def main() -> None:
    project_id = _require_env("PUBSUB_PROJECT_ID")
    subscription_id = _require_env("PUBSUB_SUBSCRIPTION_ID")

    subscriber = pubsub_v1.SubscriberClient()
    subscription_path = subscriber.subscription_path(project_id, subscription_id)
    print(f"Escuchando (pull) en {subscription_path} cada {POLL_INTERVAL_SECONDS}s...")

    while True:
        response = subscriber.pull(
            request={
                "subscription": subscription_path,
                "max_messages": MAX_MESSAGES_PER_PULL,
            }
        )
        ack_ids = []
        for received in response.received_messages:
            try:
                handle_message(received.message.data)
            except Exception as exc:
                print(f"Error procesando mensaje: {exc}")
            ack_ids.append(received.ack_id)

        if ack_ids:
            subscriber.acknowledge(
                request={"subscription": subscription_path, "ack_ids": ack_ids}
            )

        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
