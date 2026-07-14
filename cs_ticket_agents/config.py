"""Configuración centralizada: modelo por agente, resuelto por variable de entorno.

Requisito explícito del proyecto: el sistema debe funcionar con cualquier
modelo (Gemini, Anthropic, OpenAI) sin tocar código. El modelo de cada agente
es un string de configuración — Gemini nativo se pasa tal cual; cualquier otro
proveedor se envuelve automáticamente en LiteLlm según el prefijo del string.
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from google.adk.models.lite_llm import LiteLlm

# Ruta explícita: el .env vive junto a este archivo, no en el cwd del proceso
# que importa este módulo (el listener, por ejemplo, corre desde la raíz del
# proyecto). load_dotenv() sin argumentos solo busca hacia arriba desde el cwd.
load_dotenv(Path(__file__).resolve().parent / ".env")

# --- Autenticación Gemini (mismo patrón que ambient-expense-agent) ---
# Si GOOGLE_API_KEY está seteada, usa AI Studio. Si no, cae a Vertex AI.
if os.getenv("GOOGLE_API_KEY"):
    os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "False")
else:
    import google.auth

    _, project_id = google.auth.default()
    os.environ.setdefault("GOOGLE_CLOUD_PROJECT", project_id or "")
    os.environ.setdefault("GOOGLE_CLOUD_LOCATION", "global")
    os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "True")

# Prefijos de proveedor que LiteLLM reconoce — cualquier otro string se asume
# Gemini nativo y se pasa como string simple a Agent(model=...).
_LITELLM_PREFIXES = ("anthropic/", "openai/", "ollama_chat/", "vertex_ai/", "azure/")


def resolve_model(model_str: str) -> str | LiteLlm:
    """Convierte un string de config en lo que espera Agent(model=...).

    "gemini-flash-latest"              -> "gemini-flash-latest" (nativo)
    "anthropic/claude-sonnet-5"         -> LiteLlm(model="anthropic/claude-sonnet-5")
    "openai/gpt-5"                      -> LiteLlm(model="openai/gpt-5")
    """
    if model_str.startswith(_LITELLM_PREFIXES):
        return LiteLlm(model=model_str)
    return model_str


DEFAULT_MODEL = "gemini-flash-latest"

ORCHESTRATOR_MODEL = resolve_model(os.getenv("ORCHESTRATOR_MODEL", DEFAULT_MODEL))
IDSE_AGENT_MODEL = resolve_model(os.getenv("IDSE_AGENT_MODEL", DEFAULT_MODEL))
NOMINA_AGENT_MODEL = resolve_model(os.getenv("NOMINA_AGENT_MODEL", DEFAULT_MODEL))
GENERAL_AGENT_MODEL = resolve_model(os.getenv("GENERAL_AGENT_MODEL", DEFAULT_MODEL))
