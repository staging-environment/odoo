# -*- coding: utf-8 -*-
from odoo import http
from odoo.exceptions import UserError
from odoo.http import request
import json
import logging
import time
import pytz

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
            'status': 'dispensing',
            'statusText': 'LLENO (POSTPAGO)' if is_lleno else f'PREFIJADO {amt:.2f}€',
            'fuel': fuel_name,
            'amount': 0.0 if is_lleno else amt,
            'liters': 0.0 if is_lleno else lts,
            'preset_amount': 0.0 if is_lleno else amt,
            'is_lleno': is_lleno,
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
            'action': 'set_pump_mode' if pid else 'set_global_mode',
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
        env['utrecar.role'].auto_link_admin_users()
        users = env['res.users'].search([('active', '=', True)], order='name')
        companies = env['res.company'].search_read([], ['id', 'name'])
        stations = env['pos.config'].search_read([], ['id', 'name', 'company_id'])

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
            'company_id': u.company_id.id if u.company_id else False,
            'company_name': u.company_id.name if u.company_id else '',
            'role_id': u.utrecar_role_id.id if u.utrecar_role_id else False,
            'role_name': u.utrecar_role_id.name if u.utrecar_role_id else 'Sin Rol',
            'pos_config_ids': u.pos_config_ids.ids if hasattr(u, 'pos_config_ids') else [],
            'pos_config_names': [p.name for p in u.pos_config_ids] if hasattr(u, 'pos_config_ids') else []
        } for u in users]

        return {
            'status': 'success',
            'roles': roles_data,
            'categories': sorted_categories,
            'matrix': matrix_state,
            'users': users_data,
            'companies': companies,
            'stations': stations
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
    def assign_user_role(self, user_id, role_id=None, pos_config_ids=None):
        env = request.env
        user = env['res.users'].browse(int(user_id))
        if not user.exists():
            return {'status': 'error', 'message': 'Usuario no encontrado'}

        vals = {}
        if role_id is not None:
            vals['utrecar_role_id'] = int(role_id) if role_id else False
        if pos_config_ids is not None:
            vals['pos_config_ids'] = [(6, 0, [int(pid) for pid in pos_config_ids])]
        if vals:
            user.write(vals)
        return {'status': 'success'}


    # ==================== DASHBOARD MULTI-EMPRESA / GESTIÓN DE GASOLINERAS ====================
    @http.route('/pos_gas_station/dashboard_data', type='json', auth='user', methods=['POST'], csrf=False)
    def get_gas_station_dashboard_data(self):
        env = request.env
        user = env.user
        is_manager = user.has_group('point_of_sale.group_pos_manager') or user._is_admin()

        companies = user.company_ids
        if not companies:
            companies = env['res.company'].search([])

        companies_data = []
        total_stations = 0
        total_open_sessions = 0

        for c in companies:
            domain = [('company_id', '=', c.id)]
            all_stations = env['pos.config'].sudo().search(domain)

            accessible_stations = []
            for st in all_stations:
                has_access = is_manager
                if not has_access:
                    has_access = (user.id in st.allowed_user_ids.ids) or (st.id in user.pos_config_ids.ids)

                if not has_access:
                    continue

                active_session = env['pos.session'].sudo().search([
                    ('config_id', '=', st.id),
                    ('state', 'in', ['opened', 'opening_control'])
                ], limit=1)

                if active_session:
                    total_open_sessions += 1

                pumps_cnt = 8 if ('ronda norte' in st.name.lower() or 'repsol' in st.name.lower()) else 4

                fuels = [
                    {'code': 'GA', 'name': 'Gasóleo A'},
                    {'code': '95', 'name': 'Sin Plomo 95'}
                ]
                if 'repsol' in st.name.lower():
                    fuels.append({'code': 'G+', 'name': 'Gasóleo Plus'})

                accessible_stations.append({
                    'id': st.id,
                    'name': st.name,
                    'company_id': c.id,
                    'company_name': c.name,
                    'pumps_count': pumps_cnt,
                    'has_active_session': bool(active_session),
                    'session_state': active_session.state if active_session else 'closed',
                    'session_name': active_session.name if active_session else None,
                    'session_user': active_session.user_id.name if active_session else None,
                    'fuels': fuels,
                })

            total_stations += len(accessible_stations)
            has_logo = bool(c.logo)

            companies_data.append({
                'id': c.id,
                'name': c.name,
                'vat': c.vat or '',
                'city': c.city or '',
                'street': c.street or '',
                'phone': c.phone or '',
                'has_logo': has_logo,
                'logo_url': f'/web/image?model=res.company&id={c.id}&field=logo' if has_logo else None,
                'stations': accessible_stations,
                'stations_count': len(accessible_stations)
            })

        return {
            'status': 'success',
            'is_manager': is_manager,
            'user_name': user.name,
            'companies': companies_data,
            'stats': {
                'total_companies': len(companies_data),
                'total_stations': total_stations,
                'total_open_sessions': total_open_sessions
            }
        }

    @http.route('/pos_gas_station/open_station', type='json', auth='user', methods=['POST'], csrf=False)
    def open_gas_station(self, config_id):
        try:
            cfg = request.env['pos.config'].sudo().browse(int(config_id))
            if not cfg.exists():
                return {'status': 'error', 'message': 'Punto de venta no encontrado'}

            comp_id = cfg.company_id.id
            action = cfg.with_user(request.env.user).with_company(cfg.company_id).open_ui()
            session = cfg.current_session_id
            if session and session.state == 'opening_control':
                session.action_pos_session_open()
                if session.state == 'opening_control':
                    session.write({'state': 'opened'})
            url = action.get('url', f'/pos/ui?config_id={cfg.id}')
            if 'cids=' not in url:
                sep = '&' if '?' in url else '?'
                url = f"{url}{sep}cids={comp_id}"

            return {
                'status': 'success',
                'url': url,
                'action': action,
            }
        except Exception as e:
            _logger.exception("Error in /pos_gas_station/open_station: %s", e)
            return {'status': 'error', 'message': str(e)}

    # ==================== GESTIÓN DE PEDIDOS DEL TURNO ACTIVO ====================
    @http.route('/pos_gas_station/get_shift_orders', type='json', auth='user', methods=['POST'], csrf=False)
    def get_shift_orders(self, session_id=None, config_id=None):
        try:
            env = request.env
            session = None
            if session_id:
                session = env['pos.session'].sudo().browse(int(session_id))
            elif config_id:
                cfg = env['pos.config'].sudo().browse(int(config_id))
                session = cfg.current_session_id

            if not session or not session.exists():
                return {'status': 'error', 'message': 'Sesión no encontrada'}

            # Find previous session for quick switching if needed
            prev_session = env['pos.session'].sudo().search([
                ('config_id', '=', session.config_id.id),
                ('id', '<', session.id),
                ('state', '=', 'closed')
            ], order='id desc', limit=1)

            orders = env['pos.order'].sudo().search([
                ('session_id', '=', session.id),
                ('state', 'in', ['paid', 'done', 'invoiced'])
            ], order='date_order desc, id desc')

            payments = env['pos.payment'].sudo().search([('session_id', '=', session.id)])
            total_sales = round(sum(o.amount_total for o in orders), 2)

            total_cash = 0.0
            total_bank = 0.0
            for p in payments:
                method_name = p.payment_method_id.name.lower() if p.payment_method_id else ''
                is_cash = getattr(p.payment_method_id, 'is_cash_count', False) or 'efectivo' in method_name
                if is_cash:
                    total_cash += p.amount
                else:
                    total_bank += p.amount

            total_cash = round(total_cash, 2)
            total_bank = round(total_bank, 2)

            user_tz = pytz.timezone(env.user.tz or 'Europe/Madrid')

            orders_list = []
            for o in orders:
                if o.date_order:
                    try:
                        local_dt = pytz.utc.localize(o.date_order).astimezone(user_tz)
                        date_str = local_dt.strftime('%d/%m/%Y %H:%M:%S')
                    except Exception:
                        date_str = str(o.date_order)
                else:
                    date_str = ''

                lines_data = []
                for l in o.lines:
                    taxes_str = ', '.join(l.tax_ids_after_fiscal_position.mapped('name')) if l.tax_ids_after_fiscal_position else ''
                    lot_str = l.pack_lot_ids[0].lot_name if l.pack_lot_ids else ''
                    lines_data.append({
                        'id': l.id,
                        'product_name': l.product_id.display_name or l.product_id.name or 'Producto',
                        'lot_name': lot_str,
                        'qty': round(l.qty, 3),
                        'qty_str': f"{l.qty:.3f}",
                        'price_unit': round(l.price_unit, 4),
                        'price_unit_str': f"{l.price_unit:.2f}",
                        'discount': round(l.discount, 2),
                        'discount_str': f"{l.discount:.2f}",
                        'taxes': taxes_str,
                        'price_subtotal': round(l.price_subtotal, 2),
                        'price_subtotal_str': f"{l.price_subtotal:.2f}",
                        'price_subtotal_incl': round(l.price_subtotal_incl, 2),
                        'price_subtotal_incl_str': f"{l.price_subtotal_incl:.2f}",
                    })

                payments_data = []
                for p in o.payment_ids:
                    p_date_str = ''
                    if p.payment_date:
                        try:
                            p_dt = pytz.utc.localize(p.payment_date).astimezone(user_tz)
                            p_date_str = p_dt.strftime('%d/%m/%Y %H:%M:%S')
                        except Exception:
                            p_date_str = str(p.payment_date)
                    payments_data.append({
                        'id': p.id,
                        'name': p.payment_method_id.name if p.payment_method_id else 'Pago',
                        'amount': round(p.amount, 2),
                        'amount_str': f"{p.amount:.2f}",
                        'payment_date': p_date_str,
                    })

                is_inv = bool(o.account_move)
                inv_url = f'/report/pdf/account.report_invoice_with_payments/{o.account_move.id}' if is_inv else False

                orders_list.append({
                    'id': o.id,
                    'name': o.name,
                    'pos_reference': o.pos_reference or o.name,
                    'date_order': date_str,
                    'session_id': session.id,
                    'session_name': session.name,
                    'user_name': o.user_id.name or 'Cajero',
                    'partner_id': o.partner_id.id if o.partner_id else False,
                    'partner_name': o.partner_id.name if o.partner_id else False,
                    'partner_vat': o.partner_id.vat if o.partner_id else '',
                    'partner_street': o.partner_id.street or '',
                    'partner_city': o.partner_id.city or '',
                    'partner_zip': o.partner_id.zip or '',
                    'partner_phone': o.partner_id.phone or '',
                    'partner_email': o.partner_id.email or '',
                    'fiscal_position': o.fiscal_position_id.name if o.fiscal_position_id else 'Posición fiscal ordinaria',
                    'state': 'invoiced' if is_inv else o.state,
                    'is_invoiced': is_inv,
                    'account_move_id': o.account_move.id if is_inv else False,
                    'account_move_name': o.account_move.name if is_inv else '',
                    'invoice_url': inv_url,
                    'amount_total': round(o.amount_total, 2),
                    'amount_total_str': f"{o.amount_total:.2f}",
                    'amount_tax': round(o.amount_tax, 2),
                    'amount_tax_str': f"{o.amount_tax:.2f}",
                    'amount_paid': round(o.amount_paid, 2),
                    'amount_paid_str': f"{o.amount_paid:.2f}",
                    'amount_return': round(o.amount_return, 2),
                    'margin': round(getattr(o, 'margin', 0.0), 2),
                    'margin_str': f"{getattr(o, 'margin', 0.0):.2f}",
                    'lines': lines_data,
                    'payments': payments_data,
                    'company': {
                        'name': o.company_id.name,
                        'vat': o.company_id.vat or '',
                        'street': o.company_id.street or '',
                        'city': o.company_id.city or '',
                        'phone': o.company_id.phone or '',
                    }
                })

            return {
                'status': 'success',
                'session_id': session.id,
                'session_name': session.name,
                'session_state': session.state,
                'prev_session_id': prev_session.id if prev_session else False,
                'prev_session_name': prev_session.name if prev_session else False,
                'summary': {
                    'total_sales': total_sales,
                    'total_sales_str': f"{total_sales:.2f}",
                    'total_cash': total_cash,
                    'total_cash_str': f"{total_cash:.2f}",
                    'total_bank': total_bank,
                    'total_bank_str': f"{total_bank:.2f}",
                    'orders_count': len(orders_list)
                },
                'orders': orders_list
            }
        except Exception as e:
            _logger.exception("Error in /pos_gas_station/get_shift_orders: %s", e)
            return {'status': 'error', 'message': str(e)}

    @http.route('/pos_gas_station/invoice_order', type='json', auth='user', methods=['POST'], csrf=False)
    def invoice_order(self, order_id, partner_id=None, partner_data=None):
        try:
            env = request.env
            order = env['pos.order'].sudo().browse(int(order_id))
            if not order.exists():
                return {'status': 'error', 'message': 'Pedido no encontrado'}

            if order.account_move:
                return {
                    'status': 'success',
                    'already_invoiced': True,
                    'account_move_id': order.account_move.id,
                    'account_move_name': order.account_move.name,
                    'invoice_url': f'/report/pdf/account.report_invoice_with_payments/{order.account_move.id}'
                }

            partner = None
            if partner_id:
                p = env['res.partner'].sudo().browse(int(partner_id))
                if p.exists():
                    partner = p
            elif partner_data and partner_data.get('vat'):
                vat = str(partner_data['vat']).strip().upper()
                name = str(partner_data.get('name') or vat).strip()
                partner = env['res.partner'].sudo().search([('vat', '=', vat)], limit=1)
                if not partner:
                    partner = env['res.partner'].sudo().create({
                        'name': name,
                        'vat': vat,
                        'street': partner_data.get('street', '').strip(),
                        'city': partner_data.get('city', '').strip(),
                        'zip': partner_data.get('zip', '').strip(),
                        'email': partner_data.get('email', '').strip(),
                        'phone': partner_data.get('phone', '').strip(),
                        'company_id': order.company_id.id,
                    })

            if partner:
                order.write({'partner_id': partner.id})

            if not order.partner_id:
                return {'status': 'error', 'message': 'Se requiere un cliente con NIF/CIF para emitir la factura.'}

            # Generate invoice
            order.action_pos_order_invoice()

            if not order.account_move:
                return {'status': 'error', 'message': 'No se pudo generar el asiento contable de factura.'}

            return {
                'status': 'success',
                'account_move_id': order.account_move.id,
                'account_move_name': order.account_move.name,
                'invoice_url': f'/report/pdf/account.report_invoice_with_payments/{order.account_move.id}'
            }
        except Exception as e:
            _logger.exception("Error in /pos_gas_station/invoice_order: %s", e)
            return {'status': 'error', 'message': str(e)}

    @http.route('/pos_gas_station/search_partners', type='json', auth='user', methods=['POST'], csrf=False)
    def search_partners(self, query):
        try:
            env = request.env
            q = (query or '').strip()
            if not q or len(q) < 2:
                return {'status': 'success', 'partners': []}
            domain = ['|', ('name', 'ilike', q), ('vat', 'ilike', q)]
            partners = env['res.partner'].sudo().search(domain, limit=12)
            results = []
            for p in partners:
                results.append({
                    'id': p.id,
                    'name': p.name,
                    'vat': p.vat or '',
                    'street': p.street or '',
                    'city': p.city or '',
                    'zip': p.zip or '',
                    'phone': p.phone or '',
                    'email': p.email or ''
                })
            return {'status': 'success', 'partners': results}
        except Exception as e:
            _logger.exception("Error in /pos_gas_station/search_partners: %s", e)
            return {'status': 'error', 'message': str(e)}


    @http.route('/pos_gas_station/delete_station', type='json', auth='user', methods=['POST'], csrf=False)
    def delete_station(self, config_id):
        try:
            env = request.env
            config = env['pos.config'].sudo().browse(int(config_id))
            if not config.exists():
                return {'status': 'error', 'message': 'La estación no existe.'}

            name = config.name
            # config.unlink() ejecuta la validación exhaustiva de trazabilidad e integridad del modelo
            config.unlink()
            return {'status': 'success', 'message': f'Estación "{name}" eliminada correctamente.'}
        except UserError as ue:
            return {'status': 'error', 'message': ue.args[0] if ue.args else str(ue)}
        except Exception as e:
            _logger.exception("Error in /pos_gas_station/delete_station: %s", e)
            return {'status': 'error', 'message': str(e)}

    @http.route('/pos_gas_station/delete_company', type='json', auth='user', methods=['POST'], csrf=False)
    def delete_company(self, company_id):
        try:
            env = request.env
            comp = env['res.company'].sudo().browse(int(company_id))
            if not comp.exists():
                return {'status': 'error', 'message': 'La empresa no existe.'}

            stations_count = env['pos.config'].sudo().search_count([('company_id', '=', comp.id)])
            if stations_count > 0:
                return {
                    'status': 'error',
                    'message': f'No se puede eliminar la empresa "{comp.name}" porque contiene {stations_count} estación(es) asociada(s). Elimine primero las estaciones.'
                }

            orders_count = env['pos.order'].sudo().search_count([('company_id', '=', comp.id)])
            if orders_count > 0:
                return {
                    'status': 'error',
                    'message': f'No se puede eliminar la empresa "{comp.name}" porque contiene {orders_count} tickets de venta asociados.'
                }

            moves_count = env['account.move'].sudo().search_count([('company_id', '=', comp.id)])
            if moves_count > 0:
                return {
                    'status': 'error',
                    'message': f'No se puede eliminar la empresa "{comp.name}" porque contiene {moves_count} asientos o facturas contables.'
                }

            name = comp.name
            comp.unlink()
            return {'status': 'success', 'message': f'Empresa "{name}" eliminada correctamente.'}
        except Exception as e:
            _logger.exception("Error in /pos_gas_station/delete_company: %s", e)
            return {'status': 'error', 'message': str(e)}
