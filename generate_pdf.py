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
            self.drawString(54, 800, "Guía Técnica: Integración de Gasolineras y Módulos en Odoo 17")
            self.setStrokeColor(colors.HexColor("#CBD5E1"))
            self.setLineWidth(0.5)
            self.line(54, 792, 541, 792)
            
        # Footer
        page_text = f"Página {self._pageNumber} de {page_count}"
        self.drawRightString(541, 36, page_text)
        self.drawString(54, 36, "Documentación Oficial - Proyecto Odoo 17 Staging")
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

    story = []

    # Title Banner
    story.append(Paragraph("Guía Técnica: Integración de Gasolineras y Desarrollo de Módulos Custom en Odoo 17", title_style))
    story.append(Paragraph("Arquitectura Forecourt Controller (FCC), IoT Box Edge, Gestión de Módulos y Desarrollo de Addons", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#2563EB'), spaceAfter=12))

    # SECTION 1
    story.append(Paragraph("1. Arquitectura de Integración de Surtidores de Gasolinera", h1_style))
    story.append(Paragraph(
        "Para integrar estaciones de servicio con Odoo 17 se utiliza una arquitectura en 3 capas que conecta el hardware físico de la pista de servicio con los módulos de <b>Point of Sale (POS)</b> e <b>Inventario (Stock)</b> de Odoo.",
        body_style
    ))

    # Architecture diagram with clean ASCII characters
    diagram_text = (
        "+--------------------------------------------------------+<br/>"
        "|             SURTIDORES DE COMBUSTIBLE                  |<br/>"
        "|       (Gilbarco / Tokheim / Wayne / Cetil)             |<br/>"
        "+--------------------------+-----------------------------+<br/>"
        "                           | Protocolo RS-485 / IFSF / Loop<br/>"
        "                           v<br/>"
        "+--------------------------------------------------------+<br/>"
        "|     CONTROLADOR DE PISTA / FORECOURT CONTROLLER        |<br/>"
        "|        (Ej: DOMS PSS 5000 / Alvesa / Concentrador)     |<br/>"
        "+--------------------------+-----------------------------+<br/>"
        "                           | TCP/IP / API Local (Serial/Ethernet)<br/>"
        "                           v<br/>"
        "+--------------------------------------------------------+<br/>"
        "|          AGENTE EDGE / ODOO IOT BOX (PYTHON)           |<br/>"
        "|    - Servicio Daemon local en la estacion              |<br/>"
        "|    - Escucha eventos de manguera (Descolgada/Servida)  |<br/>"
        "|    - Envia autorizaciones de suministro                |<br/>"
        "+--------------------------+-----------------------------+<br/>"
        "                           | WebSockets / JSON-RPC (HTTPS)<br/>"
        "                           v<br/>"
        "+--------------------------------------------------------+<br/>"
        "|                    ODOO 17 ERP                         |<br/>"
        "|  - Modulo pos_gas_station (TPV)                        |<br/>"
        "|  - Modulo stock_tank_management (Control Tanques)     |<br/>"
        "+--------------------------------------------------------+"
    )
    story.append(Paragraph(diagram_text, code_style))

    story.append(Paragraph("1.1 Flujos de Operación en Pista", h2_style))
    story.append(Paragraph("<b>A. Post-Pago (Servicio Atendido):</b>", body_style))
    story.append(Paragraph("• El cliente llena el depósito en el surtidor.", bullet_style))
    story.append(Paragraph("• El <b>Controlador de Pista (FCC)</b> registra los litros, manguera e importe total.", bullet_style))
    story.append(Paragraph("• El <b>Agente Edge</b> recibe el evento final y envía una notificación WebSocket a Odoo.", bullet_style))
    story.append(Paragraph("• El <b>TPV de Odoo (POS)</b> muestra la manguera activada con la venta pendiente.", bullet_style))
    story.append(Paragraph("• El cajero pulsa sobre la venta en pantalla, se carga en el ticket y se cobra.", bullet_style))
    story.append(Paragraph("• Odoo descuenta los litros del tanque correspondiente en el módulo de Inventario.", bullet_style))

    story.append(Paragraph("<b>B. Pre-Pago (Autoservicio / Desatendido):</b>", body_style))
    story.append(Paragraph("• El cliente abona un importe determinado (ej. 50€) en caja o terminal.", bullet_style))
    story.append(Paragraph("• Odoo envía una orden de autorización al Agente Edge: <i>'Autorizar Manguera N por máximo 50€'</i>.", bullet_style))
    story.append(Paragraph("• El Agente Edge transmite el comando al Controlador de Pista (FCC).", bullet_style))
    story.append(Paragraph("• El surtidor se activa y corta automáticamente al llegar al límite configurado.", bullet_style))
    story.append(Paragraph("• Al terminar el suministro, Odoo ajusta el importe definitivo consumido.", bullet_style))

    story.append(Paragraph("1.2 Modelos de Datos Principales en Odoo", h2_style))
    story.append(Paragraph("• <b>gas.station.tank:</b> Control de tanques de almacenamiento (capacidad, stock actual, sondas).", bullet_style))
    story.append(Paragraph("• <b>gas.station.dispenser:</b> Identificación física de surtidores en pista.", bullet_style))
    story.append(Paragraph("• <b>gas.station.nozzle:</b> Asociación entre mangueras, tipos de combustible (Producto Odoo) y tanques.", bullet_style))

    story.append(Spacer(1, 8))

    # SECTION 2
    story.append(Paragraph("2. Mecanismo para Activar / Desactivar Módulos en Odoo 17", h1_style))
    story.append(Paragraph("2.1 Vía Interfaz Web (UI)", h2_style))
    story.append(Paragraph("1. <b>Activar Modo Desarrollador:</b> Ve a <i>Ajustes -> Activar modo desarrollador</i> (o añade <code>?debug=1</code> a la URL).", bullet_style))
    story.append(Paragraph("2. <b>Actualizar Lista de Aplicaciones:</b> Ve a <i>Aplicaciones -> Actualizar lista de aplicaciones</i> y confirma.", bullet_style))
    story.append(Paragraph("3. <b>Instalar/Activar Módulo:</b> En la barra de búsqueda de Aplicaciones, <b>elimina el filtro por defecto 'Aplicaciones'</b> (icono 'x'). Busca el nombre técnico del módulo (ej: <code>pos_gas_station</code>) y pulsa <b>Instalar</b>.", bullet_style))
    story.append(Paragraph("4. <b>Desactivar/Desinstalar Módulo:</b> Entra al detalle del módulo y selecciona <b>Desinstalar</b>.", bullet_style))

    story.append(Paragraph("2.2 Vía Línea de Comandos (CLI / DDEV)", h2_style))
    cli_code = (
        "# 1. Instalar un nuevo modulo<br/>"
        "ddev exec odoo -c /etc/odoo/odoo.conf -d db -i pos_gas_station --stop-after-init<br/><br/>"
        "# 2. Actualizar un modulo tras modificar codigo<br/>"
        "ddev exec odoo -c /etc/odoo/odoo.conf -d db -u pos_gas_station --stop-after-init<br/><br/>"
        "# 3. Desinstalar un modulo<br/>"
        "ddev exec odoo -c /etc/odoo/odoo.conf -d db --uninstall=pos_gas_station --stop-after-init"
    )
    story.append(Paragraph(cli_code, code_style))

    story.append(Spacer(1, 8))

    # SECTION 3
    story.append(Paragraph("3. Guía de Desarrollo de Módulos Custom en Odoo 17", h1_style))
    story.append(Paragraph("Todos los módulos personalizados deben alojarse dentro de la carpeta <code>./extra-addons/</code> del repositorio.", body_style))
    
    story.append(Paragraph("3.1 Estructura Estándar de Archivos", h2_style))
    tree_text = (
        "extra-addons/pos_gas_station/<br/>"
        "+-- __init__.py<br/>"
        "+-- __manifest__.py<br/>"
        "+-- models/<br/>"
        "|   +-- __init__.py<br/>"
        "|   +-- dispenser.py<br/>"
        "|   +-- tank.py<br/>"
        "+-- security/<br/>"
        "|   +-- ir.model.access.csv<br/>"
        "+-- views/<br/>"
        "    +-- dispenser_views.xml<br/>"
        "    +-- tank_views.xml"
    )
    story.append(Paragraph(tree_text, code_style))

    story.append(Paragraph("3.2 Código Paso a Paso", h2_style))
    
    story.append(Paragraph("<b>A. Archivo __manifest__.py</b>", body_style))
    manifest_code = (
        "{\n"
        "    'name': 'Gestion de Gasolineras y Surtidores',\n"
        "    'version': '17.0.1.0.0',\n"
        "    'category': 'Point of Sale',\n"
        "    'summary': 'Integracion de surtidores, mangueras y tanques con Odoo 17 POS',\n"
        "    'author': 'Tu Empresa / Developer',\n"
        "    'depends': ['base', 'point_of_sale', 'stock'],\n"
        "    'data': [\n"
        "        'security/ir.model.access.csv',\n"
        "        'views/dispenser_views.xml',\n"
        "    ],\n"
        "    'installable': True,\n"
        "    'application': True,\n"
        "}"
    )
    story.append(Paragraph(manifest_code.replace('\n', '<br/>').replace(' ', '&nbsp;'), code_style))

    story.append(Paragraph("<b>B. Modelos Python (models/dispenser.py)</b>", body_style))
    py_code = (
        "from odoo import models, fields\n\n"
        "class GasStationDispenser(models.Model):\n"
        "    _name = 'gas.station.dispenser'\n"
        "    _description = 'Surtidor de Gasolinera'\n\n"
        "    name = fields.Char(string='Nombre Surtidor', required=True)\n"
        "    code = fields.Char(string='Codigo Pista (FCC)', required=True)\n"
        "    active = fields.Boolean(string='Activo', default=True)\n"
        "    nozzle_ids = fields.One2many('gas.station.nozzle', 'dispenser_id', string='Mangueras')\n"
    )
    story.append(Paragraph(py_code.replace('\n', '<br/>').replace(' ', '&nbsp;'), code_style))

    story.append(Paragraph("<b>C. Permisos de Seguridad (security/ir.model.access.csv)</b>", body_style))
    csv_code = (
        "id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink<br/>"
        "access_gas_dispenser_user,access.gas.dispenser.user,model_gas_station_dispenser,base.group_user,1,1,1,1<br/>"
        "access_gas_nozzle_user,access.gas.nozzle.user,model_gas_station_nozzle,base.group_user,1,1,1,1"
    )
    story.append(Paragraph(csv_code, code_style))

    story.append(Paragraph("4. Ciclo de Despliegue a Producción", h1_style))
    deploy_callout = (
        "<b>Pasos para desplegar un nuevo módulo:</b><br/>"
        "1. Escribir el código dentro de <code>./extra-addons/mi_modulo</code>.<br/>"
        "2. Probar e instalar localmente con <code>ddev exec odoo ... -i mi_modulo</code>.<br/>"
        "3. Hacer <code>git add</code>, <code>git commit</code> y <code>git push origin main</code>.<br/>"
        "4. En el servidor ejecutar <code>git pull origin main</code> e instalar/reiniciar Odoo."
    )
    story.append(Paragraph(deploy_callout, callout_style))

    doc.build(story, canvasmaker=NumberedCanvas)

if __name__ == "__main__":
    pdf_path = os.path.abspath("docs/Guia_Integracion_Gasolineras_Odoo17.pdf")
    os.makedirs(os.path.dirname(pdf_path), exist_ok=True)
    create_pdf(pdf_path)
    print(f"PDF successfully generated at: {pdf_path}")
