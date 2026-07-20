"""Tools genéricas compartidas por los subagentes (independientes del MCP)."""

import os
import tempfile
from pathlib import Path

import pandas as pd

MAX_ROWS = 200  # evita volcar excels enormes al contexto del modelo

# Guardrail (protección de herramientas): read_excel solo puede leer archivos
# bajo estos directorios. file_path lo escribe el modelo a partir de lo que
# el ticket le mostró — es una entrada no confiable, viene de afuera. Sin
# esta lista, un ticket que sugiera un path como "/etc/passwd" o el .env con
# las API keys sería legible por el agente. Configurable vía
# ALLOWED_ATTACHMENT_DIRS (rutas separadas por coma) para producción; el
# default cubre las dos fuentes reales de adjuntos en desarrollo: el
# listener de Chat (temp dir del SO) y Active Storage de cs-tickets-web.
_DEFAULT_ALLOWED_DIRS = [
    tempfile.gettempdir(),
    str(Path.home() / "code" / "cs-tickets-web" / "storage"),
]


def _allowed_dirs() -> list[Path]:
    raw = os.environ.get("ALLOWED_ATTACHMENT_DIRS")
    dirs = raw.split(",") if raw else _DEFAULT_ALLOWED_DIRS
    return [Path(d).resolve() for d in dirs if d.strip()]


def read_excel(file_path: str, sheet_name: str | None = None) -> dict:
    """Parsea un archivo Excel/CSV adjunto a un ticket y devuelve sus filas.

    Args:
        file_path: ruta absoluta al archivo (.xlsx, .xls o .csv) del adjunto.
        sheet_name: nombre de hoja a leer (Excel). Si se omite, lee la primera.

    Returns:
        Dict con "columns", "rows" (hasta 200, como lista de dicts),
        "row_count" (total real) y "truncated". Si falla el parseo o la
        ruta no está permitida, devuelve {"error": "..."} en vez de lanzar
        una excepción.
    """
    path = Path(file_path)
    if not path.is_absolute():
        return {"error": "file_path debe ser una ruta absoluta"}

    resolved = path.resolve()  # normaliza ".." y symlinks antes de comparar
    if not any(resolved.is_relative_to(allowed) for allowed in _allowed_dirs()):
        return {
            "error": (
                f"Ruta no permitida (fuera de los directorios de adjuntos "
                f"autorizados): {file_path}"
            )
        }

    if not resolved.exists():
        return {"error": f"No existe el archivo: {file_path}"}

    try:
        if resolved.suffix.lower() == ".csv":
            df = pd.read_csv(resolved)
        else:
            df = pd.read_excel(resolved, sheet_name=sheet_name or 0)
    except Exception as exc:
        return {"error": f"No se pudo parsear el archivo: {exc}"}

    return {
        "columns": [str(c) for c in df.columns],
        "rows": df.head(MAX_ROWS).to_dict(orient="records"),
        "row_count": len(df),
        "truncated": len(df) > MAX_ROWS,
    }
