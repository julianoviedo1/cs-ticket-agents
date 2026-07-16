---
id: cfdi-retimbrar-fecha-pago
title: Re-timbrar CFDI con fecha de pago equivocada (cancelar con referencia)
category: timbrado
tags: [cfdi, retimbrado, cancelacion, motivo-01, paid_at, restamp]
summary: Usar RestampPayrollHelper para re-timbrar con el paid_at correcto y gestionar la cancelación con relación del folio viejo.
related: [cancelar-cfdi-uuid, liquidacion-timbre-parcial]
---

## Síntoma

"Timbré con fecha (de pago) equivocada, me ayudan a cancelar con referencia y re-timbrar" — nómina ya timbrada/finished, se necesita CFDI nuevo con `paid_at` correcto y cancelación motivo 01 del folio anterior.

## Corrección

```ruby
payroll = Payroll.find ID
eps = payroll.employee_payrolls
# fijar la fecha de pago correcta ANTES (el helper toma pluck(:paid_at).uniq.compact.last)
eps.each { |e| e.update_columns(paid_at: Date.new(YYYY, M, D)) }
include RestampPayrollHelper
restamp_payrolls("tag-del-ticket", [{ 'payroll_id' => ID, 'employee_ids' => eps.pluck(:employee_id) }])
```

El helper: guarda el/los UUID viejos como `EmployeePayrollUuid` motivo 01, limpia el payload, re-timbra (el XML nuevo incluye `CfdiRelacionados TipoRelacion 04` al viejo, porque `pending_cancellation` + el registro motivo 01 existen al timbrar) y regenera recibos.

## Verificación

```ruby
ep.reload; [ep.status, ep.paid_at, ep.payload['uuid']]
AdminRestampPayrollEntry.where(employee_payroll_id: ep.id).pluck(:error, :message, :tag)
xml = OpenURLUtil.call(ep.employee_payroll_files.find_by(key: 'stamped_xml').download_url_for('employee_payroll_document')).read
xml[/<cfdi:CfdiRelacionados.*?CfdiRelacionados>/m]  # debe traer el UUID viejo con TipoRelacion 04
```

## Cancelación del folio viejo — OJO

`restamp_payrolls` **NO encola** `EmployeePayrollUuidCancellerJob`: el folio viejo queda `is_canceled: false, sat_validation_status: pending`. Lo levantan los sweepers nocturnos (`UuidSatStatusJob` 01:00 y `ReCancelUuidsJob` 03:00 CDMX), o a mano:

```ruby
Mexico::PacsV2::Finkok::CancelStampEmployeePayrollUuids.new(employee_payroll_uuids: EmployeePayrollUuid.where(id: X)).call
```

### Códigos de error vistos

- **305** "fecha de emisión fuera de la vigencia del CSD" — verificar el cert real: `OpenSSL::X509::Certificate.new(cer).not_before/.not_after`; puede ser mapeo engañoso de otro código.
- **207** — motivo 01 cuyo `FolioSustitucion` el SAT **aún no indexa** (CFDI sustituto timbrado hace minutos). No es error de construcción: esperar unas horas y reintentar (los jobs nocturnos lo hacen solos).

## Notas

- El helper puede ajustar la job position de empleados dados de baja (tipo "Sueldos"/contrato indeterminado) como parte del flujo estándar.
- El CFDI nuevo sale con fecha de timbrado actual; la fecha de pago es la que se fijó en `paid_at`.
- Confirmar con el cliente que SOLO la fecha estaba mal — el re-timbrado usa los montos actuales de la nómina tal cual.
