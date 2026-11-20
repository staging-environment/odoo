# -*- coding: utf-8 -*-
"""
Cola de impresión directa del TPV.

El navegador no puede elegir impresora de Windows, así que el TPV envía aquí cada
documento con la impresora asignada. Odoo lo convierte en:
  - ESC/POS raster (bytes listos para la térmica, con corte de papel), o
  - PDF (A4 / documentos),
y lo deja en cola como `ir.attachment` (res_model = PRINT_JOB_MODEL, res_id = config_id).
El agente del PC de pista (scripts/agente_impresoras_pista.py) recoge los trabajos
pendientes, los imprime en la impresora indicada y marca el resultado.
"""
import base64
import io
import json
import logging
import os
import re
import subprocess
import tempfile
import time

from odoo import http
from odoo.http import request
from odoo.tools.misc import find_in_path

_logger = logging.getLogger(__name__)

PRINT_JOB_MODEL = 'pos_gas_station.print_job'
MIME_ESCPOS = 'application/vnd.escpos'
MIME_PDF = 'application/pdf'
THERMAL_DOTS = 576          # ancho imprimible de una térmica de 80 mm a 203 ppp
THERMAL_ZOOM = 1.5          # 576 / 1.5 = 384 px CSS de ancho de maquetación
AGENT_ALIVE_SECONDS = 120   # el agente escribe latido cada ~30 s
JOB_KEEP_SECONDS = 3600     # trabajos terminados o con error se purgan pasada 1 h
REPORT_URL_RE = re.compile(r'^/report/pdf/([\w.]+)/([\d,]+)')


# ---------------------------------------------------------------- conversión
_FLEX_RE = re.compile(r'display\s*:\s*flex\b', re.I)
_SPACE_BETWEEN_RE = re.compile(r'justify-content\s*:\s*space-between', re.I)
_CENTER_RE = re.compile(r'justify-content\s*:\s*center', re.I)
_CSS_RULE_RE = re.compile(r'([^{}]+)\{([^{}]*)\}')
_INLINE_STYLE_RE = re.compile(r'style="([^"]*)"', re.I)
_FLEX_COMPAT_CSS = ('<style>[data-flexrow]{overflow:hidden}'
                    '[data-flexrow]>*:last-child{float:right}</style>')


def _flex_body(body):
    """Traduce un bloque de declaraciones con flex a bloque clásico."""
    if _SPACE_BETWEEN_RE.search(body):
        return _FLEX_RE.sub('display:block', body), True
    if _CENTER_RE.search(body):
        return _FLEX_RE.sub('display:block;text-align:center', body), False
    return _FLEX_RE.sub('display:block', body), False


def _strip_scripts(html):
    """Quita scripts y adapta el CSS al WebKit antiguo de wkhtmltox (no soporta flexbox):
    las filas `display:flex; justify-content:space-between` pasan a bloque con el último
    elemento flotando a la derecha, que da el mismo resultado visual en los tickets."""
    html = re.sub(r'<script\b.*?</script>', '', html or '', flags=re.S | re.I)

    def fix_style_block(m):
        extra = []

        def fix_rule(r):
            selector, body = r.group(1), r.group(2)
            if not _FLEX_RE.search(body) or selector.strip().startswith('@'):
                return r.group(0)
            body, row = _flex_body(body)
            if row:
                extra.append(','.join(s.strip() + '>*:last-child' for s in selector.split(',')) + '{float:right}')
                extra.append(selector.strip() + '{overflow:hidden}')
            return '%s{%s}' % (selector, body)

        css = _CSS_RULE_RE.sub(fix_rule, m.group(2))
        return m.group(1) + css + '\n' + '\n'.join(extra) + m.group(3)

    html = re.sub(r'(<style[^>]*>)(.*?)(</style>)', fix_style_block, html, flags=re.S | re.I)

    def fix_inline(m):
        style = m.group(1)
        if not _FLEX_RE.search(style):
            return m.group(0)
        style, row = _flex_body(style)
        return ('data-flexrow="1" ' if row else '') + 'style="%s"' % style

    html = _INLINE_STYLE_RE.sub(fix_inline, html)
    if re.search(r'</head>', html, re.I):
        html = re.sub(r'</head>', _FLEX_COMPAT_CSS + '</head>', html, count=1, flags=re.I)
    else:
        html = _FLEX_COMPAT_CSS + html
    return html


