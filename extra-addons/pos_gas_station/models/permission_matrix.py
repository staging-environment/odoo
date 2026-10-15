# -*- coding: utf-8 -*-
from odoo import models, fields, api

class UtrecarRole(models.Model):
    _name = 'utrecar.role'
    _description = 'Rol de Usuario UTRECAR'
    _order = 'sequence, id'

    name = fields.Char(string='Nombre del Rol', required=True)
    code = fields.Char(string='Código', required=True)
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
    user_count = fields.Integer(string='Nº Usuarios', compute='_compute_user_count')

    @api.depends('user_ids')
    def _compute_user_count(self):
        for role in self:
            role.user_count = len(role.user_ids)

class UtrecarPermissionCategory(models.Model):
    _name = 'utrecar.permission.category'
    _description = 'Categoría de Permisos UTRECAR'
    _order = 'sequence, id'

    name = fields.Char(string='Nombre de la Categoría', required=True)
    code = fields.Char(string='Código')
    sequence = fields.Integer(string='Secuencia', default=10)
    permission_ids = fields.One2many('utrecar.permission', 'category_id', string='Permisos')

class UtrecarPermission(models.Model):
    _name = 'utrecar.permission'
    _description = 'Permiso de Sistema UTRECAR'
    _order = 'category_sequence, sequence, id'

    name = fields.Char(string='Descripción del Permiso', required=True)
    code = fields.Char(string='Clave Única (Código)', required=True, index=True)
    category_id = fields.Many2one('utrecar.permission.category', string='Categoría', required=True, ondelete='cascade')
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

class ResUsers(models.Model):
    _inherit = 'res.users'

    utrecar_role_id = fields.Many2one('utrecar.role', string='Rol UTRECAR')

    def has_utrecar_permission(self, perm_code):
        self.ensure_one()
        if self._is_admin():
            return True
        if not self.utrecar_role_id:
            return False
        return any(p.code == perm_code for p in self.utrecar_role_id.permission_ids)
