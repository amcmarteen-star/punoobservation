"""Organization membership: join links, approval, leaders, leaving.

Every route checks the actor and the target on the server. An ID in the
URL is never trusted on its own. A leader's own organization comes from
their account, not from the URL.

The rules are in app/utils/organization.py.
"""

from flask import (
    Blueprint, render_template, request, redirect, url_for, session, flash,
    abort,
)

from app.extensions import db
from app.models import Organization, User
from app.routes.auth import _render_register
from app.utils.audit import log_action
from app.utils.decorators import login_required
from app.utils.organization import (
    can_act_on, can_appoint_leaders, can_approve, can_view,
    clear_membership, ensure_join_token, find_org_by_token,
    is_active_leader_of, is_last_active_leader, is_provincial,
    new_join_token,
)

org_bp = Blueprint('organization', __name__)

INVALID_LINK = "This link no longer works. Ask your leader for the new one."


def _current_user():
    user = db.session.get(User, session['user_id'])
    if user is None:
        abort(403)
    return user


def _load(org_id, user_id):
    """The organization and the target user, both must exist."""
    org = db.session.get(Organization, org_id)
    if org is None:
        abort(404)
    target = db.session.get(User, user_id)
    if target is None:
        abort(404)
    return org, target


def _members_url(org):
    return url_for('organization.org_members_page', org_id=org.organization_id)


# ----------------------------------------------------------------------
# Joining
# ----------------------------------------------------------------------

@org_bp.route('/join/<token>')
def join_page(token):
    """The invite link. Anonymous people get the sign-up page with the
    organization named; signed-in people get a confirm page."""
    org = find_org_by_token(token)
    if org is None:
        return render_template('Orgjoin.html', org=None,
                               invalid=INVALID_LINK, blocked=None)

    if 'user_id' not in session:
        return _render_register(org=org)

    user = _current_user()
    blocked = None
    if user.organization_id:
        blocked = "Leave your current organization before joining another."
    return render_template('Orgjoin.html', org=org, invalid=None,
                           blocked=blocked)


@org_bp.route('/join/<token>/request', methods=['POST'])
@login_required
def join_request(token):
    org = find_org_by_token(token)
    if org is None:
        flash(INVALID_LINK, "danger")
        return redirect(url_for('dashboard.index'))

    user = _current_user()
    if user.organization_id:
        flash("Leave your current organization before joining another.",
              "danger")
        return redirect(url_for('dashboard.index'))

    user.organization_id = org.organization_id
    user.org_role = 'member'
    user.org_status = 'pending'
    log_action('join_request', 'users', user.user_id,
               f"Asked to join {org.organization_name}")
    db.session.commit()
    flash(f"Request sent to {org.organization_name}. Your leader will "
          "review it.", "success")
    return redirect(url_for('dashboard.index'))


@org_bp.route('/org/leave', methods=['POST'])
@login_required
def leave_org():
    user = _current_user()
    if not user.organization_id:
        return redirect(url_for('dashboard.my_account'))

    if is_last_active_leader(user):
        flash("Appoint another leader first.", "danger")
        return redirect(url_for('dashboard.my_account'))

    org = db.session.get(Organization, user.organization_id)
    name = org.organization_name if org else "the organization"
    clear_membership(user)
    log_action('leave_org', 'users', user.user_id, f"Left {name}")
    db.session.commit()
    flash(f"You have left {name}.", "success")
    return redirect(url_for('dashboard.my_account'))


# ----------------------------------------------------------------------
# Members page
# ----------------------------------------------------------------------

@org_bp.route('/org/members')
@login_required
def members_page():
    """A leader's own organization. Taken from the account, not the URL."""
    user = _current_user()
    org = (db.session.get(Organization, user.organization_id)
           if user.organization_id else None)
    if org is None or not is_active_leader_of(user, org):
        abort(403)
    return _members_view(org, user)


@org_bp.route('/org/<int:org_id>/members')
@login_required
def org_members_page(org_id):
    """Any organization the viewer may see: leaders, CENRO admins, the
    provincial office."""
    user = _current_user()
    org = db.session.get(Organization, org_id)
    if org is None:
        abort(404)
    if not can_view(user, org):
        abort(403)
    return _members_view(org, user)


def _members_view(org, user):
    if not org.join_token:
        ensure_join_token(org)
        db.session.commit()

    waiting = (User.query
               .filter(User.organization_id == org.organization_id,
                       User.org_status == 'pending',
                       User.email_verified.is_(True))
               .order_by(User.username).all())
    members = (User.query
               .filter(User.organization_id == org.organization_id,
                       User.org_status == 'active')
               .order_by(User.org_role.desc(), User.username).all())

    invite_url = url_for('organization.join_page', token=org.join_token,
                         _external=True)
    return render_template(
        'Orgmembers.html',
        active_page='my_org',
        org=org,
        me=user,
        waiting=waiting,
        members=members,
        invite_url=invite_url,
        can_approve=can_approve(user, org),
        can_appoint=can_appoint_leaders(user, org),
    )


# ----------------------------------------------------------------------
# Approving, rejecting, removing members
# ----------------------------------------------------------------------

@org_bp.route('/org/<int:org_id>/members/<int:user_id>/approve',
              methods=['POST'])
