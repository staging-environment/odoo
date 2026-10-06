# Reglas de Integración Odoo 17 - Aseproda

## 1. Arquitectura Nativa de Odoo
- Respetar siempre los modelos estándar sin alterar esquemas con hacks:
  - Clientes/Proveedores: `res.partner` (usar `customer_rank` y `supplier_rank`).
  - Facturación: `account.move` (`out_invoice` para clientes, `in_invoice` para compras a proveedores).
  - Almacenes y Tanques: `stock.warehouse` y `stock.location` interna.
  - Existencias: `stock.quant` (aplicar con `action_apply_inventory()`).
  - Los productos inventariables deben tener obligatoriamente `type = 'product'`.

## 2. Datos de Prueba y Política de Reversibilidad
- Identificar siempre los registros de prueba mediante prefijos en `ref`:
  - Clientes de prueba: `ref = 'ASEPRODA-{Codigo}'`
  - Proveedores de prueba: `ref = 'PROV-{Codigo}'`
  - Facturas: `ref = '{Serie}/{Numero}'`
- Toda carga de datos de prueba debe incluir su script de limpieza (`scripts/cleanup_*_test_data.py`) con soporte para:
  - `--dry-run`: simulación y conteo sin modificar datos.
  - `--confirm`: paso de facturas a borrador, reseteo de inventarios a 0 y borrado seguro de partners de prueba.

## 3. Conectividad XML-RPC con Odoo
- Al conectar mediante `xmlrpc.client.ServerProxy`, usar siempre `allow_none=True`:
  ```python
  common = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/common", allow_none=True)
  models = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/object", allow_none=True)
  ```
  De lo contrario, métodos que devuelven `None` (como `action_apply_inventory` o transiciones de estado) provocarán errores `TypeError: cannot marshal None`.

## 4. Consultas a Bases de Datos Aseproda (MySQL 5.5 / MariaDB 33061)
- Servidor de producción: `164.68.101.69:33061` en `/home/developer/Projects/utrecardbs`.
- En tablas con millones de registros (`detalledefacturasyticketsdeventa`, `movimientosdealmacen`):
  - Incluir siempre el prefijo del índice: `CodigoDeEmpresaPropia = 1`.
  - Preferir precarga en memoria en una sola consulta con `JOIN` sobre el periodo temporal en lugar de consultas individuales por documento en bucle.
