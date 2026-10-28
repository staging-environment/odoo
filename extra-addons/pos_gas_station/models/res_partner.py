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
            # Si no tiene empresa asignada, usar la empresa actual en contexto
            if not vals.get('company_id') and self.env.company:
                vals['company_id'] = self.env.company.id
        return super().create(vals_list)

    def write(self, vals):
        if vals.get('station_id') and not vals.get('company_id'):
            st = self.env['pos.config'].browse(vals['station_id'])
            if st.exists() and st.company_id:
                vals['company_id'] = st.company_id.id
        return super().write(vals)
