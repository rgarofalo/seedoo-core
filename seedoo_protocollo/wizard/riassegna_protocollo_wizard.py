# -*- coding: utf-8 -*-
# This file is part of Seedoo.  The COPYRIGHT file at the top level of
# this module contains the full copyright notices and license terms.

from openerp.osv import fields, osv
from openerp.tools.translate import _
import openerp.exceptions


class protocollo_riassegna_wizard(osv.TransientModel):
    _name = 'protocollo.riassegna.wizard'
    _description = 'Riassegna Protocollo'

    _columns = {
        'reserved': fields.boolean('Riservato', readonly=True),
        'assegnatore_department_id': fields.many2one('hr.department',
                                          "Ufficio dell'Assegnatore",
                                          domain="[('member_ids.user_id', '=', uid)]",
                                          required=True),
        'assegnatore_department_name': fields.related('assegnatore_department_id', 'name', type='char', string="Ufficio dell'Assegnatore", readonly=True),
        'assegnatario_competenza_id': fields.many2one('protocollo.assegnatario',
                                                      'Assegnatario per Competenza',
                                                      domain="[('is_visible', '=', True)]"),
        'assegnatario_conoscenza_ids': fields.many2many('protocollo.assegnatario',
                                                        'protocollo_riassegna_assegnatari_rel',
                                                        'wizard_id',
                                                        'assegnatario_id',
                                                        'Assegnatari per Conoscenza',
                                                        domain="[('is_visible', '=', True)]"),
        'assegnatario_conoscenza_disable_ids': fields.many2many('protocollo.assegnatario',
                                                        'protocollo_riassegna_assegnatari_disable_rel',
                                                        'wizard_id',
                                                        'assegnatario_id',
                                                        'Assegnatari per Conoscenza Disabilitati'),
        'motivation': fields.text('Motivazione'),
        'assegnatari_empty': fields.boolean('Assegnatari Non Presenti'),
        'assegnatari_empty_message': fields.html('Messaggio Assegnatari Non Presenti', readonly=True),
        'assegnatore_department_id_invisible': fields.boolean('Dipartimento Assegnatore Non Visibile', readonly=True),
    }

    def _default_reserved(self, cr, uid, context):
        protocollo_obj = self.pool.get('protocollo.protocollo')
        protocollo = protocollo_obj.browse(cr, uid, context['active_id'], {'skip_check': True})
        if protocollo:
            return protocollo.reserved
        return False

    def _default_assegnatore_department_id(self, cr, uid, context):
        # l'ufficio con cui si deve riassegnare è lo stesso dell'assegnazione per competenza rifiutata
        assegnazione_obj = self.pool.get('protocollo.assegnazione')
        assegnazione_ids = assegnazione_obj.search(cr, uid, [
            ('protocollo_id', '=', context['active_id']),
            ('tipologia_assegnazione', '=', 'competenza'),
            ('assegnatore_id.user_id.id', '=', uid),
            ('state', '=', 'rifiutato'),
            ('parent_id', '=', False)
        ])
        if assegnazione_ids:
            assegnazione = assegnazione_obj.browse(cr, uid, assegnazione_ids[0])
            return assegnazione.assegnatore_department_id.id
        return False

    def _default_assegnatario_conoscenza_ids(self, cr, uid, context):
        assegnazione_obj = self.pool.get('protocollo.assegnazione')
        assegnazione_ids = assegnazione_obj.search(cr, uid, [
            ('protocollo_id', '=', context['active_id']),
            ('tipologia_assegnazione', '=', 'conoscenza'),
            ('parent_id', '=', False)
        ])
        if assegnazione_ids:
            assegnatario_ids = []
            assegnazione_ids = assegnazione_obj.browse(cr, uid, assegnazione_ids)
            for assegnazione in assegnazione_ids:
                assegnatario_ids.append(assegnazione.assegnatario_id.id)
            return assegnatario_ids
        return False

    def _default_assegnatario_conoscenza_disable_ids(self, cr, uid, context):
        assegnazione_obj = self.pool.get('protocollo.assegnazione')
        assegnazione_ids = assegnazione_obj.search(cr, uid, [
            ('protocollo_id', '=', context['active_id']),
            ('tipologia_assegnazione', '=', 'conoscenza')
        ])
        if assegnazione_ids:
            assegnatario_ids = []
            assegnazione_ids = assegnazione_obj.browse(cr, uid, assegnazione_ids)
            for assegnazione in assegnazione_ids:
                assegnatario_ids.append(assegnazione.assegnatario_id.id)
                # se l'assegnazione per conoscenza è di tipo employee allora anche l'ufficio di appartenenza non
                # deve essere selezionabile, mentre gli altri appartenenti all'ufficio possono esserlo
                if assegnazione.tipologia_assegnatario == 'employee' and not assegnazione.parent_id and assegnazione.assegnatario_id.parent_id:
                    assegnatario_ids.append(assegnazione.assegnatario_id.parent_id.id)
            return assegnatario_ids
        return False

    def _default_assegnatari_empty(self, cr, uid, context):
        count = self.pool.get('protocollo.assegnatario').search(cr, uid, [], count=True, context=context)
        if count > 0:
            return False
        else:
            return True

    def _default_assegnatari_empty_message(self, cr, uid, context):
        if self._default_assegnatari_empty(cr, uid, context):
            return '''
            <h3>Non ci sono assegnatari.</h3>
            <p>Per selezionare gli assegnatari è necessario configurare gli uffici e i relativi dipendenti dalla apposita sezione di configurazione.</p>
            '''
        else:
            return False

    _defaults = {
        'reserved': _default_reserved,
        'assegnatore_department_id': _default_assegnatore_department_id,
        'assegnatario_conoscenza_ids': _default_assegnatario_conoscenza_ids,
        'assegnatario_conoscenza_disable_ids': _default_assegnatario_conoscenza_disable_ids,
        'assegnatari_empty': _default_assegnatari_empty,
        'assegnatari_empty_message': _default_assegnatari_empty_message,
        'assegnatore_department_id_invisible': True
    }

    def on_change_assegnatario_competenza_id(self, cr, uid, ids, assegnatario_competenza_id, context=None):
        data = {}
        if context and 'active_id' in context:
            assegnazione_obj = self.pool.get('protocollo.assegnazione')
            assegnazione_competenza_ids = assegnazione_obj.search(cr, uid, [
                ('protocollo_id', '=', context['active_id']),
                ('tipologia_assegnazione', '=', 'competenza'),
                ('state', '=', 'rifiutato'),
                ('parent_id', '=', False)
            ], limit=1)
            assegnazione_competenza = None
            if assegnazione_competenza_ids:
                assegnazione_competenza = assegnazione_obj.browse(cr, uid, assegnazione_competenza_ids[0])
            if assegnazione_competenza and assegnazione_competenza.assegnatario_id.id==assegnatario_competenza_id:
                data = {
                    'warning': {
                        'title': 'Attenzione',
                        'message': 'Hai selezionato lo stesso Assegnatario per Competenza che ha rifiutato l\'assegnazione!'
                    }
                }
        return data

    def check_riassegna_visibility(self, cr, uid, protocollo):
        check = protocollo.riassegna_visibility
        return check

    def salva_assegnazione_competenza(self, cr, uid, protocollo, wizard, assegnatario_ids, assegnatore_id, assegnatario_id_to_replace, before, after, values={}, context={}):
        new_context = dict(context or {})
        new_context['riassegna'] = True
        before['competenza'] = ', '.join([a.assegnatario_id.nome for a in protocollo.assegnazione_competenza_ids])
        self.pool.get('protocollo.assegnazione').salva_assegnazione_competenza(
            cr,
            uid,
            protocollo.id,
            assegnatario_ids,
            assegnatore_id,
            assegnatario_id_to_replace,
            values,
            new_context
        )
        after['competenza'] = ', '.join([a.assegnatario_id.nome for a in protocollo.assegnazione_competenza_ids])

    def salva_assegnazione_conoscenza(self, cr, uid, protocollo, wizard, assegnatore_id, before, after):
        before['conoscenza'] = ', '.join([a.assegnatario_id.nome for a in protocollo.assegnazione_conoscenza_ids])
        assegnatario_conoscenza_to_save_ids = []
        if not protocollo.reserved:
            assegnatario_conoscenza_ids = wizard.assegnatario_conoscenza_ids.ids
            for assegnatario in wizard.assegnatario_conoscenza_ids:
                if assegnatario.tipologia == 'department' or (assegnatario.parent_id and assegnatario.parent_id.id not in assegnatario_conoscenza_ids):
                    assegnatario_conoscenza_to_save_ids.append(assegnatario.id)
        self.pool.get('protocollo.assegnazione').salva_assegnazione_conoscenza(
            cr,
            uid,
            protocollo.id,
            assegnatario_conoscenza_to_save_ids,
            assegnatore_id
        )
        after['conoscenza'] = ', '.join([a.assegnatario_id.nome for a in protocollo.assegnazione_conoscenza_ids])

    def get_history_label(self, cr, uid, context):
        return "Riassegnazione"

    def action_save(self, cr, uid, ids, context=None):
        before = {'competenza': '', 'conoscenza': ''}
        after = {'competenza': '', 'conoscenza': ''}
        protocollo_obj = self.pool.get('protocollo.protocollo')
        protocollo = protocollo_obj.browse(cr, uid, context['active_id'], {'skip_check': True})
        wizard = self.browse(cr, uid, ids[0], context)
        employee_ids = self.pool.get('hr.employee').search(cr, uid, [
            ('department_id', '=', wizard.assegnatore_department_id.id),
            ('user_id', '=', uid)
        ])
        assegnatore_id = employee_ids[0] if employee_ids else False
        check = self.check_riassegna_visibility(cr, uid, protocollo)

        if not check:
            raise openerp.exceptions.Warning(_('"Non è più possibile eseguire l\'operazione richiesta!'))

        # assegnazione per competenza
        assegnatario_competenza_ids = [wizard.assegnatario_competenza_id.id] if wizard.assegnatario_competenza_id else []
        self.salva_assegnazione_competenza(cr, uid, protocollo, wizard, assegnatario_competenza_ids, assegnatore_id, False, before, after, context=context)

        # assegnazione per conoscenza
        self.salva_assegnazione_conoscenza(cr, uid, protocollo, wizard, assegnatore_id, before, after)

        action_class = "history_icon update"
        body = "<div class='%s'><ul>" % action_class
        if before['competenza'] or after['competenza']:
            body = body + "<li>%s: <span style='color:#990000'> %s</span> -> <span style='color:#007ea6'> %s </span></li>" \
                          % (protocollo_obj.get_label_competenza(cr, uid), before['competenza'], after['competenza'])
        if (before['conoscenza'] or after['conoscenza']) and before['conoscenza']!=after['conoscenza']:
            body = body + "<li>%s: <span style='color:#990000'> %s</span> -> <span style='color:#007ea6'> %s </span></li>" \
                          % ('Assegnatari Conoscenza', before['conoscenza'], after['conoscenza'])
        history_body_append = context.get('history_body_append', False)
        if history_body_append:
            body += history_body_append
        body += "</ul></div>"
        post_vars = {
            'subject': "%s%s" % (self.get_history_label(cr, uid, context), ": " + wizard.motivation if wizard.motivation else ""),
            'body': body,
            'model': "protocollo.protocollo",
            'res_id': context['active_id']
        }
        new_context = dict(context).copy()
        new_context.update({'pec_messages': True})
        protocollo_obj.message_post(cr, uid, context['active_id'], type="notification", context=new_context, **post_vars)

        return {'type': 'ir.actions.act_window_close'}
