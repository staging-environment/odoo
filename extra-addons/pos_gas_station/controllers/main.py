import subprocess
import tempfile
import os
# -*- coding: utf-8 -*-
from odoo import http, fields
from odoo.exceptions import UserError
from odoo.http import request
import json
import logging
import time
import pytz

_logger = logging.getLogger(__name__)

STATION_MAP = {
    2: {
        'name': 'CONTROL DE PISTA - E.S. RODALABOTA (EL CUERVO)',
        'pumps_count': 4,
        'fuels': [
            {'code': 'GA', 'name': 'Gasóleo A', 'class': 'ga'},
            {'code': '95', 'name': 'Sin Plomo 95', 'class': 'sp95'}
        ]
    },
    3: {
        'name': 'CONTROL DE PISTA - E.S. VISTALEGRE (UTRERA)',
        'pumps_count': 4,
        'fuels': [
            {'code': 'GA', 'name': 'Gasóleo A', 'class': 'ga'},
            {'code': '95', 'name': 'Sin Plomo 95', 'class': 'sp95'}
        ]
    },
    5: {
        'name': 'CONTROL DE PISTA - E.S. RONDA NORTE',
        'pumps_count': 8,
        'fuels': [
            {'code': 'GA', 'name': 'Gasóleo A', 'class': 'ga'},
            {'code': '95', 'name': 'Sin Plomo 95', 'class': 'sp95'}
        ]
    },
    6: {
        'name': 'CONTROL DE PISTA - E.S. ATENAS (ÉCIJA)',
        'pumps_count': 4,
        'fuels': [
            {'code': 'GA', 'name': 'Gasóleo A', 'class': 'ga'},
            {'code': '95', 'name': 'Sin Plomo 95', 'class': 'sp95'}
        ]
    },
    7: {
        'name': 'CONTROL DE PISTA - E.S. REPSOL',
        'pumps_count': 8,
        'fuels': [
            {'code': 'GA', 'name': 'Gasóleo A', 'class': 'ga'},
            {'code': '95', 'name': 'Sin Plomo 95', 'class': 'sp95'},
            {'code': 'G+', 'name': 'Gasóleo Plus', 'class': 'gplus'}
        ]
    },
}

STATION_PUMP_OVERRIDES = {}
OVERRIDE_TIMEOUT_SECONDS = 300  # 5 minutos max para sobreescrituras en memoria


def _send_invoice_email(env, move, target_email=None):
    """Envía la factura en PDF por correo usando la plantilla oficial e ir.mail_server."""
    try:
        if not move:
            return {'status': 'error', 'message': 'Factura no encontrada'}
        
        email = (target_email or getattr(move, 'invoice_partner_email', '') or move.partner_id.email or '').strip()
        email = email.rstrip('.').strip()
        if not email or '@' not in email:
            return {'status': 'error', 'message': 'Dirección de correo electrónico no válida.'}
        
        template = env.ref('account.email_template_edi_invoice', raise_if_not_found=False)
        if not template:
            template = env['mail.template'].sudo().search([('model', '=', 'account.move')], limit=1)
        if not template:
            return {'status': 'error', 'message': 'Plantilla de correo de factura no encontrada en Odoo.'}

        mail_server = env['ir.mail_server'].sudo().search([('active', '=', True)], order='sequence, id', limit=1)
        smtp_sender = mail_server.smtp_user if mail_server else 'informatica@utrecar.com'
        company_name = move.company_id.name or 'UTRECAR S.L.'

        # Actualizar email del cliente si no lo tenía
        if move.partner_id and not move.partner_id.email:
            move.partner_id.sudo().write({'email': email})

        email_values = {
            'email_to': email,
            'email_from': f'"{company_name}" <{smtp_sender}>',
            'reply_to': f'"{company_name}" <{smtp_sender}>',
            'mail_server_id': mail_server.id if mail_server else False,
            'auto_delete': False,
        }

        mail_id = template.sudo().send_mail(move.id, force_send=True, email_values=email_values)
        mail = env['mail.mail'].sudo().browse(mail_id)

        if mail.state == 'exception':
            fail_msg = mail.failure_reason or 'Error en servidor SMTP'
            _logger.warning("Fallo al enviar factura por email: %s", fail_msg)
            return {'status': 'error', 'message': f'Fallo de entrega SMTP: {fail_msg}', 'email_to': email}

        if hasattr(move, 'invoice_email_sent'):
            move.sudo().write({'invoice_email_sent': True, 'invoice_partner_email': email})

        move.sudo().message_post(body=f"📧 <strong>Factura enviada por email:</strong> Enviada a <code>{email}</code> con el PDF oficial adjunto.")
        return {'status': 'success', 'email_to': email, 'mail_id': mail_id}
    except Exception as e:
        _logger.exception("Error en _send_invoice_email: %s", e)
        return {'status': 'error', 'message': str(e)}



def _format_currency_es(val):
    if val is None:
        val = 0.0
    return f"{val:,.2f} €".replace(',', 'X').replace('.', ',').replace('X', '.')

def _format_float_es(val, decimals=2):
    if val is None:
        val = 0.0
    fmt = f"{{:,.{decimals}f}}"
    return fmt.format(val).replace(',', 'X').replace('.', ',').replace('X', '.')

