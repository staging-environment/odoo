# -*- coding: utf-8 -*-
from odoo import models, api, fields, _
from odoo.exceptions import UserError
import pytz

class PosConfig(models.Model):
    _inherit = 'pos.config'

    @api.depends('session_ids')
    def _compute_last_session(self):
        PosSession = self.env['pos.session']
        for pos_config in self:
            session = PosSession.search_read(
                [('config_id', '=', pos_config.id), ('state', '=', 'closed'), ('stop_at', '!=', False)],
                ['cash_register_balance_end_real', 'stop_at'],
                order='stop_at desc', limit=1)
            if session and session[0].get('stop_at'):
                try:
                    timezone = pytz.timezone(self._context.get('tz') or self.env.user.tz or 'UTC')
                    stop_at = session[0]['stop_at']
                    if hasattr(stop_at, 'astimezone'):
                        pos_config.last_session_closing_date = stop_at.astimezone(timezone).date()
                    else:
                        pos_config.last_session_closing_date = fields.Date.today()
                    pos_config.last_session_closing_cash = session[0].get('cash_register_balance_end_real') or 0.0
                except Exception:
                    pos_config.last_session_closing_date = fields.Date.today()
                    pos_config.last_session_closing_cash = 0.0
            else:
                pos_config.last_session_closing_cash = 0.0
                pos_config.last_session_closing_date = False

    def unlink(self):
        for config in self:
            orders_count = self.env['pos.order'].sudo().search_count([('config_id', '=', config.id)])
            if orders_count > 0:
                raise UserError(_(
                    'No se puede eliminar la estación "%s" porque contiene %s pedidos/tickets de venta registrados. '
                    'Para garantizar la trazabilidad contable no es posible borrarla.'
                ) % (config.name, orders_count))
            empty_sessions = self.env['pos.session'].sudo().search([('config_id', '=', config.id)])
            for s in empty_sessions:
                s_orders = self.env['pos.order'].sudo().search_count([('session_id', '=', s.id)])
                if s_orders == 0:
                    if s.state == 'opening_control':
                        s.write({'state': 'closed'})
                    s.unlink()
        return super(PosConfig, self).unlink()
