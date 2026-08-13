# RESUMEN EJECUTIVO & CONTEXTO PERSISTENTE - PROYECTO PISTA EL CUERVO

## 📌 Datos de Producción (Odoo Cloud)
- **URL Servidor Odoo Cloud:** `https://odoo.utrecar.com`
- **Base de Datos:** `odoo`
- **Usuario Administrador:** `jarodriguezbonilla@gmail.com`
- **Contraseña:** `Utrecar2026!`
- **Punto de Venta Creado:** `E.S. Rodalabota (El Cuervo)` (ID: `2`)
- **Módulo de Gasolinera:** `pos_gas_station` (Instalado y activado)

---

## 🛠️ Hardware & Instalación Eléctrica Pista (Aseproda -> DSD TECH)
- **Ubicación:** E.S. Rodalabota (El Cuervo), Sevilla.
- **Hardware Entregado:** Conversor USB a RS485 DSD TECH SH-U10 + Cable de 2 hilos 20AWG (5M).
- **Cajita Metálica Verde Aseproda (Existente en Caja):**
  - **Ranura 1 (Negro):** RS485 `Data+ (A)` ➔ Empalmar **Hilo 1** y conectar a terminal **`A+`** en DSD TECH.
  - **Ranura 2 (Blanco):** RS485 `Data- (B)` ➔ Empalmar **Hilo 2** y conectar a terminal **`B-`** en DSD TECH.
  - **`GND` y `5V0`:** VACÍOS.

---

## 💻 Protocolo de Trabajo en PowerShell (Scripts en `docs/` y `scripts/`)

| Orden | Archivo Script | Propósito | Comando Exacto en PowerShell |
| :---: | :--- | :--- | :--- |
| **ORDEN 1** | **`install_prerequisites.ps1`** | Instala Python 3.12, PySerial y Requests en 1 clic. | `powershell -ExecutionPolicy Bypass -File .\install_prerequisites.ps1` |
| **ORDEN 2** | *(Empalme físico)* | Conectar Hilo 1 $\rightarrow$ `A+` e Hilo 2 $\rightarrow$ `B-`. | *(Atornillar bornes y conectar USB)* |
| **ORDEN 3** | **`test_rs485.py`** | Prueba de consola en vivo con Auto-Detección COM. | `python test_rs485.py` |
| **ORDEN 4** | **`start_daemon.ps1`** | Arranca `agente_odoo_elcuervo.py` en segundo plano. | `powershell -ExecutionPolicy Bypass -File .\start_daemon.ps1` |
| **ORDEN 5** | **`setup_task_scheduler.ps1`** | Configura Tarea Programada para autostart 24/7. | `powershell -ExecutionPolicy Bypass -File .\setup_task_scheduler.ps1` |

---

## ⏱️ Cronograma de Señales de Surtidores (Aseproda Hexadecimal)
- **Idle / Reposo (02 30 31 41 43...):** Polling constante cada 0.5s-1s.
- **Descolgado (02 30 31 53 54...):** Manguera levantada en pista.
- **Repostaje (02 30 31 44 41...):** Conteo de litros e importe en tiempo real.
- **Fin de Venta (02 30 31 45 4E 44...):** Manguera colgada. Envío automático a Odoo Cloud.

---

## 📄 Archivo Manual PDF
- **`docs/Guia_Instalacion_RS485_ElCuervo.pdf`** (3 páginas completas con foto, diagramas y tablas de comandos).
