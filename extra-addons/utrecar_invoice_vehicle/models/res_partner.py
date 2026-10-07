from odoo import models, fields, api

class ResPartner(models.Model):
    _inherit = 'res.partner'

    vehicle_ids = fields.One2many('res.partner.vehicle', 'partner_id', string='Vehículos / Matrículas')
    vehicle_count = fields.Integer(string='Vehículos', compute='_compute_vehicle_count')

    invoice_delivery_method = fields.Selection([
        ('email', 'Correo electrónico'),
        ('paper', 'Factura en papel'),
    ], string='Entrega de Facturas', default='email', help='Preferencia por defecto para el envío de facturas a este cliente.')

    @api.depends('vehicle_ids')
    def _compute_vehicle_count(self):
        for partner in self:
            partner.vehicle_count = len(partner.vehicle_ids)

    def action_view_vehicles(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Vehículos de {self.name}',
            'res_model': 'res.partner.vehicle',
            'view_mode': 'tree,form',
            'domain': [('partner_id', '=', self.id)],
            'context': {'default_partner_id': self.id},
        }
