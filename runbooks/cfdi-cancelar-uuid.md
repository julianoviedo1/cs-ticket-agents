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

## Caso C: nómina/employee_payroll ELIMINADOS (soft-delete) y/o folio huérfano sin `payload['uuid']` vigente

`CancelStampEmployeePayrollUuids` (la orquestación de alto nivel) tiene dos bloqueos que pueden hacer que no pase nada, sin error visible:

1. `belongs_to :employee_payroll`/`:payroll` usan paranoia por defecto — si cualquiera de los dos está soft-deleted, `.employee_payroll`/`.payroll` devuelven `nil` y el servicio explota con `NoMethodError`.
2. `cancellation_reason` (`app/services/mexico/pacs_v2/finkok/cancel_stamp_employee_payroll_uuids.rb`) solo autoriza motivo 02 si `employee_payroll.payload['uuid'].present?` (un uuid "vigente" en el payload). Si el folio a cancelar es huérfano y el payload no tiene ningún uuid actual, `cancellation_reason` devuelve `nil` y el método corta en silencio — no cancela, no marca error.

**Fix para (1):** restaurar temporalmente el `deleted_at` con `update_columns` (no `.destroy`/`.restore`, para no disparar callbacks de `Payroll` como `create_payroll_event`), guardando el valor original ANTES de tocar nada en una variable aparte — no volver a leerlo del objeto ya mutado en memoria.

**Fix para (2):** llamar directo al servicio de bajo nivel `Mexico::PacsV2::Finkok::Api::Cancellation::CancelStamp` (bypasea la guarda de negocio), con las credenciales CSD de la sub_company (mismo patrón que Caso B pero con `cancel_reason: '02'` y `uuid_replacement: nil`):

```ruby
payroll = Payroll.with_deleted.find(payroll_id)
ep = EmployeePayroll.with_deleted.find(ep_id)
original_payroll_deleted_at = payroll.deleted_at
original_ep_deleted_at = ep.deleted_at
payroll.update_columns(deleted_at: nil)
ep.update_columns(deleted_at: nil)

sub_company = payroll.sub_company
sub_company.load_fields_as_attributes(%w[csd_password])
cer_file_content = OpenURLUtil.call(sub_company.download_url_for('csd_cer')).read
key_file_content = OpenURLUtil.call(sub_company.download_url_for('csd_key')).read
cer_tmp_file = Tempfile.new(['cer_cancel', '.cer'], Rails.root.join('tmp/')); cer_tmp_file.binmode; cer_tmp_file.write(cer_file_content.force_encoding('utf-8')); cer_tmp_file.close
key_tmp_file = Tempfile.new(['key_cancel', '.key'], Rails.root.join('tmp/')); key_tmp_file.binmode; key_tmp_file.write(key_file_content.force_encoding('utf-8')); key_tmp_file.close
key_password = sub_company.sub_company_fields.find_by(field_name: 'csd_password').raw_decrypted_value
sender_rfc = sub_company.find_sub_company_field_by_field_name('rfc')&.value&.dig('value')

service = Mexico::PacsV2::Finkok::Api::Cancellation::CancelStamp.new(cancel_reason: '02', uuid_to_cancel: uuid_to_cancel, uuid_replacement: nil, sub_company_rfc: sender_rfc, cer_path: cer_tmp_file.path, key_path: key_tmp_file.path, key_password: key_password)
begin
  service.send(:perform) # bypassea el rescue genérico de .call para leer FinkokError#code — .call solo guarda el mensaje traducido
  puts "CANCELADO OK"
rescue FinkokError => e
  puts "code=#{e.code} message=#{e.message}"
end

cer_tmp_file.unlink rescue nil
key_tmp_file.unlink rescue nil
payroll.update_columns(deleted_at: original_payroll_deleted_at)
ep.update_columns(deleted_at: original_ep_deleted_at)
```

Si sale OK o `code=202` ("Ya fue cancelado previamente"), actualizar el registro local: `EmployeePayrollUuid.find_or_initialize_by(employee_payroll_id: ep_id, uuid: uuid_to_cancel)` — ojo, `find_or_create_by!`/`.save!` normal también falla por la validación de presencia de `employee_payroll` si sigue soft-deleted; usar `.new` + `assign_attributes` + `.save!(validate: false)`, o hacerlo mientras `deleted_at` está en `nil`. Luego `update_columns(is_canceled: true, sat_validation_status: 'canceled', canceled_at: Time.current)`.

**Código 708 de Finkok** = "Error de conexión con el SAT" (mapeo explícito en `config/locales/mexico/stamp_error_messages.es.yml`, no fallback genérico) — es transitorio, no un rechazo de negocio; reintentar en 15-30 min si aparece.

## Caveat

Distinguir bien motivo 01 (con relación, requiere `uuid_replacement` — el folio nuevo que sustituye al viejo) de motivo 02 (sin relación, no requiere sustituto) — pedirlo explícito en el ticket si no viene claro.

El CSD (cer/key/password) se descarga de la `sub_company`, no de la `company`.

Verificar antes en el SAT (o en la captura que suele adjuntar el cliente) el estatus real del folio (`Cancelable sin aceptación` / `con aceptación`) antes de intentar.
