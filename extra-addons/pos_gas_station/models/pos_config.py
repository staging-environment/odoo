import logging
_logger = logging.getLogger(__name__)
# -*- coding: utf-8 -*-
from odoo import models, api, fields, _
from odoo.exceptions import UserError
import pytz

class PosConfig(models.Model):
    _inherit = 'pos.config'

    vpn_ip = fields.Char(
        string='IPs VPN de Pista',
        help='Dirección IP o lista de IPs separadas por coma asignadas a esta estación en la VPN WireGuard (ej: 10.8.0.18)'
    )
    admin_platform_code = fields.Integer(
        string='Código Estación Admin Platform',
        help='Código numérico de estación (gasolinera_codigo) en la base de datos de admin-platform'
    )

    @api.model
    def _get_default_station_vpn_mapping(self):
        """Mapeo estándar de estaciones por ID, IPs de WireGuard VPN y código en admin-platform."""
        return {
            7: {'vpn_ips': ['10.8.0.18'], 'code': 5, 'name': 'E.S. Repsol'},
            5: {'vpn_ips': ['10.8.0.6', '10.8.0.7'], 'code': 2, 'name': 'E.S. Ronda Norte'},
            3: {'vpn_ips': ['10.8.0.11', '10.8.0.12'], 'code': 1, 'name': 'E.S. Vistalegre (Utrera)'},
            2: {'vpn_ips': ['10.8.0.9', '10.8.0.10'], 'code': 3, 'name': 'E.S. Rodalabota (El Cuervo)'},
            6: {'vpn_ips': ['10.8.0.14', '10.8.0.15'], 'code': 4, 'name': 'E.S. Atenas (Écija)'},
        }

    @api.model
    def get_station_by_vpn_ip(self, ip):
        """Busca y retorna el pos.config asociado a una IP de VPN."""
        if not ip:
            return False
        clean_ip = str(ip).strip()
        
        # 1. Búsqueda en base de datos en pos.config con vpn_ip configurada
        configs = self.sudo().search([('active', 'in', [True, False])])
        for cfg in configs:
            if cfg.vpn_ip:
                ips = [x.strip() for x in cfg.vpn_ip.split(',') if x.strip()]
                if clean_ip in ips:
                    if not cfg.active:
                        cfg.sudo().write({'active': True})
                    return cfg

        # 2. Fallback a mapeo por defecto de la infraestructura WireGuard
        default_map = self._get_default_station_vpn_mapping()
        for cfg_id, info in default_map.items():
            if clean_ip in info['vpn_ips']:
                cfg = self.sudo().browse(cfg_id)
                if cfg.exists():
                    vals = {}
                    if not cfg.vpn_ip:
                        vals['vpn_ip'] = ", ".join(info['vpn_ips'])
                    if not cfg.admin_platform_code:
                        vals['admin_platform_code'] = info['code']
                    if not cfg.active:
                        vals['active'] = True
                    if vals:
                        try:
                            cfg.sudo().write(vals)
                        except Exception:
                            pass
                    return cfg
        return False

    def get_admin_platform_code(self):
        self.ensure_one()
        if self.admin_platform_code:
            return self.admin_platform_code
        default_map = self._get_default_station_vpn_mapping()
        if self.id in default_map:
            return default_map[self.id]['code']
        n = (self.name or '').lower()
        if 'vistalegre' in n or 'utrera' in n:
            return 1
        elif 'ronda norte' in n:
            return 2
        elif 'rodalabota' in n or 'cuervo' in n:
            return 3
        elif 'atenas' in n or 'ecija' in n or 'écija' in n or 'lebrija' in n:
            return 4
        elif 'repsol' in n or 'trieste' in n:
            return 5
        return 0

    def get_admin_platform_employees(self):
        """Consulta la base de datos de admin-platform en MariaDB de producción y devuelve los empleados activos para esta estación."""
        self.ensure_one()
        import pymysql
        import pymysql.cursors

        ICP = self.env['ir.config_parameter'].sudo()
        host = ICP.get_param('admin_platform.db_host', 'ddev-admin-platform-db')
        port = int(ICP.get_param('admin_platform.db_port', 3306))
        user = ICP.get_param('admin_platform.db_user', 'db')
        password = ICP.get_param('admin_platform.db_password', 'db')
        database = ICP.get_param('admin_platform.db_name', 'db')

        target_code = self.get_admin_platform_code()

        color_palette = [
            'linear-gradient(135deg, #2563eb, #1d4ed8)',
            'linear-gradient(135deg, #059669, #047857)',
            'linear-gradient(135deg, #d97706, #b45309)',
            'linear-gradient(135deg, #7c3aed, #6d28d9)',
            'linear-gradient(135deg, #0891b2, #0e7490)',
            'linear-gradient(135deg, #db2777, #be185d)',
            'linear-gradient(135deg, #ea580c, #c2410c)',
            'linear-gradient(135deg, #4f46e5, #4338ca)',
        ]

        employees = []
        try:
            conn = pymysql.connect(
                host=host,
                port=port,
                user=user,
                password=password,
                database=database,
                charset='utf8mb4',
                cursorclass=pymysql.cursors.DictCursor,
                connect_timeout=3
            )
            with conn.cursor() as cur:
                # Comprobar si existe el permiso 'acceso_odoo' en la matriz de permisos de admin-platform
                cur.execute("SELECT id FROM permissions WHERE name = 'acceso_odoo' LIMIT 1")
                has_odoo_perm_def = cur.fetchone()

                if has_odoo_perm_def:
                    # Filtrar solo aquellos empleados autorizados con 'acceso_odoo' en admin-platform
                    # (bien directamente a su usuario o mediante su rol en la Matriz de Permisos)
                    sql = """
                        SELECT e.id, e.nombre, e.apellidos, e.dni, e.email, e.puesto, e.gasolinera_codigo, e.foto
                        FROM empleados e
                        JOIN users u ON e.email = u.email
                        WHERE e.estado = 'Alta' AND (e.deleted_at IS NULL)
                          AND (
                              EXISTS (
                                  SELECT 1 FROM model_has_permissions mhp
                                  JOIN permissions p ON mhp.permission_id = p.id
                                  WHERE mhp.model_id = u.id AND mhp.model_type LIKE '%%User' AND p.name = 'acceso_odoo'
                              )
                              OR EXISTS (
                                  SELECT 1 FROM model_has_roles mhr
                                  JOIN role_has_permissions rhp ON mhr.role_id = rhp.role_id
                                  JOIN permissions p ON rhp.permission_id = p.id
                                  WHERE mhr.model_id = u.id AND mhr.model_type LIKE '%%User' AND p.name = 'acceso_odoo'
                              )
                          )
                        ORDER BY e.nombre, e.apellidos
                    """
                else:
                    sql = """
                        SELECT id, nombre, apellidos, dni, email, puesto, gasolinera_codigo, foto
                        FROM empleados
                        WHERE estado = 'Alta' AND (deleted_at IS NULL)
                        ORDER BY nombre, apellidos
                    """
                cur.execute(sql)
                rows = cur.fetchall()

                matched_rows = [r for r in rows if r.get('gasolinera_codigo') == target_code]
                if not matched_rows:
                    matched_rows = rows

                for idx, r in enumerate(matched_rows):
                    nombre = (r.get('nombre') or '').strip()
                    apellidos = (r.get('apellidos') or '').strip()
                    full_name = f"{nombre} {apellidos}".strip() or f"Empleado #{r['id']}"
                    
                    parts = full_name.split()
                    initials = (parts[0][0] + (parts[1][0] if len(parts) > 1 else '')) if parts else 'EM'
                    initials = initials.upper()

                    email = (r.get('email') or '').strip()
                    dni = (r.get('dni') or '').strip()
                    login = email or dni or f"empleado_{r['id']}@utrecar.com"

                    employees.append({
                        'id': r['id'],
                        'full_name': full_name,
                        'first_name': nombre,
                        'last_name': apellidos,
                        'dni': dni,
                        'email': email,
                        'login': login,
                        'puesto': (r.get('puesto') or 'Expendedor de Pista').strip().title(),
                        'initials': initials,
                        'avatar_gradient': color_palette[idx % len(color_palette)],
                        'photo': r.get('foto') or False,
                        'gasolinera_codigo': r.get('gasolinera_codigo'),
                    })
            conn.close()
        except Exception:
            for idx, u in enumerate(self.allowed_user_ids or self.env['res.users'].sudo().search([('active', '=', True), ('share', '=', False)])):
                parts = u.name.split()
                initials = (parts[0][0] + (parts[1][0] if len(parts) > 1 else '')) if parts else 'U'
                employees.append({
                    'id': u.id,
                    'full_name': u.name,
                    'first_name': parts[0] if parts else u.name,
                    'last_name': " ".join(parts[1:]) if len(parts) > 1 else '',
                    'dni': getattr(u, 'dni', '') or '',
                    'email': u.email or u.login,
                    'login': u.login,
                    'puesto': 'Expendedor Odoo',
                    'initials': initials.upper(),
                    'avatar_gradient': color_palette[idx % len(color_palette)],
                    'photo': False,
                    'gasolinera_codigo': target_code,
                })

        return employees

    def sync_or_get_odoo_user_for_employee(self, emp_data):
        """Garantiza la existencia y vinculación de un usuario en res.users para el empleado de admin-platform."""
        self.ensure_one()
        User = self.env['res.users'].sudo()
        login = emp_data.get('login') or emp_data.get('email') or emp_data.get('dni')
        email = emp_data.get('email') or login

        user = User.search(['|', ('login', '=', login), ('email', '=', email)], limit=1)
        if not user and emp_data.get('dni'):
            user = User.search([('login', '=', emp_data['dni'])], limit=1)

        role_employee = self.env.ref('pos_gas_station.role_employee', raise_if_not_found=False)
        group_pos_user = self.env.ref('point_of_sale.group_pos_user', raise_if_not_found=False)
        group_internal = self.env.ref('base.group_user', raise_if_not_found=False)

        company = self.company_id or self.env.company

        if not user:
            vals = {
                'name': emp_data['full_name'],
                'login': login,
                'email': email,
                'company_id': company.id,
                'company_ids': [(6, 0, [company.id])],
                'pos_config_ids': [(6, 0, [self.id])],
                'active': True,
            }
            if role_employee:
                vals['utrecar_role_id'] = role_employee.id
            groups = []
            if group_pos_user:
                groups.append(group_pos_user.id)
            if group_internal:
                groups.append(group_internal.id)
            if groups:
                vals['groups_id'] = [(6, 0, groups)]

            user = User.with_context(no_reset_password=True, mail_create_nosubscribe=True, mail_create_nolog=True).create(vals)
        else:
            vals = {}
            if self.id not in user.pos_config_ids.ids:
                vals['pos_config_ids'] = [(4, self.id)]
            if company.id not in user.company_ids.ids:
                vals['company_ids'] = [(4, company.id)]
            if not user.active:
                vals['active'] = True
            if role_employee and not user.utrecar_role_id:
                vals['utrecar_role_id'] = role_employee.id
            
            groups_to_add = []
            if group_pos_user and group_pos_user.id not in user.groups_id.ids:
                groups_to_add.append(group_pos_user.id)
            if group_internal and group_internal.id not in user.groups_id.ids:
                groups_to_add.append(group_internal.id)
            if groups_to_add:
                vals['groups_id'] = [(4, gid) for gid in groups_to_add]

            if vals:
                user.write(vals)

        return user

    def open_shift_for_user(self, user):
        """Abre o reanuda el turno (pos.session) en este TPV para el empleado seleccionado."""
        self.ensure_one()
        Session = self.env['pos.session'].sudo()

        session = Session.search([
            ('config_id', '=', self.id),
            ('state', 'in', ['opened', 'opening_control'])
        ], limit=1)

        if session:
            if session.state == 'opening_control':
                session.action_pos_session_open()
                if session.state == 'opening_control':
                    session.write({'state': 'opened'})
            if session.user_id != user:
                session.write({'user_id': user.id})
            return session

        session = Session.create({
            'user_id': user.id,
            'config_id': self.id,
        })
        session.action_pos_session_open()
        if session.state == 'opening_control':
            session.write({'state': 'opened'})
        return session

    @api.depends('session_ids')
    def _compute_last_session(self):
        PosSession = self.env['pos.session']
        for pos_config in self:
            session = PosSession.search_read(
                [('config_id', '=', pos_config.id), ('state', '=', 'closed'), ('stop_at', '!=', False)],
                ['cash_register_balance_end_real', 'stop_at'],
                order='stop_at desc', limit=1)
            if session and session[0].get('stop_at'):
                try:
                    timezone = pytz.timezone(self._context.get('tz') or self.env.user.tz or 'UTC')
                    stop_at = session[0]['stop_at']
                    if hasattr(stop_at, 'astimezone'):
                        pos_config.last_session_closing_date = stop_at.astimezone(timezone).date()
                    else:
                        pos_config.last_session_closing_date = fields.Date.today()
                    pos_config.last_session_closing_cash = session[0].get('cash_register_balance_end_real') or 0.0
                except Exception:
                    pos_config.last_session_closing_date = fields.Date.today()
                    pos_config.last_session_closing_cash = 0.0
            else:
                pos_config.last_session_closing_cash = 0.0
                pos_config.last_session_closing_date = False

    def unlink(self):
        for config in self:
            associated_records = []

            # 1. Turnos y Sesiones del TPV (pos.session)
            sessions = self.env['pos.session'].sudo().search([('config_id', '=', config.id)])
            if sessions:
                active_sessions = sessions.filtered(lambda s: s.state in ['opened', 'opening_control'])
                if active_sessions:
                    cashiers = ", ".join(set(active_sessions.mapped('user_id.name')))
                    associated_records.append(
                        _("• %d turno(s)/sesión(es) de caja (¡Turno actualmente ABIERTO por: %s!)") % (len(sessions), cashiers)
                    )
                else:
                    associated_records.append(
                        _("• %d turno(s)/sesión(es) de caja registrados") % len(sessions)
                    )

            # 2. Tickets y Pedidos de venta (pos.order)
            orders = self.env['pos.order'].sudo().search([('config_id', '=', config.id)])
            if orders:
                associated_records.append(
                    _("• %d tickets y pedidos de venta") % len(orders)
                )

                # 3. Facturas vinculadas (account.move)
                invoices = orders.mapped('account_move').filtered(lambda m: m.exists())
                if invoices:
                    associated_records.append(
                        _("• %d facturas oficiales asociadas a las ventas del TPV") % len(invoices)
                    )

                # 4. Pagos registrados (pos.payment)
                payments_count = self.env['pos.payment'].sudo().search_count([('pos_order_id', 'in', orders.ids)])
                if payments_count:
                    associated_records.append(
                        _("• %d transacciones de cobro / pagos registrados") % payments_count
                    )

            # 5. Empleados y Usuarios autorizados asignados a este TPV
            assigned_users = self.env['res.users'].sudo().search([('pos_config_ids', 'in', [config.id])])
            if assigned_users:
                user_names = ", ".join(assigned_users.mapped('name'))
                associated_records.append(
                    _("• %d usuarios/empleados autorizados con acceso asignado (%s)") % (len(assigned_users), user_names)
                )

            if hasattr(config, 'basic_employee_ids') and config.basic_employee_ids:
                emp_names = ", ".join(config.basic_employee_ids.mapped('name'))
                associated_records.append(
                    _("• %d empleados asignados en control de presencia (%s)") % (len(config.basic_employee_ids), emp_names)
                )

            # 6. Albaranes o Movimientos de existencias (stock.picking)
            if hasattr(self.env['stock.picking'], 'pos_session_id') and sessions:
                pickings_count = self.env['stock.picking'].sudo().search_count([('pos_session_id', 'in', sessions.ids)])
                if pickings_count:
                    associated_records.append(
                        _("• %d albaranes de salida / movimientos de stock de pista") % pickings_count
                    )

            # 7. Clientes asignados a esta estación (res.partner)
            partners_count = self.env['res.partner'].sudo().search_count([('station_id', '=', config.id)])
            if partners_count:
                associated_records.append(
                    _("• %d cliente(s) vinculados a esta estación") % partners_count
                )

            if associated_records:
                details = "\n".join(associated_records)
                raise UserError(_(
                    'No se puede eliminar la estación de servicio "%(name)s" porque contiene registros asociados en el sistema:\n\n'
                    '%(details)s\n\n'
                    'Para mantener la trazabilidad y la integridad con el core de Odoo, debe eliminar o desvincular '
                    'previamente todos los registros vinculados antes de poder borrar la estación.'
                ) % {
                    'name': config.name,
                    'details': details,
                })

        return super(PosConfig, self).unlink()

    def action_open_station_form(self):
        self.ensure_one()
        return {
            'name': f"Estación de Servicio: {self.name}",
            'type': 'ir.actions.act_window',
            'res_model': 'pos.config',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_company_id': self.company_id.id if self.company_id else False,
            }
        }

    def action_edit_station(self):
        self.ensure_one()
        return {
            'name': f"Editar Estación: {self.name}",
            'type': 'ir.actions.act_window',
            'res_model': 'pos.config',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
            'flags': {'mode': 'edit'},
            'context': {
                'default_company_id': self.company_id.id if self.company_id else False,
            }
        }

    def action_delete_station(self):
        self.ensure_one()
        station_name = self.name
        self.unlink()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Estación eliminada'),
                'message': _('La estación de servicio "%s" se ha eliminado con éxito.') % station_name,
                'sticky': False,
                'type': 'success',
                'next': {'type': 'ir.actions.client', 'tag': 'reload'},
            }
        }

    def action_return_to_gas_station_dashboard(self):
        return {
            'type': 'ir.actions.client',
            'tag': 'gas_station_dashboard',
            'target': 'main',
        }


    @api.model
    def get_user_available_stations(self, current_config_id=None):
        """Retorna las estaciones accesibles según el usuario actual."""
        user = self.env.user
        is_admin = user._is_admin() or user.has_group('point_of_sale.group_pos_manager')
        if is_admin:
            configs = self.search([('active', '=', True)])
        else:
            configs = self.search([
                ('active', '=', True),
                '|', ('id', 'in', user.pos_config_ids.ids),
                     ('allowed_user_ids', 'in', [user.id])
            ])
            if not configs and current_config_id:
                configs = self.browse(current_config_id)
        
        stations_data = []
        for c in configs:
            active_session = self.env['pos.session'].search([
                ('config_id', '=', c.id),
                ('state', '=', 'opened')
            ], limit=1)
            stations_data.append({
                'id': c.id,
                'name': c.name,
                'company_name': c.company_id.name,
                'is_current': c.id == current_config_id,
                'has_active_session': bool(active_session),
                'active_user_name': active_session.user_id.name if active_session else None,
                'vpn_ip': c.vpn_ip or '',
            })
        return {
            'is_admin': is_admin,
            'stations': stations_data,
        }


    @api.model
    def cron_sync_admin_platform_employees(self):
        """Sincroniza periódicamente los empleados de admin-platform en res.users de Odoo."""
        _logger.info("Iniciando sincronización programada de empleados desde admin-platform...")
        import pymysql
        import pymysql.cursors

        ICP = self.env['ir.config_parameter'].sudo()
        host = ICP.get_param('admin_platform.db_host', 'ddev-admin-platform-db')
        port = int(ICP.get_param('admin_platform.db_port', 3306))
        user_db = ICP.get_param('admin_platform.db_user', 'db')
        password = ICP.get_param('admin_platform.db_password', 'db')
        database = ICP.get_param('admin_platform.db_name', 'db')

        try:
            conn = pymysql.connect(
                host=host,
                port=port,
                user=user_db,
                password=password,
                database=database,
                charset='utf8mb4',
                cursorclass=pymysql.cursors.DictCursor,
                connect_timeout=5
            )
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, nombre, apellidos, dni, email, puesto, gasolinera_codigo, foto, estado
                    FROM empleados
                    WHERE (deleted_at IS NULL)
                    ORDER BY id ASC
                """)
                rows = cur.fetchall()
            conn.close()
        except Exception as e:
            _logger.error("Error conectando a MariaDB admin-platform para sincronizar empleados: %s", e)
            return {'status': 'error', 'message': str(e)}

        User = self.env['res.users'].sudo()
        all_stations = self.search([])
        default_map = self._get_default_station_vpn_mapping()

        role_employee = self.env.ref('pos_gas_station.role_employee', raise_if_not_found=False)
        role_manager = self.env.ref('pos_gas_station.role_manager', raise_if_not_found=False)
        role_admin = self.env.ref('pos_gas_station.role_admin_hr', raise_if_not_found=False)

        group_pos_user = self.env.ref('point_of_sale.group_pos_user', raise_if_not_found=False)
        group_internal = self.env.ref('base.group_user', raise_if_not_found=False)

        created_count = 0
        updated_count = 0

        for r in rows:
            estado = (r.get('estado') or '').strip().title()
            is_active = (estado == 'Alta')

            nombre = (r.get('nombre') or '').strip()
            apellidos = (r.get('apellidos') or '').strip()
            full_name = f"{nombre} {apellidos}".strip() or f"Empleado #{r['id']}"

            dni = (r.get('dni') or '').strip()
            email = (r.get('email') or '').strip()
            login = email or dni or f"empleado_{r['id']}@utrecar.com"
            puesto = (r.get('puesto') or '').strip()
            gas_code = r.get('gasolinera_codigo')

            # Buscar estación correspondiente
            target_station = False
            if gas_code:
                target_station = all_stations.filtered(lambda s: s.get_admin_platform_code() == gas_code)
                if not target_station:
                    for sid, m in default_map.items():
                        if m.get('admin_platform_code') == gas_code:
                            target_station = self.browse(sid)
                            break

            company = target_station.company_id if target_station and target_station.company_id else self.env.company

            # Buscar si el usuario ya existe en Odoo
            user = User.search(['|', ('login', '=', login), ('email', '=', email)], limit=1)
            if not user and dni:
                user = User.search([('login', '=', dni)], limit=1)

            # Rol según puesto
            puesto_lower = puesto.lower()
            assigned_role = role_employee
            if 'admin' in puesto_lower:
                assigned_role = role_admin or role_manager
            elif any(k in puesto_lower for k in ['encargad', 'responsable', 'gestor', 'jefe']):
                assigned_role = role_manager

            if not user:
                if not is_active:
                    continue

                vals = {
                    'name': full_name,
                    'login': login,
                    'email': email or (f"{login}@utrecar.com" if '@' not in login else login),
                    'company_id': company.id,
                    'company_ids': [(6, 0, [company.id])],
                    'active': True,
                }
                if target_station:
                    vals['pos_config_ids'] = [(6, 0, [target_station.id])]
                if assigned_role:
                    vals['utrecar_role_id'] = assigned_role.id

                groups = []
                if group_internal:
                    groups.append(group_internal.id)
                if group_pos_user:
                    groups.append(group_pos_user.id)
                if groups:
                    vals['groups_id'] = [(6, 0, groups)]

                try:
                    user = User.with_context(
                        no_reset_password=True,
                        mail_create_nosubscribe=True,
                        mail_create_nolog=True
                    ).create(vals)
                    created_count += 1
                except Exception as ex:
                    _logger.warning("No se pudo crear usuario para %s: %s", full_name, ex)
            else:
                vals = {}
                if user.active != is_active:
                    vals['active'] = is_active
                if is_active:
                    if company.id not in user.company_ids.ids:
                        vals['company_ids'] = [(4, company.id)]
                    if target_station and target_station.id not in user.pos_config_ids.ids:
                        vals['pos_config_ids'] = [(4, target_station.id)]
                    if not user.utrecar_role_id and assigned_role:
                        vals['utrecar_role_id'] = assigned_role.id
                if vals:
                    user.write(vals)
                    updated_count += 1

            if user and is_active and target_station and user.id not in target_station.allowed_user_ids.ids:
                target_station.sudo().write({'allowed_user_ids': [(4, user.id)]})

        _logger.info("Sincronización finalizada: %d creados, %d actualizados de %d empleados.", created_count, updated_count, len(rows))
        return {
            'status': 'success',
            'created': created_count,
            'updated': updated_count,
            'total': len(rows)
        }
