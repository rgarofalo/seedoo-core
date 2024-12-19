/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onWillStart, onMounted } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

class M2oTreeField extends Component {
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
        const modelFields = ["id"];
        const field_name = this.props.nodeOptions.field_name || "name";
        modelFields.push(field_name);

        if (this.props.nodeOptions.field_style) {
            modelFields.push(this.props.nodeOptions.field_style);
        }

        const pid = this.props.nodeOptions.field_parent || "parent_id";
        modelFields.push(pid);

        if (this.props.nodeOptions.field_checkable) {
            modelFields.push(this.props.nodeOptions.field_checkable);
        }

        const order = this.props.nodeOptions.order
            ? this.props.nodeOptions.order.split(",").map((orderComponent) => {
                  const orderFieldComponents = orderComponent.split(" ");
                  return {
                      name: orderFieldComponents[0],
                      asc: orderFieldComponents[1]?.toLowerCase() !== "desc",
                  };
              })
            : [{ name: field_name }];

        const res = await this.orm.searchRead(this.props.field.relation, [], {
            domain: this.props.nodeDomain,
            fields: modelFields,
            limit: this.props.nodeOptions.limit,
            order: order,
            context: this.props.nodeContext,
        });

        this.state.zNodes = res.map((r) => {
            const iconSkin = this.props.nodeOptions.field_style ? r[this.props.nodeOptions.field_style] : "";
            const nocheck = this.props.nodeOptions.field_checkable && r[this.props.nodeOptions.field_checkable]
                ? true
                : this.props.nodeContext.disable_ids?.includes(r.id) || false;

            return {
                id: r.id,
                pId: r[pid]?.[0] || false,
                name: r[field_name],
                doCheck: true,
                chkDisabled: nocheck,
                checked: this.props.value.res_id === r.id,
                open: false,
                iconSkin: iconSkin,
                isParent: this.props.nodeContext.async,
            };
        });
    }

    _renderTree() {
        const setting = {
            view: {
                selectedMulti: false,
                dblClickExpand: false,
            },
            check: {
                enable: true,
                chkStyle: "radio",
                radioType: "all",
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

        if (this.props.nodeContext.async) {
            setting.async = {
                enable: true,
                contentType: "application/json",
                dataType: "json",
                url: this.props.nodeContext.async_url,
                autoParam: ["id"],
                dataFilter: this.filter,
            };
        }

        $.fn.zTree.init(this.el, setting, this.state.zNodes);
        const zTree = $.fn.zTree.getZTreeObj(`treeData_${this.props.name}`);
        if (zTree) {
            const all_parent_nodes = zTree.getNodesByParam("isParent", true, null);
            if (!this.props.nodeOptions.all_checkable) {
                all_parent_nodes.forEach((node) => {
                    if (node.isParent) {
                        zTree.setChkDisabled(node, true);
                    }
                });
            }
            const checked = zTree.getNodeByParam("checked", true, null);
            this.expandParentNode(zTree, checked);
        }

        this.state.isRendered = true;
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
        if (this.props.value.res_id === treeNode.id) {
            this.props.updateValue({ id: false });
        } else {
            this.props.updateValue({ id: treeNode.id });
        }
    }

    expandParentNode(zTree, node) {
        let pnode = node ? zTree.getNodeByParam("id", node.pId, null) : false;
        if (pnode) {
            zTree.expandNode(pnode, true, false, true);
            this.expandParentNode(zTree, pnode);
        }
    }
}

M2oTreeField.template = "m2o_tree";

registry.category("fields").add("m2o_tree", M2oTreeField);
