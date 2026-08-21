{
    'name': 'POS Gas Station Integration',
    'version': '17.0.1.9.0',
    'category': 'Point of Sale',
    'summary': 'Control táctil de gasolinera en tiempo real y compatibilidad con VirtusTPV',
    'description': """
        Módulo TPV para estaciones de servicio UTRECAR.
        - Monitorización en directo de surtidores
        - Carga de repostajes postpago y prepago a ticket
        - Catálogo de tienda y pistolas lectoras de código de barras
        - Matrícula y vehículos asociados
    """,
    'depends': ['point_of_sale'],
    'data': [],
    'assets': {
        'point_of_sale._assets_pos': [
            'pos_gas_station/static/src/css/pos_gas_station.css',
            'pos_gas_station/static/src/js/pos_gas_station.js',
            'pos_gas_station/static/src/xml/pos_gas_station.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
