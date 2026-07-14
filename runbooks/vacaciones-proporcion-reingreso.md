---
id: vacaciones-proporcion-reingreso
title: Proporción de vacaciones inflada tras reingreso
category: nomina
tags: [vacaciones, request_balances, reingreso, rehire, antiquity_date]
summary: El total de vacaciones mostrado es la suma de request_balances activos; un reingreso deja un balance residual del ciclo anterior.
related: []
---

## Síntoma

"La proporción de días de vacaciones es mayor a la correcta" tras un reingreso (rehire). Ejemplo real: empleado 408126, mostraba 6.64 cuando lo correcto era ~1.86.

## Causa

El total mostrado es la **suma** de los `request_balances` activos del empleado. Tras un reingreso queda un balance residual del ciclo laboral anterior (con `belongs_to_year` alto, ej. 12) además del balance nuevo del año 1. En el ejemplo: 6.64 = 1.91 (correcto, año 1 desde reingreso) + 4.73 (residual).

## Diagnóstico (una línea por sentencia)

```ruby
employee = Employee.find(ID)
```
Revisar `antiquity_date`, `started_working_at`, `start_date_last_contract`, `employee.anniversary_calculated_by` (el cálculo usa `antiquity_date` o `start_date_last_contract` según el beneficio `calculated_by`, ver `employee.rb#first_day`).

```ruby
employee.region_employee_service.proportional_vacation_days
```
La proporción correcta al día de hoy (fórmula: días trabajados desde aniversario × días de política / 365, acumula a diario — el número del ticket puede estar unos décimos abajo si lo calcularon días antes).

```ruby
employee.request_balances.order(:start_date)
```
Revisar `belongs_to_year`, `status`, `init/current_balance`, `request_balance_transactions.count`.

## Corrección propuesta (revisión humana antes de ejecutar)

**Si las fechas están bien y solo sobra el balance residual:**
```ruby
stale.destroy
```
(`RequestBalance` es `acts_as_paranoid` + `paper_trail`, soft-delete auditado; verificar antes que `txns = 0`), luego recalcular:
```ruby
employee.update!(vacation_days: employee.request_balances.where(status: :active).sum(&:current_balance).round(2))
```
```ruby
employee.employee_fields.where(field_name: 'vacation_days').update_all(value: { value: total })
```

**Si la fecha base está mal:** corregirla primero y usar `Vacations::GoldenRecalc.new(company: c, dry_run: true, employee_id: ID).call` (reconstruye balances desde `antiquity_date`; correr primero con `dry_run`). OJO: `antiquity_date` también afecta finiquito/prima de antigüedad/aguinaldo.

## Caveat

**NO** parchar `current_balance` a mano sin arreglar la causa: el recálculo/acumulado diario lo pisa.
