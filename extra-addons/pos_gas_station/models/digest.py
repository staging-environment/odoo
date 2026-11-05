# -*- coding: utf-8 -*-
from odoo import api, fields, models
import logging

_logger = logging.getLogger(__name__)


class Digest(models.Model):
    _inherit = 'digest.digest'

    def _cron_send_digest_email(self):
        """
        Bloqueo permanente del envío de resúmenes periódicos por correo electrónico a empleados.
        """
        _logger.info("Envío de correos Digest cancelado (desactivado permanentemente para UTRECAR).")
        return True

    def action_send(self):
        """
        Bloqueo del envío manual de resúmenes periódicos.
        """
        _logger.info("Envío manual de correo Digest cancelado (desactivado permanentemente para UTRECAR).")
        return True

    @api.model_create_multi
    def create(self, vals_list):
        """
        Garantizar que cualquier digest que se cree nazca desactivado y sin usuarios suscritos.
        """
        for vals in vals_list:
            vals['state'] = 'deactivated'
            vals['user_ids'] = [(5, 0, 0)]
        return super().create(vals_list)


class ResUsers(models.Model):
    _inherit = 'res.users'

    @api.model_create_multi
    def create(self, vals_list):
        """
        Asegura que ningún nuevo empleado/usuario sea suscrito automáticamente a resúmenes periódicos.
        """
        users = super().create(vals_list)
        if 'digest.digest' in self.env:
            digests = self.env['digest.digest'].sudo().search([])
            for d in digests:
                if d.user_ids & users:
                    d.user_ids -= users
        return users
