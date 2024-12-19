/** @odoo-module **/

import { registry } from '@web/core/registry';
import { Many2OneField } from '@web/views/fields/many2one/many2one_field';
import { Component } from '@odoo/owl';

class IconLabel extends Many2OneField {
    setup() {
        super.setup();
        this.icon_fa = "fa fa-paper-plane";
        this.icon_color = "#D2691E";
        const field_name_icon = this.props.nodeOptions.icon_field || false;
        const field_name_icon_color = this.props.nodeOptions.icon_color_field || false;
        if (field_name_icon && field_name_icon_color) {
            this.icon_fa = this.props.record.data[field_name_icon];
            this.icon_color = this.props.record.data[field_name_icon_color];
        }
    }

    get classes() {
        return [this.icon_fa];
    }

    get styles() {
        return {
            color: this.icon_color,
            cursor: 'pointer',
            'pointer-events': 'none',
        };
    }
}

IconLabel.template = 'sd_protocollo.IconLabel';

registry.category('fields').add('icon_label', IconLabel);
