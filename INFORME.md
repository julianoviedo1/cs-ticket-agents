# Informe — Sistema Multiagente de Soporte Técnico (cs-ticket-agents)

**Trabajo Práctico: Sistemas Multiagente con LLMs**
**Modalidad:** A — Implementación de agentes con código y prompts.
**Framework:** Google Agent Development Kit (ADK), con soporte multi-proveedor vía LiteLLM.

---

## 1. Introducción

### Problema que se busca resolver

Runa es un SaaS de nómina para México. Su equipo de Customer Support (CS) resuelve tickets técnicos recurrentes —activación de módulos, correcciones de cálculo de nómina, problemas de timbrado fiscal, movimientos ante el IMSS, etc.— diagnosticando manualmente en la consola de Rails de producción, guiándose por patrones que solo existen en la memoria del equipo. El mismo tipo de ticket se vuelve a investigar desde cero cada vez que aparece, sin una base de conocimiento explícita ni una forma sistemática de reutilizar diagnósticos previos.

### Contexto de negocio

CS atiende una taxonomía real de **~70 tipos de ticket** (`issue_type`), documentada por la propia empresa, que abarca dominios técnicamente muy distintos entre sí: afiliación ante el IMSS (IDSE/SUA), cálculo de nómina y percepciones, timbrado y cancelación de CFDI, dispersión de pagos vía STP, edición de perfil de empleado, y configuración/accesos de la plataforma. Cada dominio tiene su propio conjunto de modelos, servicios y reglas de negocio en el código (namespace `Mexico::` del monolito Rails).

### Objetivos funcionales

- Recibir un ticket (texto + adjuntos) y clasificarlo automáticamente en uno de los dominios de CS.
- Diagnosticar la causa raíz usando una base de conocimiento de runbooks previamente resueltos, y —cuando el runbook no alcanza— el código fuente real del sistema.
- Proponer una corrección concreta (script de consola) para revisión humana.
- Aprender de cada ticket resuelto, incluso cuando no había runbook aplicable.

### Objetivos no funcionales

- **Seguridad primero:** ningún agente ejecuta nada en producción en esta versión; todo pasa por un usuario.
- **Agnosticismo de modelo:** el sistema debe funcionar con cualquier proveedor (Gemini, Anthropic, OpenAI, y —en teoría— modelos open-source), intercambiable por configuración.
- **Costo acotado:** viable de operar con presupuesto de desarrollo mínimo (tier gratuito).
- **Trazabilidad:** cada resolución debe quedar registrada para retroalimentar el propio sistema.

### Justificación de un sistema multiagente

Un único agente con acceso a todas las tools sería, en la práctica, un prompt gigante que mezcla reglas de dominio de IDSE, nómina, timbrado, STP, perfil de empleado y configuración en un solo contexto — con alto riesgo de que el modelo aplique una regla de un dominio a un ticket de otro (por ejemplo, mezclar el criterio de "qué es un dato bloqueante" de PTU con el de timbrado). Además, cada dominio tiene su propio vocabulario técnico y sus propios runbooks: separar por subagente permite que la instrucción de cada uno sea corta, específica, y que el *tool budget* de RAG (qué runbooks son relevantes) se acote naturalmente por categoría. La delegación por un orquestador liviano —que **no diagnostica, solo clasifica**— es lo que permite escalar el número de dominios (hoy 7, hasta cerca de 70 issue_types reales) sin que el prompt de ningún agente individual crezca sin control.

---

## 2. Requerimientos

**Funcionales**
- Clasificar un ticket entrante en una de 7 categorías de dominio (o "otro").
- Recuperar runbooks relevantes por similitud semántica (RAG).
- Recuperar fragmentos del código fuente real cuando el runbook no alcanza (RAG sobre código).
- Mantener contexto compartido entre el orquestador y el subagente (categoría, entidades detectadas, progreso del diagnóstico) durante la conversación.
- Permitir que el usuario responda con datos de consola y que el agente continúe el diagnóstico sobre la misma sesión.
- Registrar cada resolución (con o sin runbook aplicable) para retroalimentar el sistema.

