from odoo import models, fields, api

class ResPartner(models.Model):
    _inherit = 'res.partner'

    vehicle_ids = fields.One2many('res.partner.vehicle', 'partner_id', string='Vehículos / Matrículas')
    vehicle_count = fields.Integer(string='Vehículos', compute='_compute_vehicle_count')

    invoice_delivery_method = fields.Selection([
        ('email', 'Correo electrónico'),
        ('paper', 'Factura en papel'),
    ], string='Entrega de Facturas', default='email', tracking=True, help='Preferencia por defecto para el envío de facturas a este cliente.')

    # Gestión Comercial (Crédito, Mensual, Ordinaria)
    customer_type = fields.Selection([
        ('credit', 'Crédito'),
        ('monthly', 'Mensual'),
        ('ordinary', 'Ordinaria'),
    ], string='Tipo de Facturación / Cliente', default='ordinary', tracking=True,
       help='Configuración del cliente: Crédito (genera albarán en cobro), Mensual (facturación agrupada mensual), u Ordinaria (contado/ticket).')

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

    @api.onchange('customer_type')
    def _onchange_customer_type(self):
        if self.customer_type == 'credit':
            self.customer_payment_mode = 'credit'
            self.invoice_periodicity = 'daily'
        elif self.customer_type == 'monthly':
            self.customer_payment_mode = 'credit'
            self.invoice_periodicity = 'monthly'
        elif self.customer_type == 'ordinary':
            self.customer_payment_mode = 'cash'
            self.invoice_periodicity = 'daily'

    @api.onchange('customer_payment_mode', 'invoice_periodicity')
    def _onchange_payment_mode_periodicity(self):
        if self.customer_payment_mode == 'credit':
            if self.invoice_periodicity == 'monthly':
                self.customer_type = 'monthly'
            else:
                self.customer_type = 'credit'
        else:
            self.customer_type = 'ordinary'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'customer_type' in vals:
                ctype = vals['customer_type']
                if ctype == 'credit':
                    vals.setdefault('customer_payment_mode', 'credit')
                    vals.setdefault('invoice_periodicity', 'daily')
                elif ctype == 'monthly':
                    vals.setdefault('customer_payment_mode', 'credit')
                    vals.setdefault('invoice_periodicity', 'monthly')
                elif ctype == 'ordinary':
                    vals.setdefault('customer_payment_mode', 'cash')
                    vals.setdefault('invoice_periodicity', 'daily')
        return super().create(vals_list)

    def write(self, vals):
        if 'customer_type' in vals:
            ctype = vals['customer_type']
            if ctype == 'credit':
                vals['customer_payment_mode'] = 'credit'
            elif ctype == 'monthly':
                vals['customer_payment_mode'] = 'credit'
                vals['invoice_periodicity'] = 'monthly'
            elif ctype == 'ordinary':
                vals['customer_payment_mode'] = 'cash'
        return super().write(vals)

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
