"""
Site visits: field validation of a site made from a request.

A temporary site (created by a CENRO from an approved request) has no
seedlings to count yet, so a monitoring report does not fit its first
field visits. A site visit checks the land instead, can walk the corners
for a GPS boundary, and can confirm planting. See SiteVisit in
app/models.py.

THE FLOW

    field officer   records a visit from the site's page or the GIS map
                    (Site visits button on a temporary site)
    CENRO admin     approves or rejects it. On approval:
                      Suitable      a captured boundary goes to Boundary
                                    Publications; a planting confirmation
                                    writes the seedlings actually planted
                                    to the planting record
                      Not suitable  the CENRO suggests a new planting
                                    site; the site is marked Not Suitable
                                    and the requester is told
    provincial      publishes or declines the boundary, exactly as for a
    admin           monitoring report (services/boundary_publication.py)

WHO SEES WHAT

    Staff only (field officers, admins). A CENRO's staff see their own
    CENRO's sites; province-wide staff see every site. Only a field
    officer of the site's CENRO records a visit, and only that CENRO's
    admin reviews it. A decision is final: a new visit is recorded
    instead of reopening one.
"""

from datetime import datetime

from flask import (
    Blueprint, render_template, request, redirect, url_for, flash, session,
    current_app, abort,
)

from app.extensions import db
from sqlalchemy.orm import contains_eager, selectinload

from app.models import (
    Location, Notification, ReforestationRecord, Site, SiteVisit,
    SiteVisitPhoto,
)
from app.services.boundary_publication import (
    NOT_SUITABLE, apply_publication, publication_problem,
)
from app.services.mailer import email_link, send_template
from app.services.monitoring import build_boundary, inspect_photo, save_photo
from app.services.request_site import proposed_area_for_site
from app.utils.audit import log_action
from app.utils.decorators import admin_required, login_required
from app.utils.jurisdiction import (
    allowed_municipalities, can_see_unofficial_sites, current_cenro,
    boundary_publishers, reviewing_admins, scope_sites,
)
from app.utils.security import upload_problem
from app.utils.timeutil import manila_now

visits_bp = Blueprint('visits', __name__)

VISIT_TYPES = ('Pre-planting check', 'Planting confirmed')
FINDINGS = ('Suitable', 'Not suitable')
# the land check on the form: (field, question)
LAND_CHECKS = (
    ('land_matches', "Does the land match what the request describes?"),
    ('ownership_confirmed', "Is the land ownership confirmed?"),
    ('accessible', "Can the site be reached for planting and monitoring?"),
)


# ----------------------------------------------------------------------
# access
# ----------------------------------------------------------------------

def _can_view(site):
    """Staff, and for CENRO staff only their own CENRO's sites."""
    if not can_see_unofficial_sites():
        return False
    cenro = current_cenro()
    return cenro is None or site.cenro == cenro


def _can_record(site):
    """A field officer of the site's CENRO."""
    return (session.get('role') == 'field_officer'
            and current_cenro() == site.cenro and site.cenro is not None)


def _can_review(site):
    """An admin of the site's CENRO. Province-wide admins observe."""
    return (session.get('role') == 'admin'
            and current_cenro() is not None and current_cenro() == site.cenro)


def _visitable_site(site_id):
    """The site, if it takes visits (made from a request) and the user
    may see it; otherwise a redirect to send them away with."""
    site = db.session.get(Site, site_id)
    if site is None or not _can_view(site):
        flash("That site is not in your jurisdiction.", "danger")
        return None, redirect(url_for('dashboard.Reforestation_sites'))
    if site.source_request_id is None:
        flash("Site visits are for sites made from a request. Use a "
              "monitoring report for this site.", "warning")
        return None, redirect(url_for('dashboard.Reforestation_sites'))
    return site, None


def _today():
    """Today in the Philippines (app/utils/timeutil.py keeps Manila time)."""
    return manila_now().date()


def _parse_date(value):
    try:
        return datetime.strptime(value or '', '%Y-%m-%d').date()
    except ValueError:
        return None


def _yes_no(value):
    return {'yes': True, 'no': False}.get(value)


# ----------------------------------------------------------------------
# every site that takes visits (the field officer's sidebar link)
# ----------------------------------------------------------------------

