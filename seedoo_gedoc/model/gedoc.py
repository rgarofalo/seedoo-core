# -*- coding: utf-8 -*-
# This file is part of Seedoo.  The COPYRIGHT file at the top level of
# this module contains the full copyright notices and license terms.

from openerp.osv import fields, osv
from openerp.tools.translate import _
from openerp import SUPERUSER_ID
from openerp import tools


class res_users(osv.Model):
    _inherit = "res.users"

    def validate_login(self, cr, uid, login, context=None):
        if login and not tools.single_email_re.match(login):
            raise osv.except_osv(_('Warning!'), _('Devi inserire un indirizzo e-mail valido'))

    def on_change_login(self, cr, uid, ids, login, context=None):
        self.validate_login(cr, uid, login, context)
        return {'value': {'email': login}}

    def create(self, cr, uid, vals, context=None):
        self.validate_login(cr, uid, vals.get('login', False), context)
        return super(res_users, self).create(cr, uid, vals, context=context)

    def write(self, cr, uid, ids, values, context=None):
        self.validate_login(cr, uid, values.get('login', False), context)
        return super(res_users, self).write(cr, uid, ids, values, context=context)



class protocollo_classification(osv.Model):
    _name = 'protocollo.classification'
    _rec_name = 'path_name'

    def _name_get_fnc(self, cr, uid, ids, prop, unknow_none, context=None):
        if isinstance(ids, (list, tuple)) and not len(ids):
            return dict([])
        if isinstance(ids, (long, int)):
            ids = [ids]
        reads = self.read(cr, uid, ids, ['name', 'code'], context=context)
        res = []
        for record in reads:
            if record['code']:
                name = record['code'] + ' - ' + record['name']
            else:
                name = record['name']
            res.append((record['id'], name))
        return dict(res)

    def _name_search_fnc(self, cr, uid, obj, name, args, domain=None, context=None):
        classification_ids = []
        if args and len(args[0])==3:
            arg = args[0]
            operator = arg[1]
            value = arg[2]
            if operator in ['like', 'ilike', 'not like', 'not ilike']:
                condition = operator + " '%"+value+"%'"
            elif operator in ['=', '!='] and value==False:
                condition = 'IS NULL' if operator=='=' else 'IS NOT NULL'
            else:
                condition = operator + " '"+value+"'"
            where = "CASE WHEN pc.code IS NULL THEN pc.name "+condition+" ELSE concat_ws(' - ', pc.code, pc.name) "+condition+" END"

            cr.execute('''
                SELECT DISTINCT(pc.id) 
                FROM protocollo_classification pc
                WHERE '''+where
            )

            classification_ids = [res[0] for res in cr.fetchall()]
        return [('id', 'in', classification_ids)]

    def _path_name_get(self, cr, uid, id, context=None):
        #read = self.read(cr, uid, id, ['name', 'parent_id'], context=context)
        cr.execute('SELECT name, parent_id FROM protocollo_classification pc WHERE id = ' + str(id))
        read = cr.fetchone()
        name = read[0]
        if read[1]:
            name = self._path_name_get(cr, uid, read[1]) + ' / ' + read[0]
        return name

    def _path_name_get_fnc(self, cr, uid, ids, prop, unknow_none, context=None):
        if isinstance(ids, (list, tuple)) and not len(ids):
            return dict([])
        if isinstance(ids, (long, int)):
            ids = [ids]
        #reads = self.read(cr, uid, ids, ['name', 'code', 'parent_id'], context=context)
        reads = []
        if ids:
            cr.execute('SELECT id, name, code, parent_id FROM protocollo_classification pc WHERE id IN (' + ','.join(map(str, ids)) + ')')
            reads = cr.fetchall()
        res = []
        for record in reads:
            name = record[1]
            if record[3]:
                name = self._path_name_get(cr, uid, record[3]) + ' / ' + record[1]
            if record[2]:
                name = record[2] + ' - ' + name
            else:
                name = name
            res.append((record[0], name))
        return dict(res)

    def _path_name_search(self, cr, uid, id, context=None):
        classification_ids = []
        cr.execute('SELECT id FROM protocollo_classification pc WHERE parent_id = ' + str(id))
        for res in cr.fetchall():
            classification_ids.append(res[0])
            if res[0]:
                classification_ids += self._path_name_search(cr, uid, res[0], context)
        return classification_ids

    def _path_name_search_fnc(self, cr, uid, obj, name, args, domain=None, context=None):
        classification_ids = []
        if args and len(args[0])==3:
            arg = args[0]
            operator = arg[1]
            value = arg[2]
            if operator in ['like', 'ilike', 'not like', 'not ilike']:
                condition = operator + " '%"+value+"%'"
            elif operator in ['=', '!='] and value==False:
                condition = 'IS NULL' if operator=='=' else 'IS NOT NULL'
            else:
                condition = operator + " '"+value+"'"
            where = "CASE WHEN pc.code IS NULL THEN pc.name "+condition+" ELSE concat_ws(' - ', pc.code, pc.name) "+condition+" END"

            cr.execute('SELECT pc.id FROM protocollo_classification pc WHERE '+where)
            for res in cr.fetchall():
                classification_ids.append(res[0])
                classification_ids += self._path_name_search(cr, uid, res[0], context)
        return [('id', 'in', classification_ids)]

    def _get_child_ids(self, cr, uid, classification):
        res = []
        for child in classification.child_ids:
            res.append(child.id)
            child_res = self._get_child_ids(cr, uid, child)
            res = res + child_res
        return res

    def _get_classification_not_visibile_ids(self, cr, uid):
        classification_not_visible_ids = []
        classification_not_active_ids = self.search(cr, uid, [('active', '=', False)])
        for classification_not_active_id in classification_not_active_ids:
            if not (classification_not_active_id in classification_not_visible_ids):
                classification_not_visible_ids.append(classification_not_active_id)
                classification_not_active = self.browse(cr, uid, classification_not_active_id)
                classification_not_visible_ids += self._get_child_ids(cr, uid, classification_not_active)
        return classification_not_visible_ids

    def _is_visible(self, cr, uid, ids, name, arg, context=None):
        res = []
        classification_not_visible_ids = self._get_classification_not_visibile_ids(cr, uid)
        for id in ids:
            if id in classification_not_visible_ids:
                res.append((id, False))
            else:
                res.append((id, True))
        return dict(res)

    def _is_visible_search(self, cr, uid, obj, name, args, domain=None, context=None):
        classification_not_visible_ids = self._get_classification_not_visibile_ids(cr, uid)
        return [('id', 'not in', classification_not_visible_ids)]

    def get_all_child_ids(self, cr, uid, classification_id):
        child_ids = []
        classification = self.browse(cr, uid, classification_id)
        for child_id in classification.child_ids.ids:
            child_ids.append(child_id)
            child_ids = child_ids + self.get_all_child_ids(cr, uid, child_id)
        return child_ids

    def _is_visible_parent(self, cr, uid, ids, name, arg, context=None):
        return {}

    def _is_visible_parent_search(self, cr, uid, obj, name, args, domain=None, context=None):
        classification_not_visible_ids = []
        if context and 'id' in context and context['id']:
            classification_not_visible_ids = [context['id']] + self.get_all_child_ids(cr, uid, context['id'])
        return [('id', 'not in', classification_not_visible_ids)]

    _columns = {
        'name': fields.char(
            'Nome', size=256, required=True),
        'parent_id': fields.many2one(
            'protocollo.classification',
            'Padre'),
        'child_ids': fields.one2many(
            'protocollo.classification',
            'parent_id',
            'Children'),
        'complete_name': fields.function(
            _name_get_fnc,
            fnct_search=_name_search_fnc,
            type='char',
            string='Nome Completo'),
        'path_name': fields.function(
            _path_name_get_fnc,
            fnct_search=_path_name_search_fnc,
            type='char',
            string='Nome Completo'),
        'description': fields.text('Descrizione'),
        'code': fields.char(
            'Codice Titolario',
            char=16,
            required=False),
        'class_type': fields.selection(
            [
                ('titolo', 'Titolo'),
                ('classe', 'Classe'),
                ('sottoclasse', 'Sottoclasse'),
            ],
            'Tipologia',
            size=32,
            required=True,
            ),
        'dossier_ids': fields.one2many(
            'protocollo.dossier',
            'classification_id',
            'Fascicoli',
            readonly=True
        ),
        'sequence': fields.integer('Ordine di visualizzazione', help="Sequence"),
        'active': fields.boolean('Attivo'),
        'is_visible': fields.function(_is_visible, fnct_search=_is_visible_search, type='boolean', string='Visibile'),
        'is_visible_parent': fields.function(_is_visible_parent, fnct_search=_is_visible_parent_search, type='boolean', string='Padre Visibile'),
    }

    _defaults = {
        'sequence': 10,
        'active': True
    }


