# -*- coding: utf-8 -*-
from odoo import models, fields, api

ROLE_DEFAULT_GROUPS = {
    'ceo': [
        'base.group_system',
        'base.group_erp_manager',
        'point_of_sale.group_pos_manager',
    ],
    'manager': [
        'point_of_sale.group_pos_manager',
    ],
    'gestor': [
        'point_of_sale.group_pos_manager',
    ],
    'employee': [
        'point_of_sale.group_pos_user',
    ],
    'empleado': [
        'point_of_sale.group_pos_user',
    ],
    'admin_hr': [
        'point_of_sale.group_pos_user',
    ],
    'admin_rrhh': [
        'point_of_sale.group_pos_user',
    ],
}

class UtrecarEmployeeCompanyAccess(models.Model):
    _name = 'utrecar.employee.company.access'
    _description = 'Acceso y Rol de Empleado por Empresa'
    _order = 'company_id, user_id'

    user_id = fields.Many2one('res.users', string='Usuario / Empleado', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one('res.company', string='Empresa', required=True, ondelete='cascade', index=True)
    role_id = fields.Many2one('utrecar.role', string='Rol Principal en esta Empresa', ondelete='set null')
    role_ids = fields.Many2many(
        'utrecar.role',
        'utrecar_emp_comp_role_rel',
        'access_id',
        'role_id',
        string='Roles en esta Empresa'
    )
    active_access = fields.Boolean(string='Acceso Habilitado', default=True)

    _sql_constraints = [
        ('uniq_user_company_access', 'unique(user_id, company_id)', 'Solo puede existir una configuracion de acceso por usuario y empresa.')
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'role_ids' in vals and vals['role_ids'] and not vals.get('role_id'):
                rids = []
                for cmd in vals['role_ids']:
                    if cmd[0] == 6:
                        rids.extend(cmd[2])
                    elif cmd[0] == 4:
                        rids.append(cmd[1])
                if rids:
                    vals['role_id'] = rids[0]
            elif 'role_id' in vals and vals['role_id'] and not vals.get('role_ids'):
                vals['role_ids'] = [(4, vals['role_id'])]
        return super(UtrecarEmployeeCompanyAccess, self).create(vals_list)

    def write(self, vals):
        if 'role_ids' in vals and not vals.get('role_id'):
            for cmd in vals.get('role_ids', []):
                if cmd[0] == 6:
                    vals['role_id'] = cmd[2][0] if cmd[2] else False
                elif cmd[0] == 4:
                    vals['role_id'] = cmd[1]
        elif 'role_id' in vals and vals['role_id'] and not vals.get('role_ids'):
            vals['role_ids'] = [(4, vals['role_id'])]
        return super(UtrecarEmployeeCompanyAccess, self).write(vals)


class UtrecarCompanyRolePermission(models.Model):
    _name = 'utrecar.company.role.permission'
    _description = 'Permiso de Rol por Empresa UTRECAR'

    company_id = fields.Many2one('res.company', string='Empresa', required=True, ondelete='cascade', index=True)
    role_id = fields.Many2one('utrecar.role', string='Rol', required=True, ondelete='cascade', index=True)
    permission_id = fields.Many2one('utrecar.permission', string='Permiso', required=True, ondelete='cascade', index=True)
    granted = fields.Boolean(string='Otorgado', default=True)

    _sql_constraints = [
        ('uniq_comp_role_perm', 'unique(company_id, role_id, permission_id)', 'Ya existe una configuración de permiso para esta empresa, rol y permiso.')
    ]


class UtrecarRole(models.Model):
    _name = 'utrecar.role'
    _description = 'Rol de Usuario UTRECAR'
    _order = 'sequence, id'

    name = fields.Char(string='Nombre del Rol', required=True)
    code = fields.Char(string='Codigo', required=True)
    sequence = fields.Integer(string='Secuencia', default=10)
    color = fields.Char(string='Color', default='#0284c7')
    user_ids = fields.Many2many(
        'res.users',
        'utrecar_user_role_rel',
        'role_id',
        'user_id',
        string='Usuarios Asignados'
    )
    permission_ids = fields.Many2many(
        'utrecar.permission',
        'utrecar_role_permission_rel',
        'role_id',
        'permission_id',
        string='Permisos Otorgados'
    )
    user_count = fields.Integer(string='N Usuarios', compute='_compute_user_count')

    @api.model
    def auto_link_admin_users(self):
        home_action = self.env.ref('pos_gas_station.action_gas_station_dashboard', raise_if_not_found=False)
        all_companies = self.env['res.company'].search([])
        ceo_role = self.search([('code', '=', 'ceo')], limit=1)
        if ceo_role:
            admin_groups = [
                self.env.ref('base.group_system', raise_if_not_found=False),
                self.env.ref('base.group_erp_manager', raise_if_not_found=False),
            ]
            group_ids = [g.id for g in admin_groups if g]
            if group_ids:
                admins = self.env['res.users'].search([
                    ('groups_id', 'in', group_ids),
                    ('active', '=', True)
                ])
                for adm in admins:
                    vals = {}
                    if adm.utrecar_role_id != ceo_role:
                        vals['utrecar_role_id'] = ceo_role.id
                    if home_action and adm.action_id != home_action:
                        vals['action_id'] = home_action.id
                    missing_comps = all_companies - adm.company_ids
                    if missing_comps:
                        vals['company_ids'] = [(4, cid) for cid in missing_comps.ids]
                    if vals:
                        adm.sudo().write(vals)
                    adm._sync_utrecar_role_groups()

        # Set default home_action for active users
        if home_action:
            active_users = self.env['res.users'].search([('active', '=', True), ('action_id', '!=', home_action.id)])
            for u in active_users:
                u.sudo().write({'action_id': home_action.id})

    @api.depends('user_ids')
    def _compute_user_count(self):
        self.auto_link_admin_users()
        for role in self:
            role.user_count = len(role.user_ids)

class UtrecarPermissionCategory(models.Model):
    _name = 'utrecar.permission.category'
    _description = 'Categoria de Permisos UTRECAR'
    _order = 'sequence, id'

    name = fields.Char(string='Nombre de la Categoria', required=True)
    code = fields.Char(string='Codigo')
    sequence = fields.Integer(string='Secuencia', default=10)
    permission_ids = fields.One2many('utrecar.permission', 'category_id', string='Permisos')

class UtrecarPermission(models.Model):
    _name = 'utrecar.permission'
    _description = 'Permiso de Sistema UTRECAR'
    _order = 'category_sequence, sequence, id'

    name = fields.Char(string='Descripcion del Permiso', required=True)
    code = fields.Char(string='Clave Unica (Codigo)', required=True, index=True)
    category_id = fields.Many2one('utrecar.permission.category', string='Categoria', required=True, ondelete='cascade')
    category_sequence = fields.Integer(related='category_id.sequence', store=True)
    sequence = fields.Integer(string='Secuencia', default=10)
    description = fields.Text(string='Detalle adicional')
    role_ids = fields.Many2many(
        'utrecar.role',
        'utrecar_role_permission_rel',
        'permission_id',
        'role_id',
        string='Roles con este Permiso'
    )

class PosConfig(models.Model):
    _inherit = 'pos.config'

    allowed_user_ids = fields.Many2many(
        'res.users',
        'res_users_pos_config_rel',
        'pos_config_id',
        'user_id',
        string='Usuarios de Pista Autorizados'
    )
    station_users_summary = fields.Char(
        string='Personal y Roles Asignados',
        compute='_compute_station_users_summary'
    )
    station_link_html = fields.Html(
        string='Estación de Servicio',
        compute='_compute_station_link_html',
        sanitize=False
    )

    @api.depends('name')
    def _compute_station_link_html(self):
        for config in self:
            config.station_link_html = f'<a href="#id={config.id}&amp;model=pos.config&amp;view_type=form" class="fw-bold text-decoration-none" style="color: #0284c7; font-size: 0.95rem;"><i class="fa fa-gas-pump me-1 text-danger"></i> {config.name}</a>'

    @api.depends('allowed_user_ids', 'allowed_user_ids.name', 'allowed_user_ids.utrecar_role_id')
    def _compute_station_users_summary(self):
        for config in self:
            if not config.allowed_user_ids:
                config.station_users_summary = 'Acceso General (Sin restricción)'
            else:
                parts = []
                for u in config.allowed_user_ids:
                    role_str = u.utrecar_role_id.name if u.utrecar_role_id else 'Sin Rol'
                    parts.append(f"{u.name} ({role_str})")
                config.station_users_summary = ", ".join(parts)

    def action_return_to_company(self):
        self.ensure_one()
        if not self.company_id:
            return self.action_return_to_gas_station_dashboard()
        return {
            'type': 'ir.actions.act_window',
            'name': self.company_id.name,
            'res_model': 'res.company',
            'res_id': self.company_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_open_permission_matrix(self):
        return {
            'type': 'ir.actions.client',
            'tag': 'utrecar_permission_matrix',
            'target': 'current',
        }

    @api.model
    def action_entry_pos(self):
        user = self.env.user
        if user.has_group('point_of_sale.group_pos_manager') or user._is_admin():
            action = self.env.ref('point_of_sale.action_pos_config_kanban').sudo().read()[0]
            return action

        configs = user.pos_config_ids
        if not configs:
            configs = self.search([('allowed_user_ids', 'in', [user.id])])

        if len(configs) == 1:
            return configs.open_ui()
        elif len(configs) > 1:
            action = self.env.ref('point_of_sale.action_pos_config_kanban').sudo().read()[0]
            action['domain'] = [('id', 'in', configs.ids)]
            action['display_name'] = 'Seleccione su Punto de Venta'
            return action
        else:
            action = self.env.ref('point_of_sale.action_pos_config_kanban').sudo().read()[0]
            return action

class ResUsers(models.Model):
    _inherit = 'res.users'

    company_access_ids = fields.One2many(
        'utrecar.employee.company.access',
        'user_id',
        string='Accesos y Roles por Empresa'
    )

    def get_company_roles(self, company_id):
        self.ensure_one()
        access = self.company_access_ids.filtered(lambda a: a.company_id.id == company_id and a.active_access)
        if not access:
            return self.env['utrecar.role']
        return access[0].role_ids or (access[0].role_id if access[0].role_id else self.env['utrecar.role'])

    def get_company_role(self, company_id):
        roles = self.get_company_roles(company_id)
        return roles[:1] if roles else False

    def is_employee_for_company(self, company_id):
        """Verifica si el usuario está activo en la empresa y tiene asignado el rol EMPLEADO para esa empresa."""
        self.ensure_one()
        access = self.company_access_ids.filtered(lambda a: a.company_id.id == company_id)
        if access:
            # Si existe registro para la empresa, respetar estrictamente el switch de activo
            if not access[0].active_access:
                return False
            role_emp = self.env.ref('pos_gas_station.role_employee', raise_if_not_found=False)
            roles = access[0].role_ids or (access[0].role_id if access[0].role_id else self.env['utrecar.role'])
            return bool(role_emp and role_emp in roles)
        return False


    utrecar_role_ids = fields.Many2many(
        'utrecar.role',
        'utrecar_user_role_rel',
        'user_id',
        'role_id',
        string='Roles UTRECAR'
    )
    utrecar_role_id = fields.Many2one(
        'utrecar.role',
        string='Rol Principal UTRECAR',
        compute='_compute_utrecar_role_id',
        inverse='_inverse_utrecar_role_id',
        store=True
    )

    @api.depends('utrecar_role_ids')
    def _compute_utrecar_role_id(self):
        for user in self:
            user.utrecar_role_id = user.utrecar_role_ids[:1] if user.utrecar_role_ids else False

    def _inverse_utrecar_role_id(self):
        for user in self:
            if user.utrecar_role_id and user.utrecar_role_id not in user.utrecar_role_ids:
                user.utrecar_role_ids = [(4, user.utrecar_role_id.id)]
    pos_config_ids = fields.Many2many(
        'pos.config',
        'res_users_pos_config_rel',
        'user_id',
        'pos_config_id',
        string='Estaciones / Tiendas Autorizadas'
    )
    role_badge_html = fields.Html(
        string='Rol Asignado',
        compute='_compute_role_badge_html',
        sanitize=False
    )
    permission_badges_html = fields.Html(
        string='Permisos Efectivos Otorgados',
        compute='_compute_permission_badges_html',
        sanitize=False
    )

    @api.depends('utrecar_role_id', 'utrecar_role_ids', 'utrecar_role_ids.name', 'utrecar_role_ids.color')
    def _compute_role_badge_html(self):
        for user in self:
            roles = user.utrecar_role_ids or (user.utrecar_role_id if user.utrecar_role_id else self.env['utrecar.role'])
            if roles:
                badges = []
                for r in roles:
                    color = r.color or '#0284c7'
                    badges.append(f'<span class="badge text-white px-2 py-1 me-1 fw-bold" style="background-color: {color}; font-size: 0.85rem;"><i class="fa fa-shield me-1"></i> {r.name}</span>')
                user.role_badge_html = "".join(badges)
            else:
                user.role_badge_html = '<span class="badge text-bg-secondary px-2 py-1">Sin Rol</span>'

    @api.depends('utrecar_role_id', 'utrecar_role_ids', 'utrecar_role_ids.permission_ids')
    def _compute_permission_badges_html(self):
        for user in self:
            roles = user.utrecar_role_ids or (user.utrecar_role_id if user.utrecar_role_id else self.env['utrecar.role'])
            if not roles:
                user.permission_badges_html = '<span class="badge text-bg-warning text-dark"><i class="fa fa-exclamation-triangle me-1"></i> Sin rol asignado</span>'
                continue
            perms = roles.mapped('permission_ids')
            if not perms:
                user.permission_badges_html = '<span class="badge text-bg-secondary">Sin permisos activos</span>'
                continue

            badges = []
            role_codes = [(r.code or '').lower() for r in roles]
            if 'ceo' in role_codes or len(perms) >= 15:
                badges.append(f'<span class="badge text-bg-primary fw-bold me-1 mb-1" style="font-size: 0.8rem;"><i class="fa fa-star me-1"></i> Acceso Total ({len(perms)} permisos)</span>')
                key_perms = perms.filtered(lambda p: any(k in p.name.lower() for k in ['tpv', 'pista', 'precios', 'surtidor', 'cierre', 'arqueo', 'factura', 'descuento']))
                for p in key_perms[:4]:
                    badges.append(f'<span class="badge bg-light text-dark border me-1 mb-1" style="font-size: 0.75rem;">{p.name}</span>')
                if len(perms) > 5:
                    badges.append(f'<span class="badge bg-light text-muted border me-1 mb-1" style="font-size: 0.75rem;">+{len(perms) - 5} más</span>')
            else:
                for p in perms:
                    badges.append(f'<span class="badge bg-light text-dark border me-1 mb-1" style="font-size: 0.75rem; font-weight: 500;"><i class="fa fa-check text-success me-1"></i> {p.name}</span>')
            user.permission_badges_html = "".join(badges)

    def _sync_utrecar_role_groups(self):
        for user in self:
            if user.id in [1, 2] or user.login in ['__system__', 'jarodriguezbonilla@gmail.com']:
                continue
            all_roles = user.utrecar_role_ids or (user.utrecar_role_id if user.utrecar_role_id else self.env['utrecar.role'])
            if not all_roles:
                continue
            role_codes = [(r.code or '').lower() for r in all_roles]
            has_admin = any(c in ['ceo', 'admin_hr'] for c in role_codes)
            has_manager = any(c in ['manager', 'gestor'] for c in role_codes)

            admin_groups = [
                self.env.ref('base.group_erp_manager', raise_if_not_found=False),
                self.env.ref('base.group_system', raise_if_not_found=False),
            ]
            admin_group_ids = [g.id for g in admin_groups if g]
            pos_mgr = self.env.ref('point_of_sale.group_pos_manager', raise_if_not_found=False)
            pos_user = self.env.ref('point_of_sale.group_pos_user', raise_if_not_found=False)

            commands = []
            if has_admin:
                for gid in admin_group_ids:
                    if gid not in user.groups_id.ids:
                        commands.append((4, gid))
                if pos_mgr and pos_mgr.id not in user.groups_id.ids:
                    commands.append((4, pos_mgr.id))
            elif has_manager:
                for gid in admin_group_ids:
                    if gid in user.groups_id.ids:
                        commands.append((3, gid))
                if pos_mgr and pos_mgr.id not in user.groups_id.ids:
                    commands.append((4, pos_mgr.id))
            else:
                for gid in admin_group_ids:
                    if gid in user.groups_id.ids:
                        commands.append((3, gid))
                # Los empleados con rol activo en TPV tienen point_of_sale.group_pos_manager para poder operar con plenas facultades en el TPV
                if pos_mgr and pos_mgr.id not in user.groups_id.ids:
                    commands.append((4, pos_mgr.id))

            if pos_user and pos_user.id not in user.groups_id.ids:
                commands.append((4, pos_user.id))

            if commands:
                user.sudo().write({'groups_id': commands})

    def is_ceo(self):
        """Verifica si el usuario tiene asignado el rol CEO o es Administrador."""
        self.ensure_one()
        if self._is_admin():
            return True
        roles = self.utrecar_role_ids or (self.utrecar_role_id if self.utrecar_role_id else self.env['utrecar.role'])
        role_codes = [(r.code or '').lower() for r in roles]
        return 'ceo' in role_codes

    @api.model_create_multi
    def create(self, vals_list):
        users = super(ResUsers, self).create(vals_list)
        users._sync_utrecar_role_groups()
        return users

    def write(self, vals):
        res = super(ResUsers, self).write(vals)
        if 'utrecar_role_ids' in vals or 'utrecar_role_id' in vals:
            self._sync_utrecar_role_groups()
        return res

    def has_utrecar_permission(self, perm_code, company_id=None):
        self.ensure_one()
        if self._is_admin():
            return True
        user_roles = self.utrecar_role_ids or (self.utrecar_role_id if self.utrecar_role_id else self.env['utrecar.role'])
        if not user_roles:
            return False

        perm = self.env['utrecar.permission'].sudo().search([('code', '=', perm_code)], limit=1)
        if not perm:
            return False

        # Si se consulta para una empresa específica, buscar configuración propia de esa empresa
        if company_id:
            comp_perm = self.env['utrecar.company.role.permission'].sudo().search([
                ('company_id', '=', int(company_id)),
                ('role_id', 'in', user_roles.ids),
                ('permission_id', '=', perm.id)
            ], limit=1)
            if comp_perm:
                return comp_perm.granted

        # Fallback a permisos base del rol
        return any(perm in r.permission_ids for r in user_roles)
