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


import os

class UtrecarPosController(PosController):

    def _ensure_fresh_pos_assets(self):
        """Invalida automáticamente los bundles CSS/JS cacheados en ir.attachment si cambió algún archivo estático de pos_gas_station."""
        try:
            static_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static', 'src'))
            max_mtime = 0
            for root, _, files in os.walk(static_dir):
                for fname in files:
                    if fname.endswith(('.css', '.js', '.xml')):
                        fpath = os.path.join(root, fname)
                        mt = int(os.path.getmtime(fpath))
                        if mt > max_mtime:
                            max_mtime = mt
            ICP = request.env['ir.config_parameter'].sudo()
            last_mtime = int(ICP.get_param('pos_gas_station.assets_mtime', '0') or '0')
            if max_mtime > last_mtime:
                ICP.set_param('pos_gas_station.assets_mtime', str(max_mtime))
                attachments = request.env['ir.attachment'].sudo().search([
                    '|',
                    ('url', 'like', '/web/assets/%'),
                    ('name', 'like', '%assets_%')
                ])
                if attachments:
                    attachments.unlink()
                    request.env.cr.commit()
                    _logger.info("POS Gas Station: purgados %s bundles de assets en caché tras actualización de código.", len(attachments))
        except Exception as e:
            _logger.warning("No se pudo verificar mtime de assets POS: %s", e)

    @http.route(['/pos/web', '/pos/ui'], type='http', auth='user')
    def pos_web(self, config_id=False, **k):
        """Interpreta la entrada al TPV: si no hay turno abierto en la estación, redirige a la selección flotante de empleado."""
        self._ensure_fresh_pos_assets()
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
            # Blindaje multi-compañía: asegurar que el usuario actual tenga la compañía de esta estación asignada
            user = request.env.user
            if user and config.company_id and config.company_id.id not in user.company_ids.ids:
                user.sudo().write({'company_ids': [(4, config.company_id.id)]})

            active_session = request.env['pos.session'].sudo().search([
                ('config_id', '=', config.id),
                ('state', '=', 'opened')
            ], limit=1)

            if not active_session or k.get('select_employee'):
                is_admin = bool(user and (user._is_admin() or user.has_group('base.group_erp_manager') or user.has_group('base.group_system')))
                if is_admin:
                    config.open_shift_for_user(user)
                else:
                    return request.redirect(f'/pos_gas_station/select_employee?station_id={config.id}')

        return super(UtrecarPosController, self).pos_web(config_id=config_id, **k)


