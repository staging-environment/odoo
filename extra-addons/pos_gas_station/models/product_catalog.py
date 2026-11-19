# -*- coding: utf-8 -*-
import logging
from odoo import models, fields, api
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class ProductCategory(models.Model):
    _inherit = 'product.category'

    code = fields.Char(
        string='Código',
        size=2,
        index=True,
        help='1 dígito para categoría padre, 2 dígitos para subfamilia hija'
    )
    full_code = fields.Char(
        string='Prefijo Completo',
        compute='_compute_full_code',
        store=True,
        index=True,
    )

    @api.depends('code', 'parent_id', 'parent_id.code')
    def _compute_full_code(self):
        for rec in self:
            if rec.parent_id and rec.parent_id.code and rec.code:
                rec.full_code = f"{rec.parent_id.code}{rec.code}"
            else:
                rec.full_code = rec.code or ''

    @api.constrains('code', 'parent_id')
    def _check_category_code_format(self):
        for rec in self:
            if not rec.code:
                continue
            c = rec.code.strip()
            if rec.parent_id:
                if len(c) != 2 or not c.isdigit():
                    raise ValidationError(
                        f"La subfamilia '{rec.name}' debe tener un código de exactamente 2 dígitos (ej: 01, 11)."
                    )
            else:
                if len(c) != 1 or not c.isdigit():
                    raise ValidationError(
                        f"La categoría padre '{rec.name}' debe tener un código de exactamente 1 dígito (ej: 1, 3)."
                    )

    @api.model
    def get_next_parent_code(self):
        """Devuelve el siguiente código de 1 dígito disponible para una categoría padre."""
        parents = self.sudo().search([('parent_id', '=', False), ('code', '!=', False)])
        used = set()
        for p in parents:
            if p.code and p.code.isdigit() and len(p.code) == 1:
                used.add(int(p.code))
        for i in range(1, 10):
            if i not in used:
                return str(i)
        return '9'

    @api.model
    def get_next_child_code(self, parent_id):
        """Devuelve el siguiente código autoincremental de 2 dígitos para una subfamilia hija."""
        children = self.sudo().search([('parent_id', '=', int(parent_id)), ('code', '!=', False)])
        max_num = 0
        for ch in children:
            if ch.code and ch.code.isdigit():
                val = int(ch.code)
                if val > max_num:
                    max_num = val
        next_num = max_num + 1
        if next_num > 99:
            next_num = 99
        return str(next_num).zfill(2)


class ProductBarcode(models.Model):
    _name = 'product.barcode'
    _description = 'Códigos de Barras Adicionales de Producto'
    _order = 'id asc'

    product_tmpl_id = fields.Many2one(
        'product.template',
        string='Producto',
        required=True,
        ondelete='cascade',
        index=True,
    )
    barcode = fields.Char(
        string='Código de Barras (EAN)',
        required=True,
        index=True,
    )

    _sql_constraints = [
        ('barcode_uniq', 'unique(barcode)', 'El código de barras (EAN) ya está asignado a otro producto.')
    ]


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    extra_barcode_ids = fields.One2many(
        'product.barcode',
        'product_tmpl_id',
        string='Códigos de Barras Adicionales',
    )


class UtrecarTaxType(models.Model):
    _name = 'utrecar.tax.type'
    _description = 'Tipos de IVA (Parámetros de Administración)'
    _order = 'code_num asc, code asc, id asc'

    code = fields.Char(string='Código', required=True, size=10, index=True)
    code_num = fields.Integer(string='Orden Numérico', compute='_compute_code_num', store=True)
    name = fields.Char(string='Nombre / Descripción', required=True)
    percentage = fields.Float(string='Porcentaje (%)', digits=(5, 2), default=0.0)
    is_exempt = fields.Boolean(string='Exento de IVA', default=False)
    active = fields.Boolean(string='Activo', default=True)
    company_id = fields.Many2one('res.company', string='Empresa', index=True)
    account_tax_id = fields.Many2one(
        'account.tax',
        string='Impuesto Odoo Vinculado',
        ondelete='set null',
    )

    _sql_constraints = [
        ('code_company_uniq', 'unique(code, company_id)', 'Ya existe un tipo de IVA con ese código en esta empresa.')
    ]

    @api.depends('code')
    def _compute_code_num(self):
        for rec in self:
            try:
                rec.code_num = int(rec.code) if rec.code and rec.code.strip().isdigit() else 9999
            except Exception:
                rec.code_num = 9999

    def sync_odoo_account_tax(self):
        """Sincroniza o vincula un account.tax de venta en Odoo para este tipo de IVA."""
        Tax = self.env['account.tax'].sudo()
        for rec in self:
            if rec.is_exempt:
                continue
            cid = rec.company_id.id if rec.company_id else self.env.company.id
            if rec.account_tax_id and rec.account_tax_id.exists():
                rec.account_tax_id.sudo().write({
                    'name': rec.name,
                    'amount': rec.percentage,
                    'price_include': True,
                    'active': rec.active,
                })
            else:
                existing = Tax.search([
                    ('type_tax_use', '=', 'sale'),
                    ('company_id', '=', cid),
                    ('amount', '=', rec.percentage),
                    ('active', '=', True),
                ], limit=1)
                if existing:
                    rec.account_tax_id = existing.id
                else:
                    new_tax = Tax.create({
                        'name': rec.name,
                        'amount': rec.percentage,
                        'amount_type': 'percent',
                        'type_tax_use': 'sale',
                        'price_include': True,
                        'company_id': cid,
                    })
                    rec.account_tax_id = new_tax.id
