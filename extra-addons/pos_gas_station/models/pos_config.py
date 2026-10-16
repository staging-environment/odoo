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
            associated_records = []

            # 1. Turnos y Sesiones del TPV (pos.session)
            sessions = self.env['pos.session'].sudo().search([('config_id', '=', config.id)])
            if sessions:
                active_sessions = sessions.filtered(lambda s: s.state in ['opened', 'opening_control'])
                if active_sessions:
                    cashiers = ", ".join(set(active_sessions.mapped('user_id.name')))
                    associated_records.append(
                        _("• %d turno(s)/sesión(es) de caja (¡Turno actualmente ABIERTO por: %s!)") % (len(sessions), cashiers)
                    )
                else:
                    associated_records.append(
                        _("• %d turno(s)/sesión(es) de caja registrados") % len(sessions)
                    )

            # 2. Tickets y Pedidos de venta (pos.order)
            orders = self.env['pos.order'].sudo().search([('config_id', '=', config.id)])
            if orders:
                associated_records.append(
                    _("• %d tickets y pedidos de venta") % len(orders)
                )

                # 3. Facturas vinculadas (account.move)
                invoices = orders.mapped('account_move').filtered(lambda m: m.exists())
                if invoices:
                    associated_records.append(
                        _("• %d facturas oficiales asociadas a las ventas del TPV") % len(invoices)
                    )

                # 4. Pagos registrados (pos.payment)
                payments_count = self.env['pos.payment'].sudo().search_count([('pos_order_id', 'in', orders.ids)])
                if payments_count:
                    associated_records.append(
                        _("• %d transacciones de cobro / pagos registrados") % payments_count
                    )

            # 5. Empleados y Usuarios autorizados asignados a este TPV
            assigned_users = self.env['res.users'].sudo().search([('pos_config_ids', 'in', [config.id])])
            if assigned_users:
                user_names = ", ".join(assigned_users.mapped('name'))
                associated_records.append(
                    _("• %d usuarios/empleados autorizados con acceso asignado (%s)") % (len(assigned_users), user_names)
                )

            if hasattr(config, 'basic_employee_ids') and config.basic_employee_ids:
                emp_names = ", ".join(config.basic_employee_ids.mapped('name'))
                associated_records.append(
                    _("• %d empleados asignados en control de presencia (%s)") % (len(config.basic_employee_ids), emp_names)
                )

            # 6. Albaranes o Movimientos de existencias (stock.picking)
            if hasattr(self.env['stock.picking'], 'pos_session_id') and sessions:
                pickings_count = self.env['stock.picking'].sudo().search_count([('pos_session_id', 'in', sessions.ids)])
                if pickings_count:
                    associated_records.append(
                        _("• %d albaranes de salida / movimientos de stock de pista") % pickings_count
                    )

            if associated_records:
                details = "\n".join(associated_records)
                raise UserError(_(
                    'No se puede eliminar la estación de servicio "%(name)s" porque contiene registros asociados en el sistema:\n\n'
                    '%(details)s\n\n'
                    'Para mantener la trazabilidad y la integridad con el core de Odoo, debe eliminar o desvincular '
                    'previamente todos los registros vinculados antes de poder borrar la estación.'
                ) % {
                    'name': config.name,
                    'details': details,
                })

        return super(PosConfig, self).unlink()

    def action_open_station_form(self):
        self.ensure_one()
        return {
            'name': f"Estación de Servicio: {self.name}",
            'type': 'ir.actions.act_window',
            'res_model': 'pos.config',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_company_id': self.company_id.id if self.company_id else False,
            }
        }

    def action_return_to_gas_station_dashboard(self):
        return {
            'type': 'ir.actions.client',
            'tag': 'gas_station_dashboard',
            'target': 'main',
        }
