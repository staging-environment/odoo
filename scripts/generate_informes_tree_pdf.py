#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generador del PDF ejecutivo del Árbol de Navegación del Módulo de Informes
para Odoo 17 ERP - UTRECAR
"""

import os
import sys
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
)
from reportlab.pdfgen import canvas
from reportlab.graphics.shapes import Drawing, Rect, String, Line, Group

class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super(NumberedCanvas, self).__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_header_footer(num_pages)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def draw_header_footer(self, page_count):
        self.saveState()
        self.setFont("Helvetica-Bold", 8)
        self.setFillColor(colors.HexColor("#475569"))
        
        # Header (Pages > 1)
        if self._pageNumber > 1:
            self.drawString(54, 802, "ÁRBOL DE NAVEGACIÓN Y ARQUITECTURA DE INFORMES - ODOO 17 ERP")
            self.drawRightString(541, 802, "GRUPO UTRECAR - DIRECCIÓN GENERAL")
            self.setStrokeColor(colors.HexColor("#CBD5E1"))
            self.setLineWidth(0.75)
            self.line(54, 794, 541, 794)
            
        # Footer (All pages)
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748B"))
        page_text = f"Página {self._pageNumber} de {page_count}"
        self.drawRightString(541, 32, page_text)
        self.drawString(54, 32, "DOCUMENTO EJECUTIVO DE ARQUITECTURA FUNCIONAL - CONFIDENCIAL")
        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.setLineWidth(0.75)
        self.line(54, 44, 541, 44)
        self.restoreState()

def create_tree_drawing():
    """Genera un diagrama vectorial nítido con el árbol de navegación completo."""
    dwg_w = 487
    dwg_h = 240
    d = Drawing(dwg_w, dwg_h)
    
    # Fondo con borde sutil
    d.add(Rect(0, 0, dwg_w, dwg_h, rx=6, ry=6, fillColor=colors.HexColor("#F8FAFC"), strokeColor=colors.HexColor("#E2E8F0"), strokeWidth=1))
    
    # -------------------------------------------------------------
    # NODO RAÍZ: INFORMES
    # -------------------------------------------------------------
    rx, ry, rw, rh = 183, 192, 120, 32
    d.add(Rect(rx, ry, rw, rh, rx=5, ry=5, fillColor=colors.HexColor("#1E3A8A"), strokeColor=colors.HexColor("#1D4ED8"), strokeWidth=2))
    d.add(String(rx + rw/2, ry + 11, "INFORMES", fontName="Helvetica-Bold", fontSize=12, textAnchor="middle", fillColor=colors.white))
    
    # -------------------------------------------------------------
    # NODOS NIVEL 1 (6 ramas)
    # Distribuidas en 6 columnas:
    # ALMACÉN, COMPRAS, VENTAS, FICHEROS, TURNOS, COBROS
    # -------------------------------------------------------------
    branches = [
        {"name": "ALMACÉN",  "color": "#0284C7", "border": "#0369A1"},
        {"name": "COMPRAS",  "color": "#0D9488", "border": "#0F766E"},
        {"name": "VENTAS",   "color": "#16A34A", "border": "#15803D"},
        {"name": "FICHEROS", "color": "#6366F1", "border": "#4F46E5"},
        {"name": "TURNOS",   "color": "#D97706", "border": "#B45309"},
        {"name": "COBROS",   "color": "#EA580C", "border": "#C2410C"},
    ]
    
    box_w = 72
    box_h = 26
    start_x = 12
    gap_x = (dwg_w - 24 - (6 * box_w)) / 5
    level1_y = 120
    
    # Línea horizontal del bus principal
    bus_y = 165
    d.add(Line(rx + rw/2, ry, rx + rw/2, bus_y, strokeColor=colors.HexColor("#94A3B8"), strokeWidth=1.5))
    first_cx = start_x + box_w/2
    last_cx = start_x + 5 * (box_w + gap_x) + box_w/2
    d.add(Line(first_cx, bus_y, last_cx, bus_y, strokeColor=colors.HexColor("#94A3B8"), strokeWidth=1.5))
    
    col_centers = []
    for i, b in enumerate(branches):
        bx = start_x + i * (box_w + gap_x)
        by = level1_y
        cx = bx + box_w/2
        col_centers.append(cx)
        
        # Conector vertical desde el bus
        d.add(Line(cx, bus_y, cx, by + box_h, strokeColor=colors.HexColor("#94A3B8"), strokeWidth=1.5))
        
        # Caja de Nivel 1
        d.add(Rect(bx, by, box_w, box_h, rx=4, ry=4, fillColor=colors.HexColor(b["color"]), strokeColor=colors.HexColor(b["border"]), strokeWidth=1.5))
        d.add(String(cx, by + 8.5, b["name"], fontName="Helvetica-Bold", fontSize=9, textAnchor="middle", fillColor=colors.white))
    
    # -------------------------------------------------------------
    # SUB-NODOS NIVEL 2
    # ALMACÉN (Columna 0) -> DOCUMENTOS, SUMINISTROS
    # COMPRAS (Columna 1) -> DOCUMENTOS
    # -------------------------------------------------------------
    sub_w = 72
    sub_h = 22
    alm_cx = col_centers[0]
    com_cx = col_centers[1]
    
    # ALMACÉN -> Conector vertical
    d.add(Line(alm_cx, level1_y, alm_cx, 75, strokeColor=colors.HexColor("#0284C7"), strokeWidth=1.2))
    
    # Sub-nodo Almacén 1: DOCUMENTOS (y=56)
    sub_alm_y1 = 56
    d.add(Line(alm_cx, sub_alm_y1 + sub_h/2, start_x + sub_w, sub_alm_y1 + sub_h/2, strokeColor=colors.HexColor("#0284C7"), strokeWidth=1.2))
    d.add(Rect(start_x, sub_alm_y1, sub_w, sub_h, rx=3, ry=3, fillColor=colors.HexColor("#E0F2FE"), strokeColor=colors.HexColor("#0284C7"), strokeWidth=1.2))
    d.add(String(start_x + sub_w/2, sub_alm_y1 + 7, "DOCUMENTOS", fontName="Helvetica-Bold", fontSize=7.5, textAnchor="middle", fillColor=colors.HexColor("#0369A1")))
    
    # Sub-nodo Almacén 2: SUMINISTROS (y=24)
    sub_alm_y2 = 24
    d.add(Line(alm_cx, sub_alm_y2 + sub_h/2, start_x + sub_w, sub_alm_y2 + sub_h/2, strokeColor=colors.HexColor("#0284C7"), strokeWidth=1.2))
    d.add(Rect(start_x, sub_alm_y2, sub_w, sub_h, rx=3, ry=3, fillColor=colors.HexColor("#E0F2FE"), strokeColor=colors.HexColor("#0284C7"), strokeWidth=1.2))
    d.add(String(start_x + sub_w/2, sub_alm_y2 + 7, "SUMINISTROS", fontName="Helvetica-Bold", fontSize=7.5, textAnchor="middle", fillColor=colors.HexColor("#0369A1")))
    
    # COMPRAS -> Conector vertical
    com_bx = start_x + 1 * (box_w + gap_x)
    sub_com_y1 = 56
    d.add(Line(com_cx, level1_y, com_cx, sub_com_y1 + sub_h/2, strokeColor=colors.HexColor("#0D9488"), strokeWidth=1.2))
    d.add(Rect(com_bx, sub_com_y1, sub_w, sub_h, rx=3, ry=3, fillColor=colors.HexColor("#CCFBF1"), strokeColor=colors.HexColor("#0D9488"), strokeWidth=1.2))
    d.add(String(com_bx + sub_w/2, sub_com_y1 + 7, "DOCUMENTOS", fontName="Helvetica-Bold", fontSize=7.5, textAnchor="middle", fillColor=colors.HexColor("#0F766E")))
    
    # Indicadores discretos de expansión futura en las demás columnas
    for i in range(2, 6):
        cx = col_centers[i]
        d.add(Line(cx, level1_y, cx, level1_y - 12, strokeColor=colors.HexColor("#94A3B8"), strokeWidth=1, strokeDashArray=[2, 2]))
        d.add(String(cx, level1_y - 22, "+ Detalle", fontName="Helvetica-Oblique", fontSize=7, textAnchor="middle", fillColor=colors.HexColor("#94A3B8")))

    return d

def generate_pdf(output_path):
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54
    )
    
    styles = getSampleStyleSheet()
    
    # Estilos tipográficos refinados
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=20,
        leading=24,
        textColor=colors.HexColor('#0F172A'),
        spaceAfter=4
    )
    
    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=11,
        leading=15,
        textColor=colors.HexColor('#2563EB'),
        spaceAfter=14
    )
    
    meta_style = ParagraphStyle(
        'DocMeta',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor('#475569')
    )
    
    h1_style = ParagraphStyle(
        'SectionH1',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=13,
        leading=17,
        textColor=colors.HexColor('#1E293B'),
        spaceBefore=14,
        spaceAfter=8,
        keepWithNext=True
    )
    
    h2_style = ParagraphStyle(
        'SectionH2',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10.5,
        leading=14,
        textColor=colors.HexColor('#334155'),
        spaceBefore=10,
        spaceAfter=5,
        keepWithNext=True
    )
    
    body_style = ParagraphStyle(
        'BodyDark',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=colors.HexColor('#334155'),
        spaceAfter=8
    )
    
    callout_style = ParagraphStyle(
        'CalloutText',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=12.5,
        textColor=colors.HexColor('#1E3A8A')
    )
    
    table_hdr = ParagraphStyle(
        'TableHdr',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=10.5,
        textColor=colors.white
    )
    
    table_cell = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=11,
        textColor=colors.HexColor('#1E293B')
    )
    
    table_cell_bold = ParagraphStyle(
        'TableCellBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=11,
        textColor=colors.HexColor('#0F172A')
    )

    story = []
    
    # -------------------------------------------------------------------------
    # CABECERA EJECUTIVA / PORTADA
    # -------------------------------------------------------------------------
    story.append(Paragraph("ARQUITECTURA DE INFORMES Y REPORTING", title_style))
    story.append(Paragraph("Árbol de Navegación Oficial & Mapeo de Módulos Operativos (Odoo 17 ERP)", subtitle_style))
    
    # Tabla de Metadatos del Documento
    meta_data = [
        [
            Paragraph("<b>Empresa:</b> GRUPO UTRECAR S.L.", meta_style),
            Paragraph("<b>Fecha:</b> 16 de Noviembre de 2026", meta_style),
            Paragraph("<b>Versión:</b> 1.0 (Oficial)", meta_style)
        ],
        [
            Paragraph("<b>Destinatario:</b> Dirección General / Jefatura", meta_style),
            Paragraph("<b>Entorno:</b> Odoo 17 ERP Cloud", meta_style),
            Paragraph("<b>Estado:</b> Aprobado para Ejecución", meta_style)
        ]
    ]
    t_meta = Table(meta_data, colWidths=[162, 162, 163])
    t_meta.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F1F5F9')),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#CBD5E1')),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E2E8F0')),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(t_meta)
    story.append(Spacer(1, 14))
    
    # -------------------------------------------------------------------------
    # GRÁFICA VECTORIAL DEL ÁRBOL DE NAVEGACIÓN
    # -------------------------------------------------------------------------
    story.append(Paragraph("1. Representación Visual del Árbol de Navegación", h1_style))
    story.append(Paragraph(
        "A continuación se presenta el esquema estructural jerárquico del menú <b>INFORMES</b>. "
        "Este diseño garantiza un acceso centralizado, intuitivo y desacoplado a todos los datos "
        "analíticos, fiscales, de tanques y de pista de las 5 estaciones de servicio del grupo.",
        body_style
    ))
    
    story.append(create_tree_drawing())
    story.append(Spacer(1, 14))
    
    # Cuadro informativo destacado
    callout_data = [[
        Paragraph(
            "<b>Nota de Diseño Estratégico:</b> "
            "El árbol se ha estructurado en 6 ramas cardinales de primer nivel que cubren la totalidad del flujo del negocio "
            "de estaciones de servicio: <b>Almacén</b> (stocks/mermas de combustible), <b>Compras</b> (cisternas CLH/Repsol), "
            "<b>Ventas</b> (liquidaciones y márgenes), <b>Ficheros</b> (maestros exportables), <b>Turnos</b> (cierres de caja y arqueos) "
            "y <b>Cobros</b> (deuda de clientes a crédito y conciliación bancaria).",
            callout_style
        )
    ]]
    t_callout = Table(callout_data, colWidths=[487])
    t_callout.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#EFF6FF')),
        ('BOX', (0,0), (-1,-1), 1.5, colors.HexColor('#3B82F6')),
        ('TOPPADDING', (0,0), (-1,-1), 7),
        ('BOTTOMPADDING', (0,0), (-1,-1), 7),
        ('LEFTPADDING', (0,0), (-1,-1), 10),
        ('RIGHTPADDING', (0,0), (-1,-1), 10),
    ]))
    story.append(t_callout)
    story.append(Spacer(1, 12))
    
    # -------------------------------------------------------------------------
    # DETALLE DE SECCIONES Y ESPECIFICACIÓN FUNCIONAL
    # -------------------------------------------------------------------------
    story.append(Paragraph("2. Desglose Operativo y Modelos de Datos en Odoo 17", h1_style))
    story.append(Paragraph(
        "Cada nodo del árbol responde a un objetivo operativo concreto e interactúa de forma nativa con los "
        "módulos de Odoo 17 ERP (Inventario, Compras, Ventas, TPV y Contabilidad):",
        body_style
    ))
    
    module_table_data = [
        [
            Paragraph("ÁREA / NODO", table_hdr),
            Paragraph("SUBMENÚS", table_hdr),
            Paragraph("DESCRIPCIÓN Y OBJETIVO DE NEGOCIO", table_hdr),
            Paragraph("MODELOS ODOO", table_hdr)
        ],
        [
            Paragraph("<b>📦 ALMACÉN</b>", table_cell_bold),
            Paragraph("• DOCUMENTOS<br/>• SUMINISTROS", table_cell),
            Paragraph(
                "<b>Documentos:</b> Albaranes de entrada de cisterna, regularizaciones de tanques, aforos de varilla y mermas por temperatura.<br/>"
                "<b>Suministros:</b> Control metrológico, pruebas de probeta a 10L, calibraciones y volumen despachado por cada surtidor y manguera.",
                table_cell
            ),
            Paragraph("<code>stock.picking</code><br/><code>stock.quant</code><br/><code>stock.move</code>", table_cell)
        ],
        [
            Paragraph("<b>🛒 COMPRAS</b>", table_cell_bold),
            Paragraph("• DOCUMENTOS", table_cell),
            Paragraph(
                "Gestión y fiscalización de facturas de compra de carburantes (Exolum/CLH, Repsol, Cepsa) y mercancía de tienda. "
                "Control de precios de coste de adquisición y conciliación de albaranes de entrega.",
                table_cell
            ),
            Paragraph("<code>purchase.order</code><br/><code>account.move (in)</code>", table_cell)
        ],
        [
            Paragraph("<b>📈 VENTAS</b>", table_cell_bold),
            Paragraph("<i>(Próxima Fase)</i>", table_cell),
            Paragraph(
                "Análisis de ingresos por estación de servicio, volumen de litros por producto (Gasóleo A, SP95, Plus, B), "
                "márgenes comerciales brutos y comparativas temporales por franja horaria y turno.",
                table_cell
            ),
            Paragraph("<code>pos.order</code><br/><code>account.move (out)</code><br/><code>sale.report</code>", table_cell)
        ],
        [
            Paragraph("<b>📁 FICHEROS</b>", table_cell_bold),
            Paragraph("<i>(Próxima Fase)</i>", table_cell),
            Paragraph(
                "Maestros y listados oficiales exportables: Directorio de clientes con crédito abierto, catálogo de vehículos/matrículas, "
                "tarifas aplicables y numeración de surtidores de pista.",
                table_cell
            ),
            Paragraph("<code>res.partner</code><br/><code>res.partner.vehicle</code><br/><code>product.product</code>", table_cell)
        ],
        [
            Paragraph("<b>⏱️ TURNOS</b>", table_cell_bold),
            Paragraph("<i>(Próxima Fase)</i>", table_cell),
            Paragraph(
                "Histórico oficial de cierres de turno (`pos.session`), informes de arqueo de caja en PDF, incidencias de caja "
                "(entradas y retiradas de efectivo), sobrantes de prepago devueltos y cuadre fiscal por expendedor.",
                table_cell
            ),
            Paragraph("<code>pos.session</code><br/><code>account.bank.statement</code>", table_cell)
        ],
        [
            Paragraph("<b>💶 COBROS</b>", table_cell_bold),
            Paragraph("<i>(Próxima Fase)</i>", table_cell),
            Paragraph(
                "Control de deuda viva de clientes de cuenta mensual/crédito, seguimiento de albaranes pendientes de facturar, "
                "pagos en tarjeta por datáfono y conciliación de movimientos de caja fuerte.",
                table_cell
            ),
            Paragraph("<code>account.payment</code><br/><code>pos.payment</code>", table_cell)
        ],
    ]
    
    t_modules = Table(module_table_data, colWidths=[80, 85, 232, 90])
    t_modules.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0F172A')),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#CBD5E1')),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E2E8F0')),
        ('TOPPADDING', (0,0), (-1,-1), 4.5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4.5),
        ('LEFTPADDING', (0,0), (-1,-1), 5),
        ('RIGHTPADDING', (0,0), (-1,-1), 5),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#F8FAFC')]),
    ]))
    
    story.append(t_modules)
    story.append(Spacer(1, 14))
    
    # -------------------------------------------------------------------------
    # MATRIZ DE PERMISOS Y ROLES DE ACCESO
    # -------------------------------------------------------------------------
    story.append(Paragraph("3. Matriz de Permisos y Segregación de Acceso", h1_style))
    story.append(Paragraph(
        "Para garantizar la seguridad y confidencialidad de la información financiera y de existencias, "
        "el acceso a los informes se restringe según el perfil del usuario:",
        body_style
    ))
    
    perm_data = [
        [
            Paragraph("PERFIL / ROL", table_hdr),
            Paragraph("ALMACÉN", table_hdr),
            Paragraph("COMPRAS", table_hdr),
            Paragraph("VENTAS", table_hdr),
            Paragraph("FICHEROS", table_hdr),
            Paragraph("TURNOS", table_hdr),
            Paragraph("COBROS", table_hdr)
        ],
        [
            Paragraph("<b>Dirección General / CEO</b>", table_cell_bold),
            Paragraph("✓ Total", table_cell),
            Paragraph("✓ Total", table_cell),
            Paragraph("✓ Total", table_cell),
            Paragraph("✓ Total", table_cell),
            Paragraph("✓ Total", table_cell),
            Paragraph("✓ Total", table_cell)
        ],
        [
            Paragraph("<b>Administración y RRHH</b>", table_cell_bold),
            Paragraph("✓ Total", table_cell),
            Paragraph("✓ Total", table_cell),
            Paragraph("✓ Total", table_cell),
            Paragraph("✓ Total", table_cell),
            Paragraph("✓ Total", table_cell),
            Paragraph("✓ Total", table_cell)
        ],
        [
            Paragraph("<b>Encargado de Estación</b>", table_cell_bold),
            Paragraph("✓ Su Estación", table_cell),
            Paragraph("Lectura", table_cell),
            Paragraph("✓ Su Estación", table_cell),
            Paragraph("Lectura", table_cell),
            Paragraph("✓ Su Estación", table_cell),
            Paragraph("✓ Su Estación", table_cell)
        ],
        [
            Paragraph("<b>Expendedor de Pista</b>", table_cell_bold),
            Paragraph("✗ Sin acceso", table_cell),
            Paragraph("✗ Sin acceso", table_cell),
            Paragraph("✗ Sin acceso", table_cell),
            Paragraph("✗ Sin acceso", table_cell),
            Paragraph("Solo su turno", table_cell),
            Paragraph("✗ Sin acceso", table_cell)
        ]
    ]
    t_perm = Table(perm_data, colWidths=[127, 60, 60, 60, 60, 60, 60])
    t_perm.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1E293B')),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#CBD5E1')),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E2E8F0')),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING', (0,0), (-1,-1), 5),
        ('RIGHTPADDING', (0,0), (-1,-1), 5),
        ('ALIGN', (1,0), (-1,-1), 'CENTER'),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#F8FAFC')]),
    ]))
    story.append(t_perm)
    story.append(Spacer(1, 14))
    
    # -------------------------------------------------------------------------
    # CONCLUSIÓN Y PRÓXIMOS PASOS
    # -------------------------------------------------------------------------
    story.append(Paragraph("4. Plan de Despliegue Progresivo", h1_style))
    story.append(Paragraph(
        "<b>1. Fase 1 (Consolidada):</b> Auditoría e informes de Turnos y Cobros del TPV en tiempo real.<br/>"
        "<b>2. Fase 2 (En curso):</b> Estructuración de menús backend de Almacén (`DOCUMENTOS`, `SUMINISTROS`) "
        "y Compras (`DOCUMENTOS`) con filtros automáticos por estación WireGuard VPN.<br/>"
        "<b>3. Fase 3:</b> Desglose de Ventas, Ficheros maestros y panel analítico para la Dirección General.",
        body_style
    ))
    
    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"PDF generado con éxito en: {output_path}")

if __name__ == "__main__":
    out_dir = "/home/bonilla/Projects/odoo/docs"
    out_file = os.path.join(out_dir, "ARBOL_NAVEGACION_INFORMES.pdf")
    generate_pdf(out_file)
