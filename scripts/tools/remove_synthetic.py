"""
Remove the simulated data, for deployment handover.

Simulated rows (Site.is_simulated, Organization.is_simulated) stand in for
districts without real records. They show a province-wide rollout during
the demonstration. Before the system is handed over for real use, they go.

DRY RUN BY DEFAULT. Nothing is changed unless --apply is given.

    python -m scripts.tools.remove_synthetic            # report only
    python -m scripts.tools.remove_synthetic --apply    # delete, one transaction

What --apply does, in this order, all in one transaction:
    - notifications that point at a simulated site, or its reports and visits
    - visit assignments, site visits (and their photos)
    - monitoring reports (and their plots and photos)
    - reforestation records, synthetic map areas
    - requests: the adopted site and the organization are cleared, the
      request itself is kept (it belongs to a real person)
    - the simulated sites
    - users in a simulated organization: membership cleared, account kept
    - the simulated organizations

Real rows are never touched. Take a database backup first.
"""

# Lets the file run with VS Code's Run button as well as python -m.
if __package__ in (None, ""):
    import os as _os, sys as _sys
    _sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.dirname(
        _os.path.abspath(__file__)))))
    import scripts  # noqa: F401

import argparse
import sys

from app.extensions import db
from app.models import (
    MonitoringPhoto, MonitoringPlot, MonitoringReport, Notification,
    Organization, ReforestationRecord, Request, Site, SiteVisit,
    SiteVisitPhoto, SyntheticSiteArea, User, VisitAssignment,
)
from scripts.common import app_context


def plan():
    """What would be removed, as (label, query) pairs. Queries only."""
    site_ids = [s for (s,) in db.session.query(Site.site_id)
                .filter(Site.is_simulated.is_(True)).all()]
    org_ids = [o for (o,) in db.session.query(Organization.organization_id)
               .filter(Organization.is_simulated.is_(True)).all()]
    report_ids = [r for (r,) in db.session.query(MonitoringReport.report_id)
                  .filter(MonitoringReport.site_id.in_(site_ids)).all()] if site_ids else []
    visit_ids = [v for (v,) in db.session.query(SiteVisit.visit_id)
                 .filter(SiteVisit.site_id.in_(site_ids)).all()] if site_ids else []
    return site_ids, org_ids, report_ids, visit_ids


def _count(query):
    return query.count()


def report(site_ids, org_ids, report_ids, visit_ids):
    rows = [
        ('simulated sites', len(site_ids)),
        ('simulated organizations', len(org_ids)),
        ('reforestation records', _count(ReforestationRecord.query.filter(
            ReforestationRecord.site_id.in_(site_ids))) if site_ids else 0),
        ('monitoring reports', len(report_ids)),
        ('site visits', len(visit_ids)),
        ('visit assignments', _count(VisitAssignment.query.filter(
            VisitAssignment.site_id.in_(site_ids))) if site_ids else 0),
        ('synthetic map areas', _count(SyntheticSiteArea.query.filter(
            SyntheticSiteArea.site_id.in_(site_ids))) if site_ids else 0),
        ('requests to unlink (kept)', _count(Request.query.filter(
            db.or_(Request.adopted_site_id.in_(site_ids or [-1]),
                   Request.organization_id.in_(org_ids or [-1]))))),
        ('users to unlink from an organization (kept)', _count(User.query.filter(
            User.organization_id.in_(org_ids or [-1])))),
    ]
    width = max(len(label) for label, _ in rows)
    for label, n in rows:
        print(f"  {label.ljust(width)}  {n}")


def apply(site_ids, org_ids, report_ids, visit_ids):
    s = db.session
    none = [-1]
    s.query(Notification).filter(db.or_(
        Notification.site_id.in_(site_ids or none),
        Notification.report_id.in_(report_ids or none),
        Notification.visit_id.in_(visit_ids or none),
    )).delete(synchronize_session=False)
    s.query(VisitAssignment).filter(
        VisitAssignment.site_id.in_(site_ids or none)).delete(synchronize_session=False)
    s.query(SiteVisitPhoto).filter(
        SiteVisitPhoto.visit_id.in_(visit_ids or none)).delete(synchronize_session=False)
    s.query(SiteVisit).filter(
        SiteVisit.visit_id.in_(visit_ids or none)).delete(synchronize_session=False)
    s.query(MonitoringPhoto).filter(
        MonitoringPhoto.report_id.in_(report_ids or none)).delete(synchronize_session=False)
    s.query(MonitoringPlot).filter(
        MonitoringPlot.report_id.in_(report_ids or none)).delete(synchronize_session=False)
    s.query(MonitoringReport).filter(
        MonitoringReport.report_id.in_(report_ids or none)).delete(synchronize_session=False)
    s.query(ReforestationRecord).filter(
        ReforestationRecord.site_id.in_(site_ids or none)).delete(synchronize_session=False)
    s.query(SyntheticSiteArea).filter(
        SyntheticSiteArea.site_id.in_(site_ids or none)).delete(synchronize_session=False)
    s.query(Request).filter(Request.adopted_site_id.in_(site_ids or none)).update(
        {Request.adopted_site_id: None}, synchronize_session=False)
    s.query(Request).filter(Request.organization_id.in_(org_ids or none)).update(
        {Request.organization_id: None}, synchronize_session=False)
    s.query(Site).filter(Site.site_id.in_(site_ids or none)).delete(
        synchronize_session=False)
    s.query(User).filter(User.organization_id.in_(org_ids or none)).update(
        {User.organization_id: None, User.org_role: None, User.org_status: None},
        synchronize_session=False)
    s.query(Organization).filter(
        Organization.organization_id.in_(org_ids or none)).delete(
        synchronize_session=False)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--apply', action='store_true',
                        help='delete the simulated rows (default: report only)')
    args = parser.parse_args(argv)

    with app_context():
        ids = plan()
        print("Simulated data found:")
        report(*ids)
        if not args.apply:
            print("\nDry run. Nothing was changed. Use --apply to delete.")
            return 0
        try:
            apply(*ids)
            db.session.commit()
        except Exception as exc:
            db.session.rollback()
            print(f"\nStopped, nothing was changed: {exc}")
            return 1
        print("\nRemoved. Real rows were not touched.")
        return 0


if __name__ == '__main__':
    sys.exit(main())
