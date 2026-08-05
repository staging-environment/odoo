import os
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable, Image
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
            self.draw_page_decorations(num_pages)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def draw_page_decorations(self, page_count):
        self.saveState()
        self.setFont("Helvetica-Bold", 8)
        self.setFillColor(colors.HexColor("#64748B"))
        
        # Header (Páginas > 1)
        if self._pageNumber > 1:
            self.drawString(54, 802, "INFORME TÉCNICO: HARDWARE TPV & PROVEEDORES DE PISTA — ODOO ERP")
            self.setStrokeColor(colors.HexColor("#CBD5E1"))
            self.setLineWidth(0.75)
            self.line(54, 794, 541, 794)
            
        # Footer (Todas las páginas)
        page_text = f"Página {self._pageNumber} de {page_count}"
        self.drawRightString(541, 32, page_text)
        self.drawString(54, 32, "Confidencial — Proyecto Odoo Gasolineras | IP Producción: 164.68.101.69")
        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.setLineWidth(0.75)
        self.line(54, 44, 541, 44)
        self.restoreState()

def generate_pdf():
    brain_dir = "/mnt/c/Users/jarod/.gemini/antigravity-ide/brain/ac5ea77a-138b-4bc6-8520-f29ceb913de8"
    output_pdf = "/home/bonilla/Projects/odoo/docs/informe_tecnico_hardware_tpv_odoo.pdf"
    
    os.makedirs(os.path.dirname(output_pdf), exist_ok=True)
    
    doc = SimpleDocTemplate(
        output_pdf,
        pagesize=A4,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54
    )
    
    styles = getSampleStyleSheet()
    
    # Custom styles
    primary_color = colors.HexColor("#0F172A")
    secondary_color = colors.HexColor("#2563EB")
    accent_color = colors.HexColor("#059669")
    dark_neutral = colors.HexColor("#334155")
    light_bg = colors.HexColor("#F1F5F9")
    
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        textColor=primary_color,
        spaceAfter=8
    )
    
    subtitle_style = ParagraphStyle(
        'DocSubTitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10.5,
        leading=14,
        textColor=secondary_color,
        spaceAfter=12
    )
    
    h1_style = ParagraphStyle(
        'Heading1_Custom',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=13,
        leading=16,
        textColor=primary_color,
        spaceBefore=14,
        spaceAfter=8,
        keepWithNext=True
    )

    body_style = ParagraphStyle(
        'Body_Custom',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=dark_neutral,
        spaceAfter=6
    )
    
    caption_style = ParagraphStyle(
        'Caption_Style',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#475569"),
        alignment=1, # Center
        spaceAfter=8
    )

    table_header_style = ParagraphStyle(
        'TableHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=11,
        textColor=colors.white
    )

    table_cell_style = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=11,
        textColor=dark_neutral
    )

    story = []
    
    # Header Banner Block
    story.append(Paragraph("INFORME TÉCNICO Y DE HARDWARE: INTEGRACIÓN DE ODOO POS EN ESTACIONES DE SERVICIO", title_style))
    story.append(Paragraph("Evaluación de Compatibilidad, Análisis de Instalaciones Existentes, Proveedores de Hardware y Diseño del TPV", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=2, color=secondary_color, spaceBefore=0, spaceAfter=10))

    # Metadata Card Table
    meta_data = [
        [
            Paragraph("<b>Proyecto:</b> Odoo Gasolineras (ERP/TPV)", table_cell_style),
            Paragraph("<b>Fecha:</b> Agosto 2026", table_cell_style),
            Paragraph("<b>Estado:</b> Viable / En Planificación", table_cell_style)
        ],
        [
            Paragraph("<b>Servidor Producción IP:</b> 164.68.101.69", table_cell_style),
            Paragraph("<b>Usuario SSH:</b> developer", table_cell_style),
            Paragraph("<b>Entorno Local:</b> /home/bonilla/Projects/odoo", table_cell_style)
        ]
    ]
    t_meta = Table(meta_data, colWidths=[160, 160, 167])
    t_meta.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), light_bg),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#CBD5E1")),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
        ('PADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(t_meta)
    story.append(Spacer(1, 10))

    # Section 1: Resumen Ejecutivo
    story.append(Paragraph("1. Resumen Ejecutivo y Diagnóstico de Viabilidad", h1_style))
    story.append(Paragraph(
        "La integración del módulo de **Punto de Venta (TPV/POS) de Odoo** para la gestión completa de estaciones de servicio es **totalmente viable**. "
        "Permite unificar en una única plataforma en la nube y local la venta de carburantes a pie de pista, la tienda de conveniencia, la facturación diferida "
        "a clientes flotistas y el control automático de stock en tanques.", body_style
    ))
    story.append(Paragraph(
        "La arquitectura recomendada utiliza un **Microservicio Controlador de Pista (IoT Box / MiniPC)** que traduce las señales del hardware de pista "
        "(bus RS-485 / Bucle de corriente 20mA) a sockets/WebSockets consumibles de forma nativa por la interfaz Owl en el navegador web del TPV de Odoo.", body_style
    ))
    story.append(Spacer(1, 8))

    # Section 2: Análisis del Hardware Existente (Capturas)
    story.append(Paragraph("2. Análisis Técnico de los Equipos en Instalaciones Existentes", h1_style))
    story.append(Paragraph(
        "A partir de las imágenes proporcionadas de las gasolineras en funcionamiento, se ha analizado la infraestructura de red, seguridad y conversores de señal empleados actualmente:", body_style
    ))
    story.append(Spacer(1, 6))

    # Image 1 & Image 2: FortiGate
    img1_path = os.path.join(brain_dir, "media__1785962190895.jpg")
    img2_path = os.path.join(brain_dir, "media__1785962190903.jpg")
    
    img_forti1 = Image(img1_path, width=210, height=140)
    img_forti2 = Image(img2_path, width=210, height=140)

    t_forti = Table([
        [img_forti1, img_forti2],
        [
            Paragraph("<b>Figura 1.1:</b> Frontal Firewall FortiGate 30E", caption_style),
            Paragraph("<b>Figura 1.2:</b> Panel Trasero y Puertos LAN/WAN", caption_style)
        ]
    ], colWidths=[240, 240])
    t_forti.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('PADDING', (0,0), (-1,-1), 2),
    ]))
    story.append(KeepTogether([t_forti]))
    
    story.append(Paragraph(
        "<b>Análisis Fortinet FortiGate 30E:</b> Este equipo garantiza la seguridad perimetral de la gasolinera. Proporciona enrutamiento seguro, aislamiento de la red LAN de cobro (VLAN TPV), conexión VPN cifrada con el servidor Odoo en producción (164.68.101.69) y comunicación segura con pasarelas de pago bancarias (EMV/PINpad).", body_style
    ))
    story.append(Spacer(1, 8))

    # Image 3 & Image 4: Conversores RS485
    img3_path = os.path.join(brain_dir, "media__1785962190918.jpg")
    img4_path = os.path.join(brain_dir, "media__1785962190932.jpg")
    
    img_conv1 = Image(img3_path, width=210, height=140)
    img_conv2 = Image(img4_path, width=210, height=140)

    t_conv = Table([
        [img_conv1, img_conv2],
        [
            Paragraph("<b>Figura 2.1:</b> Conversor RS-485 con Bornera Verde", caption_style),
            Paragraph("<b>Figura 2.2:</b> Puerto Serie DB9 y DIP Switches (SW)", caption_style)
        ]
    ], colWidths=[240, 240])
    t_conv.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('PADDING', (0,0), (-1,-1), 2),
    ]))
    story.append(KeepTogether([t_conv]))

    story.append(Paragraph(
        "<b>Análisis Conversor Serie RS-485 a USB:</b> Es el componente clave de conexión con la pista. "
        "En la bornera verde (pines 1 y 2) se conectan físicamente los cables procedentes de los surtidores (bus diferencial de datos). "
        "Los micro-switches rojos (SW) regulan la impedancia de línea y baudrate. El cable USB transparente transmite las tramas de repostaje en tiempo real al equipo registrador.", body_style
    ))
    story.append(Spacer(1, 8))

    # Image 5: D-Link Hub
    img5_path = os.path.join(brain_dir, "media__1785962190944.jpg")
    img_hub = Image(img5_path, width=180, height=125)
    
    t_hub = Table([
        [img_hub],
        [Paragraph("<b>Figura 3:</b> Hub USB D-Link 7 Puertos Industrial/Sobremesa", caption_style)]
    ], colWidths=[480])
    t_hub.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('PADDING', (0,0), (-1,-1), 2),
    ]))
    story.append(KeepTogether([t_hub]))

    story.append(Paragraph(
        "<b>Análisis Hub USB D-Link:</b> Concentra las conexiones de múltiples conversores de mangueras, impresoras térmicas y lectores de códigos de barra USB hacia un único puerto del PC TPV u Odoo IoT Box.", body_style
    ))
    story.append(Spacer(1, 10))

    # Section 3: Tabla de Compatibilidad Total
    story.append(PageBreak())
    story.append(Paragraph("3. Matriz de Compatibilidad de Sistemas y Hardware", h1_style))
    story.append(Paragraph(
        "Evaluación de compatibilidad directa entre los componentes analizados y el ERP Odoo (v16, v17 y v18):", body_style
    ))
    story.append(Spacer(1, 6))

    comp_headers = [Paragraph("Componente / Sistema", table_header_style), Paragraph("Tipo de Conexión", table_header_style), Paragraph("Compatibilidad Odoo", table_header_style), Paragraph("Detalle de Integración", table_header_style)]
    comp_rows = [
        comp_headers,
        [
            Paragraph("<b>FortiGate 30E Firewall</b>", table_cell_style),
            Paragraph("Ethernet RJ45 / VPN", table_cell_style),
            Paragraph("<font color='#059669'><b>100% Compatible</b></font>", table_cell_style),
            Paragraph("Enrutamiento seguro y VPN IPsec entre la LAN local y el servidor en la nube.", table_cell_style)
        ],
        [
            Paragraph("<b>Conversor RS-485 / USB</b>", table_cell_style),
            Paragraph("USB / Serie (TTY/COM)", table_cell_style),
            Paragraph("<font color='#059669'><b>100% Compatible</b></font>", table_cell_style),
            Paragraph("Mapeado como puerto TTY en Linux/IoT Box con driver `ch341` o `ftdi_sio`.", table_cell_style)
        ],
        [
            Paragraph("<b>Hub USB D-Link 7P</b>", table_cell_style),
            Paragraph("USB 2.0 / 3.0", table_cell_style),
            Paragraph("<font color='#059669'><b>100% Compatible</b></font>", table_cell_style),
            Paragraph("Extensión de puertos para Odoo IoT Box sin necesidad de controladores adicionales.", table_cell_style)
        ],
        [
            Paragraph("<b>Surtidores Cetil</b>", table_cell_style),
            Paragraph("Protocolo Cetil / RS-485", table_cell_style),
            Paragraph("<font color='#059669'><b>Compatible (Vía Driver)</b></font>", table_cell_style),
            Paragraph("Sincronización de descolgado, suministro y totalizadores en tiempo real.", table_cell_style)
        ],
        [
            Paragraph("<b>Surtidores Wayne / Tokheim</b>", table_cell_style),
            Paragraph("Dart / Current Loop / IFSF", table_cell_style),
            Paragraph("<font color='#059669'><b>Compatible (Vía Driver/DOMS)</b></font>", table_cell_style),
            Paragraph("Compatibilidad estándar a través de microservicio o controlador DOMS PSS.", table_cell_style)
        ],
        [
            Paragraph("<b>PinPad Bancario (TPV)</b>", table_cell_style),
            Paragraph("IP Ethernet / USB", table_cell_style),
            Paragraph("<font color='#059669'><b>100% Compatible</b></font>", table_cell_style),
            Paragraph("Integración nativa con pasarelas de pago de Odoo POS (Paytef, Redsys).", table_cell_style)
        ]
    ]

    t_comp = Table(comp_rows, colWidths=[110, 95, 105, 170])
    t_comp.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), primary_color),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, light_bg]),
        ('PADDING', (0,0), (-1,-1), 4),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(t_comp)
    story.append(Spacer(1, 10))

    # Section 4: Imagen del TPV de Odoo
    story.append(Paragraph("4. Diseño y Maqueta Funcional del TPV Odoo para Gasolineras", h1_style))
    story.append(Paragraph(
        "A continuación se presenta la **interfaz diseñada específicamente para el TPV de la nueva gasolinera en Odoo POS**, "
        "optimizada para pantallas táctiles y tiempos de respuesta ultra-rápidos:", body_style
    ))
    story.append(Spacer(1, 6))

    img_mockup_path = os.path.join(brain_dir, "odoo_gas_station_pos_mockup_1785962320212.png")
    img_pos = Image(img_mockup_path, width=460, height=250)
    
    t_pos = Table([
        [img_pos],
        [Paragraph("<b>Figura 4:</b> Maqueta de la Interfaz del TPV Odoo adaptada a Control de Pista y Venta Mixta", caption_style)]
    ], colWidths=[480])
    t_pos.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('PADDING', (0,0), (-1,-1), 2),
    ]))
    story.append(KeepTogether([t_pos]))

    story.append(Paragraph(
        "<b>Puntos Destacados de la Pantalla TPV:</b><br/>"
        "• <b>Panel Superior de Surtidores:</b> Rejilla interactiva con los surtidores (1 a 6). Los surtidores en verde indican llenado activo, los amarillos repostajes pendientes de cobro y los azules vía disponible.<br/>"
        "• <b>Carga con 1 Clic:</b> Pulsar sobre un surtidor finalizado vuelca inmediatamente los litros, producto y precio exacto al ticket actual.<br/>"
        "• <b>Acciones Rápidas de Pista:</b> Botones directos para 'Autorizar Surtidor' (Prepago/Postpago) y 'Bloqueo de Emergencia'.<br/>"
        "• <b>Cobro Flexibilizado:</b> Pago combinado con tarjeta, efectivo, cuenta a crédito corporativa (factura por matrícula) y vales de fidelidad.", body_style
    ))
    story.append(Spacer(1, 10))

    # Section 5: Directores de Proveedores de Hardware
    story.append(PageBreak())
    story.append(Paragraph("5. Directorio de Proveedores de Hardware y Servicios para la Nueva Estación", h1_style))
    story.append(Paragraph(
        "Guía de proveedores clave en España y Europa para la contratación y adquisición del equipamiento de la nueva gasolinera:", body_style
    ))
    story.append(Spacer(1, 6))

    prov_headers = [Paragraph("Categoría", table_header_style), Paragraph("Empresa / Fabricante", table_header_style), Paragraph("Equipos Destacados", table_header_style), Paragraph("Contacto / Cobertura", table_header_style)]
    prov_rows = [
        prov_headers,
        [
            Paragraph("<b>Controladores de Pista / Armarios</b>", table_cell_style),
            Paragraph("<b>DOMS / Gilbarco Veeder-Root</b>", table_cell_style),
            Paragraph("Armarios de pista PSS 5000 / PSS 50. Estándar multi-marca internacional.", table_cell_style),
            Paragraph("gilbarco.com / España & Global", table_cell_style)
        ],
        [
            Paragraph("<b>Surtidores y Automatización</b>", table_cell_style),
            Paragraph("<b>Cetil Dispensing Technology</b>", table_cell_style),
            Paragraph("Surtidores, medidores de caudal y cabezales electrónicos.", table_cell_style),
            Paragraph("cetil.com / Fabricación España", table_cell_style)
        ],
        [
            Paragraph("<b>Sistemas Integrados de Pista</b>", table_cell_style),
            Paragraph("<b>Alvic Software / Aseproda</b>", table_cell_style),
            Paragraph("Concentradores de pista, consolas de control y monolitos de precios.", table_cell_style),
            Paragraph("alvic.com / aseproda.com / España", table_cell_style)
        ],
        [
            Paragraph("<b>Conversores Serie e Industrial</b>", table_cell_style),
            Paragraph("<b>Moxa Europe / Advantech</b>", table_cell_style),
            Paragraph("Conversores RS-485/USB industriales aislados (UPort 1150).", table_cell_style),
            Paragraph("moxa.com / Distribución España", table_cell_style)
        ],
        [
            Paragraph("<b>Seguridad & Redes</b>", table_cell_style),
            Paragraph("<b>Fortinet España</b>", table_cell_style),
            Paragraph("Firewalls FortiGate 40F / 60F para reemplazo o expansión.", table_cell_style),
            Paragraph("fortinet.com / Red Partners España", table_cell_style)
        ],
        [
            Paragraph("<b>Pantallas TPV & Periféricos</b>", table_cell_style),
            Paragraph("<b>Elo Touch / FEC Spain</b>", table_cell_style),
            Paragraph("Monitores táctiles IP54 resistentes a polvo, grasa y líquidos en caja.", table_cell_style),
            Paragraph("elotouch.com / fecpos.es", table_cell_style)
        ]
    ]

    t_prov = Table(prov_rows, colWidths=[105, 110, 155, 110])
    t_prov.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), primary_color),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, light_bg]),
        ('PADDING', (0,0), (-1,-1), 4),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(t_prov)
    story.append(Spacer(1, 10))

    # Section 6: Plan de Trabajo y Siguientes Pasos
    story.append(Paragraph("6. Plan de Trabajo Recomendado", h1_style))
    story.append(Paragraph(
        "<b>Fase 1 (Infraestructura Pista):</b> Encargar el tirado del cable par trenzado RS-485 blindado desde los surtidores hasta la caja TPV.<br/>"
        "<b>Fase 2 (Adquisición Hardware):</b> Adquirir conversor RS485-USB industrial (Moxa o equivalente a las fotos) y MiniPC Odoo IoT Box.<br/>"
        "<b>Fase 3 (Desarrollo Addon):</b> Programar el módulo de integración en la carpeta <code>extra-addons</code> del proyecto Odoo local (<code>/home/bonilla/Projects/odoo</code>).<br/>"
        "<b>Fase 4 (Despliegue Producción):</b> Desplegar en la máquina virtual <code>164.68.101.69</code> e integrar con el firewall FortiGate.", body_style
    ))
    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#CBD5E1"), spaceBefore=4, spaceAfter=8))
    story.append(Paragraph("<i>Documento generado automáticamente para el proyecto Odoo Gasolineras.</i>", caption_style))

    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"PDF generado con éxito en: {output_pdf}")

if __name__ == "__main__":
    generate_pdf()
