import psycopg2

def main():
    conn = psycopg2.connect("host=db port=5432 dbname=odoo user=db password=db")
    cur = conn.cursor()
    
    cur.execute("UPDATE ir_sequence SET prefix = 'TTTR%(year)s' WHERE id = 54;")
    conn.commit()

    cur.execute("""
        SELECT id, name, code, prefix, padding, number_next
        FROM ir_sequence
        WHERE code LIKE 'pos.order.annulment%' OR id = 54
        ORDER BY id;
    """)
    for row in cur.fetchall():
        print(row)

if __name__ == '__main__':
    main()
