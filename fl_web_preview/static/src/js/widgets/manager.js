/** ********************************************************************************
    Copyright 2020-2022 Flosslab S.r.l.
    Copyright 2017-2019 MuK IT GmbH
    License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).
 **********************************************************************************/

/** @odoo-module **/

import { Component,useState } from "@odoo/owl";
import { _t, qweb as QWeb } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
// import utils from "fl_web_preview.utils";
// import framework from "@web/core/framework";
import { range } from "@web/core/utils/functions";


class PreviewManager extends Component {
    static template = "fl_web_preview.PreviewManager";

    setup() {
        this.state = useState({
            files: this.props.files || [],
            index: this.props.index || 0,
            activeFile: this.props.files[this.props.index] || {},
            activePreview: null,
        });
        this.pagerSize = 9;
    }

    async willStart() {
        await this._loadLibraries(["/fl_web_preview/static/lib/printThis/printThis.js"]);
    }

    async start() {
        this.$actions = this.el.querySelector(".fl_web_preview_actions");
        this.$wrapper = this.el.querySelector(".fl_web_preview_wrapper");
        this.$pager = this.el.querySelector(".fl_web_preview_pager");
        this.renderManager();
    }

    async _loadLibraries(libraries) {
        for (const lib of libraries) {
            await import(lib);
        }
    }

    renderManager() {
        this.renderPreviewWithLoading();
        this.renderIndexPager();
        this.updateActions();
    }

    renderPreviewWithLoading() {
        const loader = this.renderLoader();
        this.destroyPreview();
        this.renderPreview(loader);
    }

    renderLoader() {
        const loaderHTML = QWeb.render("fl_web_preview.PreviewLoader", {
            loading_text: _t("Loading ..."),
            loading_text_00: _t("Loading"),
            loading_text_25: _t("Loading ."),
            loading_text_50: _t("Loading .."),
            loading_text_75: _t("Loading ..."),
        });
        this.$wrapper.innerHTML = loaderHTML;
        return this.$wrapper.querySelector(".loading-container");
    }

    renderPreview(element) {
        const { mimetype, filename, url } = this.state.activeFile;
        let PreviewWidget = registry.get(mimetype) || registry.get(filename?.split(".").pop()) || registry.defaultPreview();

        this.state.activePreview = new PreviewWidget({
            props: { url, mimetype, filename },
        });
        this.state.activePreview.mount(element);
    }

    renderIndexPager() {
        const pager = this.$pager.querySelector(".pagination");
        pager.innerHTML = "";

        if (this.state.files.length <= 1) {
            this.$pager.style.display = "none";
            return;
        }

        const createPageItem = (classes, html, index = null) => {
            const li = document.createElement("li");
            li.className = `page-item ${classes}`;
            const a = document.createElement("a");
            a.className = "page-link";
            a.innerHTML = html;
            if (index !== null) a.dataset.index = index;
            li.appendChild(a);
            return li;
        };

        const previous = createPageItem("fl_web_preview_previous", '<i class="fa fa-angle-double-left"></i>');
        const next = createPageItem("fl_web_preview_next", '<i class="fa fa-angle-double-right"></i>');

        pager.appendChild(previous);

        const pageList = this.partitionPageList(this.state.files.length, this.state.index + 1, this.pagerSize);
        pageList.forEach((page, i) => {
            const pageItem = page
                ? createPageItem(i === this.state.index ? "active" : "fl_web_preview_page", page, page - 1)
                : createPageItem("disabled", "...");
            pager.appendChild(pageItem);
        });

        pager.appendChild(next);
        this.$pager.style.display = "block";
    }

    updateActions() {
        this.$actions.innerHTML = "";
        const preview = this.state.activePreview;
        if (preview) {
            if (preview.downloadable) {
                this.addActionButton("fa-download", _t("Download"), preview.props.url);
            }
            if (preview.printable) {
                this.addActionButton("fa-print", _t("Print"), "#", this.onPrintClick.bind(this));
            }
        }
    }

    addActionButton(icon, title, href, callback = null) {
        const a = document.createElement("a");
        a.className = `fl_web_preview_${icon}`;
        a.title = title;
        a.href = href;
        a.innerHTML = `<i class="fa ${icon}"></i>`;
        if (callback) a.addEventListener("click", callback);
        this.$actions.appendChild(a);
    }

    destroyPreview() {
        if (this.state.activePreview) {
            this.state.activePreview.unmount();
        }
        this.state.activePreview = null;
    }

    onPreviousClick() {
        if (this.state.index > 0) {
            this.state.index -= 1;
            this.state.activeFile = this.state.files[this.state.index];
            this.renderManager();
        }
    }

    onNextClick() {
        if (this.state.index < this.state.files.length - 1) {
            this.state.index += 1;
            this.state.activeFile = this.state.files[this.state.index];
            this.renderManager();
        }
    }

    onPageClick(event) {
        const index = parseInt(event.target.dataset.index, 10);
        if (!isNaN(index) && index >= 0 && index < this.state.files.length) {
            this.state.index = index;
            this.state.activeFile = this.state.files[this.state.index];
            this.renderManager();
        }
    }

    onPrintClick() {
        const preview = this.state.activePreview;
        const delay = preview?.printDelay || 950;
        framework.blockUI();
        setTimeout(() => {
            framework.unblockUI();
        }, delay);
        $(this.$wrapper).printThis({
            importCSS: true,
            importStyle: true,
            printDelay: delay,
        });
    }


    partitionPageList(pages, page, size) {
        if (!size || size < 5) {
            throw new Error("The size must be at least 5 to partition the list.");
        }
        const sideSize = size < 9 ? 1 : 2;
        const leftSize = Math.floor((size - sideSize * 2 - 3) / 2);
        const rightSize = Math.floor((size - sideSize * 2 - 2) / 2);
        
        if (pages <= size) {
            return this.closedRange(1, pages);
        }
        if (page <= size - sideSize - 1 - rightSize) {
            return [
                ...closedRange(1, size - sideSize - 1),
                false,
                ...closedRange(pages - sideSize + 1, pages),
            ];
        }
        if (page >= pages - sideSize - 1 - rightSize) {
            return [
                ...closedRange(1, sideSize),
                false,
                ...closedRange(pages - sideSize - 1 - rightSize - leftSize, pages),
            ];
        }
        return [
            ...closedRange(1, sideSize),
            false,
            ...closedRange(page - leftSize, page + rightSize),
            false,
            ...closedRange(pages - sideSize + 1, pages),
        ];
    }

    closedRange(start, end) {
        return range(start, end + 1);
    }
    
}

PreviewManager.props = {
    files: Array,
    index: Number,
};

PreviewManager.events = {
    "click .fl_web_preview_previous a": "onPreviousClick",
    "click .fl_web_preview_next a": "onNextClick",
    "click .fl_web_preview_page a": "onPageClick",
    "click .fl_web_preview_print": "onPrintClick",
};

export default PreviewManager;
