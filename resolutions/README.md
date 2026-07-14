# Resolutions

Índice append-only de tickets resueltos, en `index.jsonl` (una línea JSON por resolución). Se escribe exclusivamente vía la tool MCP `log_resolution` — no editar a mano.

Cada línea:

```json
{
  "ticket_id": "identificador del ticket (subject del mail o ID interno)",
  "runbook_id": "id del runbook usado, o null si no había ninguno aplicable",
  "diagnosis": "resumen del diagnóstico",
  "script_proposed": "one-liners propuestos, o null si fue solo diagnóstico",
  "category": "idse | nomina | variabilidad | otro",
  "logged_at": "ISO 8601 UTC"
}
```

Sirve para `find_similar_tickets` (busca tickets pasados con patrón similar, no solo runbooks) y como semilla futura para nuevos runbooks cuando se acumulan casos sin uno aplicable.