@login_required
def approve_member(org_id, user_id):
    actor = _current_user()
    org, target = _load(org_id, user_id)
    if not can_approve(actor, org) or not can_act_on(actor, org, target):
        abort(403)

    if target.org_status != 'pending' or not target.email_verified:
        flash("That member is not waiting for approval.", "warning")
        return redirect(_members_url(org))

    target.org_status = 'active'
    log_action('approve_member', 'users', target.user_id,
               f"Approved {target.username} into {org.organization_name}")
    db.session.commit()
    flash(f"{target.username} is now a member.", "success")
    return redirect(_members_url(org))


@org_bp.route('/org/<int:org_id>/members/<int:user_id>/reject',
              methods=['POST'])
@login_required
def reject_member(org_id, user_id):
    actor = _current_user()
    org, target = _load(org_id, user_id)
    if not can_approve(actor, org) or not can_act_on(actor, org, target):
        abort(403)

    if target.org_status != 'pending':
        flash("That member is not waiting for approval.", "warning")
        return redirect(_members_url(org))

    name = target.username
    clear_membership(target)
    log_action('reject_member', 'users', target.user_id,
               f"Rejected {name} from {org.organization_name}")
    db.session.commit()
    flash(f"{name} was not approved.", "success")
    return redirect(_members_url(org))


@org_bp.route('/org/<int:org_id>/members/<int:user_id>/remove',
              methods=['POST'])
@login_required
def remove_member(org_id, user_id):
    actor = _current_user()
    org, target = _load(org_id, user_id)

    # Removing a leader needs a leader-level admin. Removing a member needs
    # approval rights. can_act_on also refuses leaders for other actors.
    if target.org_role == 'leader':
        allowed = can_appoint_leaders(actor, org)
    else:
        allowed = can_approve(actor, org)
    if not allowed or not can_act_on(actor, org, target):
        abort(403)

    if target.org_status not in ('active', 'pending'):
        flash("That user is not a member.", "warning")
        return redirect(_members_url(org))

    name = target.username
    clear_membership(target)
    log_action('remove_member', 'users', target.user_id,
               f"Removed {name} from {org.organization_name}")
    db.session.commit()
    flash(f"{name} was removed from {org.organization_name}.", "success")
    return redirect(_members_url(org))


# ----------------------------------------------------------------------
# Leaders
# ----------------------------------------------------------------------

@org_bp.route('/org/<int:org_id>/leaders/<int:user_id>/appoint',
              methods=['POST'])
@login_required
def appoint_leader(org_id, user_id):
    actor = _current_user()
    org, target = _load(org_id, user_id)
    if (not can_appoint_leaders(actor, org)
            or target.organization_id != org.organization_id
            or target.user_id == actor.user_id):
        abort(403)

    if target.org_status != 'active':
        flash("Only an active member can be made leader.", "warning")
        return redirect(_members_url(org))
    if target.org_role == 'leader':
        flash(f"{target.username} is already a leader.", "warning")
        return redirect(_members_url(org))

    target.org_role = 'leader'
    log_action('appoint_leader', 'users', target.user_id,
               f"Made {target.username} leader of {org.organization_name}")
    db.session.commit()
    flash(f"{target.username} is now a leader.", "success")
    return redirect(_members_url(org))


@org_bp.route('/org/<int:org_id>/leaders/<int:user_id>/remove',
              methods=['POST'])
@login_required
def remove_leader(org_id, user_id):
    actor = _current_user()
    org, target = _load(org_id, user_id)
    if (not can_appoint_leaders(actor, org)
            or target.organization_id != org.organization_id
            or target.user_id == actor.user_id):
        abort(403)

    if target.org_role != 'leader':
        flash(f"{target.username} is not a leader.", "warning")
        return redirect(_members_url(org))

    target.org_role = 'member'
    log_action('remove_leader', 'users', target.user_id,
               f"Removed {target.username} as leader of "
               f"{org.organization_name}")
    db.session.commit()
    flash(f"{target.username} is no longer a leader.", "success")
    return redirect(_members_url(org))


# ----------------------------------------------------------------------
# Join link
# ----------------------------------------------------------------------

@org_bp.route('/org/<int:org_id>/token/regenerate', methods=['POST'])
@login_required
def regenerate_token(org_id):
    actor = _current_user()
    org = db.session.get(Organization, org_id)
    if org is None:
        abort(404)
    if not can_approve(actor, org):
        abort(403)

    org.join_token = new_join_token()
    log_action('regenerate_join_link', 'organization', org.organization_id,
               f"New join link for {org.organization_name}. The old link "
               "no longer works.")
    db.session.commit()
    flash("A new invite link was made. The old link no longer works.",
          "success")
    return redirect(_members_url(org))


# ----------------------------------------------------------------------
# CENRO and provincial list
# ----------------------------------------------------------------------

@org_bp.route('/org/organizations')
@login_required
def organizations_list():
    """Organizations in the admin's CENRO. The provincial office sees all."""
    user = _current_user()
    if user.role not in ('admin', 'superadmin'):
        abort(403)

    if is_provincial(user):
        orgs = Organization.query.order_by(Organization.organization_name).all()
    elif user.cenro:
        orgs = (Organization.query
                .filter(Organization.cenro == user.cenro)
                .order_by(Organization.organization_name).all())
    else:
        abort(403)

    rows = []
    for org in orgs:
        base = (User.organization_id == org.organization_id)
        rows.append({
            'org': org,
            'members': User.query.filter(
                base, User.org_status == 'active').count(),
            'leaders': User.query.filter(
                base, User.org_role == 'leader',
                User.org_status == 'active').count(),
            'waiting': User.query.filter(
                base, User.org_status == 'pending').count(),
        })
    return render_template('Orglist.html', active_page='orgs', rows=rows,
                           provincial=is_provincial(user))
