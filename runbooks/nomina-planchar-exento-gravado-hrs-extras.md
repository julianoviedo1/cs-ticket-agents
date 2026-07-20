---
id: nomina-planchar-exento-gravado-hrs-extras
title: '"Planchar" exento/gravado de horas extras y descanso laborado desde Excel MEC'
category: nomina
tags: [perceptions, isr, exento, gravado, horas-extras, descanso-laborado, plachado]
summary: Fijar manualmente exento/gravado en el payload de la percepción y recalcular ISR y totales sin dejar que el sistema los recalcule desde cero.
related: []
---

## Síntoma

El cliente envía un Excel "MEC_Formato plachado de datos_<n>.xlsx" pidiendo "planchar" (fijar manualmente) el exento y gravado de horas extras y/o Descanso Laborado en una nómina, y recalcular ISR y totales. "Planchar" = el cliente ya calculó los montos correctos afuera y quiere que el sistema los refleje tal cual, sin recalcularlos desde cero.

## Layout del Excel

Fila 2 = headers, fila 3+ = datos por empleado. A=Clave (employee_identifier), B=Nombre.

Bloque que se usa para el payload (horas extras): `I=double_hours_amount, J=triple_hours_amount, K=grava, L=grava_monthly_with_discounts, M=exenta, N=rest_double_to_exempt`.

Descanso Laborado: `P=Importe, Q=Exento, R=Gravado`.

## Modelos/campos

`Payroll` → `EmployeePayroll` (ep) → `EmployeePerception` (keys `'extra_hours'` y `'rest_day_worked'`). Campos: `payload` (hash con `"isr"=>{"grava","grava_monthly_with_discounts","exenta"}`, `"double_hours_amount"`, `"triple_hours_amount"`, `"rest_double_to_exempt"`), `value`, `custom_value`.

`EmployeePerception#final_value` = `(custom_value || value).to_f` — es lo que suma `calculate_total_perceptions` para los totales de nómina.

## Diagnóstico

```ruby
payroll = Payroll.find(ID)
ep = payroll.employee_payrolls.joins(:employee).find_by(employees: { employee_identifier: 'CLAVE' })
p = ep.employee_perceptions.find_by_key('extra_hours'); puts "value=#{p.value} custom_value=#{p.custom_value} payload=#{p.payload.inspect}"
```

## Corrección (por empleado, con valores del Excel)

```ruby
p = ep.employee_perceptions.find_by_key('extra_hours')
p.payload = { "double_hours_amount" => I, "triple_hours_amount" => J, "isr" => { "grava" => K, "grava_monthly_with_discounts" => L, "exenta" => M }, "rest_double_to_exempt" => N }
p.value = I.to_f + J.to_f
p.custom_value = nil
p.save
```

Si hay Descanso Laborado:
```ruby
rd = ep.employee_perceptions.find_by_key('rest_day_worked')
rd.value = P
rd.payload['isr'] = { 'grava' => P, 'grava_monthly_with_discounts' => P, 'exenta' => M }
rd.save
```

Por empleado:
```ruby
CustomerService::RecalculateEmployeePayrollISR.new(ep).call
```

Al final, una vez por nómina:
```ruby
RegionService::RegionPayrollService.new(payroll.company.region, payroll.company, payroll).reload_payroll_total_values(true)
```

## Caveat

**Crítico (bug real confirmado, ticket 739162):** si solo se actualiza `.payload` y no `.value`, el ISR queda bien (lee `payload['isr']['grava']`) pero los **totales de la nómina quedan mal** (siguen sumando el `.value` viejo). Siempre fijar `.value = double_hours_amount + triple_hours_amount` junto con el payload.

`custom_value` gana sobre `value` en `final_value` — si la percepción fue editada en UI (split override), ponerlo en `nil` al planchar.

Ni `RecalculateEmployeePayrollISR` ni `reload_payroll_total_values` recalculan perceptions: solo leen lo ya guardado — es el comportamiento deseado al planchar.

Validar primero con `ActiveRecord::Base.transaction` + `raise ActiveRecord::Rollback` antes del run real.
