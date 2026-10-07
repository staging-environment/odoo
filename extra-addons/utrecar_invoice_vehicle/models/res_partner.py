from odoo import models, fields, api

class ResPartner(models.Model):
    _inherit = 'res.partner'

    vehicle_ids = fields.One2many('res.partner.vehicle', 'partner_id', string='Vehículos / Matrículas')
    vehicle_count = fields.Integer(string='Vehículos', compute='_compute_vehicle_count')

    invoice_delivery_method = fields.Selection([
        ('email', 'Correo electrónico'),
        ('paper', 'Factura en papel'),
    ], string='Entrega de Facturas', default='email', tracking=True, help='Preferencia por defecto para el envío de facturas a este cliente.')

    # Gestión Comercial (Crédito vs Contado y Periodicidad)
    customer_payment_mode = fields.Selection([
        ('cash', 'Contado (Pago en Pista)'),
        ('credit', 'Crédito (Facturación Aplazada / Flotas)'),
    ], string='Modalidad de Pago', default='cash', required=True, tracking=True, help='Modalidad de pago del cliente. Solo modificable desde Gestión/Backoffice.')

    invoice_periodicity = fields.Selection([
        ('daily', 'Diaria / Por operación (Albarán/Ticket)'),
        ('decadal', 'Decenal (Días 10, 20 y 30)'),
        ('biweekly', 'Quincenal (Días 15 y 30)'),
        ('monthly', 'Mensual (Fin de Mes / Agrupada)'),
    ], string='Periodicidad de Facturación', default='daily', required=True, tracking=True, help='Frecuencia con la que se generan las facturas para este cliente.')

    invoice_closing_day = fields.Integer(
        string='Día de Cierre de Facturación',
        default=31,
        help='Día del mes en que se ejecuta la emisión de la factura agrupada (ej: 31 para fin de mes).'
    )

    credit_limit_amount = fields.Float(
        string='Límite de Crédito (€)',
        default=0.0,
        tracking=True,
        help='Crédito máximo autorizado para repostajes y compras durante el ciclo de facturación.'
    )

    credit_blocked = fields.Boolean(
        string='Bloqueo de Crédito',
        default=False,
        tracking=True,
        help='Si está marcado, se bloquea el repostaje a crédito en pista por riesgo o impago.'
    )

    payment_method_desc = fields.Char(
        string='Forma de Pago Habitual',
        help='Ej: Domiciliación Bancaria SEPA, Transferencia Bancaria 30 días, Pagaré, etc.'
    )

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