def _run(cmd, timeout=60):
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
    if proc.returncode not in (0, 1):  # wkhtmltox devuelve 1 con avisos menores
        raise RuntimeError(proc.stderr.decode(errors='replace')[-500:])


def _html_to_png(html):
    exe = find_in_path('wkhtmltoimage')
    with tempfile.TemporaryDirectory() as tmp:
        src, out = os.path.join(tmp, 'doc.html'), os.path.join(tmp, 'doc.png')
        with open(src, 'w', encoding='utf-8') as fh:
            fh.write(_strip_scripts(html))
        _run([exe, '--quiet', '--disable-javascript', '--encoding', 'utf-8',
              '--width', str(THERMAL_DOTS), '--zoom', str(THERMAL_ZOOM), '--format', 'png', src, out])
        with open(out, 'rb') as fh:
            return fh.read()


def _html_to_pdf(html, page_size='A4'):
    exe = find_in_path('wkhtmltopdf')
    with tempfile.TemporaryDirectory() as tmp:
        src, out = os.path.join(tmp, 'doc.html'), os.path.join(tmp, 'doc.pdf')
        with open(src, 'w', encoding='utf-8') as fh:
            fh.write(_strip_scripts(html))
        margin = '7mm' if page_size == 'A5' else '10mm'
        _run([exe, '--quiet', '--disable-javascript', '--encoding', 'utf-8', '--page-size', page_size,
              '--margin-top', margin, '--margin-bottom', margin, '--margin-left', margin,
              '--margin-right', margin, src, out])
        with open(out, 'rb') as fh:
            return fh.read()


