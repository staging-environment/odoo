# -*- coding: utf-8 -*-
"""
UTRECAR ERP - Agente Puente de Pista en Tiempo Real (E.S. Repsol - Trieste)
Conexión 100% NATIVA EN PYTHON PURO (Sin DLLs, sin .NET, sin librerías de Aseproda).
Se comunica directamente por TCP Sockets (127.0.0.1:8777) mediante protocolo binario propio.
"""

import os
import sys
import time
import json
import re
import socket
import struct
import threading
import xmlrpc.client
import logging
from datetime import datetime

# Compatibilidad con consola Windows cp1252
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Conexión nativa opcional con API ClienteSDES2 para consulta directa de microswitch
try:
    import clr
    clr.AddReference(r"C:\Program Files\Aseproda\VirtusTPV Net\ClienteSDESNet.dll")
    from aseproda.ClienteSDES2 import ClienteSDES2
    SDES_DLL_DISPONIBLE = True
except Exception:
    SDES_DLL_DISPONIBLE = False

# ==================== CONFIGURACIÓN ODOO CLOUD ====================
ODOO_URL = "https://odoo.utrecar.com"
DB_NAME = "odoo"
USER_LOGIN = "jarodriguezbonilla@gmail.com"
USER_PASS = "Utrecar2026!"
CONFIG_ID = 7  # ID de pos.config en Odoo (E.S. Repsol)

# ==================== CONFIGURACIÓN ESTACIÓN LOCAL ==================
CODIGO_ESTACION = 5  # Código de estación en virtusgesnet (Trieste)
TOTAL_CALLES = 8
SDES_PORT = 8777

# Mapeo de Productos (Trieste) -> Odoo
MAPA_COMBUSTIBLES = {
    "1": {"id": 51, "name": "Gasóleo A", "code": "GA", "price": 1.45},
    "2": {"id": 52, "name": "Sin Plomo 95", "code": "95", "price": 1.55},
    "3": {"id": 54, "name": "Diesel Ultimate", "code": "G+", "price": 1.55},
    "4": {"id": 52, "name": "Sin Plomo 95", "code": "95", "price": 1.55},
    "default": {"id": 51, "name": "Gasóleo A", "code": "GA", "price": 1.45}
}

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)

