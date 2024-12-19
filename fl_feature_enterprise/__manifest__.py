{
    "name": "Feature Enterprise",
    "version": "18.0.2.0.0",
    "category": "Security",
    "summary": "Enterprise Fetures Widget",
    "description": "",
    "author": "Flosslab",
    "website": "https://www.flosslab.com",
    "license": "LGPL-3",
    "sequence": 0,
    "depends": [
        "web",
    ],
    "assets": {
        "web.assets_frontend": [
            "fl_feature_enterprise/static/src/js/fields/upgrade_fields.js"
        ]
    },
    "qweb": [
        "static/src/xml/base.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
