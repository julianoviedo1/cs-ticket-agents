---
id: reporte-cep
title: Generar el reporte CEP de una nómina por consola
category: reportes
tags: [cep, stp, dispersion, reportes]
summary: Crear el Mexico::CepReport y correr el job síncrono cuando el reporte CEP no existe o falló.
related: []
---

## Síntoma

El cliente pide el reporte CEP de una o varias nóminas y no aparece / no se descarga.

## Contexto

El reporte CEP se arma con los datos de la **dispersión STP** (fecha, `tracking_key`, instituciones operante/cooperante, cuenta beneficiaria y monto de cada `Mexico::Stp::EmployeeStpProcess` en estado `finished` — colección en Mongo). Sin dispersión STP finalizada no hay CEP posible.

## Diagnóstico

```ruby
# ¿Existen reportes previos y en qué estado?
Mexico::CepReport.where(payroll_id: [IDS]).map { |r| [r.id, r.payroll_id, r.report_status, r.report_errors] }

# ¿Hay datos de dispersión STP para armarlo?
p = Payroll.find(ID)
ids = p.stp_processes.find_by_statuses(%w[finished finished_with_errors]).pluck(:id)
Mexico::Stp::EmployeeStpProcess.where(:stp_process_id.in => ids).finished.count
```

- Count > 0 → hay datos, se puede generar.
- Count = 0 → la nómina no se dispersó por STP (o no terminó); el reporte saldría con `insufficient_information`. Confirmar con el cliente cómo pagaron.

## Corrección

```ruby
r = Mexico::CepReport.create!(payroll_id: ID, report_status: 'processing')
MexicoJobs::Payrolls::GenerateCepFileJob.perform_now(r.id)
[r.reload.report_status, r.cep_file_file_name, r.report_errors]
```

Esperado: `finished_successful` + nombre de archivo. Con 1 proceso STP y <500 empleados sale un `.txt` único; si no, `.zip`.

## Verificación

El archivo queda descargable desde la UI de la nómina. URL directa si hace falta:

```ruby
r.download_url_for('cep_file')
```

## Notas

- `report_status: 'finished_with_errors'` + `insufficient_information` = sin datos STP (ver diagnóstico).
- El job es idempotente sobre el mismo `CepReport`; se puede re-correr con `perform_now` si quedó en `processing` colgado.
