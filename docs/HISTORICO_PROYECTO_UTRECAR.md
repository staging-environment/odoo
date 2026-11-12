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
| **13/10/2026** | Servidor Pista (`10.8.0.18`) | Configuración de SSH, API nativa `ClienteSDESNet.dll` (TCP 8777) y autostart silencioso 24/7 en Sesión 0 | Pista operada por Odoo POS como MÁSTER; prueba física exitosa en Calle 8 |
| **15/10/2026** | Prod & Pista | Sincronización bidireccional hardware de cambio de modo global ("PISTA: PREFIJADO / LLENO") y candados individuales por calle | Desplegado en Cloud y en PC Repsol Trieste; persistencia de filestore con volumen `odoo-data` |
| **15/10/2026** | Prod & Pista | Corrección de ciclo de cobro y liberación de pista: corte de prefijado por hardware vía SDES Prefijar() y liberación instantánea tras cobrar en TPV | Verificado físicamente con corte exacto en 1.00 € y reseteo a 0.00 € / PREPAGO tras cobro |
| **15/10/2026** | Prod & Pista | Suministro en tiempo real vía SDES ObtenerEstado() (litros/importe en vivo) y liberación de pista al pulsar 'Cancelar' o 'BORRAR' en TPV | Desplegado en Cloud y en PC Repsol Trieste |
| **15/10/2026** | Pista (`10.8.0.18`) | Desacoplamiento total de librerías Aseproda: desarrollo de driver socket TCP nativo en Python puro (`PurePythonSdesClient`), eliminando `ClienteSDESNet.dll`, `clr`, `.NET` y MySQL | 100% operativo y probado en vivo (Consumo RAM reducido de 68MB a 26MB) |
| **15/10/2026** | Prod & TPV | Corrección visual y funcional de autorización a Lleno (Postpago): eliminación de parpadeo de texto en tarjeta de surtidor y habilitación de bloqueo por hardware inmediato mediante botones 'BORRAR' y 'Cancelar' sin necesidad de ticket previo | Desplegado y verificado en Cloud y TPV |
| **15/10/2026** | Prod & TPV | Corrección de apertura de modal de surtidor: eliminación del interceptor de clic en el panel inferior del candado para permitir que cualquier clic en la tarjeta abra limpiamente la ventana flotante de autorización | Desplegado y verificado en Cloud |
| **15/10/2026** | Prod & Pista | Suministro en tiempo real y protocolo bidireccional SDES: decodificación nativa de MSG_CAMBIO_INFO (14) con litros/importe en vivo, ACK automático de MSG_NUEVA_OP (15), latido continuo MSG_PULSO (18) y liberación automática de hardware tras validar cobro en TPV | Desplegado en Cloud y en PC Repsol Trieste |
| **10/11/2026** | Servidor Cloud (`utrecar-dev`) | Corrección de mapeo de IPs WireGuard VPN en `status.utrecar.com` (`ddev-status-utrecar-db` y `StationSeeder.php`): Ronda Norte actualizada a `10.8.0.6` | Cesaron falsas alarmas de desconexión de Ronda Norte en Telegram |
| **10/11/2026** | TPV & Cloud | Optimización de Historial de Turno: tabla compacta a 1 línea por pedido (1040px sin scroll horizontal), filas anuladas en rojo pastel y corrección de z-index del modal de anulación | Desplegado en Cloud y verificado en TPV |
| **10/11/2026** | TPV & Cloud & Pista | Gestión integral de sobrantes de prepago incompleto (Puntos 9 y 10): monedita con badge, surtidor en amarillo permanente incluso con pista cerrada, modal con importe negativo y 4 botones de acción (Ticket, Albarán, Factura, Guardar sin ticket) | Desplegado en Cloud y sincronizado con agente de pista en Repsol (`10.8.0.18`) |
| **10/11/2026** | TPV & Cloud | Composición de ticket de devolución con 1 línea de combustible en negativo (`-diffLts` / `-diffAmt`) y soporte de cobro negativo en `PaymentScreen` | Desplegado y verificado en Cloud |
| **12/11/2026** | ERP Backend | Reorganización de menú principal superior: "Usuarios" -> "Expendedores" y "Administración", con resalte visual y punto identificador de sección activa | Desplegado y verificado en Cloud |
| **12/11/2026** | ERP Backend | Compactación y reducción de márgenes y filas en la vista detalle de empresas (`res.company`) | Desplegado y verificado en Cloud |
| **12/11/2026** | TPV & Cloud | Rediseño de modal de clientes en TPV: cabecera en 2 niveles, buscador ágil con reset, botón "Editar" por fila y modal flotante de alta/edición de clientes | Desplegado y verificado en Cloud |
| **12/11/2026** | TPV & Cloud | Selector dinámico de matrículas en TPV: desplegable estilizado con matrículas previas del cliente o input directo con autoguardado en su ficha | Desplegado y verificado en Cloud |
| **12/11/2026** | ERP & TPV | Segregación estricta de clientes por Empresa (`res.company`): aislamiento de clientes de A.R. Trieste (Repsol) y UTRECAR S.L. | Desplegado y verificado en Cloud |
| **12/11/2026** | TPV & Seguridad | Restricción estricta de tipo de facturación (Crédito/Mensual/Contado): modo solo lectura con candado en TPV y gestión exclusiva para administradores en backend | Desplegado y verificado en Cloud |
| **12/11/2026** | TPV & Pista Repsol (`10.8.0.18`) | Diagnóstico y solución de congelamiento en 3 puntos (`...`): corrección de sintaxis en compilación Owl de `UtrecarMainScreen` por condicional inline en XML | Resuelto y verificado al 100% en vivo |

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
