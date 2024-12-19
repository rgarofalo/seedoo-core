/** ********************************************************************************
    Copyright 2020-2022 Flosslab S.r.l.
    Copyright 2017-2019 MuK IT GmbH
    License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).
 **********************************************************************************/

/** @odoo-module **/

import { range } from "@web/core/utils/functions";

function isUrl(string) {
    const protocol = string.match(/^(?:\w+:)?\/\/(\S+)$/);
    if (protocol && protocol[1]) {
        const localHost = (/^localhost[:?\d]*(?:[^\:?\d]\S*)?$/).test(protocol[1]);
        const nonLocalHost = (/^localhost[:?\d]*(?:[^\:?\d]\S*)?$/).test(protocol[1]);
        return !!(localHost || nonLocalHost);
    }
    return false;
}

function parseText2Html(text) {
    return text
        .replace(/((?:https?|ftp):\/\/[\S]+)/g, '<a href="$1">$1</a> ')
        .replace(/[\n\r]/g, '<br/>');
}

function closedRange(start, end) {
    return range(start, end + 1);
}

function partitionPageList(pages, page, size) {
    if (!size || size < 5) {
        throw new Error("The size must be at least 5 to partition the list.");
    }
    const sideSize = size < 9 ? 1 : 2;
    const leftSize = Math.floor((size - sideSize * 2 - 3) / 2);
    const rightSize = Math.floor((size - sideSize * 2 - 2) / 2);
    
    if (pages <= size) {
        return closedRange(1, pages);
    }
    if (page <= size - sideSize - 1 - rightSize) {
        return [
            ...closedRange(1, size - sideSize - 1),
            false,
            ...closedRange(pages - sideSize + 1, pages),
        ];
    }
    if (page >= pages - sideSize - 1 - rightSize) {
        return [
            ...closedRange(1, sideSize),
            false,
            ...closedRange(pages - sideSize - 1 - rightSize - leftSize, pages),
        ];
    }
    return [
        ...closedRange(1, sideSize),
        false,
        ...closedRange(page - leftSize, page + rightSize),
        false,
        ...closedRange(pages - sideSize + 1, pages),
    ];
}

export {
    isUrl,
    closedRange,
    parseText2Html,
    partitionPageList,
};
