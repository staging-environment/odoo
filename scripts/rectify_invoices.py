import psycopg2
import re

def main():
    conn = psycopg2.connect("host=db port=5432 dbname=odoo user=db password=db")
    cur = conn.cursor()

    print("--- 1. Rectificando Facturas en account_move ---")
    cur.execute("SELECT id, name FROM account_move WHERE name LIKE 'FTTR/%' ORDER BY id ASC;")
    moves = cur.fetchall()
    for mid, mname in moves:
        clean_name = re.sub(r'[/_\-\s]', '', mname)
        m = re.search(r'(\d+)$', clean_name)
        seq_num = int(m.group(1)) if m else 0
        print(f"Move ID {mid}: '{mname}' -> '{clean_name}', seq: {seq_num}")
        cur.execute("""
            UPDATE account_move
            SET name = %s,
                sequence_prefix = 'FTTR',
                sequence_number = %s
            WHERE id = %s;
        """, (clean_name, seq_num, mid))

    print("--- 2. Actualizando pos_order asociados ---")
    cur.execute("""
        SELECT po.id, po.name, po.account_move, am.name, po.to_invoice
        FROM pos_order po
        JOIN account_move am ON am.id = po.account_move
        WHERE am.name LIKE 'FTTR%'
        ORDER BY po.id ASC;
    """)
    orders = cur.fetchall()
    for poid, poname, amid, amname, to_inv in orders:
        print(f"POS Order ID {poid}: '{poname}' -> '{amname}'")
        cur.execute("""
            UPDATE pos_order
            SET name = %s,
                is_ticket_annulled = FALSE,
                annulment_ref = NULL,
                annulment_reason = NULL
            WHERE id = %s;
        """, (amname, poid))

    conn.commit()
    print("✅ Rectificación completada con éxito.")

if __name__ == '__main__':
    main()
