/** ********************************************************************************
    Copyright 2020-2022 Flosslab S.r.l.
    Copyright 2017-2019 MuK IT GmbH
    License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).
 **********************************************************************************/

/** @odoo-module **/

// import { Modal } from "@web/core/modal/modal";
import PreviewManager from "@fl_web_preview/js/widgets/manager";

class PreviewDialog extends PreviewManager {
    static template = "fl_web_preview.PreviewDialog";

    setup() {
        super.setup();
        this.state = {
            isMaximized: false,
        };
    }

    // Lifecycle hooks
    async willStart() {
        await super.willStart();
    }

    async start() {
        await super.start();
        const modalElement = this.el.querySelector(".modal");
        if (modalElement) {
            modalElement.addEventListener("hidden.bs.modal", () => this._onDestroy());
        }
        this.activateTooltips();
    }

    destroy() {
        const modalElement = this.el.querySelector(".modal");
        if (modalElement) {
            modalElement.classList.remove("show");
            modalElement.remove();
        }
        super.destroy();
    }

    // Tooltip activation
    activateTooltips() {
        const tooltipElements = this.el.querySelectorAll("[data-toggle='tooltip']");
        tooltipElements.forEach((el) => new bootstrap.Tooltip(el, { delay: 0 }));
    }

    // Rendering logic
    _renderPreview() {
        super._renderPreview();
        const modalTitle = this.el.querySelector(".modal-title");
        if (modalTitle) {
            modalTitle.textContent = this.activeFile?.filename || "Preview";
        }
    }

    // Event handlers
    _onDestroy() {
        this.destroy();
    }

    _onMaximizeClick() {
        const dialogElement = this.el.querySelector(".fl_web_preview_dialog");
        if (dialogElement) {
            dialogElement.classList.add("fl_web_preview_maximize");
        }
    }

    _onMinimizeClick() {
        const dialogElement = this.el.querySelector(".fl_web_preview_dialog");
        if (dialogElement) {
            dialogElement.classList.remove("fl_web_preview_maximize");
        }
    }
}

PreviewDialog.events = {
    "click .fl_web_preview_maximize_btn": "_onMaximizeClick",
    "click .fl_web_preview_minimize_btn": "_onMinimizeClick",
};

export default PreviewDialog;