@visits_bp.route('/site-visits')
@login_required
def index():
    """
    The sites made from a request in the user's area, with where each one
    stands, so an officer sees at a glance which still need a visit.

    Sites waiting for field work come first: no visit yet, then a visit
    pending review. Published and Not Suitable sites go to the end.
    """
    if not can_see_unofficial_sites():
        flash("Site visits are for DENR staff.", "warning")
        return redirect(url_for('dashboard.index'))

    # Locations come with the join, and every site's visits in one more
    # query, so the page costs the same few queries for 2 sites or 200.
    sites = (scope_sites(Site.query.join(Location,
                                         Site.location_id == Location.location_id))
             .filter(Site.source_request_id.isnot(None))
             .options(contains_eager(Site.location),
                      selectinload(Site.site_visits))
             .order_by(Location.municipality, Location.barangay, Site.site_name)
             .all())

    rows = []
    for site in sites:
        visits = site.site_visits           # newest first (see the model)
        latest = visits[0] if visits else None
        if site.site_status == NOT_SUITABLE:
            stage, order = 'Not suitable', 5
        elif site.boundary_published:
            stage, order = 'Boundary published', 4
        elif any(v.status == 'Pending' for v in visits):
            stage, order = 'Visit waiting for review', 1
        elif any(v.publication_status == 'Pending Publication' for v in visits):
            stage, order = 'Boundary waiting for the province', 2
        elif not visits:
            stage, order = 'Needs a first visit', 0
        else:
            stage, order = 'Visited', 3
        rows.append({'site': site, 'count': len(visits), 'latest': latest,
                     'stage': stage, 'order': order})
    rows.sort(key=lambda r: r['order'])

    return render_template(
        'Sitevisitsindex.html',
        active_page='site_visits',
        rows=rows,
        is_officer=session.get('role') == 'field_officer',
    )


# ----------------------------------------------------------------------
# a site's visits
# ----------------------------------------------------------------------

@visits_bp.route('/sites/<int:site_id>/visits')
@login_required
def site_visits(site_id):
    site, stop = _visitable_site(site_id)
    if stop:
        return stop
    return render_template(
        'Sitevisits.html',
        active_page='site_visits',
        site=site,
        req=site.source_request,
        proposed=proposed_area_for_site(site),
        visits=site.site_visits,
        # a site found not suitable is closed: no new visits
        can_record=_can_record(site) and site.site_status != NOT_SUITABLE,
        not_suitable=site.site_status == NOT_SUITABLE,
    )


