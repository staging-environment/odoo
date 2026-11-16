# -*- coding: utf-8 -*-
"""
Script de rectificación de series de anulación y secuencias oficiales en Odoo.
Aplica la nomenclatura NOMENCLATURA_AÑONUMERO para todas las anulaciones:
- Tickets anulados: TTTR_2026XXXXX (contador propio independiente)
- Albaranes anulados: AVTR_2026XXXXX (contador propio independiente)
- Facturas anuladas: FTTR_2026XXXXX (contador propio independiente)
"""
import psycopg2

def main():
    conn = psycopg2.connect("host=db port=5432 dbname=odoo user=db password=db")
    cur = conn.cursor()
    
    print("=== INICIANDO RECTIFICACIÓN DE SERIES DE ANULACIÓN ===")
    
    # 1. RECTIFICACIÓN DE ALBARANES ANULADOS
    # Pares (id_original, id_negativo)
    albaran_pairs = [
        (15652, 15653),
        (15655, 15656),
        (15658, 15659),
    ]
    
    print("\n--- 1. Rectificando Albaranes Anulados ---")
    for idx, (orig_id, neg_id) in enumerate(albaran_pairs, start=1):
        annul_ref = f"AVTR_2026{idx:05d}"
        print(f"Albarán Original {orig_id} & Negativo {neg_id} -> {annul_ref}")
        
        # Actualizar original
        cur.execute("""
            UPDATE pos_order
            SET annulment_ref = %s,
                annulment_reason = %s
            WHERE id = %s;
        """, (annul_ref, f"Anulado por Albarán Negativo {annul_ref}", orig_id))
        
        # Actualizar negativo
        cur.execute("""
            UPDATE pos_order
            SET name = %s,
                pos_reference = %s,
                annulment_ref = %s
            WHERE id = %s;
        """, (annul_ref, annul_ref, annul_ref, neg_id))

    # 2. RECTIFICACIÓN DE FACTURAS ANULADAS
    invoice_annuls = [
        (15654, 10465, 'FTTR/2026/00010'),  # po_id, rev_move_id, orig_inv_name
        (15657, 10468, 'FTTR/2026/00011'),
    ]
    
    print("\n--- 2. Rectificando Facturas Anuladas ---")
    for idx, (po_id, rev_id, orig_inv_name) in enumerate(invoice_annuls, start=1):
        annul_ref = f"FTTR_2026{idx:05d}"
        print(f"Pedido {po_id} (Rev Move {rev_id}) -> {annul_ref}")
        
        cur.execute("""
            UPDATE pos_order
            SET annulment_ref = %s,
                annulment_reason = %s
            WHERE id = %s;
        """, (annul_ref, f"Anulación de Factura {orig_inv_name}", po_id))
        
        cur.execute("""
            UPDATE account_move
            SET name = %s,
                ref = %s
            WHERE id = %s;
        """, (annul_ref, annul_ref, rev_id))

    # 3. RECTIFICACIÓN DE TICKETS ANULADOS
    ticket_annul_ids = [
        15600, 15602, 15603, 15610, 15615, 15616, 15623, 15626, 15628, 
        15631, 15632, 15633, 15639, 15649, 15650, 15651, 15660, 15662, 
        15664, 15665, 15666
    ]
    
    print("\n--- 3. Rectificando Tickets Anulados ---")
    for idx, t_id in enumerate(ticket_annul_ids, start=1):
        annul_ref = f"TTTR_2026{idx:05d}"
        print(f"Ticket Anulado {t_id} -> {annul_ref}")
        cur.execute("""
            UPDATE pos_order
            SET annulment_ref = %s
            WHERE id = %s;
        """, (annul_ref, t_id))

    # 4. CONFIGURACIÓN DE SECUENCIAS OFICIALES EN IR_SEQUENCE
    print("\n--- 4. Configurando Secuencias Oficiales en ir_sequence ---")
    
    # Obtener company_id de la estación Repsol (config_id = 7)
    cur.execute("SELECT company_id FROM pos_config WHERE id = 7;")
    row = cur.fetchone()
    company_id = row[0] if row else 1
    
    # A) Secuencia de Tickets Anulados (E.S. Repsol)
    # Secuencia código 'pos.order.annulment.ticket.7' y actualizar id 156
    next_ticket_annul = len(ticket_annul_ids) + 1  # 22
    cur.execute("""
        UPDATE ir_sequence
        SET code = 'pos.order.annulment.ticket.7',
            name = 'Secuencia de Anulación Ticket TPV E.S. Repsol',
            prefix = 'TTTR_%%(year)s',
            padding = 5,
            number_next = %s,
            number_increment = 1
        WHERE id = 156 OR code = 'pos.order.annulment.7';
    """, (next_ticket_annul,))
    print(f"Secuencia Ticket Anulado (pos.order.annulment.ticket.7): number_next={next_ticket_annul}")

    # B) Secuencia de Albaranes Anulados (E.S. Repsol)
    next_albaran_annul = len(albaran_pairs) + 1  # 4
    cur.execute("SELECT id FROM ir_sequence WHERE code = 'pos.order.annulment.albaran.7';")
    alb_seq = cur.fetchone()
    if alb_seq:
        cur.execute("""
            UPDATE ir_sequence
            SET prefix = 'AVTR_%%(year)s',
                padding = 5,
                number_next = %s,
                number_increment = 1
            WHERE id = %s;
        """, (next_albaran_annul, alb_seq[0]))
    else:
        cur.execute("""
            INSERT INTO ir_sequence (name, code, prefix, padding, number_next, number_increment, company_id, implementation)
            VALUES ('Secuencia de Anulación Albarán TPV E.S. Repsol', 'pos.order.annulment.albaran.7', 'AVTR_%%(year)s', 5, %s, 1, %s, 'standard');
        """, (next_albaran_annul, company_id))
    print(f"Secuencia Albarán Anulado (pos.order.annulment.albaran.7): number_next={next_albaran_annul}")

    # C) Secuencia de Facturas Anuladas (E.S. Repsol)
    next_inv_annul = len(invoice_annuls) + 1  # 3
    cur.execute("SELECT id FROM ir_sequence WHERE code = 'pos.order.annulment.invoice.7';")
    inv_seq = cur.fetchone()
    if inv_seq:
        cur.execute("""
            UPDATE ir_sequence
            SET prefix = 'FTTR_%%(year)s',
                padding = 5,
                number_next = %s,
                number_increment = 1
            WHERE id = %s;
        """, (next_inv_annul, inv_seq[0]))
    else:
        cur.execute("""
            INSERT INTO ir_sequence (name, code, prefix, padding, number_next, number_increment, company_id, implementation)
            VALUES ('Secuencia de Anulación Factura TPV E.S. Repsol', 'pos.order.annulment.invoice.7', 'FTTR_%%(year)s', 5, %s, 1, %s, 'standard');
        """, (next_inv_annul, company_id))
    print(f"Secuencia Factura Anulada (pos.order.annulment.invoice.7): number_next={next_inv_annul}")

    # D) Secuencia de Pedidos Normales de TPV E.S. Repsol (id 54)
    # Formato NOMENCLATURAAÑONUMERO: TTTR2026XXXXX
    cur.execute("""
        UPDATE ir_sequence
        SET prefix = 'TTTR%%(year)s',
            padding = 5
        WHERE id = 54;
    """)
    print("Secuencia Pedido TPV E.S. Repsol (id 54): prefix='TTTR%(year)s', padding=5")

    conn.commit()
    print("\n=== RECTIFICACIÓN COMPLETADA Y CONFIRMADA CON ÉXITO ===")

if __name__ == '__main__':
    main()
