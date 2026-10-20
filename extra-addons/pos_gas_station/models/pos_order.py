# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class PosOrder(models.Model):
    _inherit = 'pos.order'

    is_ticket_annulled = fields.Boolean(
        string="Ticket Anulado",
        default=False,
        copy=False,
        help="Indica si este ticket ha sido anulado (por factura o manualmente)"
    )
    annulment_ref = fields.Char(
        string="Ref. Anulación",
        copy=False,
        help="Referencia oficial de la anulación con serie TTTR_"
    )
    annulment_reason = fields.Char(
        string="Motivo Anulación",
        copy=False
    )
    annulment_date = fields.Datetime(
        string="Fecha Anulación",
        copy=False
    )

    def _generate_annulment_ref(self):
        self.ensure_one()
        orig_name = self.name or ''
        digits = ''.join(c for c in orig_name if c.isdigit())
        if not digits:
            digits = str(self.id).zfill(4)
        else:
            digits = digits[-4:].zfill(4)
        return f"TTTR_{digits}"

    def action_annul_ticket(self, reason=None):
        for order in self:
            if order.is_ticket_annulled:
                continue
            ref = order._generate_annulment_ref()
            order.write({
                'is_ticket_annulled': True,
                'annulment_ref': ref,
                'annulment_reason': reason or 'Anulación de ticket',
                'annulment_date': fields.Datetime.now(),
            })
        return True

    def action_pos_order_invoice(self):
        res = super().action_pos_order_invoice()
        for order in self:
            if order.account_move:
                ref = order._generate_annulment_ref()
                inv_name = order.account_move.name or 'Factura emitida'
                order.write({
                    'is_ticket_annulled': True,
                    'annulment_ref': ref,
                    'annulment_reason': f"Anulado por canje y emisión de Factura {inv_name}",
                    'annulment_date': fields.Datetime.now(),
                })
        return res
