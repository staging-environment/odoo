# Conexión Remota y Control de Pista: E.S. Repsol (Trieste / SE-30 Calonge)

Este documento detalla la infraestructura completa, parámetros de acceso remoto SSH, control de hardware de pista en tiempo real mediante la API nativa de Aseproda, y la configuración de arranque automático invisible 24/7 para operar Odoo POS como MÁSTER de la gasolinera.

---

## 📌 Parámetros de Conexión Remota SSH

- **Red VPN:** WireGuard VPN interna (`Repsol` / `Admin`)
- **IP Remota del Servidor Windows de Pista:** `10.8.0.18` (IP Local alternativa: `192.168.8.9`)
- **IP del Equipo de Desarrollo (Antigravity):** `10.8.0.2`
- **Puerto SSH:** `22` (Servicio: `OpenSSH SSH Server` en Windows)
- **Usuario de Windows:** `usuario` (`desktop-qlqikag\usuario`)
- **Autenticación:** Clave pública RSA autorizada en `C:\ProgramData\ssh\administrators_authorized_keys`
- **Comando de Conexión Directa:**
  ```bash
  ssh -o StrictHostKeyChecking=no usuario@10.8.0.18
  ```

---

## ⛽ Arquitectura de Pista (Surtidores Dresser Wayne DART)

- **Protocolo de Surtidores:** Dresser Wayne DART a 9600 baudios.
- **Puerto Serie Físico:** `COM3` (conversor USB/RS485 conectado a los surtidores).
- **Concentrador Local:** `C:\SDES\SDES.exe` (Sistema de Dispositivos Electrónicos de Surtidores).
- **API Nativa de Aseproda:** `.NET Assembly` `C:\Program Files\Aseproda\VirtusTPV Net\ClienteSDESNet.dll`
  - Clase principal: `aseproda.ClienteSDES2.ClienteSDES2`
  - Puerto de comunicación local: `TCP 127.0.0.1:8777`
  - Métodos nativos clave:
    - `Desbloquear(calle)`: Desbloquea físicamente la calle para autorizar suministro.
    - `Bloquear(calle)`: Bloquea físicamente la calle al terminar el suministro.
    - `CambiarModoTrabajo(calle, modo)`: Conmuta entre `ATENDIDO` (0), `POSTPAGO` (1) y `PREPAGO` (2).
- **Archivos de Configuración SDES:**
  - `C:\SDES\ModoTrabajo.ini`: Modos de operación por calle (1 a 8).
    - `0` = **ATENDIDO** (Manguera desbloqueada libremente al descolgar 🔓).
    - `1` = **POSTPAGO** (Manguera autorizada, venta pendiente al colgar 🔓).
    - `2` = **PREPAGO** (Manguera bloqueada 🔒, requiere preautorización de importe).
  - `C:\SDES\ConcentradorDW.ini`: Configuración del puerto COM3, baudrate y mapeo de mangueras y tanques.
  - `C:\SDES\logs\dw.log`: Registro de eventos de pista en tiempo real (descolgado, repostaje, fin de venta).
- **Base de Datos Local Aseproda:** MySQL 5.5 en `localhost:3306`, base de datos `virtusgesnet`, usuario `root`, contraseña `.root.`.

---

## 🚀 Odoo Cloud (Entorno Producción)

- **URL:** `https://odoo.utrecar.com`
- **Base de Datos:** `odoo`
- **Punto de Venta:** `E.S. Repsol` (Config ID: `7`)
- **Turno / Sesión Activa:** `POS/00008` (ID: `8`)
- **Parámetro de Estado de Calles:** `pos_gas_station.pumps_state_7`
- **Parámetro de Comandos de Control:** `pos_gas_station.pump_command_7`
- **Mapeo de Combustibles:**
  - Gasóleo A: ID `51` (código `GAS_A`)
  - Sin Plomo 95: ID `52` (código `SP95`)
  - Gasóleo Plus: ID `54` (código `GAS_PLUS`)

---

## 🔄 Protocolo de Control Bidireccional Odoo TPV ➔ Pista

1. **Autorización desde TPV:**
   - El cajero pulsa "AUTORIZAR" en la Calle deseada o selecciona litros/importe.
   - El backend de Odoo escribe en `pos_gas_station.pump_command_7` la acción `authorize`.
   - El agente puente `agente_pista_odoo_bridge.py` lee el comando en milisegundos e invoca:
     ```python
     self.sdes_client.CambiarModoTrabajo(calle, ClienteSDES2.ModosTrabajo.ATENDIDO)
     self.sdes_client.Desbloquear(calle)
     ```
2. **Suministro en Pista:**
   - El cliente descuelga la manguera y el surtidor despacha combustible.
3. **Fin de Repostaje:**
   - El cliente cuelga la manguera; `dw.log` y MySQL registran los litros e importe exactos.
   - El agente bloquea la manguera para evitar nuevos repostajes no autorizados:
     ```python
     self.sdes_client.CambiarModoTrabajo(calle, ClienteSDES2.ModosTrabajo.PREPAGO)
     self.sdes_client.Bloquear(calle)
     ```
   - El ticket queda en pantalla del TPV de Odoo en color naranja: **"PENDIENTE DE COBRO"**.
4. **Cobro:**
   - El cajero hace clic en **"PASAR A TICKET"**, selecciona método de pago (Efectivo / Tarjeta) y valida la venta.

---

## 🛠️ Arranque Automático e Invisible 24/7 (Sin Ventanas para el Cajero)

Para garantizar que el empleado trabaje únicamente con Odoo sin ver pantallas negras de consola ni que VirtusTPV interfiera tras un reinicio del servidor de la gasolinera:

1. **Agente Odoo en Segundo Plano (Sesión 0):**
   - Tarea Programada: `AgenteOdooRepsol`
   - Ejecuta: `C:\Utrecar\iniciar_agente_odoo.bat` usando `pythonw.exe` (intérprete GUI sin consola).
   - Desencadenador: Al arrancar el sistema (`BootTrigger`).
   - Usuario: `NT AUTHORITY\SYSTEM` (Sesión 0, tiempo de ejecución ilimitado `PT0S`, reinicio automático en caso de fallo).
2. **Concentrador SDES en Segundo Plano:**
   - Tarea Programada: `RunSDES`
   - Ejecuta: `C:\SDES\arrancar_sdes.bat` (verificando idempotencia con `tasklist`).
   - Desencadenador: Al arrancar el sistema (`BootTrigger`) bajo `SYSTEM`.
   - Script de respaldo silencioso para el usuario: `C:\SDES\arrancar_sdes.vbs` (ejecución oculta).
3. **Desactivación de VirtusTPV:**
   - Eliminada la entrada `Administracion Corporativa` de `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`.
   - Accesos directos antiguos archivados en `C:\Users\usuario\Desktop\Aseproda_Respaldo`.
4. **Acceso Directo para el Empleado:**
   - Acceso en escritorio: `C:\Users\usuario\Desktop\Odoo TPV - Gasolinera Repsol.lnk`
   - Comando: `"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" --app=https://odoo.utrecar.com/pos/ui?config_id=7`
   - Abre directamente el TPV de Odoo en modo aplicación a pantalla completa sin barras de direcciones ni errores.

---

## 🧪 Comprobación y Logs en Vivo

```cmd
# Comprobar estado de tareas y procesos
ssh usuario@10.8.0.18 "schtasks /query /tn AgenteOdooRepsol /fo list"
ssh usuario@10.8.0.18 "tasklist | findstr -i python"

# Ver log en tiempo real
ssh usuario@10.8.0.18 "type C:\Utrecar\agente_odoo_repsol.log"
```
