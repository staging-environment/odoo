# -*- coding: utf-8 -*-
from odoo import models, api

class PosSession(models.Model):
    _inherit = 'pos.session'

    def _loader_params_res_partner(self):
        result = super()._loader_params_res_partner()
        result['search_params']['fields'].extend([
            'ref',
            'customer_type',
            'customer_payment_mode',
            'invoice_periodicity',
            'credit_blocked',
            'credit_limit_amount',
            'station_id',
            'company_id',
        ])
        return result

    def _get_pos_ui_pos_payment_method(self, params):
        pms = super()._get_pos_ui_pos_payment_method(params)
        # Ensure 'Cuenta de cliente' / Customer Account is available in POS for credit clients
        pm_cuenta = self.env['pos.payment.method'].search([('name', 'ilike', 'cuenta')], limit=1)
        if not pm_cuenta:
            pm_cuenta = self.env['pos.payment.method'].search([('name', 'ilike', 'customer account')], limit=1)
        if pm_cuenta:
            if not any(p['id'] == pm_cuenta.id for p in pms):
                pm_data = pm_cuenta.read(params['search_params']['fields'])[0]
                pms.append(pm_data)
            # Ensure rel table has it so payment validation succeeds
            if self.config_id and pm_cuenta not in self.config_id.payment_method_ids:
                self.env.cr.execute(
                    "INSERT INTO pos_config_pos_payment_method_rel (pos_config_id, pos_payment_method_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                    (self.config_id.id, pm_cuenta.id)
                )
        return pms