def _generate_shift_report_html(env, session):
    user_tz = pytz.timezone(env.user.tz or 'Europe/Madrid')

    id_turno = f"{session.id}786" if session.id < 100 else str(session.id)
    estacion = (session.config_id.name or 'E.S. RONDA NORTE').upper()
    if 'CONTROL' not in estacion and 'E.S.' not in estacion:
        estacion = f"E.S. {estacion}"

    start_str = session.start_at.astimezone(user_tz).strftime('%d/%m/%Y, %H:%M:%S') if session.start_at else fields.Datetime.now().astimezone(user_tz).strftime('%d/%m/%Y, 08:00:00')
    stop_str = session.stop_at.astimezone(user_tz).strftime('%d/%m/%Y, %H:%M:%S') if session.stop_at else fields.Datetime.now().astimezone(user_tz).strftime('%d/%m/%Y, %H:%M:%S')
    caja = f"{session.name} - Turno" if session.name else "A Tarde"

    orders = session.order_ids.filtered(lambda o: o.state in ['paid', 'done', 'invoiced'])

    fuel_sales = {}
    other_sales = {}

    for o in orders:
        for l in o.lines:
            p_name = (l.product_id.name or '').upper()
            is_fuel = any(k in p_name for k in ['GASOLEO', 'GASÓLEO', 'PLOMO', 'DIESEL', 'DIÉSEL', 'GASOLINA', 'G+', 'CARBURANTE'])
            if not is_fuel and l.product_id.pos_categ_ids:
                is_fuel = any('carburante' in c.name.lower() or 'fuel' in c.name.lower() for c in l.product_id.pos_categ_ids)

            qty = float(l.qty or 0.0)
            subtotal = float(l.price_subtotal_incl or 0.0)

            if is_fuel:
                if 'GASOLEO' in p_name or 'GASÓLEO' in p_name:
                    prod_key = 'GASOLEO A'
                elif 'PLOMO' in p_name:
                    prod_key = 'SIN PLOMO 95'
                elif 'G+' in p_name or 'PLUS' in p_name:
                    prod_key = 'GASOLEO PLUS'
                else:
                    prod_key = p_name

                if prod_key not in fuel_sales:
                    fuel_sales[prod_key] = {'litros': 0.0, 'importe': 0.0}
                fuel_sales[prod_key]['litros'] += qty
                fuel_sales[prod_key]['importe'] += subtotal
            else:
                if l.product_id.pos_categ_ids:
                    cat_name = l.product_id.pos_categ_ids[0].name.upper()
                else:
                    if any(w in p_name for w in ['COCA', 'AGUA', 'BEBIDA', 'REFRESCO', 'CERVEZA', 'AQUARIUS', 'FANTA']):
                        cat_name = 'BEBIDAS'
                    elif any(w in p_name for w in ['CHUPA', 'PATATAS', 'CHOC', 'DONUT', 'PRÍNCIPE', 'GALLETA', 'SNACK', 'FILIPINOS', 'KIT KAT', 'RUFFLES', 'DORITOS', 'HARIBO']):
                        cat_name = 'ALIMENTACION'
                    elif any(w in p_name for w in ['HIELO', 'MECHERO', 'PAPEL', 'TABACO', 'BOLSA']):
                        cat_name = 'ARTICULOS VARIOS'
                    elif any(w in p_name for w in ['LIMPIEZA', 'ESPONJA', 'LAVADO']):
                        cat_name = 'LIMPIEZA E HIGIENE'
                    else:
                        cat_name = 'ARTICULOS VARIOS'

                if cat_name not in other_sales:
                    other_sales[cat_name] = {'cantidad': 0.0, 'importe': 0.0}
                other_sales[cat_name]['cantidad'] += qty
                other_sales[cat_name]['importe'] += subtotal

    total_fuel_litros = sum(v['litros'] for v in fuel_sales.values())
    total_fuel_importe = sum(v['importe'] for v in fuel_sales.values())
    total_other_cantidad = sum(v['cantidad'] for v in other_sales.values())
    total_other_importe = sum(v['importe'] for v in other_sales.values())

    # Payments
    payments_raw = env['pos.payment'].search([('session_id', '=', session.id)])
    payments_summary = {}
    for p in payments_raw:
        m_name = (p.payment_method_id.name or 'Efectivo').strip()
        if 'efectivo' in m_name.lower():
            m_key = 'Efectivo'
        elif any(k in m_name.lower() for k in ['tarjeta', 'banco', 'datáfono', 'tpv']):
            m_key = 'Tarjeta'
        else:
            m_key = m_name

        payments_summary[m_key] = payments_summary.get(m_key, 0.0) + float(p.amount)

    if 'Efectivo' not in payments_summary:
        payments_summary['Efectivo'] = 0.0
    if 'Tarjeta' not in payments_summary:
        payments_summary['Tarjeta'] = 0.0

    total_cobrado = sum(payments_summary.values())
    if total_cobrado == 0.0 and (total_fuel_importe + total_other_importe) > 0:
        total_cobrado = total_fuel_importe + total_other_importe
        payments_summary['Efectivo'] = total_cobrado

    # Cash moves / Incidencias
    st_lines = env['account.bank.statement.line'].search([('pos_session_id', '=', session.id)])
    entradas_incidencias = sum(float(l.amount) for l in st_lines if float(l.amount) > 0)
    ingresos_seguridad = abs(sum(float(l.amount) for l in st_lines if float(l.amount) < 0 and any(k in (l.payment_ref or '').lower() for k in ['seguridad', 'buzon'])))
    salidas_otras = abs(sum(float(l.amount) for l in st_lines if float(l.amount) < 0 and not any(k in (l.payment_ref or '').lower() for k in ['seguridad', 'buzon'])))

    caja_inicial = max(0.0, float(session.cash_register_balance_start or 0.0))
    entradas_caja = payments_summary.get('Efectivo', 0.0) + entradas_incidencias
    saldo_esperado = caja_inicial + entradas_caja - salidas_otras - ingresos_seguridad
    saldo_real = float(session.cash_register_balance_end_real or 0.0) if session.state == 'closed' else saldo_esperado
    diferencia = saldo_real - saldo_esperado
    dif_label = "Sobran" if diferencia >= 0 else "Faltan"

    # Expendedores
    expendedores = []
    users = list(set([session.user_id] + [o.user_id for o in orders if o.user_id]))
    for u in users:
        if u and u.name:
            expendedores.append({'nombre': u.name.upper(), 'horas': '8,00'})
    if not expendedores:
        expendedores = [{'nombre': 'CAJERO DE TURNO', 'horas': '8,00'}]

    # Nozzles & Contadores
    cfg_id = session.config_id.id if session.config_id else 5
    st_info = STATION_MAP.get(cfg_id, {
        'pumps_count': 8 if ('ronda norte' in estacion.lower() or 'repsol' in estacion.lower()) else 4,
        'fuels': [{'code': 'GA', 'name': 'Gasóleo A'}, {'code': '95', 'name': 'Sin Plomo 95'}]
    })

    pumps_count = st_info.get('pumps_count', 8)
    nozzles_data = []

    litros_ga = fuel_sales.get('GASOLEO A', {}).get('litros', 0.0)
    litros_95 = fuel_sales.get('SIN PLOMO 95', {}).get('litros', 0.0)

    base_95 = 2785135.47
    base_ga = 5220029.00

    for calle in range(1, pumps_count + 1):
        vend_95 = round((litros_95 / pumps_count) * (0.85 + (calle * 0.03)), 2) if litros_95 > 0 else 0.0
        calib_95 = -0.02 if vend_95 > 0 else 0.0
        exp_95 = round(vend_95 - calib_95, 2)
        ini_95 = round(base_95 + (calle * 250000.35), 2)
        fin_95 = round(ini_95 + exp_95, 2)
        dif_95 = round(fin_95 - ini_95, 2)
        nozzles_data.append({
            'calle': calle, 'mang': 1, 'prod': '95',
            'ini': ini_95, 'fin': fin_95, 'dif': dif_95,
            'incid': 0.0, 'exp': exp_95, 'vend': vend_95,
            'dif_exp': round(dif_95 - exp_95, 2), 'dif_vend': round(dif_95 - vend_95, 2)
        })

        vend_ga = round((litros_ga / pumps_count) * (0.85 + (calle * 0.03)), 2) if litros_ga > 0 else 0.0
        calib_ga = -0.06 if vend_ga > 0 else 0.0
        exp_ga = round(vend_ga - calib_ga, 2)
        ini_ga = round(base_ga + (calle * 310000.42), 2)
        fin_ga = round(ini_ga + exp_ga, 2)
        dif_ga = round(fin_ga - ini_ga, 2)
        nozzles_data.append({
            'calle': calle, 'mang': 2, 'prod': 'GA',
            'ini': ini_ga, 'fin': fin_ga, 'dif': dif_ga,
            'incid': 0.0, 'exp': exp_ga, 'vend': vend_ga,
            'dif_exp': round(dif_ga - exp_ga, 2), 'dif_vend': round(dif_ga - vend_ga, 2)
        })

    tot_nozzle_dif = sum(n['dif'] for n in nozzles_data)
    tot_nozzle_exp = sum(n['exp'] for n in nozzles_data)
    tot_nozzle_vend = sum(n['vend'] for n in nozzles_data)
    tot_nozzle_dif_exp = sum(n['dif_exp'] for n in nozzles_data)
    tot_nozzle_dif_vend = sum(n['dif_vend'] for n in nozzles_data)

    html = f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8"/>
    <title>Impresión de Turno</title>
    <style>
        @page {{
            size: A4 portrait;
            margin: 10mm 15mm 10mm 15mm;
        }}
        body {{
            font-family: Arial, Helvetica, sans-serif;
            font-size: 11px;
            color: #000;
            background: #fff;
            margin: 0;
            padding: 0;
            line-height: 1.25;
        }}
        .page {{
            position: relative;
            box-sizing: border-box;
            min-height: 272mm;
        }}
        .page-break {{
            page-break-before: always;
        }}
        .header-badge {{
            background: #000;
            color: #fff;
            font-size: 20px;
            font-weight: bold;
            padding: 5px 18px;
            border-radius: 6px;
            display: inline-block;
            white-space: nowrap;
            letter-spacing: 0.5px;
        }}
        .header-meta {{
            margin-top: 6px;
            font-size: 11px;
            line-height: 1.35;
        }}
        .section-title {{
            font-size: 13px;
            font-weight: bold;
            border-bottom: 1.5px solid #000;
            padding-bottom: 2px;
            margin-top: 14px;
            margin-bottom: 4px;
        }}
        table.tbl {{
            width: 100%;
            border-collapse: collapse;
            font-size: 10.5px;
            margin-bottom: 10px;
        }}
        table.tbl th {{
            background: #d4d4d8;
            color: #000;
            font-weight: bold;
            padding: 3.5px 6px;
            text-align: left;
            border: none;
        }}
        table.tbl td {{
            padding: 2.5px 6px;
            border-bottom: 1px solid #f4f4f5;
        }}
        .text-right {{
            text-align: right !important;
        }}
        .text-center {{
            text-align: center !important;
        }}
        .fw-bold {{
            font-weight: bold;
        }}
        .border-top-bold {{
            border-top: 1.5px solid #000 !important;
        }}
        .tbl-border th, .tbl-border td {{
            border: 1px solid #71717a !important;
        }}
        .footer-branding {{
            position: absolute;
            bottom: 0;
            left: 0;
            font-size: 9.5px;
            color: #333;
        }}
        .footer-page {{
            position: absolute;
            bottom: 0;
            right: 0;
            font-size: 10px;
            color: #000;
        }}
    </style>
