# -*- coding: utf-8 -*-
from odoo import models, fields, api

class ResPartner(models.Model):
    _inherit = 'res.partner'

    station_id = fields.Many2one(
        'pos.config',
        string='Estación de Servicio',
        domain="[('company_id', '=', company_id)]",
        tracking=True,
        help='Estación de servicio a la que pertenece o repostó habitualmente este cliente'
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if self.env.context.get('res_company_partner_create') or self.env.context.get('skip_partner_company_default') or self.env.context.get('default_company_id') is False:
            return res
        if 'company_id' in fields_list and not res.get('company_id'):
            res['company_id'] = self.env.company.id
        if 'station_id' in fields_list and not res.get('station_id'):
            user = self.env.user
            if len(user.pos_config_ids) == 1:
                res['station_id'] = user.pos_config_ids[0].id
                if user.pos_config_ids[0].company_id:
                    res['company_id'] = user.pos_config_ids[0].company_id.id
        return res

    @api.model
    def _get_next_customer_code(self):
        """Genera el siguiente código secuencial numérico para clientes de gasolinera."""
        code = self.env['ir.sequence'].next_by_code('res.partner.customer.code')
        if not code:
            # Fallback robusto en base a la base de datos
            self.env.cr.execute("""
                SELECT COALESCE(MAX(CAST(ref AS INTEGER)), 1957) + 1
                FROM res_partner
                WHERE ref ~ '^[0-9]+$' AND CAST(ref AS INTEGER) < 9999;
            """)
            next_num = self.env.cr.fetchone()[0]
            code = str(next_num)
        return code

    @api.model
    def create_from_ui(self, partner):
        # Auto-asignar estación si se crea cliente desde el TPV
        if not partner.get('station_id'):
            session = self.env['pos.session'].search([
                ('user_id', '=', self.env.uid),
                ('state', '=', 'opened')
            ], limit=1)
            if session and session.config_id:
                partner['station_id'] = session.config_id.id
                partner['company_id'] = session.config_id.company_id.id
        partner['customer_rank'] = 1
        return super().create_from_ui(partner)

    @api.onchange('station_id')
    def _onchange_station_id(self):
        if self.station_id and self.station_id.company_id:
            self.company_id = self.station_id.company_id

    @api.onchange('company_id')
    def _onchange_company_id(self):
        if self.station_id and self.station_id.company_id and self.company_id:
            if self.station_id.company_id != self.company_id:
                self.station_id = False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # Si se asigna estación y no empresa, auto-asignar empresa de la estación
            if vals.get('station_id') and not vals.get('company_id'):
                st = self.env['pos.config'].browse(vals['station_id'])
                if st.exists() and st.company_id:
                    vals['company_id'] = st.company_id.id
            # Si se está creando una compañía o se pide omitir compañía por defecto, no forzar self.env.company
            skip = (
                self.env.context.get('res_company_partner_create') or 
                self.env.context.get('skip_partner_company_default') or 
                self.env.context.get('default_company_id') is False or
                vals.get('company_id') is False
            )
            if not skip and not vals.get('company_id') and self.env.company:
                vals['company_id'] = self.env.company.id

            # Asignación automática de código numérico correlativo a clientes
            if not vals.get('ref'):
                is_customer = (
                    vals.get('customer_rank', 0) > 0 or 
                    self.env.context.get('default_customer_rank', 0) > 0 or
                    self.env.context.get('res_partner_search_mode') == 'customer' or
                    self.env.context.get('search_default_filter_customer') == 1
                )
                is_internal = (
                    self.env.context.get('res_users_partner_create') or
                    self.env.context.get('res_company_partner_create') or
                    vals.get('user_ids')
                )
                if is_customer and not is_internal:
                    vals['ref'] = self._get_next_customer_code()

        return super().create(vals_list)

    def write(self, vals):
        if vals.get('station_id') and not vals.get('company_id'):
            st = self.env['pos.config'].browse(vals['station_id'])
            if st.exists() and st.company_id:
                vals['company_id'] = st.company_id.id
        return super().write(vals)

    def action_assign_customer_code(self):
        """Asigna manualmente el siguiente código numérico a clientes que no lo tengan."""
        for partner in self:
            if not partner.ref and partner.customer_rank > 0:
                partner.ref = self._get_next_customer_code()
        return True
