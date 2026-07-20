# cs-ticket-agents

Sistema multiagente que diagnostica tickets de soporte técnico de Runa (SaaS de nómina para México): un **orquestador** clasifica el ticket y lo delega a uno de **7 subagentes especializados** (IDSE/SUA, nómina, timbrado, STP, perfil de empleado, configuración/accesos, y un catch-all general), que consultan una base de runbooks y el código fuente real del sistema (**RAG**, vía un **servidor MCP propio**) para proponer un diagnóstico y una corrección — siempre para revisión humana, nunca ejecutando nada en producción.

Trabajo Práctico — Sistemas Multiagente con LLMs. Para la arquitectura completa, decisiones de diseño, trade-offs y limitaciones, ver **[INFORME.md](INFORME.md)**.

## Estructura del proyecto

```
cs-ticket-agents/
├── cs_ticket_agents/
│   ├── agent.py                # Orquestador (root_agent): clasifica y delega
│   ├── config.py               # Modelo por agente, configurable por env (Gemini/Anthropic/OpenAI/Groq/Ollama)
│   ├── mcp_tools.py             # Builder del McpToolset (conecta agentes al servidor MCP)
│   ├── state_tools.py           # Tools de session.state (set_ticket_context, record_progress)
│   ├── tools.py                 # read_excel (con guardrail de path)
│   ├── guardrails.py             # Guardrail de salida (after_model_callback)
│   └── sub_agents/               # Los 7 subagentes especializados + reglas compartidas (common.py)
├── mcp_server/                  # Servidor MCP propio: RAG sobre runbooks, resoluciones y código
│   ├── server.py                 # FastMCP: search_runbooks, get_runbook, find_similar_tickets, search_codebase, log_resolution
│   ├── embeddings.py              # Embeddings locales (fastembed), sin llamadas a APIs externas
│   ├── runbook_store.py           # Carga + retrieval semántico de runbooks/
│   ├── resolutions_store.py       # Índice de tickets resueltos (resolutions/index.jsonl)
│   └── codebase_store.py          # Indexa y busca en el código fuente de saas-rails-api
├── runbooks/                    # Base de conocimiento (15 runbooks reales, markdown)
├── resolutions/                 # Índice append-only de tickets resueltos
├── listener/                    # Ingesta desde Google Chat (Pub/Sub pull) — ver docs/chat_listener_setup.md
├── api/local_bridge.py           # Puente HTTP local hacia cs-tickets-web (Rails, opcional)
├── tests/eval/                   # Golden cases, config de métricas (LLM as a Judge), scripts de eval
├── docs/                         # Hallazgos de compatibilidad (Groq), setup del listener
└── INFORME.md                    # Informe completo del TPO
```

## Requisitos

