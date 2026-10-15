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

    @api.depends('pos_config_ids')
    def _compute_pos_config_count(self):
        for company in self:
            company.pos_config_count = len(company.pos_config_ids)

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
