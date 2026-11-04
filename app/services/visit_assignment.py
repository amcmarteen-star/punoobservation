"""
Assigning field officers to site visits, and closing a site.

Both the create-site form (admin.create_site_from_request) and the site's
visits page (app/routes/visits.py) assign officers, so the rules live here.
The caller checks who may do this and commits. Emails go out after the
commit, like every other email: email_assignment().
"""

from app.extensions import db
from app.models import (
    MonitoringReport, Notification, SiteVisit, User, VisitAssignment,
)
from app.services.boundary_publication import NOT_SUITABLE
from app.services.mailer import email_link, send_template
from app.utils.timeutil import manila_now

VISIT_TYPES = ('Pre-planting check', 'Planting confirmed')


def officers_for(cenro):
    """The active field officers who can be sent to a site of this CENRO."""
    if not cenro:
        return []
    return (User.query
            .filter(User.role == 'field_officer', User.cenro == cenro,
                    User.is_active.is_(True))
            .order_by(User.username)
            .all())


def open_assignment_for(site, user_id):
    """This officer's oldest open assignment on the site, or None."""
    return (VisitAssignment.query
            .filter_by(site_id=site.site_id, officer_id=user_id, status='Open')
            .order_by(VisitAssignment.created_at)
            .first())


def assignment_problem(site, officer_id, visit_type, target_date, today):
    """What is wrong with this assignment, as a message, or None."""
    if site.site_status == NOT_SUITABLE:
        return "This site was found not suitable and is closed."
    officer = db.session.get(User, officer_id) if officer_id else None
    if (officer is None or officer.role != 'field_officer'
            or officer.cenro != site.cenro or not officer.is_active):
        return "Choose a field officer from this site's CENRO."
    if visit_type not in VISIT_TYPES:
        return "Choose the type of visit."
    if target_date is not None and target_date < today:
        return "The target date cannot be in the past."
    return None


def assign_officer(site, officer_id, visit_type, target_date, note, assigned_by):
    """Add the assignment and the officer's notification. Check
    assignment_problem() first."""
    assignment = VisitAssignment(
        site_id=site.site_id, officer_id=officer_id, assigned_by=assigned_by,
        visit_type=visit_type, target_date=target_date, note=note or None,
        status='Open',
    )
    db.session.add(assignment)
    where = (f"{site.location.barangay}, {site.location.municipality}"
             if site.location else site.site_name)
    due = f" by {target_date.strftime('%d %b %Y')}" if target_date else ""
    db.session.add(Notification(
        user_id=officer_id, notification_type='Site Visit',
        site_id=site.site_id, is_read=False,
        message=(f"You are assigned a site visit ({visit_type.lower()}) to "
                 f"{site.site_name}, {where}{due}."),
    ))
    return assignment


def email_assignment(assignment):
    """Tell the officer by email. Call after the commit."""
    site = assignment.site
    officer = assignment.officer
    send_template(
        'visit_assigned', to=officer.email_address,
        subject=f"Site visit assigned: {site.site_name}",
        name=officer.username,
        site_name=site.site_name,
        where=(f"{site.location.barangay}, {site.location.municipality}"
               if site.location else site.site_name),
        visit_type=assignment.visit_type,
        target_date=(assignment.target_date.strftime('%d %b %Y')
                     if assignment.target_date else None),
        note=assignment.note,
        assigned_by=assignment.assigner.username if assignment.assigner else "Your CENRO",
        visit_url=email_link('visits.site_visits', site_id=site.site_id),
    )


def close_site(site, reason, actor_id):
    """
    Close a site that will not go ahead: it is marked Not Suitable, every
    boundary still waiting for the province is declined with the reason so
    it can never reach the public map, and open assignments are withdrawn.
    """
    site.site_status = NOT_SUITABLE
    now = manila_now()
    for model in (SiteVisit, MonitoringReport):
        for source in model.query.filter(
                model.site_id == site.site_id,
                model.publication_status == 'Pending Publication'):
            source.publication_status = 'Declined'
            source.publication_note = f"Declined automatically: {reason}"
            source.published_at = now
            source.published_by = actor_id
    for assignment in VisitAssignment.query.filter_by(site_id=site.site_id,
                                                      status='Open'):
        assignment.status = 'Cancelled'
        db.session.add(Notification(
            user_id=assignment.officer_id, notification_type='Site Visit',
            site_id=site.site_id, is_read=False,
            message=(f"Your site visit to {site.site_name} is no longer "
                     f"needed: {reason}"),
        ))
