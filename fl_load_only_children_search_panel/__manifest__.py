{
    "name": "Load only children items in search panel",
    "version": "18.0.2.0.0",
    "category": "Web",
    "summary": "Load only children items on expand event of item in search panel",
    "description": """
        To enable the feature set option load_only_children_onexpand to true in the options attribute of field added in search panel.
    """,
    "author": "Flosslab",
    "website": "https://www.flosslab.com",
    "license": "LGPL-3",
    "sequence": 0,
    "depends": ["web", "fl_disable_childof_search_panel"],
    "assets": {
        "web.assets_backend": [
            # "/fl_load_only_children_search_panel/static/src/js/views/search_panel_model_extension.js"
        ]
    },
    "qweb": ["static/src/xml/search_panel.xml"],
    "installable": True,
    "application": False,
    "auto_install": False,
}