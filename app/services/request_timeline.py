"""
Where a site request is, and how it got there.

The timeline is built from the audit log, which records each stage change
of a request. Old requests have no such rows, so the steps fall back to the
request's own date fields. Nothing is left blank or broken.

THE AUDIT FORMAT THIS DEPENDS ON
    entity_type 'request', entity_id = request_id, and one of these actions:
        submit_request      a request was sent
        org_forward         the organization passed it to the CENRO
        org_return          the organization asked for changes
        org_reject          the organization rejected it
        resubmit_request    the member sent it back with documents
        review_request      the CENRO set a status (Under Review, Approved, Rejected)
    test_timeline_notifications.py pins this format.

A CENRO approval of a Not Suitable site visit also rejects the request. That
change is not in the request's audit rows, so the timeline reads the
request's own date fields for the final step.
"""

from app.models import AuditLog
from app.services.request_stage import (
    AT_ORGANIZATION, APPROVED, CENRO_ACTIONABLE, ORG_PENDING, REJECTED,
    RETURNED, request_label,
)
from app.utils.jurisdiction import cenro_for_municipality
from app.utils.timeutil import manila_now

STAGE_ACTIONS = (
    'submit_request', 'org_forward', 'org_return', 'org_reject',
    'resubmit_request', 'review_request',
)
ORG_ACTIONS = ('org_forward', 'org_return', 'org_reject')

STAFF_ROLES = ('admin', 'superadmin')


def stage_events(req):
    """The stage-changing audit rows for this request, oldest first."""
    return (AuditLog.query
            .filter(AuditLog.entity_type == 'request',
                    AuditLog.entity_id == req.request_id,
                    AuditLog.action.in_(STAGE_ACTIONS))
            .order_by(AuditLog.created_at, AuditLog.log_id)
            .all())


def can_see_request(user, req):
    """The submitter, an active leader of the request's organization, and
    the CENRO that covers the request's barangay. A provincial admin and a
    superadmin see every request. Everyone else is refused."""
    if user is None:
        return False
    if req.user_id == user.user_id:
        return True
    if (req.organization_id and user.organization_id == req.organization_id
            and user.org_role == 'leader' and user.org_status == 'active'):
        return True
    if user.role == 'superadmin':
        return True
    if user.role == 'admin':
        if not user.cenro:
            return True
        municipality = req.location.municipality if req.location else None
        return cenro_for_municipality(municipality) == user.cenro
    return False


def _step(key, label, state, date=None, who=None, note=None):
    return {'key': key, 'label': label, 'state': state,
            'date': date, 'who': who, 'note': note}


def build_timeline(req, now=None):
    """The steps, the current one, and how long it has waited.

    Returns {'steps': [...], 'current': key or None,
             'waiting_days': int or None, 'waiting_since': datetime or None}.
    Each step: key, label, state, date, who, note. A state is one of
    done, current, pending, skipped, rejected, approved.
    """
    now = now or manila_now()
    events = stage_events(req)
    submitted_at = req.date_submitted or now
    requester = req.requester.username if req.requester else None

    # the last status change: the waiting clock starts here
    last_change = events[-1].created_at if events else None
    since = last_change or submitted_at

    org_events = [e for e in events if e.action in ORG_ACTIONS]
    last_org = org_events[-1] if org_events else None
    forwarded = next((e for e in org_events if e.action == 'org_forward'),
                     None)
    review_events = [e for e in events if e.action == 'review_request']
    reviewer = req.reviewer.username if req.reviewer else None

    has_org = bool(req.organization_id) and (
        bool(org_events) or req.status in AT_ORGANIZATION
        or req.org_reviewed_at is not None)
    org_rejected = (req.status == REJECTED and last_org is not None
                    and last_org.action == 'org_reject'
                    and not review_events)

    # 1. submitted
    submitted = _step('submitted', 'Submitted', 'done',
                      date=submitted_at, who=requester)

    # 2. organization review
    if not has_org:
        org = _step('org', 'Organization review', 'skipped')
    elif org_rejected:
        org = _step('org', 'Rejected by the organization', 'rejected',
                    date=last_org.created_at, who=last_org.username,
                    note=req.org_review_note)
    elif req.status == RETURNED:
        org = _step('org', 'Returned to the member', 'current',
                    date=last_org.created_at if last_org else submitted_at,
                    who=last_org.username if last_org else None,
                    note=req.org_review_note)
    elif req.status == ORG_PENDING:
        org = _step('org', 'Organization review', 'current',
                    date=submitted_at, who=None)
    else:
        org = _step('org', 'Organization review', 'done',
                    date=(forwarded.created_at if forwarded
                          else req.org_reviewed_at or submitted_at),
                    who=(forwarded.username if forwarded else None),
                    note=req.org_review_note)

    # 3. CENRO review
    if org_rejected or (has_org and req.status in AT_ORGANIZATION):
        cenro = _step('cenro', 'CENRO review', 'pending')
    else:
        entered_at = (forwarded.created_at if forwarded else submitted_at)
        entered_by = (forwarded.username if forwarded else requester)
        if req.status in CENRO_ACTIONABLE:
            cenro = _step('cenro', 'CENRO review', 'current',
                          date=entered_at, who=entered_by)
        else:
            cenro = _step('cenro', 'CENRO review', 'done',
                          date=entered_at, who=entered_by)

    # 4. outcome
    if org_rejected:
        outcome = _step('outcome', 'Outcome', 'skipped')
    elif req.status == APPROVED:
        outcome = _step('outcome', 'Approved', 'approved',
                        date=(review_events[-1].created_at if review_events
                              else req.date_reviewed or submitted_at),
                        who=reviewer, note=req.review_note)
    elif req.status == REJECTED:
        outcome = _step('outcome', 'Rejected', 'rejected',
                        date=req.date_reviewed or submitted_at,
                        who=reviewer, note=req.review_note)
    else:
        outcome = _step('outcome', 'Approved', 'pending')

    steps = [submitted, org, cenro, outcome]
    current = next((s['key'] for s in steps if s['state'] == 'current'),
                   None)
    if current is None:
        current = next((s['key'] for s in steps
                        if s['state'] in ('rejected', 'approved')), None)

    waiting_days = None
    if current is not None and any(s['state'] == 'current' for s in steps):
        waiting_days = max(0, (now - since).days)

    return {
        'steps': steps,
        'current': current,
        'waiting_days': waiting_days,
        'waiting_since': since if waiting_days is not None else None,
        'status_label': request_label(req.status),
    }
