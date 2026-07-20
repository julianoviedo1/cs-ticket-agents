---
id: cfdi-cancelar-con-relacion-diferida
title: Cancelar CFDI con relación cuando aún no existe el sustituto (re-timbrado posterior)
category: timbrado
tags: [cfdi, cancelacion, motivo-01, pending_cancellation, folio-sustitucion]
summary: Marcar pending_cancellation antes del cancel('01') para diferir la cancelación hasta el re-timbrado; Finkok ya exige FolioSustitucion en solicitudes inmediatas.
related: [cancelar-cfdi-uuid, cfdi-retimbrar-fecha-pago]
---

## Síntoma

Ticket: "cancelar con relación este finiquito/nómina, el cliente hará cambios al cálculo y re-timbrará después". No existe todavía el CFDI sustituto, así que una cancelación motivo 01 inmediata es imposible.

## Trampa conocida

`Mexico::Payrolls::EmployeePayrollStamper#cancel('01')` llama al PAC **de inmediato** salvo que `pending_cancellation` ya esté en `true`. Finkok ahora rechaza motivo 01 sin `FolioSustitucion`:

> "Motivo cancelación es 01, FolioSustitucion del CFDI es requerido."

y el `ensure` del método deja al employee_payroll en `cancel_error` con el error en `payload['stamp_error_message']` (el uuid NO se limpia).

## Corrección

```ruby
payroll = Payroll.find ID
ep = payroll.employee_payrolls.first  # verificar empleado/uuids antes
# si ya cayó en cancel_error por el intento directo:
ep.payload.delete('stamp_error_message')
ep.status = 'finished'
ep.save!
# la clave: diferir la cancelación
ep.cancelable   # pending_cancellation = true
stamper = Mexico::Payrolls::EmployeePayrollStamper.new(ep.reload, payroll.sub_company)
stamper.cancel('01')  # con pending_cancellation true NO llama al PAC, solo registra y limpia
```

## Verificación

```ruby
ep.reload
[ep.status, ep.payload['uuid'], ep.pending_cancellation]
# => ["stamp_canceled", nil, true]
EmployeePayrollUuid.where(employee_payroll_id: ep.id).pluck(:uuid, :cancel_reason, :is_canceled, :sat_validation_status)
# => registro motivo 01, is_canceled false, pending
```

La nómina queda editable; al re-timbrar, el XML nuevo incluye `CfdiRelacionados TipoRelacion 04` y la cancelación del folio viejo se concreta ante el SAT con el sustituto.

## Notas

- Avisar al cliente: el folio viejo sigue "Vigente" en el SAT hasta que re-timbren — comportamiento esperado.
- Si el finiquito tiene partición de liquidación (advanced uuid), el mismo `cancel('01')` registra ambos UUIDs.
- Si después del re-timbrado el folio viejo no cae (798 / atorado en Finkok), ver el runbook de re-timbrado por fecha de pago (códigos 207/798, GetSatStatus).