class UtrecarLogin(Home):

    def _get_vpn_admin(self, ip):
        """Retorna el registro utrecar.vpn.admin si la IP de VPN está registrada y activa."""
        if not ip:
            return False
        clean_ip = str(ip).strip()
        try:
            VpnAdmin = request.env['utrecar.vpn.admin'].sudo()
            if not VpnAdmin.search_count([]):
                VpnAdmin.ensure_default_admins()
            admin = VpnAdmin.search([('vpn_ip', '=', clean_ip), ('active', '=', True)], limit=1)
            return admin if admin and admin.exists() else False
        except Exception as e:
            _logger.warning("Error buscando utrecar.vpn.admin para IP %s: %s", clean_ip, e)
            return False

    def _is_admin_vpn_ip(self, ip):
        """Comprueba si la IP corresponde a un administrador VPN registrado y activo con empresas asignadas."""
        admin = self._get_vpn_admin(ip)
        return bool(admin and admin.company_ids)

    def _auto_login_super_admin(self, user=None, company_id=None):
        """Autentica automáticamente como Administrador y configura la empresa activa en la sesión."""
        if not user or not user.exists():
            admin_user = request.env['res.users'].sudo().browse(2)
            if not admin_user.exists():
                admin_user = request.env['res.users'].sudo().search([('login', '=', 'jarodriguezbonilla@gmail.com')], limit=1)
            user = admin_user

        if user:
            if company_id:
                try:
                    cid = int(company_id)
                    if cid not in user.company_ids.ids:
                        user.sudo().write({'company_ids': [(4, cid)]})
                    user.sudo().write({'company_id': cid})
                    request.session['allowed_company_ids'] = [cid]
                    request.session['current_company_id'] = cid
                    request.session['admin_active_company_id'] = cid
                except Exception as e:
                    _logger.warning("Error asociando compañía %s a la sesión admin: %s", company_id, e)

            request.session.uid = user.id
            request.session.login = user.login
            request.session.session_token = security.compute_session_token(request.session, request.env)
            request.session.rotate = True
            return user
        return False

    def _get_client_ip(self):
        forwarded_for = request.httprequest.headers.get('X-Forwarded-For')
        if forwarded_for:
            return forwarded_for.split(',')[0].strip()
        return (request.httprequest.remote_addr or '').strip()

    def _is_station_vpn_ip(self, ip):
        """Comprueba si la IP corresponde a un puesto de gasolinera en pos.config."""
        if not ip:
            return False
        clean_ip = str(ip).strip()
        if self._is_admin_vpn_ip(clean_ip):
            return False
        PosConfig = request.env['pos.config'].sudo()
        station = PosConfig.get_station_by_vpn_ip(clean_ip)
        return bool(station and station.exists())

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
        """Comprueba si el usuario tiene rol de Administrador en Odoo."""
        if not user or not user.exists():
            return False
        return bool(
            user._is_admin() or 
            user.has_group('base.group_erp_manager') or 
            user.has_group('base.group_system')
        )

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

    @http.route('/pos_gas_station/admin_login', type='http', auth="none", methods=['GET', 'POST'], csrf=False)
    def admin_login(self, company_id=None, **kw):
        """Autentica a la persona física administradora para una empresa específica según su IP de VPN."""
        ip = self._get_client_ip()
        vpn_admin = self._get_vpn_admin(ip)
        if not vpn_admin or not vpn_admin.company_ids:
            _logger.warning("Intento de admin_login no autorizado desde IP %s", ip)
            return request.redirect('/pos_gas_station/select_employee')

        target_company = None
        if company_id:
            try:
                cid = int(company_id)
                target_company = vpn_admin.company_ids.filtered(lambda c: c.id == cid)
            except Exception:
                target_company = None

        if not target_company:
            target_company = vpn_admin.company_ids[:1]

        cid = target_company.id
        target_user = vpn_admin.user_id
        self._auto_login_super_admin(user=target_user, company_id=cid)
        _logger.info("Admin VPN %s (%s) autenticado para empresa %s (ID %s) -> /web",
                     vpn_admin.name, ip, target_company.name, cid)
        return request.redirect(f'/web?admin=1&cids={cid}')

    @http.route('/', type='http', auth="none")
    def index(self, s_action=None, db=None, **kw):
        """Pantalla principal de Odoo: la home siempre muestra select_employee salvo TPV activo."""
        ip = self._get_client_ip()

        # Si solicitan explícitamente acceso de administrador (?admin=1):
        if request.params.get('admin') == '1':
            vpn_admin = self._get_vpn_admin(ip)
            if vpn_admin and vpn_admin.company_ids:
                cid = request.params.get('company_id')
                if not request.session.uid or not self._is_admin_user(request.env['res.users'].sudo().browse(request.session.uid)):
                    self._auto_login_super_admin(user=vpn_admin.user_id, company_id=cid)
                return request.redirect(f'/web?admin=1{("&cids=" + str(cid)) if cid else ""}')
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

        # Si se solicita acceso de administrador explícito (?admin=1):
        if request.params.get('admin') == '1':
            vpn_admin = self._get_vpn_admin(ip)
            if vpn_admin and vpn_admin.company_ids:
                cid = request.params.get('company_id')
                if not request.session.uid or not self._is_admin_user(request.env['res.users'].sudo().browse(request.session.uid)):
                    self._auto_login_super_admin(user=vpn_admin.user_id, company_id=cid)
                return super(UtrecarLogin, self).web_client(s_action=s_action, **kw)
            else:
                if request.session.uid:
                    user = request.env['res.users'].sudo().browse(request.session.uid)
                    if self._is_admin_user(user):
                        return super(UtrecarLogin, self).web_client(s_action=s_action, **kw)
                    else:
                        _logger.info("Cerrando sesión no-admin para permitir login de administrador.")
                        request.session.logout()
                return request.redirect('/web/login?admin=1')

        # Si no viene ?admin=1, redirigir siempre a select_employee para mostrar
        # la pantalla de TPV (indicando que no es estación y ofreciendo el enlace de administración si corresponde):
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

        vpn_admin = self._get_vpn_admin(ip)
        # Si el acceso es desde la IP VPN de Administrador con ?admin=1:
        if vpn_admin and vpn_admin.company_ids and request.params.get('admin') == '1':
            cid = request.params.get('company_id')
            self._auto_login_super_admin(user=vpn_admin.user_id, company_id=cid)
            return request.redirect(redirect or f'/web?admin=1{("&cids=" + str(cid)) if cid else ""}')

        # Petición con admin=1 o envío de credenciales POST:
        if request.params.get('admin') == '1' or request.httprequest.method == 'POST':
            if request.session.uid:
                user = request.env['res.users'].sudo().browse(request.session.uid)
                if self._is_admin_user(user):
                    return request.redirect(redirect or '/web?admin=1')
                else:
                    request.session.logout()

            response = super(UtrecarLogin, self).web_login(redirect=redirect, **kw)

            if request.session.uid:
                user = request.env['res.users'].sudo().browse(request.session.uid)
                if self._is_admin_user(user):
                    return request.redirect(redirect or '/web?admin=1')
                else:
                    _logger.warning("Usuario %s no tiene rol Administrador. Bloqueando acceso a /web.", user.login)
                    request.session.logout()
                    return request.redirect('/pos_gas_station/select_employee')
            return response

        return request.redirect('/pos_gas_station/select_employee')

    @http.route(['/pos_gas_station/select_employee'], type='http', auth="none", sitemap=False)
    def select_station_employee(self, station_id=None, **kw):
        """Pantalla Principal: Identificación de empleado de la empresa correspondiente o botones dinámicos de administración."""
        ip = self._get_client_ip()
        station = self._get_default_station(station_id)

        has_tpv = bool(station and station.exists())
        employees = []
        company_name = ''
        warning_message = ''
        vpn_admin = self._get_vpn_admin(ip)
        admin_companies = []

        if vpn_admin and vpn_admin.company_ids:
            admin_companies = [{'id': c.id, 'name': c.name} for c in vpn_admin.company_ids]

        if has_tpv:
            company_name = station.company_id.name or 'Empresa'
            employees = station.get_admin_platform_employees()
        else:
            warning_message = f"Te estás conectando desde un equipo sin acceso al TPV de gasolinera. Esta conexión procede de la IP de VPN {ip}, la cual no tiene asignado ningún Punto de Venta (TPV) de gasolinera. Para operar un turno y cobrar en pista, es necesario conectarse desde un puesto autorizado de estación de servicio."

        return request.render('pos_gas_station.station_employee_select_modal', {
            'station': station,
            'has_tpv': has_tpv,
            'company_name': company_name,
            'warning_message': warning_message,
            'employees': employees,
            'employees_json': Markup(json.dumps(employees)),
            'client_ip': (station.vpn_ip if station else '') or ip,
            'admin_companies': admin_companies,
            'vpn_admin_name': vpn_admin.name if vpn_admin else '',
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

            if not user:
                _logger.warning("Empleado ID %s no autorizado para la empresa de la estación %s", employee_id, station.name)
                return request.redirect(f'/pos_gas_station/select_employee?station_id={station.id}')

            request.session.uid = user.id
            request.session.login = user.login
            request.session.session_token = security.compute_session_token(request.session, request.env)
            request.session.rotate = True

            # Si el usuario es Administrador del sistema, redirige directamente a la administración /web
            if self._is_admin_user(user):
                _logger.info("Usuario Administrador %s autenticado desde pantalla de estación %s -> /web", user.name, station.name)
                return request.redirect('/web')

            # Para acceder al TPV debe estar activo en la empresa de esta estación
            if not user.is_employee_for_company(station.company_id.id):
                _logger.warning("Usuario %s no tiene acceso activo para %s", user.name, station.company_id.name)
                request.session.logout()
                return request.redirect(f'/pos_gas_station/select_employee?station_id={station.id}')

            lat = kw.get('lat')
            lng = kw.get('lng')
            emp_id = int(target_emp['id']) if target_emp and target_emp.get('id') else None
            station.open_shift_for_user(user, latitude=lat, longitude=lng, employee_id=emp_id)

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

    @http.route(['/pos_gas_station/admin_tpv', '/pos_gas_station/repsol_tpv'], type='http', auth='none', sitemap=False)
    def admin_tpv(self, station_id=7, **kw):
        """Acceso excepcional de Administrador al TPV de la estación (por defecto Repsol ID 7)."""
        ip = self._get_client_ip()
        is_admin_ip = self._is_admin_vpn_ip(ip)
        current_uid = request.session.uid
        user = request.env['res.users'].sudo().browse(current_uid) if current_uid else None
        is_admin = is_admin_ip or bool(user and self._is_admin_user(user))

        if not is_admin:
            _logger.warning("Intento no autorizado a admin_tpv desde IP %s", ip)
            return request.redirect('/pos_gas_station/select_employee')

        if not user or not self._is_admin_user(user):
            user = self._auto_login_super_admin()

        PosConfig = request.env['pos.config'].sudo()
        station = PosConfig.browse(int(station_id or 7))
        if not station.exists():
            return request.redirect('/web?admin=1')

        # Abrir o activar turno para el administrador
        station.open_shift_for_user(user)
        return request.redirect(f'/pos/ui?config_id={station.id}')
