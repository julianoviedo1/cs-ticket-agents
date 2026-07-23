---
id: ptu-cambiar-mes-acumulado
title: Cambiar el mes de acumulado de una nómina PTU/finiquito
category: ptu
tags: [ptu, finiquito, acumulados, payroll_schedule, tax_incidence]
summary: Reasignar el mes en que una nómina aparece en el histórico "acumulados" cuando no coincide con la fecha real de pago.
related: [ptu-activar-modulo]
---

## Síntoma

"El pago de PTU de <ex empleado> se hizo el día X, pero en el histórico se acumuló en otro mes (el del periodo de la nómina). Necesito que se acumule en el mes real del pago."

## Contexto

La vista de nóminas históricas ("acumulados") usa `PayrollListSerializer#calendar_month`/`calendar_year`, que leen `payroll.payroll_schedule&.tax_incidence_month`/`tax_incidence_year`. Las nóminas PTU/finiquito de un solo empleado normalmente **no tienen** `payroll_schedule` — por eso el frontend cae a agrupar por `start_date`/`end_date` de la `Payroll` (el periodo real de la liquidación, que casi nunca coincide con la fecha en que se pagó).

## Trampa conocida — NO usar

`payroll.update(start_date:, end_date:, started_at:)` (la acción `update_report_dates` del controller). Eso mueve el periodo real de la nómina (nombre del recibo, fechas mostradas al empleado) — es semánticamente incorrecto para este caso, y no está garantizado que reagrupe correctamente si la nómina llega a tener `payroll_schedule` en el futuro.

## Corrección

```ruby
payroll = Payroll.find(PAYROLL_ID)
employee = payroll.employee_payrolls.first.employee
schedule = payroll.payroll_schedule || payroll.create_payroll_schedule!(
  payroll_group: employee.payroll_group,
  start_date: payroll.start_date,
  end_date: payroll.end_date,
  start_date_incidence: payroll.start_date_incidence || payroll.start_date,
  end_date_incidence: payroll.end_date_incidence || payroll.end_date,
  tax_incidence_month: payroll.start_date.month,
  tax_incidence_year: payroll.start_date.year
)
schedule.update_columns(tax_incidence_month: MES, tax_incidence_year: AÑO, updated_at: Time.current)

CompanyActionCache.where(company: payroll.company, action: 'payroll_historicals').update_all(result: nil)
payroll.touch
```

Se puede aplicar en lote a varios `Payroll` de la misma empresa (recorrer un array de IDs).

## Diagnóstico / identificar el payroll correcto

**Ojo:** el "ID" que da el cliente en el ticket con frecuencia NO es el `payroll_id` — suele ser un `employee_payroll_id` de una nómina totalmente distinta y sin relación (visto repetidas veces). Buscar por nombre en la empresa correcta y confirmar antes de tocar nada:

```ruby
Payroll.where(company_id: COMPANY_ID).where("name ILIKE ?", "%nombre del ex empleado%")
  .map { |p| [p.id, p.name, p.start_date, p.end_date, p.status, p.employee_payrolls.first&.paid_at] }
```

Confirmar dos cosas antes de aplicar el fix:
- `start_date` de la nómina candidata cae en el mes "equivocado" que reporta el cliente.
- `employee_payrolls.first.paid_at` coincide con la fecha de pago real que da el ticket.

Puede haber varias nóminas PTU del mismo empleado (distintos ejercicios/años) con nombres iguales — filtrar por las fechas, no solo por el nombre.

## Verificación

```ruby
payroll.reload
[payroll.id, payroll.payroll_schedule&.tax_incidence_month, payroll.payroll_schedule&.tax_incidence_year]
```

Debe reflejar el mes/año pedido. Invalidar el `CompanyActionCache` es obligatorio — sin eso el cliente sigue viendo el agrupamiento viejo por varios minutos/horas (cache de `payroll_historicals`).
