/** @odoo-module **/

// import { ActionModel } from "@web/views/action_model";
import { registry } from "@web/core/registry";
import { pyUtils } from "@web/core/py_js/py_utils";
import { SearchPanelModelExtensionDisableChildof} from "fl_disable_childof_search_panel/static/src/js/views/search_panel_model_extension.js";
/**
 * @extends ActionModel.Extension
 */
class SearchPanelModelExtensionLoadOnlyChildren extends SearchPanelModelExtensionDisableChildof{
    setup() {
        super.setup();
        this.state.sections = new Map();
    }

    /**
     * Aggiunge una sezione per ogni campo visibile nel pannello di ricerca.
     * Estende la funzione per gestire l'opzione `load_only_children_onexpand`.
     */
    _createSectionsFromArch() {
        super._createSectionsFromArch();
        this.config.archNodes.forEach(({ attrs, tag }) => {
            if (tag !== "field" || attrs.invisible === "1") return;
            const options = attrs.options ? pyUtils.py_eval(attrs.options) : {};
            if (!options.load_only_children_onexpand) return;

            for (const section of this.state.sections.values()) {
                if (section.fieldName !== attrs.name || section.type !== "category") continue;
                section.loadOnlyChildrenOnexpand = options.load_only_children_onexpand;
                section.loadOnlyChildrenOnexpandDisplayName = options.load_only_children_onexpand_display_name;
                break;
            }
        });
    }

    /**
     * Sovrascrive la funzione `callLoad` per implementare il caricamento condizionato.
     */
    async callLoad(params) {
        const searchDomain = this._getExternalDomain();
        params.searchDomainChanged = JSON.stringify(this.searchDomain) !== JSON.stringify(searchDomain);

        if (!this.shouldLoad && !this.initialStateImport) {
            const isFetchable = (section) =>
                section.enableCounters ||
                (params.searchDomainChanged && !section.expand) ||
                (section.loadOnlyChildrenOnexpand && section.expanded);

            this.categoriesToLoad = this.categories.filter(isFetchable);
            this.filtersToLoad = this.filters.filter(isFetchable);
            this.shouldLoad = params.searchDomainChanged || Boolean(this.categoriesToLoad.length + this.filtersToLoad.length);
        }

        this.searchDomain = searchDomain;
        this.initialStateImport = false;
        await super.callLoad(params);
    }

    /**
     * Effettua il caricamento delle categorie al bisogno.
     * @private
     * @param {Category[]} categories
     */
    async _fetchCategories(categories) {
        const filterDomain = this._getFilterDomain();
        for (const category of categories) {
            await this._fetchCategory(category, filterDomain);
        }
    }

    async _fetchCategory(category, filterDomain) {
        const result = await this.env.services.rpc({
            method: "search_panel_select_range",
            model: this.config.modelName,
            args: [category.fieldName],
            kwargs: {
                category_domain: this._getCategoryDomain(category.id),
                enable_counters: category.enableCounters,
                expand: category.expand,
                filter_domain: filterDomain,
                hierarchize: category.hierarchize,
                limit: category.limit,
                search_domain: this.searchDomain,
                load_only_children_onexpand: category.loadOnlyChildrenOnexpand,
                load_only_children_onexpand_display_name: category.loadOnlyChildrenOnexpandDisplayName,
                active_value_id: category.activeValueId,
            },
        });

        if (category.loadOnlyChildrenOnexpand) {
            this._createCategoryTreeLevel(category.id, category.activeValueId, result);
        } else {
            this._createCategoryTree(category.id, result);
        }
    }

    /**
     * Gestisce la struttura ad albero per i livelli caricati dinamicamente.
     * @private
     * @param {string} sectionId
     * @param {integer} activeId
     * @param {Object} result
     */
    _createCategoryTreeLevel(sectionId, activeId, result) {
        const category = this.state.sections.get(sectionId);
        if (category.values.get(activeId)) {
            category.values.get(activeId).childrenIds = [];
        }

        let { error_msg, parent_field: parentField, values } = result;
        if (error_msg) {
            category.errorMsg = error_msg;
            values = [];
        }
        if (category.hierarchize) {
            category.parentField = parentField;
        }
        for (const value of values) {
            const childrenIds = category.values.get(value.id)?.childrenIds || [];
            category.values.set(value.id, {
                ...value,
                childrenIds,
                parentId: value[parentField] || false,
            });
        }
        for (const value of values) {
            const { parentId } = category.values.get(value.id);
            if (parentId && category.values.has(parentId)) {
                category.values.get(parentId).childrenIds.push(value.id);
            }
        }
        if (!("rootIds" in category)) {
            category.rootIds = [false];
            for (const value of values) {
                const { parentId } = category.values.get(value.id);
                if (!parentId) {
                    category.rootIds.push(value.id);
                }
            }
            category.activeValueId = false;
        }
    }
}

registry.category("models").add("SearchPanel", SearchPanelModelExtensionLoadOnlyChildren, 30);
export default SearchPanelModelExtensionLoadOnlyChildren;
