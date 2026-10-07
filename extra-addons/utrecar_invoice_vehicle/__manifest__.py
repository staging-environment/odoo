{
    'name': 'Utrecar - Datos de Vehículo, Conductor y Envío Automático en Facturas',
    'version': '17.0.1.2.0',
    'category': 'Accounting/Accounting',
    'summary': 'Matrícula autoguardada, kms, conductor y envío automático por email vs papel con avisos en Odoo',
    'description': """
        Módulo para UTRECAR / Estaciones de Servicio:
        - Registro y autoguardado de matrículas por cliente (res.partner.vehicle).
        - Campos en factura (account.move): Matrícula, Kilómetros y Conductor (texto libre).
        - Preferencia de facturación (Email vs Papel) por cliente y en factura.
        - Envío automático de la factura por correo al confirmar con notificación interactiva en Odoo.
        - Impresión automática en el informe PDF de la factura si los datos existen.
    """,
    'author': 'Utrecar',
    'depends': ['account', 'base', 'contacts', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'views/res_partner_vehicle_views.xml',
        'views/res_partner_views.xml',
        'views/account_move_views.xml',
        'report/report_invoice.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
