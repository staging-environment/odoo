{
    'name': 'Utrecar - Datos de Vehículo, Conductor, Envío Automático y Gestión Comercial',
    'version': '17.0.1.3.0',
    'category': 'Accounting/Accounting',
    'summary': 'Matrículas, kms, conductor, envío automático, gestión de crédito/contado y periodicidad de facturación',
    'description': """
        Módulo para UTRECAR / Estaciones de Servicio:
        - Registro y autoguardado de matrículas por cliente (res.partner.vehicle).
        - Campos en factura (account.move): Matrícula, Kilómetros y Conductor (texto libre).
        - Preferencia de facturación (Email vs Papel) por cliente y en factura con envío automático en confirmación.
        - Gestión comercial en backoffice: Modalidad de pago (Crédito vs Contado), Periodicidad de facturación (Diaria, Decenal, Quincenal, Mensual), Límite de crédito y Bloqueo.
        - Blindaje frente a modificaciones en el TPV (solo gestionable desde el ERP/Backoffice).
        - Impresión automática en el informe PDF de la factura.
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
