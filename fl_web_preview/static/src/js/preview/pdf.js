/** ********************************************************************************
    Copyright 2020-2022 Flosslab S.r.l.
    Copyright 2017-2019 MuK IT GmbH
    License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).
 **********************************************************************************/

/** @odoo-module **/

import { registry } from "@web/core/registry";
import AbstractPreviewContent from "@fl_web_preview/js/preview/content";

class PreviewContentPDF extends AbstractPreviewContent {
    static template = "fl_web_preview.PreviewContentPDF";

    setup() {
        super.setup();
        this.viewerUrl = `/web/static/lib/pdfjs/web/viewer.html?file=${encodeURIComponent(this.props.url)}`;
    }

    async renderPreviewContent() {
        return new Promise((resolve) => {
            const iframe = this.el.querySelector(".fl_web_preview_pdf iframe");
            if (iframe) {
                iframe.addEventListener("load", () => {
                    const iframeDocument = iframe.contentDocument || iframe.contentWindow.document;
                    const openFileButton = iframeDocument.querySelector("button#openFile");
                    if (openFileButton) {
                        openFileButton.style.display = "none";
                    }
                    resolve();
                });
            } else {
                resolve();
            }
        });
    }
}

PreviewContentPDF.downloadable = false;
PreviewContentPDF.printable = false;

// Register in the preview registry
const previewRegistry = registry.category("preview_widgets");
previewRegistry.add("pdf", PreviewContentPDF);
previewRegistry.add(".pdf", PreviewContentPDF);
previewRegistry.add("application/pdf", PreviewContentPDF);

export default PreviewContentPDF;
