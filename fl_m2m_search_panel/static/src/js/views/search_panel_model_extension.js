/** @odoo-module **/

import { registry } from "@web/core/registry";
import { SearchPanel  } from "@web/search/search_panel/search_panel";

/**
 * @property {{ sections: Map<number, Section> }} state
 * @extends ActionModelExtension
 */
class SearchPanelModelExtensionM2m extends SearchPanel {
    /**
     * Computes and returns the domain based on the current active
     * categories. If "excludedCategoryId" is provided, the category with
     * that id is not taken into account in the domain computation.
     * Override the function to replace '=' with 'child_of' operator domain
     * if field type is many2many.
     * 
     * @override
     * @private
     * @param {string} [excludedCategoryId]
     * @returns {Array[]}
     */
    _getCategoryDomain(excludedCategoryId) {
        const domain = [];
        for (const category of this.categories) {
            if (
                category.id === excludedCategoryId ||
                !category.activeValueId
            ) {
                continue;
            }
            const field = this.config.fields[category.fieldName];
            const operator =
                (field.type === "many2one" || field.type === "many2many") && category.parentField ? "child_of" : "=";
            domain.push([
                category.fieldName,
                operator,
                category.activeValueId,
            ]);
        }
        return domain;
    }
}

// Register the extension in the registry
registry.category("modelExtensions").add("SearchPanel", {component:SearchPanelModelExtensionM2m});

export default SearchPanelModelExtensionM2m;
