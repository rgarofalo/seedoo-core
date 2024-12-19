/** @odoo-module **/

import { Component, useState, onWillStart } from '@odoo/owl';
import { registry } from '@web/core/registry';
import { useService } from '@web/core/utils/hooks';

class SDProtocolloDashboard extends Component {
    setup() {
        this.actionService = useService('action');
        this.rpc = useService('rpc');
        this.state = useState({
            title: this.props.action.name || this.env._t('Dashboard'),
            htmlContent: '',
        });

        onWillStart(async () => {
            const response = await this.rpc('/protocollo/dashboard');
            this.state.htmlContent = response.html_content;
        });
    }

    async _onClickKanbanButton(event) {
        const data = event.currentTarget.dataset;
        const parameters = {
            action_name: data.actionName || [],
            action_context: data.actionContext || [],
        };
        const action = await this.rpc('/protocollo/dashboard/list', { params: parameters });
        this.actionService.doAction(action, { on_reverse_breadcrumb: this.on_reverse_breadcrumb.bind(this) });
    }

    on_reverse_breadcrumb() {
        this.actionService.doPushState({});
        this.setup();
    }

    static template = 'sd_protocollo.DashboardTemplate';
}

SDProtocolloDashboard.template = 'sd_protocollo.DashboardTemplate';

registry.category('actions').add('sd.protocollo.dashboard',{component: SDProtocolloDashboard});

export default SDProtocolloDashboard;
