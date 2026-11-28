"""Organization membership rules.

Every rule about who may approve, appoint, remove, or leave lives here.
The routes call these functions and do not repeat the checks.

Who can act on an organization:

- An active leader of the organization. Leaders approve members, remove
  members, and regenerate the join link. They cannot touch other leaders.
- A CENRO admin whose CENRO is the organization's CENRO. Appoints and
  removes leaders.
- A provincial admin: a superadmin, or an admin with no CENRO. Appoints
  and removes leaders for any organization, including ones with no CENRO.

The CENRO admin and the provincial admin may also approve members, but
only while the organization has no active leader.
"""

import secrets

from app.extensions import db
from app.models import Organization, User


def new_join_token():
    return secrets.token_urlsafe(32)


def ensure_join_token(org):
    """Give the organization a join link if it has none. The caller commits."""
    if not org.join_token:
        org.join_token = new_join_token()
    return org.join_token


def find_org_by_token(token):
    """The organization a join link belongs to, or None when the link is
    old, regenerated, or made up."""
    if not token:
        return None
    return Organization.query.filter_by(join_token=token).first()


def is_provincial(user):
    return user.role == 'superadmin' or (
        user.role == 'admin' and not user.cenro)


def is_cenro_admin_for(user, org):
    return bool(user.role == 'admin' and user.cenro
                and org.cenro == user.cenro)


def is_active_leader_of(user, org):
    return (user.organization_id == org.organization_id
            and user.org_role == 'leader'
            and user.org_status == 'active')


def has_active_leader(org):
    return db.session.query(User.user_id).filter(
        User.organization_id == org.organization_id,
        User.org_role == 'leader',
        User.org_status == 'active',
    ).first() is not None


def can_appoint_leaders(user, org):
    """Make or unmake a leader. CENRO admin of the org, or provincial."""
    return is_provincial(user) or is_cenro_admin_for(user, org)


def can_approve(user, org):
    """Approve, reject or remove members, and regenerate the join link."""
    if is_active_leader_of(user, org):
        return True
    return can_appoint_leaders(user, org) and not has_active_leader(org)


def can_view(user, org):
    """May open the organization's members page."""
    return (is_active_leader_of(user, org)
            or can_appoint_leaders(user, org)
            or can_approve(user, org))


def can_act_on(actor, org, target):
    """Whether actor may approve, reject, or remove target in this org.

    Checks that target belongs to this organization, is not the actor, and
    that only a leader-level admin touches a leader.
    """
    if target.organization_id != org.organization_id:
        return False
    if target.user_id == actor.user_id:
        return False
    if target.org_role == 'leader' and not can_appoint_leaders(actor, org):
        return False
    return True


def is_last_active_leader(user):
    """True when this user is the only active leader of their organization."""
    if (not user.organization_id or user.org_role != 'leader'
            or user.org_status != 'active'):
        return False
    other = db.session.query(User.user_id).filter(
        User.organization_id == user.organization_id,
        User.org_role == 'leader',
        User.org_status == 'active',
        User.user_id != user.user_id,
    ).first()
    return other is None


STAFF_ROLES = ('admin', 'superadmin', 'field_officer')

REQUEST_BLOCK_TEXT = {
    'individual': "Only organization members can request sites. Ask your "
                  "organization leader for an invite link.",
    'pending': "You can request sites once your leader approves you. "
               "Check that your email is verified, then remind your leader.",
    'staff_admin': "Staff create sites from approved requests.",
    'staff_field': "Field officers record visits and reports. Site requests "
                   "come from organizations.",
}


def request_block(user):
    """Why this user may not send a site request, as (code, text).

    None when they may. Only an active member of an organization may send
    a request. Staff never send one: they create sites directly.
    """
    if user is None:
        return ('individual', REQUEST_BLOCK_TEXT['individual'])
    if user.role in STAFF_ROLES:
        code = ('staff_field' if user.role == 'field_officer'
                else 'staff_admin')
        return (code, REQUEST_BLOCK_TEXT[code])
    if user.organization_id and user.org_status == 'active':
        return None
    if user.organization_id and user.org_status == 'pending':
        return ('pending', REQUEST_BLOCK_TEXT['pending'])
    return ('individual', REQUEST_BLOCK_TEXT['individual'])


def clear_membership(user):
    user.organization_id = None
    user.org_role = None
    user.org_status = None
