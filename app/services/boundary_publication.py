"""
Publishing a captured site boundary.

A boundary is captured from GPS corner photos on either a monitoring
report or a site visit, approved by the site's CENRO, then published (or
declined) by the provincial administrator on Boundary Publications. Both
kinds go through apply_publication(), so they follow the same rules:

    publish     the boundary becomes the site's official one and shows on
                the public map; any boundary published for the site
                before it is set aside, so only one is ever official
    unpublish   off the map again, back in the queue
    decline     kept off the map; the caller requires a reason

The caller checks who may do this and commits.
"""

from app.models import MonitoringReport, SiteVisit

# Site.site_status once an approved visit finds the land not suitable
NOT_SUITABLE = 'Not Suitable'


def publication_problem(source, action):
    """
    Why action cannot be applied to source, as a message, or None.

    Both publish routes call this before apply_publication(), so a stale
    tab or a hand-made form cannot:
      - publish the boundary of a site found not suitable,
      - publish or decline a boundary that is already the published one,
      - withdraw a boundary that is not the published one, which would
        hide the site's real boundary from the map.
    """
    site = source.site
    published = source.publication_status == 'Published'
    if action == 'publish' and site.site_status == NOT_SUITABLE:
        return ("This site was found not suitable for planting, so its "
                "boundary cannot be published.")
    if action in ('publish', 'decline') and published:
        return "This boundary is already the published one."
    if action == 'unpublish' and not published:
        return ("Only the published boundary can be withdrawn. This one "
                "is not on the map.")
    return None


def apply_publication(source, action, note, user_id, now):
    """
    Apply action ('publish' | 'unpublish' | 'decline') to source, a
    MonitoringReport or SiteVisit with a boundary. Returns the message
    for the people told about it. Call publication_problem() first.
    """
    site = source.site
    is_visit = isinstance(source, SiteVisit)

    if action == 'publish':
        site.boundary_geojson = source.boundary_geojson
        site.boundary_area_ha = source.captured_area_ha
        site.boundary_captured_at = source.field_date
        site.boundary_published = True
        site.boundary_published_by = user_id
        site.boundary_published_at = now
        site.boundary_source_report_id = None if is_visit else source.report_id
        site.boundary_source_visit_id = source.visit_id if is_visit else None

        # only one boundary per site may be the published one
        for model, pk in ((MonitoringReport, MonitoringReport.report_id),
                          (SiteVisit, SiteVisit.visit_id)):
            others = model.query.filter(model.site_id == site.site_id,
                                        model.publication_status == 'Published')
            if isinstance(source, model):
                others = others.filter(pk != (source.visit_id if is_visit
                                              else source.report_id))
            others.update({'publication_status': 'Not Applicable'},
                          synchronize_session=False)

        source.publication_status = 'Published'
        message = f"Boundary published for {site.site_name}."
    elif action == 'unpublish':
        site.boundary_published = False
        source.publication_status = 'Pending Publication'
        message = f"Boundary withdrawn from the map for {site.site_name}."
    else:
        source.publication_status = 'Declined'
        message = f"Boundary declined for {site.site_name}."

    source.published_by = user_id
    source.published_at = now
    source.publication_note = note or None
    return message
