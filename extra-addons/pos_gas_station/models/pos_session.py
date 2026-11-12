# -*- coding: utf-8 -*-
import logging
import pytz
import datetime
from odoo import models, fields, api

_logger = logging.getLogger(__name__)

class PosSession(models.Model):
    _inherit = 'pos.session'

    admin_platform_fichaje_id = fields.Integer(
        string='ID Fichaje Admin Platform',
        copy=False,
        help='ID del registro de fichaje en la tabla empleado_fichajes de admin-platform'
    )
    admin_platform_checkout_done = fields.Boolean(
        string='Checkout Admin Platform Realizado',
        copy=False,
        default=False
    )
    checkout_latitude = fields.Float(
        string='Latitud Cierre',
        digits=(10, 8),
        copy=False
    )
    checkout_longitude = fields.Float(
        string='Longitud Cierre',
        digits=(11, 8),
        copy=False
    )

    def _get_admin_platform_conn(self):
        """Devuelve una conexión abierta a la base de datos MariaDB de admin-platform."""
        ICP = self.env['ir.config_parameter'].sudo()
        host = ICP.get_param('admin_platform.db_host', 'ddev-admin-platform-db')
        port = int(ICP.get_param('admin_platform.db_port', 3306))
        user_db = ICP.get_param('admin_platform.db_user', 'db')
        password = ICP.get_param('admin_platform.db_password', 'db')
        database = ICP.get_param('admin_platform.db_name', 'db')
        try:
            import pymysql
            import pymysql.cursors
            return pymysql.connect(
                host=host,
                port=port,
                user=user_db,
                password=password,
                database=database,
                charset='utf8mb4',
                cursorclass=pymysql.cursors.DictCursor,
                connect_timeout=5,
                autocommit=True
            )
        except Exception as e:
            _logger.error("Error conectando a MariaDB admin-platform: %s", e)
            return None

    def _clean_coordinate(self, coord):
        if coord is None or coord is False or coord == '' or coord == 0 or coord == 0.0:
            return None
        try:
            val = float(coord)
            if abs(val) < 0.0001:
                return None
            return round(val, 8)
        except (ValueError, TypeError):
            return None

    def register_admin_platform_checkin(self, latitude=None, longitude=None, employee_id=None):
        """Registra el checkin (entrada) en la tabla empleado_fichajes de admin-platform.
        Pone la hora manual (hora_entrada) y la del servidor (server_checkin_at) la misma,
        e intenta almacenar las coordenadas GPS.
        """
        self.ensure_one()
        target_user = self.user_id
        if not target_user:
            return None

        emp_id = employee_id or target_user.get_admin_platform_emp_id()
        if not emp_id:
            _logger.warning("No se pudo registrar checkin en admin-platform: usuario %s sin ID de empleado.", target_user.name)
            return None

        lat_val = self._clean_coordinate(latitude)
        lng_val = self._clean_coordinate(longitude)

        tz = pytz.timezone('Europe/Madrid')
        now = datetime.datetime.now(tz)
        today_str = now.strftime('%Y-%m-%d')
        time_str = now.strftime('%H:%M:%S')
        now_str = now.strftime('%Y-%m-%d %H:%M:%S')

        conn = self._get_admin_platform_conn()
        if not conn:
            return None

        fichaje_id = self.admin_platform_fichaje_id
        try:
            with conn.cursor() as cur:
                if fichaje_id:
                    # Esta sesión ya tiene su fichaje asignado; actualizar coordenadas si faltaban
                    if lat_val is not None and lng_val is not None:
                        cur.execute("""
                            UPDATE empleado_fichajes
                            SET checkin_latitude = COALESCE(%s, checkin_latitude),
                                checkin_longitude = COALESCE(%s, checkin_longitude),
                                updated_at = %s
                            WHERE id = %s
                        """, (lat_val, lng_val, now_str, fichaje_id))
                    _logger.info("[admin-platform] Fichaje checkin ya vinculado ID %s para empleado %s (ID %s). Coordenadas actualizadas.",
                                 fichaje_id, target_user.name, emp_id)
                else:
                    # Cerrar cualquier turno previo que haya quedado abierto sin salida
                    cur.execute("""
                        UPDATE empleado_fichajes
                        SET hora_salida = %s,
                            server_checkout_at = %s,
                            updated_at = %s
                        WHERE empleado_id = %s AND hora_salida IS NULL AND deleted_at IS NULL
                    """, (time_str, now_str, now_str, emp_id))

                    # Crear SIEMPRE un nuevo fichaje con la hora actual del servidor y manual idénticas
                    cur.execute("""
                        INSERT INTO empleado_fichajes (
                            empleado_id, fecha, hora_entrada, server_checkin_at,
                            checkin_latitude, checkin_longitude, is_retroactive, is_edited,
                            created_at, updated_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, 0, 0, %s, %s)
                    """, (emp_id, today_str, time_str, now_str, lat_val, lng_val, now_str, now_str))
                    fichaje_id = cur.lastrowid
                    _logger.info("[admin-platform] Checkin NUEVO CREADO con éxito (Fichaje ID %s) para empleado %s (ID %s) a las %s (GPS: %s, %s).",
                                 fichaje_id, target_user.name, emp_id, time_str, lat_val, lng_val)
            conn.close()

            if fichaje_id and self.admin_platform_fichaje_id != fichaje_id:
                self.sudo().write({
                    'admin_platform_fichaje_id': fichaje_id,
                    'admin_platform_checkout_done': False,
                })
        except Exception as e:
            _logger.error("Error registrando checkin en MariaDB admin-platform: %s", e)
            try:
                conn.close()
            except Exception:
                pass

        return fichaje_id

    def set_checkout_coordinates(self, latitude=None, longitude=None):
        """Guarda las coordenadas GPS del cierre desde la interfaz del TPV antes de cerrar."""
        lat_val = self._clean_coordinate(latitude)
        lng_val = self._clean_coordinate(longitude)
        for session in self:
            vals = {}
            if lat_val is not None:
                vals['checkout_latitude'] = lat_val
            if lng_val is not None:
                vals['checkout_longitude'] = lng_val
            if vals:
                session.sudo().write(vals)
        return True

    def register_admin_platform_checkout(self, latitude=None, longitude=None, user=None):
        """Registra el checkout (salida) en la tabla empleado_fichajes de admin-platform.
        Pone la hora manual (hora_salida) y la del servidor (server_checkout_at) exactamente la misma,
        e intenta almacenar las coordenadas GPS.
        """
        self.ensure_one()
        target_user = user or self.user_id
        if not target_user:
            return False

        emp_id = target_user.get_admin_platform_emp_id()
        if not emp_id:
            _logger.warning("No se pudo registrar checkout en admin-platform: usuario %s sin ID de empleado.", target_user.name)
            return False

        lat_val = self._clean_coordinate(latitude) or self._clean_coordinate(self.checkout_latitude)
        lng_val = self._clean_coordinate(longitude) or self._clean_coordinate(self.checkout_longitude)

        tz = pytz.timezone('Europe/Madrid')
        now = datetime.datetime.now(tz)
        time_str = now.strftime('%H:%M:%S')
        now_str = now.strftime('%Y-%m-%d %H:%M:%S')

        conn = self._get_admin_platform_conn()
        if not conn:
            return False

        success = False
        try:
            with conn.cursor() as cur:
                target_fichaje_id = self.admin_platform_fichaje_id
                if target_fichaje_id:
                    cur.execute("""
                        SELECT id FROM empleado_fichajes
                        WHERE id = %s AND hora_salida IS NULL AND deleted_at IS NULL
                    """, (target_fichaje_id,))
                    row = cur.fetchone()
                    if not row:
                        target_fichaje_id = None

                if not target_fichaje_id:
                    # Buscar el último fichaje abierto del empleado
                    cur.execute("""
                        SELECT id FROM empleado_fichajes
                        WHERE empleado_id = %s AND hora_salida IS NULL AND deleted_at IS NULL
                        ORDER BY id DESC LIMIT 1
                    """, (emp_id,))
                    row = cur.fetchone()
                    if row:
                        target_fichaje_id = row['id']

                if target_fichaje_id:
                    cur.execute("""
                        UPDATE empleado_fichajes
                        SET hora_salida = %s,
                            server_checkout_at = %s,
                            checkout_latitude = %s,
                            checkout_longitude = %s,
                            updated_at = %s
                        WHERE id = %s
                    """, (time_str, now_str, lat_val, lng_val, now_str, target_fichaje_id))
                    _logger.info("[admin-platform] Checkout REGISTRADO con éxito (Fichaje ID %s) para empleado %s (ID %s) a las %s (GPS: %s, %s).",
                                 target_fichaje_id, target_user.name, emp_id, time_str, lat_val, lng_val)
                    success = True
                else:
                    _logger.warning("[admin-platform] No se encontró turno abierto pendiente de checkout para empleado %s (ID %s).",
                                   target_user.name, emp_id)
            conn.close()

            self.sudo().write({'admin_platform_checkout_done': True})
        except Exception as e:
            _logger.error("Error registrando checkout en MariaDB admin-platform: %s", e)
            try:
                conn.close()
            except Exception:
                pass

        return success

    def action_pos_session_open(self):
        res = super().action_pos_session_open()
        for session in self:
            if not session.admin_platform_fichaje_id and not self.env.context.get('skip_admin_platform_checkin') and session.user_id:
                session.register_admin_platform_checkin()
        return res

    def _validate_session(self, balancing_account=False, amount_to_balance=0, bank_payment_method_diffs=None):
        res = super()._validate_session(balancing_account=balancing_account, amount_to_balance=amount_to_balance, bank_payment_method_diffs=bank_payment_method_diffs)
        for session in self:
            if session.state == 'closed' and not session.admin_platform_checkout_done:
                session.register_admin_platform_checkout()
        return res

    def close_session_from_ui(self, bank_payment_method_diff_pairs=None):
        res = super().close_session_from_ui(bank_payment_method_diff_pairs=bank_payment_method_diff_pairs)
        for session in self:
            if session.state == 'closed' and not session.admin_platform_checkout_done:
                session.register_admin_platform_checkout()
        return res

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
        # Cargar estrictamente los clientes asociados a la empresa de esta estación (sin particionar por estación)
        result['search_params']['domain'] = [
            ('company_id', '=', self.config_id.company_id.id)
        ]
        return result

    def get_pos_ui_res_partner_by_params(self, custom_search_params):
        """Asegurar que cualquier búsqueda dinámica filtre SIEMPRE por la empresa de este TPV."""
        if 'domain' in custom_search_params:
            comp_domain = [('company_id', '=', self.config_id.company_id.id)]
            custom_search_params['domain'] = comp_domain + (custom_search_params['domain'] or [])
        return super().get_pos_ui_res_partner_by_params(custom_search_params)

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

        # Adaptar nombres de métodos devueltos a la UI del TPV (Calculadora de Cobro)
        for p in pms:
            name = (p.get('name') or '').strip()
            name_lower = name.lower()
            if 'banco' in name_lower:
                p['name'] = 'Tarjeta'
            elif name_lower.startswith('efectivo'):
                p['name'] = 'Efectivo'

        return pms
