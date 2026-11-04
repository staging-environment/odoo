# Conexión Remota y Control de Hardware: E.S. Ronda Norte (Utrera)

Este documento detalla la infraestructura de red, parámetros de acceso remoto SSH, configuración de túneles y credenciales de los dos puestos TPV de la estación de servicio Ronda Norte.

---

## 📌 Parámetros de Acceso SSH (Puesto a Puesto)

### 1. TPV 1 - Puesto Principal (Con Túnel WireGuard VPN)
- **Hostname Windows:** `DESKTOP-JL2UL2J`
- **Usuario de Windows:** `jarod`
- **IP WireGuard VPN:** `10.8.0.6` (Fija / Estática, interfaz `Rn1`)
- **IP Local LAN:** `192.168.1.20` (Fija / Estática, interfaz Ethernet)
- **Puerto SSH:** `22` (Servicio: `OpenSSH SSH Server` en Windows, inicio automático `Automatic`)
- **Autenticación:** Clave pública RSA autorizada en `C:\ProgramData\ssh\administrators_authorized_keys`
- **Comando de Conexión Directa:**
  ```bash
  ssh rondanorte
  # o también:
  ssh rondanorte-tpv1
  ```

---

### 2. TPV 2 - Puesto Secundario (Red Local LAN)
- **Hostname Windows:** `MADIC-TPV-IOT`
- **Usuario de Windows:** `madic-tpv`
- **IP Local LAN:** `192.168.1.64` (Fija / Estática, interfaz `Ethernet 2`, DHCP: No)
- **Puerta de Enlace:** `192.168.1.1`
- **DNS:** `80.58.61.250`, `8.8.8.8`
- **Puerto SSH:** `22` (Servicio: `OpenSSH SSH Server` en Windows, inicio automático `Automatic`)
- **Autenticación:** Clave pública RSA autorizada en `C:\ProgramData\ssh\administrators_authorized_keys`
- **Acceso Remoto Transparente (ProxyJump a través de TPV 1):**
  ```bash
  ssh rondanorte-tpv2
  ```

---

## ⚙️ Configuración en Clientes SSH (`~/.ssh/config` y `C:\Users\jarod\.ssh\config`)

Ambos archivos de configuración local contienen las siguientes directivas:

```ssh
Host rondanorte rondanorte-tpv1
    HostName 10.8.0.6
    User jarod
    IdentityFile ~/.ssh/id_rsa

Host rondanorte-tpv2 rondanorte2
    HostName 192.168.1.64
    User madic-tpv
    IdentityFile ~/.ssh/id_rsa
    ProxyJump rondanorte
```

---

## 🛡️ Análisis de Persistencia frente a Reinicios

1. **Servicio OpenSSH (`sshd`):**
   - Configurado en ambos equipos con tipo de inicio `Automatic`. Arranca solo a nivel de sistema antes de iniciar sesión.

2. **Direccionamiento IP:**
   - **TPV 1:** Tanto la IP de WireGuard (`10.8.0.6`) como la IP Ethernet (`192.168.1.20`) están configuradas como **estáticas (DHCP: no)**.
   - **TPV 2:** Configurado como **estática (DHCP: no)** en `192.168.1.64`.
   - **Resultado:** Ambos puestos son **100% inmunes a reinicios o apagones del router**, conservando siempre la misma configuración de acceso.

