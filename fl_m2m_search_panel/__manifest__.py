{
    "name": "M2M search panel",
    "version": "18.0.2.0.0",
    "category": "Extra Tools",
    "summary": "Enable search panel for field many2many",
    "description": "",
    "author": "Flosslab",
    "website": "https://www.flosslab.com",
    "license": "LGPL-3",
    "sequence": 0,
    "depends": ["web"],
    "assets": {
        "web.assets_frontend": [
            "/fl_m2m_search_panel/static/src/js/views/search_panel_model_extension.js"
        ]
    },
    "installable": True,
    "application": False,
    "auto_install": False,
}
