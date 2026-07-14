---
id: cfdi-cancelar-uuid
title: Cancelar un CFDI de nómina por consola (sin relación / con relación)
category: timbrado
tags: [cfdi, cancelacion, uuid, employeepayrolluuid, pac, finkok]
summary: Motivo 02 (sin relación) vía EmployeePayrollUuid; motivo 01 (con relación) requiere UUID de sustitución y llamada directa al PAC con el CSD de la sub_company.
related: [liquidacion-timbre-parcial]
---

## Síntoma

"Me ayudan a cancelar el folio X" — el UUID no aparece en front/reportes para poder cancelarlo desde ahí, o se canceló "con relación" desde Runa pero al re-timbrar no quedó realmente cancelado ante el SAT.

## Localizar el employee_payroll

```ruby
payroll = Payroll.find(payroll_id)
employee_payroll = payroll.employee_payrolls.where(employee_id: X).last
```

Si no se tiene el employee_id, buscar por nombre: `company.employees.where('first_name ilike ? AND family_name ilike ?', '%NOMBRE%', '%APELLIDO%')`.

## Caso A: cancelar SIN relación (motivo 02, no genera sustituto)

```ruby
uuid = EmployeePayrollUuid.find_or_create_by!(employee_payroll_id: employee_payroll.id, uuid: uuid_to_cancel)
uuid.update!(uuid_type: 'payroll', cancel_reason: '02', total: BigDecimal('MONTO'), is_canceled: false, sat_validation_status: 'pending')
Mexico::PacsV2::Finkok::CancelStampEmployeePayrollUuids.new(employee_payroll_uuids: EmployeePayrollUuid.where(id: uuid.id)).call
```

## Caso B: cancelar CON relación (motivo 01, requiere UUID de sustitución)

Aplica por ejemplo cuando un re-timbrado dejó el folio viejo sin cancelar de verdad ante el SAT pese a que en Runa parecía cancelado. Motivo 01 exige mandar al PAC el UUID que sustituye al cancelado; si `CancelStampEmployeePayrollUuids` solo no alcanza, llamar directo al PAC:

```ruby
sub_company.load_fields_as_attributes(%w[csd_password])
cer_file_content = OpenURLUtil.call(sub_company.download_url_for('csd_cer')).read
key_file_content = OpenURLUtil.call(sub_company.download_url_for('csd_key')).read
cer_tmp_file = Tempfile.new(['cer_cancel_with_relation', '.cer'], Rails.root.join('tmp/')); cer_tmp_file.write(cer_file_content.force_encoding('utf-8')); cer_tmp_file.close
key_tmp_file = Tempfile.new(['key_cancel_with_relation', '.key'], Rails.root.join('tmp/')); key_tmp_file.write(key_file_content.force_encoding('utf-8')); key_tmp_file.close
key_password = sub_company.sub_company_fields.find_by(field_name: 'csd_password').raw_decrypted_value
sender_rfc = sub_company.sub_company_fields.find_by(field_name: 'rfc').value['value']
pac = Mexico::Pacs::Finkok.new(sub_company.company.time_zone)
pac.cancel('01', uuid_replacement, sender_rfc, cer_tmp_file.path, key_tmp_file.path, key_password, uuid_to_cancel)
key_tmp_file&.unlink; cer_tmp_file&.unlink
```

Después, sincronizar el registro local y el status del `employee_payroll`:

```ruby
Mexico::PacsV2::Finkok::CancelStampEmployeePayrollUuids.new(employee_payroll_uuids: EmployeePayrollUuid.where(id: [...])).call
Mexico::Payrolls::EmployeePayrollStamper.new(EmployeePayroll.find(ep_id), ep.payroll.sub_company).cancel('01')
```

## Caveat

Distinguir bien motivo 01 (con relación, requiere `uuid_replacement` — el folio nuevo que sustituye al viejo) de motivo 02 (sin relación, no requiere sustituto) — pedirlo explícito en el ticket si no viene claro.

El CSD (cer/key/password) se descarga de la `sub_company`, no de la `company`.

Verificar antes en el SAT (o en la captura que suele adjuntar el cliente) el estatus real del folio (`Cancelable sin aceptación` / `con aceptación`) antes de intentar.
