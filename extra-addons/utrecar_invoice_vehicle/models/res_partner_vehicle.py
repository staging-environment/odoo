from odoo import models, fields, api

class ResPartnerVehicle(models.Model):
    _name = 'res.partner.vehicle'
    _description = 'Vehículo / Matrícula de Cliente'
    _order = 'name asc'

    name = fields.Char(string='Matrícula', required=True, index=True)
    partner_id = fields.Many2one('res.partner', string='Cliente', required=True, ondelete='cascade', index=True)
    notes = fields.Char(string='Marca / Modelo / Notas')

    _sql_constraints = [
        ('name_partner_uniq', 'unique(name, partner_id)', 'Esta matrícula ya está registrada para este cliente.')
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name'):
                vals['name'] = str(vals['name']).strip().upper()
        return super().create(vals_list)

    def write(self, vals):
        if 'name' in vals and vals['name']:
            vals['name'] = str(vals['name']).strip().upper()
        return super().write(vals)

    def name_get(self):
        result = []
        for rec in self:
            label = rec.name
            if rec.notes:
                label = f"{rec.name} ({rec.notes})"
            result.append((rec.id, label))
        return result