class protocollo_dossier(osv.Model):
    _name = 'protocollo.dossier'

    DOSSIER_TYPE = {
        'fascicolo': 'Fascicolo',
        'sottofascicolo': 'Sottofascicolo',
        'inserto': 'Inserto',
    }

    PARENT_TYPE = {
        'fascicolo': False,
        'sottofascicolo': 'fascicolo',
        'inserto': 'sottofascicolo'
    }

    DOSSIER_TYPOLOGY = {
        'procedimento': 'Procedimento',
        'affare': 'Affare',
        'attivita': 'Attività',
        'fisica': 'Persona Fisica',
        'giuridica': 'Persona Giuridica',
        'materia': 'Materia',
    }

    def get_dossier_values(self, cr, uid, ids, dossier_type, classification_id, parent_id, description, context=None):
        name = ''
        parent = None
        if not description:
            description = ''
        if parent_id and dossier_type != 'fascicolo':
            parent = self.browse(cr, SUPERUSER_ID, parent_id, context=context)
            parent_split = parent.name.split(' - ', 1)
            classification_id = parent.classification_id.id
            #num = len(list(set(parent.child_ids.ids) - set(ids))) + 1
            #name = '<' + self.DOSSIER_TYPE[dossier_type] + ' N.' + str(num) + ' del "' + parent.name + '">'
            #TODO: gestire tramite una sequence
            domain = [('parent_id', '=', parent_id)]
            if ids:
                domain.append(('id', 'not in', ids))
            child_ids = self.search(cr, SUPERUSER_ID, domain, order='id DESC')
            if child_ids:
                split_result = self.browse(cr, SUPERUSER_ID, child_ids[0]).name.split(' - ', 1)[0].split('.')
                num = int(split_result[len(split_result)-1])
            else:
                num = 0
            name = '%s.%s - %s / %s' % (parent_split[0], str(num + 1), parent_split[1], description)
        elif dossier_type and dossier_type in self.DOSSIER_TYPE and classification_id:
            classification = self.pool.get('protocollo.classification').browse(cr, uid, classification_id, context=context)
            parent_split = classification.path_name.split(' - ', 1)
            #num = len(list(set(classification.dossier_ids.ids) - set(ids))) + 1
            #name = '<' + self.DOSSIER_TYPE[dossier_type] + ' N.' + str(num) + ' del \'' + classification.name + '\'>'
            #TODO: gestire tramite una sequence
            domain = [('classification_id', '=', classification_id),('dossier_type', '=', 'fascicolo')]
            if ids:
                domain.append(('id', 'not in', ids))
            child_ids = self.search(cr, SUPERUSER_ID, domain, order='id DESC')
            if child_ids:
                split_result = self.browse(cr, SUPERUSER_ID, child_ids[0]).name.split(' - ', 1)[0].split('.')
                num = int(split_result[len(split_result) - 1])
            else:
                num = 0
            name = '%s.%s - %s / %s' % (parent_split[0], str(num + 1), parent_split[1], description)
            if dossier_type == 'fascicolo':
                parent_id = False
        parent_type = self.PARENT_TYPE[dossier_type]
        values = {
            'name': name,
            'classification_id': classification_id,
            'parent_id': parent_id,
            'parent_type': parent_type
        }
        if parent and context.get('call_by_parent_id', False):
            values['office_comp_ids'] = parent.office_comp_ids.ids
            values['office_view_ids'] = parent.office_view_ids.ids
            values['employee_comp_ids'] = parent.employee_comp_ids.ids
            values['employee_view_ids'] = parent.employee_view_ids.ids
        return values

    def on_change_dossier_type_classification(self, cr, uid, ids, dossier_type, classification_id, parent_id, description, context=None):
        values = self.get_dossier_values(cr, uid, ids, dossier_type, classification_id, parent_id, description, context)
        return {'value': values}

    def _parent_type(self, cr, uid, ids, name, arg, context=None):
        if not context:
            context = {}
        if isinstance(ids, (list, tuple)) and not len(ids):
            return []
        if isinstance(ids, (long, int)):
            ids = [ids]
        res = {}
        for dossier in self.browse(cr, uid, ids):
            res[dossier.id] = dossier.dossier_type and \
                self.PARENT_TYPE[dossier.dossier_type] or \
                None
        return res

    _columns = {
        'name': fields.char(
            'Nome',
            size=256,
            required=True,
            readonly=True,
        ),
        'description': fields.text(
            'Oggetto',
            required=True,
            readonly=True,
            states={'draft':
                    [('readonly', False)]
                    }
        ),
        'classification_id': fields.many2one(
            'protocollo.classification',
            'Rif. Titolario',
            required=True
        ),
        'year': fields.char(
            'Anno',
            size=4,
            readonly=True
        ),
        'user_id': fields.many2one(
            'res.users',
            'Responsabile',
            readonly=True
        ),
        'dossier_type': fields.selection(
            DOSSIER_TYPE.items(),
            'Tipo',
            size=32,
            required=True,
            readonly=True,
            states={'draft':
                    [('readonly', False)]
                    }
            ),
        'dossier_typology': fields.selection(
            DOSSIER_TYPOLOGY.items(),
            'Tipologia',
            size=32,
            required=True,
            readonly=True,
            states={'draft':
                    [('readonly', False)]
                    }
            ),
        'date_open': fields.datetime(
            'Data Apertura',
            readonly=True
        ),
        'date_close': fields.datetime(
            'Data Chiusura',
            readonly=True
        ),
        'rel_dossier_id': fields.many2one(
            'protocollo.dossier',
            'Fascicolo Correlato',
            ),
        'parent_id': fields.many2one(
            'protocollo.dossier',
            'Fascicolo di Riferimento',
            readonly=True,
            domain=[('dossier_type', 'in', ('fascicolo', 'sottofascicolo'))],
            states={'draft':
                    [('readonly', False)],
                    'open':
                    [('readonly', False)],
                    }
        ),
        'child_ids': fields.one2many(
            'protocollo.dossier',
            'parent_id',
            'Sottofascicoli',
            readonly=True,
        ),
        'sottofascicolo_ids': fields.one2many('protocollo.dossier',
                                              'parent_id',
                                              'Sottofascicoli',
                                              domain=[('dossier_type', '=', 'sottofascicolo')],
                                              readonly=True
        ),
        'inserto_ids': fields.one2many('protocollo.dossier',
                                       'parent_id',
                                       'Inserti',
                                       domain=[('dossier_type', '=', 'inserto')],
                                       readonly=True
        ),
        'parent_type': fields.function(
            _parent_type,
            string='Tipo Padre',
            type='selection',
            selection=DOSSIER_TYPE.items(),
            store=False,
        ),
        'partner_id': fields.many2one(
            'res.partner',
            'Anagrafica Correlata',
            readonly=True,
            states={'draft':
                    [('readonly', False)]
                    }
        ),
        'owner_partner_id': fields.many2one(
            'res.partner',
            'Amministrazione Titolare',
            required=False,
            readonly=True,
            states={'draft':
                    [('readonly', False)],
                    'open':
                    [('readonly', False)],
                    }
        ),
        'participant_partner_ids': fields.many2many(
            'res.partner',
            'dossier_participant_rel',
            'dossier_id', 'partner_id',
            'Amministrazioni Partecipanti',
            readonly=True,
            states={'draft':
                    [('readonly', False)],
                    'open':
                    [('readonly', False)],
                    }
        ),
        'office_comp_ids': fields.many2many(
            'hr.department',
            'dossier_office_comp_rel',
            'dossier_id', 'office_id',
            'Uffici Competenti',
            readonly=True,
            states={'draft':
                    [('readonly', False)],
                    'open':
                    [('readonly', False)],
                    }
            ),
        'office_view_ids': fields.many2many(
            'hr.department',
            'dossier_office_view_rel',
            'dossier_id', 'office_id',
            'Uffici Interessati',
            readonly=True,
            states={'draft':
                    [('readonly', False)],
                    'open':
                    [('readonly', False)],
                    }
            ),
        'employee_comp_ids': fields.many2many(
            'hr.employee',
            'dossier_employee_comp_rel',
            'dossier_id', 'employee_id',
            'Utenti Competenti',
            readonly=True,
            states={'draft':
                    [('readonly', False)],
                    'open':
                    [('readonly', False)],
                    }
            ),
        'employee_view_ids': fields.many2many(
            'hr.employee',
            'dossier_employee_view_rel',
            'dossier_id', 'employee_id',
            'Utenti Interessati',
            readonly=True,
            states={'draft':
                    [('readonly', False)],
                    'open':
                    [('readonly', False)],
                    }
            ),
        # Documents
        'document_ids': fields.many2many(
            'gedoc.document',
            'dossier_document_rel',
            'dossier_id', 'document_id',
            'Documenti Allegati al Fascicolo',
            readonly=True,
            states={'draft':
                    [('readonly', False)],
                    'open':
                    [('readonly', False)],
                    }
            ),
        'notes': fields.text('Note'),
        'state': fields.selection(
            [('draft', 'Bozza'),
             ('open', 'Aperto'),
             ('closed', 'Chiuso')],
            'Stato',
            readonly=True,
            help="Lo stato del fascicolo.",
            select=True,
            ),
        # TODO: verify congruence of the next fields.
        'paperless': fields.boolean(
            'Non contiene documenti cartacei',
            readonly=True,
            states={'draft':
                    [('readonly', False)],
                    }
            ),
        'address': fields.char(
            'Posizione',
            help="Indirizzo posizione fisica documenti cartacei"),
        'building': fields.char(
            'Edificio',
            help="Edificio di conservazione dei documenti cartacei"),
        'floor': fields.char(
            'Piano',
            help="Piano in cui si trovano i documenti cartacei"),
        'room': fields.char(
            'Stanza',
            help="Stanza in cui si trovano i documenti cartacei"),
    }

    _defaults = {
        'state': 'draft',
        'user_id': lambda obj, cr, uid, context: uid,
        'dossier_type': 'fascicolo'
    }

    # _sql_constraints = [
    #     ('dossier_name_unique',
    #      'unique (name)',
    #      'Elemento presente nel DB!'),
    #     ]

    def is_document_present(self, cr, uid, ids, *args):
        for dossier in self.browse(cr, uid, ids):
            if len(dossier.document_ids):
                return True
        return False

    def action_open(self, cr, uid, ids, *args):
        for dossier in self.browse(cr, uid, ids):
            # if dossier.parent_id:
            #     num = len(
            #         [d.id for d in dossier.parent_id.child_ids
            #          if d.state in ('open', 'closed')]
            #     ) + 1
            #     name = self.DOSSIER_TYPE[dossier.dossier_type] + \
            #         ' N.' + str(num) + ' del "' + \
            #         dossier.parent_id.name + '"'
            # else:
            #     num = len(
            #         [d.id for d in dossier.classification_id.dossier_ids
            #          if d.state in ('open', 'closed') and
            #          d.dossier_type == 'fascicolo']
            #     ) + 1
            #     name = self.DOSSIER_TYPE[dossier.dossier_type] + \
            #         ' N.' + str(num) + ' del \'' + \
            #         dossier.classification_id.name + '\''
            date_open = fields.datetime.now()
            year = date_open[:4]
            vals = {
                # 'name': name,
                'state': 'open',
                'date_open': date_open,
                'year': year
            }
            if dossier.dossier_type == 'fascicolo':
                vals['parent_id'] = False
            self.write(cr, uid, [dossier.id], vals)
        return True

    def action_close(self, cr, uid, ids, *args):
        vals = {
            'state': 'closed',
            'date_close': fields.datetime.now()
        }
        self.write(cr, uid, ids, vals)
        return True

    def create(self, cr, uid, vals, context=None):
        if vals and 'parent_id' in vals and vals['parent_id']:
            parent = self.browse(cr, uid, vals['parent_id'], context)
            vals['classification_id'] = parent.classification_id.id
        if vals and not ('name' in vals) and 'dossier_type' in vals and 'classification_id' in vals and 'parent_id' in vals and 'description' in vals:
            dossier_values = self.get_dossier_values(cr, uid, [], vals['dossier_type'], vals['classification_id'], vals['parent_id'], vals['description'], context)
            vals['name'] = dossier_values['name']
        return super(protocollo_dossier, self).create(cr, uid, vals, context=context)

    def write(self, cr, uid, ids, vals, context=None):
        if 'dossier_type' in vals and vals['dossier_type'] == 'fascicolo':
            vals['parent_id'] = False
        if vals and 'parent_id' in vals and vals['parent_id']:
            parent = self.browse(cr, uid, vals['parent_id'], context)
            vals['classification_id'] = parent.classification_id.id
        if vals and len(ids)==1 and not ('name' in vals) and ('dossier_type' in vals or 'classification_id' in vals or 'parent_id' in vals):
            dossier = self.browse(cr, uid, ids[0])
            dossier_type = vals['dossier_type'] if 'dossier_type' in vals else dossier.dossier_type
            classification_id = vals['classification_id'] if 'classification_id' in vals else dossier.classification_id.id
            parent_id = vals['parent_id'] if 'parent_id' in vals else dossier.parent_id.id
            description = vals['description'] if 'description' in vals else dossier.description
            dossier_values = self.get_dossier_values(cr, uid, ids, dossier_type, classification_id, parent_id, description, context)
            vals['name'] = dossier_values['name']
        return super(protocollo_dossier, self).write(cr, uid, ids, vals, context=context)

    def unlink(self, cr, uid, ids, context=None):
        stat = self.read(cr, uid, ids, ['state'], context=context)
        unlink_ids = []
        for t in stat:
            if t['state'] in ('draft'):
                unlink_ids.append(t['id'])
            else:
                raise osv.except_osv(_('Azione Non Valida!'),
                                     _('Solo i fascicoli in stato \
                                     bozza possono essere eliminati.')
                                     )
        osv.osv.unlink(self, cr, uid, unlink_ids, context=context)
        return super(protocollo_dossier, self).unlink(
            cr, uid, unlink_ids, context=context)

    def copy(self, cr, uid, fid, default=None, context=None):
        raise osv.except_osv(_('Azione Non Valida!'),
                             _('Impossibile duplicare un fascicolo')
                             )
        return True


