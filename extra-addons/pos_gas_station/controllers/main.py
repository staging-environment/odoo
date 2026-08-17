# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
import json
import logging

_logger = logging.getLogger(__name__)

# Memoria de autorizaciones y estados temporales por gasolinera
STATION_PUMP_OVERRIDES = {}

class PosGasStationController(http.Controller):

    @http.route('/pos_gas_station/status', type='json', auth='user', cors='*')
    def get_pumps_status(self, config_id=None, **kw):
        """
        Retorna el estado en tiempo real de los surtidores de la gasolinera seleccionada.
        """
        station_name = "CONTROL DE PISTA"
        available_fuels = [
            {"code": "GA", "name": "Gasóleo A", "class": "ga"},
            {"code": "95", "name": "Sin Plomo 95", "class": "sp95"}
        ]
        
        num_pumps = 4
        if config_id:
            pos_config = request.env['pos.config'].sudo().browse(int(config_id))
            if pos_config.exists():
                station_name = f"CONTROL DE PISTA - {pos_config.name.upper()}"
                if 'ronda norte' in pos_config.name.lower():
                    num_pumps = 8
                    available_fuels = [
                        {"code": "GA", "name": "Gasóleo A", "class": "ga"},
                        {"code": "95", "name": "Sin Plomo 95", "class": "sp95"}
                    ]
                elif 'rodalabota' in pos_config.name.lower():
                    num_pumps = 4
                    available_fuels = [
                        {"code": "GA", "name": "Gasóleo A", "class": "ga"},
                        {"code": "95", "name": "Sin Plomo 95", "class": "sp95"}
                    ]
                elif 'atenas' in pos_config.name.lower() or 'écija' in pos_config.name.lower():
                    num_pumps = 4
                    available_fuels = [
                        {"code": "GA", "name": "Gasóleo A", "class": "ga"},
                        {"code": "95", "name": "Sin Plomo 95", "class": "sp95"}
                    ]
                elif 'vistalegre' in pos_config.name.lower():
                    num_pumps = 4
                    available_fuels = [
                        {"code": "GA", "name": "Gasóleo A", "class": "ga"},
                        {"code": "95", "name": "Sin Plomo 95", "class": "sp95"}
                    ]

        overrides = STATION_PUMP_OVERRIDES.get(int(config_id or 1), {})

        pumps = []
        for i in range(1, num_pumps + 1):
            if i in overrides:
                pumps.append(overrides[i])
            else:
                pumps.append({
                    "id": i,
                    "status": "idle",
                    "statusText": "LIBRE",
                    "fuel": "Gasóleo A / Sin Plomo 95",
                    "amount": 0.00,
                    "liters": 0.00,
                    "price": 1.78
                })

        return {
            "status": "success",
            "station_name": station_name,
            "available_fuels": available_fuels,
            "pumps": pumps
        }

    @http.route('/pos_gas_station/authorize', type='json', auth='user', cors='*')
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

    @http.route('/pos_gas_station/cancel_authorize', type='json', auth='user', cors='*')
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
