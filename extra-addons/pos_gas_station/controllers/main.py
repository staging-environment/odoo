# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
import json
import logging

_logger = logging.getLogger(__name__)

STATION_MAP = {
    2: {"db_id": 1, "name": "E.S. RODALABOTA (EL CUERVO)", "pumps_count": 4, "fuels": [{"code": "GA", "name": "Gasóleo A", "class": "ga"}, {"code": "95", "name": "Sin Plomo 95", "class": "sp95"}]},
    3: {"db_id": 2, "name": "E.S. VISTALEGRE (UTRERA)", "pumps_count": 4, "fuels": [{"code": "GA", "name": "Gasóleo A", "class": "ga"}, {"code": "95", "name": "Sin Plomo 95", "class": "sp95"}]},
    5: {"db_id": 3, "name": "E.S. RONDA NORTE", "pumps_count": 8, "fuels": [{"code": "GA", "name": "Gasóleo A", "class": "ga"}, {"code": "95", "name": "Sin Plomo 95", "class": "sp95"}]},
    6: {"db_id": 4, "name": "E.S. ATENAS (ÉCIJA)", "pumps_count": 4, "fuels": [{"code": "GA", "name": "Gasóleo A", "class": "ga"}, {"code": "95", "name": "Sin Plomo 95", "class": "sp95"}]},
}

class PosGasStationController(http.Controller):

    @http.route('/pos_gas_station/status', type='json', auth='public', methods=['POST'], csrf=False)
    def get_pumps_status(self, config_id=None, **kw):
        if not config_id:
            config_id = 2
        try:
            config_id = int(config_id)
        except Exception:
            config_id = 2

        station_info = STATION_MAP.get(config_id, STATION_MAP[2])
        param_key = f"pos_gas_station.pumps_state_{config_id}"
        
        status_json = request.env['ir.config_parameter'].sudo().get_param(param_key)
        
        if status_json:
            try:
                pumps_data = json.loads(status_json)
                return {
                    "station_name": station_info["name"],
                    "available_fuels": station_info["fuels"],
                    "pumps": pumps_data
                }
            except Exception as e:
                _logger.error(f"Error parsing {param_key}: {e}")

        # Fallback si aún no ha sincronizado el daemon
        fuels_label = "Gasóleo A / Sin Plomo 95"
        fallback_pumps = [
            {"id": i, "status": "idle", "statusText": "Libre", "fuel": fuels_label, "amount": 0.0, "liters": 0.0}
            for i in range(1, station_info["pumps_count"] + 1)
        ]
        return {
            "station_name": station_info["name"],
            "available_fuels": station_info["fuels"],
            "pumps": fallback_pumps
        }
