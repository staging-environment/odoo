# -*- coding: utf-8 -*-
import re

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class ResPartner(models.Model):
    _inherit = 'res.partner'

    station_id = fields.Many2one(
        'pos.config',
        string='Estación de Servicio',
        domain="[('company_id', '=', company_id)]",
        tracking=True,
        help='Estación de servicio a la que pertenece o repostó habitualmente este cliente'
    )
    cae = fields.Char(string='CAE', help='Código de Actividad y del Establecimiento')
    fax = fields.Char(string='Fax')
    doc_format = fields.Selection([
        ('impreso', 'Impreso'),
        ('email', 'Email'),
        ('impreso_email', 'Impreso/Email'),
        ('ninguno', 'Ninguno'),
    ], string='Formato Documentación', default='impreso')

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        # España por defecto en clientes nuevos
        if 'country_id' in fields_list and not res.get('country_id') and not self.env.context.get('default_parent_id'):
            spain = self.env.ref('base.es', raise_if_not_found=False)
            if spain:
                res['country_id'] = spain.id
        if self.env.context.get('default_company_id'):
            res['company_id'] = self.env.context.get('default_company_id')
            return res
        if self.env.context.get('res_company_partner_create') or self.env.context.get('skip_partner_company_default') or self.env.context.get('default_company_id') is False:
            return res
        if 'company_id' in fields_list and not res.get('company_id'):
            res['company_id'] = self.env.company.id
        if 'station_id' in fields_list and not res.get('station_id'):
            user = self.env.user
            if len(user.pos_config_ids) == 1:
                res['station_id'] = user.pos_config_ids[0].id
                if user.pos_config_ids[0].company_id and not res.get('company_id'):
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
    def _get_next_supplier_code(self):
        """Genera el siguiente código secuencial numérico para proveedores."""
        self.env.cr.execute("""
            SELECT COALESCE(MAX(
                CASE
                    WHEN ref ~ '^PROV-[0-9]+$' THEN CAST(SUBSTRING(ref FROM 6) AS INTEGER)
                    WHEN ref ~ '^[0-9]+$' THEN CAST(ref AS INTEGER)
                    ELSE 0
                END
            ), 0) + 1
            FROM res_partner
            WHERE supplier_rank > 0 AND (ref ~ '^PROV-[0-9]+$' OR ref ~ '^[0-9]+$');
        """)
        row = self.env.cr.fetchone()
        return str(row[0] if row and row[0] else 1)

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

    # ------------------------------------------------------------------
    # Unicidad de clientes POR EMPRESA: nunca dos clientes de la misma
    # empresa con el mismo CIF/NIF ni con el mismo número de cliente (ref).
    # No cuentan: contactos hijos, fichas internas de empresas/usuarios,
    # proveedores puros (sin rango de cliente) ni fichas archivadas.
    # ------------------------------------------------------------------
    @staticmethod
    def _utrecar_normalize_vat(vat):
        v = (vat or '').strip().upper()
        v = re.sub(r'^ES', '', v)
        return re.sub(r'[^A-Z0-9]', '', v)

    def _utrecar_is_unique_scope(self, internal_partner_ids):
        self.ensure_one()
        if not self.active or self.parent_id or self.id in internal_partner_ids:
            return False
        if self.supplier_rank and not self.customer_rank:
            return False
        return True

    @api.constrains('vat', 'ref', 'company_id', 'parent_id', 'active')
    def _check_utrecar_unique_customer(self):
        self.flush_model(['vat', 'ref', 'company_id', 'parent_id', 'active',
                          'customer_rank', 'supplier_rank'])
        internal_ids = set(self.env['res.company'].sudo().with_context(active_test=False)
                           .search([]).mapped('partner_id').ids)
        internal_ids |= set(self.env['res.users'].sudo().with_context(active_test=False)
                            .search([]).mapped('partner_id').ids)
        for partner in self:
            if not partner._utrecar_is_unique_scope(internal_ids):
                continue
            vat = self._utrecar_normalize_vat(partner.vat)
            ref = (partner.ref or '').strip()
            if not vat and not ref:
                continue
            self.env.cr.execute("""
                SELECT id, name, ref, vat
                  FROM res_partner
                 WHERE id != %(id)s
                   AND active
                   AND parent_id IS NULL
                   AND company_id IS NOT DISTINCT FROM %(company)s
                   AND NOT (COALESCE(supplier_rank, 0) > 0 AND COALESCE(customer_rank, 0) = 0)
                   AND NOT (id = ANY(%(internal)s))
                   AND (
                        (%(vat)s <> '' AND regexp_replace(regexp_replace(upper(COALESCE(vat, '')), '^ES', ''), '[^A-Z0-9]', '', 'g') = %(vat)s)
                     OR (%(ref)s <> '' AND trim(COALESCE(ref, '')) = %(ref)s)
                   )
                 LIMIT 1
            """, {
                'id': partner.id,
                'company': partner.company_id.id or None,
                'internal': list(internal_ids) or [0],
                'vat': vat,
                'ref': ref,
            })
            row = self.env.cr.fetchone()
            if row:
                dup_id, dup_name, dup_ref, dup_vat = row
                dup_label = f"{dup_ref} - {dup_name}" if dup_ref else dup_name
                company_name = partner.company_id.name or _('sin empresa')
                if vat and self._utrecar_normalize_vat(dup_vat) == vat:
                    raise ValidationError(_(
                        "Ya existe un cliente con el CIF/NIF %(vat)s en %(company)s: %(dup)s. "
                        "No puede haber dos clientes con el mismo CIF/NIF en la misma empresa.",
                        vat=vat, company=company_name, dup=dup_label))
                raise ValidationError(_(
                    "Ya existe un cliente con el número %(ref)s en %(company)s: %(dup)s. "
                    "No puede haber dos clientes con el mismo número en la misma empresa.",
                    ref=ref, company=company_name, dup=dup_label))

    # ------------------------------------------------------------------
    # Validación de formato de NIF/CIF (España) y email. Solo salta al dar
    # de alta o cambiar esos campos (o el país), para no bloquear clientes
    # antiguos de Aseproda con datos incompletos.
    # ------------------------------------------------------------------
    @api.model
    def _utrecar_check_spanish_vat(self, raw_vat):
        """Devuelve (ok, valor_normalizado, mensaje) para NIF, NIE o CIF español."""
        v = self._utrecar_normalize_vat(raw_vat)
        if len(v) != 9:
            return False, v, _('El NIF / CIF "%s" debe tener 9 caracteres (ej: 12345678Z o B41000001).') % raw_vat
        letras = 'TRWAGMYFPDXBNJZSQVHLCKE'
        if re.match(r'^\d{8}[A-Z]$', v):
            ok = v[8] == letras[int(v[:8]) % 23]
            return ok, v, '' if ok else _('El NIF "%s" no es válido (letra de control incorrecta).') % v
        if re.match(r'^[XYZ]\d{7}[A-Z]$', v):
            ok = v[8] == letras[int({'X': '0', 'Y': '1', 'Z': '2'}[v[0]] + v[1:8]) % 23]
            return ok, v, '' if ok else _('El NIE "%s" no es válido (letra de control incorrecta).') % v
        if re.match(r'^[ABCDEFGHJNPQRSUVW]\d{7}[0-9A-J]$', v):
            d = v[1:8]
            total = sum(int(d[i]) for i in (1, 3, 5))
            for i in (0, 2, 4, 6):
                x = int(d[i]) * 2
                total += x // 10 + x % 10
            ctrl_digit = (10 - total % 10) % 10
            ctrl_letter = 'JABCDEFGHI'[ctrl_digit]
            if v[0] in 'ABEH':
                ok = v[8] == str(ctrl_digit)
            elif v[0] in 'KPQS':
                ok = v[8] == ctrl_letter
            else:
                ok = v[8] in (str(ctrl_digit), ctrl_letter)
            return ok, v, '' if ok else _('El CIF "%s" no es válido (dígito/letra de control incorrecto).') % v
        return False, v, _('El formato de NIF / CIF "%s" no es válido.') % raw_vat

    @api.constrains('vat', 'email', 'country_id')
    def _check_utrecar_vat_email_format(self):
        spain = self.env.ref('base.es', raise_if_not_found=False)
        for partner in self:
            if partner.vat and (not partner.country_id or partner.country_id == spain):
                ok, _v, msg = self._utrecar_check_spanish_vat(partner.vat)
                if not ok:
                    raise ValidationError(_("%(name)s: %(msg)s", name=partner.display_name or '', msg=msg))
            email = (partner.email or '').strip()
            if email and not re.match(r'^[^\s@,;]+@[^\s@,;]+\.[^\s@,;]{2,}$', email):
                raise ValidationError(_('%(name)s: el email "%(email)s" no es válido.',
                                        name=partner.display_name or '', email=email))
