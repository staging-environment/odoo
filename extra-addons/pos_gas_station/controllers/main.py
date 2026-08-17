# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
import json

class PosGasStationController(http.Controller):
    @http.route('/pos_gas_station/status', type='json', auth='user', cors='*')
    def get_pumps_status(self):
        param = request.env['ir.config_parameter'].sudo().get_param('pos_gas_station.pumps_state')
        if param:
            try:
                return json.loads(param)
            except Exception:
                pass
        return {
            'pumps': [
                {'id': 1, 'name': 'Calle 1', 'fuel': 'Gasóleo A', 'amount': 0.0, 'liters': 0.0, 'status': 'idle', 'statusText': 'LIBRE', 'product_id': 51, 'price': 1.769},
                {'id': 2, 'name': 'Calle 2', 'fuel': 'Gasóleo A', 'amount': 0.0, 'liters': 0.0, 'status': 'idle', 'statusText': 'LIBRE', 'product_id': 51, 'price': 1.769},
                {'id': 3, 'name': 'Calle 3', 'fuel': 'Sin Plomo 95', 'amount': 0.0, 'liters': 0.0, 'status': 'idle', 'statusText': 'LIBRE', 'product_id': 52, 'price': 1.655},
                {'id': 4, 'name': 'Calle 4', 'fuel': 'Gasóleo A', 'amount': 0.0, 'liters': 0.0, 'status': 'idle', 'statusText': 'LIBRE', 'product_id': 51, 'price': 1.769},
            ]
        }
