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

## Variante: concepto con "Grava ISN" activo que no entra a la base

Ticket ejemplo (jul-2026, Safilo, empleado 485010, concepto "Seguro de Retiro" / key `retirement_insurance`): el concepto tiene el check "Grava ISN" activo pero no aparece en la base ni en el reporte.

**Causa (bug de código):** `RegionIsn::Base#calculate_taxable_base` hace `respond_to?("calculate_#{key}") ? send(...) : 0` — cualquier percepción cuya key no tenga un método `calculate_<key>` explícito queda fuera de la base ISN en silencio, sin consultar `integrated_deductions['isn']`. El fix permanente es de desarrollo; por consola solo se parcha el payload de los employee_payrolls afectados.

**Corrección (por cada EP del periodo):**

```ruby
isn = ep.payload['provisions']['isn']
tb = isn['value'].find { |v| v['key'] == 'taxable_base' }
isn['value'].insert(-2, { 'key' => KEY, 'label' => LABEL, 'display_value' => monto })
tb['display_value'] = (tb['display_value'].to_f + monto).round(2)
isn['total'] = (isn['total'].to_f + (monto * tasa)).round(2)
ep.save!
```

**Notas:**
- La tasa se deduce del propio payload (`total / taxable_base`; DIF = 4%).
- Validar el monto contra `ep.employee_perceptions.detect { |p| p.key == KEY }.final_value`, no contra el Excel del cliente.
- Avisar al cliente que el impuesto del periodo sube.
- Mientras no haya deploy del fix, repetir el parche cada quincena.
