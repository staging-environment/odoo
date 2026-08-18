# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
import json
import logging

_logger = logging.getLogger(__name__)

STATION_MAP = {
    2: {"name": "CONTROL DE PISTA - E.S. RODALABOTA (EL CUERVO)", "pumps_count": 4, "fuels": [{"code": "GA", "name": "Gasóleo A", "class": "ga"}, {"code": "95", "name": "Sin Plomo 95", "class": "sp95"}]},
    3: {"name": "CONTROL DE PISTA - E.S. VISTALEGRE (UTRERA)", "pumps_count": 4, "fuels": [{"code": "GA", "name": "Gasóleo A", "class": "ga"}, {"code": "95", "name": "Sin Plomo 95", "class": "sp95"}]},
    5: {"name": "CONTROL DE PISTA - E.S. RONDA NORTE", "pumps_count": 8, "fuels": [{"code": "GA", "name": "Gasóleo A", "class": "ga"}, {"code": "95", "name": "Sin Plomo 95", "class": "sp95"}]},
    6: {"name": "CONTROL DE PISTA - E.S. ATENAS (ÉCIJA)", "pumps_count": 4, "fuels": [{"code": "GA", "name": "Gasóleo A", "class": "ga"}, {"code": "95", "name": "Sin Plomo 95", "class": "sp95"}]},
}

# Memoria de autorizaciones y estados temporales manuales por gasolinera
STATION_PUMP_OVERRIDES = {}

class PosGasStationController(http.Controller):

    @http.route('/pos_gas_station/status', type='json', auth='public', methods=['POST'], csrf=False, cors='*')
    def get_pumps_status(self, config_id=None, **kw):
        """
        Retorna el estado en tiempo real de los surtidores leyendo la sincronización en vivo
        de ir.config_parameter generada por el sincronizador de pista (VirtusGesNet).
        """
        if not config_id:
            config_id = 5
        try:
            config_id = int(config_id)
        except Exception:
            config_id = 5

        station_info = STATION_MAP.get(config_id)
        if not station_info:
            pos_config = request.env['pos.config'].sudo().browse(config_id)
            name = f"CONTROL DE PISTA - {pos_config.name.upper()}" if pos_config.exists() else "CONTROL DE PISTA"
            pumps_cnt = 8 if 'ronda norte' in name.lower() else 4
            station_info = {
                "name": name,
                "pumps_count": pumps_cnt,
                "fuels": [
                    {"code": "GA", "name": "Gasóleo A", "class": "ga"},
                    {"code": "95", "name": "Sin Plomo 95", "class": "sp95"}
                ]
            }

        # 1. Intentar leer estado en vivo generado por el sincronizador VirtusGesNet
        param_key = f"pos_gas_station.pumps_state_{config_id}"
        status_raw = request.env['ir.config_parameter'].sudo().get_param(param_key)
        
        pumps = []
        if status_raw:
            try:
                parsed = json.loads(status_raw)
                if isinstance(parsed, dict) and "pumps" in parsed:
                    pumps = parsed["pumps"]
                elif isinstance(parsed, list):
                    pumps = parsed
            except Exception as e:
                _logger.error(f"Error parsing live pumps parameter {param_key}: {e}")

        # 2. Si no hay datos en vivo aún, generar estructura base
        if not pumps:
            for i in range(1, station_info["pumps_count"] + 1):
                pumps.append({
                    "id": i,
                    "status": "idle",
                    "statusText": "LIBRE",
                    "fuel": "Gasóleo A / Sin Plomo 95",
                    "amount": 0.00,
                    "liters": 0.00,
                    "price": 1.78
                })

        # 3. Aplicar overrides manuales desde TPV (autorizaciones activas en memoria)
        overrides = STATION_PUMP_OVERRIDES.get(config_id, {})
        for i, pump in enumerate(pumps):
            pid = pump.get("id", i + 1)
            if pid in overrides:
                pumps[i] = overrides[pid]

        return {
            "status": "success",
            "station_name": station_info["name"],
            "available_fuels": station_info["fuels"],
            "pumps": pumps
        }

    @http.route('/pos_gas_station/authorize', type='json', auth='public', methods=['POST'], csrf=False, cors='*')
    def authorize_pump(self, config_id=None, pump_id=None, fuel='GA', amount=0, liters=0, **kw):
        """
        Registra la orden de autorización en el concentrador / memoria de pista.
        """
        cfg = int(config_id or 1)
        pid = int(pump_id or 1)
        if cfg not in STATION_PUMP_OVERRIDES:
            STATION_PUMP_OVERRIDES[cfg] = {}

        fuel_name = "Gasóleo A" if fuel == 'GA' else "Sin Plomo 95"
        amt = float(amount or 0)
        lts = float(liters or 0)

        STATION_PUMP_OVERRIDES[cfg][pid] = {
            "id": pid,
            "status": "dispensing",
            "statusText": "AUTORIZADO",
            "fuel": fuel_name,
            "amount": amt,
            "liters": lts,
            "price": 1.78 if fuel == 'GA' else 1.66
        }

        _logger.info(f"⛽ [AUTORIZACIÓN PISTA] Config {cfg} | Calle {pid} | Combustible {fuel_name} | {amt}€ / {lts}L")
        return {"status": "authorized", "pump_id": pid}

    @http.route('/pos_gas_station/cancel_authorize', type='json', auth='public', methods=['POST'], csrf=False, cors='*')
    def cancel_authorize(self, config_id=None, pump_id=None, **kw):
        """
        Cancela la autorización de una calle y la vuelve a poner en estado libre.
        """
        cfg = int(config_id or 1)
        pid = int(pump_id or 1)
        if cfg in STATION_PUMP_OVERRIDES and pid in STATION_PUMP_OVERRIDES[cfg]:
            del STATION_PUMP_OVERRIDES[cfg][pid]

        _logger.info(f"🛑 [CANCELAR AUTORIZACIÓN] Config {cfg} | Calle {pid}")
        return {"status": "cancelled", "pump_id": pid}

    @http.route('/pos_gas_station/clear_pump', type='json', auth='public', methods=['POST'], csrf=False, cors='*')
    def clear_pump(self, config_id=None, pump_id=None, **kw):
        """
        Pasa el surtidor a estado libre una vez volcado al ticket.
        """
        cfg = int(config_id or 1)
        pid = int(pump_id or 1)
        if cfg in STATION_PUMP_OVERRIDES and pid in STATION_PUMP_OVERRIDES[cfg]:
            del STATION_PUMP_OVERRIDES[cfg][pid]
        return {"status": "cleared", "pump_id": pid}
