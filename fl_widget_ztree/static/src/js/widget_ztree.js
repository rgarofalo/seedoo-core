/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onMounted } from "@odoo/owl";
import { rpc } from "@web/core/rpc";
import { _t } from "@web/core/l10n/translation";

class ZTreeWidget extends Component {
    setup() {
        this.state = useState({
            ztree_title_field: this.props.data.ztree_title_field,
            ztree_nodes_to_disable: this.props.data.ztree_nodes_to_disable || [],
            ztree_only_child: this.props.data.ztree_only_child,
            ztree_custom_class: this.props.data.ztree_custom_class || "no-hover",
        });

        this.setting = this.props.setting;
        this.setting.view = {
            addDiyDom: (treeId, node) => {
                if (this.checkNodeToDisable(this.state.ztree_only_child, this.state.ztree_nodes_to_disable, node)) {
                    $.fn.zTree._z.tools.$(node, $.fn.zTree.consts.id.A, this.setting).addClass(this.state.ztree_custom_class);
                }
            },
        };

        if (this.props.setting.view) {
            $.extend(this.setting.view, this.props.setting.view);
        }
    }

    checkNodeToDisable(ztree_only_child, ztree_nodes_to_disable, node) {
        return (ztree_only_child === "only_child" && "child_ids" in node && node.child_ids.length > 0) ||
            ztree_nodes_to_disable.includes(node.id);
    }

    async start() {
        if (!this.$zTree) {
            this.$zTree = $.fn.zTree.init(this.el, this.setting, this.props.data.zNodes);
            if (this.props.data.ztree_selected_id != null && this.props.data.ztree_selected_id > 0) {
                const node = this.$zTree.getNodeByParam('id', this.props.data.ztree_selected_id, null);
                this.$zTree.selectNode(node, undefined, true);
            }
        }
    }
}

class FieldZTree extends Component {
    setup() {
        this.state = useState({
            ztree_title_field: this.props.nodeOptions.ztree_title_field,
            ztree_child_key: this.props.nodeOptions.ztree_child_key,
            ztree_only_child: this.props.nodeOptions.ztree_only_child,
            ztree_only_child_by_function: this.props.nodeOptions.ztree_only_child_by_function,
            ztree_name_field_readonly: this.props.nodeOptions.ztree_name_field_readonly,
            ztree_tree_dimension: this.props.nodeOptions.ztree_tree_dimension,
            ztree_custom_class: this.props.nodeOptions.ztree_custom_class,
        });

        this.nodeContext = this.props.record.getContext({ additionalContext: this.props.attrs.context || {} });
        this.dropdown = false;

        onMounted(() => {
            if (this.state.ztree_only_child_by_function) {
                rpc.query({
                    model: "ir.config_parameter",
                    method: this.state.ztree_only_child_by_function,
                }).then((result) => {
                    if (result === "only_child") {
                        this.state.ztree_only_child = "only_child";
                    }
                });
            }
        });
    }

    async _selectNode(event, item) {
        let disable_ids = [];
        if ("disable_ids" in this.nodeContext) {
            disable_ids = this.nodeContext.disable_ids;
        }
        if (this.many2one.checkNodeToDisable(this.state.ztree_only_child, disable_ids, item)) {
            return false;
        }

        return this._super.apply(this, arguments);
    }

