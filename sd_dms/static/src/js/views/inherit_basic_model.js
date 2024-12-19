/** @odoo-module **/

import { BasicModel } from "@web/views/basic_model";

/**
 * Estensione del modello di base per supportare personalizzazioni specifiche
 * nel caricamento e nella gestione dei dati.
 */
class ExtendedBasicModel extends BasicModel {
    /**
     * Crea un record predefinito con un processo ottimizzato:
     * - Ottiene i valori predefiniti tramite la rotta `/default_get`
     * - Carica i dati relazionali
     * - Applica gli onchange, se necessario
     * - Carica nuovamente i dati relazionali
     *
     * Questo processo è ottimizzato, ma può essere ulteriormente refattorizzato.
     *
     * @private
     * @param {Object} params Parametri per la creazione del record
     * @param {string} modelName Nome del modello
     * @returns {Promise<string>} Risolve con l'ID della risorsa creata
     */
    async _makeDefaultRecord(modelName, params) {
        this._makeDefaultRecordField(params, "folder_id");
        return await super._makeDefaultRecord(modelName, params);
    }

    /**
     * Imposta il valore predefinito per un campo utilizzando il valore selezionato
     * nel pannello di ricerca.
     *
     * @private
     * @param {Object} params Parametri di contesto
     * @param {string} fieldName Nome del campo
     */
    _makeDefaultRecordField(params, fieldName) {
        const fieldNameDefault = `default_${fieldName}`;
        const fieldNameDefaultSearchPanel = `search_panel_default_${fieldName}`;
        const shouldUpdate = !params.context[fieldNameDefault] ||
            (params.context[fieldNameDefault] === params.context[fieldNameDefaultSearchPanel]);

        if (shouldUpdate) {
            const activeValueId = this._getSearchPanelActiveValueId(fieldName);
            params.context[fieldNameDefault] = activeValueId;
            params.context[fieldNameDefaultSearchPanel] = activeValueId;
        }
    }

    /**
     * Ottiene l'ID del valore attivo dal pannello di ricerca per un campo specifico.
     *
     * @private
     * @param {string} fieldName Nome del campo
     * @returns {number|null} ID del valore attivo o `null`
     */
    _getSearchPanelActiveValueId(fieldName) {
        const sections = this._getSections();
        if (!sections) return null;

        for (const section of sections) {
            const category = section[1];
            if (category.type === "category" && category.fieldName === fieldName) {
                return category.activeValueId;
            }
        }
        return null;
    }

    /**
     * Recupera le sezioni dal modello di ricerca.
     *
     * @private
     * @returns {Object|null} Sezioni del pannello di ricerca o `null`
     */
    _getSections() {
        const searchModel = this._getSearchModel();
        if (!searchModel) return null;

        for (const extension of searchModel.extensions) {
            if (extension.state?.sections) {
                return extension.state.sections;
            }
        }
        return searchModel.externalState?.SearchPanelModelExtensionLoadOnlyChildren?.sections || null;
    }

    /**
     * Ottiene il modello di ricerca associato.
     *
     * @private
     * @returns {Object|null} Modello di ricerca o `null`
     */
    _getSearchModel() {
        let searchModel = null;

        if (this.__parentedParent?.__parentedChildren) {
            searchModel = this._getParentedChildrenSearchModel(this.__parentedParent.__parentedChildren);
        }
        if (!searchModel && this.__parentedParent?.__parentedParent?.__parentedChildren) {
            searchModel = this._getParentedChildrenSearchModel(this.__parentedParent.__parentedParent.__parentedChildren);
        }
        return searchModel;
    }

    /**
     * Recupera il modello di ricerca dai figli parented.
     *
     * @private
     * @param {Array} parentedChildrenList Elenco dei figli parented
     * @returns {Object|null} Modello di ricerca o `null`
     */
    _getParentedChildrenSearchModel(parentedChildrenList) {
        for (const child of parentedChildrenList) {
            if (child.searchModel?.extensions) {
                return child.searchModel;
            }
        }
        return null;
    }

    /**
     * Effettua una chiamata `/search_read` per recuperare i dati di una risorsa lista.
     *
     * @param {Object} list Lista di risorse
     * @returns {Promise} Promessa risolta con i dati recuperati
     */
    async _searchReadUngroupedList(list) {
        const fieldNames = list.getFieldNames();
        const domain = list.domain || [];
        const context = { ...list.getContext(), bin_size: true };

        if (list.__data) {
            this._filterUnusedFields(list, fieldNames);
            return Promise.resolve(list.__data);
        } else {
            return this._rpc({
                route: "/web/dataset/search_read",
                model: list.model,
                fields: fieldNames,
                context,
                domain,
                limit: list.limit,
                offset: list.loadMoreOffset + list.offset,
                orderBy: list.orderedBy,
            });
        }
    }

    /**
     * Filtra i campi non utilizzati dai dati di una lista.
     *
     * @private
     * @param {Object} list Lista di risorse
     * @param {Array} fieldNames Nomi dei campi da mantenere
     */
    _filterUnusedFields(list, fieldNames) {
        const fieldNameSet = new Set(fieldNames);
        fieldNameSet.add("id");
        list.__data.records.forEach(record =>
            Object.keys(record)
                .filter(fieldName => !fieldNameSet.has(fieldName))
                .forEach(fieldName => delete record[fieldName])
        );
    }
}

// Registrazione del modello esteso
export default ExtendedBasicModel;
