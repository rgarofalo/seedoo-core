# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2015 Innoviu srl (<http://www.innoviu.it>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

{
    "name": "M2M Tree Widget",
    "version": "8.0.1.8.13",
    "category": "Usability",
    "summary": "Protocollo Informatico PA",
    "author": "Agile Business Group, Innoviu, Flosslab",
    "website": "http://www.seedoo.it",
    "license": "AGPL-3",
    "depends": [
        "m2o_tree_widget"
    ],
    "data": [
        "base_data.xml"
    ],
    "css": [
    ],
    "qweb": [
        "static/src/xml/m2m_tree_widget.xml"
    ],
    "installable": True,
    "auto_install": False
}
