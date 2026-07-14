"""Descarga adjuntos de un mensaje de Google Chat vía service account.

NOTA: el método exacto de descarga (client.media().download(...)) está
documentado por la Google Chat API pero no se pudo validar contra un Space
real todavía (requiere la Chat app ya agregada a un Space — ver
docs/chat_listener_setup.md). Verificar este método en la primera prueba
end-to-end real y ajustar si el nombre del recurso difiere.
"""

from __future__ import annotations

import io
import tempfile
from pathlib import Path

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

SCOPES = ["https://www.googleapis.com/auth/chat.bot"]


def _build_chat_client(service_account_file: str):
    credentials = service_account.Credentials.from_service_account_file(
        service_account_file, scopes=SCOPES
    )
    return build("chat", "v1", credentials=credentials, cache_discovery=False)


def download_attachments(
    attachments: list[dict], service_account_file: str
) -> list[str]:
    """Descarga cada adjunto a un archivo temporal; devuelve rutas absolutas."""
    if not attachments:
        return []

    client = _build_chat_client(service_account_file)
    tmp_dir = Path(tempfile.mkdtemp(prefix="cs_ticket_attachments_"))
    paths = []

    for attachment in attachments:
        resource_name = (attachment.get("attachmentDataRef") or {}).get("resourceName")
        content_name = attachment.get("contentName", "adjunto")
        if not resource_name:
            continue

        request = client.media().download(resourceName=resource_name)  # type: ignore[attr-defined]
        dest_path = tmp_dir / content_name
        buffer = io.FileIO(dest_path, mode="wb")
        downloader = MediaIoBaseDownload(buffer, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        paths.append(str(dest_path))

    return paths
