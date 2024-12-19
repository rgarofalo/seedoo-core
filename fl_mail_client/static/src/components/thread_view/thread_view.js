/** @odoo-module **/

import { registry } from '@web/core/registry';
import { ThreadView } from '@mail/components/thread_view/thread_view';
import { MailList } from '@fl_mail_client/components/mail_list/mail_list';

const components = {
    ThreadView,
    MailList,
};

// Extend ThreadView component to include MailList
Object.assign(ThreadView.components, {
    MailList: components.MailList,
});

registry.category('components').add('fl_mail_client.ThreadView', ThreadView);
