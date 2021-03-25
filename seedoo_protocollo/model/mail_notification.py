# -*- coding: utf-8 -*-
# This file is part of Seedoo.  The COPYRIGHT file at the top level of
# this module contains the full copyright notices and license terms.

from openerp import models, api, tools


class MailNotification(models.Model):
    _inherit = 'mail.notification'

    @api.model
    def get_signature_user(self):
        if self.env.user.signature:
            return tools.append_content_to_html('<br/><br/>--<br/>', self.env.user.signature, plaintext=False)
        return False

    @api.model
    def get_signature_footer(self, user_id, res_model=None, res_id=None, user_signature=True):
        signature_footer = super(MailNotification, self).get_signature_footer(user_id, res_model=res_model, res_id=res_id, user_signature=user_signature)
        if signature_footer:
            signature_footer = signature_footer.replace(
                "<a style='color:inherit' href='https://www.odoo.com/'>Odoo</a>",
                "<a style='color:inherit' href='https://www.seedoo.it/r/oxa'>Seedoo</a>"
            )
        return signature_footer