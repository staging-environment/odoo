# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)

class UtrecarVpnAdmin(models.Model):
    _name = 'utrecar.vpn.admin'
    _description = 'Administrador VPN por Empresa'
    _order = 'name asc'

    name = fields.Char(string="Persona Física / Nombre", required=True)
    vpn_ip = fields.Char(string="IP WireGuard VPN", required=True, index=True)
    active = fields.Boolean(string="Activo", default=True)
    company_ids = fields.Many2many(
        'res.company',
        'utrecar_vpn_admin_company_rel',
        'admin_id',
        'company_id',
        string="Empresas Asignadas"
    )
    can_manage_staff = fields.Boolean(
        string="Gestionar Personal y Administradores",
        default=False,
        help="Permite a este administrador acceder y modificar la asignación de personal y administradores."
    )
    user_id = fields.Many2one('res.users', string="Usuario Odoo Vinculado", ondelete='set null')
    notes = fields.Text(string="Notas")

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            rec._sync_security_groups()
        return records

    def write(self, vals):
        res = super().write(vals)
        if 'can_manage_staff' in vals or 'user_id' in vals or 'active' in vals:
            for rec in self:
                rec._sync_security_groups()
        return res

    def _sync_security_groups(self):
        """Sincroniza el grupo de seguridad de gestión de personal según el check can_manage_staff."""
        self.ensure_one()
        group = self.env.ref('pos_gas_station.group_utrecar_manage_staff', raise_if_not_found=False)
        if not group or not self.user_id:
            return

        should_have = self.active and self.can_manage_staff
        if should_have and self.user_id.id not in group.users.ids:
            group.sudo().write({'users': [(4, self.user_id.id)]})
            _logger.info("Añadido usuario %s al grupo Gestionar Personal y Administradores", self.user_id.login)
        elif not should_have and self.user_id.id in group.users.ids:
            # No retirar si es el superadministrador principal (id=2 o admin)
            if self.user_id.id not in (1, 2) and self.user_id.login != 'jarodriguezbonilla@gmail.com':
                group.sudo().write({'users': [(3, self.user_id.id)]})
                _logger.info("Retirado usuario %s del grupo Gestionar Personal y Administradores", self.user_id.login)

    @api.model
    def ensure_default_admins(self):
        """Inicializa los administradores VPN por defecto si no existen."""
        defaults = [
            {
                'name': 'Jose (Informático)',
                'vpn_ip': '10.8.0.2',
                'active': True,
                'can_manage_staff': True,
                'user_login': 'jarodriguezbonilla@gmail.com',
                'company_ids': [1, 4],
            },
            {
                'name': 'Jose (Informático) Salón',
                'vpn_ip': '10.8.0.19',
                'active': True,
                'can_manage_staff': True,
                'user_login': 'jarodriguezbonilla@gmail.com',
                'company_ids': [1, 4],
            },
            {
                'name': 'Alfonso',
                'vpn_ip': '10.8.0.3',
                'active': True,
                'can_manage_staff': True,
                'user_login': 'utrecar@gmail.com',
                'company_ids': [1, 4],
            },
            {
                'name': 'Alfonso Portatil',
                'vpn_ip': '10.8.0.8',
                'active': True,
                'can_manage_staff': True,
                'user_login': 'utrecar@gmail.com',
                'company_ids': [1, 4],
            },
            {
                'name': 'David - Portatil',
                'vpn_ip': '10.8.0.4',
                'active': True,
                'can_manage_staff': False,
                'company_ids': [1],
            },
            {
                'name': 'Manolo - Portatil',
                'vpn_ip': '10.8.0.5',
                'active': True,
                'can_manage_staff': False,
                'company_ids': [1],
            },
            {
                'name': 'Fatima',
                'vpn_ip': '10.8.0.16',
                'active': True,
                'can_manage_staff': False,
                'user_login': 'fatimabg@hotmail.es',
                'company_ids': [1],
            },
            {
                'name': 'Maria',
                'vpn_ip': '10.8.0.17',
                'active': True,
                'can_manage_staff': False,
                'company_ids': [1],
            },
        ]
        Users = self.env['res.users'].sudo()
        Companies = self.env['res.company'].sudo()
        for item in defaults:
            existing = self.search([('vpn_ip', '=', item['vpn_ip'])], limit=1)
            user = None
            if item.get('user_login'):
                user = Users.search([('login', '=', item['user_login'])], limit=1)

            valid_companies = Companies.browse(item['company_ids']).exists()
            if not existing:
                self.create({
                    'name': item['name'],
                    'vpn_ip': item['vpn_ip'],
                    'active': item['active'],
                    'can_manage_staff': item['can_manage_staff'],
                    'user_id': user.id if user else False,
                    'company_ids': [(6, 0, valid_companies.ids)],
                })
            else:
                vals = {}
                if not existing.company_ids and valid_companies:
                    vals['company_ids'] = [(6, 0, valid_companies.ids)]
                if not existing.user_id and user:
                    vals['user_id'] = user.id
                if vals:
                    existing.write(vals)
