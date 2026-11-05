#!/usr/bin/env python3
import sys

def main():
    import odoo
    from odoo import api, SUPERUSER_ID

    # Setup Odoo environment
    registry = odoo.registry('odoo')
    with registry.cursor() as cr:
        env = api.Environment(cr, SUPERUSER_ID, {})

        print("--- Disabling Digest Emails ---")

        # 1. Deactivate digest crons
        crons = env['ir.cron'].sudo().search([
            '|',
            ('cron_name', 'ilike', 'digest'),
            ('ir_actions_server_id.model_name', '=', 'digest.digest')
        ])
        for cron in crons:
            print(f"Disabling cron: ID={cron.id}, name={cron.cron_name}, active={cron.active}")
            cron.active = False

        # 2. Deactivate all digest.digest records and clear subscribed users
        if 'digest.digest' in env:
            digests = env['digest.digest'].sudo().search([])
            for d in digests:
                print(f"Deactivating digest: ID={d.id}, name={d.name}, state={d.state}, users_count={len(d.user_ids)}")
                d.write({
                    'state': 'deactivated',
                    'user_ids': [(5, 0, 0)]  # Clear all subscribed users
                })

        # 3. Disable auto-subscription system parameter
        env['ir.config_parameter'].sudo().set_param('digest.default_digest_emails', False)
        param_digest_id = env['ir.config_parameter'].sudo().search([('key', '=', 'digest.default_digest_id')])
        if param_digest_id:
            param_digest_id.unlink()
        print("Config parameter digest.default_digest_emails set to False")

        # 4. Cancel / purge pending or exception digest emails in mail.mail
        if 'mail.mail' in env:
            mails = env['mail.mail'].sudo().search([
                '|',
                ('subject', 'ilike', 'resumen periódico'),
                ('subject', 'ilike', 'digest')
            ])
            print(f"Found {len(mails)} digest mails in mail.mail. Canceling / unlinking...")
            for mail in mails:
                try:
                    mail.unlink()
                except Exception as e:
                    mail.write({'state': 'cancel'})

        cr.commit()
        print("--- All Digest Emails successfully deactivated and cleaned up! ---")

if __name__ == '__main__':
    main()
