# Groq como alternativa gratis/barata a Gemini — hallazgos

Se evaluó Groq (modelos open-source, tier gratis sin tarjeta) como alternativa
para evitar los límites de cuota de la API gratuita de Gemini durante el
desarrollo. El sistema ya soporta el cambio sin tocar código (ver
`cs_ticket_agents/config.py`, prefijo `groq/` reconocido por `resolve_model`,
enrutado vía `LiteLlm`) — el problema encontrado es de **compatibilidad entre
Groq y el flujo de tool-calling multi-turno de ADK/LiteLLM**, no de nuestro
diseño.

## Modelos probados

| Modelo | Resultado |
|---|---|
| `groq/llama-3.3-70b-versatile` | Falló al formatear una function-call (`transfer_to_agent`): generó `<function=transfer_to_agent [...]>` — un formato no estándar que el parser de Groq rechazó (`tool_use_failed`). |
| `groq/openai/gpt-oss-120b` | Falló en el segundo turno de una secuencia con tool-calls: el modelo devuelve un campo `reasoning_content` (es un modelo "razonador") que ADK/LiteLLM reenvía en el historial del turno siguiente, y el endpoint de Groq lo rechaza (`property 'reasoning_content' is unsupported`). |
| `groq/qwen/qwen3.6-27b` | Mismo error que gpt-oss-120b — también es un modelo razonador con `reasoning_content`. |

## Conclusión

Los tres modelos probados fallan en algún punto del flujo agéntico real
(orquestador → clasifica con una tool → transfiere a subagente → subagente
llama a `search_runbooks`/`search_codebase`/`record_progress`), que requiere
varias tool-calls encadenadas dentro de la misma conversación. El patrón que
emergió:

- **Modelos no-razonadores** (Llama 3.3): tool-calling menos estricto en el
  formato, puede fallar en generar la sintaxis exacta que espera el parser.
- **Modelos razonadores** (gpt-oss, Qwen3.6): el campo adicional
  `reasoning_content` que emiten no es compatible con cómo Groq valida los
  mensajes reenviados en el historial multi-turno vía LiteLLM — esto es un
  problema de integración entre LiteLLM/ADK y la validación de Groq, no algo
  ajustable desde nuestro código de agente.

**Decisión:** por ahora el sistema sigue con Gemini (y Claude/OpenAI vía
LiteLLM, no probados en este punto pero con formato de tool-calling más
maduro/estandarizado) como los modelos confiables para el flujo agéntico
completo. Groq queda documentado como opción de costo, con esta limitación
conocida — buen trade-off para la sección de decisiones de diseño del
informe: **confiabilidad de function-calling en flujos multi-tool-call
como criterio real para elegir modelo propietario vs. open-source**, más
allá del costo.

## Trabajo futuro

- Revisar si LiteLLM/ADK agregan soporte para strip-ear `reasoning_content`
  antes de reenviar el historial a proveedores que no lo soportan (podría
  ser un fix corto si se reporta upstream).
- Probar modelos no-razonadores adicionales de Groq (ej. `llama-3.1-8b-instant`)
  para acotar si el problema de sintaxis de Llama 3.3 es específico de ese
  modelo o del enfoque no-razonador en general.
