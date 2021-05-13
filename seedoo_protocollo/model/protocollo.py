# -*- coding: utf-8 -*-
# This file is part of Seedoo.  The COPYRIGHT file at the top level of
# this module contains the full copyright notices and license terms.
import base64
import datetime
import json
import logging
import mimetypes
import os
import shutil
import subprocess
import threading
import time

import magic
import pytz
import requests
from lxml import etree

import openerp.exceptions
from openerp import SUPERUSER_ID
from openerp import netsvc, tools
from openerp.osv import orm, fields, osv
from openerp.tools import DEFAULT_SERVER_DATETIME_FORMAT as DSDF
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT as DSDT
from openerp.tools.translate import _
from ..segnatura.annullamento_xml import AnnullamentoXML
from ..segnatura.conferma_xml import ConfermaXML
from ..segnatura.segnatura_xml import SegnaturaXML

_logger = logging.getLogger(__name__)
mimetypes.init()


def convert_datetime(value, from_timezone="UTC", to_timezone="Europe/Rome", format_from='%Y-%m-%d %H:%M:%S', format_to='%Y-%m-%d %H:%M:%S', to_datetime=False):
    if not value:
        return None

    timezone_from = pytz.timezone(from_timezone)
    timezone_to = pytz.timezone(to_timezone)

    stripped_value = value.split(".")[0]
    datetime_from = datetime.datetime.strptime(stripped_value, format_from)
    localized_value = timezone_from.localize(datetime_from)
    datetime_to = localized_value.astimezone(timezone_to)

    if to_datetime:
        return datetime_to

    return datetime_to.strftime(format_to)


class protocollo_typology(orm.Model):
    _name = 'protocollo.typology'
    _order = 'display_order, name'

    def _is_visible(self, cr, uid, ids, name, arg, context=None):
        return {}

    def _is_visible_search(self, cr, uid, obj, name, args, domain=None, context=None):
        domain = []
        if 'type' in context and context['type']=='in' and 'mail_pec_ref' in context and not context['mail_pec_ref']:
            domain = [('sharedmail','=',False),('pec','=',False)]
        typology_ids = self.search(cr, uid, domain)
        return [('id', 'in', typology_ids)]

    _columns = {
        'name': fields.char('Nome', size=256, required=True),
        'sharedmail': fields.boolean('Shared Mail'),
        'pec': fields.boolean('PEC'),
        'aoo_id': fields.many2one('protocollo.aoo', 'AOO', required=True),
        'display_order': fields.integer('Ordine visualizzazione'),
        'active': fields.boolean('Attivo'),
        'is_visible': fields.function(_is_visible, fnct_search=_is_visible_search, type='boolean', string='Visibile'),
    }

    def _get_default_aoo_id(self, cr, uid, context=None):
        aoo_ids = self.pool.get('protocollo.aoo').search(cr, uid, [], context=context)
        if len(aoo_ids) > 0:
            return aoo_ids[0]
        return False

    _defaults = {
        'aoo_id': _get_default_aoo_id,
        'display_order': 100,
        'active': True
    }


class protocollo_registry(orm.Model):
    _name = 'protocollo.registry'

    def _get_first_aoo_id(self, cr, uid, ids, field, arg, context=None):
        if isinstance(ids, (list, tuple)) and not len(ids):
            return []
        if isinstance(ids, (long, int)):
            ids = [ids]
        res = dict.fromkeys(ids, False)
        for registry in self.browse(cr, uid, ids):
            for aoo in registry.aoo_ids:
                res[registry.id] = aoo.id
                break
        return res

    _columns = {
        'name': fields.char('Nome Registro', char=256, required=True),
        'code': fields.char('Codice Registro', char=16, required=True),
        'description': fields.text('Descrizione Registro'),
        'sequence': fields.many2one('ir.sequence', 'Sequenza', required=True, readonly=True),
        'office_ids': fields.many2many('hr.department', 'protocollo_registry_office_rel', 'registry_id', 'office_id',
                                       'Uffici Abilitati'),
        # TODO check for company in registry and emergency registry
        'company_id': fields.many2one('res.company', 'Ente', required=True, readonly=True),
        'priority': fields.integer('Priorità Registro'),
        # 'allowed_users': fields.many2many(
        #    'res.users', 'registry_res_users_rel',
        #    'user_id', 'registryt_id', 'Allowed Users',
        #    required=True),
        'allowed_employee_ids': fields.many2many('hr.employee', 'protocollo_registry_hr_employee_rel',
                                                 'registry_id', 'employee_id', 'Dipendenti Abilitati'),
        'aoo_ids': fields.one2many('protocollo.aoo', 'registry_id', 'AOO'),
        'first_aoo_id': fields.function(_get_first_aoo_id, type='many2one', relation='protocollo.aoo', string='AOO'),
    }

    def get_registry_for_user(self, cr, uid):
        ids = self.search(cr, uid, [('allowed_users', 'in', [uid])])
        if ids:
            return ids[0]
        else:
            return []

    def assign_employee_to_registry(self, cr, uid, aoo_id, employee_id):
        aoo = self.pool.get('protocollo.aoo').browse(cr, uid, aoo_id)

        # if aoo and aoo.registry_id and aoo.registry_id.allowed_employee_ids:
        self.write(cr, uid, [aoo.registry_id.id], {'allowed_employee_ids':
                                                       [(6, 0, [employee_id[0]])],
                                                   })
        # self.write(cr, uid, [aoo.id], {'ident_code': '1'
        # })
        # for employee in aoo.registry_id.allowed_employee_ids:
        #     if employee.user_id and employee.user_id.id == user.id and self._office_check(cr, uid, user, aoo):
        #         return True
        return True

    def unlink(self, cr, uid, ids, context=None):
        reg = self.browse(cr, uid, ids, context=context)
        sequence_obj = self.pool.get('ir.sequence')
        sequence_type_obj = self.pool.get('ir.sequence.type')
        seq_id = reg.sequence.id
        seq_code = reg.sequence.code
        res = super(protocollo_registry, self).unlink(cr, uid, ids, context=context)
        if res:
            seq_type = sequence_type_obj.search(cr, uid, [('code', '=', seq_code)])
            sequence_type_obj.unlink(cr, SUPERUSER_ID, seq_type)
            sequence_obj.unlink(cr, SUPERUSER_ID, seq_id)
        return True


