# -*- coding: utf-8 -*-
"""
UTRECAR ERP - Agente Puente de Pista en Tiempo Real (E.S. Repsol - Trieste)
Conecta la pista local (Aseproda SDES / dw.log + MySQL) con el TPV de Odoo Cloud.

Características:
- Sincroniza al instante los 3 Modos de Trabajo de VirtusTPV:
    * ATENDIDO (Modo 1): Casillas en VERDE con texto ATENDIDO 🔓.
    * PREPAGO (Modo 2 / Bloqueo): Casillas en ROJO con candado cerrado 🔒.
    * POSTPAGO (Modo 0 / Desbloqueo): Casillas en VERDE con texto POSTPAGO 🔓.
- Detecta al instante la NUEVA OPERACIÓN cuando cuelgan la manguera (litros, importe, producto y precio).
- Pone los surtidores en 'PENDIENTE DE COBRO' con el combustible y color exacto (Verde SP95, Negro GA, Azul G+).
- Pasa al ticket del TPV con un toque en la pantalla táctil y libera la pista.
- Soporta como respaldo la base MySQL local (virtusgesnet.expediciones).
"""

import os
import sys
import time
import json
import re
import subprocess
import xmlrpc.client
import logging
from datetime import datetime

# ==================== CONFIGURACIÓN ODOO CLOUD ====================
ODOO_URL = "https://odoo.utrecar.com"
DB_NAME = "odoo"
USER_LOGIN = "jarodriguezbonilla@gmail.com"
USER_PASS = "Utrecar2026!"
CONFIG_ID = 7  # ID de pos.config en Odoo (E.S. Repsol)

# ==================== CONFIGURACIÓN ESTACIÓN LOCAL ==================
CODIGO_ESTACION = 5  # Código de estación en virtusgesnet (Trieste)
TOTAL_CALLES = 8

# Archivos SDES de Aseproda
SDES_LOG_DIR = r"C:\SDES\logs"
DW_LOG = os.path.join(SDES_LOG_DIR, "dw.log")

# Conexión MySQL local Aseproda (Respaldo)
MYSQL_EXE = r"C:\Program Files\Aseproda\AdministracionCorporativa\mysql.exe"
MYSQL_USER = "root"
MYSQL_PASS = ".root."
MYSQL_DB = "virtusgesnet"

# Mapeo de Productos Aseproda (Trieste) -> Odoo
# En Trieste: Contador 1/2 = SP95, Contador 3 = Diesel Ultimate, Contador 4 = Gasoleo A
MAPA_COMBUSTIBLES = {
    "1": {"id": 56, "name": "Gasóleo A", "code": "GA", "price": 1.789},
    "2": {"id": 57, "name": "Sin Plomo 95", "code": "95", "price": 1.839},
    "3": {"id": 54, "name": "Diesel Ultimate", "code": "G+", "price": 1.899},
    "4": {"id": 56, "name": "Gasóleo A", "code": "GA", "price": 1.789},
    "default": {"id": 56, "name": "Gasóleo A", "code": "GA", "price": 1.789}
}

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)

