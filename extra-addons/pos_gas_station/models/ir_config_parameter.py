# -*- coding: utf-8 -*-
"""Parámetros volátiles de pista sin invalidar la caché global de Odoo.

El agente de pista publica el estado de los surtidores (``pumps_state_<id>``)
cada ~0,8 s y el TPV escribe órdenes (``pump_command_<id>``) mediante
``ir.config_parameter``. En Odoo 17, ``ir.config_parameter.write`` llama a
``registry.clear_cache()``, lo que vaciaba la caché ORM de *todo* el servidor
una vez por segundo (log ``Caches invalidated``) y penalizaba a todos los
usuarios.

Para estas claves concretas se lee y escribe directamente en la tabla, sin
pasar por ``_get_param`` (ormcache) ni por ``write`` (clear_cache). La API
pública (``get_param``/``set_param``) no cambia, por lo que el agente
desplegado en las estaciones sigue funcionando sin modificaciones.
"""
from odoo import api, models

VOLATILE_PARAM_PREFIXES = (
    'pos_gas_station.pumps_state_',
    'pos_gas_station.pump_command_',
)


def _is_volatile(key):
    return isinstance(key, str) and key.startswith(VOLATILE_PARAM_PREFIXES)


class IrConfigParameter(models.Model):
    _inherit = 'ir.config_parameter'

    @api.model
    def get_param(self, key, default=False):
        if not _is_volatile(key):
            return super().get_param(key, default)
        self.check_access_rights('read')
        self.env.cr.execute(
            "SELECT value FROM ir_config_parameter WHERE key = %s", [key]
        )
        row = self.env.cr.fetchone()
        return (row and row[0]) or default

    @api.model
    def set_param(self, key, value):
        if not _is_volatile(key):
            return super().set_param(key, value)
        self.check_access_rights('write')
        cr = self.env.cr
        cr.execute(
            "SELECT id, value FROM ir_config_parameter WHERE key = %s FOR UPDATE",
            [key],
        )
        row = cr.fetchone()
        if row:
            old = row[1]
            if value is False or value is None:
                cr.execute("DELETE FROM ir_config_parameter WHERE id = %s", [row[0]])
            elif str(value) != old:
                cr.execute(
                    """UPDATE ir_config_parameter
                          SET value = %s, write_uid = %s,
                              write_date = (now() at time zone 'UTC')
                        WHERE id = %s""",
                    [str(value), self.env.uid, row[0]],
                )
        else:
            old = False
            if value is not False and value is not None:
                cr.execute(
                    """INSERT INTO ir_config_parameter
                           (key, value, create_uid, write_uid, create_date, write_date)
                       VALUES (%s, %s, %s, %s,
                               (now() at time zone 'UTC'), (now() at time zone 'UTC'))""",
                    [key, str(value), self.env.uid, self.env.uid],
                )
        # Solo invalidar la caché de registros del entorno actual (barato y local).
        self.invalidate_model(['value'])
        return old
