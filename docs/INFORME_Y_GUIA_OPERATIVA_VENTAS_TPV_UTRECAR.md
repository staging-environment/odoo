# INFORME TÉCNICO Y GUÍA OPERATIVA: MÓDULO DE VENTAS Y TPV UTRECAR

**Fecha:** 07 de Octubre de 2026  
**Sistema:** Odoo 17 Enterprise / Community - Adaptación Estaciones de Servicio UTRECAR  
**Módulos Afectados:** `pos_gas_station`, `utrecar_invoice_vehicle`  
**Entornos:** Local (DDEV WSL2) y Producción (`https://odoo.utrecar.com` - VPS `164.68.101.69`)  
**Ubicación:** `docs/INFORME_Y_GUIA_OPERATIVA_VENTAS_TPV_UTRECAR.md`

---

## 1. RESUMEN DE CAMBIOS REALIZADOS

Se han implementado mejoras integrales en la interfaz táctil del Punto de Venta (TPV) y en el flujo de facturación y pista:

### A. Control de Modo de Pista (Atendido vs Prepago)
* **Conmutador en Cabecera de Surtidores:** Se ha incorporado un selector táctil dinámico en la parte superior del panel de surtidores (junto al distintivo Aseproda):
  * **`🟢 PISTA: ATENDIDO (POSTPAGO)`**: Todos los surtidores libres pasan a estado abierto en verde (`🔓 LIBRE / ATENDIDO`). Permite el repostaje libre sin prepago previo.
  * **`🔴 PISTA: PREPAGO (BLOQUEO)`**: Todos los surtidores libres pasan a estado de bloqueo en rojo (`🔒 PREPAGO`). Requiere autorización o prepago previo desde caja.
* **Persistencia:** La configuración seleccionada se almacena localmente y se mantiene entre reinicios de pantalla y cambios de turno.

### B. Introducción de Cantidades con Decimales
* **Edición Directa en Pantalla LCD:** Al pulsar sobre el visor del importe (`0,00 €` o `0.00 L`), se abre un cuadro de introducción rápida para teclear importes exactos con decimales (ej. `15.50` € o `32,80` L).
* **Botón Rápido `🔢 Dec.`:** Acceso directo junto a los modos de dinero y litros.
* **Soporte de Coma y Punto:** Acepta tanto coma `,` como punto `.` para evitar errores de digitación en teclado táctil o físico.

### C. Rediseño Ergonómico de la Pantalla de Cobro (`PaymentScreen`)
* **Botón de Salida Inmediata:** Se añadió en la cabecera un botón de alta visibilidad: `⬅ VOLVER A PISTA / CANCELAR`, que permite al operador volver a la venta sin bloquear el TPV ni perder líneas de venta.
* **Botonera Táctica de Estación:**
  * **🖨 TICKET (Imprimir):** Valida la venta, registra el cobro e imprime el ticket de caja.
  * **📄 FACTURA (NIF/CIF):** Abre el asistente de cliente si no está seleccionado, exige CIF/NIF y emite la factura con matrícula y envío automático por email.
  * **💾 GUARDAR (Sin Ticket):** Cobro ágil sin consumo de papel para clientes que no desean recibo.
* **Corrección de Maquetación:** Se eliminó el botón duplicado de Odoo que solapaba la interfaz, garantizando columnas proporcionadas y limpias.

### D. Tienda y Búsqueda Multicriterio
* **Buscador Inteligente:** Búsqueda en tiempo real por coincidencia parcial/total de nombre, código interno (`default_code`) y código de barras (`barcode`).
* **Selector de Páginas 1 a 4:** Desplegable interactivo para alternar entre cuadrículas de productos de alta rotación (20 artículos por página).
* **Catálogo Completo 📦 vs Parrilla 🛒:** Botón de caja para abrir el modal con categorías y botón de carrito para conmutar la vista.

---

## 2. GUÍA OPERATIVA PASO A PASO PARA EL CAJERO