class gedoc_model_type(osv.Model):
    _name = 'gedoc.model.type'

    _columns = {
        'name': fields.char(
            'Tipo Modello Documento',
            size=512,
            required=True
        ),
        'description': fields.char(
            'Descrizione Tipo Modello Documento',
            size=512,
            required=True
        ),
    }


class gedoc_document_type(osv.Model):
    _name = 'gedoc.document.type'

    _columns = {
        'name': fields.char(
            'Tipo Documento',
            size=512,
            required=True
        ),
        'tipologia_repertorio': fields.selection(
            [
                ('none', 'Non repertoriato'),
                ('manual', 'Numerazione Manuale'),
                ('automatic', 'Numerazione Automatica')
            ],
            'Tipologia Repertorio',
            size=32,
            required=True,
        ),
        'repertorio_sequence': fields.many2one('ir.sequence', 'Sequenza Numerazione', readonly=True)
    }

    def create(self, cr, uid, vals, context=None):
        document_type_id = super(gedoc_document_type, self).create(cr, uid, vals, context=context)
        if vals['tipologia_repertorio'] == 'automatic':
            document_type = self.browse(cr, uid, document_type_id)
            seq_id = self._create_repertorio_sequence(cr, uid, document_type.id, document_type.name)
            self.write(cr, uid, [document_type.id], {'repertorio_sequence': seq_id})
        return document_type_id

    def write(self, cr, uid, ids, vals, context=None):
        if vals.has_key('tipologia_repertorio') and vals['tipologia_repertorio'] == 'automatic':
            document_type = self.browse(cr, uid, ids[0])
            if not document_type.repertorio_sequence:
                seq_id = self._create_repertorio_sequence(cr, uid, document_type.id, document_type.name)
                vals['repertorio_sequence'] = seq_id
        document_type_id = super(gedoc_document_type, self).write(cr, uid, ids, vals, context=context)
        return document_type_id

    def _create_repertorio_sequence(self, cr, uid, document_type_id, document_type_name):
        sequence_type_obj = self.pool.get('ir.sequence.type')
        sequence_type_code = 'repertorio.sequence.' + str(document_type_id)
        sequence_type_obj.create(cr, SUPERUSER_ID, {
            'name': 'Sequence Repertorio ' + document_type_name,
            'code': sequence_type_code
        })
        sequence_obj = self.pool.get('ir.sequence')
        sequence_vals = {}
        sequence_vals['name'] = 'Repertorio - ' + document_type_name
        sequence_vals['code'] = sequence_type_code
        sequence_vals['active'] = True
        sequence_vals['suffix'] = '/%(year)s'
        sequence_vals['number_next'] = 1
        sequence_vals['number_increment'] = 1
        sequence_vals['padding'] = 0
        seq_id = sequence_obj.create(cr, SUPERUSER_ID, sequence_vals, context={})
        return seq_id

    def unlink(self, cr, uid, ids, context=None):
        rep = self.browse(cr, uid, ids, context=context)
        sequence_obj = self.pool.get('ir.sequence')
        sequence_type_obj = self.pool.get('ir.sequence.type')
        seq_id = rep.repertorio_sequence.id
        seq_code = rep.repertorio_sequence.code
        res = super(gedoc_document_type, self).unlink(cr, uid, ids, context=context)
        if res:
            seq_type = sequence_type_obj.search(cr, uid, [('code', '=', seq_code)])
            sequence_type_obj.unlink(cr, SUPERUSER_ID, seq_type)
            sequence_obj.unlink(cr, SUPERUSER_ID, seq_id)
        return True


