---
id: liquidacion-timbre-parcial
title: Nómina de liquidación atorada en stamped_error con solo un UUID timbrado
category: nomina
tags: [liquidacion, timbre, cfdi, stamp, uuid]
summary: Completar el CFDI de liquidación faltante por consola cuando la UI no puede reintentar.
related: [idse-pendientes-lote-enviado]
---

## Síntoma

Una liquidación timbra 2 CFDIs por empleado: normal (`payload['uuid']`) y liquidación (`payload['advanced']['uuid']`). Si falla el segundo, el EP queda `stamped_error` y la UI **no puede reintentar**: `StampProcessService` excluye EPs con `payload->>'uuid'` presente (`stamp_process_service.rb` ~L62). El job al fallar además pone `paid_at = nil`.

## Diagnóstico

```ruby
ep.payload.dig('advanced','stamp_error_message')
```
Si es "Ups! Vuelve a intentar timbrar" fue transitorio, retimbrable.

```ruby
Mexico::StampProcess.where(payroll_id: X).order(created_at: :desc).first.paid_at
```
Recuperar fecha de pago (Mongo).

## Corrección propuesta (timbra SOLO la partición faltante, no toca el UUID existente)

```ruby
ep.update(paid_at: sp.paid_at)
```
```ruby
Mexico::Payrolls::ChangeEmployeeDischarge.call(ep)
```
```ruby
payroll_decorated = Mexico::PayrollDecorator.new(payroll)
```
```ruby
split = Mexico::Payrolls::Split::LaborSettlement.new(payroll_decorated, [ep.id])
```
```ruby
partition = split.labor_settlement.employee_payrolls.last
```
```ruby
stamper = Mexico::Payrolls::EmployeePayrollStamper.new(partition, payroll_decorated.sub_company, :labor_settlement)
```
```ruby
stamper.stamp(sp, 2)
```

El stamper carga CSDs solo, y en éxito limpia el error, pone status `stamped`, guarda `advanced uuid` + `stamped_xml_advanced` + `receipt_pdf_advanced`. No hace falta limpiar error/status antes.

## Caveat

**NO** usar `RestampPayrollHelper#restamp_payrolls` (cancela UUIDs buenos). Cierre: `ep.finished!` y payroll a `finished` si la UI no lo permite.
