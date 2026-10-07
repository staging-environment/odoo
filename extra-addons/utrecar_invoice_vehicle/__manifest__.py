{
    'name': 'Utrecar - Datos de Vehículo y Conductor en Facturas',
    'version': '17.0.1.0.0',
    'category': 'Accounting/Accounting',
    'summary': 'Matrícula autoguardada por cliente, kilómetros y conductor en facturas e impresión PDF',
    'description': """
        Módulo para UTRECAR / Estaciones de Servicio:
        - Registro y autoguardado de matrículas por cliente (res.partner.vehicle).
        - Campos en factura (account.move): Matrícula, Kilómetros y Conductor (texto libre).
        - Visualización y gestión de vehículos en la ficha del cliente.
        - Impresión automática en el informe PDF de la factura si los datos existen.
    """,
    'author': 'Utrecar',
    'depends': ['account', 'base', 'contacts'],
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
