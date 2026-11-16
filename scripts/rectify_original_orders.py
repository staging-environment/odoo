# -*- coding: utf-8 -*-
"""
Script de rectificación de tickets y albaranes originales en Odoo.
Aplica el formato oficial NOMENCLATURAAÑONUMERO (sin guiones):
- Tickets originales: TTTR202600026 .. TTTR202600084
- Albaranes originales: AVTR202600034 .. AVTR202600077
- Secuencia Pedido TPV Repsol (54): prefix='TTTR%(year)s', padding=5, number_next=85
"""
import psycopg2
import re

def main():
    conn = psycopg2.connect("host=db port=5432 dbname=odoo user=db password=db")
    cur = conn.cursor()
    
    print("=== INICIANDO RECTIFICACIÓN DE TICKETS Y ALBARANES ORIGINALES ===")
    
    cur.execute("""
        SELECT id, name, is_albaran, date_order
        FROM pos_order
        WHERE name ~ '^(TTTR|AVTR)\d{4}$'
        ORDER BY id;
    """)
    rows = cur.fetchall()
    print(f"Total registros a rectificar: {len(rows)}")
    
    for r in rows:
        oid, old_name, is_alb, dorder = r
        year = dorder.year if dorder else 2026
        m = re.match(r'^(TTTR|AVTR)(\d+)$', old_name)
        if m:
            prefix, num_str = m.groups()
            new_name = f"{prefix}{year}{int(num_str):05d}"
            
            # Actualizar name en pos_order
            cur.execute("""
                UPDATE pos_order
                SET name = %s
                WHERE id = %s;
            """, (new_name, oid))
            print(f"pos_order {oid}: {old_name} -> {new_name}")
            
            # Si tiene factura asociada (account_move), actualizar move.ref
            cur.execute("""
                UPDATE account_move
                SET ref = %s
                WHERE ref = %s;
            """, (new_name, old_name))

    # Actualizar notas de albaranes negativos que hagan referencia al original
    cur.execute("""
        UPDATE pos_order
        SET note = regexp_replace(note, 'AVTR(\d{4})', 'AVTR20260\\1', 'g')
        WHERE note LIKE '%AVTR0%';
    """)

    # Actualizar ir_sequence 54 para que continúe en el 85
    cur.execute("""
        UPDATE ir_sequence
        SET prefix = 'TTTR%(year)s',
            padding = 5,
            number_next = 85,
            number_increment = 1
        WHERE id = 54;
    """)
    print("\nSecuencia Pedido TPV E.S. Repsol (id 54) actualizada: number_next=85, prefix='TTTR%(year)s', padding=5")

    conn.commit()
    print("\n=== RECTIFICACIÓN DE TICKETS Y ALBARANES ORIGINALES COMPLETADA CON ÉXITO ===")

if __name__ == '__main__':
    main()
