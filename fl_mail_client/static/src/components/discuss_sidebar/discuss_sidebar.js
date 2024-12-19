/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { DiscussSidebar } from "@mail/components/discuss_sidebar/discuss_sidebar";

patch(DiscussSidebar.prototype, "fl_mail_client.DiscussSidebar", {
    /**
     * Return the list of maillist.
     *
     * @returns {mail.thread[]}
     */
    getMailListSidebarItems() {
        return this.env.models["mail.thread"].all((thread) =>
            thread.isPinned && thread.model === "mail.box" && thread.id.startsWith("mail")
        );
    },

    /**
     * Called when clicking on Mail compose menu item.
     *
     * @private
     * @param {MouseEvent} ev
     */
    _onClickMailCompose(ev) {
        ev.stopPropagation();
        this.env.bus.trigger("do-action", {
            action: "fl_mail_client.action_wizard_mail_compose_message_form",
            options: {
                additional_context: {
                    mail_compose_message: true,
                },
            },
        });
    },
});