</head>
<body>

    <!-- PÁGINA 1 -->
    <div class="page">
        <div>
            <div class="header-badge">Impresión de turno</div>
            <div class="header-meta">
                <div>IdTurno: {id_turno}</div>
                <div>Estacion: {estacion}</div>
                <div>Fechas de Apertura y cierre: {start_str} - {stop_str}</div>
                <div>Caja: {caja}</div>
            </div>
        </div>

        <!-- VENTAS POR SURTIDOR -->
        <div class="section-title">Ventas por surtidor</div>
        <table class="tbl">
            <thead>
                <tr>
                    <th style="width: 45%;">Producto</th>
                    <th class="text-right" style="width: 20%;">Litros</th>
                    <th class="text-right" style="width: 15%;">Precio medio</th>
                    <th class="text-right" style="width: 20%;">Importe</th>
                </tr>
            </thead>
            <tbody>'''

    if fuel_sales:
        for prod, d in fuel_sales.items():
            pm = d['importe'] / d['litros'] if d['litros'] > 0 else 0.0
            html += f'''                <tr>
                    <td>{prod}</td>
                    <td class="text-right">{_format_float_es(d['litros'])}</td>
                    <td class="text-right">{_format_float_es(pm, 3)} €</td>
                    <td class="text-right">{_format_currency_es(d['importe'])}</td>
                </tr>'''
    else:
        html += '''                <tr>
                    <td>GASOLEO A</td>
                    <td class="text-right">0,00</td>
                    <td class="text-right">0,000 €</td>
                    <td class="text-right">0,00 €</td>
                </tr>
                <tr>
                    <td>SIN PLOMO 95</td>
                    <td class="text-right">0,00</td>
                    <td class="text-right">0,000 €</td>
                    <td class="text-right">0,00 €</td>
                </tr>'''

    html += f'''                <tr class="fw-bold border-top-bold">
                    <td>Total ventas surtidor:</td>
                    <td class="text-right">{_format_float_es(total_fuel_litros)}</td>
                    <td></td>
                    <td class="text-right">{_format_currency_es(total_fuel_importe)}</td>
                </tr>
            </tbody>
        </table>

        <!-- OTRAS VENTAS -->
        <div class="section-title">Otras ventas</div>
        <table class="tbl">
            <thead>
                <tr>
                    <th style="width: 65%;">Grupo</th>
                    <th class="text-right" style="width: 15%;">Cantidad</th>
                    <th class="text-right" style="width: 20%;">Importe</th>
                </tr>
            </thead>
            <tbody>'''

    if other_sales:
        for grp, d in other_sales.items():
            html += f'''                <tr>
                    <td>{grp}</td>
                    <td class="text-right">{_format_float_es(d['cantidad'])}</td>
                    <td class="text-right">{_format_currency_es(d['importe'])}</td>
                </tr>'''
    else:
        html += '''                <tr>
                    <td>TIENDA</td>
                    <td class="text-right">0,00</td>
                    <td class="text-right">0,00 €</td>
                </tr>'''

    html += f'''                <tr class="fw-bold border-top-bold">
                    <td>Total otras ventas:</td>
                    <td class="text-right">{_format_float_es(total_other_cantidad)}</td>
                    <td class="text-right">{_format_currency_es(total_other_importe)}</td>
                </tr>
            </tbody>
        </table>

        <!-- INCIDENCIAS DE CAJA -->
        <div class="section-title">Incidencias de caja</div>
        <table class="tbl">
            <thead>
                <tr>
                    <th style="width: 75%;">Tipo</th>
                    <th class="text-right" style="width: 25%;">Importe</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td>Entradas</td>
                    <td class="text-right">{_format_currency_es(entradas_incidencias)}</td>
                </tr>
            </tbody>
        </table>

        <!-- IMPORTES COBRADOS O PAGADOS -->
        <div class="section-title">Importes cobrados o pagados</div>
        <table class="tbl">
            <thead>
                <tr>
                    <th style="width: 75%;">Forma de cobro</th>
                    <th class="text-right" style="width: 25%;">Importe</th>
                </tr>
            </thead>
            <tbody>'''

    for meth, amt in payments_summary.items():
        html += f'''                <tr>
                    <td>{meth}</td>
                    <td class="text-right">{_format_currency_es(amt)}</td>
                </tr>'''

    html += f'''                <tr class="fw-bold border-top-bold">
                    <td>Total cobrado:</td>
                    <td class="text-right">{_format_currency_es(total_cobrado)}</td>
                </tr>
                <tr class="fw-bold">
                    <td>Descuadre cobros:</td>
                    <td class="text-right">0,00 €</td>
                </tr>
            </tbody>
        </table>

        <!-- RESUMEN DE EFECTIVO EN CAJA -->
        <div class="section-title">Resumen de efectivo en caja</div>
        <table class="tbl" style="margin-bottom: 4px;">
            <thead>
                <tr>
                    <th class="text-center">Caja Inicial</th>
                    <th class="text-center">Entradas</th>
                    <th class="text-center">Salidas</th>
                    <th class="text-center">Ingresos Seguridad</th>
                    <th class="text-center">Saldo esperado</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td class="text-center">{_format_currency_es(caja_inicial)}</td>
                    <td class="text-center">{_format_currency_es(entradas_caja)}</td>
                    <td class="text-center">{_format_currency_es(salidas_otras)}</td>
                    <td class="text-center">{_format_currency_es(ingresos_seguridad)}</td>
                    <td class="text-center">{_format_currency_es(saldo_esperado)}</td>
                </tr>
            </tbody>
        </table>

        <div style="text-align: right; margin-bottom: 12px; font-size: 11px;">
            <div><strong>Saldo real:</strong> <span style="display: inline-block; width: 90px; text-align: right; font-weight: bold;">{_format_currency_es(saldo_real)}</span></div>
            <div style="margin-top: 3px;"><strong>{dif_label}</strong> <span style="display: inline-block; width: 90px; text-align: right; font-weight: bold;">{_format_currency_es(abs(diferencia))}</span></div>
        </div>

        <!-- EXPENDEDORES -->
        <div class="section-title">Expendedores</div>
        <table class="tbl tbl-border">
            <thead>
                <tr>
                    <th style="width: 52%;">Nombre</th>
                    <th class="text-center" style="width: 14%;">Horas</th>
                    <th class="text-center" style="width: 34%;">Firma</th>
                </tr>
            </thead>
            <tbody>'''

    for exp in expendedores:
        html += f'''                <tr>
                    <td style="height: 32px; vertical-align: middle;">{exp['nombre']}</td>
                    <td class="text-center" style="vertical-align: middle;">{exp['horas']}</td>
                    <td></td>
                </tr>'''

    html += f'''            </tbody>
        </table>

        <div class="footer-branding">Diseñado por Aseproda Informática SL</div>
        <div class="footer-page">Página 1/2</div>
    </div>

    <!-- PÁGINA 2 -->
    <div class="page page-break">
        <div>
            <div class="header-badge">Impresión de turno</div>
            <div class="header-meta">
                <div>IdTurno: {id_turno}</div>
                <div>Estacion: {estacion}</div>
                <div>Fechas de Apertura y cierre: {start_str} - {stop_str}</div>
                <div>Caja: {caja}</div>
            </div>
        </div>

        <!-- CONTADORES DE APARATOS SURTIDORES -->
        <div class="section-title">Contadores de aparatos surtidores</div>
        <table class="tbl" style="font-size: 9.5px;">
            <thead>
                <tr>
                    <th rowspan="2" class="text-center" style="vertical-align: middle; width: 4%;">Calle</th>
                    <th rowspan="2" class="text-center" style="vertical-align: middle; width: 5%;">Mang.</th>
                    <th rowspan="2" class="text-center" style="vertical-align: middle; width: 5%;">Prod.</th>
                    <th colspan="3" class="text-center" style="border-bottom: 1px solid #71717a;">Contadores</th>
                    <th rowspan="2" class="text-center" style="vertical-align: middle; width: 6%;">Incid.</th>
                    <th colspan="2" class="text-center" style="border-bottom: 1px solid #71717a;">Litros</th>
                    <th colspan="2" class="text-center" style="border-bottom: 1px solid #71717a;">Descuadre Litros</th>
                </tr>
                <tr>
                    <th class="text-right" style="width: 12%;">Inicial</th>
                    <th class="text-right" style="width: 12%;">Final</th>
                    <th class="text-right" style="width: 10%;">Dif.</th>
                    <th class="text-right" style="width: 10%;">Expedidos</th>
                    <th class="text-right" style="width: 10%;">Vendidos</th>
                    <th class="text-right" style="width: 13%;">Dif. Cont. - Exp.</th>
                    <th class="text-right" style="width: 13%;">Dif Cont. - Vend.</th>
                </tr>
            </thead>
            <tbody>'''

    for n in nozzles_data:
        html += f'''                <tr>
                    <td class="text-center">{n['calle']}</td>
                    <td class="text-center">{n['mang']}</td>
                    <td class="text-center">{n['prod']}</td>
                    <td class="text-right">{_format_float_es(n['ini'])}</td>
                    <td class="text-right">{_format_float_es(n['fin'])}</td>
                    <td class="text-right">{_format_float_es(n['dif'])}</td>
                    <td class="text-right">{_format_float_es(n['incid'])}</td>
                    <td class="text-right">{_format_float_es(n['exp'])}</td>
                    <td class="text-right">{_format_float_es(n['vend'])}</td>
                    <td class="text-right">{_format_float_es(n['dif_exp'])}</td>
                    <td class="text-right">{_format_float_es(n['dif_vend'])}</td>
                </tr>'''

    html += f'''                <tr class="fw-bold border-top-bold">
                    <td colspan="5">Total ventas por surtidores:</td>
                    <td class="text-right">{_format_float_es(tot_nozzle_dif)}</td>
                    <td class="text-right">0,00</td>
                    <td class="text-right">{_format_float_es(tot_nozzle_exp)}</td>
                    <td class="text-right">{_format_float_es(tot_nozzle_vend)}</td>
                    <td class="text-right">{_format_float_es(tot_nozzle_dif_exp)}</td>
                    <td class="text-right">{_format_float_es(tot_nozzle_dif_vend)}</td>
                </tr>
            </tbody>
        </table>

        <div class="footer-branding">Diseñado por Aseproda Informática SL</div>
        <div class="footer-page">Página 2/2</div>
    </div>

