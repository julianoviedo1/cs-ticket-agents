---
id: nomina-agregar-empleado-falla-silenciosa
title: Agregar empleado a nómina falla en silencio (front y API) — INFONACOT negativo por incapacidad de periodo completo
category: nomina
tags: [employee_payroll, infonacot, disability, deductions, add-employee]
summary: save sin bang oculta el error real de validación; bug conocido de INFONACOT negativo cuando una incapacidad cubre todo el periodo de la nómina.
related: [nomina-planchar-exento-gravado-hrs-extras]
---

## Síntoma

"Al agregar el colaborador a la nómina no guarda el cambio, ni desde front ni por API" — sin mensaje de error visible.

## Causa raíz general

`Mexico::Payrolls::Processes::AddEmployeePayrollProcessService#call` llama a `calculator.save_employee_payroll`, que internamente hace `employee_payroll.save` (sin bang) — si falla una validación del modelo, el método devuelve `false` sin levantar excepción, y el servicio sigue de largo sin abortar ni informar el error real al front/API.

## Diagnóstico

Reproducir el flujo paso a paso con rollback para ver el error real de validación:

```ruby
ActiveRecord::Base.transaction do
  payroll = Payroll.find(PAYROLL_ID)
  employee = Employee.find(EMPLOYEE_ID)
  payroll_calculation_dependency = Mexico::Payrolls::PayrollCalculationDependency.new(payroll)
  employee_payroll = EmployeePayroll.find_or_initialize_by(payroll_id: payroll.id, employee_id: employee.id)
  calculator = Mexico::Payrolls::EmployeePayrollCalculatorService.new(employee_payroll, payroll_calculation_dependency, true)
  calculator.assign_payload
  calculator.calculate_hours
  calculator.calculate_perceptions
  calculator.calculate_employee_recurrencies
  calculator.calculate_deductions
  calculator.calculate_provisions
  calculator.calculate_total_values
  saved = calculator.save_employee_payroll
  puts "saved=#{saved} errors=#{employee_payroll.errors.full_messages}"
  raise ActiveRecord::Rollback
end
```

## Caso conocido: "Employee deductions value debe ser mayor o igual que 0" — INFONACOT negativo por incapacidad de periodo completo

Si el empleado tiene una `DisabilityRequest` (`DisabilityRequest.by_employee_ids([id])` — no tiene `employee_id` directo, va vía `company_user`/`requester`) que cubre **todo el periodo de la nómina**, `Mexico::Payrolls::Deductions::Infonacot#discount_amount_days` calcula:

```
periodical_amount - (periodical_amount / hash_period * disability_days)
```

`hash_period` (15 para quincenal, vía `constants.calculation_based_on / 2`) puede no coincidir exactamente con los días de incapacidad calculados para el periodo (16, por conteo de días calendario inclusive). Ese desfase de 1 día hace que el resultado dé ligeramente negativo en vez de exactamente 0, y la validación del modelo (`value >= 0`) lo rechaza.

Es un bug de sistema (el descuento debería acotarse a mínimo 0 — `discount_amount_days` no aplica `positive_or_zero` al resultado, a diferencia de `period_days` que sí lo hace internamente) — reportable a Ingeniería.

### Workaround para destrabar el alta puntual

Correr el flujo del calculador manualmente, forzar a 0 el `employee_deduction` con `key: 'infonacot'` si viene negativo, y recién ahí completar el resto del cálculo y el guardado:

```ruby
payroll = Payroll.find(PAYROLL_ID)
employee = Employee.find(EMPLOYEE_ID)
payroll_calculation_dependency = Mexico::Payrolls::PayrollCalculationDependency.new(payroll)
employee_payroll = EmployeePayroll.find_or_initialize_by(payroll_id: payroll.id, employee_id: employee.id)
calculator = Mexico::Payrolls::EmployeePayrollCalculatorService.new(employee_payroll, payroll_calculation_dependency, true)
calculator.assign_payload
calculator.calculate_hours
calculator.calculate_perceptions
calculator.calculate_employee_recurrencies
calculator.calculate_deductions
infonacot = employee_payroll.employee_deductions.detect { |d| d.key == 'infonacot' }
infonacot.value = 0 if infonacot && infonacot.value.to_f.negative?
calculator.calculate_provisions
calculator.calculate_total_values
calculator.save_employee_payroll
calculator.update_employee_recurrency_tracking
payroll.reload
RegionService::RegionPayrollService.new(payroll.company.region, payroll.company, payroll).reload_payroll_total_values(true)
```

## Caveat

Probar SIEMPRE primero con rollback antes de correr la versión final. Si el empleado además tiene otras deducciones con montos base pequeños, revisar que ninguna otra dé negativa por el mismo tipo de desfase (no solo infonacot). Si ya existe un `EmployeePayroll` soft-deleted para el mismo empleado+nómina (`EmployeePayroll.with_deleted.where(...)`), no es la causa del bloqueo — `find_or_initialize_by` respeta el scope de paranoia y construye uno nuevo sin problema.
