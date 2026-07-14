---
id: idse-pendientes-lote-enviado
title: Movimientos IDSE atorados en "Pendientes de envío" con lote ya aceptado
category: idse
tags: [idse, lote, pendientes, movements, desereti, imss]
summary: Movimientos aparecen pendientes de envío en IDSE aunque el lote ya fue aceptado por el IMSS.
related: [idse-cambiar-fecha-eliminar-duplicado, liquidacion-timbre-parcial]
---

## Síntoma

Movimientos aparecen en "Pendientes de envío" del módulo IDSE aunque el lote ya fue enviado y aceptado en IDSE. Caso resuelto así en julio 2026 (cliente Kuka, sub_company 7504, lote 438340901).

## Causa

Los `Movement` pendientes suelen ser filas duplicadas o no vinculadas al `Mexico::Desereti::Request` del lote; el request original puede estar completo (`pdf_response_success`, 45/45 successful) y aun así la pantalla muestra otros `Movement` en pending. El job `DetailedResponseService` solo reprocesa requests con `transaction_on > 2.months.ago`, así que casos viejos no se autocorrigen.

## Diagnóstico (consola, solo lectura)

```ruby
req = Mexico::Desereti::Request.find_by(batch_id: LOTE)
```
```ruby
req.transaction_status
```
```ruby
req.mexico_movements_requests.group(:status).count
```
```ruby
Movement.where(sub_company_id: SUB_COMPANY, idse_status: :pending)
```

## Corrección propuesta (revisión humana antes de ejecutar)

1. Consultar IDSE (solo lectura): `Mexico::Desereti::IdseRequest::DetailedResponseRequest.new(req, lote: req.batch_id).call`
2. Vincular los `Movement` pendientes faltantes creando `Mexico::Desereti::MovementsRequest` (status `pending`, `payload: { data: nil }`, `employee_identifier: mov.entity.employee_identifier`) apuntando al request del lote.
3. `Mexico::Desereti::SaveDetailedResponse.new(req, respuesta).success` — matchea por `employee_identifier`/NSS contra la respuesta real de IDSE y marca `reported!` solo lo confirmado (mejor que forzar estados con `update_all`).
4. Acuse: `PdfResponseRequest` + `SavePdfResponse#save_idse_file`; luego `req.update!(request_status: :finished_successful, request_errors: nil)`.

## Verificación

```ruby
Mexico::Desereti::PendingMovementsService.new(sub_company).all_movements.count
```
Debe dar 0.

## Caveat

Si los pendientes eran duplicados de movimientos ya vinculados, el request queda con `movements_requests` dobles por empleado → posibles filas duplicadas en Histórico automático. Alternativa para duplicados puros: ocultarlos con `removed_at: Date.current` (van a "Eliminados", reversible).
