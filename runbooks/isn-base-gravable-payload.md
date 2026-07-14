---
id: isn-base-gravable-payload
title: Reporte ISN muestra base gravada sin descontar un concepto negativo
category: nomina
tags: [isn, taxable_base, payload, provisions, reporte]
summary: El reporte ISN es un volcado del payload; corregir display_value de taxable_base si un fix previo no lo recalculó.
related: []
---

## Síntoma

Ticket ejemplo (julio 2026, AIDC II, payroll 725731, empleado 489626): el reporte de ISN por empleado mostraba en BASE GRAVADA (col P) $44,933.33 en vez de $39,933.33 — el concepto negativo "Salario pagado en exceso" (-5,000) aparecía como columna pero no restaba de la base. El ISN calculado sí estaba bien.

## Causa

Los reportes ISN (`Mexico::IsnReport`, por empleado y por concepto) son un volcado directo de `employee_payrolls.payload['provisions']['isn']`: `value` es un array de `{'key','label','display_value'}` (incluye el renglón `key: 'taxable_base'`) y `total` es el impuesto. Si un fix anterior agregó un concepto negativo y ajustó el `total` pero no recalculó el `display_value` de `taxable_base`, el reporte queda inconsistente. Corregir el payload arregla ambos reportes.

## Diagnóstico (una línea por paso)

```ruby
ep = EmployeePayroll.joins(:employee).where(payroll_id: PAYROLL_ID, employees: { employee_identifier: 'IDENT' }).first; isn = ep.payload['provisions']['isn']; puts "ep_id: #{ep.id} | total: #{isn['total']} | valores: #{isn['value'].map { |v| [v['key'], v['label'], v['display_value']] }.inspect}"
```

## Corrección propuesta (revisión humana antes de ejecutar)

```ruby
tb = isn['value'].find { |v| v['key'] == 'taxable_base' }; tb['display_value'] = NUEVO_VALOR; ep.save!
```

## Verificación

La suma de `display_value` de los conceptos (sin `taxable_base`) debe igualar el nuevo `taxable_base`. No tocar `total` si el impuesto ya está bien. El cliente regenera el reporte.
