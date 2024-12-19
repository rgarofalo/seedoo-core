/** @odoo-module **/

import { Component } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

/**
 *  I widget di upgrade sono destinati all'uso nelle impostazioni di configurazione.
 *  Quando selezionati, mostrano un popup di upgrade all'utente.
 */

class AbstractFieldUpgrade extends Component {
    setup() {
        this.orm = useService("orm");
        this.dialogService = useService("dialog");
    }

    /**
     * Reindirizza l'utente alla pagina di upgrade.
     *
     * @private
     * @returns {void}
     */
    _confirmUpgrade() {
        window.open("https://www.flosslab.com/", "_blank");
    }

    /**
     * Funzione pensata per essere sovrascritta per inserire
     * il nodo jQuery dell'etichetta "Enterprise" nel posto corretto.
     *
     * @abstract
     * @private
     * @param {jQuery} $enterpriseLabel Etichetta "Enterprise" da inserire
     */
    _insertEnterpriseLabel($enterpriseLabel) {
        // Implementazione specifica lasciata alle classi derivate
    }

    /**
     * Apre il dialog di upgrade.
     *
     * @private
     * @returns {Dialog} Istanza del Dialog aperto
     */
    _openDialog() {
        const message = `<div><p>${this.env._t("Per continuare, passa alla versione Enterprise.")}</p></div>`;

        const buttons = [
            {
                text: this.env._t("Vai al sito"),
                classes: "btn-primary",
                close: true,
                click: this._confirmUpgrade.bind(this),
            },
            {
                text: this.env._t("Annulla"),
                close: true,
            },
        ];

        return this.dialogService.add({
            title: this.env._t("Versione Enterprise"),
            body: message,
            buttons,
        });
    }
}

/**
 * Widget personalizzato Boolean con funzionalità di upgrade.
 */
class FLUpgradeBoolean extends AbstractFieldUpgrade {
    setup() {
        super.setup();
        this.state = useState({ value: false });
    }

    /**
     * Gestisce il clic sull'input Boolean.
     *
     * @param {Event} event
     * @private
     */
    async _onInputClicked(event) {
        this.state.value = !this.state.value;

        const result = await this.orm.call("ir.module.module", "show_dialog_on_checkbox_click", [[this.props.name]]);
        if (this.state.value && result === true) {
            this._openDialog().on("closed", this._resetValue.bind(this));
        }
    }

    /**
     * Reimposta il valore del campo.
     *
     * @private
     */
    _resetValue() {
        this.state.value = false;
    }

    /**
     * Esegue il rendering del widget con l'etichetta.
     *
     * @param {HTMLElement} label
     */
    renderWithLabel(label) {
        this.el.innerHTML = "";
        this.el.appendChild(label);
    }

    render() {
        this.el.innerHTML = `
            <div>
                <input type="checkbox" ${this.state.value ? "checked" : ""} />
                <label>${this.props.label || "Upgrade"}</label>
            </div>
        `;

        this.el.querySelector("input").addEventListener("click", (ev) => this._onInputClicked(ev));
    }
}

// Registrazione del widget nel registro dei campi
registry.category("fields").add("fl_upgrade_boolean", {component: FLUpgradeBoolean});

export { FLUpgradeBoolean };