class protocollo_protocollo(orm.Model):
    _name = 'protocollo.protocollo'
    _description = 'Protocollo'
    _inherit = 'mail.thread'
    _mail_flat_thread = False
    _order = 'id desc'

    STATE_SELECTION = [
        ('draft', 'Bozza'),
        ('registered', 'Registrato'),
        ('waiting', 'Pec Inviata'),
        ('error', 'Errore Pec'),
        ('sent', 'Inviato'),
        ('canceled', 'Annullato')
    ]

    def get_state_list(self, cr, uid, context=None):
        return self.STATE_SELECTION

    def get_history_state_list(self, cr, uid):
        return ['registered', 'waiting', 'error', 'sent', 'canceled']

    def seedoo_error(self, cr, uid):
        user = self.pool.get('res.users').browse(cr, SUPERUSER_ID, uid)

        if not user.profile_id:
            return _(
                "L'utente %s non è abilitato alla protocollazione: deve avere associato ad un profilo Seedoo"
            ) % user.name

        if len(user.employee_ids.ids) == 0:
            return _(
                "L'utente %s non è abilitato alla protocollazione: deve essere associato ad un dipendente"
            ) % user.name

        # if len(user.employee_ids.ids) > 1:
        #     return _(
        #         "L'utente %s non è configurato correttamente: deve essere associato ad un unico dipendente") % user.name

        department_ids = self.pool.get('hr.department').search(cr, uid, [('member_ids.user_id', '=', uid)])
        if len(department_ids) == 0:
            return _(
                "L'utente %s non è abilitato alla protocollazione: deve essere associato ad un ufficio"
            ) % user.name

        department_ids = self.pool.get('hr.department').search(cr, uid, [('can_used_to_protocol', '=', True)])
        if len(department_ids) == 0:
            return _(
                "L'utente %s non è abilitato alla protocollazione: configurare correttamente l'ufficio, la AOO o il relativo registro"
            ) % user.name

        return ''

    # def view_init(self, cr, uid, fields_list, context=None):
    #     error = self.seedoo_error(cr, uid)
    #     if error:
    #         raise osv.except_osv(_('Warning!'), error)

    pass

    def on_change_emergency_receiving_date(self, cr, uid, ids, emergency_receiving_date, context=None):
        values = {}
        if emergency_receiving_date:
            emergency_registry_obj = self.pool.get('protocollo.emergency.registry')
            aoo_id = self._get_default_aoo_id(cr, uid)
            if aoo_id:
                reg_ids = emergency_registry_obj.search(cr, uid, [
                    ('aoo_id', '=', aoo_id),
                    ('state', '=', 'draft')
                ])
                if len(reg_ids) > 0:
                    emergency_registry = emergency_registry_obj.browse(cr, SUPERUSER_ID, reg_ids[0])

                    if emergency_receiving_date < emergency_registry.date_start or emergency_receiving_date > emergency_registry.date_end:


                        datetime_start = datetime.datetime.strptime(emergency_registry.date_start, '%Y-%m-%d %H:%M:%S')
                        datetime_end = datetime.datetime.strptime(emergency_registry.date_end, '%Y-%m-%d %H:%M:%S')
                        raise orm.except_orm(_('Avviso'),
                                             _(
                                                 'La data di registrazione deve essere compresa nel periodo di apertura del registro di emergenza dal: %s al: %s'
                                             %(datetime_start.strftime('%d-%m-%Y'), datetime_end.strftime('%d-%m-%Y'))))

                    values = {
                        'receiving_date': emergency_receiving_date
                    }
        return {'value': values}

    def on_change_datas(self, cr, uid, ids, datas, context=None):
        values = {}
        if datas:
            ct = magic.from_buffer(base64.b64decode(datas), mime=True)
            values = {
                'preview': datas,
                'preview_image': datas,
                'mimetype': ct
            }
        return {'value': values}

    def on_change_typology(self, cr, uid, ids, typology_id, body, context=None):
        values = {'pec': False, 'sharedmail': False, 'inserisci_testo_mailpec_visibility': False}
        if typology_id:
            typology_obj = self.pool.get('protocollo.typology')
            typology = typology_obj.browse(cr, uid, typology_id)
            configurazione_ids = self.pool.get('protocollo.configurazione').search(cr, uid, [])
            configurazione = self.pool.get('protocollo.configurazione').browse(cr, uid, configurazione_ids[0])
            body = configurazione.inserisci_testo_mailpec
            values['inserisci_testo_mailpec_visibility'] = body
            if typology.pec:
                values['pec'] = True
                values['sharedmail'] = False
            if typology.sharedmail:
                values['pec'] = False
                values['sharedmail'] = True
        return {'value': values}

    def on_change_registration_employee_department(self, cr, uid, ids, department_id, context=None):
        values = {'registration_employee_department_id': department_id}
        values = self._verifica_registration_employee(cr, uid, values, context)
        return {'value': values}

    def calculate_complete_name(self, prot_date, prot_number):
        year = prot_date[:4]
        return year + prot_number

    def name_get(self, cr, uid, ids, context=None):
        if isinstance(ids, (list, tuple)) and not len(ids):
            return []
        if isinstance(ids, (long, int)):
            ids = [ids]
        reads = self.read(cr, uid, ids, ['name', 'registration_date', 'state'], {'skip_check': True})
        res = []
        for record in reads:
            name = record['name']
            if record['registration_date']:
                name = self.calculate_complete_name(record['registration_date'], name)
                # year = record['registration_date'][:4]
                # name = year + name
            res.append((record['id'], name))
        return res

    def _get_complete_name(self, cr, uid, ids, prop, unknow_none, context=None):
        res = self.name_get(cr, uid, ids, context=context)
        return dict(res)

    def _get_complete_name_search(self, cursor, user, obj, name, args, domain=None, context=None):
        res = []
        return [('id', 'in', res)]

    def _get_pec_notifications_sum(self, cr, uid, ids, field, arg, context=None):
        if isinstance(ids, (list, tuple)) and not len(ids):
            return []
        if isinstance(ids, (long, int)):
            ids = [ids]
        res = dict.fromkeys(ids, False)
        for prot in self.browse(cr, uid, ids, {'skip_check': True}):
            if prot.sender_receivers:
                check_notifications = 0
                for sender_receiver_id in prot.sender_receivers.ids:
                    sender_receiver_obj = self.pool.get('protocollo.sender_receiver').browse(cr, uid,
                                                                                             sender_receiver_id,
                                                                                             context=context)
                    # if sender_receiver_obj.pec_accettazione_status and sender_receiver_obj.pec_consegna_status:
                    #     check_notifications += 1
                if check_notifications == len(prot.sender_receivers.ids):
                    res[prot.id] = True
        return res

    def _get_assegnatari_competenza(self, cr, uid, protocollo):
        employees = []
        for assegnazione_competenza in protocollo.assegnazione_competenza_ids:
            if assegnazione_competenza.tipologia_assegnatario == 'department':
                for assegnazione_competenza_child in assegnazione_competenza.child_ids:
                    employees.append(assegnazione_competenza_child.assegnatario_employee_id)
            else:
                employees.append(assegnazione_competenza.assegnatario_employee_id)
        employees = list(set(employees))
        return employees

    def _get_assegnatari_conoscenza(self, cr, uid, protocollo):
        employees = []
        for assegnazione_conoscenza in protocollo.assegnazione_conoscenza_ids:
            if assegnazione_conoscenza.tipologia_assegnatario == 'department':
                for assegnazione_conoscenza_child in assegnazione_conoscenza.child_ids:
                    employees.append(assegnazione_conoscenza_child.assegnatario_employee_id)
            else:
                employees.append(assegnazione_conoscenza.assegnatario_employee_id)
        employees = list(set(employees))
        return employees

    def _get_assigne_emails(self, cr, uid, ids, field, arg, context=None):
        if isinstance(ids, (list, tuple)) and not len(ids):
            return []
        if isinstance(ids, (long, int)):
            ids = [ids]
        res = dict.fromkeys(ids, False)
        emails = ''
        for prot in self.browse(cr, uid, ids):
            assegnatari_competenza = self._get_assegnatari_competenza(cr, uid, prot)
            assegnatari_conoscenza = self._get_assegnatari_conoscenza(cr, uid, prot)
            assegnatari = list(set(assegnatari_competenza + assegnatari_conoscenza))
            assegnatari_emails = []
            for assegnatario in assegnatari:
                if assegnatario.user_id and assegnatario.user_id.email:
                    assegnatari_emails.append(assegnatario.user_id.email)
            emails = ','.join(assegnatari_emails)
            res[prot.id] = emails
        return res

    def _get_preview_datas(self, cr, uid, ids, field, arg, context=None):
        if isinstance(ids, (list, tuple)) and not len(ids):
            return []
        if isinstance(ids, (long, int)):
            ids = [ids]
        res = dict.fromkeys(ids, False)
        for prot in self.browse(cr, uid, ids, {'skip_check': True}):
            res[prot.id] = prot.doc_id.datas
        return res

    def _get_preview_image_datas(self, cr, uid, ids, field, arg, context=None):
        if isinstance(ids, (list, tuple)) and not len(ids):
            return []
        if isinstance(ids, (long, int)):
            ids = [ids]
        res = dict.fromkeys(ids, False)
        for prot in self.browse(cr, uid, ids, {'skip_check': True}):
            if prot.mimetype in ['image/png', 'image/jpeg', 'image/gif']:
                res[prot.id] = prot.doc_id.datas
            else:
                res[prot.id] = False
        return res

    def _get_assigne_emails_search(self, cursor, user, obj, name,
                                   args, domain=None, context=None):
        res = []
        return [('id', 'in', res)]

    def _get_senders_summary(self, cr, uid, ids, name, args, context=None):
        res = dict.fromkeys(ids, False)
        for protocol in self.browse(cr, uid, ids, {'skip_check': True}):
            if protocol.type != 'in':
                res[protocol.id] = protocol.sender_internal_name
            else:
                res[protocol.id] = u"\n".join([line.name for line in protocol.senders])
        return res

    def _get_receivers_summary(self, cr, uid, ids, name, args, context=None):
        res = dict.fromkeys(ids, False)
        for protocol in self.browse(cr, uid, ids, {'skip_check': True}):
            if protocol.type == 'out':
                res[protocol.id] = u"\n".join([line.name for line in protocol.receivers])
            else:
                res[protocol.id] = ''
        return res

    def action_apri_stampa_etichetta(self, cr, uid, ids, context=None):
        context = dict(context or {})

        if len(ids) != 1:
            raise osv.except_osv(
                _("Error!"),
                _("This action can be triggered for one record only")
            )

        # for session in self.browse(cr, uid, ids, context=context):
        #     if session.user_id.id != uid:
        #         raise osv.except_osv(
        #             _('Error!'),
        #             _(
        #                 "You cannot use the session of another users. This session is owned by %s. Please first close this one to use this point of sale." % session.user_id.name))

        protocolloid = ids[0]

        context.update({
            "active_id": protocolloid
        })

        action_class = "history_icon print"

        post_vars = {
            "subject": "Stampa Etichetta",
            "body": "<div class='%s'><ul><li>Generata l'etichetta</li></ul></div>" % action_class,
            "model": "protocollo.protocollo",
            "res_id": protocolloid,
        }

        protocollo_obj = self.pool.get("protocollo.protocollo")
        protocollo_obj.message_post(cr, uid, protocolloid, type="notification", context=context, **post_vars)

        protocollo_id = protocollo_obj.browse(cr, uid, [protocolloid], context)

        result_filename = "%04d%s.pdf" % (protocollo_id.year, protocollo_id.name)

        return {
            "type": "ir.actions.act_url",
            "url": "/seedoo/etichetta/%s" % result_filename
        }

    _columns = {
        'complete_name': fields.function(
            _get_complete_name, type='char', size=256,
            string='N. Protocollo'),
        'name': fields.char('Numero Protocollo',
                            size=256,
                            readonly=True),
        'registration_date': fields.datetime('Data Registrazione',
                                             readonly=True),
        'registration_date_from': fields.function(
            lambda *a, **k: {}, method=True,
            type='date', string="Inizio Data Ricerca"),
        'registration_date_in': fields.function(lambda *a, **k: {},
                                                method=True,
                                                type='date',
                                                string="Data Ricerca"),
        'registration_date_to': fields.function(lambda *a, **k: {},
                                                method=True,
                                                type='date',
                                                string="Fine Data Ricerca"),
        'create_uid': fields.many2one('res.users', 'Utente Creatore del Protocollo', readonly=True),
        'user_id': fields.many2one('res.users', 'Utente del Protocollatore', readonly=True),
        'registration_employee_id': fields.many2one('hr.employee', 'Protocollatore', readonly=True),
        'registration_employee_name': fields.char('Protocollatore', size=512, readonly=True),
        'registration_employee_department_id': fields.many2one('hr.department', 'Ufficio'),
        'registration_employee_department_name': fields.char('Ufficio', size=512),
        'registration_employee_department_id_readonly': fields.boolean('Campo registration_employee_department_id readonly', readonly=True),
        'registration_employee_state': fields.selection([('working', 'In Lavorazione')], 'Stato Protocollatore', size=32, readonly=True),
        'registration_type': fields.selection(
            [
                ('normal', 'Normale'),
                ('emergency', 'Emergenza'),
            ], 'Tipologia Registrazione', size=32, required=True,
            readonly=True,
            states={'draft': [('readonly', False)]}, ),
        'type': fields.selection(
            [
                ('out', 'Uscita'),
                ('in', 'Ingresso')
            ], 'Tipo', size=32, required=True, readonly=True),
        'typology': fields.many2one(
            'protocollo.typology', 'Mezzo Trasmissione', readonly=True, required=False,
            states={'draft': [('readonly', False)]}),
        'reserved': fields.boolean('Riservato',
                                   readonly=True,
                                   states={'draft': [('readonly', False)]},
                                   help="Se il protocollo e' riservato \
                                   il documento risulta visibile solo \
                                   all'ufficio di competenza"),
        'pec': fields.related('typology',
                              'pec',
                              type='boolean',
                              string='PEC',
                              readonly=False,
                              store=False),
        'sharedmail': fields.related('typology',
                                     'sharedmail',
                                     type='boolean',
                                     string='Sharedmail',
                                     readonly=False,
                                     store=False),
        'email_pec_sending_mode': fields.selection([('all_receivers', 'Un messaggio per tutti i destinatari')], 'Modalità Invio', size=32),
        'body': fields.html('Corpo della mail', readonly=True),
        'mail_pec_ref': fields.many2one('mail.message',
                                        'Riferimento PEC',
                                        readonly=True),
        'mail_sharedmail_ref': fields.many2one('mail.message',
                                               'Riferimento Mail',
                                               readonly=True),
        'mail_out_ref': fields.many2one('mail.mail',
                                        'Riferimento mail in uscita',
                                        readonly=True),
        'pec_notifications_ids': fields.related('mail_pec_ref',
                                                'pec_notifications_ids',
                                                type='one2many',
                                                relation='mail.message',
                                                string='Notification Messages',
                                                readonly=True),
        'pec_notifications_sum': fields.function(_get_pec_notifications_sum,
                                                 type="char",
                                                 string="PEC Status",
                                                 store=False),
        'creation_date': fields.date('Data Creazione',
                                     required=True,
                                     readonly=True,
                                     ),
        'receiving_date': fields.datetime('Data Ricezione',
                                          required=False,
                                          readonly=True,
                                          states={
                                              'draft': [('readonly', False)]
                                          }),
        'receiving_date_from': fields.function(
            lambda *a, **k: {}, method=True,
            type='date', string="Inizio Data ricezione Ricerca"),
        'receiving_date_to': fields.function(lambda *a, **k: {},
                                             method=True,
                                             type='date',
                                             string="Fine  Data ricezione Ricerca"),
        'subject': fields.text('Oggetto',
                               required=False,
                               readonly=True),
        'datas_fname': fields.char(
            'Nome Documento', size=256, readonly=False),
        'datas': fields.binary('File Documento',
                               required=False),
        'preview': fields.function(_get_preview_datas,
                                   type='binary',
                                   string='Preview'),
        'preview_image': fields.function(_get_preview_image_datas,
                                         type='binary',
                                         string='Preview Image'),
        'mimetype': fields.char('Mime Type', size=64),
        'doc_id': fields.many2one(
            'ir.attachment', 'Documento Principale', readonly=True,
            domain="[('res_model', '=', 'protocollo.protocollo')]"),
        'doc_content': fields.related('doc_id', 'datas', type='binary', string='Documento', readonly=True),
        'doc_description': fields.related('doc_id', 'datas_description', type='char', string='Descrizione',
                                          readonly=True),
        'doc_fname': fields.related('doc_id', 'datas_fname', type="char", readonly=True),
        'fingerprint': fields.char(string="Impronta Documento", size=256),
        'classification': fields.many2one('protocollo.classification',
                                          'Titolario di Classificazione',
                                          required=False,
                                          readonly=True,
                                          states={
                                              'draft': [('readonly', False)]
                                          }),
        'classification_name': fields.char('Codice e Nome Titolario', size=256, readonly=True),
        'emergency_protocol': fields.char(
            'Numero Protocollo in Emergenza', size=64, required=False,
            readonly=True,
            states={'draft': [('readonly', False)]}),
        'emergency_receiving_date': fields.datetime(
            'Data Registrazione in Emergenza', required=False,
            readonly=True,
            states={'draft': [('readonly', False)]}),
        'emergency_active': fields.boolean('Registro Emergenza Attivo'),
        'sender_protocol': fields.char('Protocollo Mittente',
                                       size=64,
                                       required=False,
                                       readonly=True,
                                       states={'draft': [('readonly', False)]
                                               }),
        'sender_register': fields.char('Registro Mittente',
                                       size=64,
                                       required=False,
                                       readonly=True),
        'sender_registration_date': fields.date('Data Registrazione Mittente',
                                                size=64,
                                                required=False,
                                                ),
        'sender_internal_assegnatario': fields.many2one('protocollo.assegnatario', 'Assegnatario Mittente Interno'),
        'sender_internal_name': fields.char('Protocollazione Interna Nome', size=512, readonly=True),
        'sender_internal_employee': fields.many2one('hr.employee', 'Protocollazione Interna Dipendente', required=False),
        'sender_internal_employee_department': fields.many2one('hr.department', 'Protocollazione Interna Ufficio del Dipendente', required=False),
        'sender_internal_department': fields.many2one('hr.department', 'Protocollazione Interna Ufficio', required=False),
        'sender_receivers': fields.one2many('protocollo.sender_receiver', 'protocollo_id', 'Mittenti/Destinatari'),
        'senders': fields.one2many('protocollo.sender_receiver', 'protocollo_id', 'Mittente',
                                   domain=[('source', '=', 'sender')]),
        'receivers': fields.one2many('protocollo.sender_receiver', 'protocollo_id', 'Destinatari',
                                     domain=[('source', '=', 'receiver')]),
        'senders_summary': fields.function(_get_senders_summary, type="char", string="Mittente", store=False),
        'receivers_summary': fields.function(_get_receivers_summary, type="char", string="Destinatari", store=False),
        'assigne_emails': fields.function(_get_assigne_emails, type='char', string='Email Destinatari'),
        'assigne_cc': fields.boolean('Inserisci gli Assegnatari in CC'),
        'dossier_ids': fields.many2many('protocollo.dossier', 'dossier_protocollo_rel', 'protocollo_id', 'dossier_id',
                                        'Fascicoli'),

        'assegnazione_ids': fields.one2many('protocollo.assegnazione', 'protocollo_id', 'Assegnatari', readonly=True),
        'assegnazione_first_level_ids': fields.one2many('protocollo.assegnazione', 'protocollo_id', 'Assegnatari',
                                                        domain=[('parent_id', '=', False)], readonly=True),
        'assegnazione_competenza_ids': fields.one2many('protocollo.assegnazione', 'protocollo_id',
                                                       'Assegnatari per Competenza',
                                                       domain=[('parent_id', '=', False),
                                                               ('tipologia_assegnazione', '=', 'competenza')],
                                                       readonly=True),
        'assegnazione_conoscenza_ids': fields.one2many('protocollo.assegnazione', 'protocollo_id',
                                                       'Assegnatari per Conoscenza',
                                                       domain=[('parent_id', '=', False),
                                                               ('tipologia_assegnazione', '=', 'conoscenza')],
                                                       readonly=True),

        'notes': fields.text('Altro'),
        'state': fields.selection(lambda s, *a, **k: s.get_state_list(*a, **k), string='Stato', readonly=True, help="Lo stato del protocollo.", select=True),
        'year': fields.integer('Anno', required=True),
        'attachment_ids': fields.one2many('ir.attachment', 'res_id', 'Allegati', readonly=True,
                                          domain=[('res_model', '=', 'protocollo.protocollo')]),
        'xml_signature': fields.text('Segnatura xml'),
        'aoo_id': fields.many2one('protocollo.aoo', 'AOO', required=True),
        'registry': fields.related('aoo_id', 'registry_id', type='many2one', relation='protocollo.registry',
                                   string='Registro', store=True, readonly=True),
        'protocol_request': fields.boolean('Richiesta Protocollo', readonly=True),

        'server_sharedmail_id': fields.many2one('fetchmail.server', 'Account Email',
                                                domain="[('sharedmail', '=', True),('user_sharedmail_ids', 'in', uid),('state','=','done')]"),
        'server_pec_id': fields.many2one('fetchmail.server', 'Account PEC',
                                         domain="[('pec', '=', True),('user_ids', 'in', uid),('state','=','done')]"),
        'is_imported': fields.boolean('Protocollo Importato', readonly=True),
        'request_user_id': fields.many2one('res.users', 'Autore Richiesta di protocollo', readonly=True),
        'archivio_id': fields.many2one('protocollo.archivio', 'Archivio', required=True),
        'is_current_archive': fields.related('archivio_id', 'is_current', type='boolean', string='Archivio Corrente', readonly=True)
    }

    # def _get_default_name(self, cr, uid, context=None):
    #     if context is None:
    #         context = {}
    #     user = self.pool.get('res.users').browse(cr, SUPERUSER_ID, uid)
    #     dest_tz = pytz.timezone(user.partner_id.tz) or pytz.timezone("Europe/Rome")
    #     now = datetime.datetime.now(dest_tz).strftime(DSDF)
    #     return 'Nuovo Protocollo del ' + now

    def _get_default_year(self, cr, uid, context=None):
        if context is None:
            context = {}
        now = datetime.datetime.now()
        return now.year

    def _get_default_is_emergency_active(self, cr, uid, context=None):
        emergency_registry_obj = self.pool.get('protocollo.emergency.registry')
        aoo_id = self._get_default_aoo_id(cr, uid)
        if aoo_id:
            reg_ids = emergency_registry_obj.search(cr, uid, [
                ('aoo_id', '=', aoo_id),
                ('state', '=', 'draft')
            ])
            if len(reg_ids) > 0:
                return True
        return False

    def _get_default_aoo_id(self, cr, uid, context=None):
        aoo_ids = self.pool.get('protocollo.aoo').search(cr, uid, [], context=context)
        for aoo_id in aoo_ids:
            check = self.pool.get('protocollo.aoo').is_visible_to_protocol_action(cr, uid, aoo_id)
            if check:
                return aoo_id
        return False

    def _get_def_sharedmail_server(self, cr, uid, context=None):
        res = self.pool.get('fetchmail.server').search(cr, uid,
                                                       [('user_sharedmail_ids', 'in', uid), ('sharedmail', '=', True),('state','=','done')],
                                                       context=context)
        return res and res[0] or False

    def _get_def_pec_server(self, cr, uid, context=None):
        res = self.pool.get('fetchmail.server').search(cr, uid, [('user_ids', 'in', uid), ('pec', '=', True), ('state', '=','done')],
                                                       context=context)
        return res and res[0] or False

    def _default_registration_employee_department_id_readonly(self, cr, uid, context):
        department_ids = self.pool.get('hr.department').search(cr, uid, [('can_used_to_protocol', '=', True)])
        if len(department_ids) == 1:
            return True
        return False

    def _get_registration_employee_department_id(self, cr, uid, context):
        department_ids = self.pool.get('hr.department').search(cr, uid, [('can_used_to_protocol', '=', True)])
        if department_ids:
            return department_ids[0]
        return False

    def _get_default_archivio_id(self, cr, uid, context=None):
        aoo_ids = self.pool.get('protocollo.aoo').search(cr, uid, [], context=context)
        if len(aoo_ids) > 0:
            archivio_ids = self.pool.get('protocollo.archivio').search(cr, uid, [('aoo_id', '=', aoo_ids[0]), ('is_current', '=', True)], context=context)
            return archivio_ids[0]
        return False

    _defaults = {
        'registration_type': 'normal',
        'emergency_active': _get_default_is_emergency_active,
        'creation_date': fields.date.context_today,
        'state': 'draft',
        'year': _get_default_year,
        'user_id': lambda obj, cr, uid, context: uid,
        'datas': None,
        'datas_fname': None,
        'aoo_id': _get_default_aoo_id,
        'server_sharedmail_id': _get_def_sharedmail_server,
        'server_pec_id': _get_def_pec_server,
        'email_pec_sending_mode': 'all_receivers',
        'is_imported': False,
        'registration_employee_department_id_readonly': _default_registration_employee_department_id_readonly,
        'registration_employee_state': 'working',
        'archivio_id': _get_default_archivio_id,
    }

    _sql_constraints = [
        ('protocol_number_unique', 'unique(name,year,aoo_id)',
         'Elemento già presente nel DB!'),
        ('protocol_mail_pec_ref_unique', 'unique(mail_pec_ref)',
         'Messaggio protocollato in precedenza!')
    ]

    def _get_next_number_normal(self, cr, uid, prot):

        sequence_obj = self.pool.get('ir.sequence')

        _logger.debug("Acquiring lock")
        LockerSingleton.lock.acquire()

        new_cr = self.pool.cursor()
        new_cr.execute("BEGIN TRANSACTION ISOLATION LEVEL SERIALIZABLE READ WRITE;")

        last_id = self.search(new_cr, SUPERUSER_ID,
                              [('state', 'in', ('registered', 'notified', 'sent', 'waiting', 'error', 'canceled'))],
                              limit=1, order='registration_date desc', context={'skip_check': True})
        if last_id:
            now = datetime.datetime.now()
            last = self.browse(new_cr, SUPERUSER_ID, last_id[0], {'skip_check': True})
            if last.registration_date[0:4] < str(now.year):
                seq_id = sequence_obj.search(new_cr, uid, [('code', '=', prot.registry.sequence.code)])
                sequence_obj.write(new_cr, SUPERUSER_ID, seq_id, {'number_next': 1})

        next_num = False

        _logger.debug("Getting sequence")
        try:
            next_num = sequence_obj.get_serialized_sequence_code(new_cr, uid, prot.registry.sequence.code) or None
        except Exception as e:
            _logger.error(e.message)

        new_cr.execute("COMMIT TRANSACTION;")
        new_cr.close()

        LockerSingleton.lock.release()
        _logger.debug("Lock released")

        if not next_num:
            raise orm.except_orm(_('Errore'),
                                 _('Il sistema ha riscontrato un errore nel reperimento del numero protocollo'))
        return next_num

    def _get_next_number_emergency(self, cr, uid, prot):
        emergency_registry_obj = self.pool.get('protocollo.emergency.registry')
        reg_ids = emergency_registry_obj.search(cr,
                                                uid,
                                                [('state', '=', 'draft')]
                                                )
        if len(reg_ids) > 0:
            er = emergency_registry_obj.browse(cr, uid, reg_ids[0])
            num = 0
            for enum in er.emergency_ids:
                if not enum.protocol_id:
                    num = enum.name
                    self.pool.get('protocollo.emergency.registry.line'). \
                        write(cr, uid, [enum.id], {'protocol_id': prot.id})
                    break
            reg_available = [e.id for e in er.emergency_ids
                             if not e.protocol_id]
            if len(reg_available) < 1:
                emergency_registry_obj.write(cr,
                                             uid,
                                             [er.id],
                                             {'state': 'closed'}
                                             )
            return num
        else:
            raise orm.except_orm(_('Errore'),
                                 _('Il sistema ha riscontrato un errore \
                                 nel reperimento del numero protocollo'))

    def _get_next_number(self, cr, uid, prot):
        if prot.registration_type == 'emergency':
            return self._get_next_number_emergency(cr, uid, prot)
        # FIXME what if the emergency is the 31 december
        # and we protocol the 1 january
        return self._get_next_number_normal(cr, uid, prot)

    def _convert_pdfa(self, cr, uid, doc_path):
        cmd = ['unoconv', '-f', 'pdf', '-eSelectPdfVersion=1', '-o',
               doc_path + '.pdf', doc_path]
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
            stdoutdata, stderrdata = proc.communicate()
            if proc.wait() != 0:
                _logger.warning(stdoutdata)
                raise Exception(stderrdata)
            return True
        finally:
            shutil.move(doc_path + '.pdf', doc_path)

    def _create_attachment_encryped_file(self, cr, uid, prot, path):
        pdf_file = open(path, 'r')
        data_encoded = base64.encodestring(pdf_file.read())
        attach_vals = {
            'name': prot.datas_fname + '.signed',
            'datas': data_encoded,
            'datas_fname': prot.datas_fname + '.signed',
            'res_model': 'protocollo.protocollo',
            'is_protocol': True,
            'res_id': prot.id,
        }
        attachment_obj = self.pool.get('ir.attachment')
        attachment_obj.create(cr, uid, attach_vals)
        pdf_file.close()
        os.remove(path)
        return True

    def sha256OfFile(self, filepath):
        import hashlib
        with open(filepath, 'rb') as f:
            return hashlib.sha256(f.read()).hexdigest()

    def _create_protocol_document(self, cr, uid, prot, prot_number, prot_datas):
        parent_id = 0
        ruid = 0
        # if prot.reserved:
        #    parent_id, ruid = self._create_protocol_security_folder(cr, SUPERUSER_ID, prot, prot_number)
        attachment_obj = self.pool.get('ir.attachment')
        configurazione_ids = self.pool.get('protocollo.configurazione').search(cr, uid, [])
        configurazione = self.pool.get('protocollo.configurazione').browse(cr, uid, configurazione_ids[0])
        old_attachment_id = prot.doc_id.id
        attachment = attachment_obj.browse(cr, uid, old_attachment_id)
        file_name = attachment.datas_fname

        if file_name and configurazione.rinomina_documento_allegati:
            file_name = self._get_name_documento_allegato(cr, uid, file_name, prot_number, 'Prot', True)

        attach_vals = {
            'name': file_name,
            'datas': prot_datas,
            'datas_fname': file_name,
            'datas_description': attachment.datas_description,
            'res_model': 'protocollo.protocollo',
            'is_protocol': True,
            'reserved': prot.reserved,
            'res_id': prot.id,
        }
        if parent_id:
            attach_vals['parent_id'] = parent_id

        user_id = ruid or uid
        attachment_id = attachment_obj.create(cr, user_id, attach_vals)
        self.write(cr, uid, prot.id, {'doc_id': attachment_id, 'datas': 0}, {'skip_check': True})
        attachment_obj.unlink(cr, SUPERUSER_ID, old_attachment_id)
        new_attachment = attachment_obj.browse(cr, user_id, attachment_id)
        file_path = attachment_obj._full_path(cr, uid, new_attachment.store_fname)
        return self.sha256OfFile(file_path)

    def _create_protocol_attachment(self, cr, uid, prot, name, datas, description, attachment_index):
        attachment_values = {
            'name': name,
            'datas': datas,
            'datas_fname': name,
            'datas_description': description,
            'res_model': 'protocollo.protocollo',
            'is_protocol': True,
            'res_id': prot.id
        }
        attachment_obj = self.pool.get('ir.attachment')
        attachment_created_id = attachment_obj.create(cr, uid, attachment_values)
        return attachment_created_id

    def _update_protocol_attachments(self, cr, uid, prot):
        errors = ''
        attachment_domain = [
            ('res_model', '=', 'protocollo.protocollo'),
            ('res_id', '=', prot.id),
            ('is_protocol', '=', True),
        ]
        attachment_obj = self.pool.get('ir.attachment')
        if prot.doc_id:
            attachment_domain.append(('id', '!=', prot.doc_id.id))

        configurazione_ids = self.pool.get('protocollo.configurazione').search(cr, uid, [])
        configurazione = self.pool.get('protocollo.configurazione').browse(cr, uid, configurazione_ids[0])
        if configurazione.rinomina_documento_allegati:
            attachment_ids = attachment_obj.search(cr, uid, attachment_domain)
            if attachment_ids:
                for attachment_id in attachment_ids:
                    attachment = attachment_obj.browse(cr, uid, attachment_id)
                    try:
                        filename = self._get_name_documento_allegato(cr, uid, attachment.datas_fname, prot.name, 'Prot', False)
                        attachment_values = {'name': filename, 'datas_fname': filename}
                        attachment_obj.write(cr, uid, [attachment.id], attachment_values)
                    except Exception as e:
                        _logger.error(e)
                        error = "Errore nella ridenominazione dell'allegato: %s" % attachment.datas_fname
                        errors = errors + "\n" + error if errors else error
        return errors

    def _create_protocol_security_folder(self, cr, uid, prot, prot_number):
        group_reserved_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'seedoo_protocollo',
                                                                                'group_protocollazione_riservata')[1]
        directory_obj = self.pool.get('document.directory')
        directory_root_id = \
            self.pool.get('ir.model.data').get_object_reference(cr, uid, 'seedoo_protocollo', 'dir_protocol')[1]
        ruid = None
        if prot.aoo_id.reserved_employee_id and prot.aoo_id.reserved_employee_id.user_id:
            ruid = prot.aoo_id.reserved_employee_id.user_id.id
        if not ruid:
            raise orm.except_orm(_('Attenzione!'), _('Manca il responsabile dei dati sensibili!'))
        directory_id = directory_obj.create(
            cr, uid, {
                'name': 'Protocollo %s %s' % (str(prot_number), str(prot.year)),
                'parent_id': directory_root_id,
                'user_id': ruid,
                'group_ids': [[6, 0, [group_reserved_id]]]
            })
        return directory_id, ruid

    def action_create_attachment(self, cr, uid, ids, *args):
        try:
            for prot in self.browse(cr, uid, ids, {'skip_check': True}):
                if prot.datas and prot.datas_fname:
                    attach_vals = {
                        'name': prot.datas_fname,
                        'datas': prot.datas,
                        'datas_fname': prot.datas_fname,
                        'res_model': 'protocollo.protocollo',
                        'is_protocol': True,
                        'res_id': prot.id,
                    }
                    protocollo_obj = self.pool.get('protocollo.protocollo')
                    attachment_obj = self.pool.get('ir.attachment')
                    attachment_id = attachment_obj.create(cr, uid, attach_vals)
                    protocollo_obj.write(
                        cr, uid, prot.id,
                        {'doc_id': attachment_id, 'datas': 0})
        except Exception as e:
            raise Exception(e)

        return True

    def get_partner_values(self, cr, uid, send_rec):
        values = {
            'name': send_rec.name,
            'is_company': True if (send_rec.type=='legal' or send_rec.type=='government') else False,
            'tax_code': send_rec.tax_code,
            'vat': send_rec.vat,
            'street': send_rec.street,
            'city': send_rec.city,
            'country_id': send_rec.country_id and send_rec.country_id.id or False,
            'email': send_rec.email,
            'pec_mail': send_rec.pec_mail,
            'phone': send_rec.phone,
            'mobile': send_rec.mobile,
            'fax': send_rec.fax,
            'zip': send_rec.zip,
            'legal_type': send_rec.type,
            'pa_type': send_rec.pa_type,
            'ident_code': send_rec.ident_code,
            'ammi_code': send_rec.ammi_code,
            'ipa_code': send_rec.ipa_code,
            'street2': send_rec.street2,
            'state_id': (send_rec.state_id and send_rec.state_id.id or False),
            'function': send_rec.function,
            'website': send_rec.website,
            'title': (send_rec.title and send_rec.title.id or False),
        }
        return values

    def action_create_partners(self, cr, uid, ids, *args):
        send_rec_obj = self.pool.get('protocollo.sender_receiver')
        for prot in self.browse(cr, uid, ids, {'skip_check': True}):
            for send_rec in prot.sender_receivers:
                if send_rec.save_partner and not send_rec.partner_id:
                    # if send_rec.partner_id:
                    #    raise orm.except_orm('Attenzione!', 'Si sta tentando di salvare un\' anagrafica già presente nel sistema')
                    partner_obj = self.pool.get('res.partner')
                    values = self.get_partner_values(cr, uid, send_rec)
                    partner_id = partner_obj.create(cr, uid, values)
                    send_rec_obj.write(cr, uid, [send_rec.id], {'partner_id': partner_id})
        return True

    def action_register_process(self, cr, uid, ids, context=None, *args):
        res = []
        res_registrazione = None
        res_conferma = None
        check = self.check_journal(cr, uid, ids)
        if check:
            check = self.action_create_attachment(cr, uid, ids)
        if check:
            check = self.action_create_partners(cr, uid, ids)
        if check:
            res_registrazione = self.action_register(cr, uid, ids)
            check = True if res_registrazione is not None and len(res_registrazione) > 0 and 'Registrazione' in \
                            res_registrazione[0] and 'Res' in res_registrazione[0]['Registrazione'] and \
                            res_registrazione[0]['Registrazione']['Res'] else False

        if check:
            wf_service = netsvc.LocalService('workflow')
            wf_service.trg_validate(uid, 'protocollo.protocollo', ids[0], 'register', cr)
            res_conferma = self.action_send_conferma(cr, uid, ids)

            if not context or not ('notifica_assegnazione' in context) or context['notifica_assegnazione']:
                protocollo_assegnazione_obj = self.pool.get('protocollo.assegnazione')
                for protocollo_id in ids:
                    protocollo_assegnazione_ids = protocollo_assegnazione_obj.search(cr, uid, [
                        ('protocollo_id', '=', protocollo_id),
                        ('parent_id', '=', False)
                    ])
                    for protocollo_assegnazione_id in protocollo_assegnazione_ids:
                        protocollo_assegnazione = protocollo_assegnazione_obj.browse(cr, uid, protocollo_assegnazione_id, {'skip_check': True})
                        protocollo_assegnazione_obj.notifica_assegnazione(cr, uid, protocollo_assegnazione)

        if res_registrazione is not None:
            for item_res_registrazione in res_registrazione:
                res.append(item_res_registrazione)

        if check and res_conferma is not None:
            res.append(res_conferma)

        return res

    def action_register(self, cr, uid, ids, context=None, *args):
        user = self.pool.get('res.users').browse(cr, SUPERUSER_ID, uid)
        ##TODO: prendere il timezone dal browser del client in sostituzione del timezone del res user per renderlo coerente con le viste di Odoo
        dest_tz = pytz.timezone(user.partner_id.tz) or pytz.timezone("Europe/Rome")
        # self.lock.acquire()
        res = []
        res_registrazione = []
        res_segnatura = []
        err_segnatura = False

        for prot in self.browse(cr, uid, ids, {'skip_check': True}):

            self.pool.get('protocollo.configurazione').verifica_campi_obbligatori(cr, uid, prot)

            if not prot.registration_date:
                try:
                    vals = {}
                    prot_number = self._get_next_number(cr, uid, prot)
                    prot_date = fields.datetime.now()
                    vals['name'] = prot_number
                    vals['registration_date'] = prot_date

                    # controlla che non ci siano email/pec in stato bozza collegate al protocollo
                    mail_pec_ref = prot.mail_pec_ref
                    if mail_pec_ref and mail_pec_ref.message_direction=='in':
                        # se ne trova modifica lo stato in protocollato
                        message_obj = self.pool.get('mail.message')
                        if mail_pec_ref.pec_state=='new':
                            message_obj.write(cr, SUPERUSER_ID, [mail_pec_ref.id], {'pec_state': 'protocol'})
                        elif mail_pec_ref.sharedmail_state=='new':
                            message_obj.write(cr, SUPERUSER_ID, [mail_pec_ref.id], {'sharedmail_state': 'protocol'})

                    # controlla che non ci siano documenti in stato bozza collegate al protocollo
                    doc_imported = prot.doc_imported_ref
                    if doc_imported and doc_imported.doc_protocol_state=='new':
                        # se ne trova modifica lo stato in protocollato
                        document_obj = self.pool.get('gedoc.document')
                        document_obj.write(cr, uid, [doc_imported.id], {'doc_protocol_state': 'protocol'})

                    if prot.doc_id:
                        prot_datas = prot.doc_id.datas
                        try:
                            if prot.mimetype == 'application/pdf':
                                prot_datas_signed = self.pool.get('protocollo.signature').sign_doc(cr, uid, prot, prot_number, prot_date, prot.doc_id)
                                if prot_datas_signed:
                                    prot_datas = prot_datas_signed
                                    res_segnatura = {"Segnatura": {"Res": True, "Msg": "Segnatura PDF generata correttamente"}}
                                else:
                                    res_segnatura = []
                        except Exception as e:
                            _logger.error(e)
                            err_segnatura = True
                            res_segnatura = {"Segnatura": {"Res": False, "Msg": "Errore nella segnatura PDF del documento"}}

                        fingerprint = self._create_protocol_document(cr, uid, prot, prot_number, prot_datas)
                        vals['fingerprint'] = fingerprint
                        vals['datas'] = 0

                    now = datetime.datetime.now()
                    vals['year'] = now.year
                    registration_time = datetime.datetime.now(dest_tz).strftime(DSDF)
                    self.write(cr, uid, [prot.id], vals, {'skip_check': True})
                    errors_update_attachments = self._update_protocol_attachments(cr, uid, prot)
                    if errors_update_attachments:
                        if not res_segnatura or res_segnatura["Segnatura"]["Res"]:
                            res_segnatura = {"Segnatura": {"Res": False, "Msg": errors_update_attachments}}
                        elif res_segnatura and not res_segnatura["Segnatura"]["Res"]:
                            res_segnatura["Segnatura"]["Msg"] += "\n" + errors_update_attachments

                    self.aggiorna_segnatura_xml(cr, uid, [prot.id], force=True, log=False, commit=False, context=context)

                    action_class = "history_icon registration"
                    body = "<div class='%s'><ul><li>Creato protocollo %s</li>" % (action_class, prot_number)
                    ass_com = ', '.join([a.assegnatario_id.nome for a in prot.assegnazione_competenza_ids])
                    ass_con = ', '.join([a.assegnatario_id.nome for a in prot.assegnazione_conoscenza_ids])
                    if ass_com or ass_con:
                        if ass_com:
                            body = body + "<li>%s: <span> %s </span></li>" % (self.get_label_competenza(cr, uid), ass_com)
                        if ass_con:
                            body = body + "<li>%s: <span> %s </span></li>" % ('Assegnatari Conoscenza', ass_con)
                    history_body_append = self.get_registration_history_body_append(cr, uid, prot)
                    if history_body_append:
                        body += history_body_append
                    body += "</ul></div>"
                    post_vars = {
                        'subject': "Registrazione protocollo",
                        'body': body,
                        'model': "protocollo.protocollo",
                        'res_id': prot.id,
                    }
                    self.message_post(cr, uid, prot.id, type="notification", context=context, **post_vars)

                    if err_segnatura:
                        action_class = "history_icon warning"
                        post_vars_segnatura = {
                            'subject': "Errore Generazione Segnatura",
                            'body': "<div class='%s'><ul><li>Impossibile generare la segnatura PDF</li></ul></div>" % action_class,
                            'model': "protocollo.protocollo",
                            'res_id': prot.id,
                        }
                        self.message_post(cr, uid, prot.id, type="notification", context=context, **post_vars_segnatura)

                    res_registrazione = {
                        "Registrazione": {
                            "Res": True,
                            "Msg": "Protocollo Nr. %s del %s registrato correttamente" % (prot_number, registration_time)
                        }
                    }
                except Exception as e:
                    _logger.error(e)
                    # res_registrazione = {"Registrazione":{"Res": False, "Msg": "Errore nella registrazione del protocollo"}}
                    raise openerp.exceptions.Warning(_('Errore nella registrazione del protocollo'))
                res.append(res_registrazione)
                if len(res_segnatura) > 0:
                    res.append(res_segnatura)
            else:
                raise openerp.exceptions.Warning(_('"Non è più possibile eseguire l\'operazione richiesta! Il protocollo è già stato registrato!'))
        # self.lock.release()

        try:
            self._count_protocol(cr, uid, prot.id)
        except:
            pass

        return res

    def get_registration_history_body_append(self, cr, uid, protocollo):
        return False

    def _count_protocol(self, cr, uid, protid):
        protocollo_obj = self.pool.get("protocollo.protocollo")
        instance_obj = self.pool.get("seedoo_gedoc.instance")

        protocollo_id = protocollo_obj.browse(cr, uid, [protid])
        if not protocollo_id:
            return

        prot_num = int(protocollo_id.name)
        if prot_num in [1, 10, 100] or prot_num % 1000 == 0:
            instance_uuid = instance_obj.get_seedoo_instance_uuid(cr, uid)
            thread = threading.Thread(target=self._call_count_protocol, args=[instance_uuid, prot_num])
            thread.start()

    def _call_count_protocol(self, instance_uuid, prot_num):
        try:
            headers = {
                "Content-Type": "application/json"
            }

            data = {
                "params": {
                    "instance_uuid": instance_uuid,
                    "prot_num": prot_num
                }
            }

            url = "https://www.seedoo.it/count/protocol"

            requests.post(
                url=url,
                headers=headers,
                data=json.dumps(data)
            )
        except:
            pass

    def action_send_conferma(self, cr, uid, ids, context=None, *args):
        res_conferma = {"Invio Conferma": {"Res": False, "Msg": None}}
        configurazione_ids = self.pool.get('protocollo.configurazione').search(cr, uid, [])
        configurazione = self.pool.get('protocollo.configurazione').browse(cr, uid, configurazione_ids[0])

        try:
            for prot in self.browse(cr, uid, ids, {'skip_check': True}):
                if prot.type == 'in' and prot.pec and len(
                        prot.mail_pec_ref.ids) > 0 and configurazione.conferma_xml_invia:
                    res = self.action_send_receipt(cr, uid, ids, 'conferma', context=context)
                    if res == 'sent':
                        res_conferma = {"Invio Conferma": {"Res": True, "Msg": "Conferma di Protocollazione inviata"}}
                    elif res == 'exception':
                        res_conferma = {"Invio Conferma": {"Res": False,
                                                           "Msg": "Non è stato possibile inviare la Conferma di Protocollazione al Mittente"}}
        except Exception as e:
            _logger.error(e)
            res_conferma = {"Invio Conferma": {"Res": False,
                                               "Msg": "Non è stato possibile inviare la Conferma di Protocollazione al Mittente"}}

        return res_conferma

    # def action_notify(self, cr, uid, ids, *args):
    #     email_template_obj = self.pool.get('email.template')
    #     for prot in self.browse(cr, uid, ids):
    #         if prot.type == 'in' and not prot.assegnazione_competenza_ids:
    #             raise openerp.exceptions.Warning(_('Errore nella notifica del protocollo, mancano gli assegnatari'))
    #         if prot.reserved:
    #             template_reserved_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'seedoo_protocollo',
    #                                                                                        'notify_reserved_protocol')[
    #                 1]
    #             email_template_obj.send_mail(cr, uid, template_reserved_id, prot.id, force_send=True)
    #         if prot.assigne_emails:
    #             template_id = \
    #                 self.pool.get('ir.model.data').get_object_reference(cr, uid, 'seedoo_protocollo',
    #                                                                     'notify_protocol')[1]
    #             email_template_obj.send_mail(cr, uid, template_id, prot.id, force_send=True)
    #     return True

    def action_notify_cancel(self, cr, uid, ids, *args):
        return True

    def action_send_receipt(self, cr, uid, ids, receipt_type, context=None, *args):
        if context is None:
            context = {}
        context['lang'] = 'it_IT'
        res = None
        for prot in self.browse(cr, uid, ids, {'skip_check': True}):
            receipt_xml = None
            messaggio_pec_obj = self.pool.get('protocollo.messaggio.pec')
            if receipt_type == 'conferma':
                receipt_xml = ConfermaXML(prot, cr, uid)
            if receipt_type == 'annullamento':
                receipt_xml = AnnullamentoXML(cr, uid, prot, context['receipt_cancel_reason'],
                                              context['receipt_cancel_author'], context['receipt_cancel_date'])

            xml = receipt_xml.generate_receipt_root()
            etree_tostring = etree.tostring(xml, pretty_print=True)

            if etree_tostring:
                mail_mail = self.pool.get('mail.mail')
                new_context = dict(context).copy()
                new_context.update({'pec_messages': True})
                # mail_server = self.get_mail_server(cr, uid, new_context)

                mail_server = None
                if prot.mail_pec_ref and prot.mail_pec_ref.server_id:
                    mail_server_obj = self.pool.get('ir.mail_server')
                    mail_server_ids = mail_server_obj.get_mail_server_pec(cr, uid, prot.mail_pec_ref.server_id.id,
                                                                          context)
                    if not mail_server_ids:
                        raise openerp.exceptions.Warning(
                            _('Errore nella notifica del protocollo, manca il server di posta in uscita'))
                    mail_server = mail_server_obj.browse(cr, uid, mail_server_ids[0])
                else:
                    raise openerp.exceptions.Warning(
                        _('Errore nella notifica del protocollo, nessun server pec trovato'))

                sender_receivers_pec_mails = []
                sender_receivers_pec_ids = []

                if prot.sender_receivers:
                    for sender_receiver_id in prot.sender_receivers.ids:
                        sender_receiver_obj = self.pool.get('protocollo.sender_receiver').browse(cr, uid,
                                                                                                 sender_receiver_id,
                                                                                                 context=context)
                        sender_receivers_pec_mails.append(sender_receiver_obj.pec_mail)
                        sender_receivers_pec_ids.append(sender_receiver_obj.id)

                if receipt_type == 'conferma':
                    attachment_data = ('conferma.xml', etree_tostring.encode('base64'))
                    # attachment = self.pool.get('ir.attachment').create(cr, uid, {'name': 'conferma.xml', 'datas_fname': 'conferma.xml', 'datas': etree_tostring.encode('base64')})
                elif receipt_type == 'annullamento':
                    attachment_data = ('annullamento.xml', etree_tostring.encode('base64'))
                    # attachment = self.pool.get('ir.attachment').create(cr, uid, {'name': 'annullamento.xml', 'datas_fname': 'annullamento.xml', 'datas': etree_tostring.encode('base64')})

                # vals = {'pec_conferma_ref': mail.mail_message_id.id}
                # self.write(cr, uid, [prot.id], vals)
                new_context = dict(context).copy()
                new_context.update({'receipt_email_from': mail_server.name})
                new_context.update({'receipt_email_to': ','.join([sr for sr in sender_receivers_pec_mails])})
                new_context.update({'pec_messages': True})

                email_template_obj = self.pool.get('email.template')

                if receipt_type == 'conferma':
                    template_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'seedoo_protocollo',
                                                                                      'confirm_protocol')[1]
                if receipt_type == 'annullamento':
                    template_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'seedoo_protocollo',
                                                                                      'cancel_protocol')[1]

                template = email_template_obj.browse(cr, uid, template_id, new_context)
                # template.attachment_ids = [(6, 0, [attachment])]
                # template.write({
                #     'mail_server_id': mail_server.id
                # })
                # mail_receipt_id = template.send_mail(prot.id, force_send=True)
                new_context.update({'protocollo_attachments': [attachment_data]})
                new_context.update({'protocollo_mail_server_id': mail_server.id})
                mail_receipt_id = template.with_context(new_context).send_mail(prot.id, force_send=True)
                #mail_receipt_id = email_template_obj.send_mail(cr, uid, template_id, prot.id, force_send=True, context=new_context)

                for sender_receiver_id in sender_receivers_pec_ids:
                    vals = {}
                    sender_receiver_obj = self.pool.get('protocollo.sender_receiver').browse(cr, uid,
                                                                                             sender_receiver_id,
                                                                                             context=context)
                    message_obj = self.pool.get('mail.message')
                    mail_receipt = self.pool.get('mail.mail').browse(cr, uid, mail_receipt_id[0], context=context)
                    message_receipt = mail_mail.browse(cr, uid, mail_receipt.mail_message_id.id, context=context)
                    valsreceipt = {}
                    valsreceipt['pec_protocol_ref'] = prot.id
                    valsreceipt['pec_state'] = 'protocol'
                    valsreceipt['pec_type'] = 'posta-certificata'
                    valsreceipt['direction'] = 'out'
                    valsreceipt['pec_to'] = sender_receiver_obj.pec_mail
                    valsreceipt['server_id'] = prot.mail_pec_ref.server_id.id
                    message_obj.write(cr, uid, mail_receipt.mail_message_id.id, valsreceipt)
                    messaggio_pec_id = messaggio_pec_obj.create(cr, uid, {'type': receipt_type,
                                                                          'messaggio_ref': message_receipt.id})
                    vals['pec_messaggio_ids'] = [(4, [messaggio_pec_id])]
                    sender_receiver_obj.write(vals)

                res_mail_receipt = self.pool.get('mail.mail').browse(cr, uid, mail_receipt_id, context=context)
                thread_pool = self.pool.get('protocollo.protocollo')
                if res_mail_receipt.state == "sent":
                    action_class = "history_icon mail"
                    post_vars = {
                        'subject': "Ricevuta di %s inviata" % receipt_type,
                        'body': "<div class='%s'><ul><li>Conferma.xml inviata al mittente</li></ul></div>" % (
                            action_class),
                        'model': "protocollo.protocollo",
                        'res_id': prot.id,
                    }
                elif res_mail_receipt.state == "exception":
                    action_class = "history_icon warning"
                    post_vars = {
                        'subject': "Ricevuta di %s non inviata" % receipt_type,
                        'body': "<div class='%s'><ul><li>Non è stato possibile inviare la Conferma di Protocollazione al Mittente</li></ul></div>" % (
                            action_class),
                        'model': "protocollo.protocollo",
                        'res_id': prot.id,
                    }

                if res_mail_receipt.state in ['sent', 'exception']:
                    thread_pool.message_post(cr, uid, prot.id, type="notification", context=context, **post_vars)
                    res = res_mail_receipt.state
        return res

    def _get_assigne_cc_emails(self, cr, uid, ids, context=None):
        if isinstance(ids, (list, tuple)) and not len(ids):
            return []
        if isinstance(ids, (long, int)):
            ids = [ids]
        emails = ''
        users = []
        for prot in self.browse(cr, uid, ids):
            assegnatari_competenza = self._get_assegnatari_competenza(cr, uid, prot)
            assegnatari_conoscenza = self._get_assegnatari_conoscenza(cr, uid, prot)
            assegnatari = list(set(assegnatari_competenza + assegnatari_conoscenza))
            assegnatari_emails = []
            for assegnatario in assegnatari:
                if assegnatario.user_id and assegnatario.user_id.email:
                    assegnatari_emails.append(assegnatario.user_id.email)
            emails = ','.join(assegnatari_emails)
        return emails

    def _create_outgoing_pec(self, cr, uid, prot_id, context=None):
        if context is None:
            context = {}
        prot = self.browse(cr, uid, prot_id)
        if prot.type == 'out' and prot.pec:

            configurazione_ids = self.pool.get('protocollo.configurazione').search(cr, uid, [])
            configurazione = self.pool.get('protocollo.configurazione').browse(cr, uid, configurazione_ids[0])
            mail_mail = self.pool.get('mail.mail')
            ir_attachment = self.pool.get('ir.attachment')
            mail_message_obj = self.pool.get('mail.message')
            messaggio_pec_obj = self.pool.get('protocollo.messaggio.pec')
            thread_pool = self.pool.get('protocollo.protocollo')
            fetchmail_server_id = prot.server_pec_id.id
            mail_server_obj = self.pool.get('ir.mail_server')
            mail_server_ids = mail_server_obj.search(cr, uid, [('in_server_id', '=', fetchmail_server_id)])
            mail_server = mail_server_obj.browse(cr, uid, mail_server_ids)
            subject = self._get_oggetto_mail_pec(cr, uid, prot.subject, prot.name, prot.registration_date) if configurazione.rinomina_oggetto_mail_pec else prot.subject
            subject = subject.replace('\r', '').replace('\n', '')
            if configurazione.lunghezza_massima_oggetto_pec > 0:
                subject = subject[:configurazione.lunghezza_massima_oggetto_pec]

            body_html = self.get_body_signature(cr, uid, prot.body, False, context)
            values = {}
            values['subject'] = subject
            values['body_html'] = body_html
            values['body'] = body_html
            #TODO: email_from non necessariamente deve essere la username dell'autenticazione del server SMTP
            values['email_from'] = mail_server.name
            values['reply_to'] = mail_server.in_server_id.user
            values['mail_server_id'] = mail_server.id
            values['pec_protocol_ref'] = prot.id
            values['pec_state'] = 'protocol'
            values['pec_type'] = 'posta-certificata'
            values['server_id'] = fetchmail_server_id

            if prot.assigne_cc:
                values['email_cc'] = self._get_assigne_cc_emails(cr, uid, prot_id, context)

            sender_receivers_pec_mails = []
            for sender_receiver in prot.sender_receivers:
                if ((sender_receiver.pec_errore_consegna_status or sender_receiver.pec_non_accettazione_status) and sender_receiver.to_resend) \
                        or not sender_receiver.pec_invio_status:
                    sender_receivers_pec_mails.append(sender_receiver.pec_mail)

            msg_id = False
            sent_all = True
            mail_to_send_dict = {}
            for sender_receiver in prot.sender_receivers:
                if ((sender_receiver.pec_errore_consegna_status or sender_receiver.pec_non_accettazione_status) and sender_receiver.to_resend) \
                        or not sender_receiver.pec_invio_status:

                    if prot.email_pec_sending_mode == 'all_receivers':
                        values['email_to'] = ','.join(sender_receivers_pec_mails)
                    else:
                        values['email_to'] = sender_receiver.pec_mail
                    values['pec_to'] = values['email_to']

                    if prot.mail_out_ref and prot.state == 'registered':
                        # se il protocollo è ancora in stato registrato non deve duplicare la email perchè ancora non è riuscito ad inviarla
                        pec_message_id = sender_receiver.pec_messaggio_ids.ids[len(sender_receiver.pec_messaggio_ids.ids) - 1]
                        pec_message = messaggio_pec_obj.browse(cr, uid, pec_message_id)
                        msg_ids = messaggio_pec_obj.search(cr, uid, [('mail_message_id', '=', pec_message.messaggio_ref.id)])
                        if msg_ids:
                            msg_id = msg_ids[0]
                        mail_mail.write(cr, uid, [msg_id], values, context=context)
                    else:
                        if prot.email_pec_sending_mode != 'all_receivers' or not msg_id:
                            msg_id = mail_mail.create(cr, uid, values, context=context)

                    mail = mail_mail.browse(cr, uid, msg_id, context=context)

                    if not (msg_id in mail_to_send_dict):
                        mail_to_send_dict[msg_id] = {
                            'mail': mail,
                            'to': values['email_to'],
                            'receiver_list': [sender_receiver]
                        }
                    else:
                        mail_to_send_dict[msg_id]['receiver_list'].append(sender_receiver)

            for msg_id in mail_to_send_dict.keys():
                sent_receiver = False

                mail_to_send = mail_to_send_dict[msg_id]
                mail = mail_to_send['mail']
                email_to = mail_to_send['to']
                sender_receiver_list = mail_to_send['receiver_list']

                # manage attachments
                attachment_ids = ir_attachment.search(cr, uid, [('res_model', '=', 'protocollo.protocollo'), ('res_id', '=', prot.id)])
                if attachment_ids:
                    values['attachment_ids'] = [(6, 0, attachment_ids)]
                    mail_mail.write(cr, uid, msg_id, {'attachment_ids': [(6, 0, attachment_ids)]})
                #vals = {'mail_out_ref': mail.id, 'mail_pec_ref': mail.mail_message_id.id}
                #self.write(cr, uid, [prot.id], vals)
                mail_mail.send(cr, uid, [msg_id], context=context)
                mail_message_obj.write(cr, uid, mail.mail_message_id.id, {'direction': 'out'})

                msgvals = {}
                email_list = ', '.join(email_to.split(','))
                res = mail_mail.read(cr, uid, [msg_id], ['state'], context=context)
                if res[0]['state'] != 'sent':
                    msgvals['to_resend'] = True

                    action_class = "history_icon warning"
                    post_vars = {
                        'subject': "Protocollo non inviato",
                        'body': "<div class='%s'><ul><li>Non è stato possibile inviare la PEC a: %s</li></ul></div>" % (action_class, str(email_list)),
                        'model': "protocollo.protocollo",
                        'res_id': prot_id
                    }
                    thread_pool.message_post(cr, uid, prot_id, type="notification", context=context, **post_vars)
                else:
                    msgvals['to_resend'] = False
                    sent_receiver = True

                    action_class = "history_icon mail"
                    post_vars = {
                        'subject': "Protocollo inviato",
                        'body': "<div class='%s'><ul><li>Protocollo inviato tramite PEC a: %s</li></ul></div>" % (action_class, email_list),
                        'model': "protocollo.protocollo",
                        'res_id': prot_id
                    }
                    thread_pool.message_post(cr, uid, prot_id, type="notification", context=context, **post_vars)

                for sender_receiver in sender_receiver_list:
                    messaggio_pec_id = messaggio_pec_obj.create(cr, uid, {'type': 'messaggio', 'messaggio_ref': mail.mail_message_id.id})
                    msgvals['pec_messaggio_ids'] = [(4, [messaggio_pec_id])]
                    sender_receiver.write(msgvals)

                sent_all = sent_all and sent_receiver
                cr.commit()

            if not sent_all:
                self._revert_workflow_data(cr, uid, prot)
                cr.commit()
                raise openerp.exceptions.Warning(_('Errore nella notifica del protocollo, la PEC non è stata inviata'))

        else:
            raise openerp.exceptions.Warning(_('Errore nel protocollo, si sta cercando di inviare una pec su un tipo di protocollo non pec.'))
        return True

    def _process_new_pec(self, cr, uid, ids, protocollo_obj, context=None):
        # check if waiting then resend pec mail
        if isinstance(ids, (list, tuple)) and not len(ids):
            return []
        if isinstance(ids, (long, int)):
            ids = [ids]

        for prot in self.browse(cr, uid, ids):
            if prot.state in ('waiting', 'sent', 'error'):
                wf_service = netsvc.LocalService('workflow')
                wf_service.trg_validate(uid, 'protocollo.protocollo', prot.id, 'resend', cr)
        return True

    def _create_outgoing_sharedmail(self, cr, uid, prot_id, context=None):
        if context is None:
            context = {}
        thread_pool = self.pool.get('protocollo.protocollo')
        prot = self.browse(cr, uid, prot_id)
        if prot.type == 'out' and prot.typology.sharedmail:
            configurazione_ids = self.pool.get('protocollo.configurazione').search(cr, uid, [])
            configurazione = self.pool.get('protocollo.configurazione').browse(cr, uid, configurazione_ids[0])
            mail_mail = self.pool.get('mail.mail')
            ir_attachment = self.pool.get('ir.attachment')
            fetchmail_server_id = prot.server_sharedmail_id.id
            mail_server_obj = self.pool.get('ir.mail_server')
            mail_server_ids = mail_server_obj.search(cr, uid, [('in_server_sharedmail_id', '=', fetchmail_server_id)])
            mail_server = mail_server_obj.browse(cr, uid, mail_server_ids)

            subject = self._get_oggetto_mail_pec(cr, uid, prot.subject, prot.name, prot.registration_date) if configurazione.rinomina_oggetto_mail_pec else prot.subject
            if configurazione.lunghezza_massima_oggetto_mail > 0:
                subject = subject[:configurazione.lunghezza_massima_oggetto_mail]

            body_html = self.get_body_signature(cr, uid, prot.body, False, context)
            values = {}
            values['subject'] = subject
            values['body_html'] = body_html
            values['body'] = body_html
            values['email_from'] = mail_server.name
            values['reply_to'] = mail_server.in_server_id.user
            values['mail_server_id'] = mail_server.id
            values['sharedmail_protocol_ref'] = prot.id
            values['sharedmail_state'] = 'protocol'
            values['sharedmail_type'] = 'sharedmail'
            values['server_sharedmail_id'] = fetchmail_server_id

            if prot.assigne_cc:
                values['email_cc'] = self._get_assigne_cc_emails(cr, uid, prot_id, context)

            sender_receivers_email_list = []
            for sender_receiver in prot.sender_receivers:
                if (sender_receiver.sharedmail_numero_invii==0) or (sender_receiver.sharedmail_numero_invii>0 and sender_receiver.to_resend):
                    sender_receivers_email_list.append(sender_receiver.email)

            msg_id = False
            sent_all = True
            mail_to_send_dict = {}
            for sender_receiver in prot.sender_receivers:
                if (sender_receiver.sharedmail_numero_invii==0) or (sender_receiver.sharedmail_numero_invii>0 and sender_receiver.to_resend):
                    if prot.email_pec_sending_mode == 'all_receivers':
                        values['email_to'] = ','.join(sender_receivers_email_list)
                    else:
                        values['email_to'] = sender_receiver.email
                    values['sharedmail_to'] = values['email_to']

                    # se il protocollo è ancora in stato registrato non deve duplicare la email perchè ancora non è riuscito ad inviarla
                    if sender_receiver.sharedmail_messaggio_ids and prot.state=='registered':
                        mail_message_id = sender_receiver.sharedmail_messaggio_ids.ids[len(sender_receiver.sharedmail_messaggio_ids.ids) - 1]
                        msg_ids = mail_mail.search(cr, uid, [('mail_message_id', '=', mail_message_id)])
                        if msg_ids:
                            msg_id = msg_ids[0]
                            mail_mail.write(cr, uid, [msg_id], values, context=context)
                    else:
                        if prot.email_pec_sending_mode != 'all_receivers' or not msg_id:
                            msg_id = mail_mail.create(cr, uid, values, context=context)

                    mail = mail_mail.browse(cr, uid, msg_id, context=context)
                    
                    if not (msg_id in mail_to_send_dict):
                        mail_to_send_dict[msg_id] = {
                            'mail': mail,
                            'to': values['email_to'],
                            'receiver_list': [sender_receiver]
                        }
                    else:
                        mail_to_send_dict[msg_id]['receiver_list'].append(sender_receiver)
                    

            for msg_id in mail_to_send_dict.keys():
                sent_receiver = False

                mail_to_send = mail_to_send_dict[msg_id]
                mail = mail_to_send['mail']
                email_to = mail_to_send['to']
                sender_receiver_list = mail_to_send['receiver_list']

                # manage attachments
                attachment_ids = ir_attachment.search(cr, uid, [('res_model', '=', 'protocollo.protocollo'), ('res_id', '=', prot.id)])
                if attachment_ids:
                    values['attachment_ids'] = [(6, 0, attachment_ids)]
                    mail_mail.write(cr, uid, msg_id, {'attachment_ids': [(6, 0, attachment_ids)]})
                #vals = {'mail_out_ref': mail.id, 'mail_sharedmail_ref': mail.mail_message_id.id}
                #self.write(cr, uid, [prot.id], vals)
                mail_mail.send(cr, uid, [msg_id], context=context)

                mail_message_obj = self.pool.get('mail.message')
                mail_message_obj.write(cr, uid, mail.mail_message_id.id, {'direction_sharedmail': 'out'})

                msgvals = {}
                email_list = ', '.join(email_to.split(','))
                res = mail_mail.read(cr, uid, [msg_id], ['state'], context=context)
                if res[0]['state'] != 'sent':
                    msgvals['to_resend'] = True
                    action_class = "history_icon warning"
                    post_vars = {
                        'subject': "Protocollo non inviato",
                        'body': "<div class='%s'><ul><li>Non è stato possibile inviare l'e-mail a: %s</li></ul></div>" % (action_class, str(email_list)),
                        'model': "protocollo.protocollo",
                        'res_id': prot_id
                    }
                    thread_pool.message_post(cr, uid, prot_id, type="notification", context=context, **post_vars)
                else:
                    msgvals['to_resend'] = False
                    sent_receiver = True
                    action_class = "history_icon mail"
                    post_vars = {
                        'subject': "Protocollo inviato",
                        'body': "<div class='%s'><ul><li>Protocollo inviato tramite e-mail a: %s</li></ul></div>" % (action_class, email_list),
                        'model': "protocollo.protocollo",
                        'res_id': prot_id
                    }
                    thread_pool.message_post(cr, uid, prot_id, type="notification", context=context, **post_vars)

                for sender_receiver in sender_receiver_list:
                    msgvals['sharedmail_numero_invii'] = int(sender_receiver.sharedmail_numero_invii) + 1
                    msgvals['sharedmail_messaggio_ids'] = [(4, mail.mail_message_id.id)]
                    sender_receiver.write(msgvals)

                sent_all = sent_all and sent_receiver
                cr.commit()

            if not sent_all:
                self._revert_workflow_data(cr, uid, prot)
                cr.commit()
                raise openerp.exceptions.Warning(_('Errore nella notifica del protocollo, l\'e-mail protocollo non è stata inviata'))

        else:
            raise openerp.exceptions.Warning(_('Errore nel protocollo, si sta cercando di inviare una pec su un tipo di protocollo non pec.'))

        return True

    def _revert_workflow_data(self, cr, uid, prot):
        data_obj = self.pool.get('ir.model.data')
        act_registered = data_obj.get_object_reference(cr, uid, 'seedoo_protocollo', 'act_registered')
        act_waiting = data_obj.get_object_reference(cr, uid, 'seedoo_protocollo', 'act_waiting')
        workflow_workitem_obj = self.pool.get('workflow.workitem')
        workflow_workitem_ids = workflow_workitem_obj.search(cr, uid, [
            ('inst_id.res_type', '=', 'protocollo.protocollo'),
            ('inst_id.res_id', '=', prot.id),
            ('state', '=', 'running'),
            ('act_id', '=', act_waiting[1])
        ])
        if workflow_workitem_ids:
            workflow_workitem_obj.write(cr, uid, workflow_workitem_ids, {
                'act_id': act_registered[1],
                'state': 'complete'
            })

    def get_mail_server(self, cr, uid, context=None):
        mail_server_obj = self.pool.get('ir.mail_server')
        fetch_server_obj = self.pool.get('fetchmail.server')
        if 'sharedmail_messages' in context:
            fetch_server_ids = fetch_server_obj.get_fetch_server_sharedmail(cr, uid, context)
        if 'pec_messages' in context:
            fetch_server_ids = fetch_server_obj.get_fetch_server_pec(cr, uid, context)
        if not fetch_server_ids:
            raise openerp.exceptions.Warning(_('Errore nella \
                notifica del protocollo, nessun server pec associato all\'utente'))
        if 'sharedmail_messages' in context:
            mail_server_ids = mail_server_obj.get_mail_server_sharedmail(cr, uid, fetch_server_ids[0], context)
        if 'pec_messages' in context:
            mail_server_ids = mail_server_obj.get_mail_server_pec(cr, uid, fetch_server_ids[0], context)
        if not mail_server_ids:
            raise openerp.exceptions.Warning(_('Errore nella \
                notifica del protocollo, manca il server di posta in uscita'))
        mail_server = mail_server_obj.browse(cr, uid, mail_server_ids[0])
        return mail_server

    def action_send(self, cr, uid, ids, context=None, *args):
        protocollo_obj = self.pool.get('protocollo.protocollo')
        protocollo = protocollo_obj.browse(cr, uid, ids)
        if not protocollo.typology.sharedmail and not protocollo.typology.pec:
            action_class = "history_icon sent"
            post_vars = {'subject': "Invio protocollo",
                         'body': "<div class='%s'><ul><li>Inviato protocollo %s (%s)</li></ul></div>" % (
                             action_class, protocollo.name, protocollo.typology.name),
                         'model': "protocollo.protocollo",
                         'res_id': protocollo.id,
                         }
            protocollo_obj.message_post(cr, uid, protocollo.id, type="notification", context=context, **post_vars)

        return True

    def action_mail_pec_send(self, cr, uid, ids, *args):

        for prot_id in ids:
            prot = self.pool.get('protocollo.protocollo').browse(cr, uid, prot_id)
            # if prot.state == 'sent': SOLUZIONE NON APPLICABILE. CREA PROBLEMI NEL REINVIO
            #     raise openerp.exceptions.Warning(_('Il messaggio è già stato inviato in precedenza: ricaricare la pagina'))
            if prot.pec:
                context = {'pec_messages': True}
                self._create_outgoing_pec(cr, uid, prot_id, context=context)
            else:
                context = {'sharedmail_messages': True}
                self._create_outgoing_sharedmail(cr, uid, prot_id, context=context)
        return True

    def action_resend(self, cr, uid, ids, context=None):
        protocollo_obj = self.pool.get('protocollo.protocollo')
        protocollo_obj._process_new_pec(cr, uid, ids, protocollo_obj, context)

    def mail_message_id_get(self, cr, uid, ids, *args):
        res = {}
        if not ids:
            return []
        for protocollo in self.browse(cr, uid, ids):
            msg_ids = []
            if protocollo.pec:
                for sender_receiver in protocollo.sender_receivers:
                    if sender_receiver.pec_messaggio_ids.ids:
                        msg_id = False
                        msg_date = False
                        for pec_messaggio in sender_receiver.pec_messaggio_ids:
                            if pec_messaggio.type=='messaggio' and (not msg_date or pec_messaggio.messaggio_ref.date>msg_date):
                                msg_id = pec_messaggio.messaggio_ref.id
                                msg_date = pec_messaggio.messaggio_ref.date
                        if msg_id:
                            msg_ids.append(msg_id)
            else:
                for sender_receiver in protocollo.sender_receivers:
                    if sender_receiver.sharedmail_messaggio_ids.ids:
                        msg_ids.append(sender_receiver.sharedmail_messaggio_ids.ids[0])
            res[protocollo.id] = msg_ids
        return res[ids[0]]

    def check_all_mail_messages(self, cr, uid, ids, *args):
        _logger.debug('check_all_mail_messages')
        for protocollo in self.browse(cr, SUPERUSER_ID, ids):
            if protocollo.pec:
                for sr in protocollo.sender_receivers:
                    if not sr.pec_consegna_status:
                        return False
        return True

    def test_error_mail_message(self, cr, uid, ids, *args):
        _logger.debug('test_error_mail_message')
        for protocollo in self.browse(cr, SUPERUSER_ID, ids):
            if protocollo.pec:
                for sender_receiver in protocollo.sender_receivers:
                    if sender_receiver.pec_messaggio_ids.ids:
                        error = False
                        msg_date = False
                        for pec_messaggio in sender_receiver.pec_messaggio_ids:
                            if pec_messaggio.type=='messaggio' and (not msg_date or pec_messaggio.messaggio_ref.date>msg_date):
                                error = True if (pec_messaggio.errore_consegna_ref or pec_messaggio.non_accettazione_ref) else False
                                msg_date = pec_messaggio.messaggio_ref.date
                        if error:
                            return True
        return False

    def get_body_signature(self, cr, uid, body_html, user_signature, context=None):
        mail_notification_obj = self.pool.get('mail.notification')
        signature_company = mail_notification_obj.get_signature_footer(cr, uid, uid, user_signature=user_signature, context=context)
        if signature_company:
            body_html = tools.append_content_to_html(body_html, signature_company, plaintext=False, container_tag='div')
        return body_html

    def check_journal(self, cr, uid, ids, *args):
        journal_obj = self.pool.get('protocollo.journal')
        journal_id = journal_obj.search(cr, uid, [('state', '=', 'closed'), ('date', '=', time.strftime(DSDT))])
        if journal_id:
            raise orm.except_orm(
                _('Attenzione!'),
                _('Registro Giornaliero di protocollo chiuso! Non e\' possibile inserire nuovi protocolli')
            )
        return True

    # def has_offices(self, cr, uid, ids, *args):
    #     for protocol in self.browse(cr, uid, ids):
    #         if (
    #                 protocol.assegnatari_competenza_uffici_ids or protocol.assegnatari_competenza_dipendenti_ids) and protocol.type == 'in':
    #             return True
    #     return False

    def elimina_bozza(self, cr, uid, ids, context={}):
        try:
            new_context = context.copy()
            new_context['skip_check'] = True
            protocollo = self.browse(cr, uid, ids, new_context)
            if protocollo.elimina_visibility or protocollo.elimina_visibility_with_ref:
                self.unlink(cr, SUPERUSER_ID, ids)
            else:
                raise orm.except_orm(_('Azione Non Valida!'), _('Non è più possibile eliminare la bozza del protocollo'))
        except Exception as e:
            raise orm.except_orm(_('Azione Non Valida!'), _('Si è verificato un errore durante l\'eliminazione della bozza'))
        return True

    def elimina_bozza_with_ref(self, cr, uid, ids, context={}):
        new_context = context.copy()
        new_context['skip_check'] = True
        protocollo = self.browse(cr, uid, ids, new_context)
        mail_pec_ref = protocollo.mail_pec_ref

        if self.elimina_bozza(cr, uid, ids, context):
            if mail_pec_ref.pec_type:
                mail_pec_ref.pec_state = "not_protocol"
            elif mail_pec_ref.sharedmail_type:
                mail_pec_ref.sharedmail_state = "not_protocol"

    def prendi_in_carico(self, cr, uid, ids, context={}):
        try:
            new_context = context.copy()
            new_context['skip_check'] = True
            employee_obj = self.pool.get('hr.employee')
            protocollo = self.browse(cr, uid, ids, new_context)
            check_permission, error = self.assegnazione_validation(cr, uid, protocollo, 'prendi_in_carico', new_context)
            if check_permission == True:
                if context and 'assegnatario_employee_id' in context and context['assegnatario_employee_id']:
                    assegnatario_employee_id = context['assegnatario_employee_id']
                    employee = employee_obj.browse(cr, uid, assegnatario_employee_id)
                    assegnatario_name = employee.name
                else:
                    assegnazione_obj = self.pool.get('protocollo.assegnazione')
                    assegnazione_dipendente_ids = assegnazione_obj.search(cr, uid, [
                        ('protocollo_id', '=', protocollo.id),
                        ('tipologia_assegnazione', '=', 'competenza'),
                        ('tipologia_assegnatario', '=', 'employee'),
                        ('assegnatario_employee_id.user_id.id', '=', uid),
                        ('state', '=', 'assegnato'),
                        ('parent_id', '=', False)
                    ])
                    department_ids = []
                    for employee_id in employee_obj.search(cr, uid, [('user_id', '=', uid)]):
                        employee = employee_obj.browse(cr, uid, employee_id)
                        if employee.department_id:
                            department_ids.append(employee.department_id.id)
                    assegnazione_ufficio_ids = assegnazione_obj.search(cr, uid, [
                        ('protocollo_id', '=', protocollo.id),
                        ('tipologia_assegnazione', '=', 'competenza'),
                        ('tipologia_assegnatario', '=', 'department'),
                        ('assegnatario_department_id', 'in', department_ids),
                        ('state', '=', 'assegnato')
                    ])
                    if assegnazione_dipendente_ids:
                        assegnazione = assegnazione_obj.browse(cr, uid, assegnazione_dipendente_ids[0])
                        assegnatario_employee_id = assegnazione.assegnatario_employee_id.id
                        assegnatario_name = assegnazione.assegnatario_employee_id.name
                    elif assegnazione_ufficio_ids:
                        assegnazione = assegnazione_obj.browse(cr, uid, assegnazione_ufficio_ids[0])
                        employee_id = employee_obj.search(cr, uid, [
                            ('department_id', '=', assegnazione.assegnatario_department_id.id),
                            ('user_id', '=', uid),
                        ], limit=1)
                        employee = employee_obj.browse(cr, uid, employee_id)
                        assegnatario_employee_id = employee.id
                        assegnatario_name = employee.name
                    else:
                        raise orm.except_orm(_('Azione Non Valida!'), _('Assegnazione non trovata!'))

                action_class = "history_icon taken"
                post_vars = {
                    'subject': "Presa in carico",
                    'body': "<div class='%s'><ul><li>Protocollo preso in carico da <span style='color:#007ea6;'>%s</span></li></ul></div>" % (action_class, assegnatario_name),
                    'model': "protocollo.protocollo",
                    'res_id': ids[0]
                }

                self.message_post(cr, uid, ids[0], type="notification", context=context, **post_vars)

                # l'invio della notifica avviene prima della modifica dello stato, perchè se fatta dopo, in alcuni casi,
                # potrebbe non avere più i permessi di scrittura sul protocollo
                self.pool.get('protocollo.assegnazione').modifica_stato_assegnazione(cr, uid, ids, 'preso', assegnatario_employee_id)
            else:
                raise orm.except_orm(_('Azione Non Valida!'), error)
        except Exception as e:
            raise orm.except_orm(_('Azione Non Valida!'), _('Non sei più assegnatario di questo protocollo'))
        return True

    def rifiuta_presa_in_carico(self, cr, uid, ids, motivazione, context={}):
        try:
            new_context = context.copy()
            new_context['skip_check'] = True
            employee_obj = self.pool.get('hr.employee')
            protocollo = self.browse(cr, uid, ids, new_context)
            check_permission, error = self.assegnazione_validation(cr, uid, protocollo, 'rifiuta', new_context)
            if check_permission == True:
                if context and 'assegnatario_employee_id' in context and context['assegnatario_employee_id']:
                    assegnatario_employee_id = context['assegnatario_employee_id']
                    employee = self.pool.get('hr.employee').browse(cr, uid, assegnatario_employee_id)
                    assegnatario_name = employee.name
                else:
                    assegnazione_obj = self.pool.get('protocollo.assegnazione')
                    assegnazione_dipendente_ids = assegnazione_obj.search(cr, uid, [
                        ('protocollo_id', '=', protocollo.id),
                        ('tipologia_assegnazione', '=', 'competenza'),
                        ('tipologia_assegnatario', '=', 'employee'),
                        ('assegnatario_employee_id.user_id.id', '=', uid),
                        ('state', '=', 'assegnato'),
                        ('parent_id', '=', False)
                    ])
                    department_ids = []
                    for employee_id in employee_obj.search(cr, uid, [('user_id', '=', uid)]):
                        employee = employee_obj.browse(cr, uid, employee_id)
                        if employee.department_id:
                            department_ids.append(employee.department_id.id)
                    assegnazione_ufficio_ids = assegnazione_obj.search(cr, uid, [
                        ('protocollo_id', '=', protocollo.id),
                        ('tipologia_assegnazione', '=', 'competenza'),
                        ('tipologia_assegnatario', '=', 'department'),
                        ('assegnatario_department_id', 'in', department_ids),
                        ('state', '=', 'assegnato')
                    ])
                    if assegnazione_dipendente_ids:
                        assegnazione = assegnazione_obj.browse(cr, uid, assegnazione_dipendente_ids[0])
                        assegnatario_employee_id = assegnazione.assegnatario_employee_id.id
                        assegnatario_name = assegnazione.assegnatario_employee_id.name
                    elif assegnazione_ufficio_ids:
                        assegnazione = assegnazione_obj.browse(cr, uid, assegnazione_ufficio_ids[0])
                        employee_id = employee_obj.search(cr, uid, [
                            ('department_id', '=', assegnazione.assegnatario_department_id.id),
                            ('user_id', '=', uid),
                        ], limit=1)
                        employee = employee_obj.browse(cr, uid, employee_id)
                        assegnatario_employee_id = employee.id
                        assegnatario_name = employee.name
                    else:
                        raise orm.except_orm(_('Azione Non Valida!'), _('Assegnazione non trovata!'))

                action_class = "history_icon refused"
                post_vars = {
                    'subject': "Rifiuto assegnazione: %s" % motivazione,
                    'body': "<div class='%s'><ul><li>Assegnazione rifiutata da <span style='color:#990000;'>%s</span></li></ul></div>" % (action_class, assegnatario_name),
                    'model': "protocollo.protocollo",
                    'res_id': ids[0]
                }

                self.message_post(cr, uid, ids[0], type="notification", context=context, **post_vars)

                # l'invio della notifica avviene prima della modifica dello stato, perchè se fatta dopo, in alcuni casi,
                # potrebbe non avere più i permessi di scrittura sul protocollo
                self.pool.get('protocollo.assegnazione').modifica_stato_assegnazione(cr, uid, ids, 'rifiutato', assegnatario_employee_id, motivazione)
            else:
                raise orm.except_orm(_('Attenzione!'), _('Il protocollo non può più essere rifiutato!'))
        except Exception as e:
            raise orm.except_orm(_('Attenzione!'), _('Non sei più assegnatario di questo protocollo!'))
        return True

    def segna_come_letto(self, cr, uid, ids, assegnatario_employee_id, context=None):
        try:
            check_permission = self.browse(cr, uid, ids, {'skip_check': True}).segna_come_letto_visibility
            if check_permission == True:
                employee = self.pool.get('hr.employee').browse(cr, uid, assegnatario_employee_id)
                assegnatario_name = employee.name

                action_class = "history_icon taken"
                post_vars = {
                    'subject': "Segnato come letto",
                    'body': "<div class='%s'><ul><li>Protocollo letto da <span style='color:#007ea6;'>%s</span></li></ul></div>" % (action_class, assegnatario_name),
                    'model': "protocollo.protocollo",
                    'res_id': ids[0]
                }

                self.message_post(cr, uid, ids[0], type="notification", context=context, **post_vars)

                self.pool.get('protocollo.assegnazione').modifica_stato_assegnazione_conoscenza(cr, uid, ids, 'letto', assegnatario_employee_id)
            else:
                raise orm.except_orm(_('Azione Non Valida!'), _('Il protocollo non può più essere segnato come letto!'))
        except Exception as e:
            raise orm.except_orm(_('Azione Non Valida!'), _('Non sei più assegnatario di questo protocollo'))
        return True

    def _verifica_dati_sender_receiver(self, cr, uid, vals, context):
        if vals and vals.has_key('senders'):
            for mittente in vals['senders']:
                if mittente[0] == 0:
                    mittente_data = mittente[2]
                    mittente_data['source'] = 'sender'
        if vals and vals.has_key('receivers'):
            for destinatario in vals['receivers']:
                if destinatario[0] == 0:
                    destinatario_data = destinatario[2]
                    destinatario_data['source'] = 'receiver'
        return vals

    def _verifica_registration_employee(self, cr, uid, vals, context):
        if vals and 'registration_employee_department_id' in vals and vals['registration_employee_department_id']:
            department = self.pool.get('hr.department').browse(cr, uid, vals['registration_employee_department_id'])
            vals['registration_employee_department_name'] = department and department.complete_name or False
            employee = self.pool.get('hr.employee').get_department_employee(cr, uid, department.id)
            vals['registration_employee_id'] = employee.id
            vals['registration_employee_name'] = employee.name_related
        return vals

    def create(self, cr, uid, vals, context=None):
        new_context = dict(context or {})
        new_context['skip_check'] = True
        vals = self._verifica_dati_sender_receiver(cr, uid, vals, new_context)
        protocollo_id = super(protocollo_protocollo, self).create(cr, uid, vals, context=new_context)
        if protocollo_id and not 'name' in vals:
            super(protocollo_protocollo, self).write(cr, uid, [protocollo_id], {'name': 'bozza ' + str(protocollo_id)})
        return protocollo_id

    def write(self, cr, uid, ids, vals, context=None):
        vals = self._verifica_dati_sender_receiver(cr, uid, vals, context)
        vals = self._verifica_registration_employee(cr, uid, vals, context)
        if 'registration_employee_department_id' in vals:
            department = self.pool.get('hr.department').browse(cr, uid, vals['registration_employee_department_id'])
            vals['registration_employee_department_name'] = department and department.complete_name or False
        cause = context['cause'] if context and ('cause' in context) else ''
        if isinstance(ids, int):
            ids = [ids]
        for protocollo_id in ids:
            self.save_general_data_history(cr, uid, protocollo_id, cause, vals)
        protocollo_id = super(protocollo_protocollo, self).write(cr, uid, ids, vals, context=context)
        if 'reserved' in vals and vals['reserved']:
            protocollo_assegnazione_obj = self.pool.get('protocollo.assegnazione')
            assegnazione_to_unlink_ids = protocollo_assegnazione_obj.search(cr, uid, [
                ('protocollo_id', 'in', ids),
                ('parent_id', '=', False)
            ])
            if assegnazione_to_unlink_ids:
                protocollo_assegnazione_obj.unlink(cr, uid, assegnazione_to_unlink_ids)
        return protocollo_id

    def unlink(self, cr, uid, ids, context=None):
        stat = self.read(cr, uid, ids, ['registration_date'], context=context)
        unlink_ids = []
        for t in stat:
            if not t['registration_date']:
                unlink_ids.append(t['id'])
            else:
                raise orm.except_orm(
                    _('Azione Non Valida!'),
                    _('I protocolli registrati non possono essere eliminati!')
                )
        return super(protocollo_protocollo, self).unlink(
            cr, uid, unlink_ids, context=context)

    def action_server_cancel_protocollo(self, cr, uid, ids, context=None):
        for id in ids:
            protocollo = self.browse(cr, uid, id, context)
            if protocollo.state == 'draft':
                raise orm.except_orm(
                    "Attenzione",
                    "Il protocollo deve essere registrato prima di essere annullato!"
                )
            if protocollo.state == 'canceled':
                raise orm.except_orm(
                    "Attenzione",
                    "Il protocollo è già stato annullato in precedenza!"
                )
            if not protocollo.annulla_visibility:
                raise orm.except_orm(
                    "Attenzione!",
                    "La tua utenza non è abilitata per l'annullamento del protocollo. Richiedi l'annullamento al Responsabile del Servizio di Protocollo"
                )
        return {
            'name': 'Annulla Protocollo',
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'protocollo.cancel.wizard',
            'target': 'new',
            'context': context
        }

    def action_clona_protocollo(self, cr, uid, ids, defaults, clona_assegnatari, context=None):
        protocollo_obj = self.pool.get('protocollo.protocollo')
        department_obj = self.pool.get('hr.department')
        employee_obj = self.pool.get('hr.employee')
        protocollo = protocollo_obj.browse(cr, uid, ids, context={'skip_check': True})
        if not defaults:
            defaults = {}

        type = defaults.get('type', protocollo.type)
        types = self.get_protocollo_types_by_group(cr, uid, 'seedoo_protocollo', 'group_crea_protocollo_', '')
        if not (type in types):
            raise orm.except_orm(_('Azione Non Valida!'), ('La tua utenza non ha i permessi di creazione del protocollo'))

        if protocollo.type == 'in' and (protocollo.typology.pec or protocollo.typology.sharedmail) and \
                (not context or not 'skip_typology_check' in context or not context['skip_typology_check']):
            raise orm.except_orm(_('Azione Non Valida!'), ('Impossibile duplicare un protocollo in ingresso di tipo PEC o e-mail'))

        if protocollo.registration_type == 'emergency':
            raise orm.except_orm(_('Azione Non Valida!'), ('Impossibile duplicare un protocollo in emergenza'))

        sender_receiver_obj = self.pool.get('protocollo.sender_receiver')
        sender_receivers = defaults.get('sender_receivers', [])
        department = []

        if not sender_receivers:
            for sr in protocollo.sender_receivers:
                sr_copy_id = sender_receiver_obj.copy(cr, uid, sr.id, {}, context=context)
                sender_receivers.append(sr_copy_id)

        department_ids = department_obj.search(cr, uid, [('can_used_to_protocol', '=', True)])
        employee = None
        if department_ids:
            department = department_obj.browse(cr, uid, department_ids[0])
            employee = employee_obj.get_department_employee(cr, uid, department_ids[0])

        vals = {}
        vals['type'] = type
        #vals['receiving_date'] = protocollo.receiving_date
        vals['subject'] = defaults.get('subject', protocollo.subject)
        vals['body'] = defaults.get('body', protocollo.body)
        vals['user_id'] = uid
        vals['registration_employee_department_id'] = len(department_ids) == 1 and department.id or False
        vals['registration_employee_department_name'] = len(department_ids) == 1 and department.complete_name or False
        vals['registration_employee_id'] = employee and employee.id or False
        vals['registration_employee_name'] = employee and employee.name_related or False
        vals['state'] = 'draft'
        vals['typology'] = defaults.get('typology', protocollo.typology.id)
        #vals['senders'] = protocollo.senders
        #vals['receivers'] = protocollo.receivers
        vals['reserved'] = defaults.get('reserved', protocollo.reserved)
        vals['sender_receivers'] = [[6, 0, sender_receivers]]
        vals['classification'] = defaults.get('classification', protocollo.classification.id)
        vals['classification_name'] = defaults.get('classification_name', protocollo.classification_name)
        vals['sender_internal_name'] = defaults.get('sender_internal_name', protocollo.sender_internal_name)
        vals['sender_internal_assegnatario'] = defaults.get('sender_internal_assegnatario', protocollo.sender_internal_assegnatario.id)
        vals['sender_internal_employee'] = defaults.get('sender_internal_employee', protocollo.sender_internal_employee.id)
        vals['sender_internal_employee_department'] = defaults.get('sender_internal_employee_department', protocollo.sender_internal_employee_department.id)
        vals['sender_internal_department'] = defaults.get('sender_internal_department', protocollo.sender_internal_department.id)

        protocollo_id = protocollo_obj.create(cr, uid, vals)

        if clona_assegnatari:
            self.clona_assegnatari_competenza(cr, uid, protocollo, protocollo_id, employee)
            self.clona_assegnatari_conoscenza(cr, uid, protocollo, protocollo_id, employee)

        return {
            'name': 'Protocollo',
            'view_type': 'form',
            'view_mode': 'form,tree',
            'res_model': 'protocollo.protocollo',
            'res_id': protocollo_id,
            'context': context,
            'type': 'ir.actions.act_window',
            'flags': {'initial_mode': 'edit'}
        }

    def clona_assegnatari_competenza(self, cr, uid, protocollo, protocollo_new_id, assegnatore, all=False):
        assegnazione_obj = self.pool.get('protocollo.assegnazione')
        domain = [
            ('protocollo_id', '=', protocollo.id),
            ('tipologia_assegnazione', '=', 'competenza'),
            ('parent_id', '=', False)
        ]
        config_assegnazione = self.pool.get('protocollo.configurazione').get_configurazione_assegnazione(cr, uid, True)
        if config_assegnazione != 'all':
            domain.append(('tipologia_assegnatario', '=', config_assegnazione))
        limit = 1
        if all:
            limit = None
        assegnatario_competenza_ids = []
        assegnazione_ids = assegnazione_obj.search(cr, uid, domain, order='id ASC', limit=limit)
        for assegnazione_id in assegnazione_ids:
            assegnazione = assegnazione_obj.browse(cr, uid, assegnazione_id)
            assegnatario_competenza_ids.append(assegnazione.assegnatario_id.id)
        if assegnatario_competenza_ids:
            assegnazione_obj.salva_assegnazione_competenza(cr, uid, protocollo_new_id, assegnatario_competenza_ids, assegnatore.id)

    def clona_assegnatari_conoscenza(self, cr, uid, protocollo, protocollo_new_id, assegnatore):
        assegnazione_obj = self.pool.get('protocollo.assegnazione')
        domain = [
            ('protocollo_id', '=', protocollo.id),
            ('tipologia_assegnazione', '=', 'conoscenza'),
            ('parent_id', '=', False)
        ]
        config_assegnazione = self.pool.get('protocollo.configurazione').get_configurazione_assegnazione(cr, uid, True)
        if config_assegnazione != 'all':
            domain.append(('tipologia_assegnatario', '=', config_assegnazione))
        assegnatario_conoscenza_ids = []
        assegnazione_ids = assegnazione_obj.search(cr, uid, domain, order='id ASC')
        for assegnazione_id in assegnazione_ids:
            assegnazione = assegnazione_obj.browse(cr, uid, assegnazione_id)
            assegnatario_conoscenza_ids.append(assegnazione.assegnatario_id.id)
        if assegnatario_conoscenza_ids:
            assegnazione_obj.salva_assegnazione_conoscenza(cr, uid, protocollo_new_id, assegnatario_conoscenza_ids, assegnatore.id, False)

    def carica_documento_principale(self, cr, uid, protocollo_id, datas, datas_fname, datas_description, context=None):

        configurazione_ids = self.pool.get('protocollo.configurazione').search(cr, uid, [])
        configurazione = self.pool.get('protocollo.configurazione').browse(cr, uid, configurazione_ids[0])
        raw_file_data = base64.b64decode(datas)
        if len(raw_file_data) > 1048576:
            raw_file_data = raw_file_data[:1048576]
        mimetype = magic.from_buffer(raw_file_data, mime=True)

        protocollo_obj = self.pool.get('protocollo.protocollo')
        attachment_obj = self.pool.get('ir.attachment')

        attachment_ids = attachment_obj.search(cr, uid, [
            ('res_model', '=', 'protocollo.protocollo'),
            ('res_id', '=', protocollo_id),
            ('is_protocol', '=', True)
        ])

        if attachment_ids:
            attachments = attachment_obj.browse(cr, uid, attachment_ids)
            for attachment in attachments:
                if attachment.is_main:
                    attachment_obj.unlink(cr, SUPERUSER_ID, attachment.id)

        attachment_id = attachment_obj.create(
            cr, uid,
            {
                'name': datas_fname,
                'datas': datas,
                'datas_fname': datas_fname,
                'datas_description': datas_description,
                'res_model': 'protocollo.protocollo',
                'is_protocol': True,
                'res_id': protocollo_id,
            }
        )
        protocollo_obj.write(cr, uid, protocollo_id, {'doc_id': attachment_id, 'mimetype': mimetype}, context)

        for prot in self.browse(cr, uid, protocollo_id, {'skip_check': True}):
            if prot.state == 'registered':
                try:
                    vals = {}
                    prot_number = prot.name
                    prot_complete_name = prot.name
                    prot_date = prot.registration_date
                    if prot.doc_id:
                        prot_datas = prot.doc_id.datas
                        if prot.mimetype == 'application/pdf' and configurazione.genera_segnatura:
                            prot_datas_signed = self.pool.get('protocollo.signature').sign_doc(cr, uid, prot, prot_complete_name, prot_date, prot.doc_id)
                            if prot_datas_signed:
                                prot_datas = prot_datas_signed
                        fingerprint = self._create_protocol_document(
                            cr,
                            uid,
                            prot,
                            prot_number,
                            prot_datas
                        )
                        vals['fingerprint'] = fingerprint
                        vals['datas'] = 0
                    self.write(cr, uid, [prot.id], vals, {'skip_check': True})

                    action_class = "history_icon upload"
                    post_vars = {'subject': "Upload documento",
                                 'body': "<div class='%s'><ul><li>Aggiunto documento principale: %s</li></ul></div>" % (
                                     action_class, datas_fname),
                                 'model': "protocollo.protocollo",
                                 'res_id': prot.id,
                                 }

                    thread_pool = self.pool.get('protocollo.protocollo')
                    thread_pool.message_post(cr, uid, prot.id, type="notification", context=context, **post_vars)

                    # self.write(cr, uid, [prot.id], vals)
                except Exception as e:
                    _logger.error(e)
                    raise openerp.exceptions.Warning(_("Errore nell'aggiunta del documento principale"))
                continue

            return True

    def aggiorna_segnatura_xml(self, cr, uid, ids, force=False, log=True, commit=False, context=None):
        count = 0
        total = len(ids)
        for id in ids:
            count += 1
            protocollo = self.browse(cr, uid, id, {'skip_check': True})
            try:
                if (not protocollo.xml_signature or force) and protocollo.type in ['in', 'out']:
                    segnatura_xml = SegnaturaXML(protocollo, protocollo.name, protocollo.registration_date, cr, uid)
                    xml = segnatura_xml.generate_segnatura_root()
                    etree_tostring = etree.tostring(xml, pretty_print=True)
                    vals = {'xml_signature': etree_tostring}
                    self.write(cr, uid, [protocollo.id], vals)
                    if protocollo.type == 'out' and protocollo.pec:
                        configurazione_obj = self.pool.get('protocollo.configurazione')
                        configurazione_ids = configurazione_obj.search(cr, uid, [])
                        configurazione = configurazione_obj.browse(cr, uid, configurazione_ids[0])
                        if configurazione.segnatura_xml_invia:
                            attachment_replace = True
                            # se il protocollo è stato inviato allora la vecchia segnatura.xml non deve essere eliminata
                            # perchè è un allegato della email inviata. Si deve quindi eliminare solo il collegamento
                            # con il protocollo in modo che si veda solo la nuova segnatura.xml
                            if protocollo.state in ['waiting', 'error', 'sent']:
                                attachment_replace = False
                            self.allega_segnatura_xml(cr, uid, protocollo.id, protocollo.xml_signature, attachment_replace, context)
                    if commit:
                        cr.commit()
                    if log:
                        _logger.debug("Protocollo numero %s - (%s/%s) aggiornato", protocollo.name, str(count), str(total))
                elif log:
                        _logger.debug("Protocollo numero %s - (%s/%s) non aggiornato: segnatura xml presente", protocollo.name, str(count), str(total))
            except Exception as e:
                _logger.error("Protocollo numero %s - (%s/%s) non aggiornato: %s", protocollo.name, str(count), str(total), str(e))

    def allega_segnatura_xml(self, cr, uid, protocollo_id, xml_segnatura, attachment_replace, context=None):
        xml_segnatura_datas = base64.b64encode(xml_segnatura)
        attachment_obj = self.pool.get('ir.attachment')
        attachment_ids = attachment_obj.search(cr, uid, [
            ('name', '=', 'Segnatura.xml'),
            ('res_model', '=', 'protocollo.protocollo'),
            ('is_protocol', '=', True),
            ('res_id', '=', protocollo_id)
        ])
        if attachment_ids:
            if attachment_replace:
                attachment_obj.unlink(cr, SUPERUSER_ID, attachment_ids)
            else:
                attachment_obj.write(cr, uid, attachment_ids, {
                    'res_model': False,
                    'is_protocol': False,
                    'res_id': False
                })
        attachment_obj.create(cr, uid, {
            'name': 'Segnatura.xml',
            'datas': xml_segnatura_datas,
            'datas_fname': 'Segnatura.xml',
            'datas_description': 'Segnatura.xml',
            'res_model': 'protocollo.protocollo',
            'is_protocol': True,
            'res_id': protocollo_id
        })

    def carica_documenti_secondari(self, cr, uid, protocollo_id, file_data_list, context=None):
        prot = self.browse(cr, uid, protocollo_id, context={'skip_check': True})

        attachment_index = 1
        attachment_created_ids = []
        attachment_obj = self.pool.get('ir.attachment')
        attachment_domain = [
            ('res_model', '=', 'protocollo.protocollo'),
            ('res_id', '=', protocollo_id),
            ('is_protocol', '=', True)
        ]
        if prot.doc_id:
            attachment_domain.append(('id', '!=', prot.doc_id.id))
        if prot.type == 'out' and prot.pec:
            configurazione_obj = self.pool.get('protocollo.configurazione')
            configurazione_ids = configurazione_obj.search(cr, uid, [])
            configurazione = configurazione_obj.browse(cr, uid, configurazione_ids[0])
            if configurazione.segnatura_xml_invia:
                # non si considera il file Segnatura.xml perchè tanto verrà eliminato e rigenerato
                attachment_domain.append(('name', '!=', 'Segnatura.xml'))
        attachment_ids = attachment_obj.search(cr, uid, attachment_domain)
        if attachment_ids and context and 'delete_all' in context:
            attachment_obj.unlink(cr, SUPERUSER_ID, attachment_ids)
        elif attachment_ids and context and 'append' in context:
            attachment_index = len(attachment_ids) + 1

        counter = 0
        nomi_allegati = ''
        try:
            for file_data in file_data_list:
                if 'attachment_id' in file_data and file_data['attachment_id']:
                    if prot.registration_date:
                        raise orm.except_orm(_('Attenzione!'), _('Non è possibile modificare il documento: il protocollo è già stato registrato!'))
                    attachment_values = {
                        'name': file_data['datas_fname'],
                        'datas': file_data['datas'],
                        'datas_fname': file_data['datas_fname'],
                        'datas_description': file_data['datas_description']
                    }
                    attachment_obj.write(cr, uid, [file_data['attachment_id']], attachment_values)
                else:
                    attachment_created_id = self._create_protocol_attachment(
                        cr, uid, prot,
                        file_data['datas_fname'],
                        file_data['datas'],
                        file_data['datas_description'],
                        attachment_index
                    )
                    attachment_created_ids.append(attachment_created_id)
                nomi_allegati += file_data['datas_fname']
                if counter < len(file_data_list) - 1:
                    nomi_allegati += ', '
                counter += 1
                attachment_index += 1
        except Exception as e:
            _logger.error(e)
            raise openerp.exceptions.Warning(_("Errore nell'upload documento"))

        text = 'o' if counter == 1 else 'i'

        prot = self.browse(cr, uid, protocollo_id, {'skip_check': True})
        if prot.state in self.get_history_state_list(cr, uid) and counter > 0:
            action_class = "history_icon upload"
            post_vars = {'subject': "Upload documento",
                         'body': "<div class='%s'><ul><li>Aggiunt%s %d allegat%s: <i>%s</i></li></ul></div>" % (
                             action_class, text, len(file_data_list), text, nomi_allegati),
                         'model': "protocollo.protocollo",
                         'res_id': protocollo_id,
                         }

            thread_pool = self.pool.get('protocollo.protocollo')
            thread_pool.message_post(cr, uid, protocollo_id, type="notification", context=context, **post_vars)

        return attachment_created_ids

    def carica_allegato_protocollo(self, cr, uid, ids, context=None):
        configurazione_ids = self.pool.get('protocollo.configurazione').search(cr, uid, [])
        configurazione = self.pool.get('protocollo.configurazione').browse(cr, uid, configurazione_ids[0])
        if context['active_model'] == 'ir.attachment':
            attachment = self.pool.get('ir.attachment').browse(cr, uid, context['active_id'])
            wizard_datas = {
                'read_only_mode': False,
                'datas_fname': attachment.datas_fname,
                'datas': attachment.datas,
                'datas_description': attachment.datas_description,
                'attachment_description_required': configurazione.allegati_descrizione_required
            }
        else:
            wizard_datas = {
                'read_only_mode': False,
            }
        wizard_id = self.pool.get('protocollo.carica.allegato.wizard').create(cr, uid, wizard_datas)
        return {
            'name': 'Carica Allegato',
            'view_type': 'form',
            'view_mode': 'form,tree',
            'res_model': 'protocollo.carica.allegato.wizard',
            'res_id': wizard_id,
            'context': context,
            'type': 'ir.actions.act_window',
            'target': 'new'
        }

    def mostra_allegato_protocollo(self, cr, uid, ids, context=None):
        configurazione_ids = self.pool.get('protocollo.configurazione').search(cr, uid, [])
        configurazione = self.pool.get('protocollo.configurazione').browse(cr, uid, configurazione_ids[0])
        attachment = self.pool.get('ir.attachment').browse(cr, uid, context['active_id'])
        wizard_datas = {
            'read_only_mode': True,
            'datas_fname': attachment.datas_fname,
            'datas': attachment.datas,
            'datas_description': attachment.datas_description,
            'attachment_description_required': configurazione.allegati_descrizione_required
        }
        wizard_id = self.pool.get('protocollo.carica.allegato.wizard').create(cr, uid, wizard_datas)
        return {
            'name': 'Allegato',
            'view_type': 'form',
            'view_mode': 'form,tree',
            'res_model': 'protocollo.carica.allegato.wizard',
            'res_id': wizard_id,
            'context': context,
            'type': 'ir.actions.act_window',
            'target': 'new'
        }

    def elimina_allegato_protocollo(self, cr, uid, ids, context=None):
        protocollo_id = False
        attachment_obj = self.pool.get('ir.attachment')
        attachments = attachment_obj.browse(cr, uid, ids)
        for attachment in attachments:
            if attachment.res_model == 'protocollo.protocollo':
                protocollo_id = attachment.res_id
        attachment_obj.unlink(cr, SUPERUSER_ID, ids)
        if protocollo_id:
            return {
                'name': 'Protocollo',
                'view_type': 'form',
                'view_mode': 'form,tree',
                'res_model': 'protocollo.protocollo',
                'res_id': protocollo_id,
                'context': context,
                'type': 'ir.actions.act_window',
                'flags': {'initial_mode': 'edit'}
            }

    def _get_oggetto_mail_pec(self, cr, uid, subject, prot_name, prot_registration_date):
        prefix = "Prot. n. " + prot_name + " del " + prot_registration_date + " - "
        subject_text = prefix + subject
        return subject_text

    def _get_name_documento_allegato(self, cr, uid, attachment_name, prot_number, prefix, is_main):
        reg_date = fields.datetime.now()[0:10]
        doc_type = 'Documento' if is_main else 'Allegato'
        complete_prefix = prefix + '_' + prot_number + '_' + reg_date + '_' + doc_type
        file_name = complete_prefix + "_" + attachment_name
        return file_name

    # @api.cr_uid_ids_context
    # Gestione dello Storico attraverso Mail Thread
    def message_post(self, cr, uid, thread_id, body='', subject=None, type='notification',
                     subtype=None, parent_id=False, attachments=None, context=None,
                     content_subtype='html', **kwargs):
        new_context = dict(context or {})
        new_context['skip_check'] = True
        protocollo = self.pool.get('protocollo.protocollo').browse(cr, uid, thread_id, new_context)
        if protocollo.state == 'draft' and str(subject).find('Registrazione') != 0 and str(subject).find(
                'Errore Generazione') != 0 and new_context.has_key('is_mailpec_to_draft') == False:
            pass
        else:
            return super(protocollo_protocollo, self).message_post(
                cr, uid, thread_id, body=body,
                subject=subject, type=type,
                subtype=subtype, parent_id=parent_id,
                attachments=attachments, context=new_context,
                content_subtype=content_subtype, **kwargs)


    def action_remove_sender_internal(self, cr, uid, ids, context=None):
        protocollo_obj = self.pool.get('protocollo.protocollo')
        protocollo = protocollo_obj.browse(cr, uid, context['protocollo_id'])
        vals = {}
        vals['sender_internal_assegnatario'] = False
        vals['sender_internal_name'] = False
        vals['sender_internal_employee'] = False
        vals['sender_internal_employee_department'] = False
        vals['sender_internal_department'] = False

        if protocollo.state in protocollo_obj.get_history_state_list(cr, uid):
            action_class = "history_icon update"
            body = "<div class='%s'><ul>" % action_class
            body += "<li>%s: <span style='color:#990000'> %s</span> -> <span style='color:#007ea6'> %s </span></li>" \
                    % ('Mittente', protocollo.sender_internal_name, '')
            body += "</ul></div>"
            post_vars = {
                'subject': "Cancellazione mittente",
                'body': body,
                'model': 'protocollo.protocollo',
                'res_id': context['active_id']
            }
            protocollo_obj.message_post(cr, uid, context['active_id'], type="notification", context={'pec_messages': True}, **post_vars)

        protocollo.write(vals)

        return {
            'name': 'Protocollo',
            'view_type': 'form',
            'view_mode': 'form,tree',
            'res_model': 'protocollo.protocollo',
            'res_id': context['protocollo_id'],
            'context': context,
            'type': 'ir.actions.act_window',
            'flags': {'initial_mode': 'edit'}
        }


    def crea_mittente(self, cr, uid, ids, context={}):
        model_data_obj = self.pool.get('ir.model.data')
        view_rec = model_data_obj.get_object_reference(cr, uid, 'seedoo_protocollo', 'protocollo_create_mittente_destinatario_wizard_view')
        view_id = view_rec and view_rec[1] or False

        context['default_source'] = 'sender'
        context['default_protocollo_id'] = ids[0]
        return {
            'name': 'Aggiungi Mittente',
            'view_type': 'form',
            'view_mode': 'form',
            'view_id': view_id,
            'res_model': 'protocollo.create.mittente.destinatario.wizard',
            'context': context,
            'type': 'ir.actions.act_window',
            'target': 'new'
        }


    def crea_destinatario(self, cr, uid, ids, context={}):
        model_data_obj = self.pool.get('ir.model.data')
        view_rec = model_data_obj.get_object_reference(cr, uid, 'seedoo_protocollo', 'protocollo_create_mittente_destinatario_wizard_view')
        view_id = view_rec and view_rec[1] or False

        context['default_source'] = 'receiver'
        context['default_protocollo_id'] = ids[0]
        return {
            'name': 'Aggiungi Destinatario',
            'view_type': 'form',
            'view_mode': 'form',
            'view_id': view_id,
            'res_model': 'protocollo.create.mittente.destinatario.wizard',
            'context': context,
            'type': 'ir.actions.act_window',
            'target': 'new'
        }


    def save_general_data_history(self, cr, uid, protocollo_id, cause, vals):
        before = {}
        after = {}
        protocollo_obj = self.pool.get('protocollo.protocollo')
        protocollo = protocollo_obj.browse(cr, uid, protocollo_id, {'skip_check': True})

        if not (protocollo.state in self.get_history_state_list(cr, uid)):
            return

        if 'typology' in vals:
            before_typology = protocollo.typology.id if protocollo.typology else False
            after_typology = False
            typology = None
            if vals['typology']:
                typology = self.pool.get('protocollo.typology').browse(cr, uid, vals['typology'])
                after_typology = typology.id if typology else False
            if before_typology != after_typology:
                before['Mezzo di trasmissione'] = protocollo.typology.name if protocollo.typology else ''
                after['Mezzo di trasmissione'] = typology.name if typology else ''

        if 'server_sharedmail_id' in vals:
            before_server_sharedmail = protocollo.server_sharedmail_id.id if protocollo.server_sharedmail_id else False
            after_server_sharedmail = False
            server_sharedmail = None
            if vals['server_sharedmail_id']:
                server_sharedmail = self.pool.get('fetchmail.server').browse(cr, uid, vals['server_sharedmail_id'])
                after_server_sharedmail = server_sharedmail.id if server_sharedmail else False
            if before_server_sharedmail != after_server_sharedmail:
                before['Account E-mail'] = protocollo.server_sharedmail_id.name if protocollo.server_sharedmail_id else ''
                after['Account E-mail'] = server_sharedmail.name if server_sharedmail else ''

        if 'server_pec_id' in vals:
            before_server_pec = protocollo.server_pec_id.id if protocollo.server_pec_id else False
            after_server_pec = False
            server_pec = None
            if vals['server_pec_id']:
                server_pec = self.pool.get('fetchmail.server').browse(cr, uid, vals['server_pec_id'])
                after_server_pec = server_pec.id if server_pec else False
            if before_server_pec != after_server_pec:
                before['Account PEC'] = protocollo.server_pec_id.name if protocollo.server_pec_id else ''
                after['Account PEC'] = server_pec.name if server_pec else ''

        if 'subject' in vals:
            if protocollo.subject != vals['subject']:
                before['Oggetto'] = protocollo.subject if protocollo.subject else ''
                after['Oggetto'] = vals['subject'] if vals['subject'] else ''

        if 'email_pec_sending_mode' in vals:
            if protocollo.email_pec_sending_mode != vals['email_pec_sending_mode']:
                selection_values = dict(self.fields_get(cr, uid, ['email_pec_sending_mode'])['email_pec_sending_mode']['selection'])
                before['Modalità Invio'.decode('utf-8')] = selection_values[protocollo.email_pec_sending_mode] if protocollo.email_pec_sending_mode else ''
                after['Modalità Invio'.decode('utf-8')] = selection_values[vals['email_pec_sending_mode']] if vals['email_pec_sending_mode'] else ''

        if 'body' in vals:
            if protocollo.body != vals['body']:
                before['Corpo della mail'] = protocollo.body if protocollo.body else ''
                after['Corpo della mail'] = vals['body'] if vals['body'] else ''

        if 'receiving_date' in vals:
            if protocollo.receiving_date != vals['receiving_date']:
                receiving_date_label = 'Data ricezione'
                if protocollo.receiving_date:
                    before[receiving_date_label] = convert_datetime(protocollo.receiving_date, format_to='%d/%m/%Y %H:%M:%S')
                else:
                    before[receiving_date_label] = ''
                if vals['receiving_date']:
                    after[receiving_date_label] = convert_datetime(vals['receiving_date'], format_to='%d/%m/%Y %H:%M:%S')
                else:
                    after[receiving_date_label] = ''

        self._save_history(cr, uid, protocollo_id, before, after, 'Modifica dati documento', cause)

        before = {}
        after = {}

        if 'sender_registration_date' in vals:
            if protocollo.sender_registration_date != vals['sender_registration_date']:
                sender_label = 'Data registrazione mittente'
                if protocollo.sender_registration_date:
                    before[sender_label] = convert_datetime(protocollo.sender_registration_date, format_from='%Y-%m-%d', format_to='%d/%m/%Y')
                else:
                    before[sender_label] = ''
                if vals['sender_registration_date']:
                    after[sender_label] = convert_datetime(vals['sender_registration_date'], format_from='%Y-%m-%d', format_to='%d/%m/%Y')
                else:
                    after[sender_label] = ''

        if 'sender_protocol' in vals:
            if protocollo.sender_protocol != vals['sender_protocol']:
                before['Protocollo mittente'] = protocollo.sender_protocol if protocollo.sender_protocol else ''
                after['Protocollo mittente'] = vals['sender_protocol'] if vals['sender_protocol'] else ''

        self._save_history(cr, uid, protocollo_id, before, after, 'Modifica dati protocollo mittente', cause)

        before = {}
        after = {}

        if 'notes' in vals:
            if protocollo.notes != vals['notes']:
                before['Altro'] = protocollo.notes if protocollo.notes else ''
                after['Altro'] = vals['notes'] if vals['notes'] else ''

        self._save_history(cr, uid, protocollo_id, before, after, 'Modifica altro', cause)

    def _save_history(self, cr, uid, protocollo_id, before, after, section, cause):
        protocollo_obj = self.pool.get('protocollo.protocollo')

        body = ''
        for key, before_item in before.items():
            body = body + "<li>%s: <span style='color:#990000'> %s</span> -> <span style='color:#007ea6'> %s </span></li>" \
                   % (key, before_item, after[key])
        if body:
            action_class = "history_icon update"
            body_complete = "<div class='%s'><ul>" % action_class
            body_complete += body + "</ul></div>"
            history_subject = section
            if cause:
                history_subject += ": %s" % cause

            post_vars = {
                'subject': history_subject,
                'body': body_complete,
                'model': 'protocollo.protocollo',
                'res_id': protocollo_id
            }

            context = {'pec_messages': True}
            protocollo_obj.message_post(cr, uid, protocollo_id, type="notification", context=context, **post_vars)


    def get_label_competenza(self, cr, uid):
        return 'Assegnario Competenza'


    def message_subscribe(self, cr, uid, ids, partner_ids, subtype_ids=None, context=None):
        if context and context.has_key('skip_check') and context['skip_check']:
            return True
        return super(protocollo_protocollo, self).message_subscribe(cr, uid, ids, partner_ids, subtype_ids=None, context=None)


