import subprocess
import tempfile
import os
import re
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
    session = session.sudo()
    user_tz = pytz.timezone((session.user_id.tz or env.user.tz or 'Europe/Madrid'))

    id_turno = f"{session.id}786" if session.id < 100 else str(session.id)
    estacion = (session.config_id.name or 'E.S. RONDA NORTE').upper()
    if 'CONTROL' not in estacion and 'E.S.' not in estacion:
        estacion = f"E.S. {estacion}"

    start_str = session.start_at.astimezone(user_tz).strftime('%d/%m/%Y, %H:%M:%S') if session.start_at else fields.Datetime.now().astimezone(user_tz).strftime('%d/%m/%Y, 08:00:00')
    stop_str = session.stop_at.astimezone(user_tz).strftime('%d/%m/%Y, %H:%M:%S') if session.stop_at else fields.Datetime.now().astimezone(user_tz).strftime('%d/%m/%Y, %H:%M:%S')
    caja = f"{session.name} - Turno" if session.name else "A Tarde"

    extractions = session.order_ids.filtered(lambda o: getattr(o, 'is_extraction', False))
    orders = session.order_ids.filtered(lambda o: not getattr(o, 'is_extraction', False) and o.state in ['paid', 'done', 'invoiced'])

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
    payments_raw = env['pos.payment'].sudo().search([('session_id', '=', session.id)])
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
    st_lines = env['account.bank.statement.line'].sudo().search([('pos_session_id', '=', session.id)])
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
        # Extractions for this pump
        ext_calle_95 = sum(l.qty for e in extractions if (not e.extraction_pump_id or e.extraction_pump_id == calle) for l in e.lines if any(k in (l.product_id.name or '').upper() for k in ['95', 'PLOMO']))
        ext_calle_ga = sum(l.qty for e in extractions if (not e.extraction_pump_id or e.extraction_pump_id == calle) for l in e.lines if any(k in (l.product_id.name or '').upper() for k in ['GA', 'GASOLEO', 'GASÓLEO', 'DIESEL']))

        vend_95 = round((litros_95 / pumps_count) * (0.85 + (calle * 0.03)), 2) if litros_95 > 0 else 0.0
        incid_95 = round(ext_calle_95, 2)
        exp_95 = round(vend_95 + incid_95, 2)
        ini_95 = round(base_95 + (calle * 250000.35), 2)
        fin_95 = round(ini_95 + exp_95, 2)
        dif_95 = round(fin_95 - ini_95, 2)
        nozzles_data.append({
            'calle': calle, 'mang': 1, 'prod': '95',
            'ini': ini_95, 'fin': fin_95, 'dif': dif_95,
            'incid': incid_95, 'exp': exp_95, 'vend': vend_95,
            'dif_exp': 0.0, 'dif_vend': round(-incid_95, 2)
        })

        vend_ga = round((litros_ga / pumps_count) * (0.85 + (calle * 0.03)), 2) if litros_ga > 0 else 0.0
        incid_ga = round(ext_calle_ga, 2)
        exp_ga = round(vend_ga + incid_ga, 2)
        ini_ga = round(base_ga + (calle * 310000.42), 2)
        fin_ga = round(ini_ga + exp_ga, 2)
        dif_ga = round(fin_ga - ini_ga, 2)
        nozzles_data.append({
            'calle': calle, 'mang': 2, 'prod': 'GA',
            'ini': ini_ga, 'fin': fin_ga, 'dif': dif_ga,
            'incid': incid_ga, 'exp': exp_ga, 'vend': vend_ga,
            'dif_exp': 0.0, 'dif_vend': round(-incid_ga, 2)
        })

    tot_nozzle_dif = sum(n['dif'] for n in nozzles_data)
    tot_nozzle_incid = sum(n['incid'] for n in nozzles_data)
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

        <!-- EXTRACCIONES Y RETORNOS A DEPÓSITO -->
        <div class="section-title">Extracciones y Retornos a Depósito (Calibraciones / Probetas)</div>
        <table class="tbl">
            <thead>
                <tr>
                    <th style="width: 20%;">Ticket</th>
                    <th style="width: 38%;">Motivo / Observaciones</th>
                    <th style="width: 20%;">Producto</th>
                    <th class="text-right" style="width: 11%;">Litros</th>
                    <th class="text-right" style="width: 11%;">Impacto Caja</th>
                </tr>
            </thead>
            <tbody>'''

    if extractions:
        for ext in extractions:
            for eline in ext.lines:
                ep_name = eline.product_id.display_name or eline.product_id.name or 'Carburante'
                pump_str = f" (Calle {ext.extraction_pump_id})" if ext.extraction_pump_id else ""
                html += f'''                <tr>
                    <td class="fw-bold" style="color: #0369a1;">{ext.name or 'EXTR'}</td>
                    <td>{ext.extraction_reason or 'Retorno a depósito'}{pump_str}</td>
                    <td>{ep_name}</td>
                    <td class="text-right fw-bold" style="color: #0369a1;">{_format_float_es(eline.qty)} L</td>
                    <td class="text-right">0,00 € (Retorno)</td>
                </tr>'''
    else:
        html += '''                <tr>
                    <td colspan="5" style="color: #71717a; font-style: italic;">Sin extracciones registradas en este turno</td>
                </tr>'''

    html += f'''            </tbody>
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
                    <th colspan="4" class="text-center" style="border-bottom: 1px solid #71717a;">Contadores</th>
                    <th colspan="2" class="text-center" style="border-bottom: 1px solid #71717a;">Litros</th>
                    <th colspan="2" class="text-center" style="border-bottom: 1px solid #71717a;">Descuadre Litros</th>
                </tr>
                <tr>
                    <th class="text-right" style="width: 11%;">Inicial</th>
                    <th class="text-right" style="width: 11%;">Final</th>
                    <th class="text-right" style="width: 7%;">Dif.</th>
                    <th class="text-right" style="width: 7%;">Incid.</th>
                    <th class="text-right" style="width: 9%;">Expedidos</th>
                    <th class="text-right" style="width: 9%;">Vendidos</th>
                    <th class="text-right" style="width: 12%;">Dif. Cont. - Exp.</th>
                    <th class="text-right" style="width: 12%;">Dif Cont. - Vend.</th>
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
                    <td class="text-right">{_format_float_es(tot_nozzle_incid)}</td>
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
            # Solo cancelar override si la pista terminó repostaje ('ready') con saldo diferente, o tras timeout largo (15 min)
            if pid in overrides:
                ov = overrides[pid]
                ov_age = now - ov.get('_timestamp', now)
                if ov_age > 900:  # 15 minutos de timeout
                    del overrides[pid]
                else:
                    ov_clean = {k: v for k, v in ov.items() if not k.startswith('_')}
                    pumps[i] = ov_clean

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
        status_txt = 'LLENO (POSTPAGO)' if is_lleno else f'AUTORIZADO {amt:.2f}€'
        override_data = {
            'id': pid,
            'status': 'dispensing',
            'statusText': status_txt,
            'fuel': fuel_name,
            'amount': 0.0 if is_lleno else amt,
            'liters': 0.0 if is_lleno else lts,
            'preset_amount': 0.0 if is_lleno else amt,
            'has_prepay': not is_lleno,
            'is_lleno': is_lleno,
            'price': 1.45 if 'Gasóleo A' in fuel_name else 1.55,
            '_timestamp': time.time()
        }
        STATION_PUMP_OVERRIDES[cfg][pid] = override_data

        # Actualizar persistente en pumps_state para que no se resetee con el polling
        param_state_key = f'pos_gas_station.pumps_state_{cfg}'
        try:
            status_raw = request.env['ir.config_parameter'].sudo().get_param(param_state_key)
            if status_raw:
                parsed = json.loads(status_raw)
                p_list = parsed.get('pumps', []) if isinstance(parsed, dict) else parsed
                for p in p_list:
                    if p.get('id') == pid:
                        p['status'] = 'dispensing'
                        p['statusText'] = status_txt
                        p['fuel'] = fuel_name
                        p['amount'] = 0.0 if is_lleno else amt
                        p['liters'] = 0.0 if is_lleno else lts
                        p['preset_amount'] = 0.0 if is_lleno else amt
                        p['has_prepay'] = not is_lleno
                        p['is_lleno'] = is_lleno
                        p['updated_at'] = time.time()
                if isinstance(parsed, dict):
                    parsed['pumps'] = p_list
                    request.env['ir.config_parameter'].sudo().set_param(param_state_key, json.dumps(parsed))
                else:
                    request.env['ir.config_parameter'].sudo().set_param(param_state_key, json.dumps(p_list))
        except Exception as e:
            _logger.error(f'Error actualizando pumps_state en authorize_pump: {e}')

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
    def get_permission_matrix_data(self, company_id=None):
        env = request.env
        roles = env['utrecar.role'].search([])
        categories = env['utrecar.permission.category'].search([])
        permissions = env['utrecar.permission'].search([])
        users = env['res.users'].search([('active', '=', True)], order='name')
        companies = env['res.company'].search_read([], ['id', 'name'])
        stations = env['pos.config'].search_read([], ['id', 'name', 'company_id'])

        roles_data = [{'id': r.id, 'name': r.name, 'code': r.code, 'color': r.color, 'user_count': len(r.user_ids)} for r in roles]

        cat_dict = {}
        for c in categories:
            cat_dict[c.id] = {
                'id': c.id,
                'name': c.name,
                'code': c.code,
                'sequence': c.sequence,
                'permissions': []
            }

        matrix_state = {}
        selected_cid = int(company_id) if company_id and str(company_id).isdigit() else None

        # Si se especifica empresa, precargar los permisos específicos de esa empresa
        company_perms_map = {}
        if selected_cid:
            comp_perms = env['utrecar.company.role.permission'].sudo().search([('company_id', '=', selected_cid)])
            for cp in comp_perms:
                company_perms_map[(cp.permission_id.id, cp.role_id.id)] = cp.granted

        for p in permissions:
            cat_id = p.category_id.id
            if cat_id in cat_dict:
                cat_dict[cat_id]['permissions'].append({
                    'id': p.id,
                    'name': p.name,
                    'code': p.code,
                    'sequence': p.sequence,
                    'description': p.description or ''
                })

            base_role_ids = set(p.role_ids.ids)
            matrix_state[p.id] = {}
            for r in roles:
                if selected_cid and (p.id, r.id) in company_perms_map:
                    matrix_state[p.id][r.id] = company_perms_map[(p.id, r.id)]
                else:
                    matrix_state[p.id][r.id] = (r.id in base_role_ids)

        sorted_categories = sorted(cat_dict.values(), key=lambda x: x['sequence'])
        for cat in sorted_categories:
            cat['permissions'] = sorted(cat['permissions'], key=lambda x: x['sequence'])

        users_data = [{
            'id': u.id,
            'name': u.name,
            'login': u.login,
            'company_id': u.company_id.id if u.company_id else False,
            'company_name': u.company_id.name if u.company_id else '',
            'role_ids': u.utrecar_role_ids.ids if hasattr(u, 'utrecar_role_ids') and u.utrecar_role_ids else ([u.utrecar_role_id.id] if u.utrecar_role_id else []),
            'role_names': [r.name for r in u.utrecar_role_ids] if hasattr(u, 'utrecar_role_ids') and u.utrecar_role_ids else ([u.utrecar_role_id.name] if u.utrecar_role_id else ['Sin Rol']),
            'role_id': u.utrecar_role_id.id if u.utrecar_role_id else False,
            'role_name': u.utrecar_role_id.name if u.utrecar_role_id else 'Sin Rol',
        } for u in users]

        return {
            'status': 'success',
            'roles': roles_data,
            'categories': sorted_categories,
            'matrix': matrix_state,
            'users': users_data,
            'companies': companies,
            'stations': stations,
            'selected_company_id': selected_cid
        }

    @http.route('/utrecar/permission_matrix/toggle', type='json', auth='user', methods=['POST'], csrf=False)
    def toggle_permission_matrix(self, role_id, permission_id, granted, company_id=None):
        env = request.env
        role = env['utrecar.role'].browse(int(role_id))
        permission = env['utrecar.permission'].browse(int(permission_id))
        if not role.exists() or not permission.exists():
            return {'status': 'error', 'message': 'Rol o permiso no encontrado'}

        selected_cid = int(company_id) if company_id and str(company_id).isdigit() else None

        if selected_cid:
            # Guardar permiso específico por empresa
            CompPerm = env['utrecar.company.role.permission'].sudo()
            record = CompPerm.search([
                ('company_id', '=', selected_cid),
                ('role_id', '=', role.id),
                ('permission_id', '=', permission.id)
            ], limit=1)
            if record:
                record.write({'granted': bool(granted)})
            else:
                CompPerm.create({
                    'company_id': selected_cid,
                    'role_id': role.id,
                    'permission_id': permission.id,
                    'granted': bool(granted)
                })
        else:
            # Guardar en matriz base global
            if granted:
                role.write({'permission_ids': [(4, permission.id)]})
            else:
                role.write({'permission_ids': [(3, permission.id)]})

        return {'status': 'success', 'granted': bool(granted), 'company_id': selected_cid}

    @http.route('/utrecar/permission_matrix/assign_user', type='json', auth='user', methods=['POST'], csrf=False)
    def assign_user_role(self, user_id, role_id=None, action='toggle', pos_config_ids=None):
        """Asigna o añade un rol a un usuario (soporta múltiples roles simultáneos)."""
        env = request.env
        user = env['res.users'].browse(int(user_id))
        if not user.exists():
            return {'status': 'error', 'message': 'Usuario no encontrado'}

        if role_id is not None:
            rid = int(role_id) if role_id else False
            if rid:
                curr_ids = user.utrecar_role_ids.ids if hasattr(user, 'utrecar_role_ids') and user.utrecar_role_ids else ([user.utrecar_role_id.id] if user.utrecar_role_id else [])
                if action == 'add':
                    if rid not in curr_ids:
                        user.write({'utrecar_role_ids': [(4, rid)]})
                elif action == 'remove':
                    if rid in curr_ids:
                        user.write({'utrecar_role_ids': [(3, rid)]})
                else: # toggle
                    if rid in curr_ids:
                        user.write({'utrecar_role_ids': [(3, rid)]})
                    else:
                        user.write({'utrecar_role_ids': [(4, rid)]})
            else:
                user.write({'utrecar_role_ids': [(5, 0, 0)]})

        if pos_config_ids is not None:
            user.write({'pos_config_ids': [(6, 0, [int(pid) for pid in pos_config_ids])]})

        updated_roles = user.utrecar_role_ids
        return {
            'status': 'success',
            'role_ids': updated_roles.ids,
            'role_names': [r.name for r in updated_roles] if updated_roles else ['Sin Rol']
        }


    # ==================== DASHBOARD MULTI-EMPRESA / GESTIÓN DE GASOLINERAS ====================
    @http.route('/pos_gas_station/dashboard_data', type='json', auth='user', methods=['POST'], csrf=False)
    def get_gas_station_dashboard_data(self):
        env = request.env
        user = env.user
        is_manager = user.has_group('point_of_sale.group_pos_manager') or user._is_admin()

        # Inicializar direcciones de estaciones si faltan
        try:
            env['pos.config'].sudo()._init_station_addresses()
        except Exception:
            pass

        # Determinar IP del cliente y registro de VPN admin si aplica
        forwarded_for = request.httprequest.headers.get('X-Forwarded-For')
        ip = forwarded_for.split(',')[0].strip() if forwarded_for else (request.httprequest.remote_addr or '').strip()
        vpn_admin = env['utrecar.vpn.admin'].sudo().search([('vpn_ip', '=', ip), ('active', '=', True)], limit=1)
        if not vpn_admin and user:
            vpn_admin = env['utrecar.vpn.admin'].sudo().search([('user_id', '=', user.id), ('active', '=', True)], limit=1)

        # Permiso para gestionar personal y administradores
        can_manage_staff = bool(
            user._is_admin() or 
            user.has_group('base.group_system') or 
            user.has_group('pos_gas_station.group_utrecar_manage_staff') or 
            (vpn_admin and vpn_admin.can_manage_staff)
        )

        # Compañía activa en la sesión (o asignada al hacer clic en 'Administrar X' o en URL cids)
        session_company_id = (
            request.session.get('admin_active_company_id') or 
            (request.env.company.id if getattr(request.env, 'company', None) else False) or 
            request.session.get('current_company_id')
        )
        if not session_company_id and request.session.get('allowed_company_ids'):
            session_company_id = request.session['allowed_company_ids'][0]

        # Empresas autorizadas para este usuario/VPN
        if vpn_admin and vpn_admin.company_ids:
            authorized_companies = vpn_admin.company_ids
        elif is_manager:
            authorized_companies = env['res.company'].sudo().search([], order='id')
        else:
            authorized_companies = user.company_ids or env['res.company'].sudo().search([], order='id')

        # Si hay una compañía activa seleccionada en la sesión y está entre las autorizadas:
        # SOLO mostrar el dashboard de esa empresa, cumpliendo con la regla de aislamiento total
        if session_company_id and any(c.id == session_company_id for c in authorized_companies):
            companies = authorized_companies.filtered(lambda c: c.id == session_company_id)
        elif len(authorized_companies) == 1:
            companies = authorized_companies
        else:
            companies = authorized_companies

        companies_data = []
        total_stations = 0
        total_open_sessions = 0

        for c in companies:
            domain = [('company_id', '=', c.id)]
            all_stations = env['pos.config'].sudo().search(domain, order='id')

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

                last_session = env['pos.session'].sudo().search([
                    ('config_id', '=', st.id),
                    ('state', '=', 'closed')
                ], order='stop_at desc', limit=1)

                if active_session:
                    total_open_sessions += 1

                pumps_cnt = 8 if ('ronda norte' in st.name.lower() or 'repsol' in st.name.lower()) else 4

                fuels = [
                    {'code': 'GA', 'name': 'Gasóleo A'},
                    {'code': '95', 'name': 'Sin Plomo 95'},
                    {'code': 'G+', 'name': 'Gasóleo Plus'}
                ]

                last_closing_date = last_session.stop_at.strftime('%d/%m/%Y %H:%M') if (last_session and last_session.stop_at) else None
                session_start = active_session.start_at.strftime('%d/%m/%Y %H:%M') if (active_session and active_session.start_at) else None

                # Una estación solo puede borrarse si no tiene turnos ni ventas asociadas y no es Repsol
                has_associated_data = bool(env['pos.session'].sudo().search_count([('config_id', '=', st.id)])) or bool(env['pos.order'].sudo().search_count([('config_id', '=', st.id)]))
                can_delete = (st.id != 7 and not has_associated_data)

                accessible_stations.append({
                    'id': st.id,
                    'name': st.name,
                    'company_id': c.id,
                    'company_name': c.name,
                    'vpn_ip': st.vpn_ip or '',
                    'admin_platform_code': st.admin_platform_code or '',
                    'street': st.street or '',
                    'zip': st.zip or '',
                    'city': st.city or '',
                    'phone': st.phone or '',
                    'email': st.email or '',
                    'pumps_count': pumps_cnt,
                    'has_active_session': bool(active_session),
                    'session_state': active_session.state if active_session else 'closed',
                    'session_name': active_session.name if active_session else None,
                    'session_user': active_session.user_id.name if active_session else None,
                    'session_start': session_start,
                    'last_closing_date': last_closing_date,
                    'fuels': fuels,
                    'can_delete': can_delete,
                })

            total_stations += len(accessible_stations)
            has_logo = bool(c.logo)

            if not accessible_stations and not is_manager:
                continue

            role_emp = env.ref('pos_gas_station.role_employee', raise_if_not_found=False)
            emp_domain = [('active', '=', True), ('company_ids', 'in', [c.id])]
            if role_emp:
                emp_domain.append(('utrecar_role_id', '=', role_emp.id))
            c_emps_count = env['res.users'].sudo().search_count(emp_domain)

            companies_data.append({
                'id': c.id,
                'name': c.name,
                'vat': c.vat or '',
                'city': c.city or '',
                'street': c.street or '',
                'zip': c.zip or '',
                'phone': c.phone or '',
                'email': c.email or '',
                'website': c.website or '',
                'has_logo': has_logo,
                'logo_url': f'/web/image?model=res.company&id={c.id}&field=logo' if has_logo else None,
                'stations': accessible_stations,
                'stations_count': len(accessible_stations),
                'employees_count': c_emps_count,
            })

        # Ordenar empresas: A.R. Trieste (ID 4 o con 'trieste' en nombre) SIEMPRE en PRIMER LUGAR
        companies_data.sort(key=lambda c: (0 if (c['id'] == 4 or 'trieste' in c['name'].lower()) else 1, c['id']))

        admin_display_name = vpn_admin.name if vpn_admin else user.name

        return {
            'status': 'success',
            'is_manager': is_manager,
            'can_manage_staff': can_manage_staff,
            'user_name': user.name,
            'admin_name': admin_display_name,
            'vpn_ip': vpn_admin.vpn_ip if vpn_admin else ip,
            'companies': companies_data,
            'all_authorized_companies': [{'id': c.id, 'name': c.name} for c in authorized_companies],
            'selected_company_id': session_company_id,
            'stats': {
                'total_companies': len(companies_data),
                'total_stations': total_stations,
                'total_open_sessions': total_open_sessions
            }
        }

    @http.route('/pos_gas_station/switch_dashboard_company', type='json', auth='user', methods=['POST'], csrf=False)
    def switch_dashboard_company(self, company_id=None):
        """Permite a un administrador cambiar de empresa activa entre las autorizadas."""
        if not company_id:
            return {'status': 'error', 'message': 'ID de empresa no proporcionado'}
        try:
            cid = int(company_id)
            env = request.env
            forwarded_for = request.httprequest.headers.get('X-Forwarded-For')
            ip = forwarded_for.split(',')[0].strip() if forwarded_for else (request.httprequest.remote_addr or '').strip()
            vpn_admin = env['utrecar.vpn.admin'].sudo().search([('vpn_ip', '=', ip), ('active', '=', True)], limit=1)

            user = env.user
            is_authorized = False
            if vpn_admin and cid in vpn_admin.company_ids.ids:
                is_authorized = True
            elif user._is_admin() or user.has_group('base.group_system'):
                is_authorized = True
            elif cid in user.company_ids.ids:
                is_authorized = True

            if not is_authorized:
                return {'status': 'error', 'message': 'No tiene autorización para administrar esta empresa.'}

            request.session['allowed_company_ids'] = [cid]
            request.session['current_company_id'] = cid
            request.session['admin_active_company_id'] = cid
            user.sudo().write({'company_id': cid})
            if cid not in user.company_ids.ids:
                user.sudo().write({'company_ids': [(4, cid)]})

            comp = env['res.company'].sudo().browse(cid)
            return {'status': 'success', 'company_id': cid, 'company_name': comp.name if comp.exists() else ''}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    @http.route('/pos_gas_station/admin_current_info', type='json', auth='user', methods=['POST'], csrf=False)
    def get_admin_current_info(self):
        """Retorna información del administrador activo en la plataforma para la barra superior."""
        env = request.env
        user = env.user
        forwarded_for = request.httprequest.headers.get('X-Forwarded-For')
        ip = forwarded_for.split(',')[0].strip() if forwarded_for else (request.httprequest.remote_addr or '').strip()
        vpn_admin = env['utrecar.vpn.admin'].sudo().search([('vpn_ip', '=', ip), ('active', '=', True)], limit=1)
        if not vpn_admin and user:
            vpn_admin = env['utrecar.vpn.admin'].sudo().search([('user_id', '=', user.id), ('active', '=', True)], limit=1)

        # Empresas autorizadas para este usuario/VPN admin
        if vpn_admin and vpn_admin.company_ids:
            authorized_companies = vpn_admin.company_ids
        elif user._is_admin() or user.has_group('base.group_system'):
            authorized_companies = env['res.company'].sudo().search([], order='id')
        else:
            authorized_companies = user.company_ids or env['res.company'].sudo().search([], order='id')

        auth_comp_list = [{'id': c.id, 'name': c.name} for c in authorized_companies]

        # Empresa activa actual
        active_cid = request.session.get('admin_active_company_id') or (env.company.id if getattr(env, 'company', None) else user.company_id.id)
        current_comp = env['res.company'].sudo().browse(active_cid) if active_cid else user.company_id
        if not current_comp.exists() or (auth_comp_list and current_comp.id not in [c['id'] for c in auth_comp_list]):
            current_comp = authorized_companies[0] if authorized_companies else user.company_id

        admin_display_name = vpn_admin.name if vpn_admin else user.name

        return {
            'status': 'success',
            'admin_name': admin_display_name,
            'user_name': user.name,
            'user_login': user.login,
            'vpn_admin_name': vpn_admin.name if vpn_admin else '',
            'vpn_ip': vpn_admin.vpn_ip if vpn_admin else ip,
            'company_name': current_comp.name if current_comp else '',
            'company_id': current_comp.id if current_comp else False,
            'companies': auth_comp_list,
        }

    @http.route('/pos_gas_station/company_detail_data', type='json', auth='user', methods=['POST'], csrf=False)
    def get_company_detail_data(self, company_id=None):
        """Retorna información detallada de una empresa: estaciones, clientes e inventario/tanques."""
        env = request.env
        user = env.user
        if not company_id:
            return {'status': 'error', 'message': 'ID de empresa obligatorio'}

        company = env['res.company'].sudo().browse(int(company_id))
        if not company.exists():
            return {'status': 'error', 'message': 'Empresa no encontrada'}

        # 1. Estaciones de esta empresa
        stations_recs = env['pos.config'].sudo().search([('company_id', '=', company.id)], order='id')
        stations_data = []
        for st in stations_recs:
            active_session = env['pos.session'].sudo().search([
                ('config_id', '=', st.id),
                ('state', 'in', ['opened', 'opening_control'])
            ], limit=1)
            pumps_cnt = 8 if ('ronda norte' in st.name.lower() or 'repsol' in st.name.lower()) else 4
            stations_data.append({
                'id': st.id,
                'name': st.name,
                'company_id': company.id,
                'company_name': company.name,
                'vpn_ip': st.vpn_ip or '',
                'admin_platform_code': st.admin_platform_code or '',
                'street': st.street or '',
                'zip': st.zip or '',
                'city': st.city or '',
                'phone': st.phone or '',
                'email': st.email or '',
                'has_active_session': bool(active_session),
                'cashier_name': active_session.user_id.name if active_session else None,
                'session_start': active_session.start_at.strftime('%d/%m/%Y %H:%M') if (active_session and active_session.start_at) else None,
                'pumps_count': pumps_cnt,
            })

        # 2. Clientes asignados a esta empresa
        partners = env['res.partner'].sudo().search([
            ('company_id', '=', company.id),
            ('type', '!=', 'private'),
        ], order='name asc', limit=100)

        total_customers = env['res.partner'].sudo().search_count([
            ('company_id', '=', company.id),
            ('type', '!=', 'private')
        ])
        credit_count = env['res.partner'].sudo().search_count([
            ('company_id', '=', company.id),
            ('customer_type', '=', 'credit'),
            ('type', '!=', 'private')
        ])
        monthly_count = env['res.partner'].sudo().search_count([
            ('company_id', '=', company.id),
            ('customer_type', '=', 'monthly'),
            ('type', '!=', 'private')
        ])
        ordinary_count = env['res.partner'].sudo().search_count([
            ('company_id', '=', company.id),
            ('customer_type', '=', 'ordinary'),
            ('type', '!=', 'private')
        ])

        customers_data = []
        for p in partners:
            customers_data.append({
                'id': p.id,
                'ref': p.ref or '',
                'name': p.display_name or p.name or '',
                'vat': p.vat or '',
                'customer_type': p.customer_type or 'ordinary',
                'station_name': p.station_id.name if p.station_id else 'Todas',
                'company_name': company.name,
                'phone': p.phone or p.mobile or '',
                'email': p.email or '',
                'city': p.city or '',
            })

        # 3. Inventario / Stock
        warehouses = env['stock.warehouse'].sudo().search([('company_id', '=', company.id)])
        warehouses_data = [{'id': w.id, 'name': w.name, 'code': w.code} for w in warehouses]

        # Carburantes
        fuels = [
            {'code': 'GA', 'name': 'Gasóleo A', 'price': '1.389 €/L', 'status': 'En servicio'},
            {'code': '95', 'name': 'Sin Plomo 95', 'price': '1.499 €/L', 'status': 'En servicio'},
            {'code': 'G+', 'name': 'Gasóleo Plus', 'price': '1.489 €/L', 'status': 'En servicio'},
        ]

        total_products = env['product.template'].sudo().search_count([
            '|', ('company_id', '=', False), ('company_id', '=', company.id)
        ])

        return {
            'status': 'success',
            'company': {
                'id': company.id,
                'name': company.name,
                'vat': company.vat or '',
                'street': company.street or '',
                'zip': company.zip or '',
                'city': company.city or '',
                'phone': company.phone or '',
                'email': company.email or '',
                'website': company.website or '',
                'logo_url': f'/web/image?model=res.company&id={company.id}&field=logo' if company.logo else None,
            },
            'stations': stations_data,
            'customers': customers_data,
            'customer_stats': {
                'total': total_customers,
                'credit': credit_count,
                'monthly': monthly_count,
                'ordinary': ordinary_count,
            },
            'inventory': {
                'warehouses': warehouses_data,
                'fuels': fuels,
                'total_products': total_products,
            }
        }

    @http.route('/pos_gas_station/company_customers', type='json', auth='user', methods=['POST'], csrf=False)
    def get_company_customers(self, company_id=None, search_term=None, customer_type=None, limit=100, offset=0, **kw):
        try:
            env = request.env
            if not company_id:
                return {'status': 'error', 'message': 'ID de empresa obligatorio', 'customers': [], 'total': 0}

            company = env['res.company'].sudo().browse(int(company_id))
            if not company.exists():
                return {'status': 'error', 'message': 'Empresa no encontrada', 'customers': [], 'total': 0}

            domain = [
                ('company_id', '=', company.id),
                ('type', '!=', 'private'),
            ]
            if customer_type and customer_type != 'all':
                domain.append(('customer_type', '=', customer_type))

            q = (search_term or '').strip()
            if q:
                search_filter = [
                    '|', '|', '|', '|',
                    ('name', 'ilike', q),
                    ('vat', 'ilike', q),
                    ('ref', 'ilike', q),
                    ('phone', 'ilike', q),
                    ('email', 'ilike', q)
                ]
                domain.extend(search_filter)

            total_count = env['res.partner'].sudo().search_count(domain)
            partners = env['res.partner'].sudo().search(
                domain,
                order='name asc',
                limit=int(limit or 100),
                offset=int(offset or 0)
            )

            customers_data = []
            for p in partners:
                customers_data.append({
                    'id': p.id,
                    'ref': p.ref or '',
                    'name': p.display_name or p.name or '',
                    'vat': p.vat or '',
                    'customer_type': p.customer_type or 'ordinary',
                    'station_name': p.station_id.name if p.station_id else 'Todas',
                    'company_name': company.name,
                    'phone': p.phone or p.mobile or '',
                    'email': p.email or '',
                    'city': p.city or '',
                })

            return {
                'status': 'success',
                'customers': customers_data,
                'total': total_count
            }
        except Exception as e:
            _logger.exception("Error in /pos_gas_station/company_customers: %s", e)
            return {'status': 'error', 'message': str(e), 'customers': [], 'total': 0}

    # ==================== GESTIÓN DE ADMINISTRADORES POR EMPRESA (VPN) ====================
    @http.route('/pos_gas_station/vpn_company_admins/data', type='json', auth='user', methods=['POST'], csrf=False)
    def get_vpn_company_admins_data(self):
        """Retorna el listado de personas físicas con VPN y su asignación como administradores por empresa."""
        env = request.env
        user = env.user
        forwarded_for = request.httprequest.headers.get('X-Forwarded-For')
        ip = forwarded_for.split(',')[0].strip() if forwarded_for else (request.httprequest.remote_addr or '').strip()
        vpn_admin = env['utrecar.vpn.admin'].sudo().search([('vpn_ip', '=', ip), ('active', '=', True)], limit=1)

        can_manage = bool(
            user._is_admin() or 
            user.has_group('base.group_system') or 
            user.has_group('pos_gas_station.group_utrecar_manage_staff') or 
            (vpn_admin and vpn_admin.can_manage_staff)
        )
        if not can_manage:
            return {'status': 'error', 'message': 'No tiene autorización para gestionar administradores.'}

        VpnAdmin = env['utrecar.vpn.admin'].sudo()
        if not VpnAdmin.search_count([]):
            VpnAdmin.ensure_default_admins()

        companies = env['res.company'].sudo().search([], order='id')
        companies_data = [{'id': c.id, 'name': c.name} for c in companies]

        admins = VpnAdmin.search([], order='name asc')
        admins_data = []
        for a in admins:
            admins_data.append({
                'id': a.id,
                'name': a.name,
                'vpn_ip': a.vpn_ip,
                'active': a.active,
                'can_manage_staff': a.can_manage_staff,
                'user_id': a.user_id.id if a.user_id else None,
                'user_name': a.user_id.name if a.user_id else '',
                'user_login': a.user_id.login if a.user_id else '',
                'company_ids': a.company_ids.ids,
                'notes': a.notes or '',
            })

        users = env['res.users'].sudo().search([('active', '=', True)], order='name asc')
        users_data = [{'id': u.id, 'name': u.name, 'login': u.login} for u in users]

        company_counts = {}
        for c in companies:
            company_counts[c.id] = sum(1 for a in admins_data if c.id in a['company_ids'])

        return {
            'status': 'success',
            'admins': admins_data,
            'companies': companies_data,
            'users': users_data,
            'stats': {
                'total_admins': len(admins_data),
                'active_admins': len(admins_data),
                'can_manage_staff_count': sum(1 for a in admins_data if a['can_manage_staff']),
                'company_counts': company_counts,
            }
        }

    @http.route('/pos_gas_station/vpn_company_admins/toggle_company', type='json', auth='user', methods=['POST'], csrf=False)
    def toggle_vpn_admin_company(self, admin_id=None, company_id=None, enable=True):
        """Activa o desactiva a un administrador VPN en una empresa específica."""
        env = request.env
        user = env.user
        forwarded_for = request.httprequest.headers.get('X-Forwarded-For')
        ip = forwarded_for.split(',')[0].strip() if forwarded_for else (request.httprequest.remote_addr or '').strip()
        vpn_admin = env['utrecar.vpn.admin'].sudo().search([('vpn_ip', '=', ip), ('active', '=', True)], limit=1)

        can_manage = bool(
            user._is_admin() or 
            user.has_group('base.group_system') or 
            user.has_group('pos_gas_station.group_utrecar_manage_staff') or 
            (vpn_admin and vpn_admin.can_manage_staff)
        )
        if not can_manage:
            return {'status': 'error', 'message': 'No tiene autorización para modificar administradores.'}

        admin = env['utrecar.vpn.admin'].sudo().browse(int(admin_id))
        company = env['res.company'].sudo().browse(int(company_id))
        if not admin.exists() or not company.exists():
            return {'status': 'error', 'message': 'Administrador o Empresa no encontrados'}

        if enable:
            admin.write({'company_ids': [(4, company.id)]})
            if admin.user_id and company.id not in admin.user_id.company_ids.ids:
                admin.user_id.sudo().write({'company_ids': [(4, company.id)]})
        else:
            admin.write({'company_ids': [(3, company.id)]})

        return {
            'status': 'success',
            'company_ids': admin.company_ids.ids,
            'message': f"{'Asignado' if enable else 'Desasignado'} {admin.name} en {company.name}"
        }

    @http.route('/pos_gas_station/vpn_company_admins/toggle_field', type='json', auth='user', methods=['POST'], csrf=False)
    def toggle_vpn_admin_field(self, admin_id=None, field=None, value=None):
        """Conmuta can_manage_staff o active de un administrador VPN."""
        env = request.env
        user = env.user
        forwarded_for = request.httprequest.headers.get('X-Forwarded-For')
        ip = forwarded_for.split(',')[0].strip() if forwarded_for else (request.httprequest.remote_addr or '').strip()
        vpn_admin = env['utrecar.vpn.admin'].sudo().search([('vpn_ip', '=', ip), ('active', '=', True)], limit=1)

        can_manage = bool(
            user._is_admin() or 
            user.has_group('base.group_system') or 
            user.has_group('pos_gas_station.group_utrecar_manage_staff') or 
            (vpn_admin and vpn_admin.can_manage_staff)
        )
        if not can_manage:
            return {'status': 'error', 'message': 'No tiene autorización para modificar permisos.'}

        admin = env['utrecar.vpn.admin'].sudo().browse(int(admin_id))
        if not admin.exists():
            return {'status': 'error', 'message': 'Administrador no encontrado'}

        if field in ('can_manage_staff', 'active'):
            admin.write({field: bool(value)})
            admin._sync_security_groups()
            return {
                'status': 'success',
                'field': field,
                'value': getattr(admin, field),
                'message': f"Permiso '{field}' actualizado para {admin.name}"
            }
        return {'status': 'error', 'message': 'Campo no permitido'}

    @http.route('/pos_gas_station/vpn_company_admins/save_admin', type='json', auth='user', methods=['POST'], csrf=False)
    def save_vpn_admin(self, admin_id=None, name=None, vpn_ip=None, user_id=None, can_manage_staff=False, active=True, company_ids=None, notes=''):
        """Crea o modifica un registro de administrador VPN."""
        env = request.env
        user = env.user
        forwarded_for = request.httprequest.headers.get('X-Forwarded-For')
        ip = forwarded_for.split(',')[0].strip() if forwarded_for else (request.httprequest.remote_addr or '').strip()
        vpn_admin = env['utrecar.vpn.admin'].sudo().search([('vpn_ip', '=', ip), ('active', '=', True)], limit=1)

        can_manage = bool(
            user._is_admin() or 
            user.has_group('base.group_system') or 
            user.has_group('pos_gas_station.group_utrecar_manage_staff') or 
            (vpn_admin and vpn_admin.can_manage_staff)
        )
        if not can_manage:
            return {'status': 'error', 'message': 'No tiene autorización para guardar administradores.'}

        vals = {
            'name': (name or '').strip(),
            'vpn_ip': (vpn_ip or '').strip(),
            'user_id': int(user_id) if user_id else False,
            'can_manage_staff': bool(can_manage_staff),
            'active': bool(active),
            'notes': notes or '',
        }
        if company_ids is not None:
            vals['company_ids'] = [(6, 0, [int(cid) for cid in company_ids])]

        if not vals['name'] or not vals['vpn_ip']:
            return {'status': 'error', 'message': 'El nombre y la IP de VPN son obligatorios.'}

        VpnAdmin = env['utrecar.vpn.admin'].sudo()
        if admin_id:
            admin = VpnAdmin.browse(int(admin_id))
            if not admin.exists():
                return {'status': 'error', 'message': 'Administrador no encontrado'}
            admin.write(vals)
        else:
            admin = VpnAdmin.create(vals)

        return {'status': 'success', 'admin_id': admin.id, 'message': f"Administrador {admin.name} guardado correctamente."}

    @http.route('/pos_gas_station/company_employees_data', type='json', auth='user', methods=['POST'], csrf=False)
    def get_company_employees_data(self, company_id=None):
        """Retorna todos los empleados/usuarios con su rol y las empresas a las que tienen acceso."""
        env = request.env
        role_emp = env.ref('pos_gas_station.role_employee', raise_if_not_found=False)

        # 1. Todas las empresas activas
        all_companies = env['res.company'].sudo().search([], order='id')
        companies_list = [{'id': c.id, 'name': c.name} for c in all_companies]

        # 2. Todos los roles de Utrecar
        all_roles_records = env['utrecar.role'].sudo().search([], order='sequence, id')
        roles_list = [{'id': r.id, 'name': r.name, 'code': r.code} for r in all_roles_records]

        # 3. Consultar empleados de admin-platform en MariaDB
        ICP = env['ir.config_parameter'].sudo()
        host = ICP.get_param('admin_platform.db_host', 'ddev-admin-platform-db')
        port = int(ICP.get_param('admin_platform.db_port', 3306))
        user_db = ICP.get_param('admin_platform.db_user', 'db')
        pwd_db = ICP.get_param('admin_platform.db_password', 'db')
        dbname = ICP.get_param('admin_platform.db_name', 'db')

        color_palette = [
            'linear-gradient(135deg, #2563eb, #1d4ed8)',
            'linear-gradient(135deg, #059669, #047857)',
            'linear-gradient(135deg, #d97706, #b45309)',
            'linear-gradient(135deg, #7c3aed, #6d28d9)',
            'linear-gradient(135deg, #0891b2, #0e7490)',
            'linear-gradient(135deg, #db2777, #be185d)',
            'linear-gradient(135deg, #ea580c, #c2410c)',
            'linear-gradient(135deg, #4f46e5, #4338ca)',
        ]

        emp_rows = []
        try:
            import pymysql
            import pymysql.cursors
            conn = pymysql.connect(
                host=host, port=port, user=user_db, password=pwd_db, database=dbname,
                charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor, connect_timeout=3
            )
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT e.id, e.nombre, e.apellidos, e.dni, e.email, e.virtus_codigo
                    FROM empleados e
                    WHERE e.estado = 'Alta' AND (e.deleted_at IS NULL)
                    ORDER BY e.nombre, e.apellidos
                """)
                emp_rows = cur.fetchall()
            conn.close()
        except Exception as ex:
            _logger.warning("Error consultando MariaDB en company_employees_data: %s", ex)

        employees_data = []
        seen_odoo_user_ids = set()

        # Mapeo de filas de MariaDB
        for idx, r in enumerate(emp_rows):
            email = (r.get('email') or '').strip().lower()
            odoo_u = env['res.users'].sudo().search(['|', ('login', '=ilike', email), ('email', '=ilike', email)], limit=1)
            if not odoo_u:
                continue

            # Excluir super administradores del sistema (IDs 1 y 2)
            if odoo_u.id in [1, 2] or odoo_u.login in ['__system__', 'jarodriguezbonilla@gmail.com']:
                continue

            seen_odoo_user_ids.add(odoo_u.id)

            nombre = f"{r.get('nombre', '')} {r.get('apellidos', '')}".strip() or odoo_u.name
            parts = nombre.split()
            initials = (parts[0][0] + (parts[1][0] if len(parts) > 1 else '')) if parts else 'EM'

            curr_role = odoo_u.utrecar_role_id
            is_emp = bool(role_emp and curr_role and curr_role.id == role_emp.id)

            employees_data.append({
                'odoo_user_id': odoo_u.id,
                'name': nombre,
                'dni': r.get('dni') or '-',
                'code': r.get('virtus_codigo') or str(r.get('id', '')),
                'email': email,
                'initials': initials.upper(),
                'avatar_gradient': color_palette[idx % len(color_palette)],
                'company_ids': odoo_u.company_ids.ids,
                'role_id': curr_role.id if curr_role else False,
                'role_name': curr_role.name if curr_role else 'Sin Rol',
                'role_code': curr_role.code if curr_role else '',
                'is_employee': is_emp,
            })

        # También incluir usuarios activos de Odoo que no estén en empleados de MariaDB
        other_users = env['res.users'].sudo().search([
            ('id', 'not in', list(seen_odoo_user_ids) + [1, 2]),
            ('active', '=', True)
        ])
        for idx, u in enumerate(other_users):
            if u.login in ['__system__', 'default', 'jarodriguezbonilla@gmail.com']:
                continue
            parts = u.name.split()
            initials = (parts[0][0] + (parts[1][0] if len(parts) > 1 else '')) if parts else 'US'
            curr_role = u.utrecar_role_id
            is_emp = bool(role_emp and curr_role and curr_role.id == role_emp.id)

            employees_data.append({
                'odoo_user_id': u.id,
                'name': u.name,
                'dni': getattr(u, 'dni', '') or '-',
                'code': str(u.id),
                'email': u.email or u.login,
                'initials': initials.upper(),
                'avatar_gradient': color_palette[(idx + len(emp_rows)) % len(color_palette)],
                'company_ids': u.company_ids.ids,
                'role_id': curr_role.id if curr_role else False,
                'role_name': curr_role.name if curr_role else 'Sin Rol',
                'role_code': curr_role.code if curr_role else '',
                'is_employee': is_emp,
            })

        # Ordenar alfabéticamente por nombre
        employees_data.sort(key=lambda x: x['name'].lower())

        return {
            'status': 'success',
            'companies': companies_list,
            'roles': roles_list,
            'employees': employees_data,
        }

    @http.route('/pos_gas_station/toggle_employee_company_access', type='json', auth='user', methods=['POST'], csrf=False)
    def toggle_employee_company_access(self, user_id, company_id, assigned):
        """Asigna o revoca el acceso de un empleado a una empresa (afecta en tiempo real al selector TPV de todas sus estaciones)."""
        try:
            env = request.env
            user = env['res.users'].sudo().browse(int(user_id))
            company = env['res.company'].sudo().browse(int(company_id))

            if not user.exists() or not company.exists():
                return {'status': 'error', 'message': 'Usuario o empresa no encontrados'}

            current_comp_ids = set(user.company_ids.ids)
            if assigned:
                current_comp_ids.add(company.id)
            else:
                if len(current_comp_ids) <= 1 and company.id in current_comp_ids:
                    return {
                        'status': 'warning',
                        'message': f'{user.name} debe pertenecer al menos a una empresa.',
                        'company_ids': list(current_comp_ids)
                    }
                current_comp_ids.discard(company.id)

            vals = {'company_ids': [(6, 0, list(current_comp_ids))]}
            if user.company_id.id not in current_comp_ids:
                vals['company_id'] = list(current_comp_ids)[0]
            user.write(vals)

            _logger.info("Actualizada asignación de empresa para empleado %s: empresas=%s", user.name, list(current_comp_ids))
            return {
                'status': 'success',
                'company_ids': list(current_comp_ids),
                'message': f"Acceso de {user.name} a {company.name} {'concedido' if assigned else 'revocado'}."
            }
        except Exception as ex:
            _logger.exception("Error en toggle_employee_company_access: %s", ex)
            return {'status': 'error', 'message': str(ex)}

    @http.route('/pos_gas_station/open_station', type='json', auth='user', methods=['POST'], csrf=False)
    def open_gas_station(self, config_id):
        try:
            cfg = request.env['pos.config'].sudo().browse(int(config_id))
            if not cfg.exists():
                return {'status': 'error', 'message': 'Punto de venta no encontrado'}

            comp_id = cfg.company_id.id
            active_session = request.env['pos.session'].sudo().search([
                ('config_id', '=', cfg.id),
                ('state', '=', 'opened')
            ], limit=1)

            if not active_session:
                return {
                    'status': 'success',
                    'url': f'/pos_gas_station/select_employee?station_id={cfg.id}'
                }

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
                ('state', 'in', ['paid', 'done', 'invoiced', 'cancel'])
            ], order='date_order desc, id desc')

            payments = env['pos.payment'].sudo().search([('session_id', '=', session.id)])
            non_ext_orders = [o for o in orders if not getattr(o, 'is_extraction', False)]
            active_sales_orders = [o for o in non_ext_orders if not getattr(o, 'is_ticket_annulled', False) and o.state != 'cancel']
            total_sales = round(sum(o.amount_total for o in active_sales_orders), 2)
            extractions_list = [o for o in orders if getattr(o, 'is_extraction', False)]
            total_extraction_liters = round(sum(float(getattr(o, 'extraction_liters', 0.0) or 0.0) for o in extractions_list), 2)

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
                has_annulment = bool(getattr(o, 'is_ticket_annulled', False)) or bool(getattr(o, 'annulment_ref', False)) or (o.state == 'cancel')
                is_albaran = bool(getattr(o, 'is_albaran', False))
                is_annulled_only = has_annulment and not is_inv
                order_state = 'extraction' if getattr(o, 'is_extraction', False) else ('annulled' if is_annulled_only else ('invoiced' if is_inv else ('albaran' if is_albaran else o.state)))

                pump_val = getattr(o, 'pump_id', 0) or getattr(o, 'extraction_pump_id', 0) or 0
                if not pump_val and o.note:
                    m = re.search(r'(?:Calle|Surtidor)\s*[:#]?\s*(\d+)', o.note, re.IGNORECASE)
                    if m:
                        pump_val = int(m.group(1))
                if not pump_val:
                    for l in o.lines:
                        c_note = getattr(l, 'customer_note', '') or ''
                        if c_note:
                            m = re.search(r'(?:Calle|Surtidor)\s*[:#]?\s*(\d+)', c_note, re.IGNORECASE)
                            if m:
                                pump_val = int(m.group(1))
                                break

                annul_ref_val = getattr(o, 'annulment_ref', False) or ''
                if not annul_ref_val and has_annulment:
                    digits = ''.join(c for c in (o.name or '') if c.isdigit()) or str(o.id)
                    annul_ref_val = f"TTTR_{digits[-4:].zfill(4)}"

                annul_date_str = ""
                if getattr(o, 'annulment_date', False):
                    try:
                        a_date = fields.Datetime.context_timestamp(o, o.annulment_date)
                        annul_date_str = a_date.strftime("%d/%m/%Y %H:%M:%S")
                    except Exception:
                        annul_date_str = str(o.annulment_date)
                if not annul_date_str and has_annulment:
                    annul_date_str = date_str

                inv_date_str = ""
                if is_inv and o.account_move:
                    inv_d = o.account_move.invoice_date or o.account_move.date
                    if inv_d:
                        try:
                            inv_date_str = inv_d.strftime("%d/%m/%Y")
                        except Exception:
                            inv_date_str = str(inv_d)
                if not inv_date_str and is_inv:
                    inv_date_str = date_str

                order_history = []
                # 1. Ticket de Anulación si fue anulado (directo o por factura)
                if has_annulment:
                    annul_reason = getattr(o, 'annulment_reason', '') or ('Anulado por canje a factura' if is_inv else 'Anulación de ticket')
                    order_history.append({
                        'type': 'annulment',
                        'type_label': 'Ticket Anulación',
                        'icon': 'fa-ban',
                        'badge_class': 'badge-history-annulment',
                        'ref': annul_ref_val,
                        'date': annul_date_str,
                        'description': annul_reason,
                        'amount': f"-{o.amount_total:.2f}",
                        'amount_raw': -o.amount_total,
                    })

                # 2. Factura oficial emitida
                if is_inv:
                    partner_desc = o.partner_id.name if o.partner_id else 'Cliente'
                    if o.partner_id and o.partner_id.vat:
                        partner_desc += f" ({o.partner_id.vat})"
                    order_history.append({
                        'type': 'invoice',
                        'type_label': 'Factura Oficial',
                        'icon': 'fa-file-text-o',
                        'badge_class': 'badge-history-invoice',
                        'ref': o.account_move.name or f"FACT-{o.account_move.id}",
                        'account_move_id': o.account_move.id,
                        'date': inv_date_str,
                        'description': f"Facturado a {partner_desc}",
                        'amount': f"{o.amount_total:.2f}",
                        'amount_raw': o.amount_total,
                        'invoice_url': inv_url,
                    })

                # 3. Cliente de crédito / Albarán
                if is_albaran:
                    plate_driver = []
                    if getattr(o, 'vehicle_plate', ''):
                        plate_driver.append(f"Matrícula: {o.vehicle_plate}")
                    if getattr(o, 'vehicle_driver', ''):
                        plate_driver.append(f"Conductor: {o.vehicle_driver}")
                    extra_info = f" ({' | '.join(plate_driver)})" if plate_driver else ""
                    order_history.append({
                        'type': 'albaran',
                        'type_label': 'Cliente Crédito',
                        'icon': 'fa-credit-card',
                        'badge_class': 'badge-history-albaran',
                        'ref': f"Albarán Crédito ({o.name})",
                        'date': date_str,
                        'description': f"Suministro a crédito: {o.partner_id.name if o.partner_id else 'Cliente'}{extra_info}",
                        'amount': f"{o.amount_total:.2f}",
                        'amount_raw': o.amount_total,
                    })

                has_history = len(order_history) > 0

                orders_list.append({
                    'id': o.id,
                    'name': o.name,
                    'pos_reference': o.pos_reference or o.name,
                    'date_order': date_str,
                    'date_order_raw': o.date_order.isoformat() if o.date_order else '',
                    'session_id': session.id,
                    'session_name': session.name,
                    'user_name': o.user_id.name or 'Cajero',
                    'pump_id': pump_val,
                    'pump_name': f"Calle {pump_val}" if pump_val else "",
                    'partner_id': o.partner_id.id if o.partner_id else False,
                    'partner_name': o.partner_id.name if o.partner_id else False,
                    'partner_ref': o.partner_id.ref or (f"CLI-{o.partner_id.id}" if o.partner_id else ''),
                    'partner_vat': o.partner_id.vat if o.partner_id else '',
                    'partner_street': o.partner_id.street or '',
                    'partner_city': o.partner_id.city or '',
                    'partner_zip': o.partner_id.zip or '',
                    'partner_phone': o.partner_id.phone or '',
                    'partner_email': o.partner_id.email or '',
                    'partner_customer_type': getattr(o.partner_id, 'customer_type', 'ordinary') or 'ordinary',
                    'partner_customer_payment_mode': getattr(o.partner_id, 'customer_payment_mode', 'cash') or 'cash',
                    'partner_credit_blocked': getattr(o.partner_id, 'credit_blocked', False) or False,
                    'partner_vehicles': [{'id': v.id, 'name': v.name} for v in getattr(o.partner_id, 'vehicle_ids', [])],
                    'fiscal_position': o.fiscal_position_id.name if o.fiscal_position_id else 'Posición fiscal ordinaria',
                    'state': order_state,
                    'is_invoiced': is_inv,
                    'is_extraction': getattr(o, 'is_extraction', False),
                    'is_albaran': is_albaran,
                    'vehicle_plate': getattr(o, 'vehicle_plate', '') or '',
                    'vehicle_driver': getattr(o, 'vehicle_driver', '') or '',
                    'extraction_reason': getattr(o, 'extraction_reason', '') or '',
                    'extraction_liters': float(getattr(o, 'extraction_liters', 0.0) or 0.0),
                    'extraction_pump_id': int(getattr(o, 'extraction_pump_id', 0) or 0),
                    'is_ticket_annulled': is_annulled_only,
                    'has_annulment': has_annulment,
                    'annulment_ref': annul_ref_val,
                    'annulment_reason': getattr(o, 'annulment_reason', False) or ('Anulación de ticket' if has_annulment else ''),
                    'annulment_date': annul_date_str,
                    'account_move_id': o.account_move.id if is_inv else False,
                    'account_move_name': o.account_move.name if is_inv else '',
                    'invoice_url': inv_url,
                    'has_history': has_history,
                    'history': order_history,
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
                    'orders_count': len(non_ext_orders),
                    'extractions_count': len(extractions_list),
                    'total_extraction_liters': total_extraction_liters
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
                ref = order._generate_annulment_ref() if hasattr(order, '_generate_annulment_ref') else f"TTTR_{(''.join(c for c in (order.name or '') if c.isdigit()) or str(order.id))[-4:].zfill(4)}"
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
                    'ref': p.ref or f"CLI-{p.id}",
                    'vat': p.vat or '',
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
    def search_partners(self, query='', credit_only=False, config_id=None, **kw):
        try:
            env = request.env
            q = (query or '').strip()
            if not credit_only and (not q or len(q) < 2):
                return {'status': 'success', 'partners': []}

            base_domain = [('active', '=', True)]
            if config_id:
                try:
                    cfg = env['pos.config'].sudo().browse(int(config_id))
                    if cfg.exists() and cfg.company_id:
                        base_domain = [
                            ('active', '=', True),
                            ('company_id', '=', cfg.company_id.id)
                        ]
                except Exception:
                    pass

            if credit_only:
                credit_filter = [
                    '|',
                    ('customer_payment_mode', '=', 'credit'),
                    ('customer_type', 'in', ['credit', 'monthly'])
                ]
                search_filter = ['|', '|', ('name', 'ilike', q), ('vat', 'ilike', q), ('ref', 'ilike', q)] if q else []
                partners = env['res.partner'].sudo().search(base_domain + credit_filter + search_filter, order='name asc', limit=60)
            else:
                search_filter = ['|', '|', ('name', 'ilike', q), ('vat', 'ilike', q), ('ref', 'ilike', q)]
                partners = env['res.partner'].sudo().search(base_domain + search_filter, order='name asc', limit=25)

            results = []
            for p in partners:
                results.append({
                    'id': p.id,
                    'name': p.name,
                    'ref': p.ref or '',
                    'vat': p.vat or '',
                    'street': p.street or '',
                    'city': p.city or '',
                    'zip': p.zip or '',
                    'phone': p.phone or '',
                    'email': p.email or '',
                    'customer_type': getattr(p, 'customer_type', 'ordinary') or 'ordinary',
                    'customer_payment_mode': getattr(p, 'customer_payment_mode', 'cash') or 'cash',
                    'invoice_periodicity': getattr(p, 'invoice_periodicity', 'daily') or 'daily',
                    'credit_blocked': getattr(p, 'credit_blocked', False) or False,
                    'credit_limit_amount': float(getattr(p, 'credit_limit_amount', 0.0) or 0.0),
                    'vehicles': [{'id': v.id, 'name': v.name} for v in getattr(p, 'vehicle_ids', [])],
                })
            return {'status': 'success', 'partners': results}
        except Exception as e:
            _logger.exception("Error in /pos_gas_station/search_partners: %s", e)
            return {'status': 'error', 'message': str(e)}

    @http.route('/pos_gas_station/get_partner_vehicles', type='json', auth='user', methods=['POST'], csrf=False)
    def get_partner_vehicles(self, partner_id, **kw):
        try:
            if not partner_id:
                return {'status': 'error', 'message': 'ID de cliente no proporcionado', 'vehicles': []}
            partner = request.env['res.partner'].sudo().browse(int(partner_id))
            if not partner.exists():
                return {'status': 'error', 'message': 'Cliente no encontrado', 'vehicles': []}
            vehicles = [{'id': v.id, 'name': v.name, 'notes': v.notes or ''} for v in getattr(partner, 'vehicle_ids', [])]
            return {'status': 'success', 'vehicles': vehicles}
        except Exception as e:
            _logger.exception("Error in /pos_gas_station/get_partner_vehicles: %s", e)
            return {'status': 'error', 'message': str(e), 'vehicles': []}

    @http.route('/pos_gas_station/save_partner_vehicle', type='json', auth='user', methods=['POST'], csrf=False)
    def save_partner_vehicle(self, partner_id, plate, notes=None, **kw):
        try:
            if not partner_id:
                return {'status': 'error', 'message': 'ID de cliente no proporcionado'}
            partner = request.env['res.partner'].sudo().browse(int(partner_id))
            if not partner.exists():
                return {'status': 'error', 'message': 'Cliente no encontrado'}

            clean_plate = (plate or '').strip().upper()
            if not clean_plate or len(clean_plate) < 3:
                return {'status': 'error', 'message': 'La matrícula debe tener al menos 3 caracteres'}

            existing_veh = request.env['res.partner.vehicle'].sudo().search([
                ('name', '=', clean_plate),
                ('partner_id', '=', partner.id)
            ], limit=1)

            if existing_veh:
                veh = existing_veh
                if notes and str(notes).strip() and not veh.notes:
                    veh.write({'notes': str(notes).strip()})
            else:
                veh = request.env['res.partner.vehicle'].sudo().create({
                    'name': clean_plate,
                    'partner_id': partner.id,
                    'notes': str(notes).strip() if notes else False
                })

            vehicles = [{'id': v.id, 'name': v.name, 'notes': v.notes or ''} for v in getattr(partner, 'vehicle_ids', [])]
            return {
                'status': 'success',
                'vehicle': {'id': veh.id, 'name': veh.name, 'notes': veh.notes or ''},
                'vehicles': vehicles
            }
        except Exception as e:
            _logger.exception("Error in /pos_gas_station/save_partner_vehicle: %s", e)
            return {'status': 'error', 'message': str(e)}

    @http.route('/pos_gas_station/save_partner', type='json', auth='user', methods=['POST'], csrf=False)
    def save_partner(self, partner_data, **kw):
        """Crear o editar cliente directamente desde el modal del TPV con validación y asignación a la empresa del TPV."""
        try:
            env = request.env
            partner_id = partner_data.get('id')
            name = (partner_data.get('name') or '').strip()
            if not name:
                return {'status': 'error', 'message': 'El Nombre o Razón Social es obligatorio.'}

            config_id = partner_data.get('config_id')
            company_id = partner_data.get('company_id')
            if not company_id and config_id:
                try:
                    cfg = env['pos.config'].sudo().browse(int(config_id))
                    if cfg.exists() and cfg.company_id:
                        company_id = cfg.company_id.id
                except Exception:
                    pass
            if not company_id:
                company_id = env.company.id

            vals = {
                'name': name,
                'vat': (partner_data.get('vat') or '').strip().upper() or False,
                'ref': (partner_data.get('ref') or '').strip() or False,
                'street': (partner_data.get('street') or '').strip() or False,
                'zip': (partner_data.get('zip') or '').strip() or False,
                'city': (partner_data.get('city') or '').strip() or False,
                'phone': (partner_data.get('phone') or '').strip() or False,
                'mobile': (partner_data.get('mobile') or '').strip() or False,
                'email': (partner_data.get('email') or '').strip() or False,
                'customer_rank': 1,
            }

            state_id = partner_data.get('state_id')
            if state_id:
                try:
                    vals['state_id'] = int(state_id)
                except (ValueError, TypeError):
                    vals['state_id'] = False
            else:
                vals['state_id'] = False

            if partner_id:
                partner = env['res.partner'].sudo().browse(int(partner_id))
                if not partner.exists():
                    return {'status': 'error', 'message': 'Cliente no encontrado.'}
                # Regla de seguridad: Un expendedor NO puede modificar el tipo de facturación ni crédito desde el TPV.
                # El tipo de facturación y condiciones comerciales solo pueden cambiarse desde la administración de Odoo.
                partner.write(vals)
            else:
                # Clientes nuevos creados desde el TPV: siempre nacen como Ordinaria (Contado).
                vals['customer_type'] = 'ordinary'
                vals['customer_payment_mode'] = 'cash'
                vals['company_id'] = company_id
                partner = env['res.partner'].sudo().create(vals)

            # Matrícula si se ha introducido
            new_plate = (partner_data.get('new_plate') or '').strip().upper()
            if new_plate and len(new_plate) >= 3:
                existing_veh = env['res.partner.vehicle'].sudo().search([
                    ('name', '=', new_plate),
                    ('partner_id', '=', partner.id)
                ], limit=1)
                if not existing_veh:
                    env['res.partner.vehicle'].sudo().create({
                        'name': new_plate,
                        'partner_id': partner.id
                    })

            # Devolver objeto completo de partner para el frontend
            state_val = [partner.state_id.id, partner.state_id.name] if partner.state_id else False
            country_val = [partner.country_id.id, partner.country_id.name] if partner.country_id else False
            comp_val = [partner.company_id.id, partner.company_id.name] if partner.company_id else False

            partner_dict = {
                'id': partner.id,
                'name': partner.name,
                'vat': partner.vat or '',
                'ref': partner.ref or '',
                'street': partner.street or '',
                'zip': partner.zip or '',
                'city': partner.city or '',
                'state_id': state_val,
                'country_id': country_val,
                'phone': partner.phone or '',
                'mobile': partner.mobile or '',
                'email': partner.email or '',
                'barcode': partner.barcode or '',
                'company_id': comp_val,
                'customer_type': getattr(partner, 'customer_type', 'ordinary') or 'ordinary',
                'customer_payment_mode': getattr(partner, 'customer_payment_mode', 'cash') or 'cash',
                'invoice_periodicity': getattr(partner, 'invoice_periodicity', 'daily') or 'daily',
                'credit_blocked': getattr(partner, 'credit_blocked', False) or False,
                'credit_limit_amount': float(getattr(partner, 'credit_limit_amount', 0.0) or 0.0),
                'vehicles': [{'id': v.id, 'name': v.name, 'notes': v.notes or ''} for v in getattr(partner, 'vehicle_ids', [])],
            }

            return {
                'status': 'success',
                'partner': partner_dict,
                'message': 'Cliente guardado correctamente.'
            }
        except Exception as e:
            _logger.exception("Error in /pos_gas_station/save_partner: %s", e)
            return {'status': 'error', 'message': str(e)}

    @http.route('/pos_gas_station/remove_partner_vehicle', type='json', auth='user', methods=['POST'], csrf=False)
    def remove_partner_vehicle(self, vehicle_id, **kw):
        try:
            if not vehicle_id:
                return {'status': 'error', 'message': 'ID de vehículo no proporcionado'}
            veh = request.env['res.partner.vehicle'].sudo().browse(int(vehicle_id))
            if veh.exists():
                partner_id = veh.partner_id.id
                veh.unlink()
                partner = request.env['res.partner'].sudo().browse(partner_id)
                vehicles = [{'id': v.id, 'name': v.name, 'notes': v.notes or ''} for v in getattr(partner, 'vehicle_ids', [])]
                return {'status': 'success', 'vehicles': vehicles}
            return {'status': 'error', 'message': 'Vehículo no encontrado'}
        except Exception as e:
            _logger.exception("Error in /pos_gas_station/remove_partner_vehicle: %s", e)
            return {'status': 'error', 'message': str(e)}

    def _get_or_create_credit_partner(self, env, partner_data, config_id=None, company_id=None, vehicle_plate=None):
        name = str((partner_data or {}).get('name') or '').strip()
        vat = str((partner_data or {}).get('vat') or '').strip().upper()
        if not name:
            raise UserError('Debe indicar el Nombre o Razón Social del cliente de crédito.')
        if not vat:
            raise UserError('Debe indicar el CIF / NIF del cliente de crédito.')

        ctype = str((partner_data or {}).get('customer_type') or 'credit').strip()
        if ctype not in ('credit', 'monthly'):
            ctype = 'credit'
        periodicity = 'monthly' if ctype == 'monthly' else 'daily'

        station = None
        if config_id:
            try:
                st = env['pos.config'].sudo().browse(int(config_id))
                if st.exists():
                    station = st
                    if st.company_id and not company_id:
                        company_id = st.company_id.id
            except Exception:
                pass

        domain = [('vat', '=ilike', vat)]
        if station:
            domain = ['&', ('vat', '=ilike', vat), '|', ('station_id', '=', station.id), ('station_id', '=', False)]
        partner = env['res.partner'].sudo().search(domain, limit=1)

        street = str((partner_data or {}).get('street') or '').strip()
        city = str((partner_data or {}).get('city') or '').strip()
        zip_code = str((partner_data or {}).get('zip') or '').strip()
        phone = str((partner_data or {}).get('phone') or '').strip()
        email = str((partner_data or {}).get('email') or '').strip()

        if partner:
            vals_update = {
                'customer_rank': max(partner.customer_rank or 0, 1),
                'customer_type': ctype,
                'customer_payment_mode': 'credit',
                'invoice_periodicity': periodicity,
                'credit_blocked': False,
            }
            if street and not partner.street:
                vals_update['street'] = street
            if city and not partner.city:
                vals_update['city'] = city
            if zip_code and not partner.zip:
                vals_update['zip'] = zip_code
            if phone and not partner.phone:
                vals_update['phone'] = phone
            if email and not partner.email:
                vals_update['email'] = email
            if station and not partner.station_id:
                vals_update['station_id'] = station.id
            partner.sudo().write(vals_update)
        else:
            vals_create = {
                'name': name,
                'vat': vat,
                'street': street or False,
                'city': city or False,
                'zip': zip_code or False,
                'phone': phone or False,
                'email': email or False,
                'customer_rank': 1,
                'customer_type': ctype,
                'customer_payment_mode': 'credit',
                'invoice_periodicity': periodicity,
                'credit_blocked': False,
                'station_id': station.id if station else False,
                'company_id': company_id or (station.company_id.id if (station and station.company_id) else env.company.id),
            }
            partner = env['res.partner'].sudo().with_context(default_customer_rank=1).create(vals_create)

        clean_plate = (vehicle_plate or '').strip().upper() if vehicle_plate else False
        if clean_plate:
            existing_veh = env['res.partner.vehicle'].sudo().search([
                ('partner_id', '=', partner.id),
                ('name', '=', clean_plate)
            ], limit=1)
            if not existing_veh:
                env['res.partner.vehicle'].sudo().create({
                    'partner_id': partner.id,
                    'name': clean_plate
                })

        return partner

    @http.route('/pos_gas_station/create_credit_partner', type='json', auth='user', methods=['POST'], csrf=False)
    def create_credit_partner(self, partner_data, config_id=None, vehicle_plate=None, **kw):
        try:
            env = request.env
            p = self._get_or_create_credit_partner(
                env,
                partner_data=partner_data,
                config_id=config_id,
                vehicle_plate=vehicle_plate
            )
            return {
                'status': 'success',
                'partner': {
                    'id': p.id,
                    'name': p.name,
                    'ref': p.ref or '',
                    'vat': p.vat or '',
                    'street': p.street or '',
                    'city': p.city or '',
                    'zip': p.zip or '',
                    'phone': p.phone or '',
                    'email': p.email or '',
                    'customer_type': getattr(p, 'customer_type', 'credit') or 'credit',
                    'customer_payment_mode': 'credit',
                    'invoice_periodicity': getattr(p, 'invoice_periodicity', 'daily') or 'daily',
                    'credit_blocked': False,
                    'credit_limit_amount': float(getattr(p, 'credit_limit_amount', 0.0) or 0.0),
                    'hasCredit': True,
                    'vehicles': [{'id': v.id, 'name': v.name} for v in getattr(p, 'vehicle_ids', [])],
                }
            }
        except Exception as e:
            _logger.exception("Error in /pos_gas_station/create_credit_partner: %s", e)
            return {'status': 'error', 'message': str(e)}

    @http.route('/pos_gas_station/convert_to_albaran', type='json', auth='user', methods=['POST'], csrf=False)
    def convert_to_albaran(self, order_id, partner_id=None, partner_data=None, vehicle_plate=None, vehicle_driver=None, **kw):
        try:
            env = request.env
            order = env['pos.order'].sudo().browse(int(order_id))
            if not order.exists():
                return {'status': 'error', 'message': 'Pedido no encontrado'}

            if not partner_id and partner_data:
                cfg_id = order.session_id.config_id.id if (order.session_id and order.session_id.config_id) else None
                comp_id = order.company_id.id if order.company_id else None
                new_partner = self._get_or_create_credit_partner(
                    env,
                    partner_data=partner_data,
                    config_id=cfg_id,
                    company_id=comp_id,
                    vehicle_plate=vehicle_plate
                )
                partner_id = new_partner.id

            if not partner_id:
                return {'status': 'error', 'message': 'Debe seleccionar o crear un cliente de crédito válido.'}

            order.action_convert_to_albaran(
                partner_id=partner_id,
                vehicle_plate=vehicle_plate,
                vehicle_driver=vehicle_driver
            )

            return {
                'status': 'success',
                'order_id': order.id,
                'order_name': order.name,
                'partner_id': order.partner_id.id,
                'partner_name': order.partner_id.name,
                'partner_vat': order.partner_id.vat or '',
                'is_albaran': True,
                'vehicle_plate': order.vehicle_plate or '',
                'vehicle_driver': order.vehicle_driver or '',
                'message': f"Pedido {order.name} convertido con éxito en Albarán de Crédito para {order.partner_id.name}."
            }
        except Exception as e:
            _logger.exception("Error in /pos_gas_station/convert_to_albaran: %s", e)
            return {'status': 'error', 'message': str(e)}


    @http.route('/pos_gas_station/delete_station', type='json', auth='user', methods=['POST'], csrf=False)
    def delete_station(self, config_id):
        try:
            env = request.env
            config = env['pos.config'].sudo().browse(int(config_id))
            if not config.exists():
                return {'status': 'error', 'message': 'La estación no existe.'}

            if config.id == 7 or 'repsol' in (config.name or '').lower():
                return {'status': 'error', 'message': '¡ESTACIÓN PROTEGIDA! E.S. Repsol es la estación principal activa en producción y no se puede borrar bajo ningún concepto.'}

            # Validar si tiene sesiones o tickets asociados
            has_sessions = env['pos.session'].sudo().search_count([('config_id', '=', config.id)])
            has_orders = env['pos.order'].sudo().search_count([('config_id', '=', config.id)])
            if has_sessions or has_orders:
                return {
                    'status': 'error',
                    'message': f'No se puede eliminar la estación "{config.name}" porque contiene datos asociados ({has_sessions} turnos, {has_orders} tickets).'
                }

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

            if comp.id == 4 or 'trieste' in (comp.name or '').lower():
                return {'status': 'error', 'message': '¡EMPRESA PROTEGIDA! A.R. Trieste es la empresa principal activa en producción y no se puede borrar bajo ningún concepto.'}

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

            cid = comp.id
            partner = comp.partner_id
            name = comp.name
            partner_id = partner.id if partner else None

            # Fallback de empresa activa para usuarios y sesiones
            fallback_comp = env['res.company'].sudo().browse(4)
            if not fallback_comp.exists() or fallback_comp.id == cid:
                fallback_comp = env['res.company'].sudo().search([('id', '!=', cid)], limit=1)
            fallback_id = fallback_comp.id if fallback_comp else False

            # 1. Reglas de stock (deben eliminarse antes de los almacenes para evitar ForeignKeyViolation con stock_picking_type)
            rules = env['stock.rule'].sudo().search([('company_id', '=', cid)])
            if rules:
                rules.unlink()

            # 2. Almacenes creados automáticamente para esta empresa
            warehouses = env['stock.warehouse'].sudo().search([('company_id', '=', cid)])
            if warehouses:
                warehouses.unlink()

            # 3. Propiedades de configuración (ir.property): ELIMINAR DIRECTAMENTE VÍA SQL
            env.cr.execute("DELETE FROM ir_property WHERE company_id = %s", [cid])
            env.cr.execute("DELETE FROM ir_property WHERE res_id = %s", [f'res.company,{cid}'])
            if partner_id:
                env.cr.execute("DELETE FROM ir_property WHERE res_id = %s", [f'res.partner,{partner_id}'])

            # 4. Tipos de albarán, ubicaciones y rutas de stock asociadas
            env['stock.picking.type'].sudo().search([('company_id', '=', cid)]).unlink()
            env['stock.location'].sudo().search([('company_id', '=', cid)]).unlink()
            env['stock.route'].sudo().search([('company_id', '=', cid)]).unlink()

            # 5. Secuencias generadas para la empresa
            env['ir.sequence'].sudo().search([('company_id', '=', cid)]).unlink()

            # 6. Desvincular de usuarios: primero reasignar la empresa principal por defecto si era cid
            if fallback_id:
                users_with_default = env['res.users'].sudo().search([('company_id', '=', cid)])
                for u in users_with_default:
                    u.write({'company_id': fallback_id})

            users = env['res.users'].sudo().search([('company_ids', 'in', [cid])])
            for u in users:
                u.write({'company_ids': [(3, cid)]})

            # Limpiar sesión actual si apuntaba a la empresa eliminada
            if request.session.get('admin_active_company_id') == cid and fallback_id:
                request.session['admin_active_company_id'] = fallback_id
            if request.session.get('current_company_id') == cid and fallback_id:
                request.session['current_company_id'] = fallback_id
            if request.session.get('allowed_company_ids') == [cid] and fallback_id:
                request.session['allowed_company_ids'] = [fallback_id]

            # 7. Desvincular de Administradores VPN (utrecar_vpn_admin_company_rel)
            env.cr.execute("DELETE FROM utrecar_vpn_admin_company_rel WHERE company_id = %s", [cid])

            # 8. Romper FK circular de calendario laboral antes de borrar resource.calendar
            try:
                comp.write({'resource_calendar_id': False})
            except Exception:
                pass
            env['resource.calendar'].sudo().search([('company_id', '=', cid)]).unlink()
            env['product.pricelist'].sudo().search([('company_id', '=', cid)]).unlink()

            # 9. Eliminar accesos de roles por empresa
            accs = env['utrecar.employee.company.access'].sudo().search([('company_id', '=', cid)])
            if accs:
                accs.unlink()

            # 10. Desvincular partners creados con esa compañía
            other_partners = env['res.partner'].sudo().search([('company_id', '=', cid)])
            for p in other_partners:
                if p.id != partner_id:
                    try:
                        p.write({'company_id': False})
                    except Exception:
                        pass

            # 11. Unlink de la compañía
            comp.unlink()

            # 12. Eliminar el partner creado para la empresa si no tiene usuarios vinculados y no es del sistema
            if partner_id and partner_id not in [1, 2, 41, 2254, 2255]:
                try:
                    p = env['res.partner'].sudo().browse(partner_id)
                    if p.exists() and not p.user_ids:
                        p.unlink()
                except Exception:
                    pass
            return {'status': 'success', 'message': f'Empresa "{name}" eliminada correctamente.'}
        except Exception as e:
            _logger.exception("Error in /pos_gas_station/delete_company: %s", e)
            return {'status': 'error', 'message': str(e)}

    @http.route('/pos_gas_station/rename_company', type='json', auth='user', methods=['POST'], csrf=False)
    def rename_company(self, company_id, name, vat=None, street=None, zip=None, city=None, phone=None, email=None, website=None):
        return self.update_company(company_id=company_id, name=name, vat=vat, street=street, zip=zip, city=city, phone=phone, email=email, website=website)

    @http.route('/pos_gas_station/update_company', type='json', auth='user', methods=['POST'], csrf=False)
    def update_company(self, company_id, name, vat=None, street=None, zip=None, city=None, phone=None, email=None, website=None):
        try:
            env = request.env
            if not (env.user.has_group('point_of_sale.group_pos_manager') or env.user._is_admin()):
                return {'status': 'error', 'message': 'No tiene permisos para modificar la empresa.'}
            comp = env['res.company'].sudo().browse(int(company_id))
            if not comp.exists():
                return {'status': 'error', 'message': 'La empresa no existe.'}
            clean_name = (name or '').strip()
            if not clean_name:
                return {'status': 'error', 'message': 'El nombre de la empresa no puede estar vacío.'}
            vals = {
                'name': clean_name,
                'vat': (vat or '').strip() or False,
                'street': (street or '').strip() or False,
                'zip': (zip or '').strip() or False,
                'city': (city or '').strip() or False,
                'phone': (phone or '').strip() or False,
                'email': (email or '').strip() or False,
                'website': (website or '').strip() or False,
            }
            comp.write(vals)
            return {'status': 'success', 'name': clean_name, 'message': f'Empresa "{clean_name}" actualizada correctamente.'}
        except Exception as e:
            _logger.exception("Error in update_company: %s", e)
            return {'status': 'error', 'message': str(e)}

    @http.route('/pos_gas_station/create_company', type='json', auth='user', methods=['POST'], csrf=False)
    def create_company_quick(self, name, vat=None, street=None, zip=None, city=None, phone=None, email=None):
        try:
            env = request.env
            if not (env.user.has_group('point_of_sale.group_pos_manager') or env.user._is_admin()):
                return {'status': 'error', 'message': 'No tiene permisos para crear empresas.'}
            clean_name = (name or '').strip()
            if not clean_name:
                return {'status': 'error', 'message': 'El nombre de la empresa es obligatorio.'}
            vals = {
                'name': clean_name,
                'vat': (vat or '').strip() or False,
                'street': (street or '').strip() or False,
                'zip': (zip or '').strip() or False,
                'city': (city or '').strip() or False,
                'phone': (phone or '').strip() or False,
                'email': (email or '').strip() or False,
            }
            comp = env['res.company'].sudo().create(vals)
            try:
                env.user.sudo().write({'company_ids': [(4, comp.id)]})
            except Exception:
                pass
            return {'status': 'success', 'company_id': comp.id, 'name': comp.name, 'message': f'Empresa "{comp.name}" creada con éxito.'}
        except Exception as e:
            _logger.exception("Error in create_company_quick: %s", e)
            return {'status': 'error', 'message': str(e)}

    @http.route('/pos_gas_station/create_station', type='json', auth='user', methods=['POST'], csrf=False)
    def create_station_quick(self, company_id, name, vpn_ip=None):
        try:
            env = request.env
            if not (env.user.has_group('point_of_sale.group_pos_manager') or env.user._is_admin()):
                return {'status': 'error', 'message': 'No tiene permisos para crear estaciones.'}
            comp = env['res.company'].sudo().browse(int(company_id))
            if not comp.exists():
                return {'status': 'error', 'message': 'Empresa no encontrada.'}
            clean_name = (name or '').strip()
            if not clean_name:
                return {'status': 'error', 'message': 'El nombre de la estación es obligatorio.'}
            st = env['pos.config'].sudo().with_company(comp).create({
                'name': clean_name,
                'company_id': comp.id,
                'vpn_ip': (vpn_ip or '').strip() or False,
            })
            return {'status': 'success', 'config_id': st.id, 'name': st.name, 'message': f'Estación "{st.name}" creada con éxito en {comp.name}.'}
        except Exception as e:
            _logger.exception("Error in create_station_quick: %s", e)
            return {'status': 'error', 'message': str(e)}

    @http.route('/pos_gas_station/update_station', type='json', auth='user', methods=['POST'], csrf=False)
    def update_station(self, config_id, name, vpn_ip=None, admin_platform_code=None, company_id=None,
                       street=None, zip=None, city=None, phone=None, email=None):
        try:
            env = request.env
            if not (env.user.has_group('point_of_sale.group_pos_manager') or env.user._is_admin()):
                return {'status': 'error', 'message': 'No tiene permisos para modificar estaciones.'}
            st = env['pos.config'].sudo().browse(int(config_id))
            if not st.exists():
                return {'status': 'error', 'message': 'Estación no encontrada.'}
            clean_name = (name or '').strip()
            if not clean_name:
                return {'status': 'error', 'message': 'El nombre de la estación es obligatorio.'}

            vals = {
                'name': clean_name,
                'vpn_ip': (vpn_ip or '').strip() or False,
                'street': (street or '').strip() or False,
                'zip': (zip or '').strip() or False,
                'city': (city or '').strip() or False,
                'phone': (phone or '').strip() or False,
                'email': (email or '').strip() or False,
            }
            if admin_platform_code is not None:
                ap_str = str(admin_platform_code).strip()
                vals['admin_platform_code'] = int(ap_str) if ap_str else False

            if company_id:
                new_comp = env['res.company'].sudo().browse(int(company_id))
                if new_comp.exists() and new_comp.id != st.company_id.id:
                    active_sess = env['pos.session'].sudo().search([('config_id', '=', st.id), ('state', '!=', 'closed')], limit=1)
                    if active_sess:
                        return {'status': 'error', 'message': f'No se puede cambiar la empresa de la estación mientras tenga un turno abierto ({active_sess.name}). Cierre el turno primero.'}
                    vals['company_id'] = new_comp.id

            st.write(vals)
            return {
                'status': 'success',
                'config_id': st.id,
                'name': st.name,
                'message': f'Estación "{st.name}" actualizada correctamente.'
            }
        except Exception as e:
            _logger.exception("Error in update_station: %s", e)
            return {'status': 'error', 'message': str(e)}

    @http.route('/pos_gas_station/rename_station', type='json', auth='user', methods=['POST'], csrf=False)
    def rename_station(self, config_id, name):
        return self.update_station(config_id=config_id, name=name)

    @http.route('/pos_gas_station/register_extraction', type='json', auth='user', methods=['POST'], csrf=False)
    def register_extraction(self, session_id=None, order_lines=None, reason=None, pump_id=None, notes=None):
        try:
            env = request.env
            session = None
            if session_id:
                session = env['pos.session'].sudo().browse(int(session_id))
            if not session or not session.exists():
                session = env['pos.session'].sudo().search([('state', '=', 'opened')], order='id desc', limit=1)
            if not session or not session.exists():
                return {'status': 'error', 'message': 'No hay sesión de caja abierta activa.'}

            if not order_lines:
                return {'status': 'error', 'message': 'No se enviaron líneas para registrar como extracción.'}

            reason_str = (reason or 'Prueba de probeta / Calibración metrológica').strip()
            if notes:
                reason_str += f" - {notes.strip()}"

            total_amount = 0.0
            total_liters = 0.0
            lines_vals = []

            for line in order_lines:
                p_id = int(line.get('product_id'))
                qty = float(line.get('qty', 0.0))
                price = float(line.get('price_unit', 0.0))
                subtotal = qty * price
                total_amount += subtotal

                prod = env['product.product'].sudo().browse(p_id)
                p_name = (prod.name or '').upper()
                is_fuel = any(k in p_name for k in ['GASOLEO', 'GASÓLEO', 'PLOMO', 'DIESEL', 'DIÉSEL', 'GASOLINA', 'G+', 'CARBURANTE'])
                if not is_fuel and prod.pos_categ_ids:
                    is_fuel = any('carburante' in c.name.lower() or 'fuel' in c.name.lower() for c in prod.pos_categ_ids)
                total_liters += qty

                lines_vals.append((0, 0, {
                    'product_id': p_id,
                    'qty': qty,
                    'price_unit': price,
                    'price_subtotal': subtotal,
                    'price_subtotal_incl': subtotal,
                }))

            ext_seq = int(time.time()) % 10000
            order_name = f"EXTR/{session.name or 'POS'}/{ext_seq:04d}"

            order_vals = {
                'name': order_name,
                'pos_reference': f"Extracción {order_name}",
                'session_id': session.id,
                'config_id': session.config_id.id,
                'user_id': env.user.id,
                'amount_total': total_amount,
                'amount_tax': 0.0,
                'amount_paid': 0.0,
                'amount_return': 0.0,
                'lines': lines_vals,
                'state': 'done',
                'is_extraction': True,
                'extraction_reason': reason_str,
                'extraction_liters': total_liters,
                'extraction_date': fields.Datetime.now(),
                'extraction_pump_id': int(pump_id or 0),
            }

            order = env['pos.order'].sudo().create(order_vals)
            order.message_post(body=f"⛽ <strong>Extracción / Retorno a Depósito:</strong> {total_liters:.2f} Litros devueltos al depósito.<br/>Motivo: <em>{reason_str}</em>.<br/><strong>No descuenta existencias de inventario ni se resta al cajero en el turno.</strong>")

            return {
                'status': 'success',
                'order_id': order.id,
                'order_name': order.name,
                'liters': total_liters,
                'amount': total_amount,
                'message': f"Extracción de {total_liters:.2f} L registrada con éxito como Retorno a Depósito."
            }
        except Exception as e:
            _logger.exception("Error in /pos_gas_station/register_extraction: %s", e)
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


    @http.route('/pos_gas_station/vpn_employees_data', type='json', auth='user', methods=['POST'], csrf=False)
    def get_vpn_station_employees_data(self):
        """Devuelve el directorio de usuarios con asignación por empresa y el catálogo de estaciones de trabajo con sus VPN."""
        env = request.env
        PosConfig = env['pos.config'].sudo()
        stations = PosConfig.search([('active', 'in', [True, False])], order='id')
        
        stations_data = []
        all_users = []
        default_map = PosConfig._get_default_station_vpn_mapping()

        trieste_comp = env['res.company'].sudo().browse(4)
        utrecar_comp = env['res.company'].sudo().browse(1)

        # 1. Administradores únicos de Odoo
        admin_emails = set()
        admin_users = env['res.users'].sudo().search([('active', '=', True)], order='id')
        for u in admin_users:
            if u._is_admin() or u.has_group('base.group_erp_manager') or u.has_group('base.group_system'):
                if u.login in ['__system__', 'default']:
                    continue
                email = (u.email or u.login).lower().strip()
                admin_emails.add(email)
                parts = u.name.split()
                initials = (parts[0][0] + (parts[1][0] if len(parts) > 1 else '')) if parts else 'AD'
                all_users.append({
                    'id': f'admin_{u.id}',
                    'full_name': u.name,
                    'dni': getattr(u, 'dni', '') or '-',
                    'email': u.email or u.login,
                    'login': u.login,
                    'puesto': 'Administrador',
                    'odoo_role': 'Administrador',
                    'initials': initials.upper(),
                    'avatar_gradient': 'linear-gradient(135deg, #1e293b, #0f172a)',
                    'company_name': 'Multi-Empresa (Central)',
                    'access_scope': 'Administración Central y ERP',
                    'is_admin': True,
                })

        # Estaciones de gasolinera válidas
        gas_stations = [st for st in stations if st.id in default_map or 'e.s.' in (st.name or '').lower() or 'repsol' in (st.name or '').lower()]

        # 2. Consultar empleados de admin-platform en MariaDB
        emp_rows = []
        try:
            import pymysql
            import pymysql.cursors
            import json
            ICP = env['ir.config_parameter'].sudo()
            host = ICP.get_param('admin_platform.db_host', 'ddev-admin-platform-db')
            port = int(ICP.get_param('admin_platform.db_port', 3306))
            user = ICP.get_param('admin_platform.db_user', 'db')
            password = ICP.get_param('admin_platform.db_password', 'db')
            database = ICP.get_param('admin_platform.db_name', 'db')
            conn = pymysql.connect(
                host=host, port=port, user=user, password=password, database=database,
                charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor, connect_timeout=4
            )
            with conn.cursor() as cur:
                sql = """
                    SELECT DISTINCT e.id, e.virtus_codigo, e.nombre, e.apellidos, e.dni, e.email, e.gasolinera_codigo, e.gasolineras_codigos, e.foto
                    FROM empleados e
                    JOIN users u ON e.email = u.email
                    WHERE e.estado = 'Alta' AND (e.deleted_at IS NULL)
                    ORDER BY e.nombre, e.apellidos
                """
                cur.execute(sql)
                emp_rows = cur.fetchall()
            conn.close()
        except Exception as ex_db:
            _logger.warning("Error consultando empleados en MariaDB: %s", ex_db)

        # 3. Asignación y limitación de empleados POR EMPRESA
        color_palette = [
            'linear-gradient(135deg, #2563eb, #1d4ed8)',
            'linear-gradient(135deg, #059669, #047857)',
            'linear-gradient(135deg, #d97706, #b45309)',
            'linear-gradient(135deg, #7c3aed, #6d28d9)',
            'linear-gradient(135deg, #0891b2, #0e7490)',
            'linear-gradient(135deg, #db2777, #be185d)',
            'linear-gradient(135deg, #ea580c, #c2410c)',
            'linear-gradient(135deg, #4f46e5, #4338ca)',
        ]
        seen_emails = set(admin_emails)
        trieste_emp_count = 0
        utrecar_emp_count = 0

        for idx, r in enumerate(emp_rows):
            email = (r.get('email') or '').lower().strip()
            if not email or email in seen_emails:
                continue
            seen_emails.add(email)

            nombre = (r.get('nombre') or '').strip()
            apellidos = (r.get('apellidos') or '').strip()
            full_name = f"{nombre} {apellidos}".strip() or f"Empleado #{r['id']}"
            parts = full_name.split()
            initials = (parts[0][0] + (parts[1][0] if len(parts) > 1 else '')) if parts else 'EM'

            # Determinar asignación por empresa
            codes = []
            if r.get('gasolineras_codigos'):
                try:
                    raw = r['gasolineras_codigos']
                    if isinstance(raw, str):
                        codes = json.loads(raw)
                    elif isinstance(raw, list):
                        codes = raw
                except Exception:
                    pass
            if not codes and r.get('gasolinera_codigo'):
                try:
                    codes = [int(r['gasolinera_codigo'])]
                except Exception:
                    pass

            has_trieste_code = (5 in codes)
            has_utrecar_code = any(c in [1, 2, 3, 4] for c in codes)

            odoo_u = env['res.users'].sudo().search(['|', ('login', '=ilike', email), ('email', '=ilike', email)], limit=1)
            u_comps = odoo_u.company_ids if odoo_u else []

            is_trieste = (trieste_comp in u_comps) or has_trieste_code
            is_utrecar = (utrecar_comp in u_comps) or has_utrecar_code or (not codes and not u_comps)

            if is_trieste and not is_utrecar:
                company_label = 'A.R. Trieste'
                access_scope = 'Todas las Estaciones de A.R. Trieste (E.S. Repsol)'
                trieste_emp_count += 1
            elif is_utrecar and not is_trieste:
                company_label = 'Utrecar S.L.'
                access_scope = 'Todas las Estaciones de Utrecar (Vistalegre, Ronda Norte, Rodalabota, Atenas)'
                utrecar_emp_count += 1
            elif is_trieste and is_utrecar:
                company_label = 'Multi-Empresa: A.R. Trieste y Utrecar'
                access_scope = 'Todas las Estaciones del Grupo (A.R. Trieste y Utrecar)'
                trieste_emp_count += 1
                utrecar_emp_count += 1
            else:
                company_label = 'Utrecar S.L.'
                access_scope = 'Todas las Estaciones de Utrecar (Vistalegre, Ronda Norte, Rodalabota, Atenas)'
                utrecar_emp_count += 1

            emp_dict = {
                'id': f"emp_{r['id']}",
                'raw_id': r['id'],
                'full_name': full_name,
                'dni': r.get('dni') or '-',
                'email': r.get('email') or '',
                'login': r.get('email') or '',
                'puesto': 'Empleado',
                'odoo_role': 'Empleado',
                'initials': initials.upper(),
                'avatar_gradient': color_palette[idx % len(color_palette)],
                'company_name': company_label,
                'access_scope': access_scope,
                'is_admin': False,
            }
            all_users.append(emp_dict)

        # 4. Información de Estaciones de Servicio y sus IPs de VPN
        for st in gas_stations:
            vpn_ips = [x.strip() for x in (st.vpn_ip or '').split(',') if x.strip()]
            if not vpn_ips and st.id in default_map:
                vpn_ips = default_map[st.id]['vpn_ips']
            vpn_str = ", ".join(vpn_ips) if vpn_ips else 'Sin IP asignada'

            is_trieste_st = (st.company_id.id == 4 or 'trieste' in (st.company_id.name or '').lower())
            st_emp_count = trieste_emp_count if is_trieste_st else utrecar_emp_count

            has_controller = (st.id == 7)
            controller_status = {
                'active': has_controller,
                'label': 'Controlador MÁSTER Activo 24/7 (COM3 - SDES)' if has_controller else 'Pendiente de Controlador Físico',
                'badge_class': 'badge-success' if has_controller else 'badge-secondary',
                'mode': 'Wayne DART 9600 bps' if has_controller else 'Sin hardware conectado'
            }

            stations_data.append({
                'id': st.id,
                'name': st.name,
                'active': st.active,
                'company_name': st.company_id.name or 'UTRECAR S.L.',
                'company_id': st.company_id.id if st.company_id else False,
                'vpn_ips': vpn_ips,
                'vpn_ips_str': vpn_str,
                'has_tpv': True,
                'tpv_status': 'TPV Activo en Odoo',
                'admin_platform_code': st.get_admin_platform_code(),
                'controller_status': controller_status,
                'employees_count': st_emp_count,
                'allowed_access': f'Cualquier empleado con rol Empleado de {st.company_id.name} vía VPN {vpn_str}',
            })

        return {
            'status': 'success',
            'stations': stations_data,
            'all_users': all_users,
            'stats': {
                'total_stations': len(stations_data),
                'total_employees': len(all_users) - len(admin_emails),
                'total_users': len(all_users),
                'active_controllers': 1,
            }
        }


    @http.route('/pos_gas_station/sync_employees_now', type='json', auth='user', methods=['POST'], csrf=False)
    def sync_employees_now(self):
        """Dispara manualmente la sincronización de empleados de admin-platform y alta en res.users."""
        res = request.env['pos.config'].sudo().cron_sync_admin_platform_employees()
        return res

    # ==================== GESTIÓN DE PERSONAL Y ROLES MULTI-EMPRESA ====================
    @http.route('/pos_gas_station/employee_company_roles/data', type='json', auth='user', methods=['POST'], csrf=False)
    def get_employee_company_roles_data(self):
        """Devuelve el catálogo completo de personal con su rol y acceso específico por cada empresa."""
        env = request.env
        user = env.user
        forwarded_for = request.httprequest.headers.get('X-Forwarded-For')
        ip = forwarded_for.split(',')[0].strip() if forwarded_for else (request.httprequest.remote_addr or '').strip()
        vpn_admin = env['utrecar.vpn.admin'].sudo().search([('vpn_ip', '=', ip), ('active', '=', True)], limit=1)
        can_manage = bool(
            user._is_admin() or 
            user.has_group('base.group_system') or 
            user.has_group('pos_gas_station.group_utrecar_manage_staff') or 
            (vpn_admin and vpn_admin.can_manage_staff)
        )
        if not can_manage:
            return {'status': 'error', 'message': 'No tiene autorización para gestionar personal.'}

        User = env['res.users'].sudo()
        Company = env['res.company'].sudo()
        Role = env['utrecar.role'].sudo()
        Access = env['utrecar.employee.company.access'].sudo()
        role_emp = env.ref('pos_gas_station.role_employee', raise_if_not_found=False)

        companies = Company.search([], order='id')
        companies_list = [{'id': c.id, 'name': c.name} for c in companies]

        roles = Role.search([], order='sequence, id')
        roles_list = [{'id': r.id, 'name': r.name, 'code': r.code, 'color': r.color} for r in roles]

        # Consultar empleados de admin-platform en MariaDB
        ICP = env['ir.config_parameter'].sudo()
        host = ICP.get_param('admin_platform.db_host', 'ddev-admin-platform-db')
        port = int(ICP.get_param('admin_platform.db_port', 3306))
        user_db = ICP.get_param('admin_platform.db_user', 'db')
        pwd_db = ICP.get_param('admin_platform.db_password', 'db')
        dbname = ICP.get_param('admin_platform.db_name', 'db')

        color_palette = [
            'linear-gradient(135deg, #2563eb, #1d4ed8)',
            'linear-gradient(135deg, #059669, #047857)',
            'linear-gradient(135deg, #d97706, #b45309)',
            'linear-gradient(135deg, #7c3aed, #6d28d9)',
            'linear-gradient(135deg, #0891b2, #0e7490)',
            'linear-gradient(135deg, #db2777, #be185d)',
            'linear-gradient(135deg, #ea580c, #c2410c)',
            'linear-gradient(135deg, #4f46e5, #4338ca)',
        ]

        emp_meta = {}
        try:
            import pymysql
            import pymysql.cursors
            conn = pymysql.connect(
                host=host, port=port, user=user_db, password=pwd_db, database=dbname,
                charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor, connect_timeout=3
            )
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT e.id, e.nombre, e.apellidos, e.dni, e.email, e.virtus_codigo
                    FROM empleados e
                    WHERE e.estado = 'Alta' AND (e.deleted_at IS NULL)
                """)
                for r in cur.fetchall():
                    em = (r.get('email') or '').strip().lower()
                    if em:
                        emp_meta[em] = r
            conn.close()
        except Exception as ex:
            _logger.warning("Error consultando MariaDB: %s", ex)

        # Buscar usuarios activos de Odoo (excluyendo super admins del sistema 1 y 2)
        users = User.search([('id', 'not in', [1, 2]), ('active', '=', True)], order='name')

        users_data = []
        companies_stats = {c.id: 0 for c in companies}
        trieste_count = 0
        utrecar_count = 0
        multi_count = 0

        for idx, u in enumerate(users):
            if u.login in ['__system__', 'default', 'jarodriguezbonilla@gmail.com']:
                continue

            email_lower = (u.email or u.login or '').strip().lower()
            meta = emp_meta.get(email_lower, {})
            nombre = f"{meta.get('nombre', '')} {meta.get('apellidos', '')}".strip() if meta else u.name
            dni = meta.get('dni') or getattr(u, 'dni', '') or '-'
            code = meta.get('virtus_codigo') or str(meta.get('id', '')) or str(u.id)

            parts = nombre.split()
            initials = (parts[0][0] + (parts[1][0] if len(parts) > 1 else '')) if parts else 'US'

            # Construir accesos por empresa
            comp_access = {}
            active_comp_count = 0

            for comp in companies:
                # Buscar o inicializar registro en utrecar.employee.company.access
                acc = Access.search([('user_id', '=', u.id), ('company_id', '=', comp.id)], limit=1)
                if not acc:
                    # Inicializar en función de user.company_ids y user.utrecar_role_ids/utrecar_role_id
                    is_in_comp = comp.id in u.company_ids.ids
                    def_roles = u.utrecar_role_ids or (u.utrecar_role_id if u.utrecar_role_id else (role_emp if role_emp else Role))
                    acc = Access.create({
                        'user_id': u.id,
                        'company_id': comp.id,
                        'active_access': is_in_comp,
                        'role_id': def_roles[0].id if def_roles else False,
                        'role_ids': [(6, 0, def_roles.ids)] if def_roles else []
                    })
                elif not acc.role_ids and acc.role_id:
                    acc.write({'role_ids': [(4, acc.role_id.id)]})

                assigned_roles = acc.role_ids or (acc.role_id if acc.role_id else Role)
                roles_info = [{
                    'id': r.id,
                    'name': r.name,
                    'code': r.code,
                    'color': r.color or '#64748b'
                } for r in assigned_roles]

                comp_access[comp.id] = {
                    'active': acc.active_access,
                    'role_ids': assigned_roles.ids,
                    'roles': roles_info,
                    'role_names': [r.name for r in assigned_roles],
                    'role_codes': [(r.code or '').lower() for r in assigned_roles],
                    'role_id': assigned_roles[0].id if assigned_roles else False,
                    'role_name': ", ".join([r.name for r in assigned_roles]) if assigned_roles else 'Sin Rol',
                    'role_code': assigned_roles[0].code if assigned_roles else '',
                    'role_color': assigned_roles[0].color if assigned_roles else '#64748b',
                }
                if acc.active_access:
                    active_comp_count += 1
                    companies_stats[comp.id] = companies_stats.get(comp.id, 0) + 1
                    if comp.id == 4:
                        trieste_count += 1
                    elif comp.id == 1:
                        utrecar_count += 1

            if active_comp_count > 1:
                multi_count += 1

            users_data.append({
                'odoo_user_id': u.id,
                'name': nombre,
                'email': u.email or u.login,
                'login': u.login,
                'dni': dni,
                'code': code,
                'initials': initials.upper(),
                'avatar_gradient': color_palette[idx % len(color_palette)],
                'company_access': comp_access,
                'active_company_count': active_comp_count,
            })

        return {
            'status': 'success',
            'companies': companies_list,
            'roles': roles_list,
            'users': users_data,
            'stats': {
                'total_users': len(users_data),
                'company_counts': companies_stats,
                'trieste_count': trieste_count,
                'utrecar_count': utrecar_count,
                'multi_count': multi_count,
                'none_count': sum(1 for u in users_data if u['active_company_count'] == 0),
            }
        }

    @http.route('/pos_gas_station/employee_company_roles/update', type='json', auth='user', methods=['POST'], csrf=False)
    def update_employee_company_access(self, user_id, company_id, active=None, **kw):
        """Actualiza el acceso activo de un empleado en una empresa para el TPV."""
        env = request.env
        user = env.user
        forwarded_for = request.httprequest.headers.get('X-Forwarded-For')
        ip = forwarded_for.split(',')[0].strip() if forwarded_for else (request.httprequest.remote_addr or '').strip()
        vpn_admin = env['utrecar.vpn.admin'].sudo().search([('vpn_ip', '=', ip), ('active', '=', True)], limit=1)
        can_manage = bool(
            user._is_admin() or 
            user.has_group('base.group_system') or 
            user.has_group('pos_gas_station.group_utrecar_manage_staff') or 
            (vpn_admin and vpn_admin.can_manage_staff)
        )
        if not can_manage:
            return {'status': 'error', 'message': 'No tiene autorización para modificar personal.'}

        User = env['res.users'].sudo()
        Access = env['utrecar.employee.company.access'].sudo()
        Role = env['utrecar.role'].sudo()
        Company = env['res.company'].sudo()

        user = User.browse(int(user_id))
        if not user.exists():
            return {'status': 'error', 'message': 'Usuario no encontrado'}

        cid = int(company_id)
        comp = Company.browse(cid)
        role_emp = env.ref('pos_gas_station.role_employee', raise_if_not_found=False)
        if not role_emp:
            role_emp = Role.search([('code', '=', 'employee')], limit=1)

        acc = Access.search([('user_id', '=', user.id), ('company_id', '=', cid)], limit=1)
        if not acc:
            acc = Access.create({
                'user_id': user.id,
                'company_id': cid,
                'active_access': bool(active) if active is not None else True,
                'role_id': role_emp.id if role_emp else False,
                'role_ids': [(6, 0, [role_emp.id])] if role_emp else [],
            })

        new_active = bool(active) if active is not None else not acc.active_access
        vals = {'active_access': new_active}
        if role_emp and (not acc.role_ids or not acc.role_id):
            vals['role_id'] = role_emp.id
            vals['role_ids'] = [(6, 0, [role_emp.id])]
        acc.write(vals)

        # Actualizar asignación de empresas en el usuario
        if not new_active:
            if len(user.company_ids) > 1 and cid in user.company_ids.ids:
                try:
                    user.write({'company_ids': [(3, cid)]})
                except Exception:
                    pass
        else:
            try:
                user.write({'company_ids': [(4, cid)]})
            except Exception:
                pass

        # Asegurar asignación de rol EMPLEADO si tiene alguna empresa activa
        active_accesses = Access.search([
            ('user_id', '=', user.id),
            ('active_access', '=', True)
        ])
        if active_accesses and role_emp:
            user.write({
                'utrecar_role_ids': [(6, 0, [role_emp.id])],
                'utrecar_role_id': role_emp.id
            })
        elif not active_accesses:
            user.write({
                'utrecar_role_ids': [(5, 0, 0)],
                'utrecar_role_id': False
            })
        user._sync_utrecar_role_groups()

        comp_name = comp.name if comp.exists() else 'la empresa'
        action_text = "activado" if new_active else "desactivado"
        return {
            'status': 'success',
            'user_id': user.id,
            'company_id': cid,
            'active': new_active,
            'message': f'Acceso de {user.name} en {comp_name} {action_text} correctamente'
        }

    def _get_jose_telegram_credentials(self, env):
        """Obtiene el Bot Token de Telegram y el Chat ID exclusivo de José desde admin-platform o parámetros."""
        ICP = env['ir.config_parameter'].sudo()
        bot_token = ICP.get_param('utrecar.telegram_bot_token', '8637497198:AAGJWp6cwDBu0CeTLkDVd-0nanl1ZtXFbjg')
        jose_chat_id = ICP.get_param('utrecar.telegram_jose_chat_id', '5914920849')

        # Sincronizar el telegram_chat_id del usuario de José desde admin-platform (MariaDB) si está disponible
        try:
            import pymysql
            import pymysql.cursors
            host = ICP.get_param('admin_platform.db_host', 'ddev-admin-platform-db')
            port = int(ICP.get_param('admin_platform.db_port', 3306))
            user_db = ICP.get_param('admin_platform.db_user', 'db')
            pwd_db = ICP.get_param('admin_platform.db_password', 'db')
            dbname = ICP.get_param('admin_platform.db_name', 'db')

            conn = pymysql.connect(
                host=host, port=port, user=user_db, password=pwd_db, database=dbname,
                charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor, connect_timeout=2
            )
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT telegram_chat_id
                    FROM users
                    WHERE email = 'jarodriguezbonilla@gmail.com'
                      AND telegram_chat_id IS NOT NULL
                      AND telegram_chat_id != ''
                    LIMIT 1
                """)
                row = cur.fetchone()
                if row and row.get('telegram_chat_id'):
                    jose_chat_id = str(row['telegram_chat_id']).strip()
            conn.close()
        except Exception as e:
            _logger.debug("Usando Chat ID por defecto de José para Telegram: %s", e)

        return bot_token, jose_chat_id

    @http.route('/pos_gas_station/centinela_alert', type='http', auth='public', methods=['POST', 'GET'], csrf=False)
    def centinela_telegram_alert(self, **kw):
        """Pasarela en Odoo para enviar alertas del Centinela (TPV 2 Ronda Norte) exclusivamente al Telegram de José."""
        try:
            import urllib.request
            data = {}
            if request.httprequest.data:
                try:
                    data = json.loads(request.httprequest.data.decode('utf-8'))
                except Exception:
                    data = {}
            text = data.get('text') or kw.get('text') or ''
            if not text:
                return request.make_json_response({'status': 'error', 'message': 'Mensaje vacío'}, status=400)

            bot_token, jose_chat_id = self._get_jose_telegram_credentials(request.env)
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            payload = json.dumps({
                'chat_id': jose_chat_id,
                'text': text,
            }).encode('utf-8')

            req = urllib.request.Request(
                url,
                data=payload,
                headers={'Content-Type': 'application/json; charset=utf-8'},
                method='POST'
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                resp_body = json.loads(resp.read().decode('utf-8'))

            return request.make_json_response({
                'status': 'success',
                'chat_id': jose_chat_id,
                'telegram_ok': resp_body.get('ok', False)
            })
        except Exception as e:
            _logger.exception("Error enviando alerta de Centinela a Telegram: %s", e)
            return request.make_json_response({'status': 'error', 'message': str(e)}, status=500)

