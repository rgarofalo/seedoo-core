/** @odoo-module **/

import { Component, useState, useRef, onWillUpdateProps, useEffect } from "@odoo/owl";
import { getLangDatetimeFormat } from "@web/core/l10n/dates";
import { useStore } from "@mail/core/hooks/use_store";
import { useUpdate } from "@mail/core/hooks/use_update";
import { AttachmentList } from "@mail/components/attachment_list/attachment_list";

export class Mail extends Component {
    static template = "fl_mail_client.Mail";
    static components = { AttachmentList };

    static props = {
        mailLocalId: { type: String, required: true },
        threadViewLocalId: { type: String, optional: true },
    };

    setup() {
        this.state = useState({ isClicked: false });
        this._prettyBodyRef = useRef("prettyBody");
        this._lastPrettyBody = null;

        this.store = useStore((props) => {
            const mail = this.env.models["fl_mail_client.mail"].get(props.mailLocalId);
            const threadView = this.env.models["mail.thread_view"].get(props.threadViewLocalId);
            return {
                mail: mail?.__state,
                author: mail?.author,
                attachments: mail?.attachments.map((att) => att.__state) || [],
                thread: threadView?.thread,
            };
        });

        useUpdate(() => this._update());
    }

    get mail() {
        return this.env.models["fl_mail_client.mail"].get(this.props.mailLocalId);
    }

    get serverReceivedDatetimeFormatted() {
        return this.mail?.server_received_datetime.format(getLangDatetimeFormat());
    }

    get sentDatetimeFormatted() {
        return this.mail?.sent_datetime.format(getLangDatetimeFormat());
    }

    get stateOutList() {
        return [
            ["outgoing", this.env._t("Outgoing")],
            ["sent", this.env._t("Sent")],
            ["accepted", this.env._t("Accepted")],
            ["received", this.env._t("Received")],
            ["exception", this.env._t("Delivery Failed")],
            ["cancel", this.env._t("Cancelled")],
        ];
    }

    _update() {
        if (!this.mail || !this._prettyBodyRef.el) return;
        if (this._lastPrettyBody !== this.mail.prettyBody) {
            this._prettyBodyRef.el.innerHTML = this.mail.prettyBody;
            this._lastPrettyBody = this.mail.prettyBody;
        }
    }

    onClick() {
        this.el.querySelector(".o_Message_footer")?.classList.toggle("not_visible");
        document.querySelectorAll(".nav-pills a").forEach((tab) => {
            tab.addEventListener("click", (event) => {
                document.querySelectorAll(".tab-content > .tab-pane").forEach((pane) => {
                    pane.classList.remove("active");
                });
                const linkTab = tab.getAttribute("aria-controls");
                document.querySelector(`.tab-content > ${linkTab}`).classList.add("active");
            });
        });
    }
}