# ==============================================================================
# DRIVER NATIVO 100% PYTHON PARA CONTROL DE HARDWARE DE PISTA (TCP SOCKETS)
# Reemplaza completamente a ClienteSDESNet.dll y cualquier dependencia de Aseproda
# ==============================================================================
class PurePythonSdesClient:
    VERSION = 2
    MSG_SUBSCRIBIR = 1
    MSG_DESBLOQUEO = 3
    MSG_BLOQUEO = 4
    MSG_PREFIJADO = 5
    MSG_MODO_TRABAJO = 6
    MSG_COBRO = 10
    MSG_ESTADO = 13
    MSG_CAMBIO_INFO = 14
    MSG_NUEVA_OP = 15
    MSG_PULSO = 18

    PARAM_INT16 = 1
    PARAM_INT32 = 2
    PARAM_BYTE = 3

    def __init__(self, host="127.0.0.1", port=SDES_PORT, on_operacion_cb=None, on_cambio_cb=None):
        self.host = host
        self.port = port
        self.sock = None
        self.seq_id = 0
        self.on_operacion_cb = on_operacion_cb
        self.on_cambio_cb = on_cambio_cb
        self.running = False
        self.lock = threading.Lock()
        self.pending_responses = {}

    def connect(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(10.0)
            self.sock.connect((self.host, self.port))
            self.running = True

            # Iniciar hilo de lectura continua
            t_reader = threading.Thread(target=self._socket_reader_loop, daemon=True)
            t_reader.start()

            # Iniciar hilo de latido / ping periódico (mantiene conexión viva 24/7)
            t_heartbeat = threading.Thread(target=self._heartbeat_loop, daemon=True)
            t_heartbeat.start()

            # Suscribirse a eventos de pista (Tipo 1)
            self._send_raw(self.MSG_SUBSCRIBIR, [], wait_resp=False)
            logging.info(f"✅ [DRIVER NATIVO] Conexión TCP socket establecida con el hardware en {self.host}:{self.port}")
            return True
        except Exception as e:
            logging.warning(f"Aviso conectando socket hardware ({self.host}:{self.port}): {e}")
            self.sock = None
            self.running = False
            return False

    def is_connected(self):
        return self.sock is not None and self.running

    def _next_id(self):
        with self.lock:
            self.seq_id = (self.seq_id + 1) & 0xFFFF
            return self.seq_id

    def _heartbeat_loop(self):
        while self.running:
            time.sleep(5.0)
            if not self.running or not self.sock:
                break
            try:
                pkt_id = self._next_id()
                ping_header = struct.pack(">HHHBB I", self.VERSION, pkt_id, self.MSG_PULSO, 0, 0, 0)
                with self.lock:
                    if self.sock and self.running:
                        self.sock.sendall(ping_header)
            except Exception as e:
                logging.debug(f"Aviso en heartbeat socket: {e}")
                self.running = False
                break

    def _send_raw(self, msg_type, params, wait_resp=True, timeout=3.0):
        if not self.is_connected():
            return None

        param_bytes = bytearray()
        for ptype, pval in params:
            if ptype == self.PARAM_INT16:
                param_bytes.extend(struct.pack(">HH", self.PARAM_INT16, int(pval) & 0xFFFF))
            elif ptype == self.PARAM_INT32:
                param_bytes.extend(struct.pack(">HI", self.PARAM_INT32, int(pval) & 0xFFFFFFFF))
            elif ptype == self.PARAM_BYTE:
                param_bytes.extend(struct.pack(">HB", self.PARAM_BYTE, int(pval) & 0xFF))

        num_params = len(params)
        payload_len = len(param_bytes)
        packet_id = self._next_id()

        header = struct.pack(">HHHBB I", self.VERSION, packet_id, msg_type, 0, num_params, payload_len)
        event = threading.Event()
        if wait_resp:
            self.pending_responses[packet_id] = {"event": event, "resp": None}

        try:
            with self.lock:
                if self.sock and self.running:
                    self.sock.sendall(header + param_bytes)
        except Exception as e:
            logging.error(f"Error enviando comando socket {msg_type}: {e}")
            self.pending_responses.pop(packet_id, None)
            self.running = False
            return None

        if not wait_resp:
            return None

        if event.wait(timeout):
            resp = self.pending_responses.pop(packet_id, {}).get("resp")
            return resp
        else:
            self.pending_responses.pop(packet_id, None)
            return None

    def _socket_reader_loop(self):
        while self.running:
            try:
                header_raw = self._recv_exact(12)
                if not header_raw or len(header_raw) < 12:
                    break
                version, pkt_id, msg_type, is_resp, num_params, payload_len = struct.unpack(">HHHBB I", header_raw)
                payload = self._recv_exact(payload_len) if payload_len > 0 else b""

                if is_resp == 1:
                    if pkt_id in self.pending_responses:
                        self.pending_responses[pkt_id]["resp"] = {
                            "id": pkt_id,
                            "type": msg_type,
                            "num_params": num_params,
                            "payload": payload
                        }
                        self.pending_responses[pkt_id]["event"].set()
                else:
                    if msg_type == self.MSG_NUEVA_OP:
                        # Enviar inmediatamente el ACK requerido por SDES para liberar la cola (1 = Aceptado/True)
                        try:
                            ack_hdr = struct.pack(">HHHBB I", self.VERSION, pkt_id, self.MSG_NUEVA_OP, 1, 1, 3)
                            ack_pay = struct.pack(">HB", self.PARAM_BYTE, 1)
                            with self.lock:
                                if self.sock and self.running:
                                    self.sock.sendall(ack_hdr + ack_pay)
                        except Exception as e:
                            logging.debug(f"Aviso enviando ACK nueva op: {e}")

                        # Decodificar datos de la venta completada
                        try:
                            if len(payload) >= 24 and self.on_operacion_cb:
                                op_id = struct.unpack_from(">I", payload, 2)[0]
                                fecha_raw = payload[6:20].decode("ascii", errors="ignore").strip() if len(payload) >= 20 else ""
                                op_ts = None
                                if fecha_raw:
                                    try:
                                        op_ts = datetime.strptime(fecha_raw, "%Y%m%d%H%M%S").timestamp()
                                    except Exception:
                                        op_ts = None
                                rest = payload[20:]
                                calle, manguera, prod, precio, tanque = struct.unpack_from(">HHHHH", rest, 0)
                                lts, imp, imp_pref = struct.unpack_from(">III", rest, 10)
                                self.on_operacion_cb(calle, lts / 100.0, imp / 100.0, precio / 1000.0, prod, op_ts)
                        except Exception as e:
                            logging.error(f"Error decodificando MSG_NUEVA_OP: {e}")

                    elif msg_type == self.MSG_CAMBIO_INFO:
                        try:
                            if len(payload) >= 24 and self.on_cambio_cb:
                                ptype, calle, flags, cod_err, prod_pref = struct.unpack_from(">HHHHH", payload, 0)
                                imp_pref, imp_serv, lts_serv = struct.unpack_from(">III", payload, 10)
                                prod_serv = struct.unpack_from(">H", payload, 22)[0] if len(payload) >= 24 else 0
                                is_sum = bool(flags & 0x0010)
                                is_pte = bool(flags & 0x0002)
                                is_col = bool(flags & 0x0001)
                                self.on_cambio_cb(calle, is_sum, is_pte, is_col, lts_serv / 100.0, imp_serv / 100.0, prod_serv)
                        except Exception as e:
                            logging.error(f"Error decodificando MSG_CAMBIO_INFO: {e}")
            except Exception as e:
                logging.debug(f"Conexión de lectura cerrada: {e}")
                break
        self.running = False

    def _recv_exact(self, length):
        data = bytearray()
        while len(data) < length and self.running:
            try:
                chunk = self.sock.recv(length - len(data))
                if not chunk:
                    break
                data.extend(chunk)
            except socket.timeout:
                continue
            except Exception:
                break
        return bytes(data)

    def bloquear(self, calle):
        res = self._send_raw(self.MSG_BLOQUEO, [(self.PARAM_INT16, calle)])
        if res and len(res["payload"]) >= 4:
            err = struct.unpack(">HH", res["payload"][:4])[1]
            return err == 0
        return False

    def desbloquear(self, calle):
        res = self._send_raw(self.MSG_DESBLOQUEO, [(self.PARAM_INT16, calle)])
        if res and len(res["payload"]) >= 4:
            err = struct.unpack(">HH", res["payload"][:4])[1]
            return err == 0
        return False

    def cobrar(self, calle):
        res = self._send_raw(self.MSG_COBRO, [(self.PARAM_INT16, calle)])
        if res and len(res["payload"]) >= 4:
            err = struct.unpack(">HH", res["payload"][:4])[1]
            return err == 0
        return False

    def prefijar(self, calle, producto, importe):
        centimos = int(round(importe * 100))
        params = [
            (self.PARAM_INT16, calle),
            (self.PARAM_INT16, producto),
            (self.PARAM_INT32, centimos)
        ]
        res = self._send_raw(self.MSG_PREFIJADO, params)
        if res and len(res["payload"]) >= 4:
            err = struct.unpack(">HH", res["payload"][:4])[1]
            return err == 0
        return False

    def cambiar_modo_trabajo(self, calle, modo):
        params = [
            (self.PARAM_INT16, calle),
            (self.PARAM_INT16, modo)
        ]
        res = self._send_raw(self.MSG_MODO_TRABAJO, params)
        if res and len(res["payload"]) >= 4:
            err = struct.unpack(">HH", res["payload"][:4])[1]
            return err == 0
        return False

    def obtener_estado_raw(self):
        res = self._send_raw(self.MSG_ESTADO, [])
        return res["payload"] if res else b""

    def close(self):
        self.running = False
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None


class AgentePistaRepsol:
    def __init__(self):
        self.start_time = time.time()
        self.uid = None
        self.models = None
        self.pumps = []
        self.ultimo_id_expedicion = 0
        self.ultimo_envio_odoo = 0
        self.ultimo_dibujo = 0
        self.modo_estacion_global = "blocked"  # Modo por defecto para control Odoo
        self.sdes_client = None
        self.sdes_api = None
        self.last_sdes_check = 0
        self.last_command_ts = 0.0
        if SDES_DLL_DISPONIBLE:
            try:
                self.sdes_api = ClienteSDES2(None)
                logging.info("[OK] Interfaz SDES API inicializada para lectura directa de estado.")
            except Exception as e:
                logging.warning(f"Aviso inicializando ClienteSDES2: {e}")
        self.asegurar_conexion_hardware()
        self.inicializar_calles()

    def inicializar_calles(self):
        self.pumps = []
        for i in range(1, TOTAL_CALLES + 1):
            status = self.modo_estacion_global
            status_txt = "ATENDIDO" if status == "atendido" else "PREPAGO"
            self.pumps.append({
                "id": i,
                "name": f"Calle {i}",
                "fuel": "Gasóleo A / Sin Plomo 95",
                "amount": 0.0,
                "liters": 0.0,
                "price": 1.45,
                "product_id": 51,
                "status": status,
                "statusText": status_txt,
                "has_prepay": False,
                "is_descolgada": False,
                "updated_at": time.time()
            })

    def asegurar_conexion_hardware(self):
        if self.sdes_client is None or not self.sdes_client.is_connected():
            self.sdes_client = PurePythonSdesClient(
                on_operacion_cb=self._on_nueva_operacion_socket,
                on_cambio_cb=self._on_cambio_estado_socket
            )
            if self.sdes_client.connect():
                logging.info("[OK] Driver nativo Python conectado con hardware de pista (TCP 8777).")
            else:
                logging.warning("[AVISO] No se pudo conectar con el hardware en TCP 8777.")

    def _on_cambio_estado_socket(self, calle, is_suministrando, is_pte_cobro, is_colgado, litros, importe, prod_code):
        """Procesa cambio de estado en vivo con litros e importe en tiempo real"""
        if not (1 <= calle <= TOTAL_CALLES):
            return
        local = self.pumps[calle - 1]
        hubo_cambio = False

        is_des = not is_colgado
        if self._sim_microswitch_activo(calle):
            # Simulación en curso: el microswitch real (manguera colgada) no debe resetear la calle
            is_des = local.get("is_descolgada", False)
            is_colgado = not is_des
        if local.get("is_descolgada") != is_des:
            local["is_descolgada"] = is_des
            hubo_cambio = True
            logging.info(f"🔌 [SOCKET 8777] Calle {calle}: manguera {'DESCOLGADA' if is_des else 'COLGADA'}")

        if is_suministrando:
            if local["status"] != "dispensing" or abs(local["liters"] - litros) > 0.05 or abs(local["amount"] - importe) > 0.05:
                local["status"] = "dispensing"
                local["statusText"] = f"SUMINISTRO {litros:.2f}L" if litros > 0 else "SUMINISTRO"
                local["liters"] = round(litros, 2)
                local["amount"] = round(importe, 2)
                local["updated_at"] = time.time()
                hubo_cambio = True
                logging.info(f"⛽ [SUMINISTRO EN VIVO] Calle {calle}: {litros:.2f}L | {importe:.2f}€")
        elif local["status"] == "dispensing" and not is_pte_cobro and not local.get("has_prepay") and is_colgado:
            # Si el hardware ya no está suministrando activamente ni pendiente de cobro y la manguera está colgada, resetear a estado seguro
            status = self.modo_estacion_global
            status_txt = "ATENDIDO" if status == "atendido" else "PREPAGO"
            local["status"] = status
            local["statusText"] = status_txt
            local["amount"] = 0.0
            local["liters"] = 0.0
            local["preset_amount"] = 0.0
            local["has_prepay"] = False
            local["is_lleno"] = False
            local["is_descolgada"] = False
            local["updated_at"] = time.time()
            hubo_cambio = True
            logging.info(f"🔒 Calle {calle} finalizó suministro/bloqueada -> {status_txt}")

        if hubo_cambio:
            self.enviar_estado_a_odoo(forzar=True)

    def _on_nueva_operacion_socket(self, calle, litros, importe, precio, cod_producto, op_ts=None):
        """Procesa evento instantáneo de nueva operación finalizada recibido por el socket"""
        now = time.time()
        # Si la operación tiene una fecha/hora antigua (más de 60s antes de ahora o anterior al arranque del agente),
        # es un replay de la cola histórica interna de SDES que ya fue ACKed. No debe ensuciar la pantalla en vivo.
        if op_ts and (now - op_ts > 60.0):
            logging.info(f"⏭️ [OP HISTÓRICA SDES DESCARTADA] Calle {calle}: {litros:.2f}L | {importe:.2f}€ con antigüedad de {now - op_ts:.0f}s. ACK confirmado a SDES, no se aplica a pantalla en vivo.")
            return
        self.marcar_calle_completada(calle, litros, importe, precio, cod_producto)

    def conectar_odoo(self):
        try:
            common = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/common", allow_none=True)
            self.uid = common.authenticate(DB_NAME, USER_LOGIN, USER_PASS, {})
            if self.uid:
                self.models = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/object", allow_none=True)
                logging.info(f"[OK] Conectado a Odoo Cloud con UID {self.uid}")
                return True
            else:
                logging.error("[ERROR] Autenticación fallida en Odoo Cloud.")
                return False
        except Exception as e:
            logging.error(f"[ERROR] Error de conexión con Odoo: {e}")
            return False

    def enviar_estado_a_odoo(self, forzar=False):
        now = time.time()
        if not forzar and (now - self.ultimo_envio_odoo < 0.8):
            return

        self.ultimo_envio_odoo = now
        payload = {
            "config_id": CONFIG_ID,
            "timestamp": now,
            "station_name": "CONTROL DE PISTA - E.S. REPSOL",
            "modo_estacion": self.modo_estacion_global,
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

    def autorizar_surtidor_hardware(self, calle, importe=0.0, litros=0.0, combustible="", has_prepay=False):
        if not (1 <= calle <= TOTAL_CALLES):
            return

        self.asegurar_conexion_hardware()
        if not self.sdes_client or not self.sdes_client.is_connected():
            logging.error(f"No hay conexión con hardware para autorizar Calle {calle}")
            return

        prods_pref = []
        comb_upper = (combustible or "").upper()
        if "95" in comb_upper or "PLOMO" in comb_upper:
            prods_pref = [2, 4]  # En la estación Repsol, Manguera 1 (prod 4) y Manguera 2 (prod 2) son Sin Plomo 95
        elif "PLUS" in comb_upper or "ULTIMATE" in comb_upper or "G+" in comb_upper:
            prods_pref = [3]     # Manguera 3 es Diesel Ultimate
        elif " B" in comb_upper or "AGR" in comb_upper:
            prods_pref = [3]
        elif "GASOIL" in comb_upper or "GASÓLEO" in comb_upper or "DIESEL" in comb_upper or "GA" in comb_upper:
            prods_pref = [1]     # Manguera 4 es Gasóleo A

        try:
            if importe and float(importe) > 0:
                imp = float(importe)
                logging.info(f"🎯 [HARDWARE PREFIJADO NATIVO] Fijando límite de {imp:.2f} € en Calle {calle} (Productos hardware: {prods_pref}) | Prepago previo: {has_prepay}...")
                
                # Para prefijar con corte de válvula exacto, modo PREPAGO (Modo 2)
                self.sdes_client.cambiar_modo_trabajo(calle, 2)
                
                for p_id in prods_pref:
                    res_pref = self.sdes_client.prefijar(calle, p_id, imp)
                    logging.info(f"🎯 [HARDWARE NATIVO] prefijar(calle={calle}, prod={p_id}, {imp}€) -> {res_pref}")
                
                if not prods_pref:
                    res_pref_gen = self.sdes_client.prefijar(calle, 0, imp)
                    logging.info(f"🎯 [HARDWARE NATIVO] prefijar genérico(calle={calle}, prod=0, {imp}€) -> {res_pref_gen}")

                self.cambiar_modo_calle(calle, "dispensing", f"PREFIJADO {imp:.2f}€")
                self.pumps[calle - 1]["preset_amount"] = imp
                self.pumps[calle - 1]["has_prepay"] = bool(has_prepay)
            else:
                # Suministro LIBRE (LLENO)
                logging.info(f"⛽ [HARDWARE LIBRE NATIVO] Enviando DESBLOQUEO LIBRE (LLENO) a Calle {calle}...")
                self.sdes_client.cambiar_modo_trabajo(calle, 0)
                res_desb = self.sdes_client.desbloquear(calle)
                self.cambiar_modo_calle(calle, "dispensing", "LLENO (POSTPAGO)")
                self.pumps[calle - 1]["has_prepay"] = False
                self.pumps[calle - 1]["is_lleno"] = True
                logging.info(f"⛽ [HARDWARE NATIVO] Calle {calle} libre desbloqueada -> {res_desb}")

        except Exception as e:
            logging.error(f"Error autorizando hardware en Calle {calle}: {e}")

    def desbloquear_surtidor_hardware(self, calle):
        if not (1 <= calle <= TOTAL_CALLES):
            return
        logging.info(f"⛽ [HARDWARE NATIVO] Enviando DESBLOQUEO LIBRE (ATENDIDO) a Calle {calle}...")
        self.asegurar_conexion_hardware()
        if self.sdes_client and self.sdes_client.is_connected():
            try:
                self.sdes_client.cambiar_modo_trabajo(calle, 0)
                res_desb = self.sdes_client.desbloquear(calle)
                self.cambiar_modo_calle(calle, "atendido", "LIBRE")
                self.pumps[calle - 1]["has_prepay"] = False
                self.pumps[calle - 1]["is_lleno"] = False
                self.pumps[calle - 1]["is_descolgada"] = False
                self.pumps[calle - 1]["amount"] = 0.0
                self.pumps[calle - 1]["liters"] = 0.0
                logging.info(f"⛽ [HARDWARE NATIVO] Desbloquear(calle={calle}) -> {res_desb}")
            except Exception as e:
                logging.error(f"Error desbloqueando hardware en Calle {calle}: {e}")

    def bloquear_surtidor_hardware(self, calle):
        if not (1 <= calle <= TOTAL_CALLES):
            return
        logging.info(f"🔒 [HARDWARE NATIVO] Enviando BLOQUEO (PREPAGO) a Calle {calle}...")
        self.asegurar_conexion_hardware()
        if self.sdes_client and self.sdes_client.is_connected():
            try:
                self.sdes_client.prefijar(calle, 0, 0.0)
                self.sdes_client.cambiar_modo_trabajo(calle, 2)
                res_bloq = self.sdes_client.bloquear(calle)
                self.cambiar_modo_calle(calle, "blocked", "PREPAGO")
                self.pumps[calle - 1]["has_prepay"] = False
                self.pumps[calle - 1]["is_lleno"] = False
                self.pumps[calle - 1]["is_descolgada"] = False
                self.pumps[calle - 1]["amount"] = 0.0
                self.pumps[calle - 1]["liters"] = 0.0
                logging.info(f"🔒 [HARDWARE NATIVO] Bloquear(calle={calle}) -> {res_bloq}")
            except Exception as e:
                logging.error(f"Error bloqueando hardware en Calle {calle}: {e}")

    def procesar_comandos_odoo(self):
        try:
            param_key = f'pos_gas_station.pump_command_{CONFIG_ID}'
            cmd_raw = self.models.execute_kw(
                DB_NAME, self.uid, USER_PASS,
                'ir.config_parameter', 'get_param',
                [param_key]
            )
            if cmd_raw:
                cmd = json.loads(cmd_raw)
                ts = cmd.get("timestamp", 0)
                if ts != self.last_command_ts and ts > 0:
                    self.last_command_ts = ts
                    action = cmd.get("action")
                    pid = cmd.get("pump_id")
                    logging.info(f"⚡ [COMANDO ODOO] Acción={action} para Calle={pid} (ts={ts})")
                    
                    if action == "authorize":
                        fuel = cmd.get("fuel", "GA")
                        amount = cmd.get("amount", 0.0)
                        liters = cmd.get("liters", 0.0)
                        has_prepay = bool(cmd.get("has_prepay", False))
                        self.autorizar_surtidor_hardware(pid, importe=amount, litros=liters, combustible=fuel, has_prepay=has_prepay)
                    elif action == "lock":
                        self.bloquear_surtidor_hardware(pid)
                        self.cambiar_modo_calle(pid, "blocked", "PREPAGO")
                    elif action == "unlock":
                        self.desbloquear_surtidor_hardware(pid)
                        self.cambiar_modo_calle(pid, "atendido", "ATENDIDO")
                    elif action in ("set_global_mode", "set_track_mode"):
                        mode = cmd.get("mode")
                        is_atendido = mode in ("atendido", "lleno", "postpago")
                        self.modo_estacion_global = "atendido" if is_atendido else "blocked"
                        status_str = "atendido" if is_atendido else "blocked"
                        status_txt = "LIBRE" if is_atendido else "PREPAGO"
                        logging.info(f"🔄 [CAMBIO GLOBAL MODO] Estableciendo toda la pista en {status_txt} ({self.modo_estacion_global})")
                        for i in range(1, TOTAL_CALLES + 1):
                            if self.pumps[i-1]["status"] not in ("ready", "dispensing"):
                                self.pumps[i-1]["status"] = status_str
                                self.pumps[i-1]["statusText"] = status_txt
                                self.pumps[i-1]["amount"] = 0.0
                                self.pumps[i-1]["liters"] = 0.0
                                self.pumps[i-1]["updated_at"] = time.time()
                                if is_atendido:
                                    self.desbloquear_surtidor_hardware(i)
                                else:
                                    self.bloquear_surtidor_hardware(i)
                        self.enviar_estado_a_odoo(forzar=True)
                    elif action in ("set_mode", "set_pump_mode"):
                        mode = cmd.get("mode")
                        is_atendido = mode in ("atendido", "lleno", "postpago")
                        status_str = "atendido" if is_atendido else "blocked"
                        status_txt = "LIBRE" if is_atendido else "PREPAGO"
                        if pid and 1 <= pid <= TOTAL_CALLES:
                            if self.pumps[pid-1]["status"] not in ("ready", "dispensing"):
                                self.pumps[pid-1]["status"] = status_str
                                self.pumps[pid-1]["statusText"] = status_txt
                                self.pumps[pid-1]["amount"] = 0.0
                                self.pumps[pid-1]["liters"] = 0.0
                                self.pumps[pid-1]["updated_at"] = time.time()
                                if is_atendido:
                                    self.desbloquear_surtidor_hardware(pid)
                                else:
                                    self.bloquear_surtidor_hardware(pid)
                                self.enviar_estado_a_odoo(forzar=True)
                    elif action == "clear_pump":
                        logging.info(f"✅ [COMANDO ODOO] Recibida orden de LIBERAR/COBRAR Calle {pid}")
                        self.liberar_calle_local(pid)
        except Exception as e:
            logging.debug(f"Error procesando comandos de Odoo: {e}")

    def _sim_microswitch_activo(self, calle):
        """True si hay una simulación de microswitch en curso para la calle (máx. 120 s)."""
        hasta = getattr(self, "_sim_microswitch_hasta", {}).get(calle)
        if hasta and time.time() < hasta:
            return True
        if hasta:
            self._sim_microswitch_hasta.pop(calle, None)
        return False

    def comprobar_simulacion_local(self):
        import glob
        sim_files = glob.glob(r"C:\Utrecar\simular_venta*.json")
        for sim_path in sim_files:
            try:
                with open(sim_path, "r", encoding="utf-8") as f:
                    content = f.read()
                try:
                    os.remove(sim_path)
                except Exception:
                    pass
                if not content.strip():
                    continue
                data_list = json.loads(content)
                if not isinstance(data_list, list):
                    data_list = [data_list]
                for data in data_list:
                    calle = data.get("calle", 8)
                    litros = float(data.get("litros", 24.24))
                    importe = float(data.get("importe", 40.0))
                    precio = float(data.get("precio", 1.65))
                    prod = int(data.get("cod_producto", 2))
                    estado = data.get("estado", "ready")
                    logging.info(f"🧪 [SIMULACIÓN LOCAL] Recibida simulación para Calle {calle}: {estado} ({importe}€ / {litros}L)")
                    prod_info = MAPA_COMBUSTIBLES.get(str(prod), MAPA_COMBUSTIBLES["default"])
                    if estado in ("descolgar", "colgar"):
                        # Simulación SOLO del microswitch: no cambia estado de la calle ni envía órdenes al hardware
                        if not hasattr(self, "_sim_microswitch_hasta"):
                            self._sim_microswitch_hasta = {}
                        des = estado == "descolgar"
                        self.pumps[calle - 1]["is_descolgada"] = des
                        if des:
                            self._sim_microswitch_hasta[calle] = time.time() + 120
                        else:
                            self._sim_microswitch_hasta.pop(calle, None)
                        logging.info(f"🧪 [SIMULACIÓN MICROSWITCH] Calle {calle}: manguera {'DESCOLGADA' if des else 'COLGADA'}")
                        self.enviar_estado_a_odoo(forzar=True)
                        continue
                    if not hasattr(self, "_sim_microswitch_hasta"):
                        self._sim_microswitch_hasta = {}
                    if estado in ("unhook", "dispensing"):
                        # Durante una simulación de suministro, la manguera se considera descolgada
                        self.pumps[calle - 1]["is_descolgada"] = True
                        self._sim_microswitch_hasta[calle] = time.time() + 60
                    else:
                        self._sim_microswitch_hasta.pop(calle, None)
                    if estado == "dispensing":
                        self.pumps[calle - 1]["fuel"] = prod_info["name"]
                        self.pumps[calle - 1]["product_id"] = prod_info["id"]
                        self.pumps[calle - 1]["price"] = precio
                        self._on_cambio_estado_socket(calle, True, False, False, litros, importe, prod)
                    elif estado == "unhook":
                        self.pumps[calle - 1]["status"] = "dispensing"
                        self.pumps[calle - 1]["statusText"] = "SUMINISTRO 0.00L"
                        self.pumps[calle - 1]["amount"] = 0.0
                        self.pumps[calle - 1]["liters"] = 0.0
                        self.pumps[calle - 1]["fuel"] = prod_info["name"]
                        self.pumps[calle - 1]["product_id"] = prod_info["id"]
                        self.pumps[calle - 1]["price"] = precio
                        if "has_prepay" in data:
                            self.pumps[calle - 1]["has_prepay"] = bool(data["has_prepay"])
                        if "preset_amount" in data:
                            self.pumps[calle - 1]["preset_amount"] = float(data["preset_amount"])
                        self._on_cambio_estado_socket(calle, False, False, False, 0.0, 0.0, prod)
                    else:
                        if "has_prepay" in data:
                            self.pumps[calle - 1]["has_prepay"] = bool(data["has_prepay"])
                        if "preset_amount" in data:
                            self.pumps[calle - 1]["preset_amount"] = float(data["preset_amount"])
                        self.marcar_calle_completada(calle, litros, importe, precio, prod)
            except Exception as e:
                logging.error(f"Error procesando simulación ({sim_path}): {e}")

    def leer_liberaciones_de_odoo(self):
        self.comprobar_simulacion_local()

    def liberar_calle_local(self, calle):
        if 1 <= calle <= TOTAL_CALLES:
            local = self.pumps[calle - 1]
            status_txt = "PREPAGO" if self.modo_estacion_global == "blocked" else ("ATENDIDO" if self.modo_estacion_global == "atendido" else "POSTPAGO")
            logging.info(f"Calle {calle} reseteada tras cobro/cancelación -> {status_txt}")
            local["status"] = self.modo_estacion_global
            local["statusText"] = status_txt
            local["amount"] = 0.0
            local["liters"] = 0.0
            local["preset_amount"] = 0.0
            local["has_prepay"] = False
            local["is_descolgada"] = False
            local["fuel"] = "Gasóleo A / Sin Plomo 95"
            local["updated_at"] = time.time()
            if self.sdes_client and self.sdes_client.is_connected():
                try:
                    res_cob = self.sdes_client.cobrar(calle)
                    logging.info(f"✅ [HARDWARE NATIVO] cobrar(calle={calle}) -> {res_cob}")
                except Exception as e:
                    logging.debug(f"Aviso en cobrar hardware calle {calle}: {e}")
            if self.modo_estacion_global == "blocked":
                self.bloquear_surtidor_hardware(calle)
            self.enviar_estado_a_odoo(forzar=True)

    def cambiar_modo_calle(self, calle, status, status_text):
        if 1 <= calle <= TOTAL_CALLES:
            p = self.pumps[calle - 1]
            if p["status"] != "ready":
                if p["status"] != status or p["statusText"] != status_text:
                    p["status"] = status
                    p["statusText"] = status_text
                    p["amount"] = 0.0
                    p["liters"] = 0.0
                    p["updated_at"] = time.time()
                    self.enviar_estado_a_odoo(forzar=True)

    def sincronizar_estados_hardware_sdes(self):
        """Consulta el estado del hardware para asegurar sincronización de mangueras colgadas/descolgadas y suministro en vivo"""
        now = time.time()
        if now - getattr(self, "_last_sdes_sync", 0) < 0.6:
            return
        self._last_sdes_sync = now

        if getattr(self, "sdes_api", None):
            try:
                res = self.sdes_api.ObtenerEstado()
                if res and res.estados:
                    hubo_cambio = False
                    for ec in res.estados:
                        calle = ec.numero
                        if 1 <= calle <= TOTAL_CALLES:
                            local = self.pumps[calle - 1]
                            is_des = not ec.estaColgada
                            if self._sim_microswitch_activo(calle):
                                is_des = local.get("is_descolgada", False)
                            if local.get("is_descolgada") != is_des:
                                local["is_descolgada"] = is_des
                                hubo_cambio = True
                                logging.info(f"🔌 [SDES ESTADO] Calle {calle}: manguera {'DESCOLGADA' if is_des else 'COLGADA'}")
                            if ec.estaSuministrando and local["status"] != "ready":
                                if local["status"] != "dispensing" or abs(local["liters"] - ec.litrosEnServicio) > 0.05:
                                    local["status"] = "dispensing"
                                    local["liters"] = round(ec.litrosEnServicio, 2)
                                    local["amount"] = round(ec.importeEnServicio, 2)
                                    local["statusText"] = f"SUMINISTRO {ec.litrosEnServicio:.2f}L" if ec.litrosEnServicio > 0 else "SUMINISTRO"
                                    hubo_cambio = True
                    if hubo_cambio:
                        self.enviar_estado_a_odoo(forzar=True)
            except Exception as e:
                logging.debug(f"Aviso sync SDES API: {e}")

    def marcar_calle_completada(self, calle, litros, importe, precio, cod_producto):
        if 1 <= calle <= TOTAL_CALLES:
            p = self.pumps[calle - 1]
            prod = MAPA_COMBUSTIBLES.get(str(cod_producto), MAPA_COMBUSTIBLES["default"])
            
            p["fuel"] = prod["name"]
            p["amount"] = round(importe, 2)
            p["liters"] = round(litros, 3)
            p["price"] = precio if precio > 0 else prod["price"]
            p["product_id"] = prod["id"]
            p["is_descolgada"] = False
            p["updated_at"] = time.time()

            logging.info(f"🎉 [VENTA LISTA] Calle {calle} completó {litros:.2f}L de {prod['name']} por {importe:.2f}€")

            # Solo es prepago si fue cobrado previamente en caja (has_prepay == True)
            is_prepay = bool(p.get("has_prepay", False))
            preset_amt = p.get("preset_amount", 0.0)

            # Si era prepago cobrado y no echó todo el combustible prefijado (falta por suministrar > 0.05€)
            if is_prepay and preset_amt > 0 and importe < (preset_amt - 0.05):
                logging.info(f"⚠️ [SOBRANTE PREPAGO] Calle {calle}: prefijado {preset_amt:.2f}€ vs repostado {importe:.2f}€. Bloqueando pista pero manteniendo saldo para Odoo.")
                p["status"] = "ready"
                p["statusText"] = f"SOBRANTE {(preset_amt - importe):.2f}€"
                if self.sdes_client and self.sdes_client.is_connected():
                    try:
                        self.sdes_client.bloquear(calle)
                    except Exception:
                        pass
                self.enviar_estado_a_odoo(forzar=True)
            elif is_prepay:
                logging.info(f"Calle {calle} era prepago completado íntegramente. Liberando y bloqueando pista...")
                self.liberar_calle_local(calle)
            else:
                # Suministro libre, postpago o ALBARÁN con prefijado: pasa a COBRAR/ALBARANAR
                p["status"] = "ready"
                p["statusText"] = "COBRAR"
                if self.sdes_client and self.sdes_client.is_connected():
                    try:
                        self.sdes_client.bloquear(calle)
                    except Exception:
                        pass
                self.enviar_estado_a_odoo(forzar=True)

    def pintar_tabla_consola(self):
        now = time.time()
        if now - self.ultimo_dibujo < 2.0:
            return
        self.ultimo_dibujo = now

        iconos_modo = {
            "atendido": "🟢 ATENDIDO [🔓]",
            "postpago": "🟢 POSTPAGO [🔓]",
            "blocked":  "🔴 PREPAGO  [🔒]",
            "dispensing": "🟡 SUMINISTRO [⛽]",
            "ready":    "🟠 COBRAR   [💰]"
        }
        
        modo_txt = iconos_modo.get(self.modo_estacion_global, self.modo_estacion_global)
        lineas = [
            f"\n=== ESTADO DE PISTA (ESTACIÓN {CODIGO_ESTACION} - MODO GLOBAL: {modo_txt}) ===",
            "CALLE | ESTADO ODOO       | IMPORTE  | LITROS  | COMBUSTIBLE",
            "------------------------------------------------------------------"
        ]
        for p in self.pumps:
            st = iconos_modo.get(p["status"], p["status"])
            lineas.append(f"  {p['id']:<3} | {st:<17} | {p['amount']:>6.2f} €   | {p['liters']:>5.2f} L  | {p['fuel']}")
        print("\n".join(lineas))

    def ejecutar(self):
        logging.info("=" * 60)
        logging.info("  AGENTE PUENTE DE PISTA ODOO CLOUD (E.S. REPSOL - TRIESTE)")
        logging.info("  Driver nativo socket 127.0.0.1:8777 (100% independiente de Aseproda)")
        logging.info("=" * 60)

        intentos = 0
        while not self.conectar_odoo():
            intentos += 1
            logging.warning(f"Esperando conexión con Odoo Cloud ({ODOO_URL})... Reintentando en 5s (#{intentos})")
            time.sleep(5.0)

        logging.info(f"[OK] Inicializando las {TOTAL_CALLES} calles en Odoo Cloud...")
        if self.modo_estacion_global == "blocked" and self.sdes_client and self.sdes_client.is_connected():
            for i in range(1, TOTAL_CALLES + 1):
                try:
                    self.sdes_client.cobrar(i)
                    self.sdes_client.bloquear(i)
                except Exception:
                    pass

        self.enviar_estado_a_odoo(forzar=True)
        logging.info("[OK] Bucle principal de sincronización arrancado.")

        while True:
            try:
                # 1. Asegurar socket hardware vivo
                self.asegurar_conexion_hardware()

                # 2. Sincronizar estado en tiempo real (litros en vivo)
                self.sincronizar_estados_hardware_sdes()

                # 3. Procesar comandos inmediatos emitidos desde el TPV Odoo
                self.procesar_comandos_odoo()

                # 4. Comprobar si el cajero ha cobrado algún surtidor en Odoo
                self.leer_liberaciones_de_odoo()

                # 5. Publicar estado a Odoo periódicamente
                self.enviar_estado_a_odoo()

                # 6. Mostrar tabla de monitoreo en consola
                self.pintar_tabla_consola()

                time.sleep(0.2)
            except KeyboardInterrupt:
                logging.info("\nDeteniendo Agente Puente...")
                break
            except Exception as e:
                logging.error(f"Error inesperado en bucle principal: {e}")
                time.sleep(1.0)

if __name__ == "__main__":
    agente = AgentePistaRepsol()
    agente.ejecutar()
