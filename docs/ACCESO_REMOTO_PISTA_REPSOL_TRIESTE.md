# Conexión Remota y Control de Pista: E.S. Repsol (Trieste / SE-30 Calonge)

Este documento detalla los parámetros de acceso remoto SSH, la infraestructura de pista local y el procedimiento para alternar entre VirtusTPV (Aseproda) y Odoo ERP como MÁSTER de los surtidores.

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
- **Archivos de Configuración SDES:**
  - `C:\SDES\ModoTrabajo.ini`: Define el modo de operación por calle (1 a 8).
    - `0` = **ATENDIDO** (Manguera desbloqueada libremente al descolgar 🔓).
    - `1` = **POSTPAGO** (Manguera autorizada, venta pendiente al colgar 🔓).
    - `2` = **PREPAGO** (Manguera bloqueada 🔒, requiere preautorización de importe).
  - `C:\SDES\ConcentradorDW.ini`: Configuración del puerto COM3, baudrate y mapeo de mangueras y tanques.
  - `C:\SDES\logs\dw.log`: Registro de eventos de pista en tiempo real (descolgado, repostaje, cambio de modo, fin de venta).
- **Base de Datos Local Aseproda:** MySQL 5.5 en `localhost:3306`, base de datos `virtusgesnet`, usuario `root`, contraseña `.root.`.

---

## 🚀 Odoo Cloud (Entorno Producción)

- **URL:** `https://odoo.utrecar.com`
- **Base de Datos:** `odoo`
- **Punto de Venta:** `E.S. Repsol` (Config ID: `7`)
- **Turno / Sesión Activa:** `POS/00008` (ID: `8`)
- **Parámetro de Estado de Calles:** `pos_gas_station.pumps_state_7`

---

## 🔄 Protocolo de Control: Poner Odoo como MÁSTER de Pista

### 1. Desactivar MÁSTER en VirtusTPV (Aseproda)
`VirtusTPVNet.exe` y `EOVGNET.exe` toman el control forzando todas las calles a Modo 2 (Prepago/Bloqueado). Para liberarlo:
```cmd
ssh usuario@10.8.0.18 "taskkill /IM VirtusTPVNet.exe /F"
ssh usuario@10.8.0.18 "taskkill /IM EOVGNET.exe /F"
```
*(Nota: `SDES.exe` debe permanecer en ejecución porque es el driver que dialoga con el COM3).*

### 2. Configurar Modos de Trabajo en `C:\SDES\ModoTrabajo.ini`
Para dejar las calles listas para repostar:
- Calle de prueba (ej. Calle 1): Modo `0` (Atendido) o `1` (Postpago).
- Calles en reposo: Modo `2` (Prepago).

### 3. Agente Puente de Odoo (`agente_pista_odoo_bridge.py`)
- Ubicación en servidor: `C:\agente_pista_odoo_bridge.py`
- Tarea Programada de Windows (Arranque 24/7): `AgenteOdooRepsol`
  - Lanzador: `C:\Utrecar\iniciar_agente_odoo.bat`
  - Log en vivo: `C:\Utrecar\agente_odoo_repsol.log`
- Comandos de gestión de la tarea:
  ```cmd
  # Iniciar agente
  ssh usuario@10.8.0.18 "schtasks /Run /TN AgenteOdooRepsol"

  # Comprobar proceso
  ssh usuario@10.8.0.18 "tasklist" | findstr -i python

  # Ver log en tiempo real
  ssh usuario@10.8.0.18 "type C:\Utrecar\agente_odoo_repsol.log"
  ```

---

## 🧪 Comprobación de Repostaje en Pista

1. Descolgar la manguera en la **Calle 1**.
2. Al estar en Modo Atendido, el motor arranca y suministra combustible.
3. Al colgar la manguera, `dw.log` emite la trama `CALLE:ANALIZATESTADO. NUEVAOPERACION`.
4. El agente de Odoo detecta la venta al instante y actualiza Odoo Cloud (`pos_gas_station.pumps_state_7`).
5. En la pantalla del TPV de Odoo (`https://odoo.utrecar.com/pos/ui?config_id=7`), la Calle 1 se ilumina en naranja con el importe y litros listos para cobrar con un clic en **"PASAR A TICKET"**.
