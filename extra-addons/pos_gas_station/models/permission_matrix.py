# -*- coding: utf-8 -*-
from odoo import models, fields, api

ROLE_DEFAULT_GROUPS = {
    'ceo': [
        'base.group_system',
        'point_of_sale.group_pos_manager',
    ],
    'gestor': [
        'point_of_sale.group_pos_manager',
    ],
    'empleado': [
        'point_of_sale.group_pos_user',
    ],
    'admin_rrhh': [
        'point_of_sale.group_pos_user',
    ],
}

class UtrecarRole(models.Model):
    _name = 'utrecar.role'
    _description = 'Rol de Usuario UTRECAR'
    _order = 'sequence, id'

    name = fields.Char(string='Nombre del Rol', required=True)
    code = fields.Char(string='Codigo', required=True)
    sequence = fields.Integer(string='Secuencia', default=10)
    color = fields.Char(string='Color', default='#0284c7')
    user_ids = fields.One2many('res.users', 'utrecar_role_id', string='Usuarios Asignados')
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
        ceo_role = self.search([('code', '=', 'ceo')], limit=1)
        if ceo_role:
            admin_group = self.env.ref('base.group_system', raise_if_not_found=False)
            if admin_group:
                admins = self.env['res.users'].search([
                    ('groups_id', 'in', [admin_group.id]),
                    ('active', '=', True)
                ])
                for adm in admins:
                    if adm.utrecar_role_id != ceo_role:
                        adm.sudo().write({'utrecar_role_id': ceo_role.id})

    @api.depends('user_ids')
    def _compute_user_count(self):
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

    utrecar_role_id = fields.Many2one('utrecar.role', string='Rol UTRECAR')
    pos_config_ids = fields.Many2many(
        'pos.config',
        'res_users_pos_config_rel',
        'user_id',
        'pos_config_id',
        string='Estaciones / Tiendas Autorizadas'
    )

    def _sync_utrecar_role_groups(self):
        for user in self:
            if not user.utrecar_role_id:
                continue
            role_code = user.utrecar_role_id.code
            group_xmlids = ROLE_DEFAULT_GROUPS.get(role_code, [])
            groups_to_add = []
            for xmlid in group_xmlids:
                grp = self.env.ref(xmlid, raise_if_not_found=False)
                if grp:
                    groups_to_add.append(grp.id)
            if groups_to_add:
                user.sudo().write({'groups_id': [(4, gid) for gid in groups_to_add]})

    @api.model_create_multi
    def create(self, vals_list):
        users = super(ResUsers, self).create(vals_list)
        users._sync_utrecar_role_groups()
        return users

    def write(self, vals):
        res = super(ResUsers, self).write(vals)
        if 'utrecar_role_id' in vals:
            self._sync_utrecar_role_groups()
        return res

    def has_utrecar_permission(self, perm_code):
        self.ensure_one()
        if self._is_admin():
            return True
        if not self.utrecar_role_id:
            return False
        return any(p.code == perm_code for p in self.utrecar_role_id.permission_ids)