### 2.1. ¿Cómo cambiar el modo de la pista (Atendido / Prepago)?
1. En la pantalla principal, observe el botón situado encima del mapa de surtidores:
   * Si muestra **`🔴 PISTA: PREPAGO (BLOQUEO)`**, pulse sobre él.
   * Cambiará automáticamente a **`🟢 PISTA: ATENDIDO (POSTPAGO)`** y los surtidores se pondrán en verde listos para suministrar.
2. Para la noche o periodos de autoservicio prepago, vuelva a pulsar para bloquear la pista en modo **Prepago**.

---

### 2.2. ¿Cómo cobrar un repostaje?

#### Caso 1: Suministro Atendido / Postpago (Echar primero y cobrar después)
1. El cliente o expendedor realiza el repostaje en pista.
2. La casilla de la **Calle** correspondiente (ej. *Calle 1*) mostrará el importe en euros y los litros.
3. El cajero hace **clic sobre la casilla de esa Calle** (o el botón `⬆ PASAR A TICKET`).
4. El combustible sube automáticamente a la tabla del ticket a la izquierda.
5. Pulse el botón azul inferior derecho **`COBRAR [Importe] €`**.
6. Seleccione la forma de pago (**Efectivo** o **Tarjeta**) y pulse **`🖨 TICKET`** o **`📄 FACTURA`**.

#### Caso 2: Suministro Prepago (Cobrar antes de suministrar)
1. Haga clic sobre la **Calle** deseada (ej. *Calle 3*).
2. Seleccione el combustible (**GA** para Gasóleo o **95** para Gasolina).
3. Seleccione el importe:
   * Pulsando los billetes rápidos (`10€`, `20€`, `50€`...).
   * O pulsando sobre el visor LCD `0,00 €` / botón **`🔢 Dec.`** para teclear un importe exacto (ej. `18.50`).
4. Pulse el botón verde **`AUTORIZAR CALLE 3`**.
5. El importe se carga en el ticket y el surtidor queda abierto para suministrar exactamente esa cantidad.
6. Pulse **`COBRAR`** para registrar el pago del cliente.

---

### 2.3. ¿Cómo emitir Ticket, Factura o Guardar a Crédito?

Al pulsar **`COBRAR`**, en la pantalla de pago tiene tres vías:

* **Para emitir un Ticket normal:**
  * Seleccione el método de pago (Efectivo / Tarjeta).
  * Pulse **`🖨 TICKET (Imprimir)`**.
* **Para emitir una Factura con NIF/CIF:**
  * Pulse **`📄 FACTURA (NIF/CIF)`**.
  * Si no hay cliente seleccionado, se abrirá la ventana para buscar por CIF/Nombre o crear uno nuevo.
  * Si el cliente tiene correo registrado, Odoo le enviará la factura en PDF de forma automática.
* **Para guardar a Crédito / Cuenta de Cliente (Facturación mensual):**
  * Asigne el cliente desde el botón superior **`👤 CLIENTE`**.
  * En la pantalla de cobro, elija como medio de pago **`Cuenta Cliente / Crédito`**.
  * Pulse **`GUARDAR`**. La venta queda guardada en el albarán del cliente para la factura agrupada de fin de mes.
* **Para dejar un ticket en espera:**
  * En la barra superior, pulse sobre la pestaña de tickets/pedidos para abrir un nuevo ticket en blanco y atender a otro cliente mientras el anterior completa su compra.

---

### 2.4. ¿Cómo volver a la pantalla de pista si se entra por error a Cobro?
* En la parte superior izquierda de la pantalla de pago, pulse el botón rojo **`⬅ VOLVER A PISTA / CANCELAR`**.
* Regresará inmediatamente a la vista de surtidores y ticket sin perder los datos introducidos.

---

## 3. REGISTRO DE DESPLIEGUE EN PRODUCCIÓN

| Componente | Versión | Estado en Producción |
| :--- | :--- | :--- |
| `pos_gas_station` (XML/JS/CSS) | v17.0.2.0 | **Desplegado y Verificado** en `https://odoo.utrecar.com` |
| `utrecar_invoice_vehicle` | v17.0.1.0 | **Desplegado y Verificado** (SMTP IONOS activo) |
| Repositorio Git | Rama `main` | **Sincronizado** (`staging-environment/odoo`) |

---
*Documento generado y archivado en el repositorio oficial de UTRECAR.*
