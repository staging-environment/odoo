from odoo import models, fields, api

class AccountMove(models.Model):
    _inherit = 'account.move'

    vehicle_id = fields.Many2one(
        'res.partner.vehicle',
        string='Vehículo / Matrícula',
        domain="[('partner_id', '=', partner_id)]",
        copy=False,
        help="Selecciona o crea un vehículo vinculado a este cliente."
    )
    vehicle_plate = fields.Char(
        string='Matrícula',
        copy=False,
        index=True,
        help="Matrícula del vehículo. Si se introduce una nueva, se guardará automáticamente en la ficha del cliente."
    )
    vehicle_mileage = fields.Integer(
        string='Kilómetros',
        copy=False,
        help="Kilometraje actual del vehículo en la factura."
    )
    vehicle_driver = fields.Char(
        string='Conductor',
        copy=False,
        help="Nombre del conductor (texto libre)."
    )

    @api.onchange('vehicle_id')
    def _onchange_vehicle_id(self):
        if self.vehicle_id:
            self.vehicle_plate = self.vehicle_id.name

    @api.onchange('vehicle_plate')
    def _onchange_vehicle_plate(self):
        if self.vehicle_plate:
            clean_plate = str(self.vehicle_plate).strip().upper()
            self.vehicle_plate = clean_plate
            if self.partner_id:
                vehicle = self.env['res.partner.vehicle'].search([
                    ('partner_id', '=', self.partner_id.id),
                    ('name', '=', clean_plate)
                ], limit=1)
                if vehicle:
                    self.vehicle_id = vehicle.id
                else:
                    self.vehicle_id = False
        else:
            self.vehicle_id = False

    @api.onchange('partner_id')
    def _onchange_partner_id_vehicle(self):
        if self.vehicle_id and self.vehicle_id.partner_id != self.partner_id:
            self.vehicle_id = False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            partner_id = vals.get('partner_id')
            plate = vals.get('vehicle_plate')
            vehicle_id = vals.get('vehicle_id')
            if plate and partner_id:
                clean_plate = str(plate).strip().upper()
                vals['vehicle_plate'] = clean_plate
                vehicle = self.env['res.partner.vehicle'].search([
                    ('partner_id', '=', partner_id),
                    ('name', '=', clean_plate)
                ], limit=1)
                if not vehicle:
                    vehicle = self.env['res.partner.vehicle'].create({
                        'name': clean_plate,
                        'partner_id': partner_id,
                    })
                vals['vehicle_id'] = vehicle.id
            elif vehicle_id and not plate:
                veh = self.env['res.partner.vehicle'].browse(vehicle_id)
                if veh.exists():
                    vals['vehicle_plate'] = veh.name
        return super().create(vals_list)

    def write(self, vals):
        for move in self:
            partner_id = vals.get('partner_id', move.partner_id.id if move.partner_id else False)
            plate = vals.get('vehicle_plate', move.vehicle_plate)
            
            if ('vehicle_plate' in vals or 'partner_id' in vals) and plate and partner_id:
                clean_plate = str(plate).strip().upper()
                vals['vehicle_plate'] = clean_plate
                vehicle = self.env['res.partner.vehicle'].search([
                    ('partner_id', '=', partner_id),
                    ('name', '=', clean_plate)
                ], limit=1)
                if not vehicle:
                    vehicle = self.env['res.partner.vehicle'].create({
                        'name': clean_plate,
                        'partner_id': partner_id,
                    })
                vals['vehicle_id'] = vehicle.id
            elif 'vehicle_id' in vals and vals.get('vehicle_id') and 'vehicle_plate' not in vals:
                veh = self.env['res.partner.vehicle'].browse(vals['vehicle_id'])
                if veh.exists():
                    vals['vehicle_plate'] = veh.name
        return super().write(vals)