**No funcionales**
- El modelo de cada agente debe ser configurable por variable de entorno, sin cambios de código.
- El sistema debe correr en desarrollo local sin infraestructura cloud obligatoria.
- Los guardrails de seguridad deben aplicar por defecto, no ser opt-in.

**Restricciones tecnológicas**
- Framework: Google ADK (Python).
- MCP como mecanismo de acceso a herramientas externas (requisito de la cátedra).
- RAG como mecanismo de recuperación de información (requisito de la cátedra).

**Supuestos**
- El proceso Python y el origen de los adjuntos comparten filesystem en desarrollo (no así, necesariamente, en producción — ver Limitaciones).
- El equipo de CS es el único consumidor de las propuestas del sistema; no hay usuarios externos con acceso directo al agente.

---

## 3. Arquitectura general

![Arquitectura general del sistema](docs/architecture.svg)

Un ticket entra vía el listener de Google Chat, el `root_agent` (orquestador) lo clasifica y escribe el contexto en `session.state`, delega a uno de los 7 subagentes especializados, que consultan el servidor MCP propio (RAG sobre runbooks, código fuente y resoluciones) y le piden al usuario de CS un dato de consola cuando hace falta, hasta completar el diagnóstico.

### Componentes principales

| Componente | Rol |
|---|---|
| `cs_ticket_agents/agent.py` | Orquestador (`root_agent`): clasifica y delega. |
| `cs_ticket_agents/sub_agents/*.py` | 7 subagentes especializados por dominio. |
| `cs_ticket_agents/state_tools.py` | Tools de escritura de `session.state` compartido. |
| `cs_ticket_agents/tools.py` | Tool `read_excel` (con guardrail de path). |
| `cs_ticket_agents/guardrails.py` | Guardrail de salida (`after_model_callback`). |
| `mcp_server/` | Servidor MCP propio: runbooks, resoluciones, código fuente (RAG). |
| `runbooks/` | Base de conocimiento en markdown (15 runbooks reales). |
| `resolutions/index.jsonl` | Índice append-only de tickets resueltos. |
| `listener/` | Ingesta desde Google Chat (Pub/Sub pull). |

> **Nota:** `cs-tickets-web` (interfaz Rails + Postgres, repo hermano) y `api/local_bridge.py` son una extensión de producto en desarrollo paralelo, no forman parte del núcleo evaluado en este TPO — ver sección 12 (Trabajo futuro).

### Modelos LLM involucrados

Configurables por variable de entorno vía `resolve_model()` (`cs_ticket_agents/config.py`): Gemini nativo por default (`gemini-flash-latest`), con soporte transparente para Anthropic, OpenAI, Groq y Ollama vía `LiteLlm` (ver sección 9).

---

## 4. Diseño del sistema multiagente

### Orquestador (`root_agent`)

- **Objetivo:** clasificar el ticket y delegar, sin diagnosticar.
- **Entradas:** texto del ticket (delimitado, ver sección 5), adjuntos ya normalizados.
- **Salidas:** ninguna respuesta directa al usuario — transfiere la conversación.
- **Tools:** `set_ticket_context` (escribe `state`).
- **Contexto que mantiene:** ninguno propio; su única función es poblar el `state` que los subagentes van a leer.
- **Criterio de delegación:** mapeo explícito, en su instrucción, de los ~70 `issue_type` reales agrupados en 7 categorías (ver tabla abajo). Ante ambigüedad, elige la categoría más cercana — el subagente puede escalar si no es lo suyo.

### Los 7 subagentes

