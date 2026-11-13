# -*- coding: utf-8 -*-
import re
from odoo import models, fields, api, _
from odoo.exceptions import UserError

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
    pump_id = fields.Integer(
        string="Surtidor / Calle",
        default=0,
        copy=False,
        help="Número de la calle o surtidor del suministro"
    )
    is_albaran = fields.Boolean(
        string="Es Albarán de Crédito",
        default=False,
        copy=False,
        help="Indica si este ticket es un Albarán de suministro a crédito para facturación periódica"
    )
    vehicle_id = fields.Many2one(
        'res.partner.vehicle',
        string="Vehículo / Matrícula",
        domain="[('partner_id', '=', partner_id)]",
        copy=False
    )
    vehicle_plate = fields.Char(
        string="Matrícula",
        copy=False
    )
    vehicle_driver = fields.Char(
        string="Conductor / DNI",
        copy=False
    )

    def init(self):
        super().init()
        # Asegurar impuestos con IVA incluido para ventas TPV y 5 decimales de precisión para combustible
        self.env.cr.execute("""
            UPDATE account_tax
            SET price_include = true
            WHERE type_tax_use = 'sale'
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
        config = self.session_id.config_id or self.config_id
        base_prefix = "TTTR"
        if config and config.sequence_id and config.sequence_id.prefix:
            clean_p = config.sequence_id.prefix.strip().rstrip('/')
            if clean_p:
                base_prefix = clean_p

        seq_code = f"pos.order.annulment.{config.id}" if config else "pos.order.annulment"
        sequence = self.env['ir.sequence'].sudo().search([('code', '=', seq_code)], limit=1)
        if not sequence:
            # Buscar el mayor correlativo existente con este prefijo para continuar la serie
            self.env.cr.execute("""
                SELECT annulment_ref FROM pos_order 
                WHERE annulment_ref IS NOT NULL AND annulment_ref LIKE %s
            """, (f"{base_prefix}_%",))
            existing_refs = [r[0] for r in self.env.cr.fetchall() if r[0]]
            max_num = 0
            for ref_str in existing_refs:
                parts = ref_str.split('_')
                if len(parts) >= 2 and parts[-1].isdigit():
                    num = int(parts[-1])
                    if num > max_num:
                        max_num = num

            next_num = max_num + 1
            sequence = self.env['ir.sequence'].sudo().create({
                'name': f"Secuencia de Anulación TPV {config.name if config else ''}",
                'code': seq_code,
                'prefix': f"{base_prefix}_",
                'padding': 4,
                'number_next': next_num,
                'number_increment': 1,
                'company_id': self.company_id.id if self.company_id else False,
            })

        return sequence.next_by_id()

    def action_annul_ticket(self, reason=None):
        for order in self:
            if order.is_ticket_annulled and order.annulment_ref:
                continue
            if getattr(order, 'is_albaran', False):
                alb_name = order.name.replace('TTTR', 'AVTR', 1) if (order.name and order.name.startswith('TTTR')) else order.name
                ref = order.annulment_ref or f"{alb_name}_"
                order_reason = reason or f"Anulado por Albarán Negativo {ref}"
            elif order.account_move:
                inv_name = order.account_move.name or order.name
                ref = order.annulment_ref or f"{inv_name}_"
                order_reason = reason or f"Anulación de Factura {inv_name}"
            else:
                ref = order.annulment_ref or order._generate_annulment_ref()
                order_reason = reason or 'Anulación de ticket'

            order.write({
                'is_ticket_annulled': True,
                'annulment_ref': ref,
                'annulment_reason': order_reason,
                'annulment_date': fields.Datetime.now(),
            })
        return True

    def action_pos_order_invoice(self):
        res = super().action_pos_order_invoice()
        for order in self:
            if order.account_move:
                ref = order.annulment_ref or order._generate_annulment_ref()
                inv_name = order.account_move.name or 'Factura emitida'
                order.write({
                    'is_ticket_annulled': True,
                    'annulment_ref': ref,
                    'annulment_reason': f"Anulado por canje y emisión de Factura {inv_name}",
                    'annulment_date': fields.Datetime.now(),
                })
        return res

    def action_convert_to_albaran(self, partner_id, vehicle_plate=None, vehicle_driver=None):
        self.ensure_one()
        partner = self.env['res.partner'].browse(int(partner_id))
        if not partner.exists():
            raise UserError(_("Cliente no encontrado."))

        has_credit = (
            getattr(partner, 'customer_payment_mode', 'cash') == 'credit' or
            getattr(partner, 'customer_type', 'ordinary') in ('credit', 'monthly')
        )
        if not has_credit:
            raise UserError(_("El cliente '%s' no tiene modalidad de Crédito autorizada (es cliente de Contado).") % partner.name)

        if getattr(partner, 'credit_blocked', False):
            raise UserError(_("El cliente '%s' tiene el crédito BLOQUEADO por riesgo o impago.") % partner.name)

        # 1. Si tenía factura emitida, cancelarla y desvincularla limpiamente
        if self.account_move:
            move = self.account_move
            try:
                if move.state == 'posted':
                    move.button_draft()
                    move.button_cancel()
                elif move.state == 'draft':
                    move.button_cancel()
            except Exception as e:
                pass
            self.write({'account_move': False})

        # 2. Resetear banderas de anulación (para reactivar el pedido como albarán activo)
        clean_plate = (vehicle_plate or '').strip().upper() if vehicle_plate else False
        clean_driver = (vehicle_driver or '').strip() if vehicle_driver else False

        vals_to_write = {
            'is_ticket_annulled': False,
            'annulment_ref': False,
            'annulment_reason': False,
            'annulment_date': False,
            'partner_id': partner.id,
            'is_albaran': True,
            'state': 'paid',
            'vehicle_plate': clean_plate,
            'vehicle_driver': clean_driver,
        }
        if self.name and self.name.startswith('TTTR'):
            vals_to_write['name'] = self.name.replace('TTTR', 'AVTR', 1)

        if clean_plate:
            existing_veh = self.env['res.partner.vehicle'].search([
                ('partner_id', '=', partner.id),
                ('name', '=', clean_plate)
            ], limit=1)
            if not existing_veh:
                existing_veh = self.env['res.partner.vehicle'].create({
                    'partner_id': partner.id,
                    'name': clean_plate
                })
            vals_to_write['vehicle_id'] = existing_veh.id

        self.write(vals_to_write)

        # 3. Reemplazar líneas de cobro por Cuenta de Cliente (pay_later)
        credit_pm = self.session_id.config_id.payment_method_ids.filtered(lambda m: m.type == 'pay_later')
        if not credit_pm:
            credit_pm = self.env['pos.payment.method'].search([('type', '=', 'pay_later')], limit=1)
        if not credit_pm:
            credit_pm = self.env['pos.payment.method'].search([('name', 'ilike', 'cuenta')], limit=1)

        if credit_pm:
            self.payment_ids.unlink()
            self.env['pos.payment'].create({
                'pos_order_id': self.id,
                'payment_method_id': credit_pm.id,
                'amount': self.amount_total,
                'session_id': self.session_id.id,
                'payment_date': fields.Datetime.now(),
            })
            self.write({
                'amount_paid': self.amount_total,
                'amount_return': 0.0,
            })

        return True

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('is_albaran'):
                curr_name = vals.get('name')
                if curr_name and curr_name.startswith('TTTR'):
                    vals['name'] = curr_name.replace('TTTR', 'AVTR', 1)
        orders = super().create(vals_list)
        for order in orders:
            if order.is_albaran and order.name and order.name.startswith('TTTR'):
                order.write({'name': order.name.replace('TTTR', 'AVTR', 1)})
        return orders

    def _compute_order_name(self):
        name = super()._compute_order_name()
        if self.is_albaran and name and name.startswith('TTTR'):
            return name.replace('TTTR', 'AVTR', 1)
        return name

    @api.model
    def _order_fields(self, ui_order):
        fields = super()._order_fields(ui_order)
        fields['is_albaran'] = ui_order.get('is_albaran', False)
        fields['vehicle_plate'] = ui_order.get('vehicle_plate', False)
        fields['vehicle_driver'] = ui_order.get('vehicle_driver', False)
        if ui_order.get('is_albaran') and ui_order.get('name') and ui_order['name'].startswith('TTTR'):
            fields['name'] = ui_order['name'].replace('TTTR', 'AVTR', 1)
        pump_id = ui_order.get('pump_id', 0)
        if not pump_id:
            for l in ui_order.get('lines', []):
                line_dict = l[2] if isinstance(l, (list, tuple)) and len(l) == 3 else (l if isinstance(l, dict) else {})
                c_note = line_dict.get('customer_note', '') or ''
                m = re.search(r'(?:Calle|Surtidor)\s*[:#]?\s*(\d+)', c_note, re.IGNORECASE)
                if m:
                    pump_id = int(m.group(1))
                    break
        fields['pump_id'] = pump_id
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
                        r['vehicle_plate'] = o.vehicle_plate
                        r['vehicle_driver'] = o.vehicle_driver
                        r['pump_id'] = o.pump_id
        return order_sync_results
