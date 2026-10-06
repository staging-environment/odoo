# Guía de Integración Aseproda ➔ Odoo Cloud (Clientes, Facturación e Inventario)

Este documento describe la arquitectura técnica, mapeo de datos, estructura de inventario y procedimientos de operación y limpieza para los datos de Aseproda en Odoo Cloud (`https://odoo.utrecar.com`).

---

## 1. Fuentes de Datos (Aseproda en Producción)

- **Servidor:** `164.68.101.69`
- **Ubicación en el servidor:** `/home/developer/Projects/utrecardbs`
- **Motor:** MySQL 5.5 / MariaDB (puerto expuesto: `33061`)
- **Bases de datos:**
  - **`virtusgesnet`**:
    - `clientes`: **1.811 registros** (CIF/NIF, razón social, dirección fiscal, teléfono, email, IBAN/BIC, forma de pago habitual).
    - `proveedores`: **483 registros** (suministradores de carburante mayorista y artículos de tienda).
    - `facturasyticketsdeventa`: **64.993 facturas oficiales** a clientes (`EsTicket = 0` y `CodigoDeCliente > 0`). En 2026: **8.770 facturas** (~1,50 M€).
    - `detalledefacturasyticketsdeventa`: Líneas de factura (litros, precio unitario, % IVA, código de producto).
    - `facturasdecompra`: **10.585 facturas de compra**. En 2026: **1.580 facturas** (~21,35 M€).
    - `detalledefacturasdecompra`: 37.110 líneas de coste de compra.
    - `almacenesytanques`: 14 almacenes y tanques distribuidos en las 4 estaciones de servicio.
    - `detallederegularizacionesdealmacen`: Histórico de recuentos físicos y aforos de combustible.
  - **`administracioncorporativa`**: Configuración de perfiles, usuarios e informes del software Aseproda.
  - **`sii`**: Registro de envíos a la Agencia Tributaria (tipos F1, F2).

---

## 2. Arquitectura de Mapeo en Odoo Cloud

Todos los datos se han estructurado siguiendo el estándar nativo de Odoo 17:

### A. Clientes y Contactos (`res.partner`)
- Clientes de Aseproda: `customer_rank = 1`, `ref = ASEPRODA-{Codigo}`.
- Proveedores de Aseproda: `supplier_rank = 1`, `ref = PROV-{Codigo}`.
- Normalización: CIF/NIF con prefijo `ES...`, clasificación `is_company` (sociedades) o persona física, direcciones con mapeo a provincias de España (`res.country.state`) y cuentas bancarias en `res.partner.bank`.

### B. Facturación de Ventas (`account.move` - `out_invoice`)
- Diario: `Customer Invoices` (ID 1, código `INV`).
- Impuestos: IVA 21% (ID 4), IVA 10% (ID 5), IVA 4% (ID 6), IVA 0% (ID 3).
- Identificador Aseproda: Guardado en `ref` y `payment_reference` (`{Serie}/{Numero}`, ej: `FRUTR/2026006483`).
- Estado: Publicado (`posted`).

### C. Facturación de Compras (`account.move` - `in_invoice`)
- Diario: `Vendor Bills` (ID 2, código `BILL`).
- Impuestos: IVA Soportado 21% (ID 7), IVA 10% (ID 8), IVA 4% (ID 9), IVA 0% (ID 10).
- Identificador: `ref = {Serie}/{Numero}`, `payment_reference = SuFactura`.

### D. Inventariado y Almacenes (`stock.warehouse`, `stock.location`, `stock.quant`)
Almacenes físicos configurados:
1. **`E.S. Utrera` (`UTR`)**:
   - `TK_UTR_GAS_A`: Tanque Gasóleo A (40.914 L)
   - `TK_UTR_SP95`: Tanque Sin Plomo 95 (7.320 L)
   - `TIENDA_UTR`: Tienda Utrera
2. **`E.S. Atalaya` (`ATE`)**:
   - `TK_ATE_GAS_A_1` / `TK_ATE_GAS_A_2`: Tanques Gasóleo A (41.500 L)
   - `TK_ATE_SP95_1` / `TK_ATE_SP95_2`: Tanques Sin Plomo 95 (29.000 L)
   - `TIENDA_ATE`: Tienda Atalaya
3. **`E.S. Rodalabota` (`RO`)**:
   - `TK_RO_GAS_A`: Tanque Gasóleo A (24.435 L)
   - `TK_RO_SP95`: Tanque Sin Plomo 95 (6.704 L)
   - `TIENDA_RO`: Tienda Rodalabota
4. **`E.S. Ronda Norte` (`RN`)**:
   - `TK_RN_GAS_A`: Tanque Gasóleo A (16.260 L)
   - `TK_RN_SP95`: Tanque Sin Plomo 95 (7.415 L)
   - `TIENDA_RN`: Tienda Ronda Norte

Productos carburante y de tienda marcados como almacenables (`type = 'product'`) con existencias actualizadas en `stock.quant`.

---

## 3. Scripts de Sincronización y Mantenimiento

Ubicación en el repositorio: `scripts/`  
Ubicación en el servidor de producción: `/opt/utrecar/`

### A. Sincronización de Clientes y Facturas
```bash
# Sincronizar clientes
python3 scripts/migrate_aseproda_to_odoo.py --clients

# Sincronizar facturas de cliente (2026)
python3 scripts/migrate_aseproda_to_odoo.py --invoices --year 2026

# Sincronizar clientes y facturación
python3 scripts/migrate_aseproda_to_odoo.py --all
```

### B. Procedimiento de Borrado / Purga de Datos de Prueba
Dado que estos datos son para evaluación y pruebas en Odoo:
```bash
# Simulación previa (muestra recuentos de registros a eliminar)
python3 scripts/cleanup_aseproda_test_data.py --dry-run

# Confirmación y borrado total
python3 scripts/cleanup_aseproda_test_data.py --confirm
```

El script elimina de forma segura las facturas de venta y compra, restablece las existencias de inventario a cero y elimina los proveedores y clientes creados, restaurando la base de datos de Odoo a su estado limpio original.
