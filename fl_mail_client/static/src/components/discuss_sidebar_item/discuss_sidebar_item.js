/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { DiscussSidebarItem } from "@mail/components/discuss_sidebar_item/discuss_sidebar_item";

patch(DiscussSidebarItem.prototype, "fl_mail_client.DiscussSidebarItem", {
    /**
     * Gestisce il click sull'elemento DiscussSidebarItem.
     *
     * @private
     * @param {MouseEvent} ev
     */
    _onClick(ev) {
        // Il domain della ricerca deve essere resettato se uno dei due casi è vero:
        // Caso 1: Clicca su 'mail.box_mailreceived' e il thread corrente è diverso da 'mailreceived'
        // Caso 2: Clicca su 'mail.box_mailsent' e il thread corrente è diverso da 'mailsent'
        const caso1 = this.discuss.activeId === "mail.box_mailreceived" && this.thread.id !== "mailreceived";
        const caso2 = this.discuss.activeId === "mail.box_mailsent" && this.thread.id !== "mailsent";
        if (caso1 || caso2) {
            this.discuss.update({
                stringifiedDomain: "[]",
            });
        }
        // Imposta a 0 i contatori dei menù
        if (this.thread.id === "mailreceived") {
            this.env.messaging.received.update({ counter: 0 });
        }
        if (this.thread.id === "mailsent") {
            this.env.messaging.sent.update({ counter: 0 });
        }

        // Chiama il metodo originale
        super._onClick(ev);
    },
});
