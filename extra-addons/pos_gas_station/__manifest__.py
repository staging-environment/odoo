{
    'name': 'POS Gas Station Integration',
    'version': '17.0.3.1.0',
    'category': 'Point of Sale',
    'summary': 'Control táctil de gasolinera en tiempo real, PWA y compatibilidad con VirtusTPV',
    'description': """
        Módulo TPV para estaciones de servicio UTRECAR.
        - Soporte PWA instalable con aviso interactivo y Service Worker
        - Monitorización en directo de surtidores
        - Carga de repostajes postpago y prepago a ticket
        - Catálogo de tienda y pistolas lectoras de código de barras
        - Matrícula y vehículos asociados
        - Matriz Visual de Roles y Permisos (Sistema y TPV)
        - Dashboard Multi-Empresa de Estaciones de Servicio
    """,
    'depends': ['point_of_sale', 'mail', 'digest'],
    'data': [
        'security/ir.model.access.csv',
        'data/permission_matrix_data.xml',
        'data/pos_security_rules.xml',
        'data/sync_cron.xml',
        'data/disable_digest.xml',
        'views/res_partner_views.xml',
        'views/permission_matrix_views.xml',
        'views/res_company_views.xml',
        'views/employee_select_template.xml',
        'views/pwa_templates.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'pos_gas_station/static/src/css/pos_gas_station.css',
            'pos_gas_station/static/src/js/pos_gas_station.js',
            'pos_gas_station/static/src/xml/pos_gas_station.xml',
        ],
        'web.assets_backend': [
            'pos_gas_station/static/src/css/permission_matrix.css',
            'pos_gas_station/static/src/js/permission_matrix.js',
            'pos_gas_station/static/src/xml/permission_matrix.xml',
            'pos_gas_station/static/src/css/gas_station_dashboard.css',
            'pos_gas_station/static/src/js/gas_station_dashboard.js',
            'pos_gas_station/static/src/css/employee_company_roles.css',
            'pos_gas_station/static/src/js/employee_company_roles.js',
            'pos_gas_station/static/src/xml/gas_station_dashboard.xml',
            'pos_gas_station/static/src/xml/employee_company_roles.xml',
            'pos_gas_station/static/src/css/res_partner_full_width.css',
            'pos_gas_station/static/src/css/vpn_station_employees.css',
            'pos_gas_station/static/src/js/vpn_station_employees.js',
            'pos_gas_station/static/src/xml/vpn_station_employees.xml',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
