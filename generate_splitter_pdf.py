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
        
        # Header (pages > 1)
        if self._pageNumber > 1:
            self.drawString(40, 805, "UTRECAR ERP | GUIA TECNICA: SPLITTER DE PUERTO COM")
            self.drawRightString(555, 805, "E.S. RODALAB_OTA (EL CUERVO)")
            self.setStrokeColor(colors.HexColor("#CBD5E1"))
            self.setLineWidth(0.75)
            self.line(40, 798, 555, 798)
            
        # Footer (all pages)
        self.setStrokeColor(colors.HexColor("#E2E8F0"))
        self.setLineWidth(0.75)
        self.line(40, 42, 555, 42)
        
        self.setFont("Helvetica", 8)
        self.drawString(40, 30, "Documento de Ingenieria y Despliegue de Software de Pista | Odoo Cloud 17")
        self.drawRightString(555, 30, f"Pagina {self._pageNumber} de {page_count}")
        self.restoreState()

def build_pdf(filename):
    doc = SimpleDocTemplate(
        filename,
        pagesize=A4,
        leftMargin=40,
        rightMargin=40,
        topMargin=50,
        bottomMargin=50
    )

    styles = getSampleStyleSheet()

    c_primary = colors.HexColor("#1E3A8A")     # Navy
    c_secondary = colors.HexColor("#0284C7")   # Blue / Cyan
    _accent = colors.HexColor("#10B981")      # Emerald Green
    c_dark = colors.HexColor("#0F172A")        # Slate 900
    c_text = colors.HexColor("#334155")        # Slate 700
    _alight_bg = colors.HexColor("#F8FAFC")    # Slate 50
    c_border = colors.HexColor("#CBD5E1")      # Slate 300

    title_style = ParagraphStyle(
        "DocTitle",
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=c_primary,
        spaceAfter=4
    )

    subtitle_style = ParagraphStyle(
        "DocSubTitle",
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=14,
        textColor=c_secondary,
        spaceAfter=6
    )

    h1_style = ParagraphStyle(
        "Heading1_Custom",
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=15,
        textColor=c_primary,
        spaceBefore=10,
        spaceAfter=5,
        keepWithNext=True
     )

    body_style = ParagraphStyle(
        "Body_Custom",
        fontName="Helvetica",
        fontSize=8.5,
        leading=12,
        textColor=c_text,
        spaceAfter=4
     )

    body_bold = ParagraphStyle(
        "Body_Bold",
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=12,
        textColor=c_dark,
        spaceAfter=4
    )

    code_style = ParagraphStyle(
        "Code_Custom",
        fontName="Courier",
        fontSize=7.5,
        leading=10,
        textColor=colors.HexColor("#1E292B"),
    )

    table_header = ParagraphStyle(
        "TableHeader",
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
        textColor=colors.white,
        alignment=1
    )

    story = []

    story.append(Paragraph("UTRECAR ERP &dash; INTEGRACION ASEPRODA & ODOO CLOUD", subtitle_style))
    story.append(Paragraph("Guia Tecnica: Divisor Virtual de Puerto COM (100% Software)", title_style))
    story.append(Paragraph("<b>Estacion:</b> E.S. Rodalabota (El Cuervo) &nbsp;partial;&nbsp; <b>Hardware:</b> TPV Principal & Caja Aseproda USB &nbsp;partial;&nbsp; <b>Fecha:</b> Agosto 2026", body_style))
    story.append(HRFlowable(width="100%", thickness=2, color=c_primary, spaceBefore=4, spaceAfter=8))

    banner_data = [[
        Paragraph(
            "<b>OBJETIVO DE ESTA SOLUCION:</b><br/>"
            "Eliminar la necesidad de anadir resistencias o;modificar oel cableado fisico de pista. La caja negra de Aseproda ya esta conectada por USB al TPV principal. Utilizando un <b>Splitter Virtual de Puerto COM</b>, el software de Aseproda y nuestro agente de Odoo leen simultaneamente los mismos datos de los surtidores sin cortes de servicio ni bloqueos del bus RS-485.",
            body_style
        )
    ]]
    banner_table = Table(banner_data, colWidths=[515])
    banner_table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), colors.HexColor("#EFF6FF")),
        ("BOX", (0,0), (-1,-1), 1, c_secondary),
        ("PADDING", (0,0), (-1,-1), 7),
    ]))
    story.append(banner_table)
    story.append(Spacer(1, 8))

    story.append(Paragraph("1. Por que ocurre el bloqueo y como lo soluciona el Splitter", h1_style))
    story.append(Paragraph(
        "Al conectar un segundo conversor USB-RS485 en paralelo con la caja de Aseproda, se colocan dos resistencias de terminacion de 120 Ohm y dos redes de polarizacion activa en la misma linea fisica. Esto genera una <b>sobrecarga de impedancia que desploma el voltaje del bus</b> e impide que el TPV reciba respuesta de los surtidores.<br/><br/>"
        "
<b>La solucion por software:</b> La caja negra ya digitaliza las senales de pista y las envia al TPV principal por su propio cable USB. Con un <b>emulador virtual de puertos COM</b>, clonamos ese flujo de datos para que dos programas lo abran simultaneamente sin conflictos de Windows.",
        body_style
    ))
    story.append(Spacer(1, 6))

    diag_data = [
        [
            Paragraph("<b>ESQUEMA DE FLUJO POR SOFTWARE (SIN TOCAR CABLES)</b>", ParagraphStyle("DTitle", fontName="Helvetica-Bold", fontSize=8.5, textColor=c_primary, alignment=1)),
        ],
        [
            Paragraph(
                "[Surtidores Pista] ==(RS-485)==> [Caja Negra Aseproda] ==(USB)==> [COM3 Fisico en TPV]<br/>"
                "                                                                     |<br/>"
                "                                                                     v<br/>"
                "                                                          [VSPE / Splitter Virtual]<br/>"
                "                                                               /          <br/>"
                "                                                              v            v<br/>"
                "                                                          [Virtual COM10]   [Virtual COM10]<br/>"
                "                                                              |                 |<br/>"
                "                                                              v                 v<br/>"
                "                                                          [TPV Aseproda]   [Agente Odoo Cloud]",
                code_style
            )
        ]
    ]
    diag_table = Table(diag_data, colWidths=[515])
    diag_table.setStyle(TableStyle([]
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#F1F5F9")),
        ("BACKGROUND", (0,1), (-1,-1), colors.white),
        ("BOX", (0,0), (-1,-1), 1, c_border),
        ("PADDING", (0,0), (-1,-1), 6),
    ]))
    story.append(diag_table)
    story.append(Spacer(1, 8))

    story.append(Paragraph("2. Paso 1: Identificar el puerto COM real de la Caja Aseproda", h1_style))
    story.append(Paragraph(
        "Antes de configurar el splitter, identificamos que puerto COM tiene asignada la caja negra en Windows:",
        body_style
    ))
    
    paso1_items = [
        [Paragraph("<b>Accion 1.1</b>", body_bold), Paragraph("Pulsa <b>Win + X</b> en el TPV principal y selecciona <b>Administrador de Dispositivos</b> (o pulsa <i>Win + R</i> y escribe <b>devmgmt.msc</b>).", body_style)],
        [Paragraph("<b>Accion 1.2</b>", body_bold), Paragraph("Despliega la categoria <b>Puertos (COM y LPT)</b>.", body_style)],
        [Paragraph("<b>Accion 1.3</b>", body_bold), Paragraph("<b>Comprobacion</b> Desconecta el cable USB de la caja negra durante 2 segundos y reconectalo. Observa que puerto desaparece y reaparece (ejemplo: <b>COM3</b> o <b>COM1</b>). Anota ese puerto.", body_style)],
        [Paragraph("<b>Accion 1.4</b>", body_bold), Paragraph("Clic derecho sobre el puerto –<i>Propiedades</i>↓<i>Configuracion de puerto</i>. Verifica velocidad (estandar: <b>9600 baudios</b>, 8 bits, Sin paridad, 1 bit parada).", body_style)]
    ]
    t_paso1 = Table(paso1_items, colWidths=[80, 435])
    t_paso1.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), c_light_bg),
        ("BOX", (0,0), (-1,-1), 1, c_border),
        ("INNERGRID", (0,0), (-1,-1), 0.5, c_border),
        ("PADDING", (0,0), (-1,-1), 5),
    ]))
    story.append(t_paso1)
    story.append(Spacer(1, 8))

    story.append(PageBreak())

    story.append(Paragraph("3. Paso 2: Descargar e Instalar VSPE (Virtual Serial Ports Emulator)", h1_style))
    story.append(Paragraph(
        "Utilizaremos la herramienta estandar industrial <b>VSPE</b> de Eterlogic:",
        body_style
    )

    vspe_steps = [
        [Paragraph("<b>Descarga</b>", body_bold), Paragraph("Descargar el instalador desde la web oficial de Eterlogic:<br/><b>http://www.eterlogic.com/Products.VSPE.html</b> (Descargar version de 32 o 64 bits segun el Windows del TPV).", body_style)],
        [Paragraph("<b>Instalacion</b>", body_bold), Paragraph("Ejecutar <b>SetupVKPE.exe</b> como Administrador y completar el asistente (Next ↓ Accept ↕ Install).", body_style)],
        [Paragraph("<b>Controladores</b>", body_bold), Paragraph("Si Windows solicita confirmacion para instalar controladores de dispositivos virtuales serie, marcar <b>Confiar e Instalar</b>.", body_style)]
    ]
    t_vspe = Table(vspe_steps, colWidths=[80, 435])
    t_vspe.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), c_light_bg),
        ("BOX", (0,0), (-1,-1), 1, c_border),
        ("INNERGRID", (0,0), (-1,-1), 0.5, c_border),
        ("PADDING", (0,0), (-1,-1), 5),
    ]))
    story.append(t_vspe)
    story.append(Spacer(1, 8))

    story.append(Paragraph("4. Paso 3: Configurar el Dispositivo tipo Splitter en VSPE", h1_style))
    story.append(Paragraph(
        "El modo <b>Splitter</b> vincula el puerto real de Aseproda con un nuevo puerto virtual compartido:",
        body_style
    )

    conf_steps = [
        [Paragraph("<b>Paso 3.1</b>", body_bold), Paragraph("Abre <b>VSPE</b> (icono en escritorio o menu Inicio) ejecutandolo como Administrador.", body_style)],
        [Paragraph("<b>Paso 3.2</b>", body_bold), Paragraph("Haz clic en el menu <b>Device ↓ Create...</b> (o pulsa el icono de nuevo dispositivo).", body_style)],
        [Paragraph("<b>Paso 3.3</b>", body_bold), Paragraph("En el desplegable <i>Device type</i>, selecciona <b>Splitter</b> y pulsa <b>Next</b>.", body_style)],
        [Paragraph("<b>Paso 3.4</b>", body_bold), Paragraph(
            "<b>Configuracion de parametros:</b><br/>"
            "&bull; <b>Virtual serial port:</b> Selecciona un puerto virtual libre (ejemplo: <b>COM10</b>).<br/>"
            "&bull; <b>Data source serial port:</b> Selecciona el puerto real de la caja Aseproda (ejemplo: <b>COM3</b>).<br/>"
            "&bull; <b>Baud rate:</b> 9600 &nbsp;|&nbsp; <b>Data bits:</b> 8 &nbsp;|&nbsp; <b>Parity:</b> None &nbsp;|&nbsp; <b>Stop bits:</b> 1<br/>"
            "&bull; Pulsa <b>Finish</b>.",
            body_style
        )],
        [Paragraph("<b>Paso 3.5</b>", body_bold), Paragraph("En la lista de dispositivos de VSPE, verificaras que el estado indica <b>INITIALIZED (OK)</b> con icono verde.", body_style)],
        [Paragraph("<b>Paso 3.6</b>", body_bold), Paragraph("Guarda la configuracion: Menu <b>File ↓ Save layout as...</b> y guardalo en <b>C:\Utrecar\vspe_config.vspe</b>.", body_style)]
    ]
    t_conf = Table(conf_steps, colWidths=[80, 435])
    t_conf.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), c_light_bg),
        ("BOX", (0,0), (-1,-1), 1, c_border),
        ("INNERGRID", (0,0), (-1,-1), 0.5, c_border),
        ("PADDING", (0,0), (-1,-1), 5),
    ]))
    story.append(t_conf)
    story.append(Spacer(1, 8))

    story.append(Paragraph("5. Paso 4: Conectar TPV Aseproda y Agente Odoo a COM10", h1_style))
    story.append(Paragraph(
        "Una vez activo el puerto virtual <b>COM10</b>, ambas aplicaciones operan en paralelo de forma transparente:",
        body_style
    ))

    app_table_data = [
        [
            Paragraph("<b>Aplicacion</b>", table_header),
            Paragraph("<b>Puerto</b>", table_header),
            Paragraph("<b>Funcion en la Estacion</b>", table_header)
        ],
        [
            Paragraph("<b>TPV Aseproda</b><br/>(Programa de Caja)", body_bold),
            Paragraph("<b>COM10</b>", body_style),
            Paragraph("Sigue operando normalmente. Gestiona cobros, ticketera y ordenes de surtidor sin alteraciones.", body_style)
        ],
        [
            Paragraph("<b>Agente Odoo</b><br/>(agente_odoo_elcuervo.py)", body_bold),
            Paragraph("<b>COM10</b>", body_style),
            Paragraph("Lee las tramas de pista en tiempo real y sube automaticamente los manguerazos a <b>https://odoo.utrecar.com</b>.", body_style)
        ]
    ]
    t_app = Table(app_table_data, colWidths=[130, 85, 300])
    t_app.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), c_primary),
        ("BOX", (0,0), (-1,-1), 1, c_border),
        ("INNERGRID", (0,0), (-1,-1), 0.5, c_border),
        ("PADDING", (0,0), (-1,-1), 5),
    ]))
    story.append(t_app)
    story.append(Spacer(1, 8))

    story.append(PageBreak())

    story.append(Paragraph("6. Paso 5: Autoinicio 24/7 lfrente a Reinicios del TPV", h1_style))
    story.append(Paragraph(
        "Para que el sistema se recupere solo ante cualquier apagado o corte de luz:",
        body_style
    ))

    auto_steps = [
        [Paragraph("<b>Arranque VSPE</b>", body_bold), Paragraph(
            "1. Pulsa <b>Win + R</b>, escribe <b>shell:startup</b> y pulsa Enter.<br/>"
            "2. En esa carpeta, crea un acceso directo a VSPE con el siguiente destino:<br/>"
            "<b>\"C:\Program Files\Eterlogic.com\VSPE\VSPEmulator.exe\" -minimize -hide_splash \"C:\Utrecar\vspe_config.vspe\"</b><br/>"
            "<i>(Arranca en silencio minimizado en la bandeja del sistema y activa el puerto virtual automaticamente)</i>.",
            body_style
        )],
        [Paragraph("<b>Arranque Odoo</b>", body_bold), Paragraph(
            "Ejecuta en PowerShell el instalador de tarea programada ya preparado:<br/>"
            "<b>powershell -ExecutionPolicy Bypass -File .\setup_task_scheduler.ps1</b>",
            body_style
        )]
    ]
    t_auto = Table(auto_steps, colWidths=[100, 415])
    t_auto.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), c_light_bg),
        ("BOX", (0,0), (-1,-1), 1, c_border),
        ("INNERGRID", (0,0), (-1,-1), 0.5, c_border),
        ("PADDING", (0,0), (-1,-1), 5),
    ]))
    story.append(t_auto)
    story.append(Spacer(1, 10))

    story.append(Paragraph("7. Checklist de Comprobacion en Vivo", h1_style))

    check_data = [
        [Paragraph("<b>Num</b>", table_header), Paragraph("<b>Verificacion Tecnica</b>", table_header), Paragraph("<b>Resultado Esperado</b>", table_header)],
        [Paragraph("1", body_bold), Paragraph("Desconectar USB azul externo (dejar cableado fisico tal como esta).", body_style), Paragraph("<font color=\"#10B981\"><b>Completado</b></font>", body_bold)],
        [Paragraph("2", body_bold), Paragraph("Identificar puerto COM de caja negra en Administrador de Dispositivos.", body_style), Paragraph("<font color=\"#10B981\"><b>Identificado</b></font>", body_bold)],
        [Paragraph("3", body_bold), Paragraph("Instalar VSPE y crear Splitter (Origen: COM real ↓ Virtual: COM10).", body_style), Paragraph("<font color=\"#10B981\"><b>Inicializado</b></font>", body_bold)],
        [Paragraph("4", body_bold), Paragraph("Ejecutar <b>python test_rs485.py</b> apuntando a COM10 y verificar lectura.", body_style), Paragraph("<font color=\"#10B981\">><b>Tramas HEX OK</b></font>", body_bold)],
        [Paragraph("5", body_bold), Paragraph("Verificar que TPV Aseproda cobra y descuelga mangueras en pista.", body_style), Paragraph("<font color=\"#10B981\"><b>TPV Activo</b></font>", body_bold)],
        [Paragraph("6", body_bold), Paragraph("Configurar acceso directo en <b>shell:startup</b> para VSPE.", body_style), Paragraph("<font color=\"#10B981\"><b>Persistencia 24/7</b></font>", body_bold)]
    ]
    t_check = Table(check_data, colWidths=[35, 380, 100])
    t_check.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), c_primary),
        ("BOX", (0,0), (-1,-1), 1, c_border),
        ("INNERGRID", (0,0), (-1,-1), 0.5, c_border),
        ("PADDING", (0,0), (-1,-1), 5),
    ]))
    story.append(t_check)

    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"PDF generado con exito en: {filename}")

if __name__ == "__main__":
    output_pdf = "/home/bonilla/Projects/odoo/docs/Guia_Instalacion_Software_Splitter_COM_ElCuervo.pdf"
    build_pdf(output_pdf)
