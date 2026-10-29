# -*- coding: utf-8 -*-
from odoo import http, _
from odoo.http import request
from odoo.addons.web.controllers.home import Home
from odoo.addons.point_of_sale.controllers.main import PosController
from odoo.service import security
import logging

_logger = logging.getLogger(__name__)


class UtrecarPosController(PosController):

    @http.route(['/pos/web', '/pos/ui'], type='http', auth='user')
    def pos_web(self, config_id=False, **k):
        """Interpreta la entrada al TPV: si no hay turno abierto en la estación, redirige a la selección flotante de empleado."""
        PosConfig = request.env['pos.config'].sudo()
        config = None
        if config_id:
            try:
                config = PosConfig.browse(int(config_id))
                if not config.exists():
                    config = None
            except Exception:
                config = None

        if not config:
            forwarded_for = request.httprequest.headers.get('X-Forwarded-For')
            ip = forwarded_for.split(',')[0].strip() if forwarded_for else (request.httprequest.remote_addr or '').strip()
            config = PosConfig.get_station_by_vpn_ip(ip)

        if config:
            # Comprobar si hay una sesión activa abierta en esta estación
            active_session = request.env['pos.session'].sudo().search([
                ('config_id', '=', config.id),
                ('state', '=', 'opened')
            ], limit=1)

            # Si NO hay sesión abierta (turno cerrado o pendiente de apertura) o se solicita explícitamente select_employee:
            if not active_session or k.get('select_employee'):
                return request.redirect(f'/pos_gas_station/select_employee?station_id={config.id}')

        return super(UtrecarPosController, self).pos_web(config_id=config_id, **k)


