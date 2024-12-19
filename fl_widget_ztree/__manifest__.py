{
    "name": "Widget zTree",
    "version": "18.0.2.0.0",
    "category": "Extra Tools",
    "summary": "Modulo estensivo del modulo app_web_widget_ztree",
    "description": """
    Modulo estensivo del modulo app_web_widget_ztree, aggiunge la possibilità di disabilitare i nodi padre e di ricercare
    tramite field personalizzato.  
    """,
    "author": "Flosslab",
    "website": "https://www.flosslab.com",
    "license": "LGPL-3",
    "sequence": 0,
    "depends": [
        "app_web_widget_ztree",
    ],
    "assets": {
        "web.assets_backend": [
            "/fl_widget_ztree/static/src/scss/widget_ztree.scss",
            "/fl_widget_ztree/static/src/js/widget_ztree.js",
        ]
    },
    "installable": True,
    "application": False,
    "auto_install": False,
}
