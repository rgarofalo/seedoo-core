
from openerp import api, models
from openerp.osv import fields
from openerp.exceptions import ValidationError, except_orm
from openerp.tools.translate import _

class TileTile(models.Model):

    _inherit = 'tile.tile'

    def _remove_tile_from_ids(self, cr, uid, ids, module, data_xml_id):
        tile_to_remove = self.pool.get('ir.model.data').get_object_reference(cr, uid, module, data_xml_id)
        if tile_to_remove and tile_to_remove[1] in ids:
            ids.remove(tile_to_remove[1])

    def _compute_configuration_active(self, cr, uid, ids, name, arg, context=None):
        {}

    def _search_configuration_active(self, cr, uid, obj, name, args, domain=None, context=None):
        if args:
            for domain_condition in args:
                if domain_condition[1] != '=':
                    raise except_orm(_('Unimplemented Feature. Search on Active field disabled.'))

        ids = []
        cr.execute("""
                SELECT tt.id
                FROM tile_tile tt
        """)
        for result in cr.fetchall():
            ids.append(result[0])

        configurazione_ids = self.pool.get('protocollo.configurazione').search(cr, uid, [])
        configurazione = self.pool.get('protocollo.configurazione').browse(cr, uid, configurazione_ids[0])
        if not configurazione.non_classificati_active:
            self._remove_tile_from_ids(cr, uid, ids, 'seedoo_protocollo', 'tile_protocollo_non_classificati')
        if not configurazione.non_fascicolati_active:
            self._remove_tile_from_ids(cr, uid, ids, 'seedoo_protocollo', 'tile_protocollo_non_fascicolati')
        if not configurazione.assegnato_a_me_active:
            self._remove_tile_from_ids(cr, uid, ids, 'seedoo_protocollo', 'tile_protocollo_totali_assegnati_a_me')
        if not configurazione.assegnato_a_mio_ufficio_active:
            self._remove_tile_from_ids(cr, uid, ids, 'seedoo_protocollo', 'tile_protocollo_totali_assegnati_mio_ufficio')
        if not configurazione.assegnato_a_me_competenza_active:
            self._remove_tile_from_ids(cr, uid, ids, 'seedoo_protocollo', 'tile_protocollo_totali_assegnati_a_me_comp')
        if not configurazione.assegnato_a_me_active:
            self._remove_tile_from_ids(cr, uid, ids, 'seedoo_protocollo', 'tile_protocollo_totali_assegnati_a_me')
        if not configurazione.assegnato_a_mio_ufficio_competenza_active:
            self._remove_tile_from_ids(cr, uid, ids, 'seedoo_protocollo', 'tile_protocollo_totali_assegnati_mio_ufficio_comp')
        if not configurazione.assegnato_cc_active:
            self._remove_tile_from_ids(cr, uid, ids, 'seedoo_protocollo', 'tile_protocollo_totali_assegnati_cc')
        if not configurazione.assegnato_da_me_active:
            self._remove_tile_from_ids(cr, uid, ids, 'seedoo_protocollo', 'tile_protocollo_totali_assegnati_da_me_assegnato')
        if not configurazione.da_assegnare_active:
            self._remove_tile_from_ids(cr, uid, ids, 'seedoo_protocollo', 'tile_protocollo_tatali_da_assegnare')

        return [('id', 'in', ids)]

    # Action methods
    @api.multi
    def open_link(self):
        res = super(TileTile, self).open_link()
        if self.action_id and len(self.action_id.view_ids) == 2:
            res["views"] = [(self.action_id.view_ids[0].view_id.id, 'tree'), (self.action_id.view_ids[1].view_id.id, 'form')]
        if self.action_id and self.action_id.search_view_id:
            res["search_view_id"] = [self.action_id.search_view_id.id]
        return res

    TAG_SELECTION = [
        ('generale', 'Generale'),
        ('totale', 'Totale'),
        ('ingresso', 'Ingresso'),
        ('uscita', 'Uscita'),
        ('ingresso_assegnazioni', 'Assegnazioni / Ingresso'),
        ('uscita_assegnazioni', 'Assegnazioni / Uscita'),
    ]

    _columns = {
        'sequence_tile': fields.integer('Ordine', required=True),
        'icon_tile': fields.char('Classe icona', required=True),
        'tag_tile': fields.selection(
            TAG_SELECTION,
            'Tag Board',
            help="Indicare il tag",
            select=True,
        ),
        'configuration_active': fields.function(_compute_configuration_active,
                                                fnct_search=_search_configuration_active,
                                                type='boolean',
                                                string='Visibile'),
    }

    _order = 'sequence_tile'

    _defaults = {
        'icon_tile': 'fa-envelope-o',
        'tag_tile': 'generale',
    }
