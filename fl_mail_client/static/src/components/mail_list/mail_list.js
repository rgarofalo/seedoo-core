/** @odoo-module **/

import { Component, useRef, useState, onMounted } from "@odoo/owl";
import { debounce } from "@web/core/utils/timing";
import { useService } from "@web/core/utils/hooks";
import { Mail } from "../mail/mail";

export class MailList extends Component {
    static template = "fl_mail_client.MailList";
    static components = { Mail };

    static props = {
        order: { type: String, validate: (value) => ["asc", "desc"].includes(value) },
        selectedMailLocalId: { type: String, optional: true },
        threadViewLocalId: { type: String, required: true },
    };

    setup() {
        this.messaging = useService("messaging");
        this.state = useState({ order: this.props.order || "desc" });

        this.scrollRef = useRef("scrollContainer");
        this.loadMoreRef = useRef("loadMore");

        this.threadView = this.messaging.models["mail.thread_view"].get(this.props.threadViewLocalId);
        this._isLastScrollProgrammatic = false;

        this._onScrollThrottled = debounce(this._onScrollThrottled.bind(this), 100);

        onMounted(() => this._loadMails());
    }

    //--------------------------------------------------------------------------
    // Public
    //--------------------------------------------------------------------------

  
    mailRefFromId(mailId) {
        return this.mailRefs.find(ref => ref.mail.id === mailId);
    }

    /**
     * Restituisce un elenco ordinato di riferimenti ai componenti Mail, basato sull'ordine.
     *
     * Get list of sub-components Mail, ordered based on prop `order`
     * (ASC/DESC).
     *
     * The asynchronous nature of OWL rendering pipeline may reveal disparity
     * between knowledgeable state of store between components. Use this getter
     * with extreme caution!
     *
     * Let's illustrate the disparity with a small example:
     *
     * - Suppose this component is aware of ordered (record) mails with
     *   following IDs: [1, 2, 3, 4, 5], and each (sub-component) mails map
     * each of these records.
     * - Now let's assume a change in store that translate to ordered (record)
     *   mails with following IDs: [2, 3, 4, 5, 6].
     * - Because store changes trigger component re-rendering by their "depth"
     *   (i.e. from parents to children), this component may be aware of
     *   [2, 3, 4, 5, 6] but not yet sub-components, so that some (component)
     *   mails should be destroyed but aren't yet (the ref with mail ID 1)
     *   and some do not exist yet (no ref with mail ID 6).
     *
     * @returns {Array}
     */
    get mailRefs() {
        const refs = this.refs || {};
        const ascOrderedMailRefs = Object.values(refs)
            .filter((ref) => ref.mail) // Filtra solo i riferimenti con una mail valida
            .sort((ref1, ref2) => (ref1.mail.id < ref2.mail.id ? -1 : 1));

        if (this.state.order === "desc") {
            return ascOrderedMailRefs.reverse();
        }
        return ascOrderedMailRefs;
    }

    get orderedMails() {
         /**
         * La condizione è stata messa per evitare che venga generato un errore js nel seguente flusso:
         * - l'utente è nella vista "Comunicazioni"
         * - attiva uno qualsiasi dei filtri di ricerca
         * - crea la bozza di un protocollo partendo da una mail
         * - elimina la bozza di protocollo create
         * - ritorna nella vista "Comunicazioni" passando per il menù delle App e non dal breadcrumb
         * TODO: il fix in questione è un workaround momentaneo per evitare il blocco della vista
         */
        const mails = this.threadView?.mailCache?.orderedMails || [];
        return this.state.order === "desc" ? [...mails].reverse() : mails;
    }

    setScrollTop(value) {
        const scrollEl = this.scrollRef.el;
        if (scrollEl && scrollEl.scrollTop !== value) {
            this._isLastScrollProgrammatic = true;
            scrollEl.scrollTop = value;
        }
    }

    get threadView() {
        return this.messaging.models["mail.thread_view"].get(this.props.threadViewLocalId);
    }   

    getDateDay(mail) {
        let mailDate = mail.create_date;
        if (mail.direction === "in" && mail.server_received_datetime) {
            mailDate = mail.server_received_datetime;
        } else if (mail.direction === "out" && mail.sent_datetime) {
            mailDate = mail.sent_datetime;
        }

        const today = moment().format("YYYY-MM-DD");
        const yesterday = moment().subtract(1, "days").format("YYYY-MM-DD");

        if (mailDate.format("YYYY-MM-DD") === today) return this.env._t("Today");
        if (mailDate.format("YYYY-MM-DD") === yesterday) return this.env._t("Yesterday");
        return mailDate.format("LL");
    }

    onScroll() {
        this._onScrollThrottled();
    }
    

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    _loadMails() {
        if (this.threadView?.mailCache) {
            this.state.mails = [...this.threadView.mailCache.orderedMails];
        }
    }

    _loadMore() {
        this.threadView?.mailCache?.loadMoreMails();
    }

    _isLoadMoreVisible() {
        const loadMoreEl = this.loadMoreRef.el;
        const scrollEl = this.scrollRef.el;
        if (!loadMoreEl || !scrollEl) return false;

        const loadMoreRect = loadMoreEl.getBoundingClientRect();
        const scrollRect = scrollEl.getBoundingClientRect();
        return loadMoreRect.top < scrollRect.bottom;
    }

    _onScrollThrottled() {
        if (this._isLoadMoreVisible()) {
            this._loadMore();
        }
    }

    _checkMostRecentMailIsVisible() {
        const mailCache = this.threadView?.mailCache;
        if (mailCache) {
            const mostRecentMailRef = this.refs?.mostRecentMailRef;
            if (mostRecentMailRef?.isPartiallyVisible()) {
                this.threadView.handleVisibleMail(mostRecentMailRef.mail);
            }
        }
    }

    _getScrollableElement() {
        return this.props.getScrollableElement ? this.props.getScrollableElement() : this.scrollRef.el;
    }
    
}
