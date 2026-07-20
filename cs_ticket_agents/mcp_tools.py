"""Builder del McpToolset que conecta los agentes al servidor MCP de runbooks.

En local (v1) el servidor corre como subproceso vía stdio. Al migrar a Cloud
Run, este builder cambia a SseConnectionParams contra una URL — los agentes
que lo consumen no cambian.

Nota (trabajo futuro): cada llamada crea una instancia nueva del toolset →
un subproceso MCP propio por subagente, cada uno indexando por su cuenta el
código de saas-rails-api (~1 min c/u la primera vez que se usa ese subagente
en el proceso). Se probó compartir una única instancia entre los 7 subagentes
para evitar esta redundancia, pero la conexión MCP se comportó de forma
inconsistente entre agentes (tools no listadas) — se optó por la versión sin
compartir, más simple y confiable, y se dejó la optimización pendiente
(ver informe, sección "trabajo futuro": servidor MCP persistente aparte, o
índice cacheado en disco en vez de en memoria por proceso).
"""

from pathlib import Path

from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from mcp import StdioServerParameters

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def build_runbooks_toolset() -> McpToolset:
    """Nueva instancia del toolset de runbooks (una por agente que lo use)."""
    return McpToolset(
        connection_params=StdioConnectionParams(
            server_params=StdioServerParameters(
                command="uv",
                args=["run", "python", "-m", "mcp_server.server"],
                cwd=str(PROJECT_ROOT),
            ),
        ),
    )