| Subagente | Dominio | Issue types que agrupa (muestra) |
|---|---|---|
| `agente_idse_sua` | Afiliación IMSS | IDSE-*, SUA - Other, edit-sdi, employee-edit-sbc/status/infonavit |
| `agente_nomina` | Cálculo de nómina | payroll-*, nominista-*, Payroll Review-*, Reporte CEP, PTU |
| `agente_timbrado` | CFDI / timbrado | Stamp*, stamping-*, Duplicidad CFDI |
| `agente_stp` | Dispersión de pagos | stp-*, devolucion-stp, Payment - Stuck |
| `agente_perfil_empleado` | Perfil de empleado | employee-edit-*, employee-create/delete, vacaciones, eventos |
| `agente_config_accesos` | Configuración/accesos | admin-create, configuration-*, user-other, access-other |
| `agente_general` | Catch-all | Todo lo que no matchea; evalúa si amerita un subagente nuevo |

Cada subagente comparte una misma estructura (definida en `cs_ticket_agents/sub_agents/common.py`):

- **Entradas:** el texto del ticket + `session.state` poblado por el orquestador (`category`, `issue_type`, `detected_entities`).
- **Salidas:** diagnóstico en texto + script de consola propuesto (one-liners) + citación del runbook usado.
- **Tools:** `search_runbooks`, `get_runbook`, `find_similar_tickets`, `search_codebase`, `log_resolution` (vía MCP) + `read_excel` + `record_progress` (state).
- **Memoria:** ninguna de largo plazo (ver Trabajo futuro); dentro de una sesión, el `state` compartido cumple ese rol.
- **Estrategia de prompting:** instrucción de dominio corta y específica + tres bloques compartidos inyectados por composición de strings: `PROMPT_INJECTION_GUARD`, `STATE_CONTEXT` (con placeholders `{category}`/`{issue_type}`/`{detected_entities}` que ADK resuelve en runtime desde `session.state`), y `SAFETY_RULES`.

### Patrón de coordinación

**Orquestación**, no colaboración simétrica: hay una jerarquía clara (root → sub_agents), el orquestador nunca vuelve a intervenir una vez delegado. La delegación usa el mecanismo nativo de ADK (`sub_agents=[...]` + `transfer_to_agent` generado automáticamente), no `AgentTool` — porque queremos que el subagente controle el resto de la conversación con el usuario (incluida la espera de un dato de consola), no que el orquestador quede "esperando" un resultado único.

### Uso de state

Dos tools dedicadas (`cs_ticket_agents/state_tools.py`) formalizan el contrato:

```python
def set_ticket_context(category, issue_type, detected_entities, tool_context): ...
def record_progress(runbook_id, diagnosis_so_far, pending_question, tool_context): ...
```

El orquestador escribe `category`/`issue_type`/`detected_entities` **antes** de delegar; el subagente lee esos valores vía template `{category}` en su instrucción (evitando re-extraerlos del texto), y escribe de vuelta `runbook_id`/`diagnosis_so_far`/`pending_question` al final de cada turno — así, cuando el usuario responde con un dato de consola en el turno siguiente, el subagente retoma con contexto ya armado. Validado end-to-end: una corrida real mostró `set_ticket_context` clasificando correctamente `category="nomina"`, `issue_type="payroll-ptu"` y extrayendo `sub_company_id`/`company_subdomain` sin inventar valores, con el `stateDelta` confirmando la escritura real en la sesión de ADK.

### Sesiones

`InMemorySessionService` de ADK a nivel de conversación (efímera, vive mientras el proceso está arriba): el `session_id` que devuelve cada corrida (`agents-cli run --session-id ...`) es la única forma de continuar una conversación con contexto ya armado. No hay, por ahora, persistencia a nivel de producto (qué ticket corresponde a qué `session_id`, historial legible entre sesiones) — es un problema de producto, no de este TPO, y queda documentado como trabajo futuro (sección 12): la idea es que `cs-tickets-web` (Rails + Postgres, en desarrollo paralelo) guarde ese mapeo el día que se integre.

---

## 5. Herramientas y fuentes de información

### MCP — servidor propio (`mcp_server/`)