class AgentePistaRepsol:
    def __init__(self):
        self.uid = None
        self.models = None
        self.pumps = []
        self.ultimo_id_expedicion = 0
        self.ultimo_envio_odoo = 0
        self.ultimo_dibujo = 0
        self.modo_estacion_global = "atendido"  # "atendido", "postpago" o "blocked"
        self.inicializar_calles()

    def inicializar_calles(self):
        self.pumps = []
        for i in range(1, TOTAL_CALLES + 1):
            self.pumps.append({
                "id": i,
                "name": f"Calle {i}",
                "fuel": "Gasóleo A / Sin Plomo 95",
                "amount": 0.0,
                "liters": 0.0,
                "status": "atendido",
                "statusText": "ATENDIDO",
                "product_id": 56,
                "price": 1.789,
                "updated_at": time.time()
            })

    def conectar_odoo(self):
        print(f"[*] Conectando con Odoo Cloud ({ODOO_URL})...")
        try:
            common = xmlrpc.client.ServerProxy(f'{ODOO_URL}/xmlrpc/2/common', allow_none=True)
            self.uid = common.authenticate(DB_NAME, USER_LOGIN, USER_PASS, {})
            if not self.uid:
                print("[ERROR] Credenciales Odoo incorrectas.")
                return False
            self.models = xmlrpc.client.ServerProxy(f'{ODOO_URL}/xmlrpc/2/object', allow_none=True)
            print(f"[OK] Autenticado en Odoo como usuario ID #{self.uid}")
            return True
        except Exception as e:
            print(f"[ERROR] Error al conectar con Odoo: {e}")
            return False

    def ejecutar_sql(self, sql):
        if not os.path.exists(MYSQL_EXE):
            return []
        try:
            cmd = [MYSQL_EXE, f"-u{MYSQL_USER}", f"-p{MYSQL_PASS}", MYSQL_DB, "-e", sql, "-B", "-N"]
            res = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return [line.strip() for line in res.stdout.strip().split("\n") if line.strip()]
        except Exception as e:
            logging.debug(f"Error consultando MySQL: {e}")
            return []

    def obtener_ultimo_id_expedicion(self):
        filas = self.ejecutar_sql(f"SELECT MAX(id) FROM expediciones WHERE CodigoDeEstacion = {CODIGO_ESTACION};")
        if filas and filas[0] and filas[0] != "NULL":
            try:
                return int(filas[0])
            except ValueError:
                pass
        return 0

    def enviar_estado_a_odoo(self, forzar=False):
        now = time.time()
        if not forzar and (now - self.ultimo_envio_odoo < 1.0):
            return
        self.ultimo_envio_odoo = now

        if not self.uid or not self.models:
            return

        payload = {
            "station_name": "CONTROL DE PISTA - E.S. REPSOL (TRIESTE)",
            "available_fuels": [
                {"code": "GA", "name": "Gasóleo A", "class": "ga"},
                {"code": "95", "name": "Sin Plomo 95", "class": "sp95"},
                {"code": "G+", "name": "Diesel Ultimate", "class": "gplus"}
            ],
            "pumps": self.pumps
        }

        try:
            param_key = f"pos_gas_station.pumps_state_{CONFIG_ID}"
            self.models.execute_kw(
                DB_NAME, self.uid, USER_PASS,
                'ir.config_parameter', 'set_param',
                [param_key, json.dumps(payload)]
            )
        except Exception as e:
            logging.warning(f"Error enviando estado a Odoo: {e}")

    def leer_liberaciones_de_odoo(self):
        """
        Sincroniza cuando el cajero pulsa en el TPV de Odoo ('PASAR A TICKET' o cobro).
        Si Odoo marca la calle como 'idle', devolvemos localmente la calle al modo activo.
        """
        if not self.uid or not self.models:
            return
        try:
            param_key = f"pos_gas_station.pumps_state_{CONFIG_ID}"
            raw = self.models.execute_kw(
                DB_NAME, self.uid, USER_PASS,
                'ir.config_parameter', 'get_param',
                [param_key]
            )
            if raw:
                parsed = json.loads(raw)
                odoo_pumps = parsed.get("pumps", []) if isinstance(parsed, dict) else parsed
                for op in odoo_pumps:
                    pid = op.get("id")
                    if 1 <= pid <= TOTAL_CALLES:
                        local = self.pumps[pid - 1]
                        if op.get("status") == "idle" and local["status"] == "ready":
                            if time.time() - local.get("updated_at", 0) > 1.5:
                                status_txt = "PREPAGO" if self.modo_estacion_global == "blocked" else ("ATENDIDO" if self.modo_estacion_global == "atendido" else "POSTPAGO")
                                logging.info(f"Calle {pid} cobrada en Odoo. Volviendo al modo activo ({status_txt}).")
                                local["status"] = self.modo_estacion_global
                                local["statusText"] = status_txt
                                local["amount"] = 0.0
                                local["liters"] = 0.0
                                local["fuel"] = "Gasóleo A / Sin Plomo 95"
                                local["updated_at"] = time.time()
                                self.enviar_estado_a_odoo(forzar=True)
        except Exception as e:
            logging.debug(f"Error leyendo liberaciones de Odoo: {e}")

    def cambiar_modo_calle(self, calle, status, status_text):
        """Actualiza el modo de una calle (Atendido / Prepago / Postpago) respetando ventas listas"""
        if 1 <= calle <= TOTAL_CALLES:
            p = self.pumps[calle - 1]
            if p["status"] != "ready":  # No pisar si está lista para cobrar
                if p["status"] != status or p["statusText"] != status_text:
                    p["status"] = status
                    p["statusText"] = status_text
                    p["amount"] = 0.0
                    p["liters"] = 0.0
                    p["updated_at"] = time.time()
                    self.enviar_estado_a_odoo(forzar=True)

    def marcar_calle_completada(self, calle, litros, importe, precio, cod_producto):
        if 1 <= calle <= TOTAL_CALLES:
            p = self.pumps[calle - 1]
            prod = MAPA_COMBUSTIBLES.get(str(cod_producto), MAPA_COMBUSTIBLES["default"])
            
            p["status"] = "ready"
            p["statusText"] = "PENDIENTE DE COBRO"
            p["fuel"] = prod["name"]
            p["amount"] = round(importe, 2)
            p["liters"] = round(litros, 3)
            p["price"] = precio if precio > 0 else prod["price"]
            p["product_id"] = prod["id"]
            p["updated_at"] = time.time()

            logging.info(f"🎯 VENTA FINALIZADA: Calle {calle} | {prod['name']} | {litros:.2f}L | {importe:.2f}€")
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] ⛽ VENTA FINALIZADA -> Calle {calle}: {prod['name']} | {litros:.2f}L | {importe:.2f}€ -> ¡PENDIENTE DE COBRO EN TPV!")
            self.enviar_estado_a_odoo(forzar=True)

    def pintar_tabla_consola(self):
        now = time.time()
        if now - self.ultimo_dibujo < 1.5:
            return
        self.ultimo_dibujo = now

        os.system('cls' if os.name == 'nt' else 'clear')
        print("=" * 75)
        print("   UTRECAR ERP - PUENTE PISTA EN VIVO A ODOO TPV (E.S. REPSOL / TRIESTE)")
        print(f"   Servidor: {ODOO_URL} | TPV Config: #{CONFIG_ID} | Estación: #{CODIGO_ESTACION}")
        print("=" * 75)
        print(f"{'CALLE':<9} | {'ESTADO EN TPV':<22} | {'COMBUSTIBLE':<18} | {'LITROS':<9} | {'TOTAL €':<9}")
        print("-" * 75)
        for p in self.pumps:
            amt = f"{p['amount']:.2f} €" if p['amount'] > 0 else "-"
            lts = f"{p['liters']:.2f} L" if p['liters'] > 0 else "-"
            print(f"Calle {p['id']:<3} | {p['statusText']:<22} | {p['fuel'][:18]:<18} | {lts:<9} | {amt:<9}")
        print("=" * 75)
        print(f"• Modo actual detectado: {self.modo_estacion_global.upper()} (Sincronizado con VirtusTPV)")
        print("• En VirtusTPV: [ATENDIDO] ➔ Odoo muestra ATENDIDO (Verde 🔓).")
        print("• En VirtusTPV: [PREPAGO]  ➔ Odoo muestra PREPAGO (Rojo 🔒).")
        print("• En VirtusTPV: [POSTPAGO] ➔ Odoo muestra POSTPAGO (Verde 🔓).")
        print("• Fin de repostaje ➔ Pasa al instante a PENDIENTE DE COBRO con botón naranja.")
        print("Presiona Ctrl+C para salir.\n")

    def iniciar(self):
        print("=" * 75)
        print("   UTRECAR ERP - PUENTE PISTA A ODOO CLOUD (E.S. REPSOL - TRIESTE)")
        print("=" * 75 + "\n")

        if not self.conectar_odoo():
            input("\nPresiona Enter para reintentar...")
            if not self.conectar_odoo():
                return

        self.ultimo_id_expedicion = self.obtener_ultimo_id_expedicion()
        print(f"[OK] Conectado a base local Aseproda. Último ID expedición: #{self.ultimo_id_expedicion}")
        print(f"[OK] Inicializando las {TOTAL_CALLES} calles en Odoo Cloud...")
        
        self.enviar_estado_a_odoo(forzar=True)
        time.sleep(1.0)

        # Expresiones regulares dw.log
        dw_handle = None
        
        # 1. Detección de Modo de Trabajo en VirtusTPV:
        # Modo=0 -> POSTPAGO (Verde)
        # Modo=1 -> ATENDIDO (Verde)
        # Modo=2 -> PREPAGO (Rojo)
        re_modotrabajo = re.compile(r"CALLE:MODOTRABAJO>\s*Calle=(\d+)\s+Modo=\s*(\d+)", re.IGNORECASE)
        re_bloqueo = re.compile(r"Calle:(?:BLOQUEO|CERRAR)>\s*Calle=(\d+)", re.IGNORECASE)
        re_desbloqueo = re.compile(r"Calle:DESBLOQUEO\.\s*SOLICITADO>\s*Calle=(\d+)", re.IGNORECASE)

        # 2. Detección de Fin de Suministro (Litros e Importe)
        re_nueva_op = re.compile(
            r"CALLE:ANALIZATESTADO\.\s*NUEVAOPERACION>\s*Calle=(\d+).*?Producto=(\d+)\s+Litros=([\d\.]+)\s+Importe=([\d\.]+)\s+Precio=([\d\.]+)",
            re.IGNORECASE
        )

        if os.path.exists(DW_LOG):
            try:
                dw_handle = open(DW_LOG, "r", encoding="latin-1", errors="ignore")
                dw_handle.seek(0, os.SEEK_END)
                print(f"[OK] Monitor dw.log de SDES enganchado en {DW_LOG}")
            except Exception as e:
                print(f"[AVISO] No se pudo abrir dw.log: {e}")

        last_mysql_check = 0

        try:
            while True:
                # 1. LECTURA EN TIEMPO REAL DESDE dw.log (0 ms de retardo)
                if dw_handle:
                    line = dw_handle.readline()
                    while line:
                        # Cambio de Modo de Trabajo explícito
                        m_modo = re_modotrabajo.search(line)
                        if m_modo:
                            c = int(m_modo.group(1))
                            c = (c % 10) if c > 10 else c
                            modo = int(m_modo.group(2))
                            if modo == 2:
                                self.modo_estacion_global = "blocked"
                                self.cambiar_modo_calle(c, "blocked", "PREPAGO")
                            elif modo == 1:
                                self.modo_estacion_global = "atendido"
                                self.cambiar_modo_calle(c, "atendido", "ATENDIDO")
                            elif modo == 0:
                                self.modo_estacion_global = "postpago"
                                self.cambiar_modo_calle(c, "postpago", "POSTPAGO")
                            else:
                                logging.info(f"Modo detectado para Calle {c}: Modo={modo}")

                        # Bloqueo explícito de calle (PREPAGO / ROJO)
                        m_bloq = re_bloqueo.search(line)
                        if m_bloq:
                            c = int(m_bloq.group(1))
                            c = (c % 10) if c > 10 else c
                            self.cambiar_modo_calle(c, "blocked", "PREPAGO")

                        # Desbloqueo explícito de calle (POSTPAGO o ATENDIDO según modo activo)
                        m_desb = re_desbloqueo.search(line)
                        if m_desb:
                            c = int(m_desb.group(1))
                            c = (c % 10) if c > 10 else c
                            status = "atendido" if self.modo_estacion_global == "atendido" else "postpago"
                            status_text = "ATENDIDO" if self.modo_estacion_global == "atendido" else "POSTPAGO"
                            self.cambiar_modo_calle(c, status, status_text)

                        # Detección de fin de suministro
                        m_op = re_nueva_op.search(line)
                        if m_op:
                            c = int(m_op.group(1))
                            c = (c % 10) if c > 10 else c
                            prod_cod = m_op.group(2)
                            litros = float(m_op.group(3))
                            importe = float(m_op.group(4))
                            precio = float(m_op.group(5))
                            self.marcar_calle_completada(c, litros, importe, precio, prod_cod)

                        line = dw_handle.readline()
                elif os.path.exists(DW_LOG):
                    try:
                        dw_handle = open(DW_LOG, "r", encoding="latin-1", errors="ignore")
                        dw_handle.seek(0, os.SEEK_END)
                    except Exception:
                        pass

                # 2. RESPALDO MYSQL (Cada 1.5s comprueba nuevas filas en expediciones)
                now = time.time()
                if now - last_mysql_check > 1.5:
                    sql = f"""
                    SELECT id, CodigoDeMaquinaExpendedora, NumeroDeContador, CantidadExpedida, Precio, ImporteExpedido, CodigoDeProducto, FechaYHoraDeExpedicion
                    FROM expediciones
                    WHERE CodigoDeEstacion = {CODIGO_ESTACION} AND id > {self.ultimo_id_expedicion}
                    ORDER BY id ASC;
                    """
                    filas = self.ejecutar_sql(sql)
                    for f in filas:
                        partes = f.split("\t")
                        if len(partes) >= 8:
                            exp_id = int(partes[0])
                            surtidor = int(partes[1])
                            litros = float(partes[3].replace(",", "."))
                            precio = float(partes[4].replace(",", "."))
                            importe = float(partes[5].replace(",", "."))
                            producto = partes[6]
                            self.ultimo_id_expedicion = max(self.ultimo_id_expedicion, exp_id)
                            calle = (surtidor % 10) if surtidor > 10 else surtidor
                            self.marcar_calle_completada(calle, litros, importe, precio, producto)
                    last_mysql_check = now

                # 3. SINCRONIZACIÓN DESDE ODOO (Comprobar si el cajero ha cobrado o liberado calles)
                self.leer_liberaciones_de_odoo()

                # 4. ENVÍO PERIÓDICO Y PINTADO DE CONSOLA
                self.enviar_estado_a_odoo()
                self.pintar_tabla_consola()

                time.sleep(0.1)

        except KeyboardInterrupt:
            print("\n[!] Agente detenido por el usuario.")

if __name__ == "__main__":
    agente = AgentePistaRepsol()
    agente.iniciar()
