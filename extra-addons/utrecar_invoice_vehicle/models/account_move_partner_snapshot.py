import logging
from odoo import models, fields, api

_logger = logging.getLogger(__name__)


class AccountMovePartnerSnapshot(models.Model):
    """Copia inmutable de los datos fiscales del cliente en el momento de emitir la factura.

    El PDF de la factura usa siempre esta copia, de modo que si en el futuro se cambia
    la dirección, el NIF o el nombre del cliente, las facturas ya emitidas no varían.
    """
    _inherit = 'account.move'

    inv_snap_set = fields.Boolean(string='Datos fiscales congelados', copy=False, readonly=True)
    inv_snap_date = fields.Datetime(string='Fecha de captura de datos', copy=False, readonly=True)
    inv_snap_name = fields.Char(string='Cliente (en factura)', copy=False, readonly=True)
    inv_snap_vat = fields.Char(string='NIF/CIF (en factura)', copy=False, readonly=True)
    inv_snap_street = fields.Char(string='Dirección (en factura)', copy=False, readonly=True)
    inv_snap_street2 = fields.Char(string='Dirección 2 (en factura)', copy=False, readonly=True)
    inv_snap_zip = fields.Char(string='C.P. (en factura)', copy=False, readonly=True)
    inv_snap_city = fields.Char(string='Población (en factura)', copy=False, readonly=True)
    inv_snap_state = fields.Char(string='Provincia (en factura)', copy=False, readonly=True)
    inv_snap_country = fields.Char(string='País (en factura)', copy=False, readonly=True)

    def _utrecar_partner_snapshot_vals(self):
        self.ensure_one()
        partner = self.partner_id
        commercial = partner.commercial_partner_id or partner
        return {
            'inv_snap_set': True,
            'inv_snap_date': fields.Datetime.now(),
            'inv_snap_name': partner.display_name or partner.name or '',
            'inv_snap_vat': commercial.vat or partner.vat or '',
            'inv_snap_street': partner.street or '',
            'inv_snap_street2': partner.street2 or '',
            'inv_snap_zip': partner.zip or '',
            'inv_snap_city': partner.city or '',
            'inv_snap_state': partner.state_id.name or '',
            'inv_snap_country': partner.country_id.name or '',
        }

    def _utrecar_freeze_partner_data(self):
        for move in self:
            if move.inv_snap_set or not move.partner_id:
                continue
            if not move.is_sale_document(include_receipts=True):
                continue
            move.sudo().write(move._utrecar_partner_snapshot_vals())

    def _post(self, soft=True):
        posted = super()._post(soft=soft)
        posted._utrecar_freeze_partner_data()
        return posted

    def button_draft(self):
        # Al volver a borrador se permite corregir el cliente; se recapturan los datos al confirmar de nuevo
        res = super().button_draft()
        self.sudo().write({'inv_snap_set': False})
        return res

    @api.model
    def _utrecar_backfill_partner_snapshot(self):
        """Congela los datos de cliente de las facturas ya emitidas (con los datos actuales de la ficha)."""
        moves = self.sudo().search([
            ('state', '=', 'posted'),
            ('move_type', 'in', ('out_invoice', 'out_refund', 'out_receipt')),
            ('inv_snap_set', '=', False),
            ('partner_id', '!=', False),
        ])
        moves._utrecar_freeze_partner_data()
        _logger.info("Utrecar: datos fiscales de cliente congelados en %s facturas existentes", len(moves))
