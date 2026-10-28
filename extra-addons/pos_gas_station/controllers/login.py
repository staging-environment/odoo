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
        request.update_env(user=user.id)
        request.update_context(**user.context_get())
        
        station.open_shift_for_user(user)
        target_url = redirect or f'/pos/ui?config_id={station.id}'
        _logger.info("Acceso estación por VPN %s: Empleado %s (ID %s) logueado y turno abierto -> %s", station.name, user.name, user.id, target_url)
        return request.redirect(target_url)

    @http.route('/web/login', type='http', auth="none", sitemap=False)
    def web_login(self, redirect=None, **kw):
        ip = self._get_client_ip()
        PosConfig = request.env['pos.config'].sudo()
        station = PosConfig.get_station_by_vpn_ip(ip)

        # ---------------------------------------------------------------------
        # CASO 1: LA IP PERTENECE A UNA ESTACIÓN DE SERVICIO (GASOLINERA)
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
                    request.update_env(user=admin_user.id)
                    request.update_context(**admin_user.context_get())
                    return request.redirect(redirect or '/web')

            # Si ya hay un usuario logueado en la sesión
            if request.session.uid and not request.params.get('select_employee'):
                current_user = request.env['res.users'].sudo().browse(request.session.uid)
                # Si el usuario actual es admin o tiene acceso a esta estación
                if current_user._is_admin() or (station.id in current_user.pos_config_ids.ids):
                    station.open_shift_for_user(current_user)
                    return request.redirect(redirect or f'/pos/ui?config_id={station.id}')

            # Obtener los empleados de admin-platform para esta estación
            employees = station.get_admin_platform_employees()

            # Si solo hay 1 empleado, acceso directo y apertura de turno
            if len(employees) == 1:
                return self._station_login_and_redirect(station, employees[0], redirect=redirect)

            # Si hay varios empleados (o ninguno específico y se muestran los activos):
            # Mostrar la ventana flotante para elegir el empleado
            return request.render('pos_gas_station.station_employee_select_modal', {
                'station': station,
                'employees': employees,
                'client_ip': ip,
                'redirect': redirect,
                'csrf_token': request.csrf_token(),
            })

        # ---------------------------------------------------------------------
        # CASO 2: NO ES IP DE ESTACIÓN (ACCESO GENERAL PROTEGIDO POR VPN)
        # "cuando alguien entre al entorno https://odoo.utrecar.com/ se acceda directamente con el usuario de administrador"
        # ---------------------------------------------------------------------
        # Si ya está autenticado, continuar a la URL destino o /web
        if request.session.uid:
            return request.redirect(redirect or '/web')

        # Auto-login automático como Administrador
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
            request.update_env(user=admin_user.id)
            request.update_context(**admin_user.context_get())
            _logger.info("Auto-login directo como Administrador (%s) desde IP VPN: %s", admin_user.login, ip)
            return request.redirect(redirect or '/web')

        return super(UtrecarLogin, self).web_login(redirect=redirect, **kw)


    @http.route('/pos_gas_station/station_login', type='http', auth='none', methods=['POST', 'GET'], csrf=False)
    def station_login(self, station_id=None, employee_id=None, redirect=None, **kw):
        """Procesa la selección de empleado en la ventana flotante, autentica y abre el turno."""
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
            request.update_env(user=user.id)
            request.update_context(**user.context_get())

            # Abrir o activar el turno del TPV
            station.open_shift_for_user(user)

            dest_url = redirect or f'/pos/ui?config_id={station.id}'
            _logger.info("Empleado %s (ID %s) autenticado con éxito en %s. Turno listo -> %s", user.name, user.id, station.name, dest_url)
            return request.redirect(dest_url)

        except Exception as e:
            _logger.exception("Error en /pos_gas_station/station_login: %s", e)
            return request.redirect('/web/login')


    @http.route('/pos_gas_station/switch_cashier', type='http', auth='user', methods=['GET'], csrf=False)
    def switch_cashier(self, config_id=None, **kw):
        """Permite cambiar de cajero o reabrir el selector de empleados de la estación."""
        request.session.logout()
        return request.redirect('/web/login?select_employee=1')
