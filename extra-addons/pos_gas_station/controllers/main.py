# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
import json
import logging
import time

_logger = logging.getLogger(__name__)

STATION_MAP = {
    2: {
        'name': 'CONTROL DE PISTA - E.S. RODALABOTA (EL CUERVO)',
        'pumps_count': 4,
        'fuels': [
            {'code': 'GA', 'name': 'Gasóleo A', 'class': 'ga'},
            {'code': '95', 'name': 'Sin Plomo 95', 'class': 'sp95'}
        ]
    },
    3: {
        'name': 'CONTROL DE PISTA - E.S. VISTALEGRE (UTRERA)',
        'pumps_count': 4,
        'fuels': [
            {'code': 'GA', 'name': 'Gasóleo A', 'class': 'ga'},
            {'code': '95', 'name': 'Sin Plomo 95', 'class': 'sp95'}
        ]
    },
    5: {
        'name': 'CONTROL DE PISTA - E.S. RONDA NORTE',
        'pumps_count': 8,
        'fuels': [
            {'code': 'GA', 'name': 'Gasóleo A', 'class': 'ga'},
            {'code': '95', 'name': 'Sin Plomo 95', 'class': 'sp95'}
        ]
    },
    6: {
        'name': 'CONTROL DE PISTA - E.S. ATENAS (ÉCIJA)',
        'pumps_count': 4,
        'fuels': [
            {'code': 'GA', 'name': 'Gasóleo A', 'class': 'ga'},
            {'code': '95', 'name': 'Sin Plomo 95', 'class': 'sp95'}
        ]
    },
    7: {
        'name': 'CONTROL DE PISTA - E.S. REPSOL',
        'pumps_count': 8,
        'fuels': [
            {'code': 'GA', 'name': 'Gasóleo A', 'class': 'ga'},
            {'code': '95', 'name': 'Sin Plomo 95', 'class': 'sp95'},
            {'code': 'G+', 'name': 'Gasóleo Plus', 'class': 'gplus'}
        ]
    },
}

STATION_PUMP_OVERRIDES = {}
OVERRIDE_TIMEOUT_SECONDS = 300  # 5 minutos max para sobreescrituras en memoria

