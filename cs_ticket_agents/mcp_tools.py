"""Builder del McpToolset que conecta los agentes al servidor MCP de runbooks.

En local (v1) el servidor corre como subproceso vía stdio. Al migrar a Cloud
Run, este builder cambia a SseConnectionParams contra una URL — los agentes
que lo consumen no cambian.
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
