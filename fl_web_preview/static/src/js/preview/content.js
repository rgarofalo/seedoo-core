/** ********************************************************************************
    Copyright 2020-2022 Flosslab S.r.l.
    Copyright 2017-2019 MuK IT GmbH
    License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).
 **********************************************************************************/

/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
// import ajax from "web.ajax";
// import { jsonrpc } from "@web/core/network/rpc_service";
// import { useState } from "@odoo/owl/hooks";
import { _t } from "@web/core/l10n/translation";

class AbstractPreviewContent extends Component {
    // Props
    static props = {
        url: { type: String },
        mimetype: { type: String, default: "application/octet-stream" },
        filename: { type: String, default: "Unknown" },
    };

    // State
    setup() {
        this.state = useState({
            printable: false,
            downloadable: false,
        });
    }

    // Lifecycle Hooks
    async willStart() {
        const assets_backend = this.env.services['web.assets_backend'];

        await assets_backend.loadLibs(this);
    }

    async start() {
        await this.renderPreviewContent();
    }

    async renderPreviewContent() {
        // Placeholder for extending classes
    }

    contentActions() {
        return [];
    }
}

export default AbstractPreviewContent;
