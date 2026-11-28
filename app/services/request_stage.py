"""
The stages of a site request.

A request made by a member goes to the organization first. A request made
by a leader goes straight to the CENRO. The shape follows
boundary_publication.py: this module says what may happen, the routes say
who may do it, and the caller commits.

    member sends  -> Pending Org Approval
    leader sends  -> Submitted (Pending CENRO)

    Pending Org Approval  --forward-->  Submitted (Pending CENRO)
    Pending Org Approval  --return-->   Returned        (note required)
    Pending Org Approval  --reject-->   Rejected        (note required, final)
    Returned              --resubmit--> Pending Org Approval
                                        (the member adds documents only)
    Submitted             --review-->   Under Review
    Submitted / Under Review --approve--> Approved
    Submitted / Under Review --reject--->  Rejected     (note required)

The stored value 'Submitted' is kept as it is. The screens call it
"Pending CENRO".
"""

ORG_PENDING = 'Pending Org Approval'
RETURNED = 'Returned'
SUBMITTED = 'Submitted'
UNDER_REVIEW = 'Under Review'
APPROVED = 'Approved'
REJECTED = 'Rejected'

# What the CENRO can act on, and what it may only read.
CENRO_ACTIONABLE = (SUBMITTED, UNDER_REVIEW)
AT_ORGANIZATION = (ORG_PENDING, RETURNED)

# The statuses a CENRO may set. Submitted is not one of them.
CENRO_TARGETS = (UNDER_REVIEW, APPROVED, REJECTED)

# Shown to people in place of the stored value.
LABELS = {SUBMITTED: 'Pending CENRO'}

ORG_ACTIONS = {
    'forward': SUBMITTED,
    'return': RETURNED,
    'reject': REJECTED,
}

ORG_ACTION_NOTE_REQUIRED = ('return', 'reject')


def notify_cenro(req, message):
    """Tell the CENRO that reviews this request's barangay. Only the
    reviewing office is told: PENRO and superadmins cannot act on it."""
    from app.models import Notification
    from app.extensions import db
    from app.utils.jurisdiction import (
        cenro_for_municipality, reviewing_admins,
    )
    municipality = req.location.municipality if req.location else None
    for admin in reviewing_admins(cenro_for_municipality(municipality)):
        db.session.add(Notification(
            user_id=admin.user_id,
            notification_type='New Request',
            message=message,
            request_id=req.request_id,
            is_read=False,
        ))


def notify_org_leaders(org, message, request_id=None):
    """Tell every active leader of the organization."""
    from app.models import Notification, User
    from app.extensions import db
    if org is None:
        return
    leaders = User.query.filter(
        User.organization_id == org.organization_id,
        User.org_role == 'leader',
        User.org_status == 'active',
    ).all()
    for leader in leaders:
        db.session.add(Notification(
            user_id=leader.user_id,
            notification_type='Request Update',
            message=message,
            request_id=request_id,
            is_read=False,
        ))


def org_has_active_leader(org):
    from app.utils.organization import has_active_leader
    return org is not None and has_active_leader(org)


def request_label(status):
    """The words shown for a stored status."""
    return LABELS.get(status, status)


def initial_status(member):
    """Where a new request starts, from who sends it."""
    if member.org_role == 'leader':
        return SUBMITTED
    return ORG_PENDING


def org_action_problem(req, action, note):
    """Why an organization action cannot be applied, or None."""
    if action not in ORG_ACTIONS:
        return "Choose Forward, Return or Reject for this request."
    if req.status != ORG_PENDING:
        return ("This request has already moved on from the organization. "
                "Its current status is shown below.")
    if action in ORG_ACTION_NOTE_REQUIRED and not note:
        return ("Write a reason. The member will see it."
                if action == 'reject' else
                "Write what the member should change.")
    return None


def apply_org_action(req, action, note, user_id, now):
    """Move the request on. Returns the new status. Call
    org_action_problem() first."""
    req.status = ORG_ACTIONS[action]
    req.org_reviewed_by = user_id
    req.org_reviewed_at = now
    req.org_review_note = note or None
    return req.status


def resubmit_problem(req, member):
    """Why this member cannot resubmit the request, or None."""
    if req.status != RETURNED:
        return ("Only a request returned for changes can be sent again. "
                "Its current status is on its row.")
    if req.user_id != member.user_id:
        return "You can only resubmit your own request."
    if (not member.organization_id
            or member.organization_id != req.organization_id
            or member.org_status != 'active'):
        return ("Only an active member of this organization can resubmit "
                "the request.")
    return None


def apply_resubmit(req):
    """Back to the organization. The caller has saved the documents. The
    original submission date is kept."""
    req.status = ORG_PENDING


def cenro_problem(req, new_status):
    """Why the CENRO may not set new_status on req, or None.

    Requests still with the organization are read-only for the CENRO.
    """
    if new_status not in CENRO_TARGETS:
        return "Invalid status."
    if req.status in AT_ORGANIZATION:
        return ("This request is still with the organization. You can read "
                "it, but only the organization can act on it now.")
    if new_status == req.status:
        return f"This request is already {request_label(req.status)}."
    if req.status == REJECTED:
        return ("A rejected request is final. The member can send a new "
                "request.")
    if req.status == APPROVED and new_status == UNDER_REVIEW:
        return "An approved request cannot go back to Under Review."
    if req.status == APPROVED and new_status == REJECTED:
        # A site is closed only by a site visit found Not Suitable. That path
        # calls close_site() directly and does not come through here.
        return ("To close this site, assign a site visit and mark it Not "
                "Suitable.")
    return None