Un único servidor MCP (`FastMCP`, transporte stdio) expone 5 tools: `search_runbooks`, `get_runbook`, `find_similar_tickets`, `search_codebase`, `log_resolution`. Se eligió MCP —en vez de, por ejemplo, tools Python directas contra los mismos módulos— porque desacopla el *qué* expone la capa de conocimiento del *cómo* la consumen los agentes: el mismo servidor podría, sin cambiar el código de los agentes, migrar de stdio local a un endpoint remoto (`SseConnectionParams`) el día que se despliegue a Cloud Run. El trade-off es la complejidad operativa de correr un proceso más (ver Limitaciones: no se pudo compartir una sola instancia entre los 7 subagentes).

### RAG — dos corpus, mismo mecanismo

Se implementó RAG real (no solo keyword search) usando **embeddings locales** (`fastembed`, modelo `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`, 384 dim, corre en CPU sin llamar a ninguna API externa):

1. **`search_runbooks` / `find_similar_tickets`** — similitud coseno contra los 15 runbooks reales (migrados de resoluciones anteriores del equipo de CS) y contra el índice de resoluciones.
2. **`search_codebase`** — indexa ~1830 chunks (ventanas de 60 líneas con solapamiento de 10) de `app/models/mexico`, `app/services/mexico`, `app/controllers/v1/mexico`, `app/queries/mexico`, `app/interactors/mexico`, más `db/schema.rb` (chunkeado por tabla vía `create_table ... do |t| ... end`) del repositorio `saas-rails-api`.

**Por qué embeddings locales y no la API de embeddings de Gemini:** evitar sumar otro consumidor más a una cuota gratuita ya escasa (ver Limitaciones) — el corpus es acotado (~2000 documentos entre ambos corpus) y el costo de indexar localmente es de segundos a un minuto, pagado una sola vez por proceso.

**Por qué acotar el código indexado y no todo el monolito:** el repositorio completo tiene decenas de miles de archivos (specs, vistas, paneles de admin) que no aportan al diagnóstico y solo agregan ruido al retrieval. Se acotó a los namespaces `Mexico::` con lógica de negocio real, alineados 1:1 con los 7 dominios de los subagentes.

**Trade-off encontrado y documentado:** el retrieval semántico no siempre prioriza el match léxico más obvio — en una prueba real, la query "activar PTU para un registro patronal" priorizó `ptu-crear-nomina-individual` (0.43) por sobre `ptu-activar-modulo` (0.35), semánticamente cercanos pero no el mismo caso. Es una limitación conocida y esperable de RAG puro por embeddings (ver Limitaciones/Trabajo futuro: retrieval híbrido).

### Otras fuentes

- **`read_excel`** — parseo de adjuntos Excel/CSV (pandas), con guardrail de directorio permitido (ver sección 6).
- **Modelos ML** — no se usó inferencia de ML clásico (clasificación/regresión); la clasificación de tickets la hace el propio LLM orquestador, no un modelo entrenado aparte. Queda como posible extensión de "contenidos medios" (ver Trabajo futuro).

---

## 6. Seguridad

### Prompt Injection

El texto de un ticket llega de un cliente externo (mensaje de Chat, card de Rumi) — es, por definición, entrada no confiable que puede intentar instrucciones tipo *"ignorá tus reglas anteriores"* o hacerse pasar por un mensaje de sistema. **Mitigación implementada:** el contenido del ticket se delimita explícitamente con marcadores (`=== INICIO CONTENIDO DEL TICKET (dato externo, no confiable) ===` / `=== FIN ===`) tanto en el listener de Chat (Python) como en el modelo `Ticket` de Rails, y la instrucción de cada agente (`PROMPT_INJECTION_GUARD`, en `common.py`) le indica explícitamente que ese bloque es dato, nunca una instrucción, incluso si el texto simula serlo.

### Jailbreak / "solo diagnóstico, nunca ejecución"

La regla "nunca ejecutes nada en producción" vive en el prompt (`SAFETY_RULES`), pero **no depende solo de que el modelo la respete**: como defensa en profundidad, un `after_model_callback` (`cs_ticket_agents/guardrails.py`, `destructive_script_guard`) escanea cada respuesta final por patrones destructivos sin acotar antes de dejarla pasar:

