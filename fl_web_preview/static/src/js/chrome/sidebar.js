/** ********************************************************************************
	Copyright 2020-2022 Flosslab S.r.l.
	Copyright 2017-2019 MuK IT GmbH
	License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).
 **********************************************************************************/

import { Component, useState, useRef } from '@odoo/owl';
import { useService } from '@web/core/utils/hooks';
import { Context } from '@web/core/context';
import { PreviewManager } from '@fl_web_preview/js/widgets/manager';
import { PreviewDialog } from '@fl_web_preview/js/widgets/dialog';

class Sidebar extends Component {
	setup() {
		this.state = useState({
			items: this.props.items,
		});
		this.rpc = useService('rpc');
		this.actionService = useService('action');
		this.tooltipRef = useRef('tooltip');
	}

	onReportPreview(event) {
		this.tooltipRef.el.tooltip({ delay: 0 });
		const index = event.currentTarget.dataset.index;
		const item = this.state.items.print[index];
		if (item.action) {
			this.trigger('sidebar_data_asked', {
				callback: async (env) => {
					const contextValues = {
						active_id: env.activeIds[0],
						active_ids: env.activeIds,
						active_model: env.model,
						active_domain: env.domain || [],
					};
					const context = new Context(env.context, contextValues);
					const result = await this.rpc('/web/action/load', {
						action_id: item.action.id,
						context: context,
					});
					result.context = new Context(result.context || {}, contextValues).set_eval_context(context);
					result.flags = result.flags || {};
					result.flags.new_window = true;
					if (result.report_type === 'qweb-pdf') {
						const state = await this.call('report', 'checkWkhtmltopdf');
						if (state === 'upgrade' || state === 'ok') {
							result.context = new Context(result.context).eval();
							this.callReportPreview(result, item.label, 'pdf', 'application/pdf');
						} else {
							this.callReportAction(result);
						}
					} else if (result.report_type === 'qweb-text') {
						result.context = new Context(result.context).eval();
						this.callReportPreview(result, item.label, 'text', 'text/plain');
					} else {
						this.callReportAction(result);
					}
				},
			});
		}
		event.stopPropagation();
		event.preventDefault();
	}

	callReportAction(action) {
		this.actionService.doAction(action, {
			on_close: () => {
				this.trigger('reload');
			},
		});
	}

	callReportPreview(action, label, type, mimetype) {
		const reportUrls = {
			pdf: `/report/pdf/${action.report_name}`,
			text: `/report/text/${action.report_name}`,
		};
		if (!action.data || (typeof action.data === 'object' && Object.keys(action.data).length === 0)) {
			if (action.context.active_ids) {
				const activeIDsPath = `/${action.context.active_ids.join(',')}`;
				for (const key in reportUrls) {
					reportUrls[key] += activeIDsPath;
				}
			}
		} else {
			const serializedOptionsPath = `?options=${encodeURIComponent(JSON.stringify(action.data))}&context=${encodeURIComponent(JSON.stringify(action.context))}`;
			for (const key in reportUrls) {
				reportUrls[key] += serializedOptionsPath;
			}
		}
		const url = this.rpc.session.url('/report/download', {
			data: JSON.stringify([reportUrls[type], action.report_type]),
			token: this.rpc.core.csrf_token,
		});
		const preview = new PreviewDialog(this, [{
			url: url,
			filename: label,
			mimetype: mimetype,
		}], 0);
		preview.appendTo(document.body);
	}
}

Sidebar.template = 'fl_web_preview.Sidebar';
Sidebar.props = {
	items: Object,
};

export default Sidebar;
