"""Normaliza un evento de Google Chat (entregado por Pub/Sub) a un dict de ticket.

Cuando una Chat app está configurada con entrega vía Pub/Sub, cada mensaje
nuevo en un Space donde la app es miembro llega como un evento JSON con esta
forma (documentado en la Google Chat API — eventos de tipo MESSAGE):

    {
      "type": "MESSAGE",
      "eventTime": "...",
      "message": {
        "name": "spaces/AAAA/messages/BBBB",
        "text": "cuerpo del mensaje",
        "createTime": "...",
        "sender": {"displayName": "...", "email": "..."},
        "space": {"name": "spaces/AAAA", "displayName": "Customer support"},
        "attachment": [ { "contentName": "...", "attachmentDataRef": {...} } ]
      }
    }

Otros tipos de evento (ADDED_TO_SPACE, REMOVED_FROM_SPACE, CARD_CLICKED, ...)
no son tickets — se descartan devolviendo None.
"""

from __future__ import annotations

import json


def parse_chat_event(raw_json: bytes | str) -> dict | None:
    """Parsea el payload de un evento de Chat App. None si no es un MESSAGE."""
    event = json.loads(raw_json)
    if event.get("type") != "MESSAGE":
        return None

    message = event.get("message", {})
    space = message.get("space") or event.get("space") or {}
    sender = message.get("sender", {})

    return {
        "message_name": message.get("name"),
        "space_name": space.get("name"),
        "space_display_name": space.get("displayName"),
        "sender_display_name": sender.get("displayName"),
        "sender_email": sender.get("email"),
        "text": message.get("text", ""),
        "attachments": message.get("attachment", []) or [],
        "create_time": message.get("createTime"),
    }


def build_ticket_text(ticket: dict, attachment_paths: list[str]) -> str:
    """Arma el texto que recibe el orquestador a partir del ticket normalizado."""
    lines = [
        f"[Ticket de Chat] Space: {ticket.get('space_display_name')}",
        f"De: {ticket.get('sender_display_name')} <{ticket.get('sender_email') or 'sin email'}>",
        "",
        ticket.get("text", ""),
    ]
    if attachment_paths:
        lines.append("")
        lines.append(
            "Adjuntos descargados (rutas absolutas, usá read_excel si aplica):"
        )
        lines.extend(f"- {path}" for path in attachment_paths)
    return "\n".join(lines)
