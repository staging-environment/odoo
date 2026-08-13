import os
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
)
from reportlab.pdfgen import canvas

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
        self.setFont('Helvetica-Bold', 8)
        self.setFillColor(colors.HexColor('#475569'))
        
        # Header (Pages > 1)
        if self._pageNumber > 1:
            self.drawString(54, 802, 'INFORME TÉCNICO Y HOJA DE RUTA: ASEPRODA -> ODOO 17 ERP')
            self.drawRightString(541, 802, 'PROYECTO ESTACIONES DE SERVICIO')
            self.setStrokeColor(colors.HexColor('#CBD5E1'))
            self.setLineWidth(0.75)
            self.line(54, 794, 541, 794)
            
        # Footer (All pages)
        self.setFont('Helvetica', 8)
        self.setFillColor(colors.HexColor('#64748B'))
        page_text = f'Página {self._pageNumber} de {page_count}'
        self.drawRightString(541, 32, page_text)
        self.drawString(54, 32, 'CONFIDENCIAL - Arquitectura Tecnológica & Plan de Transición ERP')
        self.setStrokeColor(colors.HexColor('#CBD5E1'))
        self.setLineWidth(0.75)
        self.line(54, 44, 541, 44)
        self.restoreState()

def build_pdf(filename):
    doc = SimpleDocTemplate(
        filename,
        pagesize=A4,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54
    )

    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        textColor=colors.white,
        alignment=0,
        spaceAfter=6
    )
    
    subtitle_style = ParagraphStyle(
        'DocSubTitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10.5,
        leading=14,
        textColor=colors.HexColor('#E2E8F0'),
        spaceAfter=2
    )

    meta_style = ParagraphStyle(
        'MetaStyle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor('#475569')
    )

    h1_style = ParagraphStyle(
        'SectionH1',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=16,
        textColor=colors.HexColor('#1E3A8A'),
        spaceBefore=12,
        spaceAfter=6,
        keepWithNext=True
    )

    h2_style = ParagraphStyle(
        'SectionH2',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=9.5,
        leading=13,
        textColor=colors.HexColor('#0F172A'),
        spaceBefore=8,
        spaceAfter=4,
        keepWithNext=True
    )

    body_style = ParagraphStyle(
        'BodyDark',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor('#1E293B'),
        spaceAfter=5
    )

    bullet_style = ParagraphStyle(
        'BulletText',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=11.5,
        textColor=colors.HexColor('#334155'),
        spaceAfter=3,
        leftIndent=10
    )

    table_header_style = ParagraphStyle(
        'TableHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=10,
        textColor=colors.white,
        alignment=0
    )

    table_cell_style = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7.8,
        leading=10.5,
        textColor=colors.HexColor('#1E293B')
    )

    callout_style = ParagraphStyle(
        'CalloutText',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.2,
        leading=11.5,
        textColor=colors.HexColor('#0F172A')
    )

    code_style = ParagraphStyle(
        'CodeStyle',
        parent=styles['Code'],
        fontName='Courier',
        fontSize=7.2,
        leading=9,
        textColor=colors.HexColor('#0F172A'),
        backColor=colors.HexColor('#F8FAFC'),
        borderColor=colors.HexColor('#CBD5E1'),
        borderWidth=0.5,
        borderPadding=5,
        spaceBefore=4,
        spaceAfter=6
    )

    story = []

    # BANNER PORTADA
    header_table_data = [
        [Paragraph('INFORME TÉCNICO Y HOJA DE RUTA', title_style)],
        [Paragraph('Transición Estratégica de Aseproda a Odoo 17 ERP (TPV, Control de Pista, Flotas y Gestión Global)', subtitle_style)]
    ]
    header_table = Table(header_table_data, colWidths=[487])
    header_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#1E3A8A')),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ('LEFTPADDING', (0, 0), (-1, -1), 12),
        ('RIGHTPADDING', (0, 0), (-1, -1), 12),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 6))

    # METADATOS
    meta_data = [
        [
            Paragraph('<b>Fecha:</b> Agosto 2026', meta_style),
            Paragraph('<b>Versión:</b> 1.0 Final', meta_style),
            Paragraph('<b>Estado:</b> Propuesta Estratégica', meta_style),
            Paragraph('<b>Ámbito:</b> Estaciones de Servicio', meta_style)
        ]
    ]
    meta_table = Table(meta_data, colWidths=[120, 100, 140, 127])
    meta_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8FAFC')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 8))

    # 1. RESUMEN EJECUTIVO
    story.append(Paragraph('1. Resumen Ejecutivo y Visión Estratégica', h1_style))
    story.append(Paragraph(
        'El presente documento define la <b>hoja de ruta técnica y funcional</b> para migrar el sistema de gestión '
        'actual (<b>Aseproda</b>) hacia la plataforma unificada <b>Odoo 17 ERP (Enterprise/Community + Módulos Personalizados '
        'para Estaciones de Servicio)</b>.', body_style
    ))
    story.append(Paragraph(
        'Aseproda ha sido una solución vertical sólida para el control de pista y la emisión de facturación simplificada. '
        'Sin embargo, su arquitectura cerrada limita la automatización de procesos corporativos, la omnicanalidad, la facturación '
        'electrónica avanzada y la visión financiera 360° en tiempo real.', body_style
    ))

    principle_box = (
        '<b>Principio Director de la Migración:</b><br/>'
        'La estrategia <b>no consiste en imitar rígidamente Aseproda</b>, sino en <b>absorber y perfeccionar todas sus '
        'capacidades críticas de pista</b> (cobro ultrarrápido en TPV, autorización de surtidores, crédito de flotas, '
        'varillaje y MITECO) mientras se aprovecha la enorme potencia del ecosistema estándar de Odoo (CRM, Compras, Contabilidad '
        'Española, SII, VeriFactu, RRHH y Portal del Cliente).'
    )
    story.append(Table([[Paragraph(principle_box, callout_style)]], colWidths=[487], style=[
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#EFF6FF')),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#3B82F6')),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(Spacer(1, 8))

    # 2. ANÁLISIS COMPARATIVO
    story.append(Paragraph('2. Análisis Comparativo: Aseproda vs. Odoo 17', h1_style))
    story.append(Paragraph(
        'Matriz funcional de correspondencia entre el sistema Aseproda y la solución modular propuesta en Odoo 17:', body_style
    ))

    comp_data = [
        [
            Paragraph('Área Funcional', table_header_style),
            Paragraph('Solución Aseproda (Legacy)', table_header_style),
            Paragraph('Solución Odoo 17 (Estándar + Addons)', table_header_style),
            Paragraph('Ventaja Estratégica Odoo', table_header_style)
        ],
        [
            Paragraph('<b>TPV / POS Pista</b>', table_cell_style),
            Paragraph('Escritorio Windows local. Cobro mangueras básico.', table_cell_style),
            Paragraph('<b>pos_gas_station</b> (Odoo POS Web/WebSockets).', table_cell_style),
            Paragraph('Cobro táctil ultra-rápido en PC, tablet o terminales móviles Android/iOS.', table_cell_style)
        ],
        [
            Paragraph('<b>Control Surtidores</b>', table_cell_style),
            Paragraph('Tarjetas serie / Concentrador Aseproda cerrado.', table_cell_style),
            Paragraph('<b>Agente Edge / Odoo IoT Box</b> (vía IFSF / TCP IP).', table_cell_style),
            Paragraph('Independencia de hardware. Soporte DOMS PSS 5000, Cetil, Tokheim, Gilbarco.', table_cell_style)
        ],
        [
            Paragraph('<b>Gestión Tanques</b>', table_cell_style),
            Paragraph('Volúmenes y lecturas manuales o básicas.', table_cell_style),
            Paragraph('<b>stock_tank_management</b> + Sondas Veeder-Root.', table_cell_style),
            Paragraph('Control de mermas por temperatura/densidad y asientos de ajuste automático.', table_cell_style)
        ],
        [
            Paragraph('<b>Crédito Flotas</b>', table_cell_style),
            Paragraph('Tarjetas locales. Facturación mensual manual.', table_cell_style),
            Paragraph('<b>fleet_credit_cards</b> + Portal Cliente Web.', table_cell_style),
            Paragraph('Autogestión de clientes: descarga facturas, control de saldos y PIN en tiempo real.', table_cell_style)
        ],
        [
            Paragraph('<b>Precios Carburante</b>', table_cell_style),
            Paragraph('Cambio manual o programado local.', table_cell_style),
            Paragraph('Tarifas Odoo + Monolito/Tótem y Surtidor.', table_cell_style),
            Paragraph('Reglas automáticas por margen sobre coste o precios de la competencia.', table_cell_style)
        ],
        [
            Paragraph('<b>Cumplimiento Fiscal</b>', table_cell_style),
            Paragraph('Exportación o módulos independientes.', table_cell_style),
            Paragraph('<b>l10n_es + SII + VeriFactu / TicketBAI</b>.', table_cell_style),
            Paragraph('Declaración fiscal automática a AEAT, libros oficiales e impuestos al día.', table_cell_style)
        ],
        [
            Paragraph('<b>MITECO (Geoportal)</b>', table_cell_style),
            Paragraph('Envío manual o vía script externo.', table_cell_style),
            Paragraph('<b>fuel_pricing_minetur</b> (API REST directa).', table_cell_style),
            Paragraph('Notificación legal automática en menos de 30 min tras cambio de precio.', table_cell_style)
        ],
        [
            Paragraph('<b>ERP Corporativo</b>', table_cell_style),
            Paragraph('Inexistente (requiere software externo).', table_cell_style),
            Paragraph('<b>Ecosistema Odoo 17 Completo</b>.', table_cell_style),
            Paragraph('CRM, Compras, Contabilidad, RRHH, Sitio Web y Cuadros de Mando BI unificados.', table_cell_style)
        ]
    ]

    comp_table = Table(comp_data, colWidths=[85, 125, 140, 137])
    comp_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E3A8A')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor('#F8FAFC')),
        ('BACKGROUND', (0, 3), (-1, 3), colors.HexColor('#F8FAFC')),
        ('BACKGROUND', (0, 5), (-1, 5), colors.HexColor('#F8FAFC')),
        ('BACKGROUND', (0, 7), (-1, 7), colors.HexColor('#F8FAFC')),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(comp_table)
    story.append(Spacer(1, 8))

    # 3. ARQUITECTURA TPV
    story.append(Paragraph('3. Arquitectura del TPV / POS y Control de Pista', h1_style))
    story.append(Paragraph(
        'Se implementa una arquitectura en 3 capas desacopladas para garantizar tiempo de respuesta instantáneo y tolerancia cero a fallos:', body_style
    ))

    arch_diagram = (
        "┌────────────────────────────────────────────────────────────────────────┐<br/>"
        "│                      SURTIDORES DE COMBUSTIBLE                         │<br/>"
        "│             (Gilbarco / Tokheim / Wayne Dresser / Cetil)               │<br/>"
        "└───────────────────────────────────┬────────────────────────────────────┘<br/>"
        "                                    │ RS-485 / IFSF / Bucle Corriente<br/>"
        "                                    ▼<br/>"
        "┌────────────────────────────────────────────────────────────────────────┐<br/>"
        "│        CONTROLADOR DE PISTA / FORECOURT CONTROLLER (DOMS PSS 5000)     │<br/>"
        "└───────────────────────────────────┬────────────────────────────────────┘<br/>"
        "                                    │ TCP/IP (IFSF / DOMS Binary Socket)<br/>"
        "                                    ▼<br/>"
        "┌────────────────────────────────────────────────────────────────────────┐<br/>"
        "│        AGENTE EDGE / ODOO IOT BOX (Daemon Python Local en Estación)    │<br/>"
        "│   - SQLite local buffer para operabilidad offline en caso de caída    │<br/>"
        "│   - Socket WebSockets permanente con el TPV de Odoo en la LAN local    │<br/>"
        "└───────────────────────────────────┬────────────────────────────────────┘<br/>"
        "                                    │ WebSockets (WSS) / JSON-RPC<br/>"
        "                                    ▼<br/>"
        "┌────────────────────────────────────────────────────────────────────────┐<br/>"
        "│                       ODOO 17 ERP (CLOUD / LOCAL)                      │<br/>"
        "│   - pos_gas_station (POS)      - stock_tank_management (Tanques)       │<br/>"
        "│   - fleet_credit_cards (Flotas) - l10n_es / SII (Contabilidad/AEAT)    │<br/>"
        "└────────────────────────────────────────────────────────────────────────┘"
    )
    story.append(Paragraph(arch_diagram, code_style))

    story.append(Paragraph('<b>Modalidades Principales de Operación en Pista:</b>', h2_style))
    story.append(Paragraph('• <b>Post-Pago (Atendido / Autoservicio):</b> El descolgado y suministro es registrado por el controlador. El Agente Edge emite un evento WebSocket al TPV Odoo POS. El cajero selecciona la manguera activada, cobra y emite el ticket.', bullet_style))
    story.append(Paragraph('• <b>Pre-Pago (Pago Previo):</b> El cliente abona el importe en caja. Odoo POS emite la orden AUTH_PUMP(manguera, importe_max). El surtidor permite el suministro y corta automáticamente al llegar al límite.', bullet_style))
    story.append(Paragraph('• <b>Tolerancia Offline (Contingencia Red):</b> Si se pierde la conexión a Internet, el Agente Edge guarda todas las transacciones en una base de datos SQLite local y el TPV en caja sigue cobrando normalmente. Al volver la red, se sincroniza automáticamente.', bullet_style))

    story.append(Spacer(1, 8))

    # 4. GESTIÓN DE CARBURANTES Y TANQUES
    story.append(Paragraph('4. Gestión de Carburantes, Tanques e Inventario', h1_style))
    story.append(Paragraph(
        'El módulo <b>stock_tank_management</b> extiende el sistema de inventario estándar de Odoo para adaptar el control de stock a las propiedades físicas de los hidrocarburos:', body_style
    ))
    story.append(Paragraph('1. <b>Integración con Sondas ATG:</b> Conexión directa con sondas Veeder-Root TLS-350/450 y OPW para lectura de volumen real, nivel de agua acumulada y temperatura del producto.', bullet_style))
    story.append(Paragraph('2. <b>Control de Varillaje y Mermas:</b> Comparación diaria entre el stock teórico en Odoo y el volumen corregido a 15°C medido en tanque. Generación de asientos automáticos de ajuste por pérdidas térmicas o evaporación.', bullet_style))
    story.append(Paragraph('3. <b>Recepciones de Cisterna:</b> Descarga de producto con verificación del albarán de la distribuidora mayorista y valoración contable de inventario por Precio Medio Ponderado (PMP).', bullet_style))
    story.append(Paragraph('4. <b>Tótems y Monolitos de Precios:</b> Cambio de tarifas desde Odoo con envío instantáneo a los displays exteriores en calle y surtidores de pista.', bullet_style))

    story.append(Spacer(1, 8))

    # 5. CRÉDITO DE FLOTAS
    story.append(Paragraph('5. Gestión Comercial, Flotas y Crédito de Clientes', h1_style))
    story.append(Paragraph(
        'Aseproda destaca por su control de crédito. Odoo 17 no solo absorbe este módulo con <b>fleet_credit_cards</b>, sino que lo digitaliza por completo:', body_style
    ))
    story.append(Paragraph('• <b>Reglas de Seguridad por Tarjeta:</b> Código PIN obligatorio, validación de matrícula, límites diarios/semanales/mensuales (en € o litros) y restricción por manguera/producto.', bullet_style))
    story.append(Paragraph('• <b>Facturación Mensual Agrupada:</b> Los repostajes con tarjeta de flota acumulan albaranes de crédito durante el mes. El último día del periodo, Odoo ejecuta un proceso por lotes que emite una factura agrupada desglosada por vehículo, estación, fecha y producto.', bullet_style))
    story.append(Paragraph('• <b>Portal Web del Cliente de Flotas:</b> Los clientes profesionales acceden con su usuario web para consultar consumo en tiempo real, descargar facturas firmadas en PDF/XML, bloquear tarjetas extraviadas y ajustar límites de chóferes.', bullet_style))

    story.append(Spacer(1, 8))

    # 6. CUMPLIMIENTO FISCAL
    story.append(Paragraph('6. Cumplimiento Normativo y Fiscal en España', h1_style))
    story.append(Paragraph(
        'Integración nativa con los requerimientos legales vigentes en el territorio español:', body_style
    ))
    story.append(Paragraph('• <b>SII (Agencia Tributaria):</b> Envío automático de facturas emitidas y recibidas a la AEAT en los plazos legales.', bullet_style))
    story.append(Paragraph('• <b>VeriFactu / TicketBAI:</b> Facturación simplificada con código QR, encadenamiento de facturas Hash y registro inalterable.', bullet_style))
    story.append(Paragraph('• <b>Notificación MITECO (Geoportal):</b> Módulo <b>fuel_pricing_minetur</b> para notificar al Ministerio de Transición Ecológica cualquier modificación de precios en menos de 30 minutos.', bullet_style))
    story.append(Paragraph('• <b>Impuestos Especiales de Hidrocarburos (IIEE):</b> Trazabilidad de ventas de gasóleo bonificado (Agrícola B/C) y generación de ficheros de declaración obligatoria.', bullet_style))

    story.append(Spacer(1, 8))

    # 7. ECOSISTEMA AMPLIADO
    story.append(Paragraph('7. Ecosistema Ampliado Odoo 17: Valor Añadido', h1_style))
    story.append(Paragraph(
        'Al adoptar Odoo 17, la empresa desbloquea funcionalidades avanzadas que Aseproda no puede proporcionar:', body_style
    ))
    story.append(Paragraph('• <b>Contabilidad Española Oficial:</b> Balances de Pérdidas y Ganancias, Libro Diario, Mayor, Modelos 303, 347, 390 y conciliación bancaria con inteligencia artificial.', bullet_style))
    story.append(Paragraph('• <b>Tienda de Conveniencia (Superette) y Lavadero:</b> Gestión de stock de tienda (bebidas, lubricantes, snacks) y fichas de lavadero en el mismo TPV.', bullet_style))
    story.append(Paragraph('• <b>Recursos Humanos y Turnos:</b> Planificación de horarios de empleados de gasolinera, fichaje digital obligatorio y cálculo de incentivos por ventas.', bullet_style))
    story.append(Paragraph('• <b>Business Intelligence (BI):</b> Cuadros de mando con análisis de ventas por litro/hora, margen bruto por tipo de combustible y rentabilidad por turno.', bullet_style))

    story.append(Spacer(1, 8))

    # 8. ROADMAP
    story.append(Paragraph('8. Hoja de Ruta de Implementación (Roadmap por Fases)', h1_style))
    story.append(Paragraph(
        'Cronograma estructurado en <b>5 fases estratégicas (16 a 20 semanas en total)</b>:', body_style
    ))

    roadmap_data = [
        [
            Paragraph('Fase y Duración', table_header_style),
            Paragraph('Objetivos Principales', table_header_style),
            Paragraph('Entregables Clave', table_header_style)
        ],
        [
            Paragraph('<b>Fase 1: Análisis y Prototipo Agente Edge</b><br/>(Semanas 1 - 4)', table_cell_style),
            Paragraph('Auditoría de hardware de pista (DOMS PSS 5000, Cetil, Sondas). Prototipo de comunicación WebSocket.', table_cell_style),
            Paragraph('Documento de arquitectura de pista y prototipo de Agente Edge funcional en laboratorio.', table_cell_style)
        ],
        [
            Paragraph('<b>Fase 2: Configuración Core Odoo</b><br/>(Semanas 5 - 8)', table_cell_style),
            Paragraph('Configuración de Contabilidad ES, Compras, Inventario, SII y desarrollo de módulos custom (stock_tank, fleet_credit).', table_cell_style),
            Paragraph('Instancia Staging de Odoo 17 configurada con catálogo de productos y reglas de negocio.', table_cell_style)
        ],
        [
            Paragraph('<b>Fase 3: Desarrollo TPV POS Pista</b><br/>(Semanas 9 - 12)', table_cell_style),
            Paragraph('Adaptación de la interfaz TPV POS, conexión con el Agente Edge, terminales de cobro y ticketeras.', table_cell_style),
            Paragraph('Módulo pos_gas_station integrado y validado con surtidores de prueba.', table_cell_style)
        ],
        [
            Paragraph('<b>Fase 4: Migración Datos & Pruebas</b><br/>(Semanas 13 - 16)', table_cell_style),
            Paragraph('Importación de datos de Aseproda (clientes, saldos flotas, tarifas). Pruebas en paralelo en estación piloto.', table_cell_style),
            Paragraph('Informe de cuadre de migración y validación operativa en estación piloto.', table_cell_style)
        ],
        [
            Paragraph('<b>Fase 5: Formación & Go-Live</b><br/>(Semanas 17 - 20)', table_cell_style),
            Paragraph('Formación a personal de pista y administración. Arrancado definitivo y soporte presencial.', table_cell_style),
            Paragraph('Puesta en producción (Go-Live) completa y paso a fase de mantenimiento.', table_cell_style)
        ]
    ]

    roadmap_table = Table(roadmap_data, colWidths=[120, 187, 180])
    roadmap_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E3A8A')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor('#F8FAFC')),
        ('BACKGROUND', (0, 3), (-1, 3), colors.HexColor('#F8FAFC')),
        ('BACKGROUND', (0, 5), (-1, 5), colors.HexColor('#F8FAFC')),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(roadmap_table)
    story.append(Spacer(1, 8))

    # 9. MATRIZ DE RIESGOS
    story.append(Paragraph('9. Matriz de Riesgos y Plan de Mitigación', h1_style))
    
    risk_data = [
        [
            Paragraph('Riesgo Identificado', table_header_style),
            Paragraph('Impacto', table_header_style),
            Paragraph('Prob.', table_header_style),
            Paragraph('Estrategia de Mitigación y Contingencia', table_header_style)
        ],
        [
            Paragraph('Caída de conexión de red durante horas pico de venta', table_cell_style),
            Paragraph('<font color="#DC2626"><b>Crítico</b></font>', table_cell_style),
            Paragraph('Baja', table_cell_style),
            Paragraph('Agente Edge con almacenamiento en buffer SQLite local y doble interfaz Ethernet redundante.', table_cell_style)
        ],
        [
            Paragraph('Inconsistencia en los saldos de flotas migrados de Aseproda', table_cell_style),
            Paragraph('<font color="#EA580C"><b>Alto</b></font>', table_cell_style),
            Paragraph('Baja', table_cell_style),
            Paragraph('Ejecución de scripts de auditoría previa y corte contable duplicado el día de la transición.', table_cell_style)
        ],
        [
            Paragraph('Resistencia del personal de pista a la nueva interfaz TPV', table_cell_style),
            Paragraph('Medio', table_cell_style),
            Paragraph('Media', table_cell_style),
            Paragraph('Diseño de TPV ultra-simplificado y capacitaciones prácticas intensivas previa en estación piloto.', table_cell_style)
        ],
        [
            Paragraph('Latencia en la respuesta de la orden de autorización (> 200ms)', table_cell_style),
            Paragraph('<font color="#EA580C"><b>Alto</b></font>', table_cell_style),
            Paragraph('Baja', table_cell_style),
            Paragraph('Uso exclusivo de conexiones permanentes WebSockets sobre la red local (LAN) de la estación.', table_cell_style)
        ]
    ]

    risk_table = Table(risk_data, colWidths=[130, 50, 45, 262])
    risk_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E3A8A')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor('#F8FAFC')),
        ('BACKGROUND', (0, 3), (-1, 3), colors.HexColor('#F8FAFC')),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(risk_table)
    story.append(Spacer(1, 8))

    # 10. CONCLUSIONES Y PRÓXIMOS PASOS
    story.append(Paragraph('10. Conclusiones y Próximos Pasos', h1_style))
    story.append(Paragraph(
        'La migración estratégica de <b>Aseproda a Odoo 17</b> proporciona a la organización una solución moderna, '
        'escalable y totalmente integrada. Se garantiza la continuidad operativa de la estación de servicio mientras se '
        'reemplaza un software cerrado por una plataforma ERP líder mundial.', body_style
    ))

    next_steps_box = (
        '<b>Próximos Pasos Recomendados:</b><br/>'
        '1. <b>Aprobación Directiva:</b> Validar la presente hoja de ruta y asignar los recursos del proyecto.<br/>'
        '2. <b>Inicio Fase 1 (Semana 1):</b> Iniciar la auditoría física de hardware de pista (controladores DOMS/Aseproda y sondas ATG).<br/>'
        '3. <b>Despliegue Staging:</b> Levantar el entorno Staging de Odoo 17 con los módulos base configurados.'
    )
    story.append(Table([[Paragraph(next_steps_box, callout_style)]], colWidths=[487], style=[
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F0FDF4')),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#16A34A')),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))

    doc.build(story, canvasmaker=NumberedCanvas)

if __name__ == '__main__':
    script_dir = os.path.dirname(os.path.abspath(__file__))
    pdf_path = os.path.join(script_dir, 'docs', 'Informe_Tecnico_Hoja_de_Ruta_Odoo_Aseproda.pdf')
    os.makedirs(os.path.dirname(pdf_path), exist_ok=True)
    build_pdf(pdf_path)
    print(f'PDF technical roadmap report successfully generated at: {pdf_path}')