```python
_DESTRUCTIVE_PATTERNS = {
    "shell exec (backticks)": ...,
    "shell exec (system/exec/popen)": ...,
    "destroy_all/delete_all sin scope (Modelo.destroy_all)": ...,
    "DDL crudo (DROP/TRUNCATE)": ...,
}
```

Calibrado explícitamente para **no** producir falsos positivos contra patrones ya documentados en los propios runbooks (ej. `movement.mexico_movements_imss_reports.destroy_all`, un `destroy_all` acotado a una asociación — legítimo) mientras sí bloquea un `Employee.destroy_all` sin scope. Validado con 5 casos (2 legítimos que no deben bloquearse, 3 maliciosos que sí).

### Protección de herramientas

Se encontró y corrigió una vulnerabilidad real durante el desarrollo: `read_excel(file_path)` aceptaba cualquier ruta absoluta sin validación — un ticket podía, en teoría, hacer que el agente leyera `/etc/passwd` o el `.env` con las API keys del sistema. **Fix:** allowlist de directorios permitidos (los dos orígenes reales de adjuntos: el temp dir del listener de Chat y el storage de Active Storage de Rails), resolviendo la ruta a su forma canónica antes de comparar (protección contra `../` y symlinks). Validado con 4 intentos de ataque, incluyendo path traversal.

### Autenticación y autorización

El webhook de ingesta desde Rumi/AppSheet (`cs-tickets-web`, `WebhooksController#rumi`) exige un secreto compartido (`RUMI_WEBHOOK_SECRET`) vía header `Authorization: Bearer`, comparado con `ActiveSupport::SecurityUtils.secure_compare` (constante en tiempo, contra timing attacks).

### Aislamiento entre agentes / control de acceso

El control de acceso más importante del sistema es **arquitectónico, no un chequeo puntual**: en esta versión, ningún agente tiene ninguna tool de escritura ni ejecución contra producción. La única forma de que algo llegue a ejecutarse es que un usuario lea la propuesta y la corra él mismo. Este diseño de mínimo privilegio por construcción es, en la práctica, más robusto que cualquier guardrail de prompt.

### Manejo de datos sensibles

El texto del ticket (con PII real de empleados: nombres, salarios, IDs) sale hacia un proveedor de LLM externo (Gemini/Groq/etc.) — es una limitación inherente a usar cualquier API de LLM alojada, no algo "guardraileable" sin dejar de usar un LLM externo. Se documenta como limitación conocida (sección 11) en vez de fingir una mitigación que no existe.

---

## 7. Evaluación

### Golden Cases

Dos casos reales, tomados de resoluciones efectivas del equipo de CS (anonimizados los nombres de cliente donde correspondía), cada uno con su `reference` (la respuesta real que dio un usuario) como golden answer:

1. **`activar_ptu_registro_patronal`** — activación de PTU bloqueada por un `ProfitSharingPayment` del año anterior.
2. **`planchar_horas_extras_exento_gravado`** — fijar manualmente exento/gravado de horas extras desde un Excel del cliente.

### Métricas (LLM as a Judge + trayectoria)

`tests/eval/eval_config.yaml` define 3 métricas:

| Métrica | Tipo | Qué mide |
|---|---|---|
| `multi_turn_tool_use_quality` | Built-in (adaptativa) | ¿Llamó a las tools correctas, en un orden razonable? (trayectoria) |
| `correctness_vs_golden` | Custom LLM-as-Judge | ¿El diagnóstico coincide en causa raíz y corrección de fondo con la respuesta real de referencia? (escala 1-5) |
| `faithfulness` | Custom LLM-as-Judge | ¿La respuesta se basa en lo que efectivamente recuperó `search_runbooks`/`search_codebase`, o alucinó? (escala 1-5) |

### Criterios de aceptación

Umbral propuesto: promedio ≥ 4/5 en `correctness_vs_golden` y `faithfulness`, y `multi_turn_tool_use_quality` sin fallas de trayectoria evidentes (ej. proponer un diagnóstico sin haber llamado a `search_runbooks` antes).

### Estado de ejecución

