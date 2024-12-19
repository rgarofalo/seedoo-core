/** ********************************************************************************
    Copyright 2020-2022 Flosslab S.r.l.
    Copyright 2017-2019 MuK IT GmbH
    License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).
 **********************************************************************************/

/** @odoo-module **/

import { registry } from "@web/core/registry";
import PreviewContentUnsupported from "@fl_web_preview/js/preview/unsupported";

const previewRegistry = registry.category("preview_widgets");

// Register default preview widget
previewRegistry.add("default", () => PreviewContentUnsupported);

export default previewRegistry;
