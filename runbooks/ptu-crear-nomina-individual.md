---
id: ptu-crear-nomina-individual
title: Crear la nómina de PTU de un empleado puntual
category: nomina
tags: [ptu, profitsharingpayment, profitsharingpaymentemployee, payroll]
summary: Dar de alta el pago de PTU de un empleado dentro de un ProfitSharingPayment ya existente y crear su nómina si no existe.
related: [ptu-activar-modulo]
---

## Síntoma

Ticket recurrente: "me ayudan a crear la nómina PTU para el empleado X" con monto y días laborados, dando la URL del módulo PTU (`.../payrolls/ptu/payrolls_ptu/<sub_company_id>/<profit_sharing_payment_id>`) y del empleado. Aplica también a empleados con status de baja.

## Diagnóstico previo (confirmar antes de correr)

```ruby
company = Company.find_by!(subdomain: X)
employee = company.employees.find(ID)
puts "#{employee.first_name} #{employee.family_name} status=#{employee.status}"
sub_company = employee.payroll_group.sub_company
puts "sub_company=#{sub_company.id} (debe coincidir con el de la URL)"
payment = ProfitSharingPayment.find(<id de la URL>)
puts "payment sub_company_id=#{payment.sub_company_id} status=#{payment.status} report_date=#{payment.report_date}"
puts "company_banks=#{sub_company.company_banks.pluck(:id)}"
existing = payment.payrolls.where(extraordinary_type: 'ptu').joins(:employee_payrolls).find_by(employee_payrolls: { employee_id: employee.id })
puts "payroll existente=#{existing&.id}"
```

## Corrección

Dentro de `ActiveRecord::Base.transaction`:

1. `ProfitSharingPaymentEmployee.find_or_initialize_by(profit_sharing_payment: payment, employee: employee)` con `payload = {'employee_identifier' => ..., 'ptu' => monto, 'worked_days' => días}` y `save!`.
2. Si no existe ya la `payroll` de PTU de ese empleado dentro de `payment.payrolls`, crearla con `Mexico::Entities::PayrollService.new(company.region, company, type: 'extraordinary').create_object(...)`:
   - `name`: `"NOMINA PTU #{employee.name}"`
   - `extraordinary_type`: `'ptu'`
   - `currency_id`: `Currency.find_by!(code: 'MXN').id`
   - `sub_company_id`: `sub_company.id`
   - `company_bank_id`: primer `company_bank` de la sub_company
   - `start_date`/`end_date`: `payment.report_date || Date.current`
   - `employee_ids`: `[employee.id]`
3. `payment.payrolls << payroll`.

```ruby
company = Company.find_by!(subdomain: X)
employee = company.employees.find(ID)
sub_company = employee.payroll_group.sub_company
ptu_amount = MONTO
worked_days = DIAS
payment = ProfitSharingPayment.find(PAYMENT_ID)
report_date = payment.report_date || Date.current
company_bank = sub_company.company_banks.first
payroll = nil

ActiveRecord::Base.transaction do
  payment_employee = ProfitSharingPaymentEmployee.find_or_initialize_by(profit_sharing_payment: payment, employee: employee)
  payment_employee.payload = { 'employee_identifier' => employee.employee_identifier, 'ptu' => ptu_amount, 'worked_days' => worked_days }
  payment_employee.save!

  payroll = payment.payrolls.where(extraordinary_type: 'ptu').joins(:employee_payrolls).find_by(employee_payrolls: { employee_id: employee.id })

  unless payroll
    payroll_service = Mexico::Entities::PayrollService.new(company.region, company, type: 'extraordinary')
    payroll_params = ActionController::Parameters.new(payroll: { name: "NOMINA PTU #{employee.name}", extraordinary_type: 'ptu', currency_id: Currency.find_by!(code: 'MXN').id, sub_company_id: sub_company.id, company_bank_id: company_bank.id, start_date: report_date, end_date: report_date, employee_ids: [employee.id] })

    unless payroll_service.create_object(payroll_params)
      errors = payroll_service.object&.errors&.full_messages&.to_sentence
      raise "Could not create PTU payroll for employee #{employee.id}: #{errors.presence || 'unknown error'}"
    end

    payroll = payroll_service.object.reload
    payment.payrolls << payroll
  end
end
```

## Caveat

Esto solo crea/asocia la nómina — no la timbra ni la cierra. Validar primero con rollback antes del run real.
