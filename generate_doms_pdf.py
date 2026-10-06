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
        self.setFont("Helvetica-Bold", 8)
        self.setFillColor(colors.HexColor("#475569"))
        
        # Header (Pages > 1)
        if self._pageNumber > 1:
            self.drawString(54, 802, "COMPATIBILIDAD DE MODELOS DOMS CON ODOO ERP / POS")
            self.drawRightString(541, 802, "GUIA TECNICA DE HARDWARE FCC")
            self.setStrokeColor(colors.HexColor("#CBD5E1"))
            self.setLineWidth(0.75)
            self.line(54, 794, 541, 794)
            
        # Footer (All pages)
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748B"))
        page_text = f"Pagina {self._pageNumber} de {page_count}"
        self.drawRightString(541, 32, page_text)
        self.drawString(54, 32, "Controladores de Pista DOMS PSS 5000 & Integracion Odoo 17 POS")
        self.setStrokeColor(colors.HexColor("#CBD5E1"))
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
    
    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=16,
        leading=20,
        textColor=colors.white,
        alignment=0,
        spaceAfter=4
    )
    
    subtitle_style = ParagraphStyle(
        "DocSubTitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9.5,
        leading=13.5,
        textColor=colors.HexColor("#E2E8F0"),
        spaceAfter=2
    )

    meta_style = ParagraphStyle(
        "MetaStyle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#475569")
    )

    h1_style = ParagraphStyle(
        "SectionH1",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=10.5,
        leading=14,
        textColor=colors.HexColor("#1E3A8A"),
        spaceBefore=9,
        spaceAfter=4,
        keepWithNext=True
    )

    body_style = ParagraphStyle(
        "BodyDark",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=11.5,
        textColor=colors.HexColor("#1E293B"),
        spaceAfter=4
    )

    bullet_style = ParagraphStyle(
        "BulletText",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7.8,
        leading=11,
        textColor=colors.HexColor("#334155"),
        spaceAfter=2.5,
        leftIndent=8
    )

    table_header_style = ParagraphStyle(
        "TableHeader",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7.8,
        leading=9.8,
        textColor=colors.white,
        alignment=0
    )

    table_cell_style = ParagraphStyle(
        "TableCell",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7.3,
        leading=9.8,
        textColor=colors.HexColor("#1E293B")
    )

    callout_style = ParagraphStyle(
        "CalloutText",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7.8,
        leading=11,
        textColor=colors.HexColor("#0F172A")
    )

    code_style = ParagraphStyle(
        "CodeStyle",
        parent=styles["Code"],
        fontName="Courier",
        fontSize=6.8,
        leading=8.6,
        textColor=colors.HexColor("#0F172A"),
        backColor=colors.HexColor("#F8FAFC"),
        borderColor=colors.HexColor("#CBD5E1"),
        borderWidth=0.5,
        borderPadding=4,
        spaceBefore=3,
        spaceAfter=5
    )

    story = []

    # BANNER PORTADA
    header_table_data = [
        [Paragraph("COMPATIBILIDAD DE MODELOS DOMS CON ODOO", title_style)],
        [Paragraph("Guia Tecnica de Controladores de Pista (FCC) DOMS PSS 5000, Placas CPU, Protocolos y Conexion Odoo POS", subtitle_style)]
    ]
    header_table = Table(header_table_data, colWidths=[487])
    header_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#1E3A8A")),
        ("TOPPADDING", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 4))

    # METADATOS
    meta_data = [
        [
            Paragraph("<b>Fecha:</b> Septiembre 2026", meta_style),
            Paragraph("<b>Version:</b> 1.0 Oficial", meta_style),
            Paragraph("<b>Ambito:</b> Estaciones de Servicio", meta_style),
            Paragraph("<b>Tipo:</b> Especificacion Hardware FCC", meta_style)
        ]
    ]
    meta_table = Table(meta_data, colWidths=[115, 95, 140, 137])
    meta_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 6))

    # 1. INTRODUCCION
    story.append(Paragraph("1. Introduccion y Rol de DOMS como Forecourt Controller (FCC)", h1_style))
    story.append(Paragraph(
        "En el ambito de las estaciones de servicio, <b>DOMS</b> (desarrollado por <b>DOMS ApS / Gilbarco Veeder-Root</b>) "
        "es el controlador de pista (<b>Forecourt Controller - FCC</b>) lider a nivel mundial. Su funcion principal es actuar "
        "como concentrador y traductor maestro de hardware: hacia la pista gestiona la electronica y bucles de corriente "
        "propietarios de surtidores (Gilbarco, Tokheim, Wayne, Cetil, Bennett) y sondas de tanques (ATG Veeder-Root TLS), "
        "mientras que hacia el TPV/ERP expone una interfaz normalizada de alto nivel sobre red local Ethernet (TCP/IP).",
        body_style
    ))

    callout_principio = (
        "<b>Principio Fundamental de Compatibilidad con Odoo:</b><br/>"
        "La compatibilidad entre DOMS y Odoo <b>no depende de las marcas ni modelos de los surtidores fisicos de la pista</b>, "
        "sino de la <b>capacidad del controlador DOMS para comunicarse por red Ethernet (TCP/IP)</b> utilizando interfaces "
        "de host estandar (DOMS PSS Direct Protocol o IFSF TCP/IP). Cualquier surtidor conectado a DOMS se vuelve transparente "
        "y controlable por Odoo."
    )
    callout_table = Table([[Paragraph(callout_principio, callout_style)]], colWidths=[487])
    callout_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#EFF6FF")),
        ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#3B82F6")),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 9),
        ("RIGHTPADDING", (0, 0), (-1, -1), 9),
    ]))
    story.append(callout_table)
    story.append(Spacer(1, 5))

    # 2. MATRIZ DE MODELOS Y CPUS
    story.append(Paragraph("2. Matriz de Compatibilidad: Modelos y Placas CPU (CPUB)", h1_style))
    story.append(Paragraph(
        "La plataforma de referencia es el <b>DOMS PSS 5000</b>. La compatibilidad con Odoo esta determinada "
        "directamente por la tarjeta procesadora central (<b>CPUB</b>) que tiene montada el rack:",
        body_style
    ))

    cpub_table_data = [
        [
            Paragraph("Modelo / Placa CPU", table_header_style),
            Paragraph("Compatibilidad Odoo", table_header_style),
            Paragraph("Conectividad Fisica", table_header_style),
            Paragraph("Protocolos Soportados", table_header_style),
            Paragraph("Diagnostico y Recomendacion", table_header_style)
        ],
        [
            Paragraph("<b>DOMS PSS 5000<br/>(CPUB 520)</b>", table_cell_style),
            Paragraph('<font color="#059669"><b>100% Nativa<br/>(Recomendado)</b></font>', table_cell_style),
            Paragraph("Multi-LAN (2-3 puertos Ethernet RJ-45 independientes), USB, Criptografia SSL/TLS.", table_cell_style),
            Paragraph("• PSS Direct TCP<br/>• IFSF TCP/IP<br/>• DOMS REST API / WebServices", table_cell_style),
            Paragraph("<b>Generacion actual.</b> Maximo rendimiento, aislamiento de red pista/caja y seguridad avanzada.", table_cell_style)
        ],
        [
            Paragraph("<b>DOMS PSS 5000<br/>(CPUB 510 / 511)</b>", table_cell_style),
            Paragraph('<font color="#059669"><b>100% Compatible</b></font>', table_cell_style),
            Paragraph("1 puerto Ethernet 10/100 BASE-T, USB, RS-232, RS-485.", table_cell_style),
            Paragraph("• PSS Direct TCP (puerto 7000)<br/>• IFSF TCP/IP (puerto 4000)", table_cell_style),
            Paragraph("<b>El modelo mas extendido</b> en instalaciones activas. Totalmente probado y compatible con Agente Edge Odoo.", table_cell_style)
        ],
        [
            Paragraph("<b>DOMS PSS 5000<br/>(CPUB 500 a 505)</b><br/><i>(Legacy)</i>", table_cell_style),
            Paragraph('<font color="#D97706"><b>Condicional<br/>(Requiere LAN)</b></font>', table_cell_style),
            Paragraph("Puertos serie nativos. Requiere tarjeta de red Ethernet opcional.", table_cell_style),
            Paragraph("• PSS Serial<br/>• IFSF LonWorks/HDLC<br/>• PSS TCP (con tarjeta LAN)", table_cell_style),
            Paragraph("Compatible solo si equipa tarjeta Ethernet y firmware moderno. De lo contrario, se recomienda actualizar la CPU a CPUB 510/520.", table_cell_style)
        ],
        [
            Paragraph("<b>DOMS Compact</b>", table_cell_style),
            Paragraph('<font color="#059669"><b>100% Compatible</b></font>', table_cell_style),
            Paragraph("1 puerto Ethernet 10/100, puertos serie integrados.", table_cell_style),
            Paragraph("• PSS Direct TCP<br/>• IFSF TCP/IP", table_cell_style),
            Paragraph("Version reducida para estaciones desatendidas / postes de autoservicio. Integra la misma arquitectura TCP que PSS 5000.", table_cell_style)
        ]
    ]

    cpub_table = Table(cpub_table_data, colWidths=[88, 77, 110, 106, 106])
    cpub_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E3A8A")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(cpub_table)
    story.append(Spacer(1, 6))

    # 3. FACTORES DE FORMA
    story.append(Paragraph("3. Factores de Forma y Enclosures (Chasis Fisicos)", h1_style))
    story.append(Paragraph(
        "El factor de forma o chasis exterior aloja la fuente conmutada, el plano trasero (backplane) y las bahias para "
        "modulos. <b>El tipo de caja no limita la conectividad con Odoo</b>, ya que todas comparten las mismas opciones de CPU:",
        body_style
    ))
    story.append(Paragraph("• <b>PSS 5000 19 Pulgadas Rack Mount (16 ranuras):</b> Disenado para armarios de telecomunicaciones estandar. Aloja gran cantidad de lineas de comunicacion para estaciones de alto transito o mixtas.", bullet_style))
    story.append(Paragraph("• <b>PSS 5000 Wall-Mount Box (4 u 8 ranuras):</b> Chasis mural blindado con llave de seguridad. Es la opcion estandar instalada en oficinas de gasolinera y casetas tecnicas.", bullet_style))
    story.append(Paragraph("• <b>DOMS Compact Box:</b> Formato ultra-reducido para estaciones desatendidas o quioscos exteriores de pago desatendido (OPT).", bullet_style))

    story.append(PageBreak())

    # 4. TARJETAS DE INTERFAZ DSB
    story.append(Paragraph("4. Tarjetas de Interfaz de Pista (DSB - Device Specific Boards)", h1_style))
    story.append(Paragraph(
        "Aunque la comunicacion entre DOMS y Odoo se realiza por red TCP/IP, el controlador DOMS debe disponer de las tarjetas "
        "<b>DSB</b> adecuadas para comunicar fisicamente con el hardware instalado en cada estacion:",
        body_style
    ))

    dsb_table_data = [
        [
            Paragraph("Tarjeta DSB", table_header_style),
            Paragraph("Dispositivos y Fabricantes Conectados", table_header_style),
            Paragraph("Tecnologia / Protocolo de Pista", table_header_style),
            Paragraph("Impacto en Odoo", table_header_style)
        ],
        [
            Paragraph("<b>DSB 451</b>", table_cell_style),
            Paragraph("Surtidores Gilbarco Veeder-Root (SK700, Horizon, etc.)", table_cell_style),
            Paragraph("Two-Wire Current Loop (bucle 20mA activo)", table_cell_style),
            Paragraph("Traduccion transparente a eventos de manguera y litros en Odoo POS.", table_cell_style)
        ],
        [
            Paragraph("<b>DSB 452</b>", table_cell_style),
            Paragraph("Surtidores Tokheim (Quantium, Koppens)", table_cell_style),
            Paragraph("Ka-Loop / Dunclare Current Loop", table_cell_style),
            Paragraph("Permite totalizadores y control de parada/autorizacion desde Odoo.", table_cell_style)
        ],
        [
            Paragraph("<b>DSB 453</b>", table_cell_style),
            Paragraph("Surtidores Wayne Dresser (Global Century, Helix, Ovation)", table_cell_style),
            Paragraph("Wayne DART Protocol / Current Loop / RS-485", table_cell_style),
            Paragraph("Sincronizacion instantanea de importes y precios por producto.", table_cell_style)
        ],
        [
            Paragraph("<b>DSB 454 / 455</b>", table_cell_style),
            Paragraph("Surtidores Cetil, Bennett, Salzkotten, Petrotec", table_cell_style),
            Paragraph("RS-485 / RS-422 configurable multicanal", table_cell_style),
            Paragraph("Integracion homogenea en la misma vista de pista Odoo.", table_cell_style)
        ],
        [
            Paragraph("<b>DSB 461 / 462</b>", table_cell_style),
            Paragraph("Sondas de Nivel ATG (Veeder-Root TLS-350 / 450, OPW, Colibri)", table_cell_style),
            Paragraph("Comunicacion serie RS-232 / bucle de sonda de tanque", table_cell_style),
            Paragraph("Lectura de stock de carburante, temperatura y agua en Odoo Inventario.", table_cell_style)
        ],
        [
            Paragraph("<b>DSB 471</b>", table_cell_style),
            Paragraph("Monolitos de Precios y Totems LED exteriores", table_cell_style),
            Paragraph("Interfaces serie propietarias / Bucle de cartelera", table_cell_style),
            Paragraph("Actualizacion automatica del monolito al cambiar tarifas en Odoo.", table_cell_style)
        ]
    ]

    dsb_table = Table(dsb_table_data, colWidths=[65, 155, 137, 130])
    dsb_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E3A8A")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ("TOPPADDING", (0, 0), (-1, -1), 3.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(dsb_table)
    story.append(Spacer(1, 6))

    # 5. PROTOCOLOS HOST
    story.append(Paragraph("5. Protocolos y Licencias de Software DOMS para Odoo", h1_style))
    story.append(Paragraph(
        "Para que el sistema de software (Odoo / Agente Edge) pueda interactuar con el DOMS, se debe disponer de "
        "una de las siguientes licencias de protocolo activas en la placa CPU:",
        body_style
    ))
    story.append(Paragraph("• <b>1. DOMS PSS Direct Protocol (TCP Socket - Puerto 7000):</b> Protocolo nativo binario de bajisima latencia (< 20ms). Permite recibir eventos en tiempo real (descolgado de manguera, bombeo, importe en directo, corte de suministro y totalizadores inalterables de surtidor). Es el mas eficiente y robusto para TPV.", bullet_style))
    story.append(Paragraph("• <b>2. Estandar IFSF POS Protocol (over TCP/IP - Puerto 4000/4001):</b> Estandar abierto internacional (International Forecourt Standards Forum). Facilita una capa de abstraccion estandarizada para surtidores, precios y sondas de nivel.", bullet_style))
    story.append(Paragraph("• <b>3. DOMS Web Services / XML REST API:</b> Disponible en CPUB 510/520 para interrogacion de auditoria y cierres.", bullet_style))
    story.append(Spacer(1, 5))

    # 6. ARQUITECTURA DE INTEGRACION
    story.append(Paragraph("6. Arquitectura de Integracion con Odoo ERP / POS", h1_style))
    story.append(Paragraph(
        "Para garantizar la estabilidad y el cumplimiento de tiempos reales de pista, la conexion se implementa en 3 capas "
        "mediante un <b>Agente Edge Local</b>:",
        body_style
    ))

    arch_diagram = (
        "+-----------------------------------------------------------------------------+<br/>"
        "|                         SURTIDORES Y TANQUES (PISTA)                        |<br/>"
        "|         Gilbarco · Tokheim · Wayne · Cetil · Sondas Veeder-Root TLS         |<br/>"
        "+--------------------------------------+--------------------------------------+<br/>"
        "                                       | Cableado 20mA Loop / RS-485 / RS-422<br/>"
        "                                       v<br/>"
        "+-----------------------------------------------------------------------------+<br/>"
        "|                 CONTROLADOR DE PISTA: DOMS PSS 5000                         |<br/>"
        "|   - Placa CPU: CPUB 510 o CPUB 520                                          |<br/>"
        "|   - Tarjetas DSB especificas de cada surtidor                               |<br/>"
        "|   - Licencia: PSS TCP Direct Protocol o IFSF TCP/IP                         |<br/>"
        "+--------------------------------------+--------------------------------------+<br/>"
        "                                       | Red Local Ethernet (TCP/IP - Socket 7000 / 4000)<br/>"
        "                                       v<br/>"
        "+-----------------------------------------------------------------------------+<br/>"
        "|                    AGENTE EDGE LOCAL / ODOO IOT BOX                         |<br/>"
        "|   - Hardware: Mini PC Industrial Fanless / Raspberry Pi 4 (Linux)           |<br/>"
        "|   - Agente Daemon Python (Servicio de Pista y Maquina de Estados)          |<br/>"
        "|   - Base de Datos Local de Contingencia (SQLite / PostgreSQL Buffer)        |<br/>"
        "+--------------------------------------+--------------------------------------+<br/>"
        "                                       | WebSockets (WSS) / JSON-RPC (LAN o Cloud)<br/>"
        "                                       v<br/>"
        "+-----------------------------------------------------------------------------+<br/>"
        "|                        CAJA Y TPV: ODOO 17 POS                              |<br/>"
        "|   - Modulo pos_gas_station integrado en TPV tactil                          |<br/>"
        "|   - Autorizacion de repostajes prepago y postpago                           |<br/>"
        "|   - Carga directa del importe y litros a la cesta del ticket                |<br/>"
        "|   - Gestion de clientes de credito, matriculas y flotas                     |<br/>"
        "+-----------------------------------------------------------------------------+"
    )
    story.append(Paragraph(arch_diagram, code_style))

    # Callout offline
    callout_offline = (
        "<b>Garantia de Servicio Continuo y Modo Offline:</b><br/>"
        "El Agente Edge almacena cada repostaje en un buffer local SQLite/PostgreSQL si la conexion con Odoo Cloud cae. "
        "El TPV en caja sigue cobrando suministros via red local. Una vez restablecido el acceso a internet, los repostajes "
        "se sincronizan automaticamente con Odoo ERP sin duplicidades ni perdida de ventas."
    )
    offline_table = Table([[Paragraph(callout_offline, callout_style)]], colWidths=[487])
    offline_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
        ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#059669")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(offline_table)
    story.append(Spacer(1, 5))

    # 7. CHECKLIST
    story.append(Paragraph("7. Checklist de Auditoria de Campo para Gasolineras Existentes", h1_style))
    checklist_data = [
        [Paragraph("<b>Paso</b>", table_header_style), Paragraph("<b>Verificacion Requerida</b>", table_header_style), Paragraph("<b>Criterio de Aceptacion</b>", table_header_style)],
        [Paragraph("1. CPU", table_cell_style), Paragraph("Revisar la serigrafia de la placa CPU en el rack.", table_cell_style), Paragraph("Debe indicar <b>CPUB 510, 511 o 520</b>.", table_cell_style)],
        [Paragraph("2. Red", table_cell_style), Paragraph("Comprobar conector RJ-45 y LED de enlace LAN.", table_cell_style), Paragraph("Asignar IP estatica en el rango LAN de la estacion.", table_cell_style)],
        [Paragraph("3. Licencia", table_cell_style), Paragraph("Verificar protocolo host configurado en DOMS.", table_cell_style), Paragraph("Debe estar activo <b>PSS Direct TCP</b> o <b>IFSF POS</b>.", table_cell_style)],
        [Paragraph("4. Pista", table_cell_style), Paragraph("Comprobar estado de LEDs en tarjetas DSB.", table_cell_style), Paragraph("LEDs de canal en verde / parpadeo de datos activo.", table_cell_style)],
        [Paragraph("5. Edge", table_cell_style), Paragraph("Test de conectividad TCP desde Mini PC / IoT Box.", table_cell_style), Paragraph("Respuesta socket afirmativa en puerto 7000 o 4000.", table_cell_style)],
    ]
    check_table = Table(checklist_data, colWidths=[55, 230, 202])
    check_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E3A8A")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(check_table)

    doc.build(story, canvasmaker=NumberedCanvas)

if __name__ == '__main__':
    output_pdf = '/home/bonilla/Projects/odoo/docs/Compatibilidad_Modelos_DOMS_Odoo.pdf'
    os.makedirs(os.path.dirname(output_pdf), exist_ok=True)
    build_pdf(output_pdf)
    print(f'PDF successfully generated at: {output_pdf}')