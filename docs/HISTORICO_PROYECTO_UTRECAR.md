# HISTÓRICO Y REGISTRO TÉCNICO DEL PROYECTO UTRECAR (ODOO 17 ERP & POS)

**Fecha de última actualización:** 07/10/2026  
**Entorno de Producción:** `https://odoo.utrecar.com` (VPS: `164.68.101.69`)  
**Entorno Local:** WSL2 Ubuntu / DDEV (`ddev-odoo-odoo`)  
**Repositorio Git:** `git@github.com:staging-environment/odoo.git` (Rama: `main`)

---

## 1. Resumen Ejecutivo
Este documento recopila de manera cronológica y técnica todas las personalizaciones, módulos, integraciones y configuraciones desplegadas en el sistema ERP Odoo 17 y Punto de Venta (TPV) para la red de Estaciones de Servicio **UTRECAR**.

---

## 2. Módulos Personalizados Desarrollados

### 2.1. Módulo `utrecar_invoice_vehicle`
*Ruta: `extra-addons/utrecar_invoice_vehicle`*

#### Objetivos y Funcionalidades:
1. **Datos de Vehículo y Conductor en Facturación:**
   - Campos en Facturas de Cliente (`account.move`):
     - `vehicle_plate`: Matrícula del vehículo (texto en mayúsculas / normalizado).
     - `vehicle_mileage`: Kilometraje en el momento del repostaje/servicio.
     - `vehicle_driver`: Conductor (campo de texto libre, sin requerir crear un contacto formal).
     - `vehicle_id`: Enlace con el registro histórico de vehículos del cliente.
     - `invoice_delivery_method`: Método de entrega (`email` por defecto, o `paper` si el cliente solicita factura física en papel).
     - `invoice_partner_email`: Correo destinatario (relleno automáticamente con el correo del cliente o modificable puntualmente).
   - **Registro y Memoria de Matrículas por Cliente (`res.partner.vehicle`):**
     - Al validar una factura con matrícula, el sistema auto-registra la matrícula en la ficha del cliente si aún no existía, manteniendo el historial de su flota.

2. **Envío Automático de Facturas por Correo Electrónico:**
   - Método `_handle_auto_invoice_dispatch`: Al publicar/validar una factura (`action_post`), si `invoice_delivery_method == 'email'` y existe correo válido, el sistema genera automáticamente el PDF de la factura oficial y lo envía mediante el servidor SMTP.
   - **Notificación en Tiempo Real:** Emisión de alerta/toast en la interfaz de Odoo mediante `bus.bus._sendone` confirmando el envío exitoso (`📧 Factura enviada por email a ...`).
   - Configuración SMTP en Producción: Integración con IONOS (`smtp.ionos.es:465`, SSL, usuario `informatica@utrecar.com`). Pruebas en vivo verificadas con éxito.

3. **Políticas Comerciales y Gestión de Crédito Centralizada:**
   - Se configuraron los parámetros comerciales en `res.partner`:
     - `customer_payment_mode`: Crédito (`credit`) vs Contado (`cash`).
     - `invoice_periodicity`: Facturación mensual (`monthly`), diaria (`daily`), quincenal (`biweekly`) o por operación (`single`).
     - `invoice_closing_day`: Día de corte/cierre de facturación.
     - `credit_limit_amount` y `credit_blocked`: Control de riesgo y bloqueo de crédito.
   - **Regla de Negocio:** Estas condiciones se configuran y controlan exclusivamente desde el ERP de gestión / backoffice, quedando protegidas y no editables desde el TPV de pista.

4. **Diseño de Informe PDF de Factura:**
   - Herencia de `account.report_invoice_document` en `report/report_invoice.xml` para incluir cabecera estilizada con matrícula, conductor y kilometraje.

---

### 2.2. Módulo `pos_gas_station`
*Ruta: `extra-addons/pos_gas_station`*

#### Objetivos y Funcionalidades:
1. **Parrilla de Artículos de Tienda y Búsqueda Multicriterio:**
   - **Búsqueda Inteligente:** Búsqueda en tiempo real por nombre de producto (coincidencia total o parcial), código interno (`default_code` / referencia) y código de barras (`barcode`).
   - **Paginación Dinámica (1 a 4):** Selector interactivo desplegable (▼) para alternar entre páginas de artículos predefinidos de alta rotación (20 productos por página).
   - **Catálogo Completo vs Parrilla Rápida:**
     - Botón **Caja 📦**: Abre el catálogo completo con buscador y filtro por categorías.
     - Botón **Carrito 🛒**: Alterna entre la parrilla de tienda y la vista estándar de ticket.

2. **Rediseño Integral de la Pantalla de Cobro (`PaymentScreen`):**
   - **Navegación y Retorno a Pista:** Se implementó un botón prominente en color rojo (`⬅ VOLVER A PISTA / CANCELAR`) en la cabecera superior izquierda, permitiendo al cajero salir de la pantalla de pago en cualquier momento con un solo toque y sin perder el ticket.
   - **Eliminación de Solapamiento:** Se sustituyó el botón estándar morado `Validar` de Odoo que colapsaba la interfaz inferior.
   - **Botonera Táctica de Estación:**
     - 🖨 **TICKET (Imprimir):** Valida la venta emitiendo el ticket impreso.
     - 📄 **FACTURA (NIF/CIF):** Solicita/valida cliente con datos fiscales y emite factura con matrícula.
     - 💾 **GUARDAR (Sin Ticket):** Cobro ágil sin impresión para clientes que no desean recibo.
     - **VALIDAR COBRO:** Botón principal de validación general.
   - **Distribución de Columnas:** Alineación limpia de métodos de pago (Efectivo / Tarjeta), resumen de líneas, teclado numérico y desglose de importes (Total, Restante, Cambio).

---

## 3. Registro Cronológico de Pruebas y Despliegues

| Fecha | Entorno | Acción Realizada | Resultado |
| :--- | :--- | :--- | :--- |
| **07/10/2026** | Producción (`164.68.101.69`) | Configuración del servidor de correo saliente SMTP IONOS | Verificado / Conexión exitosa |
| **07/10/2026** | Producción (`164.68.101.69`) | Emisión y envío automático de factura de prueba con PDF adjunto a `jarodriguezbonilla@gmail.com` | Factura recibida correctamente con PDF y datos de vehículo |
| **07/10/2026** | Local & Prod | Implementación de política comercial y crédito en ficha de cliente (`res.partner`) | Bloqueo en TPV y control centralizado en ERP |
| **07/10/2026** | Local & Prod | Corrección de buscador multicriterio de tienda y selector desplegable de páginas 1-4 | Operativo en TPV |
| **07/10/2026** | Local & Prod | Rediseño de `PaymentScreenTop` y `PaymentScreenValidate` con botón de retorno y acciones de cobro | Desplegado y verificado en `https://odoo.utrecar.com` |

---

## 4. Guía de Mantenimiento y Actualización de Módulos

Para desplegar cambios futuros en producción:
```bash
# 1. En local: Guardar cambios y subir a GitHub
git add .
git commit -m "Descripción de los cambios"
git push origin main

# 2. En servidor de producción (164.68.101.69):
ssh developer@164.68.101.69
cd /home/developer/Projects/odoo
git pull origin main
docker exec ddev-odoo-odoo odoo -u pos_gas_station,utrecar_invoice_vehicle -d odoo -c /etc/odoo/odoo.conf --stop-after-init
docker restart ddev-odoo-odoo
```
