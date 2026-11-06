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
            self.draw_header_footer(num_pages)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def draw_header_footer(self, page_count):
        self.saveState()
        self.setFont('Helvetica-Bold', 7.5)
        self.setFillColor(colors.HexColor('#475569'))
        
        # Header (Pages > 1)
        if self._pageNumber > 1:
            self.drawString(54, 804, 'INFORME TÉCNICO: DIAGNÓSTICO DE CONFLICTO Y BLOQUEO DE TPVS - RONDA NORTE')
            self.drawRightString(541, 804, 'UTRECAR ERP / ALINEACIÓN PRD ODOO 17')
            self.setStrokeColor(colors.HexColor('#CBD5E1'))
            self.setLineWidth(0.75)
            self.line(54, 796, 541, 796)
            
        # Footer (All pages)
        self.setFont('Helvetica', 7.5)
        self.setFillColor(colors.HexColor('#64748B'))
        page_text = f'Página {self._pageNumber} de {page_count}'
        self.drawRightString(541, 32, page_text)
        self.drawString(54, 32, 'CONFIDENCIAL - Auditoría de Concurrencia de Pista & Arquitectura de Software')
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
    
    # Custom Typography Styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=15,
        leading=19,
        textColor=colors.white,
        spaceAfter=4
    )
    
    subtitle_style = ParagraphStyle(
        'DocSubTitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=12.5,
        textColor=colors.HexColor('#E2E8F0'),
        spaceAfter=2
    )

    meta_label = ParagraphStyle(
        'MetaLabel',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=7.5,
        leading=10,
        textColor=colors.HexColor('#1E293B')
    )

    meta_val = ParagraphStyle(
        'MetaVal',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7.5,
        leading=10,
        textColor=colors.HexColor('#334155')
    )

    h1_style = ParagraphStyle(
        'SectionH1',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=15,
        textColor=colors.HexColor('#1E3A8A'),
        spaceBefore=10,
        spaceAfter=4,
        keepWithNext=True
    )

    h2_style = ParagraphStyle(
        'SectionH2',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#0F172A'),
        spaceBefore=7,
        spaceAfter=3,
        keepWithNext=True
    )

    body_style = ParagraphStyle(
        'BodyDark',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=11,
        textColor=colors.HexColor('#1E293B'),
        spaceAfter=4
    )

    bullet_style = ParagraphStyle(
        'BulletText',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=11,
        textColor=colors.HexColor('#334155'),
        spaceAfter=2.5,
        leftIndent=10
    )

    table_header_style = ParagraphStyle(
        'TableHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=7.5,
        leading=9.5,
        textColor=colors.white,
        alignment=0
    )

    table_cell_style = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7.2,
        leading=9.5,
        textColor=colors.HexColor('#1E293B')
    )

    callout_alert = ParagraphStyle(
        'CalloutAlert',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7.8,
        leading=11,
        textColor=colors.HexColor('#991B1B')
    )

    callout_info = ParagraphStyle(
        'CalloutInfo',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7.8,
        leading=11,
        textColor=colors.HexColor('#0F172A')
    )

    code_style = ParagraphStyle(
        'CodeStyle',
        parent=styles['Code'],
        fontName='Courier',
        fontSize=6.8,
        leading=8.5,
        textColor=colors.HexColor('#0F172A')
    )

    story = []

    # BANNER PORTADA
    header_table_data = [
        [Paragraph('INFORME TÉCNICO: DIAGNÓSTICO DE CONFLICTO Y BLOQUEO DE TPVS', title_style)],
        [Paragraph('Análisis Forense de Concurrencia Aseproda, Fallos de Red, Deadlocks MySQL y Alineación con el PRD de Odoo 17 POS', subtitle_style)]
    ]
    header_table = Table(header_table_data, colWidths=[487])
    header_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#1E3A8A')),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 5))

    # METADATOS
    meta_data = [
        [
            Paragraph('<b>Estación Auditada:</b> E.S. Ronda Norte (Utrera) - Cód 2', meta_val),
            Paragraph('<b>Fecha Auditoría:</b> 04 de Noviembre de 2026', meta_val)
        ],
        [
            Paragraph('<b>TPV 1 (Master / Pista):</b> DESKTOP-JL2UL2J (10.8.0.6 / 192.168.1.20)', meta_val),
            Paragraph('<b>TPV 2 (Esclavo):</b> MADIC-TPV-IOT (192.168.1.64)', meta_val)
        ],
        [
            Paragraph('<b>Estado Operativo:</b> ESTACIÓN EN SERVICIO ACTIVO (100%)', meta_val),
            Paragraph('<b>Estado Intervención:</b> <font color="#DC2626"><b>PAUSADO / OBSERVACIÓN PURA</b></font>', meta_val)
        ],
        [
            Paragraph('<b>Software Actual:</b> Aseproda (VirtusTPVNet 64-bit + SDES 8777 + MySQL 5.1)', meta_val),
            Paragraph('<b>Alcance:</b> Cero impacto en pista; diagnóstico 100% no invasivo', meta_val)
        ]
    ]
    meta_table = Table(meta_data, colWidths=[243, 244])
    meta_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8FAFC')),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 6))

    # SECCIÓN 1: RESUMEN EJECUTIVO
    story.append(Paragraph('1. Resumen Ejecutivo y Naturaleza de la Incidencia', h1_style))
    story.append(Paragraph(
        'El cliente reportó un grave conflicto recurrente en la estación de servicio Ronda Norte: <b>el TPV 2 (puesto esclavo) sufre congelaciones completas de pantalla y caídas de aplicación intermitentes</b> al cobrar o atender clientes. La empresa ya había sustituido previamente tanto el switch de red Ethernet físico como los propios equipos informáticos, sin lograr solucionar la incidencia. Esto demostraba que el origen del fallo no era un defecto de hardware físico.',
        body_style
    ))
    story.append(Paragraph(
        'Bajo la premisa crítica de no interrumpir la operativa comercial activa de la gasolinera, el equipo de arquitectura realizó una auditoría forense remota no invasiva sobre ambos puestos a través de la VPN y conexiones SSH seguras. El análisis determinó concluyentemente que <b>los bloqueos son fruto de problemas arquitectónicos de software y concurrencia</b> en la solución heredada de Aseproda, agravados por configuración de ahorro de energía en la tarjeta de red del TPV 2.',
        body_style
    ))

    # BOX DE ALERTA
    alert_box_data = [[
        Paragraph('<b>DIAGNÓSTICO CONCLUYENTE:</b> El TPV 2 se congela fundamentalmente porque <b>ambos puestos comparten la misma serie fiscal (TTRN)</b>, compitiendo simultáneamente por el bloqueo de fila en MySQL, mientras que el servicio de réplica <b>EOVGNET</b> satura el motor de base de datos con un bucle infinito de transacciones fallidas que bloquean hasta 18 tablas a la vez.', callout_alert)
    ]]
    alert_box = Table(alert_box_data, colWidths=[487])
    alert_box.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#FEF2F2')),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#F87171')),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(alert_box)
    story.append(Spacer(1, 8))

    # SECCIÓN 2: TOPOLOGÍA
    story.append(Paragraph('2. Topología de Comunicación y Flujo en Pista', h1_style))
    story.append(Paragraph(
        'En la arquitectura actual de Ronda Norte, el TPV 1 actúa como concentrador y base de datos local centralizada. El TPV 2 carece de base de datos operativa y ataca a TPV 1 a través de la red de área local (LAN 192.168.1.x):',
        body_style
    ))

    topo_data = [
        [Paragraph('<b>Elemento / Canal</b>', table_header_style), Paragraph('<b>Configuración Observada</b>', table_header_style), Paragraph('<b>Impacto Operativo</b>', table_header_style)],
        [
            Paragraph('<b>Conexión MySQL TPV 2 ➔ TPV 1</b>', table_cell_style),
            Paragraph('7 sockets TCP permanentes abiertos desde TPV 2 (192.168.1.64) hacia TPV 1 (192.168.1.20:3306).', table_cell_style),
            Paragraph('Cualquier bloqueo o latencia en el MySQL de TPV 1 congela sincrónicamente la GUI de TPV 2.', table_cell_style)
        ],
        [
            Paragraph('<b>Conexión Concentrador SDES</b>', table_cell_style),
            Paragraph('1 socket TCP persistente desde TPV 2 hacia TPV 1 en el puerto 8777 (SDES LON/Wayne).', table_cell_style),
            Paragraph('Control de mangueras y desbloqueo de surtidores dependiente del hilo de SDES en TPV 1.', table_cell_style)
        ],
        [
            Paragraph('<b>Sincronizador Nube (EOVGNET)</b>', table_cell_style),
            Paragraph('Ejecutándose en TPV 1 cada 10-15s intentando sincronizar contra la BD corporativa central.', table_cell_style),
            Paragraph('Transacciones pesadas de fondo con locks exclusivos sobre tablas de ventas y clientes.', table_cell_style)
        ]
    ]
    topo_table = Table(topo_data, colWidths=[120, 217, 150])
    topo_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0284C7')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8FAFC')]),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(topo_table)
    story.append(Spacer(1, 8))

    # SECCIÓN 3: CAUSAS RAÍZ
    story.append(Paragraph('3. Diagnóstico Forense Detallado: Las 5 Causas Raíz', h1_style))

    # 3.1 Causa 1
    story.append(Paragraph('3.1. Causa 1 (Crítica): Colisión de Series Fiscales (TTRN y FTRN)', h2_style))
    story.append(Paragraph(
        'Al auditar la tabla <code>virtusgesnet.seriesportpv</code> en MySQL, se detectó una negligencia crítica de configuración en Ronda Norte. Mientras que en otras estaciones como Vistalegre el TPV 1 y el TPV 2 tienen series independientes (<code>TTUTR</code> y <code>TTUTR2</code>), <b>en Ronda Norte ambos puestos tienen asignada la MISMA serie: TTRN (Tickets) y FTRN (Facturas)</b>. Las series <code>TTRN2</code> ni existen.',
        body_style
    ))
    story.append(Paragraph(
        'Al cobrar dos ventas en paralelo, ambos TPVs compiten por ejecutar simultáneamente:<br/>'
        '<code>UPDATE seriesdefacturasyticketsdeventa SET Numerador = Numerador + 1 WHERE Codigo = \'TTRN\';</code><br/>'
        'Esto desencadena un <b>bloqueo exclusivo de fila en InnoDB</b>. Como VirtusTPV hace la llamada sincrónica en el hilo de interfaz, el TPV 2 entra en estado de suspensión blanca ("No responde") esperando el candado de red.',
        body_style
    ))

    # 3.2 Causa 2
    story.append(Paragraph('3.2. Causa 2 (Crítica): Tormenta de Bloqueos y Deadlocks por Bucle de EOVGNET', h2_style))
    story.append(Paragraph(
        'Al ejecutar <code>SHOW ENGINE INNODB STATUS</code> en TPV 1, se capturó un <b>Deadlock en tiempo real</b> sobre la tabla <code>expediciones</code> entre el hilo de EOVGNET (139578) y el TPV. El log <code>SyncReg.log</code> demostró que EOVGNET falla en bucle cada 10-15s por violación de claves foráneas en <code>documentosacobrar</code> y duplicado en <code>regularizacionesdealmacen (RRN-2021000001-1)</code>.',
        body_style
    ))
    story.append(Paragraph(
        'En cada reintento fallido, EOVGNET abre transacciones reteniendo bloqueos sobre <b>18 tablas a la vez</b>. Toda petición entrante de TPV 2 queda encolada en MySQL, provocando congelación inmediata del software en pista.',
        body_style
    ))

    # 3.3 Causa 3
    story.append(Paragraph('3.3. Causa 3 (Alta): Ahorro de Energía Agresivo en la Tarjeta de Red de TPV 2', h2_style))
    story.append(Paragraph(
        'La tarjeta de red Realtek PCIe GbE del TPV 2 tiene habilitada por defecto la opción <b>"Permitir que el equipo apague este dispositivo para ahorrar energía"</b> (<code>MSPower_DeviceEnable: True</code>), además de tener activados <code>Ethernet ecológico (Green Ethernet)</code> y <code>Energy Efficient Ethernet (EEE)</code>. Cuando el cajero pasa varios minutos sin registrar ventas, la tarjeta reduce la energía del enlace; al pulsar la pantalla táctil, se producen <b>micro-cortes y picos de latencia en los sockets TCP con TPV 1</b>, causando la desconexión o congelación de la interfaz.',
        body_style
    ))

    # 3.4 Causa 4 & 5
    story.append(Paragraph('3.4. Causa 4 (Media-Alta): Fuga de Memoria (1.58 GB) y Fallos de Impresión WSD', h2_style))
    story.append(Paragraph(
        'El proceso <code>VirtusTPVNet.exe</code> de TPV 2 acumulaba <b>1.581 MB de memoria física</b> tras 6 días continuos sin reinicio (uptime desde 29/10/2026). Esto satura el Garbage Collector de .NET, provocando congelaciones por pausas Stop-The-World. Además, se registraron excepciones no controladas en <code>combit.ListLabel18</code> al imprimir en segundo hilo y caídas en <code>spoolsv.exe</code> debido a que la impresora Epson WF-M5299 está conectada por un <b>puerto dinámico WSD</b> en lugar de un puerto IP TCP/IP estándar.',
        body_style
    ))

    story.append(Paragraph('3.5. Causa 5 (Media): Inversión de Códigos de TPV', h2_style))
    story.append(Paragraph(
        'En los archivos locales de arranque, TPV 1 se ejecuta bajo <code>CodigoTPV = 2</code> y TPV 2 bajo <code>CodigoTPV = 1</code>, invirtiendo la asignación de base de datos donde TPV 1 es "Principal" y TPV 2 es "Secundario".',
        body_style
    ))

    story.append(Spacer(1, 6))

    # SECCIÓN 4: ALINEACIÓN CON EL PRD
    story.append(Paragraph('4. Alineación Estratégica con el PRD (Product Requirements Document) de Odoo 17 POS', h1_style))
    story.append(Paragraph(
        'Este diagnóstico en Ronda Norte demuestra de forma contundente la <b>justificación técnica y comercial del PRD de Odoo 17 POS</b>. Las limitaciones observadas son fallas intrínsecas del modelo cliente-servidor tradicional de Aseproda (acceso síncrono a tablas MySQL compartidas), las cuales quedan completamente resueltas mediante los principios de diseño de Odoo 17:',
        body_style
    ))

    prd_data = [
        [
            Paragraph('<b>Requisito del PRD Odoo</b>', table_header_style),
            Paragraph('<b>Fallo Identificado en Aseproda</b>', table_header_style),
            Paragraph('<b>Solución Estructural en Odoo 17 POS</b>', table_header_style)
        ],
        [
            Paragraph('<b>FR-POS-01: Sesiones Multi-Cajero Aisladas</b>', table_cell_style),
            Paragraph('TPV 2 ataca síncronamente la BD de TPV 1 por TCP raw. Un bloqueo en el master congela al esclavo.', table_cell_style),
            Paragraph('Cada puesto corre una sesión desacoplada (<code>pos.session</code>) en navegador web OWL. Cero bloqueos de GUI por BD.', table_cell_style)
        ],
        [
            Paragraph('<b>FR-FISCAL-02: Numeración Fiscal Particionada</b>', table_cell_style),
            Paragraph('Ambos TPVs colisionan sobre la misma serie <code>TTRN</code>, generando bloqueos de fila exclusivos en cada cobro.', table_cell_style),
            Paragraph('Odoo genera secuencias fiscales independientes por terminal (ej. <code>RN1/2026/...</code> y <code>RN2/2026/...</code>) sin locks.', table_cell_style)
        ],
        [
            Paragraph('<b>FR-HARDWARE-03: Broker de Pista Desacoplado</b>', table_cell_style),
            Paragraph('VirtusTPV consulta por polling tablas MySQL y sockets de pista en el mismo hilo de pantalla.', table_cell_style),
            Paragraph('El <b>Agente Edge Odoo</b> canaliza eventos de pista asíncronamente por WebSockets. La interfaz jamás se congela.', table_cell_style)
        ],
        [
            Paragraph('<b>NFR-RESIL-04: Tolerancia a Caídas de Red</b>', table_cell_style),
            Paragraph('Un micro-corte por ahorro de energía en la tarjeta de red provoca cuelgues irreversibles en VirtusTPV.', table_cell_style),
            Paragraph('Odoo POS implementa buffer offline en IndexedDB local; las ventas continúan sin interrupción ante caídas de red.', table_cell_style)
        ],
        [
            Paragraph('<b>NFR-STABILITY-05: Única Fuente de Verdad Cloud</b>', table_cell_style),
            Paragraph('Servicio <code>EOVGNET</code> colapsa el motor MySQL local con bucles infinitos de sincronización defectuosa.', table_cell_style),
            Paragraph('Odoo centraliza los datos en PostgreSQL Cloud vía API transaccional robusta, erradicando sincronizadores locales frágiles.', table_cell_style)
        ]
    ]
    prd_table = Table(prd_data, colWidths=[125, 175, 187])
    prd_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E3A8A')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8FAFC')]),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(prd_table)
    story.append(Spacer(1, 8))

    # SECCIÓN 5: PLAN DE MITIGACIÓN
    story.append(Paragraph('5. Plan de Mitigación Transitoria (Pausado - En Espera de Autorización)', h1_style))
    story.append(Paragraph(
        'Siguiendo las instrucciones explícitas del cliente (<i>"De momento no hagas nada"</i>), <b>no se ha aplicado ningún cambio en los sistemas ni en la base de datos de Ronda Norte</b>. La estación continúa su actividad habitual. Cuando el cliente lo autorice (en un momento de baja afluencia), se recomienda aplicar el siguiente plan quirúrgico:',
        body_style
    ))

    plan_data = [
        [Paragraph('<b>Paso</b>', table_header_style), Paragraph('<b>Acción Técnica de Mitigación</b>', table_header_style), Paragraph('<b>Prioridad</b>', table_header_style), Paragraph('<b>Estado</b>', table_header_style)],
        [
            Paragraph('<b>1</b>', table_cell_style),
            Paragraph('Crear series <code>TTRN2</code> y <code>FTRN2</code> en MySQL y asignarlas a <code>CodigoDeTPV = 2</code> en <code>seriesportpv</code>.', table_cell_style),
            Paragraph('CRÍTICA', table_cell_style),
            Paragraph('<b><font color="#D97706">Pendiente de Visto Bueno</font></b>', table_cell_style)
        ],
        [
            Paragraph('<b>2</b>', table_cell_style),
            Paragraph('Desactivar EEE, Green Ethernet y "Permitir apagar este dispositivo" en el adaptador Realtek del TPV 2.', table_cell_style),
            Paragraph('ALTA', table_cell_style),
            Paragraph('<b><font color="#D97706">Pendiente de Visto Bueno</font></b>', table_cell_style)
        ],
        [
            Paragraph('<b>3</b>', table_cell_style),
            Paragraph('Limpiar en BD central el registro duplicado <code>RRN-2021000001-1</code> y claves foráneas para frenar bucle de <code>EOVGNET</code>.', table_cell_style),
            Paragraph('ALTA', table_cell_style),
            Paragraph('<b><font color="#D97706">Pendiente de Visto Bueno</font></b>', table_cell_style)
        ],
        [
            Paragraph('<b>4</b>', table_cell_style),
            Paragraph('Reconfigurar impresora Epson WF-M5299 de puerto dinámico WSD a puerto TCP/IP Estándar fijo.', table_cell_style),
            Paragraph('MEDIA', table_cell_style),
            Paragraph('<b><font color="#D97706">Pendiente de Visto Bueno</font></b>', table_cell_style)
        ],
        [
            Paragraph('<b>5</b>', table_cell_style),
            Paragraph('Programar tarea nocturna (05:00 AM) de reciclaje del proceso <code>VirtusTPVNet.exe</code> para liberar la memoria acumulada.', table_cell_style),
            Paragraph('PREVENTIVA', table_cell_style),
            Paragraph('<b><font color="#D97706">Pendiente de Visto Bueno</font></b>', table_cell_style)
        ]
    ]
    plan_table = Table(plan_data, colWidths=[25, 270, 72, 120])
    plan_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0F172A')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8FAFC')]),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(plan_table)
    story.append(Spacer(1, 8))

    # SECCIÓN 6: CONCLUSIÓN
    story.append(Paragraph('6. Conclusión y Estrategia de Transición', h1_style))
    story.append(Paragraph(
        'El conflicto entre TPV 1 y TPV 2 en Ronda Norte es el síntoma inequívoco de una deuda técnica acumulada en la infraestructura heredada de Aseproda. El plan de mitigación propuesto eliminará los bloqueos de forma temporal permitiendo operar con normalidad. Sin embargo, la resolución estructural y definitiva vendrá de la mano del <b>despliegue de Odoo 17 POS Gas Station</b>, consolidando la independencia tecnológica total y garantizando una experiencia de usuario moderna, ágil y libre de caídas para el equipo de pista.',
        body_style
    ))

    # Firmas
    story.append(Spacer(1, 10))
    sig_data = [
        [
            Paragraph('<b>Equipo de Arquitectura e Infraestructura</b><br/>Utrecar ERP - Antigravity Agentic Systems', meta_val),
            Paragraph('<b>Estado del Proyecto:</b><br/>Auditoría Documentada / Acción Pausada', meta_val)
        ]
    ]
    sig_table = Table(sig_data, colWidths=[243, 244])
    sig_table.setStyle(TableStyle([
        ('LINEBEFORE', (0, 0), (0, -1), 2, colors.HexColor('#1E3A8A')),
        ('LINEBEFORE', (1, 0), (1, -1), 2, colors.HexColor('#0284C7')),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))
    story.append(sig_table)

    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"PDF generado satisfactoriamente en: {filename}")

if __name__ == '__main__':
    output_pdf = os.path.join(os.path.dirname(__file__), '..', 'docs', 'Informe_Tecnico_Diagnostico_Conflicto_TPVs_Ronda_Norte.pdf')
    output_pdf = os.path.abspath(output_pdf)
    build_pdf(output_pdf)