@visits_bp.route('/sites/<int:site_id>/visits/new', methods=['GET', 'POST'])
@login_required
def new_visit(site_id):
    site, stop = _visitable_site(site_id)
    if stop:
        return stop
    if not _can_record(site):
        flash("Only a field officer of this site's CENRO can record a "
              "site visit.", "warning")
        return redirect(url_for('visits.site_visits', site_id=site_id))
    if site.site_status == NOT_SUITABLE:
        flash("This site was found not suitable and is closed. The requester "
              "was offered another site.", "warning")
        return redirect(url_for('visits.site_visits', site_id=site_id))

    def render(form, errors=()):
        for e in errors:
            flash(e, "danger")
        return render_template(
            'Sitevisitform.html',
            active_page='site_visits',
            site=site,
            req=site.source_request,
            form=form,
            visit_types=VISIT_TYPES,
            findings=FINDINGS,
            land_checks=LAND_CHECKS,
            today=_today().isoformat(),
        )

    if request.method == 'GET':
        return render({'visit_date': _today().isoformat(),
                       'visit_type': VISIT_TYPES[0]})

    form = request.form
    errors = []

    visit_date = _parse_date(form.get('visit_date'))
    if visit_date is None:
        errors.append("Enter the date of the visit.")
    elif visit_date > _today():
        errors.append("The visit date cannot be in the future.")

    visit_type = form.get('visit_type')
    if visit_type not in VISIT_TYPES:
        errors.append("Choose the type of visit.")
    finding = form.get('finding')
    if finding not in FINDINGS:
        errors.append("Choose whether the site is suitable.")

    remarks = (form.get('remarks') or '').strip() or None
    if finding == 'Not suitable' and not remarks:
        errors.append("Say why the site is not suitable, in the remarks.")

    planted = date_planted = None
    if visit_type == 'Planting confirmed':
        if finding == 'Not suitable':
            errors.append("A planting confirmation cannot find the site "
                          "not suitable. Record a pre-planting check instead.")
        raw = (form.get('seedlings_planted') or '').replace(',', '').strip()
        planted = int(raw) if raw.isdigit() else None
        if not planted:
            errors.append("Enter how many seedlings were actually planted.")
        date_planted = _parse_date(form.get('date_planted'))
        if date_planted is None:
            errors.append("Enter the date the seedlings were planted.")
        elif date_planted > _today():
            errors.append("The planting date cannot be in the future.")

    site_files = request.files.getlist('site_photos')
    corner_files = request.files.getlist('boundary_photos')
    problem = upload_problem(site_files + corner_files)
    if problem:
        errors.append(problem)

    if errors:
        return render(form, errors)

    visit = SiteVisit(
        site_id=site.site_id,
        user_id=session.get('user_id'),
        visit_date=visit_date,
        visit_type=visit_type,
        finding=finding,
        remarks=remarks,
        seedlings_planted=planted,
        date_planted=date_planted,
        status='Pending',
        **{field: _yes_no(form.get(field)) for field, _ in LAND_CHECKS},
    )
    db.session.add(visit)
    db.session.flush()          # visit_id for the photo file names

    # --- photos: the same checks as a monitoring report ---
    from app.routes.dashboard import _load_barangay_geometry
    geom = (_load_barangay_geometry(site.location.municipality,
                                    site.location.barangay)
            if site.location else None)
    seen = set()
    corners = []
    index = 0
    for files, kind in ((site_files, 'site'), (corner_files, 'boundary')):
        for f in files:
            if not f or not f.filename:
                continue
            index += 1
            meta, flags, inside, distance = inspect_photo(
                f, visit_date, geom, site.location, seen)
            path = save_photo(f, current_app.static_folder,
                              f"v{visit.visit_id}", index)
            db.session.add(SiteVisitPhoto(
                visit_id=visit.visit_id, photo_url=path,
                file_hash=meta['file_hash'], photo_type=kind,
                latitude=meta['latitude'], longitude=meta['longitude'],
                date_time_taken=meta['date_time_taken'],
                inside_boundary=inside, distance_from_centroid_m=distance,
                flags=','.join(flags) if flags else None,
            ))
            if kind == 'boundary' and meta['latitude'] is not None:
                corners.append((meta['longitude'], meta['latitude']))

    boundary_msg = None
    if corners:
        b = build_boundary(corners, site.area_size_ha)
        if b['ok']:
            visit.boundary_geojson = b['geojson']
            visit.captured_area_ha = b['area_ha']
            visit.area_difference_pct = b['difference_pct']
            boundary_msg = (f"Boundary captured: {b['area_ha']} ha from "
                            f"{b['points_used']} corners.")
            for w in b['warnings']:
                flash(w, "warning")
        else:
            boundary_msg = b['reason']

    where = (f"{site.location.barangay}, {site.location.municipality}"
             if site.location else site.site_name)
    for admin in reviewing_admins(site.cenro):
        db.session.add(Notification(
            user_id=admin.user_id, notification_type='Site Visit',
            visit_id=visit.visit_id, is_read=False,
            message=(f"{session.get('username')} recorded a site visit for "
                     f"{site.site_name} ({where}): {finding.lower()}."),
        ))
    log_action('submit_site_visit', 'site_visit', visit.visit_id,
               f"{visit_type} for {site.site_name}: {finding}")
    db.session.commit()

    flash("Site visit recorded. It is waiting for your CENRO to review.",
          "success")
    if boundary_msg:
        flash(boundary_msg, "info")
    return redirect(url_for('visits.visit_detail', visit_id=visit.visit_id))


# ----------------------------------------------------------------------
# one visit, and the CENRO's decision
# ----------------------------------------------------------------------

@visits_bp.route('/visits/<int:visit_id>')
@login_required
def visit_detail(visit_id):
    visit = db.session.get(SiteVisit, visit_id)
    if visit is None or not _can_view(visit.site):
        flash("That site visit is not in your jurisdiction.", "danger")
        return redirect(url_for('dashboard.Reforestation_sites'))
    site = visit.site
    munis = allowed_municipalities()
    suggest_munis = sorted(munis) if munis is not None else []
    return render_template(
        'Sitevisitdetail.html',
        active_page='site_visits',
        visit=visit,
        site=site,
        req=site.source_request,
        proposed=proposed_area_for_site(site),
        site_photos=[p for p in visit.photos if p.photo_type == 'site'],
        corner_photos=[p for p in visit.photos if p.photo_type == 'boundary'],
        land_checks=LAND_CHECKS,
        can_review=_can_review(site) and visit.status == 'Pending',
        suggest_munis=suggest_munis,
    )


