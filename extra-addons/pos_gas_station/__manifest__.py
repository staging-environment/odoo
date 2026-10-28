{
    'name': 'POS Gas Station Integration',
    'version': '17.0.2.8.2',
    'category': 'Point of Sale',
    'summary': 'Control táctil de gasolinera en tiempo real y compatibilidad con VirtusTPV',
    'description': """
        Módulo TPV para estaciones de servicio UTRECAR.
        - Monitorización en directo de surtidores
        - Carga de repostajes postpago y prepago a ticket
        - Catálogo de tienda y pistolas lectoras de código de barras
        - Matrícula y vehículos asociados
        - Matriz Visual de Roles y Permisos (Sistema y TPV)
        - Dashboard Multi-Empresa de Estaciones de Servicio
    """,
    'depends': ['point_of_sale', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'data/permission_matrix_data.xml',
        'data/pos_security_rules.xml',
        'views/res_partner_views.xml',
        'views/permission_matrix_views.xml',
        'views/res_company_views.xml',
        'views/employee_select_template.xml',
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
            'pos_gas_station/static/src/xml/gas_station_dashboard.xml',
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
