"""
Where a notification leads.

One rule for the notifications page, the bell dropdown and its API, so a
notice always opens the same page wherever it is shown.

Request notices open the request's own page. The CENRO gets the CENRO's
detail page instead. Membership notices open the members page for a
leader, and My Account for everyone else.
"""

from flask import session, url_for

STAFF_ROLES = ('admin', 'superadmin')


def notification_url(n):
    staff = session.get('role') in STAFF_ROLES

    if n.report_id:
        if staff:
            return url_for('admin.review_report_detail', report_id=n.report_id)
        return url_for('dashboard.my_report_detail', report_id=n.report_id)
    if n.visit_id:
        return url_for('visits.visit_detail', visit_id=n.visit_id)
    if n.site_id:
        return url_for('visits.site_visits', site_id=n.site_id)
    if n.request_id:
        if staff:
            return url_for('admin.review_request_detail',
                           request_id=n.request_id)
        return url_for('dashboard.request_detail', request_id=n.request_id)
    if n.notification_type == 'Membership':
        recipient = n.user
        if recipient is not None and recipient.org_role == 'leader':
            return url_for('organization.members_page')
        return url_for('dashboard.my_account')
    if n.notification_type == 'New Request':
        if staff:
            return url_for('admin.review_requests')
        return url_for('dashboard.requests_page')
    if n.notification_type == 'Request Update':
        if staff:
            return url_for('admin.review_requests')
        return url_for('dashboard.requests_page')
    return None
