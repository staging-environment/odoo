# Hoja de Ruta: Control Directo de Pista desde Odoo TPV (Bypass VirtusTPV)

**Estado:** Planificado / En contexto (No ejecutar hasta autorización expresa).  
**Estación de referencia:** E.S. Repsol - Trieste (`CODIGO_ESTACION = 5`, `CONFIG_ID = 7`).  
**Fecha de registro:** Octubre 2026.

---

## 1. Objetivo General
Evolucionar la integración actual de pista desde el **Modo Espejo/Pasivo** (solo lectura de estados y captura de ventas terminadas) a un **Control Bidireccional Total** operado exclusivamente desde la interfaz de **Odoo 17 POS (`pos_gas_station`)**, permitiendo prescindir completamente del software VirtusTPV de Aseproda.

---

## 2. Diagnóstico del Estado Actual (Fase 1 - Superada)
- **Monitoreo activo:** El agente local `agente_pista_odoo_bridge.py` monitoriza en tiempo real el concentrador `SDES.exe` mediante `dw.log` y la réplica de base de datos MySQL local (`virtusgesnet`).
- **Sincronización:** Refleja en Odoo los modos de trabajo (Atendido 🔓, Postpago 🔓, Prepago 🔒).
- **Traspaso de ventas:** Al colgar la manguera, la venta finalizada se presenta en el TPV con el botón naranja `⬆ PASAR A TICKET`.
- **Dependencia actual:** Las órdenes de pista (desbloqueo, prefijado de prepago, cambio de precios en surtidor) aún las ejecuta el operador a través de VirtusTPV.

---

## 3. Arquitectura y Vías Técnicas para la Fase 2

### Opción A: Integración por Software sobre Concentrador SDES (Recomendada inicial)
Aprovechar el concentrador `C:\SDES\SDES.exe` que ya tiene el control físico de los puertos serie (`COM3`/`COM4`):
1. **Mecanismo:** Descubrir y emular el protocolo de comunicación cliente-servidor entre VirtusTPV y SDES (revisión de sockets locales TCP, archivos IPC o interfaz de librería `clienteInt`/`servidor`).
2. **Capacidades a implementar:**
   - Enviar tramas de autorización de prepago con importe/litros prefijados.
   - Enviar tramas de desbloqueo/autorización libre para postpago.
   - Enviar órdenes de bloqueo o parada de emergencia por calle.
   - Enviar actualizaciones de precio a surtidor.
3. **Ventajas:** Cero inversión en hardware adicional; despliegue inmediato sobre el PC existente.

### Opción B: Sustitución por Controlador Industrial Homologado (DOMS PSS 5000 / Box Edge)
Independencia completa del software de Aseproda mediante hardware de control de pista industrial:
1. **Mecanismo:** Conectar los bucles de corriente (20mA Tokheim/Gilbarco) o RS-485 al controlador DOMS PSS 5000.
2. **Protocolo:** Odoo (a través de un Agente Edge local en LAN) habla por socket TCP directo (puerto 7000 / protocolo PSS Direct o puerto 4000 / estándar IFSF).
3. **Ventajas:** Estándar internacional petrolífero, máxima robustez, desacoplamiento absoluto de cualquier proveedor de software local.

---

## 4. Requisitos Funcionales en Odoo POS (`pos_gas_station`)

Cuando se active el desarrollo de esta fase, Odoo deberá incorporar:

1. **Panel de Comando de Pista:**
   - Modal táctil para prefijar prepago: selección de combustible, introducción de importe en euros o litros, y botón de autorización de manguera.
   - Botón de autorización inmediata para suministros postpago asistidos.
   - Botón de bloqueo individual y parada de emergencia general de pista.
2. **Canal de Envío Odoo ➔ Agente Local:**
   - Mensajería reactiva (Long-polling / WebSocket / Bus de Odoo) donde el agente local escuche las órdenes emitidas por el cajero en Odoo Cloud y las traslade instantáneamente al concentrador de pista.
3. **Gestión de Precios Centralizada:**
   - Sincronización del catálogo de precios de combustibles de Odoo hacia los surtidores de pista y el monolito exterior de precios.
4. **Cierre de Turno con Totalizadores Electrónicos:**
   - Lectura de los contadores inalterables de cada manguera al cierre de sesión para cotejo automático de descuadres contra el arqueo de caja.

---

## 5. Próximos Pasos Técnicos (Cuando se decida iniciar)
1. Inspeccionar `C:\SDES\` en el equipo de Trieste para documentar la configuración de puertos y sockets (`sdes.ini`, logs de cliente/servidor).
2. Trazar las tramas enviadas por VirtusTPV al realizar un prefijado de 10 € en una calle de prueba.
3. Desarrollar el conector de envío de comandos en el agente Python local y probar el corte físico en surtidor.