El diseño y la implementación de la evaluación están completos y probados de punta a punta a nivel mecánico (generación de trazas, formato de dataset, config de métricas). La ejecución final (`agents-cli eval grade` con resultados numéricos) quedó bloqueada por la cuota diaria gratuita de la API de Gemini (20 requests/día), agotada durante el desarrollo activo del resto del sistema. Se documenta como limitación con causa identificada, no como trabajo pendiente de diseño — ver sección 11.

Durante la construcción del pipeline de evaluación se encontró y resolvió un problema real: el SDK de evaluación local de Vertex AI (usado por `agents-cli eval generate`) intenta introspeccionar cada tool del agente como una función Python simple para armar el mapa de agentes, y no reconoce objetos `McpToolset` (`TypeError: McpToolset object is not a callable object`) — rompe con cualquiera de nuestros 7 subagentes. Se resolvió generando las trazas con un script propio (`tests/eval/scripts/generate_traces.py`) que corre el mismo `Runner` de ADK usado en producción, capturando la traza completa en el formato que `agents-cli eval grade` sabe consumir (que sí opera solo sobre el JSON, sin volver a tocar el agente en vivo).

---

## 8. Observabilidad

- **Trazabilidad entre agentes:** cada evento de ADK (`Event`) incluye `author`, `content` y —para tool calls— `function_call`/`function_response`; se puede inspeccionar en runtime con `agents-cli run -v` (usado extensivamente durante el desarrollo para depurar la delegación y el uso de `state`).
- **Logs de negocio:** `resolutions/index.jsonl` — cada resolución (con o sin runbook aplicable) queda registrada con `ticket_id`, `category`, `runbook_id`, `diagnosis` y `script_proposed`, timestamped en UTC.
- **Trazas de evaluación:** `artifacts/traces/` (generadas por `generate_traces.py`) y `artifacts/grade_results/` (resultados de `eval grade`) — auditables después de cada corrida.
- **Logs del servidor MCP:** stderr del subproceso (ej. confirmación de cuántos chunks se indexaron al arrancar), separado deliberadamente del canal stdout que usa el protocolo MCP.
- **Pendiente (trabajo futuro):** no hay tracing distribuido real (OpenTelemetry/Cloud Trace) todavía — el scaffold de ADK lo soporta (`otel_to_cloud=True` en `fast_api_app.py`, el entrypoint de producción) pero no se activó en desarrollo local.

---

## 9. Decisiones de diseño

| Decisión | Justificación |
|---|---|
| **Framework: Google ADK** | Requisito de la cátedra (uno de los dos framework permitidos); además, soporte nativo de `sub_agents`, `session.state`, `McpToolset` y callbacks de guardrail sin librerías adicionales. |
| **Modelo: Gemini por default, agnóstico por diseño** | `resolve_model()` envuelve cualquier proveedor no-Gemini en `LiteLlm` según el prefijo del string de config (`anthropic/`, `openai/`, `groq/`, `ollama_chat/`). Ningún agente hardcodea un proveedor. |
| **7 subagentes, no 3 ni 70** | Reflejan la taxonomía real de negocio (~70 issue_types) agrupada en dominios técnicamente coherentes — ni tan grueso que un prompt mezcle reglas de dominios distintos, ni tan fino que mantener 70 agentes sea inviable. |
| **`state` vía tools dedicadas, no vía `output_key`** | `output_key` solo permite guardar un string por turno bajo una clave; nuestro contrato necesita escribir varios campos estructurados a la vez (categoría + issue_type + entidades; o runbook_id + diagnóstico + pregunta pendiente) — de ahí `set_ticket_context`/`record_progress` como tools con acceso a `tool_context.state`. |
| **Un `McpToolset` por subagente, no uno compartido** | Se probó compartir una única instancia entre los 7 subagentes (para evitar indexar el código 7 veces) — la conexión MCP se comportó de forma inconsistente (tools no listadas en algunos agentes). Se revirtió a una instancia por subagente, priorizando corrección sobre eficiencia, con la redundancia documentada como trabajo futuro. |
| **RAG con embeddings locales, no la API de embeddings de un proveedor** | Evita sumar otro consumidor más a una cuota ya escasa; el corpus es chico, el costo de indexar en CPU es marginal y se paga una sola vez por proceso. |
| **Sesión de ADK en memoria, sin persistencia de producto por ahora** | `session.state` es un mecanismo *dentro* de una conversación de ADK; la persistencia de "qué ticket corresponde a qué sesión" y el historial legible por el equipo es un problema de producto, no de framework — se deja fuera del núcleo del TPO deliberadamente, para no acoplar el esquema interno de ADK al esquema de negocio de Rails antes de tiempo (ver Trabajo futuro). |
| **Guardrail de salida calibrado contra los propios runbooks** | Un guardrail que bloquea cualquier `destroy_all` sería inútil en este dominio (el patrón aparece legítimamente en runbooks reales) — se diseñó para distinguir alcance acotado (asociación) de alcance total (clase), no solo la presencia de la palabra. |