class PosGasStationController(http.Controller):

    @http.route('/pos_gas_station/status', type='json', auth='public', methods=['POST'], csrf=False, cors='*')
    def get_pumps_status(self, config_id=None, **kw):
        if not config_id:
            config_id = 7
        try:
            config_id = int(config_id)
        except Exception:
            config_id = 7

        station_info = STATION_MAP.get(config_id)
        if not station_info:
            pos_config = request.env['pos.config'].sudo().browse(config_id)
            name = f'CONTROL DE PISTA - {pos_config.name.upper()}' if pos_config.exists() else 'CONTROL DE PISTA'
            pumps_cnt = 8 if ('ronda norte' in name.lower() or 'repsol' in name.lower()) else 4
            station_info = {
                'name': name,
                'pumps_count': pumps_cnt,
                'fuels': [
                    {'code': 'GA', 'name': 'Gasóleo A', 'class': 'ga'},
                    {'code': '95', 'name': 'Sin Plomo 95', 'class': 'sp95'},
                    {'code': 'G+', 'name': 'Gasóleo Plus', 'class': 'gplus'}
                ]
            }

        param_key = f'pos_gas_station.pumps_state_{config_id}'
        status_raw = request.env['ir.config_parameter'].sudo().get_param(param_key)
        
        pumps = []
        if status_raw:
            try:
                parsed = json.loads(status_raw)
                if isinstance(parsed, dict) and 'pumps' in parsed:
                    pumps = parsed['pumps']
                elif isinstance(parsed, list):
                    pumps = parsed
            except Exception as e:
                _logger.error(f'Error parsing live pumps parameter {param_key}: {e}')

        if not pumps:
            for i in range(1, station_info['pumps_count'] + 1):
                pumps.append({
                    'id': i,
                    'status': 'idle',
                    'statusText': 'LIBRE',
                    'fuel': 'Gasóleo A / Sin Plomo 95',
                    'amount': 0.00,
                    'liters': 0.00,
                    'price': 1.45
                })

        now = time.time()
        overrides = STATION_PUMP_OVERRIDES.get(config_id, {})
        # Limpieza de overrides expirados
        expired_pids = [pid for pid, o in overrides.items() if now - o.get('_timestamp', now) > OVERRIDE_TIMEOUT_SECONDS]
        for pid in expired_pids:
            del overrides[pid]

        for i, pump in enumerate(pumps):
            pid = pump.get('id', i + 1)
            # Si el surtidor real ya reporta fin de repostaje (ready), suministro activo en pista, o se ha bloqueado, anular override de inmediato
            if pump.get('status') in ('ready', 'dispensing') or (pump.get('status') == 'blocked' and now - overrides.get(pid, {}).get('_timestamp', now) > 2.0):
                if pid in overrides:
                    del overrides[pid]
            elif pid in overrides:
                if now - overrides[pid].get('_timestamp', now) > 20:
                    del overrides[pid]
                else:
                    ov = {k: v for k, v in overrides[pid].items() if not k.startswith('_')}
                    pumps[i] = ov

        return {
            'status': 'success',
            'station_name': station_info['name'],
            'available_fuels': station_info['fuels'],
            'pumps': pumps
        }

    @http.route('/pos_gas_station/authorize', type='json', auth='public', methods=['POST'], csrf=False, cors='*')
    def authorize_pump(self, config_id=None, pump_id=None, fuel='GA', amount=0, liters=0, **kw):
        cfg = int(config_id or 7)
        pid = int(pump_id or 1)
        if cfg not in STATION_PUMP_OVERRIDES:
            STATION_PUMP_OVERRIDES[cfg] = {}

        fuel_names = {
            'GA': 'Gasóleo A',
            '95': 'Sin Plomo 95',
            'SP95': 'Sin Plomo 95',
            'GB': 'Gasóleo B',
            'G+': 'Gasóleo Plus'
        }
        fuel_name = fuel_names.get(fuel, 'Gasóleo A')
        amt = float(amount or 0)
        lts = float(liters or 0)

        is_lleno = (amt == 0 or lts >= 999)
        override_data = {
            'id': pid,
            'status': 'atendido' if is_lleno else 'dispensing',
            'statusText': 'LLENO (POSTPAGO)' if is_lleno else f'PREFIJADO {amt:.2f}€',
            'fuel': fuel_name,
            'amount': 0.0 if is_lleno else amt,
            'liters': 0.0 if is_lleno else lts,
            'preset_amount': 0.0 if is_lleno else amt,
            'price': 1.45 if 'Gasóleo A' in fuel_name else 1.55,
            '_timestamp': time.time()
        }
        STATION_PUMP_OVERRIDES[cfg][pid] = override_data

        _logger.info(f'⛽ [AUTORIZACIÓN PISTA] Config {cfg} | Calle {pid} | Combustible {fuel_name} | {amt}€ / {lts}L')

        # Emitir comando para el agente de pista local en la gasolinera
        cmd_key = f'pos_gas_station.pump_command_{cfg}'
        cmd_payload = {
            'action': 'authorize',
            'pump_id': pid,
            'fuel': fuel_name,
            'amount': amt,
            'liters': lts,
            'timestamp': time.time()
        }
        try:
            request.env['ir.config_parameter'].sudo().set_param(cmd_key, json.dumps(cmd_payload))
        except Exception as e:
            _logger.error(f'Error guardando comando {cmd_key}: {e}')

        return {'status': 'authorized', 'pump_id': pid}

    @http.route('/pos_gas_station/cancel_authorize', type='json', auth='public', methods=['POST'], csrf=False, cors='*')
    def cancel_authorize(self, config_id=None, pump_id=None, **kw):
        cfg = int(config_id or 7)
        pid = int(pump_id or 1)
        if cfg in STATION_PUMP_OVERRIDES and pid in STATION_PUMP_OVERRIDES[cfg]:
            del STATION_PUMP_OVERRIDES[cfg][pid]

        _logger.info(f'🛑 [CANCELAR AUTORIZACIÓN] Config {cfg} | Calle {pid}')

        # Reseteo en pumps_state
        param_key = f'pos_gas_station.pumps_state_{cfg}'
        try:
            status_raw = request.env['ir.config_parameter'].sudo().get_param(param_key)
            if status_raw:
                data = json.loads(status_raw)
                pumps = data.get('pumps', []) if isinstance(data, dict) else data
                for p in pumps:
                    if p.get('id') == pid:
                        fallback_status = 'atendido' if data.get('modo_estacion') == 'atendido' else 'blocked'
                        p['status'] = fallback_status
                        p['amount'] = 0.0
                        p['liters'] = 0.0
                        p['statusText'] = 'SIN PREFIJADO' if fallback_status == 'blocked' else 'ATENDIDO'
                        p['updated_at'] = time.time()
                request.env['ir.config_parameter'].sudo().set_param(param_key, json.dumps(data))
        except Exception as e:
            _logger.error(f'Error resetting pump state in cancel_authorize: {e}')

        # Emitir comando de liberación/bloqueo al agente de pista local
        cmd_key = f'pos_gas_station.pump_command_{cfg}'
        cmd_payload = {
            'action': 'clear_pump',
            'pump_id': pid,
            'timestamp': time.time()
        }
        try:
            request.env['ir.config_parameter'].sudo().set_param(cmd_key, json.dumps(cmd_payload))
        except Exception as e:
            _logger.error(f'Error guardando comando {cmd_key}: {e}')

        return {'status': 'cancelled', 'pump_id': pid}

    @http.route('/pos_gas_station/clear_pump', type='json', auth='public', methods=['POST'], csrf=False, cors='*')
    def clear_pump(self, config_id=None, pump_id=None, **kw):
        cfg = int(config_id or 7)
        pid = int(pump_id or 1)
        if cfg in STATION_PUMP_OVERRIDES and pid in STATION_PUMP_OVERRIDES[cfg]:
            del STATION_PUMP_OVERRIDES[cfg][pid]

        param_key = f'pos_gas_station.pumps_state_{cfg}'
        try:
            status_raw = request.env['ir.config_parameter'].sudo().get_param(param_key)
            if status_raw:
                parsed = json.loads(status_raw)
                p_list = parsed.get('pumps', []) if isinstance(parsed, dict) else parsed
                
                # Determinar si el modo predominante de la pista es bloqueado (prepago) o libre (atendido)
                is_mostly_blocked = sum(1 for p in p_list if p.get('status') in ('blocked', 'prepago')) >= (len(p_list) / 2)
                fallback_status = 'blocked' if is_mostly_blocked else 'idle'
                fallback_text = 'SIN PREFIJADO' if is_mostly_blocked else 'ATENDIDO'

                for p in p_list:
                    if p.get('id') == pid:
                        p['status'] = fallback_status
                        p['statusText'] = fallback_text
                        p['amount'] = 0.0
                        p['liters'] = 0.0
                        p['preset_amount'] = 0.0
                        p['has_prepay'] = False
                        
                if isinstance(parsed, dict):
                    parsed['pumps'] = p_list
                    request.env['ir.config_parameter'].sudo().set_param(param_key, json.dumps(parsed))
                else:
                    request.env['ir.config_parameter'].sudo().set_param(param_key, json.dumps(p_list))
        except Exception as e:
            _logger.error(f'Error resetting pump in {param_key}: {e}')

        # Emitir orden de liberación al hardware de pista local
        cmd_key = f'pos_gas_station.pump_command_{cfg}'
        cmd_payload = {
            'action': 'clear_pump',
            'pump_id': pid,
            'timestamp': time.time()
        }
        try:
            request.env['ir.config_parameter'].sudo().set_param(cmd_key, json.dumps(cmd_payload))
        except Exception as e:
            _logger.error(f'Error guardando comando {cmd_key}: {e}')

        return {'status': 'cleared', 'pump_id': pid}

    @http.route('/pos_gas_station/set_track_mode', type='json', auth='public', methods=['POST'], csrf=False, cors='*')
    def set_track_mode(self, config_id=None, mode='prepago', pump_id=None, **kw):
        cfg = int(config_id or 7)
        pid = int(pump_id) if pump_id else None
        target_status = 'atendido' if mode == 'atendido' else 'blocked'
        target_text = 'LIBRE' if mode == 'atendido' else 'PREPAGO'

        # 1. Actualizar estado inmediatamente en ir.config_parameter
        param_key = f'pos_gas_station.pumps_state_{cfg}'
        try:
            status_raw = request.env['ir.config_parameter'].sudo().get_param(param_key)
            if status_raw:
                parsed = json.loads(status_raw)
                p_list = parsed.get('pumps', []) if isinstance(parsed, dict) else parsed
                for p in p_list:
                    if pid is None or p.get('id') == pid:
                        if p.get('status') in ('idle', 'blocked', 'atendido', 'postpago', 'prepago'):
                            p['status'] = target_status
                            p['statusText'] = target_text
                if isinstance(parsed, dict):
                    parsed['pumps'] = p_list
                    request.env['ir.config_parameter'].sudo().set_param(param_key, json.dumps(parsed))
                else:
                    request.env['ir.config_parameter'].sudo().set_param(param_key, json.dumps(p_list))
        except Exception as e:
            _logger.error(f'Error actualizando estado en {param_key}: {e}')

        # 2. Emitir comando de hardware para el agente de pista
        cmd_key = f'pos_gas_station.pump_command_{cfg}'
        cmd_payload = {
            'action': 'set_pump_mode' if pid else 'set_track_mode',
            'mode': mode,
            'timestamp': time.time()
        }
        if pid:
            cmd_payload['pump_id'] = pid
        try:
            request.env['ir.config_parameter'].sudo().set_param(cmd_key, json.dumps(cmd_payload))
        except Exception as e:
            _logger.error(f'Error emitiendo comando {cmd_key}: {e}')

        _logger.info(f'⛽ [MODO PISTA] Config {cfg} | Modo {mode} | Calle {pid or "TODAS"}')
        return {'status': 'success', 'mode': mode, 'pump_id': pid}

    @http.route('/pos_gas_station/set_cashier_name', type='json', auth='user', methods=['POST'], csrf=False)
    def set_cashier_name(self, name=None, user_id=None, **kw):
        if name and name.strip():
            target_user = request.env.user
            if user_id:
                try:
                    u = request.env['res.users'].sudo().browse(int(user_id))
                    if u.exists():
                        target_user = u
                except Exception:
                    pass
            target_user.sudo().write({'name': name.strip()})
            if target_user.partner_id:
                target_user.partner_id.sudo().write({'name': name.strip()})
            return {'status': 'success', 'name': name.strip()}
        return {'status': 'error'}

    # ==================== MATRIZ VISUAL DE ROLES Y PERMISOS ====================
    @http.route('/utrecar/permission_matrix/data', type='json', auth='user', methods=['POST'], csrf=False)
    def get_permission_matrix_data(self):
        env = request.env
        roles = env['utrecar.role'].search([])
        categories = env['utrecar.permission.category'].search([])
        permissions = env['utrecar.permission'].search([])
        users = env['res.users'].search([('active', '=', True)], order='name')

        roles_data = [{
            'id': r.id,
            'name': r.name,
            'code': r.code,
            'color': r.color,
            'user_count': r.user_count,
            'users': [{'id': u.id, 'name': u.name, 'login': u.login} for u in r.user_ids]
        } for r in roles]

        cat_dict = {}
        for c in categories:
            cat_dict[c.id] = {
                'id': c.id,
                'name': c.name,
                'code': c.code,
                'sequence': c.sequence,
                'permissions': []
            }

        matrix_state = {} # perm_id -> {role_id -> bool}

        for p in permissions:
            cat_id = p.category_id.id
            if cat_id not in cat_dict:
                cat_dict[cat_id] = {
                    'id': cat_id,
                    'name': p.category_id.name,
                    'code': p.category_id.code,
                    'sequence': p.category_sequence,
                    'permissions': []
                }
            cat_dict[cat_id]['permissions'].append({
                'id': p.id,
                'name': p.name,
                'code': p.code,
                'sequence': p.sequence
            })

            role_ids = set(p.role_ids.ids)
            matrix_state[p.id] = {r.id: (r.id in role_ids) for r in roles}

        sorted_categories = sorted(cat_dict.values(), key=lambda x: x['sequence'])
        for cat in sorted_categories:
            cat['permissions'] = sorted(cat['permissions'], key=lambda x: x['sequence'])

        users_data = [{
            'id': u.id,
            'name': u.name,
            'login': u.login,
            'role_id': u.utrecar_role_id.id if u.utrecar_role_id else False,
            'role_name': u.utrecar_role_id.name if u.utrecar_role_id else 'Sin Rol'
        } for u in users]

        return {
            'status': 'success',
            'roles': roles_data,
            'categories': sorted_categories,
            'matrix': matrix_state,
            'users': users_data
        }

    @http.route('/utrecar/permission_matrix/toggle', type='json', auth='user', methods=['POST'], csrf=False)
    def toggle_permission_matrix(self, role_id, permission_id, granted):
        env = request.env
        role = env['utrecar.role'].browse(int(role_id))
        permission = env['utrecar.permission'].browse(int(permission_id))
        if not role.exists() or not permission.exists():
            return {'status': 'error', 'message': 'Rol o permiso no encontrado'}

        if granted:
            role.write({'permission_ids': [(4, permission.id)]})
        else:
            role.write({'permission_ids': [(3, permission.id)]})

        return {'status': 'success', 'granted': bool(granted)}

    @http.route('/utrecar/permission_matrix/assign_user', type='json', auth='user', methods=['POST'], csrf=False)
    def assign_user_role(self, user_id, role_id):
        env = request.env
        user = env['res.users'].browse(int(user_id))
        if not user.exists():
            return {'status': 'error', 'message': 'Usuario no encontrado'}

        r_id = int(role_id) if role_id else False
        user.write({'utrecar_role_id': r_id})
        return {'status': 'success'}
