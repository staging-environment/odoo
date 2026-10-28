# -*- coding: utf-8 -*-
from odoo import http, _
from odoo.http import request
from odoo.addons.web.controllers.home import Home
from odoo.service import security
import logging

_logger = logging.getLogger(__name__)

class UtrecarLogin(Home):

    def _get_client_ip(self):
        forwarded_for = request.httprequest.headers.get('X-Forwarded-For')
        if forwarded_for:
            return forwarded_for.split(',')[0].strip()
        return (request.httprequest.remote_addr or '').strip()

    def _station_login_and_redirect(self, station, emp_data, redirect=None):
        user = station.sync_or_get_odoo_user_for_employee(emp_data)
        request.session.uid = user.id
        request.session.login = user.login
        request.session.session_token = security.compute_session_token(request.session, request.env)
        request.session.rotate = True
        
        station.open_shift_for_user(user)
        target_url = redirect or f'/pos/ui?config_id={station.id}'
        _logger.info("Acceso estación por VPN %s: Empleado %s (ID %s) logueado y turno abierto -> %s", station.name, user.name, user.id, target_url)
        return request.redirect(target_url)

    @http.route('/', type='http', auth="none")
    def index(self, s_action=None, db=None, **kw):
        """Redirige raíz: si es IP de estación va directo al TPV, si no va al backend."""
        ip = self._get_client_ip()
        station = request.env['pos.config'].sudo().get_station_by_vpn_ip(ip)
        if station and request.params.get('admin') != '1':
            return request.redirect(f'/pos/ui?config_id={station.id}')
        return super(UtrecarLogin, self).index(s_action=s_action, db=db, **kw)

    @http.route('/web', type='http', auth="none")
    def web_client(self, s_action=None, **kw):
        """Control de acceso a /web: empleados desde IP de estación tienen acceso exclusivo al TPV."""
        ip = self._get_client_ip()
        station = request.env['pos.config'].sudo().get_station_by_vpn_ip(ip)
        if station and request.params.get('admin') != '1':
            if request.session.uid:
                user = request.env['res.users'].sudo().browse(request.session.uid)
                if not user._is_admin():
                    # El empleado de pista tiene acceso único y directo al TPV
                    return request.redirect(f'/pos/ui?config_id={station.id}')
            else:
                return request.redirect(f'/web/login?config_id={station.id}')
        return super(UtrecarLogin, self).web_client(s_action=s_action, **kw)

    @http.route('/web/login', type='http', auth="none", sitemap=False)
    def web_login(self, redirect=None, **kw):
        ip = self._get_client_ip()
        PosConfig = request.env['pos.config'].sudo()
        station = PosConfig.get_station_by_vpn_ip(ip)

        # ---------------------------------------------------------------------
        # CASO 1: LA IP PERTENECE A UNA ESTACIÓN DE SERVICIO (GASOLINERA)
        # El empleado accede directamente al TPV de la estación asignada
        # pidiéndole su nombre en ventana flotante para abrir el turno.
        # ---------------------------------------------------------------------
        if station:
            # Si se solicita explícitamente acceso manual de administrador (ej: ?admin=1)
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

            # Si ya hay un usuario empleado logueado en la sesión con turno abierto actualmente
            if request.session.uid and not request.params.get('select_employee'):
                current_user = request.env['res.users'].sudo().browse(request.session.uid)
                if station.id in current_user.pos_config_ids.ids:
                    active_session = request.env['pos.session'].sudo().search([
                        ('config_id', '=', station.id),
                        ('user_id', '=', current_user.id),
                        ('state', '=', 'opened')
                    ], limit=1)
                    if active_session:
                        return request.redirect(f'/pos/ui?config_id={station.id}')

            # Obtener los empleados de admin-platform para esta estación
            employees = station.get_admin_platform_employees()

            # Mostrar la ventana flotante táctil para seleccionar el empleado e iniciar turno
            return request.render('pos_gas_station.station_employee_select_modal', {
                'station': station,
                'employees': employees,
                'client_ip': ip,
                'redirect': f'/pos/ui?config_id={station.id}',
                'csrf_token': request.csrf_token(),
            })

        # ---------------------------------------------------------------------
        # CASO 2: NO ES IP DE ESTACIÓN (ACCESO GENERAL PROTEGIDO POR VPN)
        # "yo entro con mi usuario como administrador"
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


    @http.route('/pos_gas_station/station_login', type='http', auth='none', methods=['POST', 'GET'], csrf=False)
    def station_login(self, station_id=None, employee_id=None, redirect=None, **kw):
        """Procesa la selección de empleado en la ventana flotante, autentica y abre el turno hacia el TPV."""
        try:
            if not station_id or not employee_id:
                return request.redirect('/web/login')

            PosConfig = request.env['pos.config'].sudo()
            station = PosConfig.browse(int(station_id))
            if not station.exists():
                return request.redirect('/web/login')

            employees = station.get_admin_platform_employees()
            target_emp = None
            for e in employees:
                if str(e['id']) == str(employee_id):
                    target_emp = e
                    break

            if not target_emp:
                _logger.warning("Empleado ID %s no encontrado para estación %s", employee_id, station_id)
                return request.redirect('/web/login')

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
            return request.redirect('/web/login')


    @http.route('/pos_gas_station/switch_cashier', type='http', auth='user', methods=['GET'], csrf=False)
    def switch_cashier(self, config_id=None, **kw):
        """Permite cambiar de cajero o reabrir el selector de empleados de la estación."""
        request.session.logout()
        target = f'/web/login?select_employee=1'
        if config_id:
            target += f'&config_id={config_id}'
        return request.redirect(target)
