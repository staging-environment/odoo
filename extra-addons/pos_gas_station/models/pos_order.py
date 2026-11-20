# -*- coding: utf-8 -*-
import re
import logging
from odoo import models, fields, api, tools, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class PosOrder(models.Model):
    _inherit = 'pos.order'

    # Índices: estos campos filtran informes masivos de operaciones (ver AGENTS.md)
    name = fields.Char(index=True)
    config_id = fields.Many2one(index=True)

    is_ticket_annulled = fields.Boolean(
        string="Ticket Anulado",
        default=False,
        copy=False,
        index=True,
        help="Indica si este ticket ha sido anulado (por factura o manualmente)"
    )
    annulment_ref = fields.Char(
        string="Ref. Anulación",
        copy=False,
        index=True,
        help="Referencia oficial de la anulación con serie TTTR_"
    )
    annulment_reason = fields.Char(
        string="Motivo Anulación",
        copy=False
    )
    annulment_date = fields.Datetime(
        string="Fecha Anulación",
        copy=False,
        index=True,
    )
    is_extraction = fields.Boolean(
        string="Es Extracción / Calibración",
        default=False,
        copy=False,
        index=True,
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
        index=True,
        help="Número de la calle o surtidor del suministro"
    )
    is_albaran = fields.Boolean(
        string="Es Albarán de Crédito",
        default=False,
        copy=False,
        index=True,
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
        copy=False,
        index=True,
    )
    vehicle_driver = fields.Char(
        string="Conductor / DNI",
        copy=False
    )

    # Trazabilidad: documento negativo (albarán de anulación, rectificativo de
    # sobrante de prepago) -> ticket/albarán original. Enlace real e indexado
    # para informes, en lugar de deducirlo por texto.
    origin_order_id = fields.Many2one(
        'pos.order',
        string="Documento de origen",
        copy=False,
        index=True,
        ondelete='set null',
        readonly=True,
        help="Ticket o albarán original al que anula o rectifica este documento.",
    )
    origin_kind = fields.Selection([
        ('albaran_annulment', 'Albarán negativo de anulación'),
        ('prepay_refund', 'Rectificativo de sobrante de prepago'),
    ], string="Tipo de documento derivado", copy=False, index=True, readonly=True)
    derived_order_ids = fields.One2many(
        'pos.order', 'origin_order_id',
        string="Documentos derivados",
        readonly=True,
    )

    def init(self):
        super().init()
        # Índices compuestos para informes por empresa / estación y rango de fechas
        tools.create_index(self.env.cr, 'pos_order_company_date_idx', 'pos_order', ['company_id', 'date_order'])
        tools.create_index(self.env.cr, 'pos_order_config_date_idx', 'pos_order', ['config_id', 'date_order'])
        tools.create_index(self.env.cr, 'pos_order_partner_date_idx', 'pos_order', ['partner_id', 'date_order'])
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

    def _get_station_prefixes(self, config_id=None):
        STATION_PREFIX_MAP = {
            7: {'ticket': 'TTTR', 'albaran': 'AVTR', 'invoice': 'FTTR'},
            5: {'ticket': 'TTRN', 'albaran': 'AVRN', 'invoice': 'FTRN'},
            2: {'ticket': 'TTRO', 'albaran': 'AVRO', 'invoice': 'FTRO'},
            3: {'ticket': 'TTUTR', 'albaran': 'AVUTR', 'invoice': 'FTUTR'},
            6: {'ticket': 'TTAT', 'albaran': 'AVAT', 'invoice': 'FTAT'},
        }
        cfg = None
        if config_id:
            cfg = self.env['pos.config'].sudo().browse(int(config_id))
        elif hasattr(self, 'config_id') and self.config_id:
            cfg = self.config_id
        elif hasattr(self, 'session_id') and self.session_id and self.session_id.config_id:
            cfg = self.session_id.config_id

        if cfg and cfg.id in STATION_PREFIX_MAP:
            return STATION_PREFIX_MAP[cfg.id]

        if cfg and cfg.sequence_id and cfg.sequence_id.prefix:
            clean_p = cfg.sequence_id.prefix.strip().rstrip('/')
            if clean_p.startswith('TT'):
                suffix = clean_p[2:]
                return {'ticket': clean_p, 'albaran': f"AV{suffix}", 'invoice': f"FT{suffix}"}

        return {'ticket': 'TTTR', 'albaran': 'AVTR', 'invoice': 'FTTR'}

    def _generate_annulment_sequence(self, doc_type='ticket', year=None):
        """
        Genera la referencia correlativa de anulación para el tipo indicado ('ticket', 'albaran', 'invoice').
        Formato: NOMENCLATURA_AÑONUMERO (ej: TTTR_202600001, AVTR_202600001, FTTR_202600001)
        Cada tipo de documento tiene su propio contador independiente y correlativo.
        """
        self.ensure_one()
        config = self.session_id.config_id or self.config_id
        config_id = config.id if config else 7
        prefixes = self._get_station_prefixes(config_id)
        base_pfx = prefixes.get(doc_type, 'TTTR')

        current_year = year or fields.Date.today().year
        seq_code = f"pos.order.annulment.{doc_type}.{config_id}"
        prefix_pattern = f"{base_pfx}_{current_year}"

        sequence = self.env['ir.sequence'].sudo().search([
            ('code', '=', seq_code),
            ('company_id', 'in', [self.company_id.id if self.company_id else False, False])
        ], limit=1)

        domain_like = f"{prefix_pattern}%"
        max_num = 0
        if doc_type == 'invoice':
            self.env.cr.execute("""
                SELECT name FROM account_move WHERE name LIKE %s
                UNION
                SELECT annulment_ref FROM pos_order WHERE annulment_ref LIKE %s
            """, (domain_like, domain_like))
            existing_refs = [r[0] for r in self.env.cr.fetchall() if r[0]]
            for ref_str in existing_refs:
                m = re.search(r'_' + str(current_year) + r'(\d+)$', ref_str)
                if m:
                    num = int(m.group(1))
                    if num > max_num:
                        max_num = num
        elif doc_type == 'albaran':
            self.env.cr.execute("""
                SELECT name FROM pos_order WHERE name LIKE %s
                UNION
                SELECT annulment_ref FROM pos_order WHERE is_albaran = true AND annulment_ref IS NOT NULL AND annulment_ref LIKE %s
            """, (domain_like, domain_like))
            existing_refs = [r[0] for r in self.env.cr.fetchall() if r[0]]
            for ref_str in existing_refs:
                m = re.search(r'_' + str(current_year) + r'(\d+)$', ref_str)
                if m:
                    num = int(m.group(1))
                    if num > max_num:
                        max_num = num
        else:
            self.env.cr.execute("""
                SELECT annulment_ref FROM pos_order 
                WHERE (is_albaran IS NOT TRUE) AND (account_move IS NULL) 
                  AND annulment_ref IS NOT NULL AND annulment_ref LIKE %s
            """, (domain_like,))
            existing_refs = [r[0] for r in self.env.cr.fetchall() if r[0]]
            for ref_str in existing_refs:
                m = re.search(r'_' + str(current_year) + r'(\d+)$', ref_str)
                if m:
                    num = int(m.group(1))
                    if num > max_num:
                        max_num = num

        next_num = max_num + 1

        if not sequence:
            type_label = {'ticket': 'Ticket', 'albaran': 'Albarán', 'invoice': 'Factura'}.get(doc_type, 'Doc')
            sequence = self.env['ir.sequence'].sudo().create({
                'name': f"Secuencia de Anulación {type_label} TPV {config.name if config else ''}",
                'code': seq_code,
                'prefix': f"{base_pfx}_%(year)s",
                'padding': 5,
                'number_next': next_num,
                'number_increment': 1,
                'company_id': self.company_id.id if self.company_id else False,
            })
        else:
            if sequence.number_next <= max_num:
                sequence.sudo().write({'number_next': next_num})

        return sequence.next_by_id()

    def _generate_annulment_ref(self):
        self.ensure_one()
        return self._generate_annulment_sequence('ticket')

    def action_annul_ticket(self, reason=None):
        for order in self:
            if order.is_ticket_annulled and order.annulment_ref:
                continue
            if getattr(order, 'is_albaran', False):
                ref = order.annulment_ref or order._generate_annulment_sequence('albaran')
                order_reason = reason or f"Anulado por Albarán Negativo {ref}"
            elif order.account_move:
                inv_name = order.account_move.name or order.name
                ref = order.annulment_ref or order._generate_annulment_sequence('invoice')
                order_reason = reason or f"Anulación de Factura {inv_name}"
            else:
                ref = order.annulment_ref or order._generate_annulment_sequence('ticket')
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
                clean_inv = re.sub(r'[/_\-\s]', '', order.account_move.name or '')
                was_direct_invoice = order.to_invoice or order.state == 'invoiced'
                vals = {}
                if clean_inv:
                    vals['name'] = clean_inv
                if was_direct_invoice and not ('canje' in (getattr(order, 'annulment_reason', '') or '').lower()):
                    vals.update({
                        'is_ticket_annulled': False,
                        'annulment_ref': False,
                        'annulment_reason': False,
                    })
                elif not was_direct_invoice:
                    ref = order.annulment_ref or order._generate_annulment_ref()
                    vals.update({
                        'is_ticket_annulled': True,
                        'annulment_ref': ref,
                        'annulment_reason': f"Anulado por canje y emisión de Factura {clean_inv or order.account_move.name}",
                        'annulment_date': fields.Datetime.now(),
                    })
                if vals:
                    order.write(vals)
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
        if self.name and re.match(r'^TT[A-Z]+', self.name):
            vals_to_write['name'] = re.sub(r'^TT', 'AV', self.name, count=1)

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
                if curr_name and re.match(r'^TT[A-Z]+', curr_name):
                    vals['name'] = re.sub(r'^TT', 'AV', curr_name, count=1)
        orders = super().create(vals_list)
        for order in orders:
            curr = order.name
            if curr:
                m = re.match(r'^(TT|AV)([A-Z]+)(\d+)$', curr)
                if m:
                    t, st, num = m.groups()
                    if len(num) <= 5:
                        year = order.date_order.year if order.date_order else fields.Date.today().year
                        target_t = 'AV' if order.is_albaran else t
                        order.write({'name': f"{target_t}{st}{year}{int(num):05d}"})
                        continue
            if order.is_albaran and order.name and re.match(r'^TT[A-Z]+', order.name):
                order.write({'name': re.sub(r'^TT', 'AV', order.name, count=1)})
        return orders

    def _compute_order_name(self):
        name = super()._compute_order_name()
        if not name:
            return name
        m = re.match(r'^(TT|AV)([A-Z]+)(\d+)$', name)
        if m:
            t, st, num = m.groups()
            if len(num) <= 5:
                year = fields.Date.today().year
                target_t = 'AV' if self.is_albaran else t
                return f"{target_t}{st}{year}{int(num):05d}"
        if self.is_albaran and re.match(r'^TT[A-Z]+', name):
            return re.sub(r'^TT', 'AV', name, count=1)
        return name

    @api.model
    @api.model
    def _utrecar_fix_fuel_line_qty(self, ui_order):
        """Corrige líneas de combustible con litros x1000 y precio /1000 (p. ej. 6897 L a 0,00145 €).

        El total de la línea no cambia: se divide la cantidad entre 1000 y se multiplica el precio por 1000.
        """
        for l in ui_order.get('lines', []) or []:
            vals = l[2] if isinstance(l, (list, tuple)) and len(l) == 3 and isinstance(l[2], dict) else None
            if not vals:
                continue
            note = vals.get('customer_note') or ''
            try:
                qty = float(vals.get('qty') or 0.0)
                price = float(vals.get('price_unit') or 0.0)
            except (TypeError, ValueError):
                continue
            if 'Calle' in note and abs(qty) >= 100 and 0 < abs(price) < 0.01:
                vals['qty'] = qty / 1000.0
                vals['price_unit'] = price * 1000.0
                _logger.warning("Utrecar: corregida línea de combustible x1000 (%s L -> %s L) en %s",
                                qty, vals['qty'], ui_order.get('name'))

    def _order_fields(self, ui_order):
        self._utrecar_fix_fuel_line_qty(ui_order)
        fields = super()._order_fields(ui_order)
        fields['is_albaran'] = ui_order.get('is_albaran', False)
        raw_plate = ui_order.get('vehicle_plate')
        clean_plate = str(raw_plate).strip().upper() if raw_plate else False
        fields['vehicle_plate'] = clean_plate
        fields['vehicle_driver'] = ui_order.get('vehicle_driver', False)
        if ui_order.get('is_albaran') and ui_order.get('name') and re.match(r'^TT[A-Z]+', ui_order['name']):
            fields['name'] = re.sub(r'^TT', 'AV', ui_order['name'], count=1)
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

    def _prepare_invoice_vals(self):
        vals = super()._prepare_invoice_vals()
        if self.vehicle_plate:
            vals['vehicle_plate'] = self.vehicle_plate
        if self.vehicle_id:
            vals['vehicle_id'] = self.vehicle_id.id
        if self.vehicle_driver:
            vals['vehicle_driver'] = self.vehicle_driver
        return vals

    def _utrecar_find_origin(self):
        """Busca el documento original de un albarán negativo o rectificativo.
        Devuelve (pedido_original, tipo) o (vacío, False)."""
        self.ensure_one()
        empty = self.browse()
        same_company = [('company_id', '=', self.company_id.id), ('id', '!=', self.id)]
        # 1) Albarán negativo de anulación: nota "... (Ref: AVTR2026xxxxx)"
        if self.is_albaran and self.amount_total < 0:
            m = re.search(r'Ref:\s*([A-Z0-9_]+)', self.note or '')
            if m:
                orig = self.search(same_company + [('name', '=', m.group(1))], limit=1)
                if orig:
                    return orig, 'albaran_annulment'
        # 2) Rectificativo de sobrante de prepago: nota de línea "... | Rectifica: TTTR2026xxxxx"
        notes = ' '.join((l.customer_note or '') for l in self.lines)
        if self.amount_total < 0 and 'Sobrante de Prefijado' in notes:
            m = re.search(r'Rectifica:\s*([A-Z]{2,}[A-Z0-9_]*\d+)', notes)
            if m:
                orig = self.search(same_company + [('name', '=', m.group(1))], limit=1)
                if orig:
                    return orig, 'prepay_refund'
            # Rectificativos antiguos sin referencia: prepago de la misma calle e importe en el turno
            m_pump = re.search(r'Calle\s*(\d+)', notes)
            m_pre = re.search(r'Prefijado:\s*([\d.,]+)\s*€', notes)
            if m_pump and m_pre and self.session_id:
                key = f"Calle {m_pump.group(1)} [Prepago: {float(m_pre.group(1).replace(',', '.')):.2f}"
                cands = self.search(same_company + [
                    ('session_id', '=', self.session_id.id), ('amount_total', '>', 0),
                    ('date_order', '<=', self.date_order),
                ]).filtered(lambda x: any(key in (l.customer_note or '') for l in x.lines))
                if cands:
                    return cands.sorted(lambda x: (x.date_order, x.id))[-1], 'prepay_refund'
        return empty, False

    def _utrecar_link_origins(self):
        """Rellena origin_order_id / origin_kind donde falte. Devuelve cuántos enlazó."""
        linked = 0
        for order in self.filtered(lambda o: not o.origin_order_id and o.amount_total < 0):
            orig, kind = order._utrecar_find_origin()
            if orig:
                order.sudo().write({'origin_order_id': orig.id, 'origin_kind': kind})
                linked += 1
        return linked

    @api.model
    def create_from_ui(self, orders, draft=False):
        order_sync_results = super().create_from_ui(orders, draft=draft)
        if order_sync_results:
            order_ids = [r['id'] for r in order_sync_results if isinstance(r, dict) and 'id' in r]
            if order_ids:
                orders_records = self.browse(order_ids)
                try:
                    orders_records._utrecar_link_origins()
                except Exception as e:  # nunca bloquear la venta por la trazabilidad
                    _logger.warning("No se pudo enlazar el documento de origen: %s", e)
                order_map = {o.id: o for o in orders_records}
                for r in order_sync_results:
                    if isinstance(r, dict) and r.get('id') in order_map:
                        o = order_map[r['id']]
                        if o.account_move and o.account_move.name:
                            clean_inv = re.sub(r'[/_\-\s]', '', o.account_move.name)
                            if clean_inv and o.name != clean_inv:
                                o.write({
                                    'name': clean_inv,
                                    'is_ticket_annulled': False,
                                    'annulment_ref': False,
                                    'annulment_reason': False,
                                })
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


class PosOrderLine(models.Model):
    _inherit = 'pos.order.line'

    # Índices para informes de ventas por producto / carburante y empresa
    product_id = fields.Many2one(index=True)
    company_id = fields.Many2one(index=True)
