# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
import json
import logging

_logger = logging.getLogger(__name__)

class PosGasStationController(http.Controller):
    @http.route('/pos_gas_station/status', type='json', auth='public', cors='*')
    def get_pumps_status(self, **kwargs):
        config_id = kwargs.get('config_id')
        if not config_id and hasattr(request, 'params'):
            config_id = request.params.get('config_id')
            
        if not config_id:
            config_id = 2
            
        try:
            config_id = int(config_id)
        except Exception:
            config_id = 2

        param_name = f'pos_gas_station.pumps_state_{config_id}'
        param = request.env['ir.config_parameter'].sudo().get_param(param_name)
        
        if not param:
            param = request.env['ir.config_parameter'].sudo().get_param('pos_gas_station.pumps_state')
            
        if param:
            try:
                return json.loads(param)
            except Exception as e:
                _logger.error("Error decodificando estado de surtidores: %s", e)
                
        return {
            'station_name': f'CONTROL DE PISTA (POS {config_id})',
            'pumps': []
        }
