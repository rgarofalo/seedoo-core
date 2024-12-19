{
    "name": "M2M tree",
    "version": "18.0.2.0.0",
    "category": "Extra Tools",
    "summary": "",
    "description": "",
    "author": "Flosslab",
    "website": "https://www.flosslab.com",
    "license": "LGPL-3",
    "sequence": 0,
    "depends": ["web", "fl_m2o_tree"],
    "qweb": [
        "static/src/xml/*.xml",
    ],
    'assets': {
        'web.assets_backend': [
            "/fl_m2m_tree/static/src/js/fl_m2m_tree.js"
        ]
    },
    "installable": True,
    "application": False,
    "auto_install": False,
}
