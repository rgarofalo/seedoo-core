/** @odoo-module **/

import { SearchPanel  } from "@web/search/search_panel/search_panel";
import { patch } from "@web/core/utils/patch";
import { rpc } from "@web/core/network/rpc";

/**
 * Estende il componente `SearchPanel` per aggiungere funzionalità personalizzate
 * relative ai valori di default nel pannello di ricerca.
 */
patch(SearchPanel.prototype, "sd_dms/static/src/js/views/search_panel.js", {
    /**
     * Metodo iniziale eseguito prima del caricamento del componente.
     * Qui vengono impostati i valori di default e aggiornati i valori attivi.
     */
    async willStart() {
        // Espandi i valori predefiniti e aggiorna i valori attivi
        this._expandDefaultValues();
        this._updateActiveValues();

        // Recupera i dati relativi al pannello di ricerca dal modello
        const sections = this.model.get("sections");

        // Ottieni l'UID dell'utente attualmente connesso
        const uid = this.env.services.user.uid;

        // Recupera la cartella predefinita dell'utente tramite un'RPC
        let defaultFolder = await rpc.query({
            model: "res.users",
            method: "get_default_folder_for_documents",
            args: [[uid]],
        });

        // Imposta il valore di default per la sezione `folder_id`
        for (const section of sections) {
            if (section.fieldName === "folder_id") {
                await this._toggleCategory(section, section.values.get(defaultFolder.folder_id));
            }
        }
    },

    _expandDefaultValues() {
        // Define the logic for expanding default values
    },

    _updateActiveValues() {
        // Define the logic for updating active values
    },
});


