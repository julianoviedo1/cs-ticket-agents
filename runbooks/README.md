# Runbooks

Base de conocimiento de tickets de CS resueltos. Cada archivo `.md` documenta un patrón recurrente: síntoma, causa, diagnóstico read-only y corrección propuesta.

## Formato

```yaml
---
id: slug-unico
title: Título corto y descriptivo
category: idse | nomina | variabilidad | otro
tags: [palabras, clave, para, busqueda]
summary: Una línea, se muestra en resultados de búsqueda.
related: [otro-runbook-id]
---
```

Cuerpo en markdown, secciones típicas: Síntoma, Causa, Diagnóstico, Corrección propuesta, Verificación, Caveat.

## Regla de estilo (obligatoria)

Todo script de consola debe estar separado en **bloques de una sola línea** (statements unidos con `;`, `{ }` en vez de `do/end`, `if...;...;end` inline). Cada bloque va en su propio ```ruby``` fence, pegable por separado en la consola Rails de producción — no soporta paste multilínea bien.

## Cómo se consume

El servidor MCP (`mcp_server/`) expone estos runbooks a los agentes vía `search_runbooks` / `get_runbook`. No editar el índice a mano — se genera leyendo este directorio en cada consulta.
