/** ********************************************************************************
    Copyright 2020-2022 Flosslab S.r.l.
    Copyright 2017-2019 MuK IT GmbH
    License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).
 **********************************************************************************/

/** @odoo-module **/

import AbstractPreviewContent from "@fl_web_preview/js/preview/content";

class PreviewContentUnsupported extends AbstractPreviewContent {
    static template = "fl_web_preview.PreviewContentUnsupported";
}

PreviewContentUnsupported.downloadable = false;
PreviewContentUnsupported.printable = false;

export default PreviewContentUnsupported;