class gedoc_document(osv.Model):
    _name = 'gedoc.document'

    _order = 'id desc'

    _columns = {
        'name': fields.char(
            'Documento',
            size=512,
            required=True
        ),
        'document_type': fields.many2one(
            'gedoc.document.type',
            'Tipologia Documento',
            required=False
        ),
        'repertorio': fields.selection(
                        [('none', 'Non repertoriato'),
                        ('manual', 'Numerazione Manuale'),
                        ('automatic', 'Numerazione Automatica')],
                        string='Tipologia Repertorio', readonly=True),
        'numero_repertorio': fields.char(
            'Numero Repertorio',
            size=256,
            required=False
        ),
        'subject': fields.text(
            'Oggetto',
            required=True,
        ),
        'main_doc_id': fields.many2one(
            'ir.attachment',
            'Documento Principale',
            required=False,
            readonly=True,
            domain="[('res_model','=',\
            'gedoc.document')]",
        ),
        'user_id': fields.many2one(
            'res.users',
            'Proprietario',
            readonly=True,
        ),
        'data_doc': fields.datetime(
            'Data Caricamento',
            readonly=True,
        ),
        'office_comp_ids': fields.many2many(
            'hr.department',
            'document_office_comp_rel',
            'document_id', 'office_id',
            'Uffici Competenti',
            ),
        'office_view_ids': fields.many2many(
            'hr.department',
            'document_office_view_rel',
            'document_id', 'office_id',
            'Uffici Interessati',
            ),
        'employee_comp_ids': fields.many2many(
            'hr.employee',
            'document_employee_comp_rel',
            'document_id', 'employee_id',
            'Utenti Competenti',
            ),
        'employee_view_ids': fields.many2many(
            'hr.employee',
            'document_employee_view_rel',
            'document_id', 'employee_id',
            'Utenti Interessati',
            ),
        'dossier_ids': fields.many2many(
            'protocollo.dossier',
            'dossier_document_rel',
            'document_id', 'dossier_id',
            'Fascicoli'),
        'attachment_ids': fields.one2many('ir.attachment','res_id', 'Allegati', readonly=True, domain=[('res_model','=','gedoc.document')]),

    }

    _defaults = {
        'name': '<Nuovo Documento>',
        'user_id': lambda obj, cr, uid, context: uid,
     }

    def _get_sequence_code(self, cr, uid, document_type_id):
        document_type_obj = self.pool.get('gedoc.document.type')
        try:
            document_type = document_type_obj.browse(cr, uid, document_type_id)
            seq_id = document_type.repertorio_sequence.id
            sequence_code = self.pool.get('ir.sequence').get_id(cr, uid, seq_id)
        except:
            raise osv.except_osv(_('Si è verificato un problema nella numerazione di repertorio!'),
                                 _('Si prega di riprovare'))
        return sequence_code

    def create(self, cr, uid, vals, context=None):
        if vals.has_key('document_type') and vals['document_type']:
            document_type_obj = self.pool.get('gedoc.document.type')
            document_type = document_type_obj.browse(cr, uid, vals['document_type'])
            if document_type.tipologia_repertorio == 'automatic':
                vals['numero_repertorio'] = self._get_sequence_code(cr,uid,vals['document_type'])
            vals['repertorio'] = document_type.tipologia_repertorio
        document_id = super(gedoc_document, self).create(cr, uid, vals, context=context)
        return document_id

    def on_change_document_type(self, cr, uid, ids, document_type_id, context=None):
        document_type_obj = self.pool.get('gedoc.document.type')
        document_type = document_type_obj.browse(cr, uid, document_type_id)
        values = {
            'repertorio': document_type.tipologia_repertorio
        }
        return {'value': values}


