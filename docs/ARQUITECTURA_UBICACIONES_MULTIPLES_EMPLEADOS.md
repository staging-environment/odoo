# Especificación de Arquitectura: Ubicaciones de Trabajo Múltiples por Empleado (Admin Platform & Odoo)

## 📌 Contexto y Objetivo
En el sistema de gestión de estaciones de servicio UTRECAR, los empleados son dados de alta y gestionados principalmente desde la plataforma central **`admin-platform`** (Laravel + MariaDB).

Actualmente, cada empleado cuenta con un único campo `gasolinera_codigo` en la tabla `empleados`. Sin embargo, en la operativa real:
1. Muchos expendedores y encargados trabajan en **más de una estación de servicio** (por ejemplo, cubriendo turnos rotativos entre *E.S. Vistalegre* y *E.S. Ronda Norte* o *E.S. Repsol*).
2. En la pantalla táctil de apertura de turno de cada TPV (`/pos_gas_station/select_employee`), **únicamente deben aparecer los empleados asignados a esa ubicación de trabajo específica**.
3. Un empleado con múltiples ubicaciones debe poder abrir turno en cualquiera de las estaciones a las que esté asignado, quedando sus ventas, cobros y arqueos vinculados a su usuario y a esa sesión específica.

---

## 🗄️ 1. Esquema Técnico en `admin-platform` (MariaDB)

Para permitir que la ubicación de trabajo sea **múltiple**, se establecen las siguientes opciones de implementación en `admin-platform`:

### Opción A (Recomendada - Tabla Pivot Relacional N:M):
Crear la tabla `empleado_gasolinera` (o `empleado_estaciones`):
```sql
CREATE TABLE `empleado_gasolinera` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `empleado_id` BIGINT UNSIGNED NOT NULL,
  `gasolinera_codigo` INT NOT NULL,
  `created_at` TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_emp_gas` (`empleado_id`, `gasolinera_codigo`),
  CONSTRAINT `fk_emp_gas_empleado` FOREIGN KEY (`empleado_id`) REFERENCES `empleados` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

### Opción B (JSON / Lista de Códigos en `empleados`):
Si se prefiere mantener dentro de la misma tabla `empleados`:
- Columna `gasolinera_codigos` tipo `JSON` o `VARCHAR(255)` con lista de códigos:
  - Ejemplo JSON: `[1, 2, 5]`
  - Ejemplo String: `'1,2,5'`

---

## ⚙️ 2. Lógica de Filtrado en Odoo TPV (`pos_gas_station`)

En Odoo (`extra-addons/pos_gas_station/models/pos_config.py`), la lógica de consulta y filtrado está preparada para soportar tanto el código único como la asignación múltiple:

1. **Consulta MariaDB:**
   - Detecta si existe la tabla pivot `empleado_gasolinera` o columna de ubicaciones múltiples.
   - De lo contrario, evalúa `gasolinera_codigo` soportando formato entero, coma flotante o cadenas separadas por coma (`'1,2,5'`).

2. **Apertura de Turno en Pista (`/pos_gas_station/select_employee`):**
   - El TPV de pista detecta su estación según la IP de la VPN WireGuard (ej: `10.8.0.18` -> *E.S. Repsol*, código 5).
   - **Filtro Estricto:** Se presentan exclusivamente las tarjetas de los empleados que tengan entre sus ubicaciones asignadas el código de esa estación.
   - Si un empleado tiene asignadas las estaciones 1 y 5, aparecerá tanto en la pantalla de *Vistalegre* como en la de *Repsol*.

3. **Sincronización con `res.users`:**
   - En el modelo `res.users`, el campo `pos_config_ids` (relación `Many2many` con `pos.config`) almacena **todas** las estaciones autorizadas del empleado.
   - Cada estación correspondiente añade al usuario en su campo `allowed_user_ids`.
   - La regla de registro `ir.rule` permite al empleado acceder y vender en cualquiera de sus terminales asignadas.

---

## 📋 3. Matriz de Gasolineras y Códigos Estándar

| ID Odoo | Nombre de Estación | IP VPN WireGuard | Código en Admin Platform |
|:---:|:---|:---|:---:|
| **7** | E.S. Repsol (Trieste / Calonge) | `10.8.0.18` | **5** |
| **5** | E.S. Ronda Norte | `10.8.0.6, 10.8.0.7` | **2** |
| **3** | E.S. Vistalegre (Utrera) | `10.8.0.11, 10.8.0.12` | **1** |
| **2** | E.S. Rodalabota (El Cuervo) | `10.8.0.9, 10.8.0.10` | **3** |
| **6** | E.S. Atenas (Écija) | `10.8.0.15` | **4** |
