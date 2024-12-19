/** @odoo-module **/

import { Component, useState, onWillStart, onMounted } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

class M2mTreeField extends Component {
    setup() {
        this.orm = useService("orm");
        this.state = useState({
            isRendered: false,
            zNodes: [],
        });

        onWillStart(async () => {
            await this._fetchData();
        });

        onMounted(() => {
            this._renderTree();
        });
    }

    async _fetchData() {
        const modelFields = ["id", this.props.field_name || "name"];
        if (this.props.field_style) {
            modelFields.push(this.props.field_style);
        }
        if (this.props.field_parent) {
            modelFields.push(this.props.field_parent);
        }
        if (this.props.field_checkable) {
            modelFields.push(this.props.field_checkable);
        }
        if (this.props.field_typology) {
            modelFields.push(this.props.field_typology);
        }

        const order = this.props.order ? this.props.order.split(",").map(orderComponent => {
            const [name, direction] = orderComponent.split(" ");
            return { name, asc: direction !== "desc" };
        }) : [{ name: this.props.field_name || "name" }];

        const res = await this.orm.searchRead(this.props.relation, [], {
            domain: this.props.domain || [],
            fields: modelFields,
            limit: this.props.limit,
            order,
            context: this.props.context || {},
        });

        this.state.zNodes = res.map(r => ({
            id: r.id,
            pId: r[this.props.field_parent] && r[this.props.field_parent][0] || false,
            name: r[this.props.field_name || "name"],
            doCheck: true,
            chkDisabled: this.props.field_checkable && r[this.props.field_checkable] || false,
            checked: this.props.value.res_ids.includes(r.id),
            open: false,
            typology: this.props.field_typology && r[this.props.field_typology] || '',
            iconSkin: this.props.field_style && r[this.props.field_style] || '',
            isParent: this.props.async,
        }));
    }

    _renderTree() {
        const setting = {
            view: {
                selectedMulti: true,
                dblClickExpand: false,
            },
            check: {
                enable: true,
                chkboxType: { "Y": "", "N": "" },
            },
            data: {
                simpleData: {
                    enable: true,
                },
            },
            callback: {
                beforeCheck: this.beforeCheck,
                onClick: this.onClick,
                onCheck: this.onCheck,
            },
        };

        if (this.props.async) {
            setting.async = {
                enable: true,
                contentType: "application/json",
                dataType: "json",
                url: this.props.async_url,
                autoParam: ["id"],
                dataFilter: this.filter,
            };
        }

        $.fn.zTree.init(this.el, setting, this.state.zNodes);
    }

    beforeCheck(treeId, treeNode) {
        return treeNode.doCheck !== false;
    }

    onClick(event, treeId, treeNode) {
        if (!treeNode.chkDisabled) {
            const zTree = $.fn.zTree.getZTreeObj(treeId);
            if (zTree) {
                zTree.checkNode(treeNode, !treeNode.checked, false, true);
            }
        }
    }

    onCheck(e, treeId, treeNode) {
        if (this.props.value.res_ids.includes(treeNode.id)) {
            this.props.setValue({ operation: "FORGET", ids: [treeNode.id] });
        } else {
            this.props.setValue({ operation: "ADD_M2M", ids: [{ id: treeNode.id }] });
        }
        if (treeNode.checked && this.props.uncheck_different_typology) {
            treeNode.children.forEach(child => {
                if (treeNode.typology !== child.typology && child.checked) {
                    zTree.checkNode(child, false, false, true);
                }
            });
            const parent = treeNode.getParentNode();
            if (parent && treeNode.typology !== parent.typology && parent.checked) {
                zTree.checkNode(parent, false, false, true);
            }
        }
    }

    filter(treeId, parentNode, result) {
        return result.result;
    }
}

M2mTreeField.template = "m2m_tree";

registry.category("fields").add("m2m_tree", M2mTreeField);
