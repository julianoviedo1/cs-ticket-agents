---
id: variabilidad-imss-revertir-proceso
title: Revertir un proceso de variabilidad IMSS para volver a promediar
category: variabilidad
tags: [imss, variabilidad, variableprocess, sdi, sbc, svar, kardex]
summary: Revertir VariableProcess de un bimestre para que el cliente re-promedie.
related: [idse-pendientes-lote-enviado]
---

## Síntoma

Ticket recurrente: "revertir el proceso de variabilidad del bimestre X para volver a promediar".

## Diagnóstico

```ruby
Mexico::Imss::VariableProcess.where(company_id: X, bimestral_date: Date.new(YYYY, M, 1))
```
(Mongo; `bimestral_date` = inicio del bimestre siguiente, ej. 3er bimestre may-jun → 2026-07-01). Puede haber varios (uno por sub-empresa).

Correr script de diagnóstico por empleado (comparar `aditional_info['current_sbc']` vs `next_sbc`):
- Si NO cambió (promedio 0) → solo borrar proceso.
- Si SÍ cambió → revertir empleado + kardex antes de borrar proceso.

## Corrección propuesta (revisión humana antes de ejecutar)

1. **Revertir empleado**: el apply (`Mexico::Imss::Variability::ApplyAverageService`) pisa `employee.payload['SDI'/'SBC'/'SVAR']` y el `employee_field` `sbc`, y crea/actualiza un Movement Kardex `modification` con `date_imss = bimestral_date`. Valores previos: del kardex anterior (buscar por `aditional_info['last_date']` con `Mexico::Imss::KardexQuery`), leyendo `find_value_by_key('sdi'/'variable_concepts'/'sbc')`. **Invariante:** SBC = SDI + SVAR (restaurar los tres, no solo SBC).
2. **Borrar el movement de variabilidad**: primero `mexico_movements_imss_reports.destroy_all` y `mexico_movements_requests.destroy_all` (únicas FKs a movements, causan "Ups! Movement está siendo utilizada"), luego `reload.destroy`. Verificar antes `created_at ≈ updated_at` (el `UpdateKardexService` reutiliza movements existentes del mismo día — si `created_at` es viejo, NO borrar, restaurar valores) y `idse_status` (si `reported`, ya se envió al IMSS, avisar al cliente).
3. **Borrar proceso**: `process.employee_variable_processes.destroy_all; process.destroy`.

## Caveat

Si la sub-empresa tiene el check `imss_variable_automatic` activo, el job automático puede regenerar el proceso en las mismas condiciones (nóminas abiertas → cálculo incorrecto). Avisar al cliente que lo desactive o cierre nóminas antes de re-promediar.
