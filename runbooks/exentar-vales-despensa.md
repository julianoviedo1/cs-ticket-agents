---
id: exentar-vales-despensa
title: Exentar vales de despensa en su totalidad sin recalcular ISR
category: nomina
tags: [pantry, vales, exento, gravado, isr, planchado]
summary: Poner grava=0 y exenta=importe en el payload ISR de las percepciones pantry de una nómina, sin tocar totales ni ISR.
related: [nomina-planchar-exento-gravado-hrs-extras]
---

## Síntoma

El cliente pide "exentar los vales de despensa en su totalidad" para todos los colaboradores de una nómina, usualmente con la instrucción explícita de **no recalcular ISR**.

## Contexto

- El split exento/gravado vive en `employee_perceptions` (key `pantry`), en `payload['isr']`: `grava`, `grava_monthly_with_discounts`, a veces `grava_monthly_without_discounts`, y `exenta`.
- El importe real de la percepción es `(custom_value || value)` (= `final_value`). En nóminas extraordinarias de despensa, `custom_value` suele traer el monto completo y `value` un residuo chico — usar siempre `final_value`.
- Los totales de nómina suman `final_value`, que no cambia → no hay que recalcular totales. El ISR solo cambiaría si se recalcula, que aquí NO se hace.

## Diagnóstico

```ruby
payroll = Payroll.find ID
[payroll.name, payroll.status]  # debe estar started/to_process (sin timbrar)
pantries = EmployeePerception.joins(:employee_payroll).where(employee_payrolls: { payroll_id: ID }, key: 'pantry')
pantries.count
pantries.limit(5).map { |p| [p.id, p.value.to_f, p.custom_value&.to_f, p.payload['isr']] }
```

## Corrección

```ruby
pantries.find_each do |p|
  importe = (p.custom_value || p.value).to_f.round(4)
  isr = p.payload['isr'] || {}
  isr['grava'] = 0
  isr['grava_monthly_with_discounts'] = 0
  isr['grava_monthly_without_discounts'] = 0 if isr.key?('grava_monthly_without_discounts')
  isr['exenta'] = importe
  p.payload['isr'] = isr
  p.save!
end
```

## Verificación

```ruby
pantries.reload.map { |p| p.payload.dig('isr', 'grava').to_f }.uniq  # => [0.0]
pantries.limit(5).map { |p| [(p.custom_value || p.value).to_f, p.payload.dig('isr', 'exenta').to_f] }  # pares iguales
```

## Notas

- Si la nómina ya está timbrada, esto no cambia el XML del SAT (habría que cancelar y re-timbrar).
- Dejar constancia en el ticket de que el ISR quedó sin recalcular a petición del cliente.
