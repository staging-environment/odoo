import psycopg2

def main():
    conn = psycopg2.connect("host=db port=5432 dbname=odoo user=db password=db")
    cur = conn.cursor()
    cur.execute("""
        SELECT po.id, po.name, po.account_move, am.name as move_name, po.is_ticket_annulled, po.to_invoice
        FROM pos_order po
        LEFT JOIN account_move am ON am.id = po.account_move
        WHERE po.session_id = 51
        ORDER BY po.id DESC;
    """)
    print("Orders in session 51:")
    for r in cur.fetchall():
        print(r)

if __name__ == '__main__':
    main()














