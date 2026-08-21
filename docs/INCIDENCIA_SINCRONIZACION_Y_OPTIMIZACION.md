# Incidencia, Estado y Gestión del Servicio de Sincronización Odoo - VirtusGesNet

**Fecha:** 21 de Agosto de 2026  
**Estado actual:** ⚠️ **DESACTIVADO Y DESHABILITADO EN PRODUCCIÓN**

---

## 1. Contexto y Motivo de la Desactivación
El servicio de sincronización en tiempo real (`odoo-sync-stations.service`), ejecutado en producción en el servidor `164.68.101.69` (`/opt/utrecar/sync_all_stations_odoo.py`), fue detenido y deshabilitado temporalmente para comprobar si estaba provocando bloqueos y lentitud en los TPVs físicos de Aseproda (especialmente en la estación de **Ronda Norte**) al realizar búsquedas de clientes u operaciones de caja en la base de datos `/home/developer/utrecardbs` (puerto MariaDB 33061).

---

## 2. Configuración del Servicio en Producción (`164.68.101.69`)

- **Nombre del servicio:** `odoo-sync-stations.service`
- **Archivo de servicio:** `/etc/systemd/system/odoo-sync-stations.service`
- **Ruta del script en producción:** `/opt/utrecar/sync_all_stations_odoo.py`
- **Archivo de log:** `/var/log/odoo_sync_stations.log`
- **Archivo de estado de IDs sincronizados:** `/opt/utrecar/sync_state_all_stations.json`

### Definición del servicio systemd:
```ini
[Unit]
Description=Sincronizador Multigasolinera Global en Tiempo Real Aseproda a Odoo Cloud
After=network.target docker.service

[Service]
Type=simple
User=root
WorkingDirectory=/opt/utrecar
ExecStart=/usr/bin/python3 /opt/utrecar/sync_all_stations_odoo.py
Restart=always
RestartSec=5
StandardOutput=append:/var/log/odoo_sync_stations.log
StandardError=append:/var/log/odoo_sync_stations.log

[Install]
WantedBy=multi-user.target
```

---

## 3. Diagnóstico Técnico de los Bloqueos en MariaDB

1. **Bloqueo a Nivel de Tabla (Table Lock en MyISAM):**
   - La base de datos de VirtusGesNet utiliza motores de tabla tradicionales (MyISAM / Aria).
   - En MyISAM, cada sentencia `SELECT` adquiere un *Read Lock* sobre toda la tabla (`expediciones`, `facturasyticketsdeventa`, `detalledefacturasyticketsdeventa`).
   - Múltiples lecturas constantes bloquean las escrituras y actualizaciones del TPV de Aseproda, provocando colas (*Waiting for table metadata lock* / *Lock wait timeout*).

2. **Ráfaga Excesiva de Consultas (24 QPS):**
   - El bucle de 1 segundo ejecutaba 20 consultas individuales a `expediciones` (1 por cada calle de las 4 gasolineras, 8 en Ronda Norte) + 4 consultas con `JOIN` para ventas.

3. **Saturación de I/O por Full Table Scans:**
   - La consulta `SELECT ... FROM expediciones WHERE CodigoDeEstacion = %s AND CodigoDeMaquinaExpendedora = %s ORDER BY id DESC LIMIT 1` sin un índice compuesto exacto provoca escaneos completos de tablas voluminosas.

4. **Conexión TCP / Thread Churn:**
   - Se creaba y cerraba una conexión a MariaDB (`pymysql.connect` / `conn.close()`) en cada iteración de 1 segundo.

5. **Nivel de Aislamiento Transaccional:**
   - Se ejecutaba bajo `REPEATABLE READ` por defecto en lugar de lecturas sucias no bloqueantes (`READ UNCOMMITTED`).

---

## 4. Plan de Optimización para la Reactivación

Antes de reactivar el servicio, el script `/opt/utrecar/sync_all_stations_odoo.py` debe recibir las siguientes modificaciones:

1. **Lectura sin Bloqueos (Dirty Reads):**
   ```sql
   SET SESSION TRANSACTION ISOLATION LEVEL READ UNCOMMITTED;
   ```
2. **Consolidación en 1 Sola Consulta Global Agregada:**
   En lugar de 24 consultas por segundo, ejecutar 1 única consulta agregada para todas las pistas:
   ```sql
   SELECT e.* FROM expediciones e
   INNER JOIN (
       SELECT MAX(id) as max_id 
       FROM expediciones 
       GROUP BY CodigoDeEstacion, CodigoDeMaquinaExpendedora
   ) ult ON e.id = ult.max_id;
   ```
3. **Conexión Persistente:** Reutilizar la conexión `pymysql` manteniendo un único pool/conexión viva en lugar de reconectar cada segundo.
4. **Espaciado del Polling:** Subir el intervalo de 1s a 2–3s para pistas y 5–10s para ventas completadas.

---

## 5. Comandos para Gestionar el Servicio en Producción

```bash
# 1. Comprobar estado del servicio
systemctl status odoo-sync-stations.service

# 2. Ver logs en tiempo real
tail -f /var/log/odoo_sync_stations.log

# 3. Reactivar el servicio
systemctl enable odoo-sync-stations.service
systemctl start odoo-sync-stations.service

# 4. Detener y deshabilitar el servicio
systemctl stop odoo-sync-stations.service
systemctl disable odoo-sync-stations.service
```
