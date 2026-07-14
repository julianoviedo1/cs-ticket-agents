---
id: perfil-editar-bloqueado-salario-minimo
title: Editar campos de perfil que el front bloquea (salario < mínimo, empleado de baja)
category: perfil
tags: [salario, banco, politica, antiguedad, employee_field, job_position]
summary: Sincronizar employee_field + columna Employee + job position con update_columns para saltear la validación que bloquea el front.
related: [ptu-activar-modulo]
---

## Síntoma

Ticket recurrente: "no me deja editar X del empleado porque su sueldo es menor al mínimo / está de baja". Aplica a sueldo bruto, datos bancarios, política, antigüedad, fecha de inicio de contrato.

## Causa

El front valida contra el salario mínimo (o el estado de baja) antes de permitir el guardado. Caso legal típico: jornada reducida (medio tiempo), donde un sueldo por debajo del mínimo general es válido.

## Regla de oro

Sincronizar las 3 fuentes o el dato queda inconsistente entre perfil y nómina:
1. `EmployeeField` (lo que muestra el front).
2. `employee.current_employee_job_position` — **no** `employee_job_positions[0]`, no garantiza que sea la vigente (puede haber varias históricas).
3. Columna directa en `Employee` cuando aplica (antigüedad, fecha de contrato).

Usar `update_columns` para saltear validaciones/callbacks — `.save` sin bang falla en silencio (devuelve `false`) si la validación de mínimo rechaza el monto.

## Diagnóstico

```ruby
employee = Employee.find(ID)
puts "#{employee.first_name} #{employee.family_name} - status=#{employee.status} company=#{employee.company.subdomain}"
puts "monthly_amount field: #{employee.employee_fields.find_by(field_name: 'monthly_amount')&.value.inspect}"
jp = employee.current_employee_job_position; puts "job_position=#{jp&.id} monthly_amount=#{jp&.monthly_amount} status=#{jp&.status}"
```

## Corrección por campo

**Sueldo (`monthly_amount`)**:
```ruby
employee.employee_fields.find_by!(field_name: 'monthly_amount').update_columns(value: { 'value' => 7800.0 }, updated_at: Time.current)
employee.current_employee_job_position.update_columns(monthly_amount: 7800.0, updated_at: Time.current)
```

**Banco**: field `bank_id` con `{"entity"=>"bank","id"=>bank.id,"display_value"=>bank.name,"value"=>bank.name}`, más `interbank_number` y `number_account` (`{"value"=>...}`). Verificar `Bank` por `region_id: 1` (México) — hay homónimos de otras regiones con el mismo nombre. Prefijos CLABE útiles para identificar el banco: 002=Banamex, 012=BBVA, 014=Santander.

**Política (`policy_id`)**: field con `{"entity"=>"policy","id"=>id,"display_value"=>nombre}` + `position.policy_id`.

**Antigüedad (`antiquity_date`)**: field + `employee.antiquity_date`.

**Inicio de contrato (`contract_start_date`)**: field + `employee.started_working_at` + `employee.start_date_last_contract` + `position.contract_start_date`.

## Caveat

Si el sueldo queda debajo del mínimo, dejar registrado en el ticket que el cliente confirma el monto. El cambio por consola **no** dispara el flujo normal de cambio salarial: no recalcula SDI/SBC ni genera movimiento de modificación salarial en kardex/IDSE. Si el empleado cotiza al IMSS, avisar al cliente que valide el SBC por su lado.
