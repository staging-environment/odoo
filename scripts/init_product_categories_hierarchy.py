# -*- coding: utf-8 -*-
"""
Script idempotente para organizar las categorías de productos de Odoo en una jerarquía
de 2 niveles (Padre: 1 dígito, Hija/Subfamilia: 2 dígitos) tomando como referencia
las categorías importadas de Aseproda.

Uso en producción:
  docker exec -i ddev-odoo-odoo odoo shell -d odoo --no-http < scripts/init_product_categories_hierarchy.py
"""
import logging

_logger = logging.getLogger(__name__)

# Estructura jerárquica a 2 niveles:
#   parent_code (1 dígito): (nombre_padre, [(child_code 2 dígitos, nombre_hija, [posibles nombres existentes]), ...])
HIERARCHY = {
    '1': (
        'Combustibles',
        [
            ('01', 'Gasóleo A', ['Gasoleo A', 'Gasóleo A']),
            ('02', 'Sin Plomo 95', ['Sin Plomo 95']),
            ('03', 'Ultimate', ['Ultimate']),
        ],
    ),
    '2': (
        'Artículos Varios',
        [
            ('01', 'Artículos Campo', ['Articulos Campo', 'Artículos Campo']),
            ('02', 'Impuestos', ['Impuestos']),
            ('03', 'Otros', ['Otros']),
            ('04', 'Juguetería / Hogar', ['Jugueteria / Hogar', 'Juguetería / Hogar']),
            ('05', 'Ferretería y Similares', ['Ferreteria Y Similares', 'Ferretería y Similares']),
            ('06', 'Cafetería', ['Cafeteria', 'Cafetería']),
        ],
    ),
    '3': (
        'Alimentación',
        [
            ('11', 'Chocolates y Chocolatinas', ['Chocolates Y Chocolatinas', 'Chocolates y Chocolatinas']),
            ('12', 'Caramelos', ['Caramelos']),
            ('13', 'Chicles', ['Chicles']),
            ('14', 'Patatas', ['Patatas']),
            ('15', 'Pan y Bollería', ['Pany Bolleria', 'Pan y Bollería']),
            ('16', 'Helados', ['Helados']),
            ('17', 'Aperitivos, Galletas y Frutos Secos', ['Aperitivos, Galletas Y Frutos Secos']),
            ('18', 'Golosinas', ['Golosinas']),
            ('19', 'Comida', ['Comida']),
        ],
    ),
    '4': (
        'Centro de Lavado',
        [
            ('01', 'Lavado y Programas', ['Lavado y Programas']),
        ],
    ),
    '5': (
        'Activos Empresariales',
        [
            ('01', 'Venta y Alquiler de Activos Empresariales', ['Venta Y Alquiler De Activos Empresariales']),
        ],
    ),
    '6': (
        'Bebidas',
        [
            ('01', 'Agua', ['Agua']),
            ('02', 'Refrescos', ['Refrescos']),
            ('03', 'Alcohol', ['Alcohol']),
            ('04', 'Otras Bebidas', ['Otras Bebidas']),
        ],
    ),
    '7': (
        'Accesorios y Recambios',
        [
            ('01', 'Aceites y Afines', ['Aceites Y Afines']),
            ('02', 'Otros Accesorios', ['Otros Accesorios']),
        ],
    ),
    '8': (
        'Limpieza e Higiene',
        [
            ('01', 'Detergentes', ['Detergentes']),
            ('02', 'Higiene y Covid19', ['Higiene Y Covid19']),
        ],
    ),
    '9': (
        'Servicios y Compras (No Mercadería)',
        [
            ('01', 'Gastos Generales', ['Gastos Generales']),
            ('02', 'Agua, Luz, Teléfono, Internet', ['Agua, Luz, Telefono, Internet']),
            ('03', 'Servicios Profesionales Independientes', ['Servicios Profesionales Independientes']),
            ('04', 'Gastos de Representación y Viaje', ['Gastos De Representacion Y Viaje']),
            ('05', 'Inversiones', ['Inversiones']),
            ('06', 'Reparación y Mantenimiento Gasolinera', ['Reparacion Y Mantenimiento Gasolinera']),
            ('07', 'Reparación y Mantenimiento Lavadero', ['Reparacion Y Mantenimiento Lavadero']),
            ('08', 'Compras y Gastos Cafetería', ['Compras Y Gastos Cafeteria']),
            ('09', 'Rapeles por Compras', ['Rapeles Por Compras']),
        ],
    ),
}

# Alias de nombres existentes de padres en Odoo
PARENT_ALIASES = {
    '1': ['Combutibles', 'Combustibles'],
    '2': ['Articulos Varios', 'Artículos Varios'],
    '3': ['Alimentacion', 'Alimentación'],
    '4': ['Centro de Lavado (Grupo)', 'Centro De Lavado'],
    '5': ['Activos Empresariales'],
    '6': ['Bebidas'],
    '7': ['Accesorios Y Recambios', 'Accesorios y Recambios'],
    '8': ['Limpieza E Higiene', 'Limpieza e Higiene'],
    '9': ['Servicios Y Compras ( No Mercaderia)', 'Servicios y Compras (No Mercadería)'],
}


def run_sync(env):
    Cat = env['product.category'].sudo()
    Prod = env['product.template'].sudo()

    # Caso especial: si 'Centro De Lavado' (id 42) tiene productos directamente,
    # los reubicamos en su subfamilia '01 Lavado y Programas' para mantener 2 niveles estrictos.
    parent_records = {}
    for p_code, (p_name, children) in HIERARCHY.items():
        aliases = PARENT_ALIASES.get(p_code, [p_name])
        parent = Cat.search([('code', '=', p_code), ('parent_id', '=', False)], limit=1)
        if not parent:
            parent = Cat.search([('name', 'in', aliases)], limit=1)
        if parent:
            parent.write({'name': p_name, 'parent_id': False, 'code': p_code})
        else:
            parent = Cat.create({'name': p_name, 'parent_id': False, 'code': p_code})
        parent_records[p_code] = parent

        for c_code, c_name, c_aliases in children:
            child = Cat.search([('parent_id', '=', parent.id), ('code', '=', c_code)], limit=1)
            if not child:
                child = Cat.search([('name', 'in', c_aliases), ('id', '!=', parent.id)], limit=1)
            if child:
                child.write({'name': c_name, 'parent_id': parent.id, 'code': c_code})
            else:
                child = Cat.create({'name': c_name, 'parent_id': parent.id, 'code': c_code})

        # Si el propio padre tenía productos directos (ej. Centro de Lavado, Bebidas, Accesorios, Limpieza),
        # moverlos a su primera o última subfamilia correspondiente
        direct_prods = Prod.search([('categ_id', '=', parent.id)])
        if direct_prods:
            fallback_child = Cat.search([('parent_id', '=', parent.id)], order='code desc', limit=1)
            if fallback_child:
                direct_prods.write({'categ_id': fallback_child.id})
                print(f"Reubicados {len(direct_prods)} productos de '{parent.name}' -> '{fallback_child.name}'")

    env.cr.commit()
    print("Sincronización jerárquica de categorías completada correctamente.")


if 'env' in globals():
    run_sync(env)
