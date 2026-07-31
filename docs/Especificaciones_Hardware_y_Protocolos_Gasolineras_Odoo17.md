# Especificaciones Técnicas de Hardware, Protocolos y Control de Pistas para Gasolineras con Odoo 17

---

## 🔌 1. Hardware Necesario en la Estación de Servicio

Para que una estación de servicio (gasolinera atendida o desatendida) funcione integrada con Odoo 17, se requiere el siguiente equipamiento de hardware en pista y caja:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         SURTIDORES Y TANQUES (PISTA)                        │
│   - Surtidores: Gilbarco, Tokheim, Wayne, Cetil                             │
│   - Sondaje de Tanques (ATG): Veeder-Root TLS-350 / TLS-450                 │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ Cableado Loop 20mA / RS-485 / RS-232
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                CONTROLADOR DE PISTA (FORECOURT CONTROLLER)                  │
│   - Controlador Central: DOMS PSS 5000 / Postec / Alvesa                    │
│   - Módulos de Interfaz de Bucle (Hardware Interface Cards)                 │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ Red Local Ethernet (TCP/IP / IFSF)
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                 PASARELA EDGE LOCAL / ODOO IOT BOX                          │
│   - Hardware: Mini PC Industrial / Fanless (Intel NUC / Raspberry Pi 4)     │
│   - SO: Linux Ubuntu Server / Debian                                        │
│   - Agente Daemon Python (Servicio de Control de Pista y Offline Buffer)    │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ HTTPS / WebSockets / JSON-RPC
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        CAJA Y TPV (ODOO 17 POS)                             │
│   - Pantalla Táctil TPV / Impresora Térmica de Tickets (ESC/POS)           │
│   - Terminal de Pago Tarjeta (PinPad EMV / Contactless)                     │
│   - Odoo 17 ERP (Servidor Cloud o Servidor Local)                           │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.1 Especificaciones de Componentes

| Componente | Función Principal | Modelos Recomendados / Estándar |
| :--- | :--- | :--- |
| **Forecourt Controller (FCC)** | Agrupar y traducir los protocolos propietarios de cada surtidor a una interfaz única. | **DOMS PSS 5000** (Estándar mundial), Postec, Alvesa, Concentrador Cetil. |
| **Servidor Edge / IoT Box** | Ejecutar el Agente Daemon que comunica el FCC con Odoo vía WebSockets en tiempo real. | Mini PC Industrial Fanless (Intel Celeron/Core i3, 8GB RAM, SSD 128GB, Doble puerto Ethernet). |
| **Sondas de Tanques (ATG)** | Medir volumen de combustible, agua libre y temperatura dentro de los tanques. | **Veeder-Root TLS-350 / TLS-450**, OPW SiteSentinel, Colibri. |
| **Impresora de Tickets** | Impresión rápida de comprobantes simplificados y facturas de pista. | Epson TM-T20III / TM-T88VI (Ethernet/USB con protocolo ESC/POS). |
| **PinPad / Pago Pista** | Cobro con tarjeta bancaria, Google Pay, Apple Pay y tarjetas de flota. | Ingenico Lane/3000, Verifone P400, o Terminal de Pago de Pista (OPT). |

---

## 📡 2. Protocolos de Comunicación Industriales

Las comunicaciones entre surtidores, controlador de pista y Odoo utilizan 3 niveles de protocolos:

### 2.1 Nivel 1: Surtidor ↔ Controlador de Pista (Físico/Serie)
- **Gilbarco Two-Wire Current Loop (20mA):** Transmisión por bucle de corriente serie para surtidores Gilbarco.
- **Tokheim Ka-Loop / Dunclare:** Bucle de corriente específico de cabezales Tokheim Quantium.
- **Wayne DART Protocol:** Comunicación serie RS-485 para surtidores Wayne Dresser.
- **Modbus RTU / RS-485:** Protocolo industrial estándar para surtidores electrónicos y sondas.

### 2.2 Nivel 2: Controlador de Pista ↔ Agente Edge (Red Local)
- **IFSF (International Forecourt Standards Forum) TCP/IP:**
  - Estándar internacional sobre socket TCP (puerto 4000/4001 o configurable).
  - Define la máquina de estados estandarizada para surtidores, precio por litro y totalizadores.