def _image_to_escpos(image_bytes):
    """Imagen -> comandos ESC/POS (GS v 0) a 576 puntos, con avance y corte."""
    from PIL import Image, ImageOps

    img = Image.open(io.BytesIO(image_bytes))
    if img.mode in ('RGBA', 'LA', 'P'):
        img = img.convert('RGBA')
        bg = Image.new('RGBA', img.size, (255, 255, 255, 255))
        bg.alpha_composite(img)
        img = bg
    img = img.convert('L')
    # Recorta el margen blanco inferior/lateral para no gastar papel
    bbox = ImageOps.invert(img).getbbox()
    if bbox:
        img = img.crop((0, 0, img.width, min(img.height, bbox[3] + 8)))
    if img.width != THERMAL_DOTS:
        ratio = THERMAL_DOTS / float(img.width)
        img = img.resize((THERMAL_DOTS, max(1, int(img.height * ratio))), Image.LANCZOS)
    img = img.point(lambda p: 255 if p > 160 else 0).convert('1')
    # PIL: 1 = blanco; ESC/POS: 1 = punto negro
    width_bytes = (img.width + 7) // 8
    raw = ImageOps.invert(img.convert('L')).convert('1').tobytes()

    out = bytearray(b'\x1b@')  # reset
    # Bloques de 24 filas: algunas térmicas (Rongta/appPOS80) leen mal alturas >= 256
    # (solo el byte bajo) y toman la imagen como comandos, quedándose bloqueadas.
    band = 24
    for top in range(0, img.height, band):
        rows = min(band, img.height - top)
        chunk = raw[top * width_bytes:(top + rows) * width_bytes]
        out += b'\x1dv0\x00' + bytes([width_bytes % 256, width_bytes // 256, rows % 256, rows // 256]) + chunk
    out += b'\n' * 4 + b'\x1dV\x42\x00'  # avance + corte parcial
    return bytes(out)


def _report_pdf(report_url):
    m = REPORT_URL_RE.match(report_url or '')
    if not m:
        raise ValueError('URL de informe no reconocida: %s' % report_url)
    report_name, ids = m.group(1), [int(i) for i in m.group(2).split(',')]
    pdf, _ = request.env['ir.actions.report'].sudo()._render_qweb_pdf(report_name, ids)
    return pdf


# ---------------------------------------------------------------- endpoints
class PosPrintQueue(http.Controller):

    def _param(self, key, default=None):
        return request.env['ir.config_parameter'].sudo().get_param(key, default)

    def _attachments(self):
        return request.env['ir.attachment'].sudo()

    def _purge_old(self, config_id):
        cutoff = time.time() - JOB_KEEP_SECONDS
        old = self._attachments().search([('res_model', '=', PRINT_JOB_MODEL), ('res_id', '=', config_id)])
        stale = old.filtered(lambda a: (json.loads(a.description or '{}').get('created') or 0) < cutoff)
        stale.unlink()

    @http.route('/pos_gas_station/print/status', type='json', auth='user', methods=['POST'], csrf=False)
    def print_status(self, config_id=None, **kw):
        cfg = int(config_id or 7)
        last_seen = float(self._param(f'pos_gas_station.print_agent_seen_{cfg}') or 0)
        try:
            printers = json.loads(self._param(f'pos_gas_station.system_printers_{cfg}') or '{}')
        except Exception:
            printers = {}
        return {
            'agent_alive': (time.time() - last_seen) < AGENT_ALIVE_SECONDS,
            'pdf_ready': bool(printers.get('pdf_ready')),
            'last_seen': last_seen,
        }

    @http.route('/pos_gas_station/print/submit', type='json', auth='user', methods=['POST'], csrf=False)
    def print_submit(self, config_id=None, printer_name=None, format='thermal_80', copies=1,
                     doc_type='ticket', title=None, html=None, image=None, report_url=None, tray=None, **kw):
        cfg = int(config_id or 7)
        if not printer_name:
            return {'status': 'error', 'message': 'No hay impresora asignada a este documento.'}
        copies = max(1, min(int(copies or 1), 5))
        thermal = format not in ('a4', 'a5')
        page_size = 'A5' if format == 'a5' else 'A4'
        try:
            if report_url:
                payload, mime = _report_pdf(report_url), MIME_PDF
            elif image:
                img = base64.b64decode(image)
                if thermal:
                    payload, mime = _image_to_escpos(img), MIME_ESCPOS
                else:
                    from PIL import Image
                    buf = io.BytesIO()
                    Image.open(io.BytesIO(img)).convert('RGB').save(buf, format='PDF')
                    payload, mime = buf.getvalue(), MIME_PDF
            elif html:
                if thermal:
                    payload, mime = _image_to_escpos(_html_to_png(html)), MIME_ESCPOS
                else:
                    payload, mime = _html_to_pdf(html, page_size), MIME_PDF
            else:
                return {'status': 'error', 'message': 'Documento vacío.'}
        except Exception as e:
            _logger.exception('Error preparando trabajo de impresión')
            return {'status': 'error', 'message': 'No se pudo preparar el documento: %s' % e}

        if mime == MIME_ESCPOS and copies > 1:
            payload, copies = payload * copies, 1

        meta = {
            'state': 'pending',
            'printer': printer_name,
            'copies': copies,
            'doc_type': doc_type,
            'tray': (tray or '') if mime == MIME_PDF else '',
            'paper': page_size if mime == MIME_PDF else '',
            'created': time.time(),
            'user': request.env.user.name,
        }
        att = self._attachments().create({
            'name': (title or doc_type or 'documento')[:120],
            'res_model': PRINT_JOB_MODEL,
            'res_id': cfg,
            'type': 'binary',
            'raw': payload,
            'mimetype': mime,
            'description': json.dumps(meta, ensure_ascii=False),
        })
        self._purge_old(cfg)
        return {'status': 'queued', 'job_id': att.id}

    @http.route('/pos_gas_station/print/job_status', type='json', auth='user', methods=['POST'], csrf=False)
    def print_job_status(self, job_id=None, **kw):
        att = self._attachments().browse(int(job_id or 0)).exists()
        if not att or att.res_model != PRINT_JOB_MODEL:
            return {'state': 'done'}  # el agente borra los trabajos impresos
        meta = json.loads(att.description or '{}')
        return {'state': meta.get('state', 'pending'), 'message': meta.get('message', '')}