    async _search(search_val) {
        const context = this.props.record.getContext(this.props.recordParams);
        const domain = this.props.record.getDomain(this.props.recordParams);

        _.extend(context, this.additionalContext);

        const blacklisted_ids = this._getSearchBlacklist();
        if (blacklisted_ids.length > 0) {
            domain.push(['id', 'not in', blacklisted_ids]);
        }
        if (search_val && search_val !== "") {
            if (this.state.ztree_name_field) {
                domain.push([this.state.ztree_name_field, 'ilike', search_val]);
            } else {
                domain.push(['name', 'ilike', search_val]);
            }
        }

        const result = await rpc.query({
            model: this.props.field.relation,
            method: "search_ztree",
            kwargs: {
                domain: domain,
                context: context,
                parent_key: this.state.ztree_parent_key,
                child_key: this.state.ztree_child_key,
                root_id: this.state.ztree_root_id,
                expend_level: this.state.ztree_expend_level,
                name_field: this.state.ztree_name_field,
                title_field: this.state.ztree_title_field,
                limit: parseInt(this.limit + 1),
                order: this.order,
            }
        });

        let values = result;
        if (values.length > this.limit) {
            values = this._manageSearchMore(values, search_val, domain, context);
        }

        const create_enabled = this.can_create && !this.props.nodeOptions.no_create;
        const raw_result = _.map(result, (x) => x[1]);

        if (create_enabled && !this.props.nodeOptions.no_quick_create &&
            search_val.length > 0 && !_.contains(raw_result, search_val)) {
            values.push({
                id: null,
                name: _.str.sprintf(_t('Create "<strong>%s</strong>"'), $('<span />').text(search_val).html()),
                font: { 'color': '#00A09D', 'font-weight': 'bold' },
                label: _.str.sprintf(_t('Create "<strong>%s</strong>"'), $('<span />').text(search_val).html()),
                action: this._quickCreate.bind(this, search_val),
                classname: 'o_m2o_dropdown_option'
            });
        }
        if (create_enabled && !this.props.nodeOptions.no_create_edit) {
            const createAndEditAction = () => {
                this.$('input').val('');
                return this._searchCreatePopup("form", false, this._createContext(search_val));
            };
            values.push({
                id: null,
                name: _t("Create and Edit..."),
                font: { 'color': '#00A09D', 'font-weight': 'bold' },
                label: _t("Create and Edit..."),
                action: createAndEditAction,
                classname: 'o_m2o_dropdown_option',
            });
        } else if (values.length === 0) {
            values.push({
                id: null,
                name: _t("No results to show..."),
                font: { 'color': '#00A09D', 'font-weight': 'bold' },
                label: _t("No results to show..."),
            });
        }
        return values;
    }

    async buildTreeView(search_val) {
        const domain = this.props.record.getDomain(this.props.recordParams);
        const blacklisted_ids = this._getSearchBlacklist();
        if (blacklisted_ids.length > 0) {
            domain.push(['id', 'not in', blacklisted_ids]);
        }
        if (this.many2one) {
            this.many2one.destroy();
            this.many2one = undefined;
        }
        const setting = {
            callback: {
                onClick: (event, treeId, treeNode, clickFlag) => {
                    this._selectNode(event, treeNode);
                },
            }
        };
        const result = await this._search(search_val);
        jQuery('.ztree').remove();
        if (this.value && this.value.data.id && this.value.data.id > 0) {
            var ztree_selected_id = this.value.data.id;
        }
        this.many2one = new ZTreeWidget({
            setting: setting,
            data: {
                zNodes: result,
                ztree_domain: domain,
                ztree_field: this.props.field.name,
                ztree_model: this.props.field.relation,
                ztree_parent_key: this.state.ztree_parent_key,
                ztree_child_key: this.state.ztree_child_key,
                ztree_root_id: this.state.ztree_root_id,
                ztree_expend_level: this.state.ztree_expend_level,
                ztree_name_field: this.state.ztree_name_field,
                ztree_selected_id: ztree_selected_id,
                ztree_only_child: this.state.ztree_only_child,
                ztree_custom_class: this.state.ztree_custom_class,
                ztree_nodes_to_disable: this.nodeContext.disable_ids
            }
        });
        this.many2one.mount(this.el);
        this.$input.css('height', 'auto');
    }

    async _renderReadonly() {
        if (this.state.ztree_name_field_readonly && this.value && this.value.data && this.value.data.id) {
            const records = await rpc.query({
                model: this.props.field.relation,
                method: "read",
                args: [this.value.data.id, [this.state.ztree_name_field_readonly]],
                context: this.context,
            });
            if (records.length > 0) {
                const escapedValue = _.escape((records[0][this.state.ztree_name_field_readonly] || "").trim());
                const value = escapedValue.split('\n').map((line) => `<span>${line}</span>`).join('<br/>');
                this.el.innerHTML = value;
                if (!this.noOpen && this.value) {
                    this.el.setAttribute('href', `#id=${this.value.res_id}&model=${this.props.field.relation}`);
                    this.el.classList.add('o_form_uri');
                }
                return;
            }
        } else {
            this._super.apply(this, arguments);
        }
    }
}

registry.category("fields").add("zTree", FieldZTree);
