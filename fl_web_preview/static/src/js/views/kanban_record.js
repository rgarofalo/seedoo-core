/** ********************************************************************************
    Copyright 2020-2022 Flosslab S.r.l.
    Copyright 2017-2019 MuK IT GmbH
    License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).
 **********************************************************************************/

import { Component, useState } from '@odoo/owl';
import { useService } from '@web/core/utils/hooks';
import { KanbanRecord } from '@web/views/kanban/kanban_record';
import { PreviewDialog } from '@fl_web_preview/js/widgets/dialog';
import { formatDateTime } from '@web/core/l10n/dates';

class FlWebPreviewKanbanRecord extends KanbanRecord {
    setup() {
        super.setup();
        this.orm = useService('orm');
        this.dialogService = useService('dialog');
    }

    async _onImageClicked(event) {
        event.stopPropagation();
        event.preventDefault();

        const filenameFieldname = 'filename' in this.props.record.fields ? 'filename' : 'name';
        const contentFieldname = 'content' in this.props.record.fields ? 'content' : 'datas';
        const lastUpdate = this.props.record.data.__last_update;
        const mimetype = this.props.record.data.mimetype || null;
        const filename = this.props.record.data[filenameFieldname] || null;
        const unique = lastUpdate ? formatDateTime(lastUpdate).replace(/[^0-9]/g, '') : null;

        const binaryUrl = this.orm.url('/web/content', {
            model: this.props.record.model,
            id: JSON.stringify(this.props.record.data.id),
            data: null,
            unique: unique,
            filename_field: filenameFieldname,
            filename: filename,
            field: contentFieldname,
            download: true,
        });

        const preview = new PreviewDialog(this, [{
            url: binaryUrl,
            filename: filename,
            mimetype: mimetype,
        }], 0);

        this.dialogService.add(preview);
    }
}

FlWebPreviewKanbanRecord.template = 'fl_web_preview.KanbanRecord';
FlWebPreviewKanbanRecord.components = { PreviewDialog };

export default FlWebPreviewKanbanRecord;