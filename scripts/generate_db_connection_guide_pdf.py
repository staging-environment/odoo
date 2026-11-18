import os
import sys
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
            self.draw_page_decorations(num_pages)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def draw_page_decorations(self, page_count):
        self.saveState()
        self.setFont("Helvetica-Bold", 8)
        self.setFillColor(colors.HexColor("#64748B"))
        
        # Header (Páginas > 1)
        if self._pageNumber > 1:
            self.drawString(48, 804, "GUÍA TÉCNICA: CONEXIÓN A BASES DE DATOS DE PRODUCCIÓN (LECTURA Y ESCRITURA)")
            self.setStrokeColor(colors.HexColor("#CBD5E1"))
            self.setLineWidth(0.75)
            self.line(48, 796, 547, 796)
            
        # Footer (Todas las páginas)
        page_text = f"Página {self._pageNumber} de {page_count}"
        self.drawRightString(547, 28, page_text)
        self.drawString(48, 28, "Confidencial — Utrecar S.L. & Trieste S.L. | Servidor Producción: 10.8.0.1 (VPN WireGuard)")
        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.setLineWidth(0.75)
        self.line(48, 40, 547, 40)
        self.restoreState()

def generate_pdf():
    output_pdf = "/home/bonilla/Projects/odoo/docs/Guia_Conexion_Bases_Datos_Produccion_Utrecar.pdf"
    os.makedirs(os.path.dirname(output_pdf), exist_ok=True)
    
    doc = SimpleDocTemplate(
        output_pdf,
        pagesize=A4,
        leftMargin=48,
        rightMargin=48,
        topMargin=44,
        bottomMargin=46
    )
    
    styles = getSampleStyleSheet()
    
    # Colores corporativos
    c_primary = colors.HexColor("#0F172A")       # Slate 900
    c_secondary = colors.HexColor("#1E40AF")     # Blue 800
    c_accent_green = colors.HexColor("#059669")  # Emerald 600
    c_dark_text = colors.HexColor("#1E293B")     # Slate 800
    c_muted_text = colors.HexColor("#64748B")    # Slate 500
    c_bg_light = colors.HexColor("#F8FAFC")      # Slate 50
    c_bg_card = colors.HexColor("#EFF6FF")       # Blue 50
    c_border = colors.HexColor("#CBD5E1")        # Slate 300
    c_code_bg = colors.HexColor("#0F172A")       # Dark code box

    # Estilos tipográficos
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        textColor=c_primary,
        spaceAfter=2
    )
    
    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10.5,
        leading=14,
        textColor=c_secondary,
        spaceAfter=8
    )

    h1_style = ParagraphStyle(
        'Heading1_Custom',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=15,
        textColor=c_primary,
        spaceBefore=10,
        spaceAfter=5,
        keepWithNext=True
    )

    h2_style = ParagraphStyle(
        'Heading2_Custom',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=13,
        textColor=c_secondary,
        spaceBefore=7,
        spaceAfter=3,
        keepWithNext=True
    )

    body_style = ParagraphStyle(
        'Body_Custom',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=12,
        textColor=c_dark_text,
        spaceAfter=4
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
        fontSize=7.5,
        leading=9.5,
        textColor=c_dark_text
    )

    table_cell_code = ParagraphStyle(
        'TableCellCode',
        parent=table_cell_style,
        fontName='Courier-Bold',
        fontSize=7.5,
        leading=9.5,
        textColor=colors.HexColor("#0369A1")
    )

    code_box_style = ParagraphStyle(
        'CodeBox',
        parent=styles['Normal'],
        fontName='Courier',
        fontSize=7.5,
        leading=10.5,
        textColor=colors.HexColor("#E2E8F0"),
        spaceBefore=2,
        spaceAfter=2
    )

    callout_text = ParagraphStyle(
        'CalloutText',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor("#1E3A8A")
    )

    story = []

    # =========================================================================
    # PÁGINA 1: CABECERA + PROPÓSITO + VPN WIREGUARD COMPLETA
    # =========================================================================
    badge_vpn = "<font color='#2563EB'><b>VPN WireGuard</b></font>"
    badge_rw = "<font color='#059669'><b>READ / WRITE (Lectura y Escritura)</b></font>"
    header_table_data = [
        [
            Paragraph("<b>Utrecar S.L. &amp; Trieste S.L.</b>", title_style),
            Paragraph(f"<div align='right'>{badge_vpn} &nbsp;|&nbsp; {badge_rw}<br/><font color='#64748B' size='8'>Fecha: 18 de Noviembre de 2026</font></div>", styles['Normal'])
        ],
        [
            Paragraph("Guía de Conexión a Bases de Datos de Producción (DBeaver / Clientes SQL)", subtitle_style),
            Paragraph("<div align='right'><font color='#059669' size='8'><b>● Servidor Operativo: 10.8.0.1</b></font></div>", styles['Normal'])
        ]
    ]
    t_top = Table(header_table_data, colWidths=[335, 164])
    t_top.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 1),
        ('TOPPADDING', (0,0), (-1,-1), 1),
    ]))
    story.append(t_top)
    story.append(HRFlowable(width="100%", thickness=1.5, color=c_secondary, spaceBefore=2, spaceAfter=8))

    purpose_content = [
        [
            Paragraph(
                "<b>Propósito del documento:</b> Esta guía proporciona los datos técnicos, credenciales y pasos "
                "necesarios para conectarse mediante <b>DBeaver Community</b> a los entornos de bases de datos de producción "
                "(MySQL, MariaDB y PostgreSQL) con permisos completos de <b>lectura y escritura</b>. Todo el tráfico requiere "
                "conexión previa al túnel VPN corporativo WireGuard.",
                callout_text
            )
        ]
    ]
    t_purpose = Table(purpose_content, colWidths=[499])
    t_purpose.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), c_bg_card),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#93C5FD")),
        ('LEFTPADDING', (0,0), (-1,-1), 10),
        ('RIGHTPADDING', (0,0), (-1,-1), 10),
        ('TOPPADDING', (0,0), (-1,-1), 7),
        ('BOTTOMPADDING', (0,0), (-1,-1), 7),
    ]))
    story.append(t_purpose)
    story.append(Spacer(1, 10))

    story.append(Paragraph("1. Configuración de la VPN (WireGuard)", h1_style))
    story.append(Paragraph(
        "Para acceder a cualquier base de datos es <b>obligatorio</b> estar conectado a la VPN corporativa. "
        "Se ha configurado y habilitado el túnel con IP fija asignada en el servidor de producción.",
        body_style
    ))

    story.append(Paragraph("<b>1.1 Instalación de WireGuard</b>", h2_style))
    story.append(Paragraph(
        "1. Descarga e instala el cliente oficial de WireGuard según tu sistema operativo desde: <b>https://www.wireguard.com/install/</b><br/>"
        "2. Abre la aplicación WireGuard y pulsa en <b>'Añadir túnel'</b> (o <i>Add Tunnel</i>).",
        body_style
    ))

    story.append(Paragraph("<b>1.2 Parámetros del perfil: <code>Sin-Nombre.conf</code></b>", h2_style))
    story.append(Paragraph(
        "Guarda el siguiente bloque en un archivo de texto llamado <code>Sin-Nombre.conf</code> o impórtalo directamente en la aplicación:",
        body_style
    ))

    wg_code = """[Interface]
PrivateKey = iHK+VIzEbl3b1LsPqMO7MUwGq4jwaAFYanQKSn2SbWE=
Address = 10.8.0.15/24
DNS = 1.1.1.1, 8.8.8.8

[Peer]
PublicKey = mFiR5S6GBUPOBLCnQ1JpRtrnukWL1o6UfzXjXzE4Qy4=
PresharedKey = q3KLowPJ9tfCTu4GHbhIiqpS2eR0u8Kykf6ccNBAoIE=
AllowedIPs = 10.8.0.0/24, 164.68.101.69/32
Endpoint = 164.68.101.69:51820
PersistentKeepalive = 25"""

    t_code = Table([[Paragraph(wg_code.replace("\n", "<br/>"), code_box_style)]], colWidths=[499])
    t_code.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), c_code_bg),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#334155")),
        ('LEFTPADDING', (0,0), (-1,-1), 10),
        ('RIGHTPADDING', (0,0), (-1,-1), 10),
        ('TOPPADDING', (0,0), (-1,-1), 7),
        ('BOTTOMPADDING', (0,0), (-1,-1), 7),
    ]))
    story.append(t_code)
    story.append(Spacer(1, 6))

    note_allowed_ips = [
        [
            Paragraph(
                "<b>Importante sobre AllowedIPs:</b> La configuración enruta exclusivamente el tráfico hacia la subred de la VPN "
                "(<code>10.8.0.0/24</code>) y la IP del servidor de producción (<code>164.68.101.69/32</code>). "
                "Tu navegación general por Internet continuará por tu conexión habitual sin verse afectada.",
                body_style
            )
        ]
    ]
    t_nip = Table(note_allowed_ips, colWidths=[499])
    t_nip.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#FEF3C7")),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#FCD34D")),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(t_nip)
    story.append(Spacer(1, 8))

    story.append(Paragraph("<b>1.3 Activación y comprobación de enlace</b>", h2_style))
    story.append(Paragraph(
        "1. En la ventana de WireGuard, selecciona el túnel <b>Sin-Nombre</b> y pulsa <b>Activar</b>.<br/>"
        "2. Abre un terminal (PowerShell o CMD en Windows, o Terminal en Mac/Linux) y comprueba la conectividad con el servidor central:<br/>"
        "&nbsp;&nbsp;&nbsp;&nbsp;<code>ping 10.8.0.1</code><br/>"
        "Si recibes respuesta con 0% de pérdidas, el túnel está operativo.",
        body_style
    ))

    # =========================================================================
    # PÁGINA 2: INSTALACIÓN DBEAVER + TABLA MAESTRA DE TODAS LAS BASES DE DATOS
    # =========================================================================
    story.append(PageBreak())
    story.append(Paragraph("2. Instalación de DBeaver Community", h1_style))
    story.append(Paragraph(
        "<b>DBeaver Community</b> es un gestor universal de bases de datos gratuito y compatible con MySQL, MariaDB y PostgreSQL.<br/>"
        "1. Descarga el instalador desde la web oficial: <b>https://dbeaver.io/download/</b><br/>"
        "2. Instala la aplicación siguiendo el asistente estándar por defecto.",
        body_style
    ))
    story.append(Spacer(1, 6))

    story.append(Paragraph("3. Credenciales y Parámetros de Conexión en DBeaver", h1_style))
    story.append(Paragraph(
        "Una vez activada la VPN WireGuard, el servidor de bases de datos es siempre la IP de la VPN: <b><code>10.8.0.1</code></b>. "
        "A continuación se detallan las 7 instancias de base de datos activas en <code>/home/developer/Projects</code> "
        "con sus puertos mapeados y credenciales con permisos plenos de <b>lectura y escritura</b>:",
        body_style
    ))
    story.append(Spacer(1, 4))

    db_table_data = [
        [
            Paragraph("Entorno / Proyecto", table_header_style),
            Paragraph("Motor", table_header_style),
            Paragraph("Puerto", table_header_style),
            Paragraph("Base de Datos", table_header_style),
            Paragraph("Usuario", table_header_style),
            Paragraph("Contraseña", table_header_style),
            Paragraph("Permisos", table_header_style)
        ],
        [
            Paragraph("<b>Utrecar DBs</b><br/><font color='#64748B'>Aseproda Histórico</font>", table_cell_style),
            Paragraph("MySQL 5.5", table_cell_style),
            Paragraph("<b>33061</b>", table_cell_code),
            Paragraph("virtusgesnet<br/>administracioncorporativa<br/>sii", table_cell_code),
            Paragraph("read_utrecardbs", table_cell_code),
            Paragraph("Utr#DbRead_2026!k9", table_cell_code),
            Paragraph("<font color='#059669'><b>Lectura y Escritura</b><br/>(ALL PRIVILEGES)</font>", table_cell_style)
        ],
        [
            Paragraph("<b>Admin-Platform</b><br/><font color='#64748B'>Laravel Central</font>", table_cell_style),
            Paragraph("MariaDB 10.11", table_cell_style),
            Paragraph("<b>33062</b>", table_cell_code),
            Paragraph("db", table_cell_code),
            Paragraph("read_adminplatform", table_cell_code),
            Paragraph("Adm#PlatRead_2026!v3", table_cell_code),
            Paragraph("<font color='#059669'><b>Lectura y Escritura</b><br/>(ALL PRIVILEGES)</font>", table_cell_style)
        ],
        [
            Paragraph("<b>Odoo 17 ERP</b><br/><font color='#64748B'>ERP &amp; TPV Pista</font>", table_cell_style),
            Paragraph("PostgreSQL 15", table_cell_style),
            Paragraph("<b>54320</b>", table_cell_code),
            Paragraph("odoo", table_cell_code),
            Paragraph("read_odoo", table_cell_code),
            Paragraph("Odoo#Read_2026!z8", table_cell_code),
            Paragraph("<font color='#059669'><b>Lectura y Escritura</b><br/>(CRUD Completo)</font>", table_cell_style)
        ],
        [
            Paragraph("<b>Windows Virtusgesnet</b><br/><font color='#64748B'>Aseproda Windows</font>", table_cell_style),
            Paragraph("MariaDB 11.8", table_cell_style),
            Paragraph("<b>33063</b>", table_cell_code),
            Paragraph("db", table_cell_code),
            Paragraph("read_winvirtus", table_cell_code),
            Paragraph("Win#VirtRead_2026!m2", table_cell_code),
            Paragraph("<font color='#059669'><b>Lectura y Escritura</b><br/>(ALL PRIVILEGES)</font>", table_cell_style)
        ],
        [
            Paragraph("<b>Status Utrecar</b><br/><font color='#64748B'>Monitor Gasolineras</font>", table_cell_style),
            Paragraph("MariaDB 10.11", table_cell_style),
            Paragraph("<b>33064</b>", table_cell_code),
            Paragraph("db", table_cell_code),
            Paragraph("read_statusutr", table_cell_code),
            Paragraph("Stat#UtrRead_2026!p7", table_cell_code),
            Paragraph("<font color='#059669'><b>Lectura y Escritura</b><br/>(ALL PRIVILEGES)</font>", table_cell_style)
        ],
        [
            Paragraph("<b>Pre Admin-Platform</b><br/><font color='#64748B'>Staging / Pruebas</font>", table_cell_style),
            Paragraph("MariaDB 10.11", table_cell_style),
            Paragraph("<b>33065</b>", table_cell_code),
            Paragraph("db", table_cell_code),
            Paragraph("read_preadmin", table_cell_code),
            Paragraph("Pre#PlatRead_2026!v4", table_cell_code),
            Paragraph("<font color='#059669'><b>Lectura y Escritura</b><br/>(ALL PRIVILEGES)</font>", table_cell_style)
        ],
        [
            Paragraph("<b>Rentacar ES</b><br/><font color='#64748B'>Alquiler Vehículos</font>", table_cell_style),
            Paragraph("MariaDB 11.8", table_cell_style),
            Paragraph("<b>33066</b>", table_cell_code),
            Paragraph("db", table_cell_code),
            Paragraph("read_rentacar", table_cell_code),
            Paragraph("Rent#CarRead_2026!b5", table_cell_code),
            Paragraph("<font color='#059669'><b>Lectura y Escritura</b><br/>(ALL PRIVILEGES)</font>", table_cell_style)
        ]
    ]

    t_db = Table(db_table_data, colWidths=[92, 58, 42, 90, 85, 78, 54])
    t_db.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), c_primary),
        ('GRID', (0,0), (-1,-1), 0.5, c_border),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, c_bg_light]),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ('LEFTPADDING', (0,0), (-1,-1), 4),
        ('RIGHTPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(t_db)
    story.append(Spacer(1, 10))

    note_rw_status = [
        [
            Paragraph(
                "<b>Estado de Privilegios:</b> Todos los usuarios de la tabla cuentan con permisos activos para ejecutar "
                "<code>SELECT</code>, <code>INSERT</code>, <code>UPDATE</code>, <code>DELETE</code>, <code>CREATE</code> y "
                "<code>ALTER</code> en sus respectivas bases de datos. No se requiere solicitar permisos adicionales para "
                "realizar inserciones, actualizaciones o correcciones de datos.",
                body_style
            )
        ]
    ]
    t_nrw = Table(note_rw_status, colWidths=[499])
    t_nrw.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#ECFDF5")),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#A7F3D0")),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(t_nrw)

    # =========================================================================
    # PÁGINA 3: DESCRIPCIÓN DE PROYECTOS + PASO A PASO DBEAVER
    # =========================================================================
    story.append(PageBreak())
    story.append(Paragraph("4. Descripción Técnica de las Bases de Datos", h1_style))
    story.append(Paragraph(
        "Resumen funcional de cada entorno ubicado en <code>/home/developer/Projects</code>:",
        body_style
    ))

    p_desc = [
        ("• Utrecar DBs (Históricas Aseproda - Puerto 33061):",
         "Aloja las bases de datos históricas de Aseproda: <code>virtusgesnet</code> (clientes, proveedores, facturas y tickets oficiales series FR/FT/FC, facturas de compras y aforos de combustible), <code>administracioncorporativa</code> (usuarios y empresas) y <code>sii</code> (histórico fiscal de envíos a la AEAT)."),
        ("• Admin-Platform (Laravel Central - Puerto 33062):",
         "Base de datos de la plataforma administrativa corporativa (<code>utrecar.com/admin</code>). Gestiona cuadrantes laborales, empleados, partes de trabajo, estaciones de servicio y matriz de permisos Spatie (incluyendo el permiso <code>acceso_odoo</code>)."),
        ("• Odoo 17 ERP (Gasolineras - Puerto 54320):",
         "Base de datos PostgreSQL del ERP y TPV de pista (<code>odoo.utrecar.com</code>). Tablas clave en esquema <code>public</code>: <code>pos_order</code> (suministros y ventas), <code>pos_session</code> (turnos), <code>res_partner</code> (clientes asignados por estación), <code>account_move</code> (facturas electrónicas) y <code>product_template</code>."),
        ("• Windows Virtusgesnet (Puerto 33063):",
         "Instancia MariaDB del entorno virtualizado Windows VirtusGesNet para pruebas de compatibilidad y migración de datos."),
        ("• Status Utrecar (Monitor Pistas - Puerto 33064):",
         "Base de datos del monitor en tiempo real (<code>status.utrecar.com</code>). Registra pings y disponibilidad de las gasolineras por VPN: Repsol (<code>10.8.0.18</code>), Ronda Norte (<code>10.8.0.6</code>), Vistalegre (<code>10.8.0.11</code>) y El Cuervo (<code>10.8.0.9</code>)."),
        ("• Pre Admin-Platform (Staging - Puerto 33065):",
         "Entorno de pruebas y pre-producción de Admin-Platform para validar cambios de esquema antes de desplegar en producción."),
        ("• Rentacar ES (Puerto 33066):",
         "Base de datos de gestión de reservas de vehículos, contratos, clientes, conductores y tarifas por temporada.")
    ]
    for h, b in p_desc:
        story.append(Paragraph(f"<b>{h}</b> {b}", body_style))

    story.append(Spacer(1, 6))
    story.append(Paragraph("5. Paso a Paso para Conectar en DBeaver", h1_style))

    story.append(Paragraph("<b>5.1 Conexión a MariaDB / MySQL (Ej: Admin-Platform o Utrecar DBs):</b>", h2_style))
    story.append(Paragraph(
        "1. En DBeaver, haz clic en el menú superior: <b>Base de datos ➔ Nueva conexión</b> (icono de enchufe con <code>+</code>).<br/>"
        "2. Selecciona <b>MariaDB</b> (o <b>MySQL</b> para Utrecar DBs) y pulsa <b>Siguiente</b>.<br/>"
        "3. Rellena los campos:<br/>"
        "&nbsp;&nbsp;&nbsp;&nbsp;• <b>Host / Servidor:</b> <code>10.8.0.1</code><br/>"
        "&nbsp;&nbsp;&nbsp;&nbsp;• <b>Puerto:</b> <code>33062</code> (o el puerto del proyecto)<br/>"
        "&nbsp;&nbsp;&nbsp;&nbsp;• <b>Base de datos:</b> <code>db</code> (o <code>virtusgesnet</code>)<br/>"
        "&nbsp;&nbsp;&nbsp;&nbsp;• <b>Nombre de usuario:</b> <code>read_adminplatform</code> (o el usuario de la tabla)<br/>"
        "&nbsp;&nbsp;&nbsp;&nbsp;• <b>Contraseña:</b> <code>Adm#PlatRead_2026!v3</code> (según tabla)<br/>"
        "4. En la pestaña <b>Propiedades del controlador (Driver properties)</b>, verifica <code>allowPublicKeyRetrieval = TRUE</code> y <code>useSSL = FALSE</code>.<br/>"
        "5. Pulsa en <b>'Probar conexión'</b> (si solicita descargar el driver JDBC, pulsa 'Descargar').<br/>"
        "6. Aparecerá el mensaje de éxito <code>Conectado</code>. Pulsa <b>Finalizar</b>.",
        body_style
    ))

    story.append(Paragraph("<b>5.2 Conexión a PostgreSQL (Odoo 17 ERP):</b>", h2_style))
    story.append(Paragraph(
        "1. Haz clic en <b>Base de datos ➔ Nueva conexión</b> y selecciona <b>PostgreSQL</b>.<br/>"
        "2. Rellena los campos: <b>Host:</b> <code>10.8.0.1</code> &nbsp;|&nbsp; <b>Puerto:</b> <code>54320</code> &nbsp;|&nbsp; <b>Base de datos:</b> <code>odoo</code> &nbsp;|&nbsp; <b>Usuario:</b> <code>read_odoo</code> &nbsp;|&nbsp; <b>Contraseña:</b> <code>Odoo#Read_2026!z8</code>.<br/>"
        "3. Pulsa <b>'Probar conexión'</b> y tras confirmar, pulsa <b>Finalizar</b>.<br/>"
        "4. En el árbol de navegación izquierdo, despliega: <code>odoo ➔ Esquemas ➔ public ➔ Tablas</code>.",
        body_style
    ))

    # =========================================================================
    # PÁGINA 4: PROTOCOLO DE ESCRITURA, SEGURIDAD Y FAQ
    # =========================================================================
    story.append(PageBreak())
    story.append(Paragraph("6. Protocolo de Seguridad en Operaciones de Escritura", h1_style))
    story.append(Paragraph(
        "Al contar con <b>permisos de escritura directos</b> sobre bases de datos de producción real, "
        "es fundamental aplicar las siguientes buenas prácticas para garantizar la estabilidad e integridad de los datos:",
        body_style
    ))

    proto = [
        "• <b>Modo Manual Commit (Recomendado):</b> En DBeaver, cambia el modo de confirmación en la barra superior de <i>Auto-commit</i> a <b>Manual Commit</b>. De esta forma, cualquier <code>UPDATE</code> o <code>DELETE</code> no se consolidará hasta que pulses explícitamente el botón <i>Commit</i>.",
        "• <b>Uso de Transacciones Explícitas:</b> Al realizar cambios en múltiples tablas, encapsula la operativa con <code>START TRANSACTION;</code> ... <code>COMMIT;</code> (o <code>ROLLBACK;</code> si detectas un error).",
        "• <b>Comprobación previa con SELECT:</b> Antes de ejecutar un <code>UPDATE</code> o <code>DELETE</code>, ejecuta la misma condición con <code>SELECT * FROM tabla WHERE ...</code> para asegurarte de que solo afectará a las filas deseadas.",
        "• <b>Cuidado con Claves Foráneas en Odoo:</b> Odoo 17 cuenta con restricciones estrictas de integridad referencial. Nunca elimines registros contables o de pedidos de venta mediante <code>DELETE</code> directo sin validar sus relaciones.",
        "• <b>Copias de Seguridad Diarias:</b> El servidor cuenta con volcados automáticos nocturnos en <code>/home/developer/backups</code> y retención histórica en almacenamiento seguro."
    ]
    for pr in proto:
        story.append(Paragraph(pr, body_style))

    story.append(Spacer(1, 8))
    story.append(Paragraph("7. Diagnóstico y Preguntas Frecuentes", h1_style))

    faq_list = [
        ("¿DBeaver indica 'Connection refused' o 'Connection timed out'?",
         "Asegúrate de que el túnel WireGuard <b>Sin-Nombre</b> está activado en tu aplicación WireGuard y que la prueba de <code>ping 10.8.0.1</code> responde con 0% de pérdidas. Si no hay conexión VPN, el cortafuegos bloquea el puerto."),
        ("¿Puedo conectar sin estar en la VPN?",
         "No. Por política de seguridad estricta, los puertos de las bases de datos no están expuestos en Internet; solo responden a través de la red privada <code>10.8.0.0/24</code>."),
        ("¿Puedo usar otro cliente SQL en lugar de DBeaver?",
         "Sí. Puedes utilizar cualquier gestor compatible como HeidiSQL, DataGrip, TablePlus, VS Code Database Client, pgAdmin (para Odoo) o MySQL Workbench utilizando los mismos parámetros de la Sección 3."),
        ("¿Qué hacer ante el error 'Public Key Retrieval is not allowed' en MySQL?",
         "En DBeaver, edita la conexión, entra en la pestaña <i>Propiedades del controlador (Driver properties)</i> y cambia el parámetro <code>allowPublicKeyRetrieval</code> a <code>TRUE</code> y <code>useSSL</code> a <code>FALSE</code>."),
        ("¿Se pueden crear nuevas tablas o vistas?",
         "Sí. Los usuarios disponen del permiso <code>CREATE</code> para crear tablas de trabajo, índices auxiliares y vistas analíticas directamente desde DBeaver.")
    ]

    for q, a in faq_list:
        story.append(Paragraph(f"<b>• {q}</b><br/>{a}", body_style))
        story.append(Spacer(1, 3))

    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", thickness=1, color=c_border, spaceBefore=4, spaceAfter=8))
    story.append(Paragraph("<i>Documento técnico confidencial para uso interno — Grupo Utrecar S.L. &amp; Trieste S.L.</i>", ParagraphStyle('Foot', parent=body_style, fontName='Helvetica-Oblique', fontSize=7.5, textColor=c_muted_text, alignment=1)))

    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"PDF generado con éxito: {output_pdf}")

if __name__ == "__main__":
    generate_pdf()
