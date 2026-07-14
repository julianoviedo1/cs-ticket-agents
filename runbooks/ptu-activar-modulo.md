---
id: ptu-activar-modulo
title: Desbloquear la activación del módulo PTU
category: nomina
tags: [ptu, profitsharingpayment, activacion, registro-patronal]
summary: ProfitSharingPayment del año pasado in_progress/finished bloquea la activación; pending no bloquea.
related: []
---

## Síntoma

Ticket recurrente: "activar el módulo de PTU para el registro patronal X".

## Causa

Validación real (`Mexico::ProfitSharingPayments::Process::ProfitSharingPaymentProcessService#valid_to_create?`): bloquea si existe un `ProfitSharingPayment` con `sub_company`, `start_date = (hoy - 1 año).beginning_of_year`, `end_date = fin de ese año` y **status `in_progress` o `finished`**. Los `pending` **no** bloquean — no tocarlos.

## Diagnóstico

```ruby
sc.load_fields_as_attributes(%w[employer_registration]); sc.employer_registration
```
Identificar sub_company del registro patronal.

```ruby
ProfitSharingPayment.where(sub_company_id: X, start_date: Date.new(año_pasado,1,1), status: %w[in_progress finished])
```
Buscar el bloqueante.

## Corrección propuesta (patrón de CS, revisión humana antes de ejecutar)

Restar 1 año a `created_at`, `updated_at`, `start_date`, `end_date` y `save(validate: false)` — los cuatro campos, no solo las fechas de rango.

## Caveat

Si el bloqueante es `finished` con `report_date`, es un PTU real ya pagado — confirmar con el cliente que quieren correr otro del mismo ejercicio (riesgo de duplicar pago) y que en el historial quedará movido de año.

`ProfitSharingPayment` no tiene `company_id`, va por `sub_company_id`. `ProfitSharingPaymentProcess` sí tiene `company_id`.