class UtrecarLogin(Home):

    def _get_client_ip(self):
        forwarded_for = request.httprequest.headers.get('X-Forwarded-For')
        if forwarded_for:
            return forwarded_for.split(',')[0].strip()
        return (request.httprequest.remote_addr or '').strip()

    @http.route('/', type='http', auth="none")
    def index(self, s_action=None, db=None, **kw):
        """Redirige raíz: si es IP de estación va directo al TPV si el turno está abierto, o a la selección de empleado."""
        ip = self._get_client_ip()
        station = request.env['pos.config'].sudo().get_station_by_vpn_ip(ip)
        if station and request.params.get('admin') != '1':
            active_session = request.env['pos.session'].sudo().search([
                ('config_id', '=', station.id),
                ('state', '=', 'opened')
            ], limit=1)
            if active_session:
                return request.redirect(f'/pos/ui?config_id={station.id}')
            return request.redirect(f'/pos_gas_station/select_employee?station_id={station.id}')
        return super(UtrecarLogin, self).index(s_action=s_action, db=db, **kw)

    @http.route('/web', type='http', auth="none")
    def web_client(self, s_action=None, **kw):
        """Control de acceso a /web: empleados desde IP de estación tienen acceso exclusivo al TPV o a abrir turno."""
        ip = self._get_client_ip()
        station = request.env['pos.config'].sudo().get_station_by_vpn_ip(ip)
        if station and request.params.get('admin') != '1':
            if request.session.uid:
                user = request.env['res.users'].sudo().browse(request.session.uid)
                if not user._is_admin():
                    active_session = request.env['pos.session'].sudo().search([
                        ('config_id', '=', station.id),
                        ('state', '=', 'opened')
                    ], limit=1)
                    if active_session:
                        return request.redirect(f'/pos/ui?config_id={station.id}')
                    return request.redirect(f'/pos_gas_station/select_employee?station_id={station.id}')
            else:
                return request.redirect(f'/pos_gas_station/select_employee?station_id={station.id}')
        return super(UtrecarLogin, self).web_client(s_action=s_action, **kw)

    @http.route('/web/login', type='http', auth="none", sitemap=False)
    def web_login(self, redirect=None, **kw):
        ip = self._get_client_ip()
        PosConfig = request.env['pos.config'].sudo()
        config_id = request.params.get('config_id')
        station = None
        if config_id:
            try:
                station = PosConfig.browse(int(config_id))
                if not station.exists():
                    station = None
            except Exception:
                station = None
        if not station:
            station = PosConfig.get_station_by_vpn_ip(ip)

        # ---------------------------------------------------------------------
        # CASO 1: LA IP PERTENECE A UNA ESTACIÓN DE SERVICIO (O SE ESPECIFICÓ CONFIG_ID)
        # El empleado accede directamente al TPV o al selector de empleado para abrir turno.
        # ---------------------------------------------------------------------
        if station:
            if request.params.get('admin') == '1':
                _logger.info("IP de estación %s solicita acceso manual como Administrador", ip)
                admin_user = request.env['res.users'].sudo().search([('id', '=', 2), ('active', '=', True)], limit=1)
                if not admin_user:
                    admin_user = request.env.ref('base.user_admin', raise_if_not_found=False)
                if admin_user:
                    request.session.uid = admin_user.id
                    request.session.login = admin_user.login
                    request.session.session_token = security.compute_session_token(request.session, request.env)
                    request.session.rotate = True
                    return request.redirect(self._login_redirect(admin_user.id, redirect=redirect))

            active_session = request.env['pos.session'].sudo().search([
                ('config_id', '=', station.id),
                ('state', '=', 'opened')
            ], limit=1)

            if active_session and not request.params.get('select_employee'):
                return request.redirect(f'/pos/ui?config_id={station.id}')

            return request.redirect(f'/pos_gas_station/select_employee?station_id={station.id}')

        # ---------------------------------------------------------------------
        # CASO 2: NO ES IP DE ESTACIÓN (ACCESO GENERAL PROTEGIDO POR VPN)
        # Entra directamente autenticado con el usuario de Administrador a /web
        # ---------------------------------------------------------------------
        if request.session.uid:
            return request.redirect(redirect or '/web')

        admin_user = request.env['res.users'].sudo().search([
            ('id', '=', 2),
            ('active', '=', True)
        ], limit=1)
        if not admin_user:
            admin_user = request.env.ref('base.user_admin', raise_if_not_found=False)

        if admin_user:
            request.session.uid = admin_user.id
            request.session.login = admin_user.login
            request.session.session_token = security.compute_session_token(request.session, request.env)
            request.session.rotate = True
            _logger.info("Auto-login directo como Administrador (%s) desde IP VPN: %s", admin_user.login, ip)
            return request.redirect(self._login_redirect(admin_user.id, redirect=redirect))

        return super(UtrecarLogin, self).web_login(redirect=redirect, **kw)

    @http.route(['/pos_gas_station/select_employee'], type='http', auth="none", sitemap=False)
    def select_station_employee(self, station_id=None, **kw):
        """Muestra la ventana flotante táctil para seleccionar el empleado de admin-platform y abrir turno."""
        ip = self._get_client_ip()
        PosConfig = request.env['pos.config'].sudo()
        station = None
        if station_id:
            try:
                station = PosConfig.browse(int(station_id))
                if not station.exists():
                    station = None
            except Exception:
                station = None
        if not station:
            station = PosConfig.get_station_by_vpn_ip(ip)

        if not station:
            return request.redirect('/web')

        employees = station.get_admin_platform_employees()
        return request.render('pos_gas_station.station_employee_select_modal', {
            'station': station,
            'employees': employees,
            'client_ip': station.vpn_ip or ip,
            'redirect': f'/pos/ui?config_id={station.id}',
            'csrf_token': request.csrf_token(),
        })

    @http.route('/pos_gas_station/station_login', type='http', auth='none', methods=['POST', 'GET'], csrf=False)
    def station_login(self, station_id=None, employee_id=None, redirect=None, **kw):
        """Procesa la selección de empleado en la ventana flotante, autentica y abre el turno hacia el TPV."""
        try:
            if not station_id or not employee_id:
                return request.redirect('/web')

            PosConfig = request.env['pos.config'].sudo()
            station = PosConfig.browse(int(station_id))
            if not station.exists():
                return request.redirect('/web')

            employees = station.get_admin_platform_employees()
            target_emp = None
            for e in employees:
                if str(e['id']) == str(employee_id):
                    target_emp = e
                    break

            if not target_emp:
                _logger.warning("Empleado ID %s no encontrado para estación %s", employee_id, station_id)
                return request.redirect(f'/pos_gas_station/select_employee?station_id={station.id}')

            user = station.sync_or_get_odoo_user_for_employee(target_emp)

            # Autenticar la sesión en Odoo
            request.session.uid = user.id
            request.session.login = user.login
            request.session.session_token = security.compute_session_token(request.session, request.env)
            request.session.rotate = True

            # Abrir o activar el turno del TPV
            station.open_shift_for_user(user)

            dest_url = f'/pos/ui?config_id={station.id}'
            _logger.info("Empleado %s (ID %s) autenticado con éxito en %s. Turno listo -> %s", user.name, user.id, station.name, dest_url)
            return request.redirect(dest_url)

        except Exception as e:
            _logger.exception("Error en /pos_gas_station/station_login: %s", e)
            return request.redirect('/web')

    @http.route('/pos_gas_station/switch_cashier', type='http', auth='user', methods=['GET'], csrf=False)
    def switch_cashier(self, config_id=None, **kw):
        """Permite cambiar de cajero o reabrir el selector de empleados de la estación."""
        request.session.logout()
        target = '/pos_gas_station/select_employee'
        if config_id:
            target += f'?station_id={config_id}'
        return request.redirect(target)