@visits_bp.route('/visits/<int:visit_id>/review', methods=['POST'])
@admin_required
def review_visit(visit_id):
    visit = db.session.get(SiteVisit, visit_id)
    if visit is None or not _can_review(visit.site):
        flash("Site visits are reviewed by the CENRO of the site.", "danger")
        return redirect(url_for('dashboard.Reforestation_sites'))
    back = redirect(url_for('visits.visit_detail', visit_id=visit_id))
    if visit.status != 'Pending':
        flash(f"This visit was already {visit.status.lower()}.", "warning")
        return back

    site = visit.site
    status = request.form.get('status')
    note = (request.form.get('review_note') or '').strip() or None
    if status not in ('Approved', 'Rejected'):
        flash("Choose Approve or Reject.", "danger")
        return back
    if status == 'Rejected' and not note:
        flash("Give a reason when rejecting a visit.", "danger")
        return back
    # A site already found not suitable is closed. A visit recorded before
    # that can still be rejected, but approving it would reopen nothing.
    if status == 'Approved' and site.site_status == NOT_SUITABLE:
        flash("This site was already found not suitable, so this visit "
              "cannot be approved. Reject it with a note instead.", "danger")
        return back

    suggested = None
    suggestion = (request.form.get('suggestion_note') or '').strip() or None
    not_suitable = status == 'Approved' and visit.finding == 'Not suitable'
    if not_suitable:
        if not suggestion:
            flash("Suggest a new planting site for the requester before "
                  "approving a Not suitable finding.", "danger")
            return back
        muni = request.form.get('suggested_municipality') or ''
        brgy = request.form.get('suggested_barangay') or ''
        if muni or brgy:
            munis = allowed_municipalities()
            suggested = Location.query.filter_by(municipality=muni,
                                                 barangay=brgy).first()
            if suggested is None or (munis is not None and muni not in munis):
                flash("Choose the suggested barangay from your CENRO's "
                      "list, or leave it empty and describe it in words.",
                      "danger")
                return back

    visit.status = status
    visit.review_note = note
    visit.reviewed_by = session.get('user_id')
    visit.date_reviewed = manila_now()

    if status == 'Approved' and not not_suitable:
        # the seedlings actually planted: what later survival rates need
        if visit.seedlings_planted:
            record = (ReforestationRecord.query.filter_by(site_id=site.site_id)
                      .order_by(ReforestationRecord.date_planted.desc()).first())
            if record:
                record.actual_quantity_planted = visit.seedlings_planted
                record.date_planted = visit.date_planted
            else:
                # kept on the visit, but survival rates cannot use it
                flash("This site has no planting record, so the seedlings "
                      "planted were kept on the visit only. Ask a system "
                      "administrator to add the planting record.", "warning")
        # the boundary goes to the province, like a monitoring report's
        if visit.boundary_geojson:
            visit.publication_status = 'Pending Publication'
            for u in boundary_publishers():
                db.session.add(Notification(
                    user_id=u.user_id, notification_type='Site Visit',
                    visit_id=visit.visit_id, is_read=False,
                    message=(f"Boundary awaiting publication: {site.site_name} "
                             f"({visit.captured_area_ha} ha, from a site visit)."),
                ))

    if not_suitable:
        visit.suggested_location_id = suggested.location_id if suggested else None
        visit.suggestion_note = suggestion
        site.site_status = NOT_SUITABLE
        _decline_waiting_boundaries(site, visit)
        _tell_requester_not_suitable(visit, site, suggested, suggestion)

    db.session.add(Notification(
        user_id=visit.user_id, notification_type='Site Visit',
        visit_id=visit.visit_id, is_read=False,
        message=(f"Your site visit for {site.site_name} was {status.lower()}."
                 + (f" Note: {note}" if note else "")),
    ))
    log_action('review_site_visit', 'site_visit', visit.visit_id,
               f"Marked {status}" + (f": {note}" if note else "")
               + (" (site not suitable)" if not_suitable else ""))
    db.session.commit()

    if not_suitable:
        _email_requester_not_suitable(visit, site, suggested, suggestion)

    flash(f"Site visit {status.lower()}.", "success")
    return back




