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
            self.draw_page_number(num_pages)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def draw_page_number(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 9)
        self.setFillColor(colors.HexColor("#64748B"))
        
        # Header (pages > 1)
        if self._pageNumber > 1:
            self.drawString(54, 800, "Especificaciones Hardware & Protocolos Gasolineras - Odoo 17")
            self.setStrokeColor(colors.HexColor("#CBD5E1"))
            self.setLineWidth(0.5)
            self.line(54, 792, 541, 792)
            
        # Footer
        page_text = f"Página {self._pageNumber} de {page_count}"
        self.drawRightString(541, 36, page_text)
        self.drawString(54, 36, "Especificación Técnica Hardware - Odoo 17 ERP")
        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.setLineWidth(0.5)
        self.line(54, 48, 541, 48)
        self.restoreState()

def create_pdf(filename):
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
        parent=styles['Title'],
        fontName='Helvetica-Bold',
        fontSize=22,
        leading=26,
        textColor=colors.HexColor('#0F172A'),
        alignment=0,
        spaceAfter=8
    )

    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=11,
        leading=15,
        textColor=colors.HexColor('#475569'),
        spaceAfter=15
    )

    h1_style = ParagraphStyle(
        'Heading1_Custom',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=14,
        leading=18,
        textColor=colors.HexColor('#1E3A8A'),
        spaceBefore=14,
        spaceAfter=8,
        keepWithNext=True
    )

    h2_style = ParagraphStyle(
        'Heading2_Custom',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=15,
        textColor=colors.HexColor('#0F172A'),
        spaceBefore=10,
        spaceAfter=5,
        keepWithNext=True
    )

    body_style = ParagraphStyle(
        'Body_Custom',
        parent=styles['BodyText'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=13.5,
        textColor=colors.HexColor('#334155'),
        spaceAfter=6
    )

    bullet_style = ParagraphStyle(
        'Bullet_Custom',
        parent=body_style,
        leftIndent=12,
        spaceAfter=3
    )

    code_style = ParagraphStyle(
        'Code_Custom',
        parent=styles['Code'],
        fontName='Courier',
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor('#0F172A'),
        backColor=colors.HexColor('#F8FAFC'),
        borderColor=colors.HexColor('#CBD5E1'),
        borderWidth=0.5,
        borderPadding=8,
        spaceBefore=5,
        spaceAfter=8
    )

    callout_style = ParagraphStyle(
        'Callout',
        parent=body_style,
        fontSize=9,
        leading=13,
        textColor=colors.HexColor('#1E293B'),
        backColor=colors.HexColor('#EFF6FF'),
        borderColor=colors.HexColor('#3B82F6'),
        borderWidth=1,
        borderPadding=8,
        spaceBefore=6,
        spaceAfter=10
    )

    table_header_style = ParagraphStyle(
        'TableHeader',
        parent=body_style,
        fontName='Helvetica-Bold',
        fontSize=9,
        textColor=colors.HexColor('#FFFFFF')
    )

    table_cell_style = ParagraphStyle(
        'TableCell',
        parent=body_style,
        fontSize=8.5,
        leading=11.5,
        spaceAfter=0
    )

    story = []

    # Title Banner
    story.append(Paragraph("Especificaciones de Hardware, Protocolos y Control de Pista en Gasolineras", title_style))
    story.append(Paragraph("Integración de Surtidores, Forecourt Controllers (FCC), Tanques ATG y Comandos de Control con Odoo 17", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#2563EB'), spaceAfter=12))

    # SECTION 1
    story.append(Paragraph("1. Hardware Necesario en la Estación de Servicio", h1_style))
    story.append(Paragraph(
        "Para operar una gasolinera (atendida o desatendida) integrada con Odoo 17 se requiere una arquitectura física en pista que centralice los surtidores y los comunique con la caja vía un Agente Edge local.",
        body_style
    ))

    # Architecture diagram ASCII
    diagram_text = (
        "+-----------------------------------------------------------------------------+<br/>"
        "|                         SURTIDORES Y TANQUES (PISTA)                        |<br/>"
        "|   - Surtidores: Gilbarco, Tokheim, Wayne, Cetil                             |<br/>"
        "|   - Sondaje de Tanques (ATG): Veeder-Root TLS-350 / TLS-450                 |<br/>"
        "+--------------------------------------+--------------------------------------+<br/>"
        "                                       | Cableado Loop 20mA / RS-485 / RS-232<br/>"
        "                                       v<br/>"
        "+-----------------------------------------------------------------------------+<br/>"
        "|                CONTROLADOR DE PISTA (FORECOURT CONTROLLER)                  |<br/>"
        "|   - Controlador Central: DOMS PSS 5000 / Postec / Alvesa                    |<br/>"
        "|   - Modulos de Interfaz de Bucle (Hardware Interface Cards)                 |<br/>"
        "+--------------------------------------+--------------------------------------+<br/>"
        "                                       | Red Local Ethernet (TCP/IP / IFSF)<br/>"
        "                                       v<br/>"
        "+-----------------------------------------------------------------------------+<br/>"
        "|                 PASARELA EDGE LOCAL / ODOO IOT BOX                          |<br/>"
        "|   - Hardware: Mini PC Industrial / Fanless (Intel NUC / Raspberry Pi 4)     |<br/>"
        "|   - SO: Linux Ubuntu Server / Debian                                        |<br/>"
        "|   - Agente Daemon Python (Servicio de Control de Pista y Offline Buffer)    |<br/>"
        "+--------------------------------------+--------------------------------------+<br/>"
        "                                       | HTTPS / WebSockets / JSON-RPC<br/>"
        "                                       v<br/>"
        "+-----------------------------------------------------------------------------+<br/>"
        "|                        CAJA Y TPV (ODOO 17 POS)                             |<br/>"
        "|   - Pantalla Tactil TPV / Impresora Termica de Tickets (ESC/POS)            |<br/>"
        "|   - Terminal de Pago Tarjeta (PinPad EMV / Contactless)                     |<br/>"
        "|   - Odoo 17 ERP (Servidor Cloud o Servidor Local)                           |<br/>"
        "+-----------------------------------------------------------------------------+"
    )
    story.append(Paragraph(diagram_text, code_style))

    story.append(Paragraph("1.1 Tabla de Equipamiento y Componentes", h2_style))

    # Hardware Table
    table_data = [
        [
            Paragraph("Componente", table_header_style),
            Paragraph("Función Principal", table_header_style),
            Paragraph("Modelos Recomendados / Estándar", table_header_style)
        ],
        [
            Paragraph("<b>Forecourt Controller (FCC)</b>", table_cell_style),
            Paragraph("Agrupar y traducir los protocolos propietarios de cada surtidor a una interfaz única.", table_cell_style),
            Paragraph("<b>DOMS PSS 5000</b> (Estándar mundial), Postec, Alvesa, Concentrador Cetil.", table_cell_style)
        ],
        [
            Paragraph("<b>Servidor Edge / IoT Box</b>", table_cell_style),
            Paragraph("Ejecutar el Agente Daemon que comunica el FCC con Odoo vía WebSockets en tiempo real.", table_cell_style),
            Paragraph("Mini PC Industrial Fanless (Intel Celeron/Core i3, 8GB RAM, SSD 128GB, Doble puerto Ethernet).", table_cell_style)
        ],
        [
            Paragraph("<b>Sondas de Tanques (ATG)</b>", table_cell_style),
            Paragraph("Medir volumen de combustible, agua libre y temperatura dentro de los tanques.", table_cell_style),
            Paragraph("<b>Veeder-Root TLS-350 / TLS-450</b>, OPW SiteSentinel, Colibri.", table_cell_style)
        ],
        [
            Paragraph("<b>Impresora de Tickets</b>", table_cell_style),
            Paragraph("Impresión rápida de comprobantes simplificados y facturas de pista.", table_cell_style),
            Paragraph("Epson TM-T20III / TM-T88VI (Ethernet/USB con protocolo ESC/POS).", table_cell_style)
        ],
        [
            Paragraph("<b>PinPad / Pago Pista</b>", table_cell_style),
            Paragraph("Cobro con tarjeta bancaria, Google Pay, Apple Pay y tarjetas de flota.", table_cell_style),
            Paragraph("Ingenico Lane/3000, Verifone P400, o Terminal de Pago de Pista (OPT).", table_cell_style)
        ]
    ]

    hw_table = Table(table_data, colWidths=[130, 190, 167])
    hw_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E3A8A')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor('#F8FAFC')),
        ('BACKGROUND', (0, 3), (-1, 3), colors.HexColor('#F8FAFC')),
        ('BACKGROUND', (0, 5), (-1, 5), colors.HexColor('#F8FAFC')),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(hw_table)

    story.append(Spacer(1, 10))

    # SECTION 2
    story.append(Paragraph("2. Protocolos de Comunicación Industriales", h1_style))
    story.append(Paragraph("<b>A. Nivel 1: Surtidor ↔ Controlador de Pista (Bucle Serie/Hardware)</b>", body_style))
    story.append(Paragraph("• <b>Gilbarco Two-Wire Current Loop (20mA):</b> Transmisión por bucle de corriente serie para surtidores Gilbarco Veeder-Root.", bullet_style))
    story.append(Paragraph("• <b>Tokheim Ka-Loop / Dunclare:</b> Bucle de corriente específico de cabezales Tokheim Quantium.", bullet_style))
    story.append(Paragraph("• <b>Wayne DART Protocol:</b> Comunicación serie RS-485 para surtidores Wayne Dresser.", bullet_style))
    story.append(Paragraph("• <b>Modbus RTU / RS-485:</b> Protocolo industrial estándar para surtidores electrónicos y sondas.", bullet_style))

    story.append(Paragraph("<b>B. Nivel 2: Controlador de Pista ↔ Agente Edge (Red Local TCP/IP)</b>", body_style))
    story.append(Paragraph("• <b>IFSF (International Forecourt Standards Forum) TCP/IP:</b> Estándar internacional sobre socket TCP (puerto 4000/4001). Define máquina de estados estandarizada para surtidores, precios y totalizadores.", bullet_style))
    story.append(Paragraph("• <b>DOMS TCP Protocol (PSS Direct Protocol):</b> Protocolo socket binario de baja latencia del fabricante DOMS. Permite control total manguera por manguera, bloqueos de seguridad y lecturas contables inalterables.", bullet_style))

    story.append(Paragraph("<b>C. Nivel 3: Agente Edge ↔ Odoo 17 ERP (Capa Aplicación Cloud/Local)</b>", body_style))
    story.append(Paragraph("• <b>WebSockets (WSS):</b> Conexión dúplex permanente. Odoo envía órdenes de activación al instante y el Agente Edge notifica mangueras descolgadas o finalizaciones de suministro sin retardos (latencia < 50ms).", bullet_style))
    story.append(Paragraph("• <b>JSON-RPC / REST API (HTTPS):</b> Envío de cierres de turno, totalizadores diarios, eventos de alarma y lecturas de tanques de combustible.", bullet_style))

    story.append(Spacer(1, 10))

    # SECTION 3
    story.append(Paragraph("3. Mecanismo de Control de Pista (Abrir / Cerrar / Autorizar)", h1_style))
    story.append(Paragraph("El control de los surtidores se basa en una máquina de estados administrada por Odoo y ejecutada por el Agente Edge.", body_style))

    story.append(Paragraph("3.1 Comandos de Control Ejecutados por Odoo", h2_style))
    story.append(Paragraph("<b>1. Autorización de Surtidor (AUTH / PREPAY):</b> Habilita el suministro en un surtidor. Parámetros: <code>surtidor_id</code>, <code>manguera_id</code>, <code>limite_importe</code> (ej. 50.00€) o <code>limite_litros</code> (ej. 40.00 L). El estado pasa a <code>AUTHORIZED</code> y la bomba libera el paso de combustible.", bullet_style))
    story.append(Paragraph("<b>2. Bloqueo / Cierre de Surtidor (LOCK / STOP):</b> Impide el uso del surtidor (mantenimiento, fuera de servicio o cierre nocturno). El estado pasa a <code>LOCKED</code> y la bomba no arranca aunque se descuelgue la manguera.", bullet_style))
    story.append(Paragraph("<b>3. Parada de Emergencia (EMERGENCY HALT):</b> Corta inmediatamente el suministro en un surtidor o en toda la pista. Detención inmediata de bombas de presión y cierre de electroválvulas.", bullet_style))
    story.append(Paragraph("<b>4. Liberación / Desbloqueo tras Cobro (RELEASE / UNLOCK):</b> Tras cobrar el ticket en el TPV de Odoo, el surtidor vuelve al estado <code>IDLE</code> (Disponible).", bullet_style))

    story.append(Paragraph("3.2 Diagrama de Estados del Surtidor en Odoo POS", h2_style))
    state_diagram = (
        " +--------------+      Manguera Descolgada       +--------------+<br/>"
        " |     IDLE     +------------------------------->| LIFTED / REQ |<br/>"
        " | (Disponible) |                                |  (Solicitud) |<br/>"
        " +------+-------+                                +-------+------+<br/>"
        "        ^                                                |<br/>"
        "        | Pago Cobrado                                   | Autorizacion OK<br/>"
        "        | (Release)                                      | (Auth Command)<br/>"
        " +------+-------+       Suministro Finalizado    +-------v------+<br/>"
        " |   STOPPED /  |<-------------------------------|   PUMPING /  |<br/>"
        " | WAITING PAY  |                                |   DENSING    |<br/>"
        " | (Pendiente)  |                                | (Surtiendo)  |<br/>"
        " +--------------+                                +--------------+"
    )
    story.append(Paragraph(state_diagram, code_style))

    story.append(Paragraph("4. Tolerancia a Fallos y Modo Offline (Servicio Continuo)", h1_style))
    offline_callout = (
        "<b>Garantía de Servicio Continuo en Estación de Servicio:</b><br/>"
        "1. <b>Buffer Local de Transacciones:</b> Si la conexión HTTPS con Odoo Cloud se corta, el Agente Edge almacena todas las ventas servidas en una base de datos local aislada (SQLite/PostgreSQL).<br/>"
        "2. <b>Ventas sin Interrupción:</b> El TPV de Odoo en caja comunica directamente por LAN con el Agente Edge para seguir autorizando y cobrando ventas.<br/>"
        "3. <b>Sincronización Automática:</b> Al restablecerse el acceso a internet, el Agente Edge sincroniza automáticamente las ventas pendientes con Odoo Cloud sin duplicidades."
    )
    story.append(Paragraph(offline_callout, callout_style))

    doc.build(story, canvasmaker=NumberedCanvas)

if __name__ == "__main__":
    pdf_path = os.path.abspath("docs/Especificaciones_Hardware_y_Protocolos_Gasolineras_Odoo17.pdf")
    os.makedirs(os.path.dirname(pdf_path), exist_ok=True)
    create_pdf(pdf_path)
    print(f"PDF successfully generated at: {pdf_path}")
