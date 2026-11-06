import odoo
from odoo import api, SUPERUSER_ID

def main():
    registry = odoo.registry('odoo')
    with registry.cursor() as cr:
        env = api.Environment(cr, SUPERUSER_ID, {})
        
        # 1. Limpiar prefijo ASEPRODA- de los clientes migrados
        cr.execute("SELECT COUNT(*) FROM res_partner WHERE ref LIKE 'ASEPRODA-%';")
        count_ase = cr.fetchone()[0]
        print(f"Clientes con prefijo ASEPRODA- encontrados: {count_ase}")
        
        if count_ase > 0:
            cr.execute("UPDATE res_partner SET ref = REPLACE(ref, 'ASEPRODA-', '') WHERE ref LIKE 'ASEPRODA-%';")
            print(f"✅ Actualizados {count_ase} clientes a código numérico limpio.")

        # 2. Asignar código a clientes creados de prueba que tenían ref = False
        cr.execute("""
            SELECT id, name FROM res_partner 
            WHERE customer_rank > 0 AND (ref IS NULL OR ref = '') AND id NOT IN (
                SELECT partner_id FROM res_company WHERE partner_id IS NOT NULL
            )
            AND id NOT IN (
                SELECT partner_id FROM res_users WHERE partner_id IS NOT NULL
            )
            ORDER BY id ASC;
        """)
        null_customers = cr.fetchall()
        print(f"Clientes sin código a procesar: {len(null_customers)}")
        
        # Buscar el máximo actual numérico < 9999
        cr.execute("""
            SELECT COALESCE(MAX(CAST(ref AS INTEGER)), 1957)
            FROM res_partner
            WHERE ref ~ '^[0-9]+$' AND CAST(ref AS INTEGER) < 9999;
        """)
        current_max = cr.fetchone()[0]
        print(f"Máximo código actual en BD (<9999): {current_max}")

        next_code = current_max + 1
        for cid, name in null_customers:
            cr.execute("UPDATE res_partner SET ref = %s WHERE id = %s;", (str(next_code), cid))
            print(f"  -> Asignado código {next_code} a cliente ID {cid} ({name})")
            next_code += 1

        # 3. Ajustar la secuencia ir.sequence para que el siguiente arranque exactamente en next_code
        seq = env.ref('pos_gas_station.seq_partner_customer_code', raise_if_not_found=False)
        if not seq:
            seq_obj = env['ir.sequence'].search([('code', '=', 'res.partner.customer.code')], limit=1)
            if seq_obj:
                seq = seq_obj
        if seq:
            seq.write({'number_next': next_code})
            print(f"✅ Secuencia 'res.partner.customer.code' fijada en siguiente número: {next_code}")
        else:
            print(f"ℹ️ Secuencia se inicializará con number_next={next_code} al actualizar el módulo.")

        cr.commit()
        print("🎉 Proceso de normalización de códigos de cliente completado con éxito.")

if __name__ == '__main__':
    main()
