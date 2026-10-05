# -*- coding: utf-8 -*-
"""
UTRECAR ERP - Agente Puente de Pista en Tiempo Real (E.S. Repsol - Trieste)
Conecta la pista local (Aseproda / VirtusGesNet) con el TPV de Odoo Cloud.

Características:
- Monitorea las 8 Calles reales de la estación Trieste (Código 5 en VirtusGesNet).
- Actualiza en vivo el parámetro 'pos_gas_station.pumps_state_7' en Odoo Cloud.
- Pone los surtidores en 'PENDIENTE DE COBRO' al terminar el repostaje con litros e importe exactos.
- Detecta cuando el cajero pulsa en el surtidor en Odoo para liberar la pista ('LIBRE').
- Soporta detección en tiempo real desde MySQL (expediciones) y logs SDES (dw.log / multiconcentrador).
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

# Conexión MySQL local Aseproda
MYSQL_EXE = r"C:\Program Files\Aseproda\AdministracionCorporativa\mysql.exe"
MYSQL_USER = "root"
MYSQL_PASS = ".root."
MYSQL_DB = "virtusgesnet"

# Rutas SDES (Opcional, si existen logs de pista directa)
SDES_LOG_DIR = r"C:\SDES\logs"
DW_LOG = os.path.join(SDES_LOG_DIR, "dw.log")
MULTI_LOG = os.path.join(SDES_LOG_DIR, "multiconcentrador.log")

# Mapeo de Productos Aseproda (Trieste) -> Odoo
# En Trieste: Contador 1/2 = SP95, Contador 3 = Diesel Ultimate, Contador 4 = Gasoleo A
MAPA_COMBUSTIBLES = {
    "1": {"id": 56, "name": "Gasóleo A", "code": "GA", "price": 1.789},
    "2": {"id": 57, "name": "Sin Plomo 95", "code": "95", "price": 1.659},
    "3": {"id": 54, "name": "Diesel Ultimate", "code": "G+", "price": 1.849},
    "4": {"id": 57, "name": "Sin Plomo 95", "code": "95", "price": 1.659},
    "default": {"id": 56, "name": "Gasóleo A", "code": "GA", "price": 1.789}
}

# Configuración de Logging local
LOG_FILE = r"C:\Utrecar\agente_pista_repsol.log"
try:
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    logging.basicConfig(
        filename=LOG_FILE,
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s"
    )
except Exception:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


class PuentePistaOdoo:
    def __init__(self):
        self.uid = None
        self.models = None
        self.pumps = []
        self.inicializar_pistas()
        self.ultimo_id_expedicion = 0
        self.ultimo_json_enviado = ""
        self.ultimo_push = 0
        self.ultimo_dibujo = 0

    def inicializar_pistas(self):
        self.pumps = []
        for i in range(1, TOTAL_CALLES + 1):
            self.pumps.append({
                "id": i,
                "name": f"Calle {i}",
                "fuel": "Gasóleo A / Sin Plomo 95",
                "amount": 0.0,
                "liters": 0.0,
                "status": "idle",
                "statusText": "LIBRE",
                "product_id": MAPA_COMBUSTIBLES["default"]["id"],
                "price": MAPA_COMBUSTIBLES["default"]["price"],
                "updated_at": time.time()
            })

    def conectar_odoo(self):
        print(f"[*] Conectando con Odoo Cloud ({ODOO_URL})...")
        try:
            common = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/common", allow_none=True)
            self.uid = common.authenticate(DB_NAME, USER_LOGIN, USER_PASS, {})
            if self.uid:
                self.models = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/object", allow_none=True)
                print(f"[OK] Conectado a Odoo Cloud con éxito (Usuario ID: {self.uid}).")
                logging.info(f"Conectado a Odoo Cloud con UID {self.uid}")
                return True
            else:
                print("[ERROR] Autenticación fallida en Odoo Cloud.")
        except Exception as e:
            print(f"[ERROR] Error al conectar con Odoo: {e}")
            logging.error(f"Error conectando a Odoo: {e}")
        return False

    def ejecutar_sql(self, sql):
        cmd = [MYSQL_EXE, "-u", MYSQL_USER, f"-p{MYSQL_PASS}", MYSQL_DB, "-B", "-N", "-e", sql]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, errors="ignore", timeout=5)
            if res.returncode == 0:
                return res.stdout.strip().splitlines()
        except Exception as e:
            logging.debug(f"Error ejecutando SQL: {e}")
        return []

    def obtener_ultimo_id_expedicion(self):
        lineas = self.ejecutar_sql(f"SELECT MAX(id) FROM expediciones WHERE CodigoDeEstacion = {CODIGO_ESTACION};")
        if lineas and lineas[0] and lineas[0].isdigit():
            return int(lineas[0])
        return 0

    def enviar_estado_a_odoo(self, forzar=False):
        now = time.time()
        if not forzar and (now - self.ultimo_push < 0.8):
            return

        if not self.uid or not self.models:
            if not self.conectar_odoo():
                return

        payload = {
            "station_name": "CONTROL DE PISTA - E.S. REPSOL",
            "pumps": self.pumps
        }
        json_data = json.dumps(payload)

        if not forzar and json_data == self.ultimo_json_enviado and (now - self.ultimo_push < 3.0):
            return

        try:
            param_key = f"pos_gas_station.pumps_state_{CONFIG_ID}"
            self.models.execute_kw(
                DB_NAME, self.uid, USER_PASS,
                'ir.config_parameter', 'set_param',
                [param_key, json_data]
            )
            self.ultimo_json_enviado = json_data
            self.ultimo_push = now
        except Exception as e:
            logging.error(f"Error enviando pumps_state a Odoo: {e}")
            self.uid = None

    def sincronizar_liberaciones_desde_odoo(self):
        """
        Cuando el cajero pulsa en el TPV una calle pendiente de cobro, Odoo llama a
        clear_pump y pone el surtidor en 'idle' (LIBRE). Aquí lo leemos para liberar la pista local.
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
                        if local["status"] == "ready" and op.get("status") == "idle":
                            logging.info(f"Cajero cargó Calle {pid} en el ticket del TPV. Liberando a LIBRE.")
                            local["status"] = "idle"
                            local["statusText"] = "LIBRE"
                            local["amount"] = 0.0
                            local["liters"] = 0.0
                            local["updated_at"] = time.time()
        except Exception as e:
            logging.debug(f"Error leyendo liberaciones de Odoo: {e}")

    def marcar_calle_completada(self, calle, litros, importe, precio, cod_producto, fecha_hora):
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

            logging.info(f"🎯 SUMINISTRO REGISTRADO: Calle {calle} | {prod['name']} | {litros:.3f}L | {importe:.2f}€")
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] ⛽ VENTA EN PISTA -> Calle {calle}: {prod['name']} | {litros:.3f}L | {importe:.2f}€ -> ¡LISTO EN TPV!")
            self.enviar_estado_a_odoo(forzar=True)

    def pintar_tabla_consola(self):
        now = time.time()
        if now - self.ultimo_dibujo < 2.0:
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
        print("Cada suministro completado se ilumina en Odoo como PENDIENTE DE COBRO.")
        print("El cajero pulsa la casilla en la pantalla táctil y se añade al ticket.")
        print("Presiona Ctrl+C para detener.\n")

    def iniciar(self):
        print("=" * 75)
        print("   UTRECAR ERP - PUENTE PISTA A ODOO CLOUD (E.S. REPSOL - TRIESTE)")
        print("=" * 75 + "\n")

        if not self.conectar_odoo():
            input("\nPresiona Enter para reintentar...")
            if not self.conectar_odoo():
                return

        self.ultimo_id_expedicion = self.obtener_ultimo_id_expedicion()
        print(f"[OK] Conectado a base local Aseproda (virtusgesnet). Último ID expedición: #{self.ultimo_id_expedicion}")
        print(f"[OK] Inicializando las {TOTAL_CALLES} calles en Odoo Cloud...")
        self.enviar_estado_a_odoo(forzar=True)
        time.sleep(1.0)

        dw_handle = None
        re_descolgado = re.compile(r"Calle:DESBLOQUEO\.\s*SOLICITADO>\s*Calle=(\d+)", re.IGNORECASE)
        re_dart = re.compile(r"DART\.\s*REENVIO\s*DATOS>\s*Calle=(\d+)", re.IGNORECASE)

        if os.path.exists(DW_LOG):
            try:
                dw_handle = open(DW_LOG, "r", encoding="latin-1", errors="ignore")
                dw_handle.seek(0, os.SEEK_END)
            except Exception:
                pass

        try:
            while True:
                # 1. Monitoreo de nuevas expediciones en MySQL Aseproda
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
                        cod_prod = partes[6]
                        fecha_hora = partes[7]

                        self.marcar_calle_completada(surtidor, litros, importe, precio, cod_prod, fecha_hora)
                        self.ultimo_id_expedicion = max(self.ultimo_id_expedicion, exp_id)

                # 2. Lectura en tiempo real de descolgados / flujo si existe log SDES
                if dw_handle:
                    line = dw_handle.readline()
                    while line:
                        m_desc = re_descolgado.search(line)
                        if m_desc:
                            c = int(m_desc.group(1))
                            c = (c % 10) if c > 10 else c
                            if 1 <= c <= TOTAL_CALLES and self.pumps[c - 1]["status"] != "ready":
                                self.pumps[c - 1]["status"] = "dispensing"
                                self.pumps[c - 1]["statusText"] = "DESCOLGADO"
                                self.pumps[c - 1]["updated_at"] = time.time()
                                self.enviar_estado_a_odoo(forzar=True)
                        m_dart = re_dart.search(line)
                        if m_dart:
                            c = int(m_dart.group(1))
                            c = (c % 10) if c > 10 else c
                            if 1 <= c <= TOTAL_CALLES and self.pumps[c - 1]["status"] != "ready":
                                self.pumps[c - 1]["status"] = "dispensing"
                                self.pumps[c - 1]["statusText"] = "SUMINISTRANDO"
                                self.pumps[c - 1]["updated_at"] = time.time()
                        line = dw_handle.readline()
                elif os.path.exists(DW_LOG):
                    try:
                        dw_handle = open(DW_LOG, "r", encoding="latin-1", errors="ignore")
                        dw_handle.seek(0, os.SEEK_END)
                    except Exception:
                        pass

                # 3. Sincronizar liberaciones hechas por el cajero en el TPV
                self.sincronizar_liberaciones_desde_odoo()

                # 4. Enviar latido de estado a Odoo Cloud
                self.enviar_estado_a_odoo()

                # 5. Dibujar tabla interactiva en terminal
                self.pintar_tabla_consola()

                time.sleep(0.5)

        except KeyboardInterrupt:
            print("\n[DETENIDO] Agente puente detenido por el usuario.")
        except Exception as e:
            logging.error(f"Error crítico en bucle principal: {e}")
            print(f"\n[ERROR] Ocurrió un error: {e}")
        finally:
            if dw_handle:
                dw_handle.close()
            input("\nPresiona Enter para cerrar...")


if __name__ == '__main__':
    puente = PuentePistaOdoo()
    puente.iniciar()