- **DOMS TCP Protocol (PSS Direct Protocol):**
  - Protocolo socket binario de baja latencia del fabricante DOMS.
  - Permite control total manguera por manguera, bloqueos de seguridad y lectura continua de lecturas del contador electrónico (totalizadores inalterables).

### 2.3 Nivel 3: Agente Edge ↔ Odoo 17 ERP (Capa Aplicación)
- **WebSockets (WSS):** Conexión dúplex permanente. Odoo envía órdenes de activación al instante y el Agente Edge notifica mangueras descolgadas o finalizaciones de suministro sin retardos (latencia < 50ms).
- **JSON-RPC / REST API (HTTPS):** Envío de cierres de turno, totalizadores diarios, eventos de alarma y lecturas de tanques de combustible.

---

## ⚙️ 3. Mecanismo de Control de Pista (Abrir / Cerrar / Autorizar)

El control de los surtidores se basa en una **máquina de estados** administrada por Odoo y ejecutada por el Agente Edge.

### 3.1 Comandos de Control Ejecutados por Odoo

#### 1. Autorización de Surtidor (AUTH / PREPAY)
Habilita el suministro en un surtidor específico.
- **Parámetros:** `surtidor_id`, `manguera_id`, `limite_importe` (ej. 50.00€) o `limite_litros` (ej. 40.00 L), `modo` (`POSTPAY` / `PREPAY`).
- **Respuesta FCC:** Estado cambia a `AUTHORIZED`. El surtidor permite descolgar la manguera y empezar a bombear.

#### 2. Bloqueo / Cierre de Surtidor (LOCK / STOP)
Impide el uso del surtidor (ej. fuera de servicio, mantenimiento o cierre nocturno).
- **Parámetros:** `surtidor_id`, `motivo`.
- **Respuesta FCC:** Estado cambia a `LOCKED / OUT_OF_SERVICE`. Si la manguera se descuelga, la bomba no arranca.

#### 3. Parada de Emergencia (EMERGENCY HALT)
Corta inmediatamente el suministro en un surtidor o en toda la pista.
- **Parámetros:** `surtidor_id` (o `ALL` para corte general de pista).
- **Respuesta FCC:** Detención inmediata de las bombas de presión y cierre de electroválvulas.

#### 4. Liberación / Desbloqueo tras Cobro (RELEASE / UNLOCK)
Tras cobrar el ticket en el TPV de Odoo, el surtidor vuelve al estado `IDLE` (Disponible).
- **Parámetros:** `surtidor_id`, `transaction_id`.

---

### 3.2 Diagrama de Estados del Surtidor en Odoo POS

```
 ┌──────────────┐      Manguera Descolgada       ┌──────────────┐
 │     IDLE     ├───────────────────────────────►│ LIFTED / REQ │
 │ (Disponible) │                                │  (Solicitud) │
 └──────▲───────┘                                └──────┬───────┘
        │                                               │
        │ Pago Cobrado                                  │ Autorización OK
        │ (Release)                                     │ (Auth Command)
 ┌──────┴───────┐                                ┌──────▼───────┐
 │   STOPPED /  │       Suministro Finalizado    │   PUMPING /  │
 │ WAITING PAY  │◄───────────────────────────────┤   DENSING    │
 │ (Pendiente)  │                                │ (Surtiendo)  │
 └──────────────┘                                └──────────────┘
```

---

## 🛡️ 4. Tolerancia a Fallos y Modo Offline (Servicio Continuo)

Una gasolinera **nunca puede dejar de vender** si se pierde la conexión a internet con la nube.

1. **Buffer Local de Transacciones (Agente Edge):**
   - Si la conexión HTTPS con Odoo Cloud cae, el Agente Edge guarda todas las ventas servidas en una base de datos local SQLite/PostgreSQL aislada.
2. **Operación Local Continuada:**
   - El TPV de Odoo local (o la consola de caja) sigue permitiendo cobrar mangueras servidas conectando directamente con la IP local del Agente Edge.
3. **Sincronización Automática:**
   - En cuanto se restablece el acceso a internet, el Agente Edge sube el histórico de transacciones pendientes a Odoo ERP y ajusta las facturas y el inventario de tanques sin duplicados.
