import logging
from odoo import models, fields, api, _

_logger = logging.getLogger(__name__)

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

    invoice_delivery_method = fields.Selection([
        ('email', 'Correo electrónico'),
        ('paper', 'Factura en papel'),
    ], string='Modo de Entrega', default='email', copy=False, help="Selecciona si enviar automáticamente por correo o entregar en papel.")

    invoice_partner_email = fields.Char(
        string='Correo para Factura',
        copy=False,
        help="Correo electrónico de destino para el envío automático. Por defecto carga el correo del cliente."
    )

    invoice_email_sent = fields.Boolean(
        string='Enviada por Email',
        copy=False,
        readonly=True,
        default=False,
        help="Indica si la factura ha sido enviada por correo electrónico."
    )

    @api.onchange('partner_id')
    def _onchange_partner_id_delivery(self):
        if self.partner_id:
            if self.partner_id.invoice_delivery_method:
                self.invoice_delivery_method = self.partner_id.invoice_delivery_method
            if self.partner_id.email:
                self.invoice_partner_email = self.partner_id.email
            if self.vehicle_id and self.vehicle_id.partner_id != self.partner_id:
                self.vehicle_id = False

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

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            partner_id = vals.get('partner_id')
            plate = vals.get('vehicle_plate')
            vehicle_id = vals.get('vehicle_id')
            
            # Default email and delivery method from partner if not given
            if partner_id:
                partner = self.env['res.partner'].browse(partner_id)
                if partner.exists():
                    if 'invoice_delivery_method' not in vals and partner.invoice_delivery_method:
                        vals['invoice_delivery_method'] = partner.invoice_delivery_method
                    if 'invoice_partner_email' not in vals and partner.email:
                        vals['invoice_partner_email'] = partner.email

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

    def action_post(self):
        res = super().action_post()
        for move in self:
            if move.is_invoice(include_receipts=False):
                move._handle_auto_invoice_dispatch()
        return res

    def _handle_auto_invoice_dispatch(self):
        self.ensure_one()
        # If paper delivery requested
        if self.invoice_delivery_method == 'paper':
            self.message_post(
                body=_("📄 <strong>Factura en Papel:</strong> El cliente ha solicitado entrega en papel. No se envía por correo.")
            )
            if self.env.user and self.env.user.partner_id:
                self.env['bus.bus']._sendone(
                    self.env.user.partner_id,
                    'simple_notification',
                    {
                        'title': _('Factura en Papel'),
                        'message': _('La factura %s está configurada para entrega física en papel.') % (self.name or ''),
                        'type': 'info',
                        'sticky': False,
                    }
                )
            return

        # If email delivery
        target_email = (self.invoice_partner_email or self.partner_id.email or '').strip()
        if not target_email:
            self.message_post(
                body=_("⚠️ <strong>Atención:</strong> No se pudo enviar automáticamente la factura por correo porque el cliente no tiene una dirección de email configurada.")
            )
            if self.env.user and self.env.user.partner_id:
                self.env['bus.bus']._sendone(
                    self.env.user.partner_id,
                    'simple_notification',
                    {
                        'title': _('Sin Correo Electrónico'),
                        'message': _('No se pudo enviar la factura %s: falta indicar el correo.') % (self.name or ''),
                        'type': 'warning',
                        'sticky': True,
                    }
                )
            return

        # Locate mail template
        template = self.env.ref('account.email_template_edi_invoice', raise_if_not_found=False)
        if not template:
            template = self.env['mail.template'].search([('model', '=', 'account.move')], limit=1)

        if template:
            try:
                email_values = {'email_to': target_email}
                template.send_mail(self.id, force_send=True, email_values=email_values)
                self.invoice_email_sent = True
                
                # Register in chatter
                self.message_post(
                    body=_("📧 <strong>Factura enviada automáticamente:</strong> Enviada por correo a <code>%s</code> con el PDF adjunto.") % target_email
                )
                
                # Interactive notification banner in Odoo
                if self.env.user and self.env.user.partner_id:
                    self.env['bus.bus']._sendone(
                        self.env.user.partner_id,
                        'simple_notification',
                        {
                            'title': _('¡Factura Enviada con Éxito!'),
                            'message': _('La factura %s se ha enviado por correo a %s.') % (self.name or '', target_email),
                            'type': 'success',
                            'sticky': False,
                        }
                    )
            except Exception as e:
                _logger.error("Error al enviar factura por correo automáticamente: %s", str(e))
                self.message_post(
                    body=_("❌ <strong>Error en el envío automático:</strong> %s") % str(e)
                )