def _decline_waiting_boundaries(site, visit):
    """
    A site found not suitable must never reach the public map, so every
    boundary still waiting in the publication queue for it, from earlier
    visits or monitoring reports, is declined with the reason.
    """
    from app.models import MonitoringReport
    reason = (f"Declined automatically: site visit #{visit.visit_id} found "
              "the site not suitable for planting.")
    for model in (SiteVisit, MonitoringReport):
        for source in model.query.filter(
                model.site_id == site.site_id,
                model.publication_status == 'Pending Publication'):
            source.publication_status = 'Declined'
            source.publication_note = reason
            source.published_at = manila_now()
            source.published_by = session.get('user_id')


def _suggestion_words(suggested, suggestion):
    place = (f"{suggested.barangay}, {suggested.municipality}. "
             if suggested else "")
    return place + suggestion


def _tell_requester_not_suitable(visit, site, suggested, suggestion):
    req = site.source_request
    if req is None:
        return
    db.session.add(Notification(
        user_id=req.user_id, notification_type='Request Update', is_read=False,
        message=(f"A field visit found the site for your request #"
                 f"{req.request_id} not suitable for planting. The CENRO "
                 f"suggests: {_suggestion_words(suggested, suggestion)}"),
    ))


def _email_requester_not_suitable(visit, site, suggested, suggestion):
    """After the commit, like every other email: the decision stands
    whether or not it goes out."""
    req = site.source_request
    if req is None:
        return
    to = req.requester.email_address if req.requester else None
    contact = (req.contact_email or '').strip().lower()
    send_template(
        'site_not_suitable',
        to=to or contact,
        cc=contact if to and contact != to.lower() else None,
        subject="Your requested planting site: a new site is suggested",
        name=req.contact_name or (req.requester.username if req.requester else "there"),
        request_id=req.request_id,
        where=(f"{req.location.barangay}, {req.location.municipality}"
               if req.location else site.site_name),
        reason=visit.remarks,
        suggested=(f"{suggested.barangay}, {suggested.municipality}"
                   if suggested else None),
        suggestion=suggestion,
        requests_url=email_link('dashboard.requests_page'),
    )


# ----------------------------------------------------------------------
# publishing a visit's boundary (Boundary Publications)
# ----------------------------------------------------------------------

@visits_bp.route('/admin/publications/visits/<int:visit_id>/publish',
                 methods=['POST'])
@admin_required
def publish_visit_boundary(visit_id):
    """The site-visit twin of admin.publish_boundary, with the same rules."""
    back = redirect(url_for('admin.publications'))
    if session.get('role') == 'superadmin':
        flash("That is an operational function, not a system one.", "warning")
        return redirect(url_for('admin.user_management'))
    if current_cenro() is not None:
        flash("Boundary publication is a provincial function.", "danger")
        return redirect(url_for('admin.provincial_overview'))

    visit = db.session.get(SiteVisit, visit_id)
    if visit is None:
        abort(404)
    action = (request.form.get('action') or '').strip()
    note = (request.form.get('publication_note') or '').strip()
    if action not in ('publish', 'decline', 'unpublish'):
        flash("Invalid action.", "danger")
        return back
    if visit.status != 'Approved' or visit.finding != 'Suitable':
        flash("Only an approved visit that found the site suitable can be "
              "published.", "danger")
        return back
    if not visit.boundary_geojson:
        flash("This visit has no captured boundary.", "danger")
        return back
    if action == 'decline' and not note:
        flash("Give a reason when declining a boundary.", "danger")
        return back
    problem = publication_problem(visit, action)
    if problem:
        flash(problem, "danger")
        return back

    site = visit.site
    msg = apply_publication(visit, action, note, session.get('user_id'),
                            manila_now())
    for uid in {visit.user_id, visit.reviewed_by} - {None}:
        db.session.add(Notification(
            user_id=uid, notification_type='Site Visit',
            visit_id=visit.visit_id, is_read=False,
            message=msg + (f" Note: {note}" if note else ""),
        ))
    log_action('publish_boundary', 'site', site.site_id,
               f"{action.title()} boundary for {site.site_name} "
               f"({visit.captured_area_ha} ha, site visit #{visit.visit_id})"
               + (f": {note}" if note else ""))
    db.session.commit()
    flash(msg, "success")
    return back