---

## 10. Trade-offs

- **Costo vs. calidad de modelo:** Gemini gratuito es viable para desarrollo pero con cuota muy restrictiva (20 req/día); modelos open-source gratuitos vía Groq resultaron más baratos pero con problemas reales de compatibilidad de tool-calling en un flujo agéntico multi-turno (ver Limitaciones) — el sistema queda preparado para cualquiera de las dos rutas, pero hoy Gemini/Claude son la opción confiable para producción.
- **Cantidad de agentes vs. complejidad:** 7 subagentes reflejan mejor la realidad del negocio que 3, a costa de más superficie para mantener (7 instrucciones, 7 procesos MCP potenciales, 7 variables de modelo) — se aceptó el costo porque la alternativa (agentes de dominio demasiado amplio) es peor para la precisión del diagnóstico.
- **Rapidez vs. precisión en RAG:** embeddings semánticos son más rápidos de consultar que un índice híbrido, pero pueden priorizar un documento semánticamente cercano por sobre el léxicamente exacto (caso PTU documentado en sección 5) — se aceptó por ahora, con retrieval híbrido como mejora futura.
- **Autonomía vs. control del usuario:** el diseño es deliberadamente conservador — cero autonomía de ejecución en v1. Esto reduce el valor inmediato (todavía hace falta un usuario para cada corrección) a cambio de eliminar la clase de riesgo más grave (un agente ejecutando algo destructivo en producción de nómina real).
- **Memoria persistente vs. costo/complejidad:** no se implementó memoria de largo plazo entre sesiones ni persistencia de producto (`cs-tickets-web` todavía no guarda ese mapeo) — se prefirió mantener el `state` de ADK simple y acotado a una conversación, dejando memoria cross-session como trabajo futuro explícito.

---

## 11. Limitaciones

- **Cuota gratuita de Gemini (20 req/día, 5 req/min):** bloqueó la corrida final del eval y varias pruebas end-to-end durante el desarrollo. Causa identificada, no ambigua.
- **Groq como alternativa: dos incompatibilidades reales documentadas** (`docs/groq_compatibility_findings.md`) — `llama-3.3-70b-versatile` genera sintaxis de function-call no estándar; `openai/gpt-oss-120b` y `qwen/qwen3.6-27b` (ambos modelos "razonadores") devuelven un campo `reasoning_content` que Groq rechaza al reenviarse en el historial multi-turno vía LiteLLM/ADK — un problema de integración, no de nuestro código.
- **El SDK de evaluación local de Vertex AI no soporta `McpToolset`** — requirió un generador de trazas propio como workaround (documentado en sección 7).
- **Redundancia de indexado MCP:** cada subagente lanza su propio subproceso del servidor MCP; si se usan los 7 en una misma sesión, el código se indexa hasta 7 veces (~1 min c/u la primera vez que se usa ese subagente).
- **Alucinación / hallucination:** mitigado por `faithfulness` como métrica de evaluación y por la regla de "no inventes, escalá" en el prompt, pero no hay un guardrail mecánico que verifique fidelidad en tiempo real (solo se mide post-hoc en eval).
- **Dependencia del proveedor del modelo:** aunque el sistema es agnóstico por diseño, en la práctica solo Gemini fue validado de punta a punta sin fallas de tool-calling — Claude/OpenAI no se probaron todavía (ver Trabajo futuro).
- **Adjuntos y filesystem compartido:** `read_excel` asume que Rails y el proceso Python corren en la misma máquina — cierto en desarrollo local, falso en un despliegue distribuido (necesitaría storage compartido o reenvío de bytes).
- **Datos sensibles hacia terceros:** el contenido del ticket (con PII real) sale hacia la API del LLM elegido — limitación inherente a cualquier sistema que use un LLM alojado externamente, no resuelta ni resoluble sin dejar de usar un proveedor externo.
- **Sin memoria de largo plazo:** cada ticket es una sesión nueva de ADK; el aprendizaje entre tickets pasa exclusivamente por `resolutions/index.jsonl` vía RAG, no por memoria nativa del agente.