class protocollo_emergency_registry_line(orm.Model):
    _name = 'protocollo.emergency.registry.line'
    _columns = {
        'name': fields.char('Numero Riservato', size=256, required=True, readonly=True),
        'protocol_id': fields.many2one('protocollo.protocollo', 'Protocollo Registrato', readonly=True),
        'emergency_number': fields.related('protocol_id', 'emergency_protocol', type='char',
                                           string='Protocollo Emergenza', readonly=True),
        'emergency_id': fields.many2one('protocollo.emergency.registry', 'Registro Emergenza'),
    }


class protocollo_emergency_registry(orm.Model):
    _name = 'protocollo.emergency.registry'

    STATE_SELECTION = [
        ('draft', 'Bozza'),
        ('closed', 'Chiuso'),
    ]

    _columns = {
        'name': fields.char('Causa Emergenza', size=256, required=True, readonly=True),
        'user_id': fields.many2one('res.users', 'Responsabile', readonly=True),
        'date_start': fields.datetime('Data Inizio Emergenza', required=True, readonly=True),
        'date_end': fields.datetime('Data Fine Emergenza', required=True, readonly=True),
        'aoo_id': fields.many2one('protocollo.aoo', 'AOO', required=True),
        'registry': fields.related('aoo_id', 'registry_id', type='many2one', relation='protocollo.registry',
                                   string='Registro', store=True, readonly=True),
        'emergency_ids': fields.one2many('protocollo.emergency.registry.line', 'emergency_id',
                                         'Numeri Riservati e Protocollazioni', required=False, readonly=True, ),
        'state': fields.selection(STATE_SELECTION, 'Status', readonly=True, help="Lo stato del protocollo.",
                                  select=True),
    }

    _defaults = {
        'user_id': lambda obj, cr, uid, context: uid,
        'state': 'draft',
    }


class Wizard(object):

    def __init__(self):
        self.count_rifiutati = 100
        self.count_presi_in_carico = 100
        self.count_registrati = 100
        self.count_bozza = 100


class LockerSingleton():
    lock = threading.RLock()
