# -*- coding: utf-8 -*-
from odoo import http, _
from odoo.http import request
from odoo.addons.web.controllers.home import Home
from odoo.addons.point_of_sale.controllers.main import PosController
from odoo.service import security
import json
from markupsafe import Markup
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
            active_session = request.env['pos.session'].sudo().search([
                ('config_id', '=', config.id),
                ('state', '=', 'opened')
            ], limit=1)

            if not active_session or k.get('select_employee'):
                return request.redirect(f'/pos_gas_station/select_employee?station_id={config.id}')

        return super(UtrecarPosController, self).pos_web(config_id=config_id, **k)


class UtrecarLogin(Home):

    ADMIN_VPN_IPS = {'10.8.0.2', '10.8.0.19', '127.0.0.1'}

    def _is_admin_vpn_ip(self, ip):
        """Comprueba si la IP corresponde a la VPN de Administrador (Jose/Bonilla o configurada en plataforma)."""
        if not ip:
            return False
        clean_ip = str(ip).strip()
        try:
            ICP = request.env['ir.config_parameter'].sudo()
            param_ips = ICP.get_param('pos_gas_station.admin_vpn_ips', '')
            admin_ips = set(self.ADMIN_VPN_IPS)
            if param_ips:
                admin_ips.update([x.strip() for x in param_ips.split(',') if x.strip()])
            return clean_ip in admin_ips
        except Exception:
            return clean_ip in self.ADMIN_VPN_IPS

    def _auto_login_super_admin(self):
        """Autentica automáticamente como Super Administrador (Bonilla / id=2)."""
        admin_user = request.env['res.users'].sudo().browse(2)
        if not admin_user.exists():
            admin_user = request.env['res.users'].sudo().search([('login', '=', 'jarodriguezbonilla@gmail.com')], limit=1)
        if admin_user:
            request.session.uid = admin_user.id
            request.session.login = admin_user.login
            request.session.session_token = security.compute_session_token(request.session, request.env)
            request.session.rotate = True
            return admin_user
        return False


    def _get_client_ip(self):
        forwarded_for = request.httprequest.headers.get('X-Forwarded-For')
        if forwarded_for:
            return forwarded_for.split(',')[0].strip()
        return (request.httprequest.remote_addr or '').strip()

    def _is_station_vpn_ip(self, ip):
        """Comprueba si la IP corresponde al rango de puestos/terminales de gasolinera en la VPN WireGuard."""
        if not ip:
            return False
        clean_ip = str(ip).strip()
        PosConfig = request.env['pos.config'].sudo()

        station = PosConfig.get_station_by_vpn_ip(clean_ip)
        if station:
            return True

        station_ips = {
            '10.8.0.3', '10.8.0.4', '10.8.0.5', '10.8.0.6', '10.8.0.7',
            '10.8.0.8', '10.8.0.9', '10.8.0.10', '10.8.0.11', '10.8.0.12',
            '10.8.0.13', '10.8.0.14', '10.8.0.15', '10.8.0.16', '10.8.0.17', '10.8.0.18'
        }
        return clean_ip in station_ips

    def _get_station_by_ip(self, ip):
        """Retorna el registro pos.config en Odoo si existe para esta IP de VPN."""
        if not ip:
            return False
        clean_ip = str(ip).strip()
        PosConfig = request.env['pos.config'].sudo()
        station = PosConfig.get_station_by_vpn_ip(clean_ip)
        if station and station.exists():
            return station
        return False

    def _is_admin_user(self, user):
        """Comprueba si el usuario tiene rol de Administrador o CEO en Odoo."""
        if not user or not user.exists():
            return False
        has_ceo_role = False
        try:
            roles = user.utrecar_role_ids or (user.utrecar_role_id if user.utrecar_role_id else request.env['utrecar.role'])
            role_codes = [(r.code or '').lower() for r in roles]
            has_ceo_role = 'ceo' in role_codes
        except Exception:
            pass

        return bool(
            user._is_admin() or 
            has_ceo_role or
            user.has_group('base.group_erp_manager') or 
            user.has_group('base.group_system')
        )

    def _has_ceo_configured(self, station=None):
        """Comprueba si la empresa de la estación (o el sistema) tiene configurado un usuario activo con rol CEO."""
        try:
            Access = request.env['utrecar.employee.company.access'].sudo()
            role_ceo = request.env.ref('pos_gas_station.role_ceo', raise_if_not_found=False)
            if not role_ceo:
                Role = request.env['utrecar.role'].sudo()
                role_ceo = Role.search([('code', '=', 'ceo')], limit=1)
            if not role_ceo:
                return False
            domain = [
                ('active_access', '=', True),
                '|',
                ('role_ids', 'in', [role_ceo.id]),
                ('role_id', '=', role_ceo.id)
            ]
            if station and station.exists() and station.company_id:
                domain.append(('company_id', '=', station.company_id.id))
            return bool(Access.search(domain, limit=1))
        except Exception:
            return False

    def _get_default_station(self, station_id=None):
        """Obtiene la estación activa: por ID o por IP VPN de la gasolinera."""
        PosConfig = request.env['pos.config'].sudo()
        if station_id:
            try:
                station = PosConfig.browse(int(station_id))
                if station.exists():
                    return station
            except Exception:
                pass
        ip = self._get_client_ip()
        station = self._get_station_by_ip(ip)
        if station:
            return station
        return False

    @http.route('/', type='http', auth="none")
    def index(self, s_action=None, db=None, **kw):
        """Pantalla principal de Odoo: la home siempre muestra select_employee salvo TPV activo."""
        ip = self._get_client_ip()

        # Si solicitan explícitamente acceso de administrador (?admin=1):
        if request.params.get('admin') == '1':
            if self._is_admin_vpn_ip(ip):
                if not request.session.uid or not self._is_admin_user(request.env['res.users'].sudo().browse(request.session.uid)):
                    self._auto_login_super_admin()
                return request.redirect('/web?admin=1')
            return request.redirect('/web/login?admin=1')

        # Comprobar si la IP corresponde a una estación de gasolinera en WireGuard:
        station = self._get_station_by_ip(ip)
        if station:
            active_session = request.env['pos.session'].sudo().search([
                ('config_id', '=', station.id),
                ('state', '=', 'opened')
            ], limit=1)
            if active_session:
                return request.redirect(f'/pos/ui?config_id={station.id}')
            return request.redirect(f'/pos_gas_station/select_employee?station_id={station.id}')

        # Para cualquier otra IP (incluida la IP VPN del Administrador 10.8.0.2 que no es estación de pista):
        # Muestra la Home (select_employee). Si la IP no pertenece a una estación de pista dada de alta,
        # mostrará la advertencia de puesto pendiente con el botón 'Acceso manual de Administrador'.
        station = self._get_default_station(request.params.get('station_id'))
        if station:
            return request.redirect(f'/pos_gas_station/select_employee?station_id={station.id}')
        return request.redirect('/pos_gas_station/select_employee')

    @http.route('/web', type='http', auth="none")
    def web_client(self, s_action=None, **kw):
        """Control de acceso a /web: solo administradores pueden entrar."""
        ip = self._get_client_ip()
        if self._is_station_vpn_ip(ip):
            station = self._get_station_by_ip(ip)
            target = f'/pos_gas_station/select_employee?station_id={station.id}' if station else '/pos_gas_station/select_employee'
            _logger.warning("Bloqueado intento de acceso a /web desde IP de estación de pista %s.", ip)
            return request.redirect(target)

        # Si el acceso es desde la IP VPN del Super Administrador:
        if self._is_admin_vpn_ip(ip):
            if not request.session.uid or not self._is_admin_user(request.env['res.users'].sudo().browse(request.session.uid)):
                self._auto_login_super_admin()
            return super(UtrecarLogin, self).web_client(s_action=s_action, **kw)

        # Si se solicita acceso de administrador explícito:
        if request.params.get('admin') == '1':
            if request.session.uid:
                user = request.env['res.users'].sudo().browse(request.session.uid)
                if self._is_admin_user(user):
                    return super(UtrecarLogin, self).web_client(s_action=s_action, **kw)
                else:
                    _logger.info("Cerrando sesión no-admin para permitir login de administrador.")
                    request.session.logout()
            return request.redirect('/web/login?admin=1')

        # Si ya hay una sesión activa:
        if request.session.uid:
            user = request.env['res.users'].sudo().browse(request.session.uid)
            if self._is_admin_user(user):
                return super(UtrecarLogin, self).web_client(s_action=s_action, **kw)
            else:
                request.session.logout()
                return request.redirect('/pos_gas_station/select_employee')

        station = self._get_default_station(request.params.get('station_id'))
        target = f'/pos_gas_station/select_employee?station_id={station.id}' if station else '/pos_gas_station/select_employee'
        return request.redirect(target)

    @http.route('/web/login', type='http', auth="none", sitemap=False)
    def web_login(self, redirect=None, **kw):
        """Login de administración de Odoo."""
        ip = self._get_client_ip()
        if self._is_station_vpn_ip(ip):
            station = self._get_station_by_ip(ip)
            target = f'/pos_gas_station/select_employee?station_id={station.id}' if station else '/pos_gas_station/select_employee'
            return request.redirect(target)

        # Si el acceso es desde la IP VPN del Super Administrador:
        if self._is_admin_vpn_ip(ip):
            self._auto_login_super_admin()
            return request.redirect(redirect or '/web')

        # Petición con admin=1 o envío de credenciales POST:
        if request.params.get('admin') == '1' or request.httprequest.method == 'POST':
            if request.session.uid:
                user = request.env['res.users'].sudo().browse(request.session.uid)
                if self._is_admin_user(user):
                    return request.redirect(redirect or '/web')
                else:
                    # Cerrar la sesión de empleado para permitir loguearse como administrador
                    request.session.logout()

            response = super(UtrecarLogin, self).web_login(redirect=redirect, **kw)

            if request.session.uid:
                user = request.env['res.users'].sudo().browse(request.session.uid)
                if self._is_admin_user(user):
                    return request.redirect(redirect or '/web')
                else:
                    _logger.warning("Usuario %s no tiene rol Administrador. Bloqueando acceso a /web.", user.login)
                    request.session.logout()
                    return request.redirect('/pos_gas_station/select_employee')
            return response

        # Si entra a /web/login sin admin=1:
        if request.session.uid:
            user = request.env['res.users'].sudo().browse(request.session.uid)
            if self._is_admin_user(user):
                return request.redirect(redirect or '/web')
            else:
                request.session.logout()
                return request.redirect('/pos_gas_station/select_employee')

        return request.redirect('/pos_gas_station/select_employee')

    @http.route(['/pos_gas_station/select_employee'], type='http', auth="none", sitemap=False)
    def select_station_employee(self, station_id=None, **kw):
        """Pantalla Principal: Identificación de empleado de la empresa correspondiente y apertura de turno."""
        ip = self._get_client_ip()
        station = self._get_default_station(station_id)

        has_tpv = bool(station and station.exists())
        employees = []
        company_name = ''
        warning_message = ''
        is_admin_vpn = self._is_admin_vpn_ip(ip) or self._has_ceo_configured(station)

        if has_tpv:
            company_name = station.company_id.name or 'Empresa'
            employees = station.get_admin_platform_employees()
        else:
            warning_message = f"Te estás conectando desde un equipo (IP de VPN: {ip}) que no tiene acceso al Punto de Venta (TPV) de ninguna gasolinera."

        return request.render('pos_gas_station.station_employee_select_modal', {
            'station': station,
            'has_tpv': has_tpv,
            'company_name': company_name,
            'warning_message': warning_message,
            'employees': employees,
            'employees_json': Markup(json.dumps(employees)),
            'client_ip': (station.vpn_ip if station else '') or ip,
            'is_admin_vpn': is_admin_vpn,
            'redirect': f'/pos/ui?config_id={station.id}' if has_tpv else '#',
            'csrf_token': request.csrf_token(),
        })

    @http.route('/pos_gas_station/station_login', type='http', auth='none', methods=['POST', 'GET'], csrf=False)
    def station_login(self, station_id=None, employee_id=None, redirect=None, **kw):
        """Autentica al empleado de la empresa correspondiente y abre turno hacia el TPV."""
        try:
            if not station_id or not employee_id:
                return request.redirect('/pos_gas_station/select_employee')

            PosConfig = request.env['pos.config'].sudo()
            station = PosConfig.browse(int(station_id))
            if not station.exists():
                return request.redirect('/pos_gas_station/select_employee')

            employees = station.get_admin_platform_employees()
            target_emp = None
            for e in employees:
                if str(e['id']) == str(employee_id):
                    target_emp = e
                    break

            user = None
            if target_emp:
                user = station.sync_or_get_odoo_user_for_employee(target_emp)
            else:
                # Comprobar si employee_id es un usuario/empleado de Odoo con rol CEO
                User = request.env['res.users'].sudo()
                u_cand = User.browse(int(employee_id)) if str(employee_id).isdigit() else User.search([('login', '=', employee_id)], limit=1)
                if u_cand and u_cand.exists() and self._is_admin_user(u_cand):
                    user = u_cand

            if not user:
                _logger.warning("Empleado ID %s no autorizado para la empresa de la estación %s", employee_id, station.name)
                return request.redirect(f'/pos_gas_station/select_employee?station_id={station.id}')

            request.session.uid = user.id
            request.session.login = user.login
            request.session.session_token = security.compute_session_token(request.session, request.env)
            request.session.rotate = True

            # Si el usuario tiene rol CEO o es Administrador, redirige directamente a la administración /web
            if self._is_admin_user(user):
                _logger.info("Usuario Administrador/CEO %s autenticado desde pantalla de estación %s -> /web", user.name, station.name)
                return request.redirect('/web')

            # Para acceder al TPV debe tener rol EMPLEADO activo en la empresa de esta estación
            if not user.is_employee_for_company(station.company_id.id):
                _logger.warning("Usuario %s no tiene rol EMPLEADO activo para %s", user.name, station.company_id.name)
                request.session.logout()
                return request.redirect(f'/pos_gas_station/select_employee?station_id={station.id}')

            station.open_shift_for_user(user)

            dest_url = f'/pos/ui?config_id={station.id}'
            _logger.info("Empleado %s (ID %s) autenticado con éxito en %s. Turno listo -> %s", user.name, user.id, station.name, dest_url)
            return request.redirect(dest_url)

        except Exception as e:
            _logger.exception("Error en /pos_gas_station/station_login: %s", e)
            return request.redirect('/pos_gas_station/select_employee')

    @http.route('/pos_gas_station/switch_cashier', type='http', auth='user', methods=['GET'], csrf=False)
    def switch_cashier(self, config_id=None, **kw):
        """Permite cambiar de cajero o reabrir el selector de empleados de la estación."""
        request.session.logout()
        target = '/pos_gas_station/select_employee'
        if config_id:
            target += f'?station_id={config_id}'
        return request.redirect(target)