class DocumentSearch(osv.TransientModel):
    """
        Advanced Document Search
    """
    _name = 'gedoc.document.search'
    _description = 'Document Search'

    def _get_models(self, cr, uid, context=None):
        if context is None:
            context = {}
        model_obj = self.pool.get('gedoc.model.type')
        model_ids = model_obj.search(
            cr,
            uid,
            [],
            context=context
        )
        res = []
        for model in model_obj.browse(cr, uid, model_ids, context=context):
            res.append((model.name, model.description))
        return res

    _columns = {
        'name': fields.selection(
            _get_models,
            'Tipologia Documento',
            size=32,
            required=True,
            ),
        'text_name': fields.char(
            'Nome'
        ),
        'subject': fields.char(
            'Oggetto'
        ),
        'dossier_id': fields.many2one(
            'protocollo.dossier',
            'Fascicolo'
        ),
        'classification_id': fields.many2one(
            'protocollo.classification',
            'Titolario'
        ),
        'partner_id': fields.many2one(
            'res.partner',
            'Anagrafica'
        ),
        'user_id': fields.many2one(
            'res.users',
            'Responsabile / Proponente',
        ),
        'index_content': fields.char(
            'Contenuto nel Documento'
        ),
        'date_close_start': fields.datetime(
            'Inizio'
        ),
        'date_close_end': fields.datetime(
            'Fine'
        ),
        'office_id': fields.many2one(
            'hr.department',
            'Ufficio Competente'
        ),
        # Documents
        'document_type': fields.many2one(
            'gedoc.document.type',
            'Tipologia Documento',
        ),
     }

    def _search_action_document(
            self, cr, uid, wizard,
            search_domain, context=None):
        if wizard.name == 'gedoc.document':
            if wizard.text_name:
                search_domain.append(('name', 'ilike', wizard.text_name))
            if wizard.subject:
                search_domain.append(('subject', 'ilike', wizard.subject))
            if wizard.date_close_start:
                search_domain.append(
                    ('data_doc',
                     '>=',
                     wizard.date_close_start)
                    )
            if wizard.date_close_end:
                search_domain.append(
                    ('data_doc',
                     '<=',
                     wizard.date_close_end)
                    )
            if wizard.partner_id:
                search_domain.append(
                    ('partner_id', '=', wizard.partner_id))
            return search_domain
        else:
            return search_domain

    def search_action(self, cr, uid, ids, context=None):
        wizard = self.browse(cr, uid, ids[0], context)
        content_ids = []
        # First we search for index_content
        if wizard.index_content and len(wizard.index_content) > 2:
            query = """
                SELECT DISTINCT res_id
                FROM ir_attachment
                WHERE
                res_model=%s
                AND
                index_content ilike %s
                ORDER BY res_id ASC
            """
            cr.execute(query, (wizard.name, '%' + wizard.index_content + '%'))
            content_ids = map(lambda x: x[0], cr.fetchall())
        search_domain = []
        record_obj = self.pool.get(wizard.name)
        if wizard.dossier_id:
            search_domain.append(('dossier_ids', 'in', [wizard.dossier_id.id]))
        if wizard.user_id:
            search_domain.append(('user_id', '=', wizard.user_id))
        search_domain = self._search_action_document(
            cr, uid, wizard, search_domain, context)
        if search_domain:
            res_domain = record_obj.search(
                cr,
                uid,
                search_domain,
                context=context
                )
        else:
            res_domain = []
        if not isinstance(res_domain, list):
            res_domain = [res_domain]
        if content_ids:
            res_domain = list(set(content_ids) & set(res_domain))
        text_domain = "0"
        if res_domain:
            text_domain = ','.join(map(str, res_domain))
        return {
            'type': 'ir.actions.act_window',
            'name': 'Ricerca Avanzata ' + dict(
                self._get_models(cr, uid, context=context))[wizard.name],
            'view_type': 'form',
            'view_mode': 'tree,form',
            'domain': "[('id', 'in', (%s,))]" % text_domain,
            'res_model': wizard.name,
        }

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
