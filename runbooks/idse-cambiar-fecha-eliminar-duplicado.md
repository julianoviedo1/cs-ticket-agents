---
id: idse-cambiar-fecha-eliminar-duplicado
title: Cliente quiere quedarse con un solo movimiento IDSE pendiente y eliminar el duplicado
category: idse
tags: [idse, movements, fecha, date_imss, duplicado, kardex]
summary: Empleado con dos movimientos IDSE pendientes; conservar uno con fecha corregida y eliminar el otro.
related: [idse-pendientes-lote-enviado]
---

## Síntoma

Empleado con dos movimientos IDSE pendientes (p. ej. dos modificaciones de SBC con fechas distintas). El cliente quiere conservar uno con la fecha corregida y eliminar el otro.

## Causa

La fecha que usa IDSE (lista de pendientes del flujo automático y el TXT de envío) es el atributo `date_imss` dentro de `Movement#additional_information['attributes']`, **NO** la columna `movement_date`. El flujo oficial de la UI (`Mexico::Movements::Kardex::EmployeeMovementService#permit_params`) tampoco toca `movement_date`, así que editar solo `date_imss` es consistente con la plataforma. Eliminar = soft delete con `removed_at` (pestaña "Eliminados", reversible).

## Resolución preferida: por UI, sin consola

El cliente mismo puede hacerlo: botón "CAMBIAR FECHA DE MOVIMIENTO" (cambia `date_imss`; permitido cuando solo cambia la fecha) + botón de basurita (`removed_at`).

## Por consola (si no aplica la UI)

```ruby
keep = Movement.find(ID_KEEP)
```
```ruby
remove = Movement.find(ID_REMOVE)
```
```ruby
attr = keep.additional_information['attributes'].find { |a| a['key'] == 'date_imss' }; attr['value'] = 'YYYY-MM-DD'; keep.update!(additional_information: keep.additional_information)
```
```ruby
remove.update!(removed_at: Time.current)
```

## Variante bulk (carga masiva desde Excel)

Caso real: STP, 190 empleados desde Excel de carga masiva. El "Id del empleado" del formato de carga masiva es `employee_identifier` (string), no el id de BD. Los empleados suelen tener varios movimientos pendientes (duplicados de recálculos de kardex con SBC que difiere por centavos, y pendientes viejos 2021+, muchos infonavit con `sbc` nil).

**Selección correcta:** por empleado, el movimiento pendiente cuyo `sbc` (round 2) coincida con el SBC del Excel; de haber varios, `max_by(&:movement_date)`.

**Verificar antes de aplicar:**
- `count == total Excel`
- todas las fechas iguales
- todas las acciones `modification` (las `registration` tienen callback que recalcula `started_working_at`)

Actualizar `movement_date` Y `date_imss` juntos en transacción con `update!`.
