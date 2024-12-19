# Copyright 2020-2022 Flosslab S.r.l.
# Copyright 2017-2019 MuK IT GmbH
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).
{
    "name": "Web preview",
    "version": "18.0.2.0.0",
    "category": "Extra Tools",
    "summary": "",
    "description": "",
    "author": "Flosslab",
    "website": "https://www.flosslab.com",
    "license": "LGPL-3",
    "depends": ["web"],
    "qweb": [
        "static/src/xml/*.xml",
    ],
    "assets": {
        "web.assets_frontend": [
            "/fl_web_preview/static/src/scss/*.scss",
            "/fl_web_preview/static/src/js/preview/registry.js",
            "/fl_web_preview/static/src/js/utils/utils.js",
            "/fl_web_preview/static/src/js/preview/content.js",
            "/fl_web_preview/static/src/js/widgets/manager.js",
            "/fl_web_preview/static/src/js/widgets/dialog.js",
            # "/fl_web_preview/static/src/js/chrome/sidebar.js",
            "/fl_web_preview/static/src/js/fields/binary.js",
            "/fl_web_preview/static/src/js/fields/image.js",
            "/fl_web_preview/static/src/js/preview/pdf.js",
            "/fl_web_preview/static/src/js/preview/unsupported.js",
            "/fl_web_preview/static/src/js/views/kanban_record.js",
        ]
    },
    "images": ["static/description/banner.png"],
   
    "installable": True,
    "application": False,
    "auto_install": False,
}