- **Python 3.11+**
- **[uv](https://docs.astral.sh/uv/getting-started/installation/)** — gestor de paquetes usado en todo el proyecto
- **[agents-cli](https://github.com/google/adk-samples)** — `uv tool install google-agents-cli`
- **Una API key de Google AI Studio** (gratis, sin tarjeta) — [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey)

## Instalación

```bash
git clone <este repo>
cd cs-ticket-agents
agents-cli install          # instala dependencias (uv sync) y las del linter
```

Cargar la API key:

```bash
echo "GOOGLE_API_KEY=tu_api_key_aca" >> cs_ticket_agents/.env
```

> **Modelo por agente configurable por env** (ver `cs_ticket_agents/config.py`): por default todos los agentes usan Gemini (`gemini-flash-latest`). Para usar otro proveedor en un agente puntual, setear su variable en `cs_ticket_agents/.env`, por ejemplo `NOMINA_AGENT_MODEL=anthropic/claude-sonnet-5` (requiere `ANTHROPIC_API_KEY`) — no hace falta tocar código.

## Ejecución

**Playground interactivo** (recomendado para probar a mano):

```bash
agents-cli playground
```

**Un solo prompt, no interactivo:**

```bash
agents-cli run "El cliente pide activar el módulo de PTU para el registro patronal de Grupo Kuka, sub_company 7504" -v
```

El flag `-v` muestra el JSON completo de cada evento — útil para ver la clasificación del orquestador (`set_ticket_context`), la delegación (`transfer_to_agent`) y las tools que llama el subagente (`search_runbooks`, `search_codebase`, `record_progress`).

**Continuar una conversación** (ej. para responder con un dato de consola que pidió el agente):

```bash
agents-cli run "req = Mexico::Desereti::Request.find_by(batch_id: 438340901) => devolvió transaction_status: completed" \
  --session-id <el session-id que imprimió la corrida anterior>
```

## Ejemplos de uso

### 1. Ticket con runbook aplicable (PTU)

```bash
agents-cli run "Hola, el registro patronal de Grupo Kuka necesita activar el módulo de PTU (reparto de utilidades), sub_company 7504. Nos pueden ayudar?"
```

Comportamiento esperado: el orquestador clasifica `category="nomina"`, `issue_type="payroll-ptu"`, delega a `agente_nomina`, que encuentra el runbook `ptu-activar-modulo` (vía `search_runbooks`), diagnostica el bloqueo real (`ProfitSharingPayment` del año anterior con status `in_progress`/`finished`) y propone el one-liner de corrección, citando el runbook.

### 2. Ticket que requiere un dato de consola

```bash
agents-cli run "El cliente reporta que el reporte ISN de la empresa X muestra la base gravada mal para el empleado 12345 en la nómina 500"
```

Comportamiento esperado: el subagente (`agente_nomina`) no tiene el dato exacto del `payload` de esa nómina — en vez de inventarlo, pide el one-liner exacto para correr en consola y espera la respuesta antes de continuar el diagnóstico.

### 3. Ticket con adjunto Excel

```bash
agents-cli run "Adjunto el Excel MEC_Formato plachado de datos_1.xlsx. Necesitamos planchar el exento y gravado de horas extras del empleado EMP123 en la nómina 708862.
Adjuntos descargados (rutas absolutas, usá read_excel si aplica):
- /tmp/mec_formato.xlsx"
```

Comportamiento esperado: el subagente usa `read_excel` (con el guardrail de directorio permitido) para leer las columnas I-N del archivo y arma la corrección con los valores reales.

### 4. Ticket fuera de los 7 dominios

```bash
agents-cli run "Necesitamos migrar toda la base de datos a un nuevo proveedor de cloud"
```

Comportamiento esperado: ningún runbook ni ticket similar aplica — `agente_general` lo dice explícitamente, evalúa si amerita un subagente nuevo, y pregunta si conviene reservarlo como candidato o sumarlo a un subagente existente, en vez de inventar un diagnóstico.

## Evaluación

```bash
# 1. Generar las trazas (script propio — ver INFORME.md sección 7 sobre por qué
#    no se usa `agents-cli eval generate` directamente con este agente)
uv run python tests/eval/scripts/generate_traces.py

# 2. Graduar con las métricas configuradas (trayectoria + LLM as a Judge)
agents-cli eval grade --traces artifacts/traces/manual_trace.json --config tests/eval/eval_config.yaml
```

Los 2 golden cases y las 3 métricas (`multi_turn_tool_use_quality`, `correctness_vs_golden`, `faithfulness`) están en `tests/eval/`.

## Servidor MCP (standalone)

Para inspeccionar el servidor de runbooks/RAG por separado (no hace falta para correr los agentes, que lo lanzan solos como subproceso):

```bash
uv run python -m mcp_server.server
```

## Lint

```bash
agents-cli lint          # ruff + codespell + ty
agents-cli lint --fix    # auto-fix
```

## Componentes opcionales (no requeridos para el TPO)

- **`listener/`** — ingesta en vivo desde un Space de Google Chat vía Pub/Sub. Ver `docs/chat_listener_setup.md` (requiere un proyecto de GCP con billing habilitado).
- **`cs-tickets-web`** (repo hermano) — interfaz Rails + Postgres con dashboard de tickets y webhook de ingesta desde Rumi/AppSheet. Se comunica con este proyecto vía `api/local_bridge.py`.