---

## 12. Trabajo futuro

- **Retrieval híbrido (keyword + semántico)** para RAG, mitigando el caso documentado donde el embedding prioriza un documento semánticamente cercano pero no el más exacto.
- **Servidor MCP persistente compartido** (en vez de un subproceso por subagente) para eliminar la redundancia de indexado — requeriría entender por qué la instancia compartida se comportó de forma inconsistente en las pruebas.
- **Memoria de largo plazo** (Memory Bank de ADK o equivalente) para que un agente recuerde patrones de un cliente específico entre tickets, no solo dentro de una sesión.
- **Human-in-the-Loop formalizado** en la UI de `cs-tickets-web`: hoy la aprobación es implícita (el usuario lee y decide ejecutar por su cuenta); el paso natural es un botón explícito de aprobar/rechazar antes de que el sistema (en una v2 con ejecución real) corra algo.
- **Protocolo A2A** (simulado): un agente de otra organización (ej. el proveedor de STP) podría exponerse como agente remoto para consultas cross-organización.
- **Modelo de Machine Learning clásico** para pre-clasificación de tickets (complementando al LLM orquestador con un clasificador entrenado, más barato y determinístico para el caso común).
- **Inferencia con múltiples proveedores validados:** completar la validación de Claude y OpenAI vía LiteLLM (hoy solo Gemini está probado sin fallas de tool-calling).
- **Observabilidad real:** activar tracing distribuido (OpenTelemetry → Cloud Trace) en el entrypoint de producción, hoy soportado pero no activado.
- **Self-Correcting RAG:** si `faithfulness` cae por debajo de un umbral en producción, disparar una segunda ronda de retrieval antes de responder.
- **Completar `cs-tickets-web`** (dashboard, dos vías de entrada: webhook de Rumi + formulario manual) como interfaz de producto — construido en paralelo a este TPO pero fuera de su alcance formal.

---

## 13. Conclusiones

El sistema demuestra que un diseño multiagente con delegación clara (orquestador liviano + subagentes de dominio) es superior a un chatbot monolítico con tools cuando el dominio real tiene la heterogeneidad que tiene el soporte técnico de un SaaS de nómina: 7 especialidades técnicamente distintas, cada una con su propio vocabulario y sus propios riesgos. La combinación de **state compartido** (para no perder contexto entre el clasificador y el especialista), **RAG sobre dos corpus complementarios** (conocimiento curado y código fuente real) y **guardrails calibrados contra el propio dominio** (no genéricos) produjo un sistema que, incluso sin haber podido correr la evaluación final por restricciones de cuota, quedó validado punto por punto a nivel mecánico durante el desarrollo — con cada bug y cada limitación encontrados documentados como tal, no ocultados. La decisión más importante del proyecto no fue técnica sino de diseño de seguridad: mantener al sistema en modo solo-diagnóstico, con un usuario como única puerta de ejecución, es lo que permite que el resto de las decisiones (modelo, framework, agentes) se puedan iterar rápido sin poner en riesgo un sistema de nómina real.
