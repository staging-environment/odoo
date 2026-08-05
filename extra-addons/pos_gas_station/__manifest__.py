{
    'name': 'POS Gas Station / Control de Surtidores',
    'version': '17.0.1.0.0',
    'category': 'Sales/Point of Sale',
    'summary': 'Interfaz visual de control de pista y surtidores para Odoo POS',
    'author': 'Antigravity / Bonilla',
    'depends': ['point_of_sale'],
    'data': [],
    'assets': {
        'point_of_sale._assets_pos': [
            'pos_gas_station/static/src/css/pos_gas_station.css',
            'pos_gas_station/static/src/xml/pos_gas_station.xml',
            'pos_gas_station/static/src/js/pos_gas_station.js',
        ],
    },
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
