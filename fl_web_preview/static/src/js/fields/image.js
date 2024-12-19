/** ********************************************************************************
    Copyright 2020-2022 Flosslab S.r.l.
    Copyright 2017-2019 MuK IT GmbH
    License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).
**********************************************************************************/

import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Dialog } from "@web/core/dialog/dialog";

class FieldBinaryImagePreview extends Component {
    setup() {
        this.orm = useService("orm");
        this.dialogService = useService("dialog");
        this.fileService = useService("file");
        this.lastUpdate = this.props.record.data.__last_update;
    }

    getBinaryUrl() {
        const unique = this.lastUpdate?.replace(/[^0-9]/g, '') || null;
        return this.fileService.url('/web/content', {
            model: this.props.record.resModel,
            id: JSON.stringify(this.props.record.resId),
            field: this.props.name,
            unique,
            download: true,
        });
    }

    onImageClick(ev) {
        ev.preventDefault();
        if (this.props.attrs.no_preview) return;

        const binaryUrl = this.getBinaryUrl();
        if (binaryUrl) {
            const previewDialog = new Dialog(this, {
                title: this.env._t("Image Preview"),
                body: `<img src="${binaryUrl}" style="max-width: 100%; max-height: 80vh;" alt="Preview"/>`,
                buttons: [
                    {
                        text: this.env._t("Close"),
                        classes: "btn-primary",
                        close: true,
                    },
                ],
            });
            this.dialogService.add(previewDialog);
        }
    }

    renderReadonly() {
        const $imageWrapper = document.createElement("div");
        $imageWrapper.className = "fl_field_image_wrapper";
        if (this.props.attrs.no_preview) {
            $imageWrapper.classList.add("fl_no_preview");
        }

        const $image = document.createElement("img");
        $image.src = this.getBinaryUrl();
        $image.alt = this.props.name;
        $image.onclick = (ev) => this.onImageClick(ev);

        $imageWrapper.appendChild($image);
        this.el.appendChild($imageWrapper);
    }

    render() {
        if (this.props.readonly) {
            this.renderReadonly();
        }
    }
}

FieldBinaryImagePreview.template = "fl_web_preview.FieldBinaryImagePreview";
registry.category("fields").add("binary_image_preview", {component: FieldBinaryImagePreview});

export default FieldBinaryImagePreview;
