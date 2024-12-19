/** ********************************************************************************
    Copyright 2020-2022 Flosslab S.r.l.
    Copyright 2017-2019 MuK IT GmbH
    License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).
**********************************************************************************/

import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Dialog } from "@web/core/dialog/dialog";

class FieldBinaryPreview extends Component {
    setup() {
        this.orm = useService("orm");
        this.dialogService = useService("dialog");
        this.fileService = useService("file");
        this.filename = this.props.record.data[this.props.attrs.filename];
        this.mimetype = this.props.record.data.mimetype;
        this.lastUpdate = this.props.record.data.__last_update;
    }

    getBinaryUrl() {
        const unique = this.lastUpdate?.replace(/[^0-9]/g, '') || null;
        return this.fileService.url('/web/content', {
            model: this.props.record.resModel,
            id: JSON.stringify(this.props.record.resId),
            field: this.props.name,
            filename_field: this.props.attrs.filename,
            filename: this.filename,
            unique,
            download: true,
        });
    }

    onPreviewClick(ev) {
        ev.preventDefault();
        const binaryUrl = this.getBinaryUrl();
        if (binaryUrl) {
            const previewDialog = new Dialog(this, {
                title: this.env._t("Preview"),
                body: `<iframe src="${binaryUrl}" style="width: 100%; height: 80vh; border: none;"></iframe>`,
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
        const $previewButton = document.createElement("button");
        $previewButton.className = "btn btn-primary fl_field_preview_button";
        $previewButton.innerHTML = '<i class="fa fa-file-text-o"></i>';
        $previewButton.onclick = (ev) => this.onPreviewClick(ev);
        this.el.prepend($previewButton);
    }

    render() {
        if (this.props.readonly) {
            this.renderReadonly();
        }
    }
}

FieldBinaryPreview.template = "fl_web_preview.FieldBinaryPreview";
registry.category("fields").add("binary_preview", {component: FieldBinaryPreview});

export default FieldBinaryPreview;
