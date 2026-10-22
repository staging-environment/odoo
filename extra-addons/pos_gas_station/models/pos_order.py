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
    is_extraction = fields.Boolean(
        string="Es Extracción / Calibración",
        default=False,
        copy=False,
        help="Indica si este ticket corresponde a una extracción o retorno a depósito (no resta existencias ni suma cobro a caja)"
    )
    extraction_reason = fields.Char(
        string="Motivo de Extracción",
        copy=False,
        default="Retorno a depósito / Calibración"
    )
    extraction_liters = fields.Float(
        string="Litros Extraídos",
        digits='Product Unit of Measure',
        default=0.0
    )
    extraction_date = fields.Datetime(
        string="Fecha de Extracción",
        copy=False
    )
    extraction_pump_id = fields.Integer(
        string="Surtidor / Calle Extracción",
        default=0
    )
    is_albaran = fields.Boolean(
        string="Es Albarán de Crédito",
        default=False,
        copy=False,
        help="Indica si este ticket es un Albarán de suministro a crédito para facturación periódica"
    )

    def init(self):
        super().init()
        # Asegurar impuestos con IVA incluido para ventas TPV y 5 decimales de precisión para combustible
        self.env.cr.execute("""
            UPDATE account_tax
            SET price_include = true
            WHERE type_tax_use = 'sale'
              AND (name::text ILIKE '%15%%' OR name::text ILIKE '%IVA%')
              AND price_include = false;

            UPDATE decimal_precision
            SET digits = 5
            WHERE name = 'Product Price' AND digits < 5;
        """)

    def _create_order_picking(self):
        self.ensure_one()
        if self.is_extraction:
            return
        return super()._create_order_picking()

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

    @api.model
    def _order_fields(self, ui_order):
        fields = super()._order_fields(ui_order)
        fields['is_albaran'] = ui_order.get('is_albaran', False)
        return fields

    @api.model
    def create_from_ui(self, orders, draft=False):
        order_sync_results = super().create_from_ui(orders, draft=draft)
        if order_sync_results:
            order_ids = [r['id'] for r in order_sync_results if isinstance(r, dict) and 'id' in r]
            if order_ids:
                orders_records = self.browse(order_ids)
                order_map = {o.id: o for o in orders_records}
                for r in order_sync_results:
                    if isinstance(r, dict) and r.get('id') in order_map:
                        o = order_map[r['id']]
                        r['name'] = o.name
                        r['ticket_name'] = o.name
                        r['is_ticket_annulled'] = o.is_ticket_annulled
                        r['annulment_ref'] = o.annulment_ref
                        r['is_extraction'] = o.is_extraction
                        r['extraction_liters'] = o.extraction_liters
                        r['is_albaran'] = o.is_albaran
        return order_sync_results
