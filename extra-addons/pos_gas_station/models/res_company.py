# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError

class ResCompany(models.Model):
    _inherit = 'res.company'

    pos_config_ids = fields.One2many(
        'pos.config',
        'company_id',
        string='Estaciones de Servicio'
    )
    pos_config_count = fields.Integer(
        string='Nº Estaciones',
        compute='_compute_pos_config_count'
    )
    company_address = fields.Char(
        string='Dirección',
        compute='_compute_company_address'
    )
    station_employee_count = fields.Integer(
        string='Nº Empleados en Estaciones',
        compute='_compute_station_employee_count'
    )

    @api.depends('pos_config_ids')
    def _compute_pos_config_count(self):
        for company in self:
            company.pos_config_count = self.env['pos.config'].sudo().search_count([('company_id', '=', company.id)])

    @api.depends('partner_id.street', 'partner_id.street2', 'partner_id.city', 'partner_id.state_id', 'partner_id.zip')
    def _compute_company_address(self):
        for company in self:
            partner = company.partner_id
            if partner:
                parts = []
                if partner.street:
                    parts.append(partner.street)
                if partner.street2:
                    parts.append(partner.street2)
                loc = []
                if partner.zip:
                    loc.append(partner.zip)
                if partner.city:
                    loc.append(partner.city)
                if partner.state_id:
                    loc.append(partner.state_id.name)
                if loc:
                    parts.append(" ".join(loc))
                company.company_address = ", ".join(parts) if parts else '-'
            else:
                company.company_address = '-'

    @api.depends('pos_config_ids')
    def _compute_station_employee_count(self):
        for company in self:
            stations = company.pos_config_ids
            if not stations:
                company.station_employee_count = 0
                continue
            sessions = self.env['pos.session'].sudo().search([('config_id', 'in', stations.ids)])
            session_users = sessions.mapped('user_id').filtered(lambda u: u.active)
            assigned_users = self.env['res.users'].sudo().search([('pos_config_ids', 'in', stations.ids)]).filtered(lambda u: u.active)
            employees = (session_users | assigned_users).filtered(lambda u: u.id != self.env.ref('base.user_root').id)
            company.station_employee_count = len(employees)

    def action_view_gas_stations(self):
        self.ensure_one()
        return {
            'name': f'Estaciones de {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'pos.config',
            'view_mode': 'tree,form',
            'domain': [('company_id', '=', self.id)],
            'context': {'default_company_id': self.id},
        }

    def action_return_to_gas_station_dashboard(self):
        return {
            'type': 'ir.actions.client',
            'tag': 'gas_station_dashboard',
            'target': 'main',
        }

    def unlink(self):
        for company in self:
            if company.pos_config_ids:
                raise UserError(_(
                    'No se puede eliminar la empresa "%s" porque contiene %s estación(es) de servicio asociada(s). '
                    'Debe eliminar o reasignar las estaciones primero.'
                ) % (company.name, len(company.pos_config_ids)))
            moves_count = self.env['account.move'].sudo().search_count([('company_id', '=', company.id)])
            if moves_count > 0:
                raise UserError(_(
                    'No se puede eliminar la empresa "%s" porque contiene %s asientos o facturas contables registradas.'
                ) % (company.name, moves_count))
            orders_count = self.env['pos.order'].sudo().search_count([('company_id', '=', company.id)])
            if orders_count > 0:
                raise UserError(_(
                    'No se puede eliminar la empresa "%s" porque contiene %s tickets de venta asociados.'
                ) % (company.name, orders_count))
        return super(ResCompany, self).unlink()
