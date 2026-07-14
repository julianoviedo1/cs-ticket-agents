"""Tools genéricas compartidas por los subagentes (independientes del MCP)."""

from pathlib import Path

import pandas as pd

MAX_ROWS = 200  # evita volcar excels enormes al contexto del modelo


def read_excel(file_path: str, sheet_name: str | None = None) -> dict:
    """Parsea un archivo Excel/CSV adjunto a un ticket y devuelve sus filas.

    Args:
        file_path: ruta absoluta al archivo (.xlsx, .xls o .csv) del adjunto.
        sheet_name: nombre de hoja a leer (Excel). Si se omite, lee la primera.

    Returns:
        Dict con "columns", "rows" (hasta 200, como lista de dicts),
        "row_count" (total real) y "truncated". Si falla el parseo,
        devuelve {"error": "..."} en vez de lanzar una excepción.
    """
    path = Path(file_path)
    if not path.is_absolute():
        return {"error": "file_path debe ser una ruta absoluta"}
    if not path.exists():
        return {"error": f"No existe el archivo: {file_path}"}

    try:
        if path.suffix.lower() == ".csv":
            df = pd.read_csv(path)
        else:
            df = pd.read_excel(path, sheet_name=sheet_name or 0)
    except Exception as exc:
        return {"error": f"No se pudo parsear el archivo: {exc}"}

    return {
        "columns": [str(c) for c in df.columns],
        "rows": df.head(MAX_ROWS).to_dict(orient="records"),
        "row_count": len(df),
        "truncated": len(df) > MAX_ROWS,
    }