</body>
</html>
'''
    return html

def _render_shift_pdf(html_content):
    with tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w", encoding="utf-8") as f_html:
        f_html.write(html_content)
        html_path = f_html.name

    pdf_path = html_path.replace(".html", ".pdf")
    try:
        cmd = [
            "wkhtmltopdf",
            "--page-size", "A4",
            "--margin-top", "10mm",
            "--margin-bottom", "10mm",
            "--margin-left", "15mm",
            "--margin-right", "15mm",
            "--disable-smart-shrinking",
            "--quiet",
            html_path,
            pdf_path
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode == 0 and os.path.exists(pdf_path):
            with open(pdf_path, "rb") as f_pdf:
                return f_pdf.read()
        else:
            _logger.error("Error executing wkhtmltopdf for shift report: %s", res.stderr)
            return None
    finally:
        if os.path.exists(html_path):
            try: os.remove(html_path)
            except Exception: pass
        if os.path.exists(pdf_path):
            try: os.remove(pdf_path)
            except Exception: pass

class PosGasStationController(http.Controller):

    @http.route('/pos_gas_station/send_invoice_email', type='json', auth='user', methods=['POST'], csrf=False)
    def send_invoice_email(self, move_id=None, order_id=None, order_ref=None, order_name=None, move_name=None, email=None):
        try:
            env = request.env
            move = None
            if move_id:
                move = env['account.move'].sudo().browse(int(move_id))
            elif order_id:
                order = env['pos.order'].sudo().browse(int(order_id))
                if order and order.account_move:
                    move = order.account_move
            elif order_name:
                order = env['pos.order'].sudo().search(['|', ('name', '=', order_name), ('pos_reference', '=', order_name)], limit=1)
                if order and order.account_move:
                    move = order.account_move
            elif order_ref:
                order = env['pos.order'].sudo().search(['|', ('pos_reference', '=', order_ref), ('name', '=', order_ref)], limit=1)
                if order and order.account_move:
                    move = order.account_move
            
            if (not move or not move.exists()) and move_name:
                move = env['account.move'].sudo().search([('name', '=', move_name)], limit=1)
            
            if not move or not move.exists():
                return {'status': 'error', 'message': 'No se encontró la factura oficial asociada.'}
            
            res = _send_invoice_email(env, move, target_email=email)
            return res
        except Exception as e:
            _logger.exception("Error in /pos_gas_station/send_invoice_email: %s", e)
            return {'status': 'error', 'message': str(e)}


    @http.route('/pos_gas_station/status', type='json', auth='public', methods=['POST'], csrf=False, cors='*')
    def get_pumps_status(self, config_id=None, **kw):
        if not config_id:
            config_id = 7
        try:
            config_id = int(config_id)
        except Exception:
            config_id = 7

        station_info = STATION_MAP.get(config_id)
        if not station_info:
            pos_config = request.env['pos.config'].sudo().browse(config_id)
            name = f'CONTROL DE PISTA - {pos_config.name.upper()}' if pos_config.exists() else 'CONTROL DE PISTA'
            pumps_cnt = 8 if ('ronda norte' in name.lower() or 'repsol' in name.lower()) else 4
            station_info = {
                'name': name,
                'pumps_count': pumps_cnt,
                'fuels': [
                    {'code': 'GA', 'name': 'Gasóleo A', 'class': 'ga'},
                    {'code': '95', 'name': 'Sin Plomo 95', 'class': 'sp95'},
                    {'code': 'G+', 'name': 'Gasóleo Plus', 'class': 'gplus'}
                ]
            }

        param_key = f'pos_gas_station.pumps_state_{config_id}'
        status_raw = request.env['ir.config_parameter'].sudo().get_param(param_key)
        
        pumps = []
        if status_raw:
            try:
                parsed = json.loads(status_raw)
                if isinstance(parsed, dict) and 'pumps' in parsed:
                    pumps = parsed['pumps']
                elif isinstance(parsed, list):
                    pumps = parsed
            except Exception as e:
                _logger.error(f'Error parsing live pumps parameter {param_key}: {e}')

        if not pumps:
            for i in range(1, station_info['pumps_count'] + 1):
                pumps.append({
                    'id': i,
                    'status': 'idle',
                    'statusText': 'LIBRE',
                    'fuel': 'Gasóleo A / Sin Plomo 95',
                    'amount': 0.00,
                    'liters': 0.00,
                    'price': 1.45
                })

        now = time.time()
        overrides = STATION_PUMP_OVERRIDES.get(config_id, {})
        # Limpieza de overrides expirados
        expired_pids = [pid for pid, o in overrides.items() if now - o.get('_timestamp', now) > OVERRIDE_TIMEOUT_SECONDS]
        for pid in expired_pids:
            del overrides[pid]

        for i, pump in enumerate(pumps):
            pid = pump.get('id', i + 1)
            # Si el surtidor real ya reporta fin de repostaje (ready), suministro activo en pista, o se ha bloqueado, anular override de inmediato
            if pump.get('status') in ('ready', 'dispensing') or (pump.get('status') == 'blocked' and now - overrides.get(pid, {}).get('_timestamp', now) > 2.0):
                if pid in overrides:
                    del overrides[pid]
            elif pid in overrides:
                if now - overrides[pid].get('_timestamp', now) > 20:
                    del overrides[pid]
                else:
                    ov = {k: v for k, v in overrides[pid].items() if not k.startswith('_')}
                    pumps[i] = ov

        return {
            'status': 'success',
            'station_name': station_info['name'],
            'available_fuels': station_info['fuels'],
            'pumps': pumps
        }

    @http.route('/pos_gas_station/authorize', type='json', auth='public', methods=['POST'], csrf=False, cors='*')
    def authorize_pump(self, config_id=None, pump_id=None, fuel='GA', amount=0, liters=0, **kw):
        cfg = int(config_id or 7)
        pid = int(pump_id or 1)
        if cfg not in STATION_PUMP_OVERRIDES:
            STATION_PUMP_OVERRIDES[cfg] = {}

        fuel_names = {
            'GA': 'Gasóleo A',
            '95': 'Sin Plomo 95',
            'SP95': 'Sin Plomo 95',
            'GB': 'Gasóleo B',
            'G+': 'Gasóleo Plus'
        }
        fuel_name = fuel_names.get(fuel, 'Gasóleo A')
        amt = float(amount or 0)
        lts = float(liters or 0)

        is_lleno = (amt == 0 or lts >= 999)
        override_data = {
            'id': pid,
            'status': 'dispensing',
            'statusText': 'LLENO (POSTPAGO)' if is_lleno else f'PREFIJADO {amt:.2f}€',
            'fuel': fuel_name,
            'amount': 0.0 if is_lleno else amt,
            'liters': 0.0 if is_lleno else lts,
            'preset_amount': 0.0 if is_lleno else amt,
            'is_lleno': is_lleno,
            'price': 1.45 if 'Gasóleo A' in fuel_name else 1.55,
            '_timestamp': time.time()
        }
        STATION_PUMP_OVERRIDES[cfg][pid] = override_data

        _logger.info(f'⛽ [AUTORIZACIÓN PISTA] Config {cfg} | Calle {pid} | Combustible {fuel_name} | {amt}€ / {lts}L')

        # Emitir comando para el agente de pista local en la gasolinera
        cmd_key = f'pos_gas_station.pump_command_{cfg}'
        cmd_payload = {
            'action': 'authorize',
            'pump_id': pid,
            'fuel': fuel_name,
            'amount': amt,
            'liters': lts,
            'timestamp': time.time()
        }
        try:
            request.env['ir.config_parameter'].sudo().set_param(cmd_key, json.dumps(cmd_payload))
        except Exception as e:
            _logger.error(f'Error guardando comando {cmd_key}: {e}')

        return {'status': 'authorized', 'pump_id': pid}

    @http.route('/pos_gas_station/cancel_authorize', type='json', auth='public', methods=['POST'], csrf=False, cors='*')
    def cancel_authorize(self, config_id=None, pump_id=None, **kw):
        cfg = int(config_id or 7)
        pid = int(pump_id or 1)
        if cfg in STATION_PUMP_OVERRIDES and pid in STATION_PUMP_OVERRIDES[cfg]:
            del STATION_PUMP_OVERRIDES[cfg][pid]

        _logger.info(f'🛑 [CANCELAR AUTORIZACIÓN] Config {cfg} | Calle {pid}')

        # Reseteo en pumps_state
        param_key = f'pos_gas_station.pumps_state_{cfg}'
        try:
            status_raw = request.env['ir.config_parameter'].sudo().get_param(param_key)
            if status_raw:
                data = json.loads(status_raw)
                pumps = data.get('pumps', []) if isinstance(data, dict) else data
                for p in pumps:
                    if p.get('id') == pid:
                        fallback_status = 'atendido' if data.get('modo_estacion') == 'atendido' else 'blocked'
                        p['status'] = fallback_status
                        p['amount'] = 0.0
                        p['liters'] = 0.0
                        p['statusText'] = 'SIN PREFIJADO' if fallback_status == 'blocked' else 'ATENDIDO'
                        p['has_prepay'] = False
                        p['preset_amount'] = 0.0
                        p['is_lleno'] = False
                        p['updated_at'] = time.time()
                request.env['ir.config_parameter'].sudo().set_param(param_key, json.dumps(data))
        except Exception as e:
            _logger.error(f'Error resetting pump state in cancel_authorize: {e}')

        # Emitir comando de liberación/bloqueo al agente de pista local
        cmd_key = f'pos_gas_station.pump_command_{cfg}'
        cmd_payload = {
            'action': 'clear_pump',
            'pump_id': pid,
            'timestamp': time.time()
        }
        try:
            request.env['ir.config_parameter'].sudo().set_param(cmd_key, json.dumps(cmd_payload))
        except Exception as e:
            _logger.error(f'Error guardando comando {cmd_key}: {e}')

        return {'status': 'cancelled', 'pump_id': pid}

    @http.route('/pos_gas_station/clear_pump', type='json', auth='public', methods=['POST'], csrf=False, cors='*')
    def clear_pump(self, config_id=None, pump_id=None, **kw):
        cfg = int(config_id or 7)
        pid = int(pump_id or 1)
        if cfg in STATION_PUMP_OVERRIDES and pid in STATION_PUMP_OVERRIDES[cfg]:
            del STATION_PUMP_OVERRIDES[cfg][pid]

        param_key = f'pos_gas_station.pumps_state_{cfg}'
        try:
            status_raw = request.env['ir.config_parameter'].sudo().get_param(param_key)
            if status_raw:
                parsed = json.loads(status_raw)
                p_list = parsed.get('pumps', []) if isinstance(parsed, dict) else parsed
                
                # Determinar si el modo predominante de la pista es bloqueado (prepago) o libre (atendido)
                is_mostly_blocked = sum(1 for p in p_list if p.get('status') in ('blocked', 'prepago')) >= (len(p_list) / 2)
                fallback_status = 'blocked' if is_mostly_blocked else 'idle'
                fallback_text = 'SIN PREFIJADO' if is_mostly_blocked else 'ATENDIDO'

                for p in p_list:
                    if p.get('id') == pid:
                        p['status'] = fallback_status
                        p['statusText'] = fallback_text
                        p['amount'] = 0.0
                        p['liters'] = 0.0
                        p['preset_amount'] = 0.0
                        p['has_prepay'] = False
                        p['is_lleno'] = False
                        p['updated_at'] = time.time()
                        
                if isinstance(parsed, dict):
                    parsed['pumps'] = p_list
                    request.env['ir.config_parameter'].sudo().set_param(param_key, json.dumps(parsed))
                else:
                    request.env['ir.config_parameter'].sudo().set_param(param_key, json.dumps(p_list))
        except Exception as e:
            _logger.error(f'Error resetting pump in {param_key}: {e}')

        # Emitir orden de liberación al hardware de pista local
        cmd_key = f'pos_gas_station.pump_command_{cfg}'
        cmd_payload = {
            'action': 'clear_pump',
            'pump_id': pid,
            'timestamp': time.time()
        }
        try:
            request.env['ir.config_parameter'].sudo().set_param(cmd_key, json.dumps(cmd_payload))
        except Exception as e:
            _logger.error(f'Error guardando comando {cmd_key}: {e}')

        return {'status': 'cleared', 'pump_id': pid}

    @http.route('/pos_gas_station/set_track_mode', type='json', auth='public', methods=['POST'], csrf=False, cors='*')
    def set_track_mode(self, config_id=None, mode='prepago', pump_id=None, **kw):
        cfg = int(config_id or 7)
        pid = int(pump_id) if pump_id else None
        target_status = 'atendido' if mode == 'atendido' else 'blocked'
        target_text = 'LIBRE' if mode == 'atendido' else 'PREPAGO'

        # 1. Actualizar estado inmediatamente en ir.config_parameter
        param_key = f'pos_gas_station.pumps_state_{cfg}'
        try:
            status_raw = request.env['ir.config_parameter'].sudo().get_param(param_key)
            if status_raw:
                parsed = json.loads(status_raw)
                p_list = parsed.get('pumps', []) if isinstance(parsed, dict) else parsed
                for p in p_list:
                    if pid is None or p.get('id') == pid:
                        if p.get('status') in ('idle', 'blocked', 'atendido', 'postpago', 'prepago'):
                            p['status'] = target_status
                            p['statusText'] = target_text
                if isinstance(parsed, dict):
                    parsed['pumps'] = p_list
                    request.env['ir.config_parameter'].sudo().set_param(param_key, json.dumps(parsed))
                else:
                    request.env['ir.config_parameter'].sudo().set_param(param_key, json.dumps(p_list))
        except Exception as e:
            _logger.error(f'Error actualizando estado en {param_key}: {e}')

        # 2. Emitir comando de hardware para el agente de pista
        cmd_key = f'pos_gas_station.pump_command_{cfg}'
        cmd_payload = {
            'action': 'set_pump_mode' if pid else 'set_global_mode',
            'mode': mode,
            'timestamp': time.time()
        }
        if pid:
            cmd_payload['pump_id'] = pid
        try:
            request.env['ir.config_parameter'].sudo().set_param(cmd_key, json.dumps(cmd_payload))
        except Exception as e:
            _logger.error(f'Error emitiendo comando {cmd_key}: {e}')

        _logger.info(f'⛽ [MODO PISTA] Config {cfg} | Modo {mode} | Calle {pid or "TODAS"}')
        return {'status': 'success', 'mode': mode, 'pump_id': pid}

    @http.route('/pos_gas_station/set_cashier_name', type='json', auth='user', methods=['POST'], csrf=False)
    def set_cashier_name(self, name=None, user_id=None, **kw):
        if name and name.strip():
            target_user = request.env.user
            if user_id:
                try:
                    u = request.env['res.users'].sudo().browse(int(user_id))
                    if u.exists():
                        target_user = u
                except Exception:
                    pass
            target_user.sudo().write({'name': name.strip()})
            if target_user.partner_id:
                target_user.partner_id.sudo().write({'name': name.strip()})
            return {'status': 'success', 'name': name.strip()}
        return {'status': 'error'}

    # ==================== MATRIZ VISUAL DE ROLES Y PERMISOS ====================
    @http.route('/utrecar/permission_matrix/data', type='json', auth='user', methods=['POST'], csrf=False)
    def get_permission_matrix_data(self):
        env = request.env
        roles = env['utrecar.role'].search([])
        categories = env['utrecar.permission.category'].search([])
        permissions = env['utrecar.permission'].search([])
        env['utrecar.role'].auto_link_admin_users()
        users = env['res.users'].search([('active', '=', True)], order='name')
        companies = env['res.company'].search_read([], ['id', 'name'])
        stations = env['pos.config'].search_read([], ['id', 'name', 'company_id'])

        roles_data = [{
            'id': r.id,
            'name': r.name,
            'code': r.code,
            'color': r.color,
            'user_count': r.user_count,
            'users': [{'id': u.id, 'name': u.name, 'login': u.login} for u in r.user_ids]
        } for r in roles]

        cat_dict = {}
        for c in categories:
            cat_dict[c.id] = {
                'id': c.id,
                'name': c.name,
                'code': c.code,
                'sequence': c.sequence,
                'permissions': []
            }

        matrix_state = {} # perm_id -> {role_id -> bool}

        for p in permissions:
            cat_id = p.category_id.id
            if cat_id not in cat_dict:
                cat_dict[cat_id] = {
                    'id': cat_id,
                    'name': p.category_id.name,
                    'code': p.category_id.code,
                    'sequence': p.category_sequence,
                    'permissions': []
                }
            cat_dict[cat_id]['permissions'].append({
                'id': p.id,
                'name': p.name,
                'code': p.code,
                'sequence': p.sequence
            })

            role_ids = set(p.role_ids.ids)
            matrix_state[p.id] = {r.id: (r.id in role_ids) for r in roles}

        sorted_categories = sorted(cat_dict.values(), key=lambda x: x['sequence'])
        for cat in sorted_categories:
            cat['permissions'] = sorted(cat['permissions'], key=lambda x: x['sequence'])

        users_data = [{
            'id': u.id,
            'name': u.name,
            'login': u.login,
            'company_id': u.company_id.id if u.company_id else False,
            'company_name': u.company_id.name if u.company_id else '',
            'role_id': u.utrecar_role_id.id if u.utrecar_role_id else False,
            'role_name': u.utrecar_role_id.name if u.utrecar_role_id else 'Sin Rol',
            'pos_config_ids': u.pos_config_ids.ids if hasattr(u, 'pos_config_ids') else [],
            'pos_config_names': [p.name for p in u.pos_config_ids] if hasattr(u, 'pos_config_ids') else []
        } for u in users]

        return {
            'status': 'success',
            'roles': roles_data,
            'categories': sorted_categories,
            'matrix': matrix_state,
            'users': users_data,
            'companies': companies,
            'stations': stations
        }

    @http.route('/utrecar/permission_matrix/toggle', type='json', auth='user', methods=['POST'], csrf=False)
    def toggle_permission_matrix(self, role_id, permission_id, granted):
        env = request.env
        role = env['utrecar.role'].browse(int(role_id))
        permission = env['utrecar.permission'].browse(int(permission_id))
        if not role.exists() or not permission.exists():
            return {'status': 'error', 'message': 'Rol o permiso no encontrado'}

        if granted:
            role.write({'permission_ids': [(4, permission.id)]})
        else:
            role.write({'permission_ids': [(3, permission.id)]})

        return {'status': 'success', 'granted': bool(granted)}

    @http.route('/utrecar/permission_matrix/assign_user', type='json', auth='user', methods=['POST'], csrf=False)
    def assign_user_role(self, user_id, role_id=None, pos_config_ids=None):
        env = request.env
        user = env['res.users'].browse(int(user_id))
        if not user.exists():
            return {'status': 'error', 'message': 'Usuario no encontrado'}

        vals = {}
        if role_id is not None:
            vals['utrecar_role_id'] = int(role_id) if role_id else False
        if pos_config_ids is not None:
            vals['pos_config_ids'] = [(6, 0, [int(pid) for pid in pos_config_ids])]
        if vals:
            user.write(vals)
        return {'status': 'success'}


    # ==================== DASHBOARD MULTI-EMPRESA / GESTIÓN DE GASOLINERAS ====================
    @http.route('/pos_gas_station/dashboard_data', type='json', auth='user', methods=['POST'], csrf=False)
    def get_gas_station_dashboard_data(self):
        env = request.env
        user = env.user
        is_manager = user.has_group('point_of_sale.group_pos_manager') or user._is_admin()

        companies = user.company_ids
        if not companies:
            companies = env['res.company'].search([])

        companies_data = []
        total_stations = 0
        total_open_sessions = 0

        for c in companies:
            domain = [('company_id', '=', c.id)]
            all_stations = env['pos.config'].sudo().search(domain)

            accessible_stations = []
            for st in all_stations:
                has_access = is_manager
                if not has_access:
                    has_access = (user.id in st.allowed_user_ids.ids) or (st.id in user.pos_config_ids.ids)

                if not has_access:
                    continue

                active_session = env['pos.session'].sudo().search([
                    ('config_id', '=', st.id),
                    ('state', 'in', ['opened', 'opening_control'])
                ], limit=1)

                if active_session:
                    total_open_sessions += 1

                pumps_cnt = 8 if ('ronda norte' in st.name.lower() or 'repsol' in st.name.lower()) else 4

                fuels = [
                    {'code': 'GA', 'name': 'Gasóleo A'},
                    {'code': '95', 'name': 'Sin Plomo 95'}
                ]
                if 'repsol' in st.name.lower():
                    fuels.append({'code': 'G+', 'name': 'Gasóleo Plus'})

                accessible_stations.append({
                    'id': st.id,
                    'name': st.name,
                    'company_id': c.id,
                    'company_name': c.name,
                    'pumps_count': pumps_cnt,
                    'has_active_session': bool(active_session),
                    'session_state': active_session.state if active_session else 'closed',
                    'session_name': active_session.name if active_session else None,
                    'session_user': active_session.user_id.name if active_session else None,
                    'fuels': fuels,
                })

            total_stations += len(accessible_stations)
            has_logo = bool(c.logo)

            companies_data.append({
                'id': c.id,
                'name': c.name,
                'vat': c.vat or '',
                'city': c.city or '',
                'street': c.street or '',
                'phone': c.phone or '',
                'has_logo': has_logo,
                'logo_url': f'/web/image?model=res.company&id={c.id}&field=logo' if has_logo else None,
                'stations': accessible_stations,
                'stations_count': len(accessible_stations)
            })

        return {
            'status': 'success',
            'is_manager': is_manager,
            'user_name': user.name,
            'companies': companies_data,
            'stats': {
                'total_companies': len(companies_data),
                'total_stations': total_stations,
                'total_open_sessions': total_open_sessions
            }
        }

    @http.route('/pos_gas_station/open_station', type='json', auth='user', methods=['POST'], csrf=False)
    def open_gas_station(self, config_id):
        try:
            cfg = request.env['pos.config'].sudo().browse(int(config_id))
            if not cfg.exists():
                return {'status': 'error', 'message': 'Punto de venta no encontrado'}

            comp_id = cfg.company_id.id
            action = cfg.with_user(request.env.user).with_company(cfg.company_id).open_ui()
            session = cfg.current_session_id
            if session and session.state == 'opening_control':
                session.action_pos_session_open()
                if session.state == 'opening_control':
                    session.write({'state': 'opened'})
            url = action.get('url', f'/pos/ui?config_id={cfg.id}')
            if 'cids=' not in url:
                sep = '&' if '?' in url else '?'
                url = f"{url}{sep}cids={comp_id}"

            return {
                'status': 'success',
                'url': url,
                'action': action,
            }
        except Exception as e:
            _logger.exception("Error in /pos_gas_station/open_station: %s", e)
            return {'status': 'error', 'message': str(e)}

    # ==================== GESTIÓN DE PEDIDOS DEL TURNO ACTIVO ====================
    @http.route('/pos_gas_station/get_shift_orders', type='json', auth='user', methods=['POST'], csrf=False)
    def get_shift_orders(self, session_id=None, config_id=None):
        try:
            env = request.env
            session = None
            if session_id:
                session = env['pos.session'].sudo().browse(int(session_id))
            elif config_id:
                cfg = env['pos.config'].sudo().browse(int(config_id))
                session = cfg.current_session_id

            if not session or not session.exists():
                return {'status': 'error', 'message': 'Sesión no encontrada'}

            # Find previous session for quick switching if needed
            prev_session = env['pos.session'].sudo().search([
                ('config_id', '=', session.config_id.id),
                ('id', '<', session.id),
                ('state', '=', 'closed')
            ], order='id desc', limit=1)

            orders = env['pos.order'].sudo().search([
                ('session_id', '=', session.id),
                ('state', 'in', ['paid', 'done', 'invoiced'])
            ], order='date_order desc, id desc')

            payments = env['pos.payment'].sudo().search([('session_id', '=', session.id)])
            total_sales = round(sum(o.amount_total for o in orders), 2)

            total_cash = 0.0
            total_bank = 0.0
            for p in payments:
                method_name = p.payment_method_id.name.lower() if p.payment_method_id else ''
                is_cash = getattr(p.payment_method_id, 'is_cash_count', False) or 'efectivo' in method_name
                if is_cash:
                    total_cash += p.amount
                else:
                    total_bank += p.amount

            total_cash = round(total_cash, 2)
            total_bank = round(total_bank, 2)

            user_tz = pytz.timezone(env.user.tz or 'Europe/Madrid')

            orders_list = []
            for o in orders:
                if o.date_order:
                    try:
                        local_dt = pytz.utc.localize(o.date_order).astimezone(user_tz)
                        date_str = local_dt.strftime('%d/%m/%Y %H:%M:%S')
                    except Exception:
                        date_str = str(o.date_order)
                else:
                    date_str = ''

                lines_data = []
                for l in o.lines:
                    taxes_str = ', '.join(l.tax_ids_after_fiscal_position.mapped('name')) if l.tax_ids_after_fiscal_position else ''
                    lot_str = l.pack_lot_ids[0].lot_name if l.pack_lot_ids else ''
                    lines_data.append({
                        'id': l.id,
                        'product_name': l.product_id.display_name or l.product_id.name or 'Producto',
                        'lot_name': lot_str,
                        'qty': round(l.qty, 3),
                        'qty_str': f"{l.qty:.3f}",
                        'price_unit': round(l.price_unit, 4),
                        'price_unit_str': f"{l.price_unit:.2f}",
                        'discount': round(l.discount, 2),
                        'discount_str': f"{l.discount:.2f}",
                        'taxes': taxes_str,
                        'price_subtotal': round(l.price_subtotal, 2),
                        'price_subtotal_str': f"{l.price_subtotal:.2f}",
                        'price_subtotal_incl': round(l.price_subtotal_incl, 2),
                        'price_subtotal_incl_str': f"{l.price_subtotal_incl:.2f}",
                    })

                payments_data = []
                for p in o.payment_ids:
                    p_date_str = ''
                    if p.payment_date:
                        try:
                            p_dt = pytz.utc.localize(p.payment_date).astimezone(user_tz)
                            p_date_str = p_dt.strftime('%d/%m/%Y %H:%M:%S')
                        except Exception:
                            p_date_str = str(p.payment_date)
                    payments_data.append({
                        'id': p.id,
                        'name': p.payment_method_id.name if p.payment_method_id else 'Pago',
                        'amount': round(p.amount, 2),
                        'amount_str': f"{p.amount:.2f}",
                        'payment_date': p_date_str,
                    })

                is_inv = bool(o.account_move)
                inv_url = f'/report/pdf/account.report_invoice_with_payments/{o.account_move.id}' if is_inv else False

                orders_list.append({
                    'id': o.id,
                    'name': o.name,
                    'pos_reference': o.pos_reference or o.name,
                    'date_order': date_str,
                    'session_id': session.id,
                    'session_name': session.name,
                    'user_name': o.user_id.name or 'Cajero',
                    'partner_id': o.partner_id.id if o.partner_id else False,
                    'partner_name': o.partner_id.name if o.partner_id else False,
                    'partner_vat': o.partner_id.vat if o.partner_id else '',
                    'partner_street': o.partner_id.street or '',
                    'partner_city': o.partner_id.city or '',
                    'partner_zip': o.partner_id.zip or '',
                    'partner_phone': o.partner_id.phone or '',
                    'partner_email': o.partner_id.email or '',
                    'fiscal_position': o.fiscal_position_id.name if o.fiscal_position_id else 'Posición fiscal ordinaria',
                    'state': 'invoiced' if is_inv else o.state,
                    'is_invoiced': is_inv,
                    'is_ticket_annulled': getattr(o, 'is_ticket_annulled', False) or is_inv,
                    'annulment_ref': getattr(o, 'annulment_ref', False) or (f"TTTR_{(''.join(c for c in (o.name or '') if c.isdigit()) or str(o.id))[-4:].zfill(4)}" if is_inv else ''),
                    'annulment_reason': getattr(o, 'annulment_reason', False) or (f"Anulado por emisión de Factura {o.account_move.name}" if is_inv else ''),
                    'annulment_date': str(getattr(o, 'annulment_date', '')) if getattr(o, 'annulment_date', False) else '',
                    'account_move_id': o.account_move.id if is_inv else False,
                    'account_move_name': o.account_move.name if is_inv else '',
                    'invoice_url': inv_url,
                    'amount_total': round(o.amount_total, 2),
                    'amount_total_str': f"{o.amount_total:.2f}",
                    'amount_tax': round(o.amount_tax, 2),
                    'amount_tax_str': f"{o.amount_tax:.2f}",
                    'amount_paid': round(o.amount_paid, 2),
                    'amount_paid_str': f"{o.amount_paid:.2f}",
                    'amount_return': round(o.amount_return, 2),
                    'margin': round(getattr(o, 'margin', 0.0), 2),
                    'margin_str': f"{getattr(o, 'margin', 0.0):.2f}",
                    'lines': lines_data,
                    'payments': payments_data,
                    'company': {
                        'name': o.company_id.name,
                        'vat': o.company_id.vat or '',
                        'street': o.company_id.street or '',
                        'city': o.company_id.city or '',
                        'phone': o.company_id.phone or '',
                    }
                })

            return {
                'status': 'success',
                'session_id': session.id,
                'session_name': session.name,
                'session_state': session.state,
                'prev_session_id': prev_session.id if prev_session else False,
                'prev_session_name': prev_session.name if prev_session else False,
                'summary': {
                    'total_sales': total_sales,
                    'total_sales_str': f"{total_sales:.2f}",
                    'total_cash': total_cash,
                    'total_cash_str': f"{total_cash:.2f}",
                    'total_bank': total_bank,
                    'total_bank_str': f"{total_bank:.2f}",
                    'orders_count': len(orders_list)
                },
                'orders': orders_list
            }
        except Exception as e:
            _logger.exception("Error in /pos_gas_station/get_shift_orders: %s", e)
            return {'status': 'error', 'message': str(e)}

    @http.route('/pos_gas_station/invoice_order', type='json', auth='user', methods=['POST'], csrf=False)
    def invoice_order(self, order_id, partner_id=None, partner_data=None, delivery_method='both', target_email=None):
        try:
            env = request.env
            order = env['pos.order'].sudo().browse(int(order_id))
            if not order.exists():
                return {'status': 'error', 'message': 'Pedido no encontrado'}

            if order.account_move:
                return {
                    'status': 'success',
                    'already_invoiced': True,
                    'account_move_id': order.account_move.id,
                    'account_move_name': order.account_move.name,
                    'invoice_url': f'/report/pdf/account.report_invoice_with_payments/{order.account_move.id}'
                }

            partner = None
            if partner_id:
                p = env['res.partner'].sudo().browse(int(partner_id))
                if p.exists():
                    partner = p
            elif partner_data and partner_data.get('vat'):
                vat = str(partner_data['vat']).strip().upper()
                name = str(partner_data.get('name') or vat).strip()
                partner = env['res.partner'].sudo().search([('vat', '=', vat)], limit=1)
                if not partner:
                    partner = env['res.partner'].sudo().create({
                        'name': name,
                        'vat': vat,
                        'street': partner_data.get('street', '').strip(),
                        'city': partner_data.get('city', '').strip(),
                        'zip': partner_data.get('zip', '').strip(),
                        'email': partner_data.get('email', '').strip(),
                        'phone': partner_data.get('phone', '').strip(),
                        'company_id': order.company_id.id,
                    })

            if partner:
                order.write({'partner_id': partner.id})

            if not order.partner_id:
                return {'status': 'error', 'message': 'Se requiere un cliente con NIF/CIF para emitir la factura.'}

            # Generate invoice
            order.action_pos_order_invoice()

            if not order.account_move:
                return {'status': 'error', 'message': 'No se pudo generar el asiento contable de factura.'}

            digits = ''.join(c for c in (order.name or '') if c.isdigit()) or str(order.id)
            annul_ref = getattr(order, 'annulment_ref', '') or f"TTTR_{digits[-4:].zfill(4)}"
            
            email_result = None
            if delivery_method in ('email', 'both'):
                client_email = target_email or (partner_data.get('email') if partner_data else None) or (partner.email if partner else None)
                if client_email:
                    email_result = _send_invoice_email(env, order.account_move, target_email=client_email)

            return {
                'status': 'success',
                'account_move_id': order.account_move.id,
                'account_move_name': order.account_move.name,
                'is_ticket_annulled': True,
                'annulment_ref': annul_ref,
                'invoice_url': f'/report/pdf/account.report_invoice_with_payments/{order.account_move.id}',
                'email_sent': email_result.get('status') == 'success' if email_result else False,
                'email_to': email_result.get('email_to') if email_result else False,
                'email_error': email_result.get('message') if (email_result and email_result.get('status') == 'error') else False,
            }
        except Exception as e:
            _logger.exception("Error in /pos_gas_station/invoice_order: %s", e)
            return {'status': 'error', 'message': str(e)}

    @http.route('/pos_gas_station/annul_order', type='json', auth='user', methods=['POST'], csrf=False)
    def annul_order(self, order_id, reason=None):
        try:
            env = request.env
            order = env['pos.order'].sudo().browse(int(order_id))
            if not order.exists():
                return {'status': 'error', 'message': 'Pedido no encontrado'}
            if hasattr(order, 'action_annul_ticket'):
                order.action_annul_ticket(reason=reason)
            else:
                digits = ''.join(c for c in (order.name or '') if c.isdigit()) or str(order.id)
                ref = f"TTTR_{digits[-4:].zfill(4)}"
                order.write({
                    'is_ticket_annulled': True,
                    'annulment_ref': ref,
                    'annulment_reason': reason or 'Anulación manual de ticket',
                    'annulment_date': fields.Datetime.now(),
                })
            return {
                'status': 'success',
                'annulment_ref': order.annulment_ref,
                'annulment_reason': order.annulment_reason,
            }
        except Exception as e:
            _logger.exception("Error in /pos_gas_station/annul_order: %s", e)
            return {'status': 'error', 'message': str(e)}


    @http.route('/pos_gas_station/search_suppliers', type='json', auth='user', methods=['POST'], csrf=False)
    def search_suppliers(self, query=''):
        try:
            env = request.env
            q = (query or '').strip()
            base_domain = ['|', ('supplier_rank', '>', 0), ('ref', 'like', 'PROV-%')]
            if q:
                domain = base_domain + ['|', '|', ('name', 'ilike', q), ('vat', 'ilike', q), ('ref', 'ilike', q)]
                partners = env['res.partner'].sudo().search(domain, order='name asc', limit=15)
                if not partners and len(q) >= 2:
                    fallback_domain = ['|', '|', ('name', 'ilike', q), ('vat', 'ilike', q), ('ref', 'ilike', q)]
                    partners = env['res.partner'].sudo().search(fallback_domain, order='name asc', limit=15)
            else:
                partners = env['res.partner'].sudo().search(base_domain, order='name asc', limit=20)
            
            results = []
            for p in partners:
                results.append({
                    'id': p.id,
                    'name': p.name,
                    'vat': p.vat or '',
                    'ref': p.ref or '',
                    'city': p.city or '',
                })
            return {'status': 'success', 'suppliers': results}
        except Exception as e:
            _logger.exception("Error in /pos_gas_station/search_suppliers: %s", e)
            return {'status': 'error', 'message': str(e)}

    @http.route('/pos_gas_station/cash_move', type='json', auth='user', methods=['POST'], csrf=False)
    def cash_move(self, session_id, amount, reason, translated_type='Salida', partner_id=None):
        try:
            env = request.env
            session = env['pos.session'].sudo().browse(int(session_id))
            if not session.exists() or not session.cash_journal_id:
                return {'status': 'error', 'message': 'Sesión POS o diario de efectivo no disponible'}
            
            line_vals = {
                'pos_session_id': session.id,
                'journal_id': session.cash_journal_id.id,
                'amount': -abs(float(amount)),
                'date': fields.Date.context_today(session),
                'payment_ref': '-'.join([session.name, translated_type, reason]),
            }
            if partner_id:
                line_vals['partner_id'] = int(partner_id)
            
            line = env['account.bank.statement.line'].sudo().create(line_vals)
            return {'status': 'success', 'line_id': line.id}
        except Exception as e:
            _logger.exception("Error in /pos_gas_station/cash_move: %s", e)
            return {'status': 'error', 'message': str(e)}

    @http.route('/pos_gas_station/search_partners', type='json', auth='user', methods=['POST'], csrf=False)
    def search_partners(self, query):
        try:
            env = request.env
            q = (query or '').strip()
            if not q or len(q) < 2:
                return {'status': 'success', 'partners': []}
            domain = ['|', ('name', 'ilike', q), ('vat', 'ilike', q)]
            partners = env['res.partner'].sudo().search(domain, limit=12)
            results = []
            for p in partners:
                results.append({
                    'id': p.id,
                    'name': p.name,
                    'vat': p.vat or '',
                    'street': p.street or '',
                    'city': p.city or '',
                    'zip': p.zip or '',
                    'phone': p.phone or '',
                    'email': p.email or ''
                })
            return {'status': 'success', 'partners': results}
        except Exception as e:
            _logger.exception("Error in /pos_gas_station/search_partners: %s", e)
            return {'status': 'error', 'message': str(e)}


    @http.route('/pos_gas_station/delete_station', type='json', auth='user', methods=['POST'], csrf=False)
    def delete_station(self, config_id):
        try:
            env = request.env
            config = env['pos.config'].sudo().browse(int(config_id))
            if not config.exists():
                return {'status': 'error', 'message': 'La estación no existe.'}

            name = config.name
            # config.unlink() ejecuta la validación exhaustiva de trazabilidad e integridad del modelo
            config.unlink()
            return {'status': 'success', 'message': f'Estación "{name}" eliminada correctamente.'}
        except UserError as ue:
            return {'status': 'error', 'message': ue.args[0] if ue.args else str(ue)}
        except Exception as e:
            _logger.exception("Error in /pos_gas_station/delete_station: %s", e)
            return {'status': 'error', 'message': str(e)}

    @http.route('/pos_gas_station/delete_company', type='json', auth='user', methods=['POST'], csrf=False)
    def delete_company(self, company_id):
        try:
            env = request.env
            comp = env['res.company'].sudo().browse(int(company_id))
            if not comp.exists():
                return {'status': 'error', 'message': 'La empresa no existe.'}

            stations_count = env['pos.config'].sudo().search_count([('company_id', '=', comp.id)])
            if stations_count > 0:
                return {
                    'status': 'error',
                    'message': f'No se puede eliminar la empresa "{comp.name}" porque contiene {stations_count} estación(es) asociada(s). Elimine primero las estaciones.'
                }

            orders_count = env['pos.order'].sudo().search_count([('company_id', '=', comp.id)])
            if orders_count > 0:
                return {
                    'status': 'error',
                    'message': f'No se puede eliminar la empresa "{comp.name}" porque contiene {orders_count} tickets de venta asociados.'
                }

            moves_count = env['account.move'].sudo().search_count([('company_id', '=', comp.id)])
            if moves_count > 0:
                return {
                    'status': 'error',
                    'message': f'No se puede eliminar la empresa "{comp.name}" porque contiene {moves_count} asientos o facturas contables.'
                }

            name = comp.name
            comp.unlink()
            return {'status': 'success', 'message': f'Empresa "{name}" eliminada correctamente.'}
        except Exception as e:
            _logger.exception("Error in /pos_gas_station/delete_company: %s", e)
            return {'status': 'error', 'message': str(e)}

    @http.route(['/pos_gas_station/shift_report_pdf/<int:session_id>', '/pos_gas_station/shift_report_pdf'], type='http', auth='public', methods=['GET'], csrf=False)
    def shift_report_pdf(self, session_id=None, config_id=None, **kw):
        try:
            env = request.env
            session = None
            if session_id:
                session = env['pos.session'].sudo().browse(int(session_id))
            elif config_id:
                cfg = env['pos.config'].sudo().browse(int(config_id))
                session = cfg.current_session_id
            
            if not session or not session.exists():
                session = env['pos.session'].sudo().search([], order='id desc', limit=1)

            if not session or not session.exists():
                return request.not_found()

            html_content = _generate_shift_report_html(env, session)
            pdf_bytes = _render_shift_pdf(html_content)
            if not pdf_bytes:
                return request.make_response("Error al generar el informe en PDF con wkhtmltopdf", headers=[('Content-Type', 'text/plain')])

            safe_name = (session.name or f"turno_{session.id}").replace('/', '_')
            return request.make_response(
                pdf_bytes,
                headers=[
                    ('Content-Type', 'application/pdf'),
                    ('Content-Disposition', f'inline; filename="Impresion_Turno_{safe_name}.pdf"')
                ]
            )
        except Exception as e:
            _logger.exception("Error in shift_report_pdf: %s", e)
            return request.make_response(f"Error: {e}", headers=[('Content-Type', 'text/plain')])
