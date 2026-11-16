import psycopg2

def main():
    conn = psycopg2.connect("host=db port=5432 dbname=odoo user=db password=db")
    cur = conn.cursor()
    
    # Ver los últimos 10 pos_order en pos_order con su nuevo nombre
    cur.execute("""
        SELECT id, name, is_albaran, is_ticket_annulled, annulment_ref, amount_total
        FROM pos_order
        WHERE config_id = 7
        ORDER BY id DESC
        LIMIT 10;
    """)
    print("Últimos 10 pedidos en E.S. Repsol:")
    for r in cur.fetchall():
        print(r)

if __name__ == '__main__':
    main()
