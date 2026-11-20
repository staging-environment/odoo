# -*- coding: utf-8 -*-
"""Tanques de carburante por estación y descuento del carburante del tanque concreto.

- Un tanque es una ubicación interna del almacén de la estación con su número en el
  concentrador de pista (SDES: manguera -> tanque) y el carburante que contiene.
- Cada línea de carburante del TPV guarda el número de tanque que informó el surtidor;
  al generar los movimientos de stock del turno, el carburante sale de ese tanque.
- Si una línea no trae tanque (p. ej. prepago), sale del tanque del mismo carburante
  que tenga existencias (el más antiguo primero).
"""
import logging
from collections import defaultdict

from odoo import api, fields, models
from odoo.tools import float_compare

_logger = logging.getLogger(__name__)


class StockLocation(models.Model):
    _inherit = 'stock.location'

    utrecar_tank_number = fields.Integer(
        string='Nº de tanque en pista',
        index=True,
        help='Número del tanque en el concentrador de pista (SDES). Cada manguera '
             'de cada surtidor está asociada a un número de tanque.',
    )
    utrecar_tank_product_id = fields.Many2one(
        'product.product',
        string='Carburante del tanque',
        index=True,
    )


class PosOrderLine(models.Model):
    _inherit = 'pos.order.line'

    tank_number = fields.Integer(
        string='Nº de tanque',
        index=True,
        copy=False,
        help='Tanque del que salió el carburante, según el surtidor.',
    )
    tank_location_id = fields.Many2one(
        'stock.location',
        string='Tanque',
        compute='_compute_tank_location_id',
        store=True,
        index=True,
    )

    @api.depends('tank_number', 'product_id', 'order_id.config_id')
    def _compute_tank_location_id(self):
        Location = self.env['stock.location'].sudo()
        for line in self:
            config = line.order_id.config_id
            wh = config.warehouse_id or config.picking_type_id.warehouse_id
            tank = Location.browse()
            if wh and line.product_id:
                tanks = Location.search([
                    ('warehouse_id', '=', wh.id),
                    ('usage', '=', 'internal'),
                    ('utrecar_tank_number', '!=', 0),
                ])
                if line.tank_number:
                    tank = tanks.filtered(lambda t: t.utrecar_tank_number == line.tank_number)[:1]
                if not tank:
                    same_fuel = tanks.filtered(lambda t: t.utrecar_tank_product_id == line.product_id)
                    if len(same_fuel) == 1:
                        tank = same_fuel
            line.tank_location_id = tank


class StockMove(models.Model):
    _inherit = 'stock.move'

    def _utrecar_fuel_tanks(self, base_location):
        """Tanques (ubicaciones con número) de este carburante bajo la ubicación dada."""
        self.ensure_one()
        return self.env['stock.location'].sudo().search([
            ('id', 'child_of', base_location.id),
            ('usage', '=', 'internal'),
            ('utrecar_tank_number', '!=', 0),
            ('utrecar_tank_product_id', '=', self.product_id.id),
        ], order='utrecar_tank_number')

    def _add_mls_related_to_order(self, related_order_lines, are_qties_done=True):
        tank_moves = self.browse()
        if are_qties_done:
            for move in self:
                if move.product_id.type != 'product' or move.product_id.tracking != 'none':
                    continue
                base = move.location_id if move.location_id.usage == 'internal' else move.location_dest_id
                if base.usage != 'internal':
                    continue
                lines = related_order_lines.filtered(lambda l: l.product_id == move.product_id)
                if any(l.tank_location_id for l in lines) or move._utrecar_fuel_tanks(base):
                    tank_moves |= move
        res = super(StockMove, self - tank_moves)._add_mls_related_to_order(related_order_lines, are_qties_done)
        for move in tank_moves:
            try:
                move._utrecar_create_tank_move_lines(
                    related_order_lines.filtered(lambda l: l.product_id == move.product_id))
            except Exception:
                # Nunca bloquear el cierre de turno: si algo falla, comportamiento estándar
                _logger.exception("Descuento por tanque fallido en %s; se usa el estándar", move.display_name)
                move.move_line_ids.unlink()
                move.quantity = move.product_uom_qty
        return res

    def _utrecar_create_tank_move_lines(self, lines):
        self.ensure_one()
        rounding = self.product_uom.rounding
        outgoing = self.location_id.usage == 'internal'
        base = self.location_id if outgoing else self.location_dest_id
        loc_key = 'location_id' if outgoing else 'location_dest_id'

        # 1) Lo que el surtidor dijo de qué tanque salió
        by_tank = defaultdict(float)
        for line in lines:
            tank = line.tank_location_id
            if tank and tank.parent_path.startswith(base.parent_path):
                by_tank[tank] += abs(line.qty)

        total = self.product_uom_qty
        assigned = 0.0
        vals_list = []
        for tank, qty in by_tank.items():
            qty = min(qty, total - assigned)
            if float_compare(qty, 0, precision_rounding=rounding) <= 0:
                continue
            vals = self._prepare_move_line_vals(quantity=qty)
            vals[loc_key] = tank.id
            vals_list.append(vals)
            assigned += qty

        # 2) Resto sin tanque conocido: tanques de ese carburante (FIFO por existencias)
        rest = total - assigned
        if float_compare(rest, 0, precision_rounding=rounding) > 0:
            tanks = self._utrecar_fuel_tanks(base)
            if outgoing and tanks:
                quants = self.env['stock.quant'].sudo().search([
                    ('product_id', '=', self.product_id.id),
                    ('location_id', 'in', tanks.ids),
                    ('quantity', '>', 0),
                ], order='in_date, id')
                for quant in quants:
                    if float_compare(rest, 0, precision_rounding=rounding) <= 0:
                        break
                    available = quant.quantity - quant.reserved_quantity
                    take = min(rest, available)
                    if float_compare(take, 0, precision_rounding=rounding) <= 0:
                        continue
                    vals = self._prepare_move_line_vals(quantity=take)
                    vals[loc_key] = quant.location_id.id
                    vals_list.append(vals)
                    rest -= take
            if float_compare(rest, 0, precision_rounding=rounding) > 0:
                vals = self._prepare_move_line_vals(quantity=rest)
                vals[loc_key] = (tanks[:1] or base).id
                vals_list.append(vals)

        self.move_line_ids.unlink()
        self.env['stock.move.line'].create(vals_list)
