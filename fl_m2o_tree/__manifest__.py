{
    "name": "M2O tree",
    "version": "18.0.2.0.0",
    "category": "Extra Tools",
    "summary": "",
    "description": "",
    "author": "Flosslab",
    "website": "https://www.flosslab.com",
    "license": "LGPL-3",
    "sequence": 0,
    "depends": ["web"],
    "qweb": [
        "static/src/xml/*.xml",
    ],
    'assets': {
        'web.assets_frontend': [
            "/fl_m2o_tree/static/libs/ztree/js/jquery.ztree.core-3.5.min.js",
            "/fl_m2o_tree/static/libs/ztree/js/jquery.ztree.excheck-3.5.min.js",
            "/fl_m2o_tree/static/src/js/fl_m2o_tree.js",
            "/fl_m2o_tree/static/libs/ztree/css/zTreeStyle.css",
        ]
    },
    "installable": True,
    "application": False,
    "auto_install": False,
}
