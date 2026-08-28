# app/routes/admin.py
from flask import Blueprint, render_template, request, flash, redirect, url_for, session, jsonify
from app.extensions import db
from app.models import User, Location, Organization, Site, TreeSpecie, ReforestationRecord, Request, Notification, MonitoringReport, MonitoringPlot, MonitoringPhoto,ReforestationRecord,Site
from app.utils.decorators import admin_required
import pandas as pd
from datetime import datetime as dt
from datetime import datetime
from dateutil import parser as date_parser
from sqlalchemy import or_
from zoneinfo import ZoneInfo
from app.models import Request as ReforestationRequest

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


@admin_bp.route('/users/create', methods=['POST'])
@admin_required
def create_field_officer():
    username = request.form.get('username', '').strip().lower()
    email = request.form.get('email_address', '').strip().lower()
    password = request.form.get('password')
    role = request.form.get('role', 'field_officer') # Admin assigns role here

    existing_user = User.query.filter(
        (User.username == username) | (User.email_address == email)
    ).first()

    if existing_user:
        flash("Username or Email already exists.", "danger")
        return redirect(url_for('admin.manage_users'))

    ALLOWED_ROLES = ['normal_user', 'field_officer', 'admin']
    if role not in ALLOWED_ROLES:
        role = 'field_officer'

    new_user = User(
        username=username,
        email_address=email,
        role=role
    )
    new_user.set_password(password)

    db.session.add(new_user)
    db.session.commit()

    flash(f"User {username} successfully created as {role}.", "success")
    return redirect(url_for('admin.user_management'))


# ============================================================
# DENR NGP EXCEL IMPORT -- "Reference Dataset" page
# ============================================================

# any sheet whose row-3 header contains these columns is treated as a
# DENR NGP contract-profile sheet -- no need to hardcode year names like
# '2021', '2022'... future sheets (2024, 2025, etc) get picked up automatically
REQUIRED_DENR_COLUMNS = {'BARANGAY', 'MUNICIPALITY', 'SITE CODE'}

DEFAULT_REGION = 'Region I'
DEFAULT_PROVINCE = 'Pangasinan'

PLACEHOLDER_SPECIES_NAME = 'Unspecified (Pending Match)'

def _clean(value):
    """Turn NaN / NaT / blank string into real None, strip whitespace on strings."""
    if value is None or pd.isna(value):
        return None
    if isinstance(value, str):
        value = value.strip()
        return value if value else None
    return value


def _parse_date(value):
    """Handle both real datetime cells and messy text dates like '22/03/2021'."""
    value = _clean(value)
    if value is None:
        return None
    if hasattr(value, 'date'):  # datetime / pandas Timestamp
        res = value.date()
        return None if pd.isna(res) else res
    try:
        return date_parser.parse(str(value), dayfirst=True).date()
    except Exception:
        return None

def _to_float(value):
    value = _clean(value)
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _to_int(value):
    value = _to_float(value)
    return int(value) if value is not None else None


def _get_or_create_location(barangay, municipality):
    barangay = _clean(barangay)
    municipality = _clean(municipality)
    if not barangay or not municipality:
        return None

    location = Location.query.filter(
        db.func.lower(Location.municipality) == municipality.lower(),
        db.func.lower(Location.barangay) == barangay.lower()
    ).first()

    if location:
        return location

    location = Location(
        region=DEFAULT_REGION,
        province=DEFAULT_PROVINCE,
        municipality=municipality,
        barangay=barangay
    )
    db.session.add(location)
    db.session.flush()  # get location_id without full commit yet
    return location


def _get_or_create_organization(name):
    name = _clean(name) or "Unspecified Partner"

    org = Organization.query.filter(
        db.func.lower(Organization.organization_name) == name.lower()
    ).first()

    if org:
        return org

    org = Organization(
        organization_name=name,
        organization_type='Partner/Contractor'
    )
    db.session.add(org)
    db.session.flush()
    return org


def _get_placeholder_tree_specie():
    """
    ReforestationRecord.tree_id is NOT NULL, but species matching
    is not built yet -- use one shared placeholder row for now.
    Swap real species in later once that feature is ready.
    """
    tree = TreeSpecie.query.filter_by(specie_name=PLACEHOLDER_SPECIES_NAME).first()
    if tree:
        return tree
    tree = TreeSpecie(specie_name=PLACEHOLDER_SPECIES_NAME)
    db.session.add(tree)
    db.session.flush()
    return tree


def _is_denr_contract_sheet(df_columns):
    """Row-3 header must contain all required columns to count as a valid sheet."""
    return REQUIRED_DENR_COLUMNS.issubset(set(df_columns))

#User Management
@admin_bp.route('/user-management', methods=['GET'])
@admin_required
def user_management():
    search = request.args.get('q', '').strip()
    query = User.query

    if search:
        like = f"%{search}%"
        query = query.filter(
            or_(
                User.username.ilike(like),
                User.email_address.ilike(like),
                User.role.ilike(like)
            )
        )

    users = query.order_by(User.user_id).all()
    return render_template('Usermanagement.html', users=users, search=search)

@admin_bp.route('/users/<int:user_id>/delete', methods=['POST'])
@admin_required
def delete_user(user_id):
    if user_id == session.get('user_id'):
        flash("You cannot delete your own account.", "danger")
        return redirect(url_for('admin.user_management'))

    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    flash("User deleted.", "success")
    return redirect(url_for('admin.user_management'))

# Upload excel file
@admin_bp.route('/reference-dataset', methods=['GET'])
@admin_required
def reference_dataset():
    return render_template('Referencedataset.html')


@admin_bp.route('/reference-dataset/import', methods=['POST'])
@admin_required
def import_denr_data():
    uploaded_file = request.files.get('excel_file')

    if not uploaded_file or uploaded_file.filename == '':
        flash("No file selected.", "danger")
        return redirect(url_for('admin.reference_dataset'))

    if not uploaded_file.filename.lower().endswith(('.xlsx', '.xls')):
        flash("File must be .xlsx or .xls", "danger")
        return redirect(url_for('admin.reference_dataset'))

    try:
        xl = pd.ExcelFile(uploaded_file)
    except Exception as e:
        flash(f"Could not read file: {e}", "danger")
        return redirect(url_for('admin.reference_dataset'))

    placeholder_tree = _get_placeholder_tree_specie()
    db.session.commit()  # lock this in now, so a later row's rollback can't undo it

    sites_created = 0
    sites_updated = 0
    records_created = 0
    rows_skipped = 0
    error_samples = []
    sheets_processed = []
    sheets_ignored = []

    for sheet_name in xl.sheet_names:
        df = xl.parse(sheet_name, header=2)  # real headers sit on row 3
        df.columns = [str(c).strip() for c in df.columns]

        if not _is_denr_contract_sheet(df.columns):
            sheets_ignored.append(sheet_name)
            continue  # not a contract-profile sheet (e.g. Summary) -- skip quietly

        sheets_processed.append(sheet_name)

        for idx, row in df.iterrows():
            try:
                municipality = _clean(row.get('MUNICIPALITY'))
                barangay = _clean(row.get('BARANGAY'))
                site_code = _clean(row.get('SITE CODE'))

                if not municipality or not barangay:
                    rows_skipped += 1
                    continue

                location = _get_or_create_location(barangay, municipality)
                if not location:
                    rows_skipped += 1
                    continue

                organization = _get_or_create_organization(
                    row.get('NAME OF PARTNER/CONTRACTOR (GROUP OR INDIVIDUAL)')
                )

                area_planted = _to_float(row.get('ACTUAL AREA PLANTED (HA)'))
                area_contracted = _to_float(row.get('AREA CONTRACTED (HA)'))
                date_executed = _parse_date(
                    row.get('DATE OF EXECUTION OF CONTRACT (MM/DD/YR) 15 DAYS UPON ISSUANCE OF NTP)')
                )

                # upsert by site_code when we have one, otherwise always create new
                site = Site.query.filter_by(site_code=site_code).first() if site_code else None
                is_new_site = site is None

                if is_new_site:
                    site = Site(
                        location_id=location.location_id,
                        organization_id=organization.organization_id,
                        site_name=f"{barangay}, {municipality} Reforestation Site",
                        area_size_ha=area_planted or area_contracted or 0.0,
                        date_established=date_executed or dt.utcnow().date(),
                    )

                # fill/refresh the DENR-sourced fields either way
                site.site_code = site_code or site.site_code
                site.zone_type = _clean(row.get('ZONE (PRODUCTION OR PROTECTION)')) or site.zone_type
                site.loa_contract_code = _clean(
                    row.get('LOA/CONTRACT CODE (YEAR-CENRO CODE-3 DIGITS)')
                ) or site.loa_contract_code
                site.year_contracted = _to_int(row.get('YEAR CONTRACTED')) or site.year_contracted
                site.area_contracted_ha = area_contracted or site.area_contracted_ha
                site.date_contract_executed = date_executed or site.date_contract_executed
                site.date_contract_expiry = _parse_date(
                    row.get('DATE OF EXPIRY OF CONTRACT (END DATE AT YEAR 3)')
                ) or site.date_contract_expiry
                site.project_cost_3yr = _to_float(row.get('PROJECT COST (3 YEARS)')) or site.project_cost_3yr
                site.retention_fee_amount_paid = _to_float(
                    row.get('RETENTION FEE at 3rd YEAR (Amount paid)')
                ) or site.retention_fee_amount_paid
                site.retention_fee_date_paid = _parse_date(
                    row.get('RETENTION FEE at 3rd YEAR (Date paid)')
                ) or site.retention_fee_date_paid
                site.amount_under_land_improvement = _to_float(
                    row.get('AMOUNT UNDER LAND IMPROVEMENT')
                ) or site.amount_under_land_improvement
                site.amount_still_in_cip = _to_float(
                    row.get('AMOUNT STILL IN CIP')
                ) or site.amount_still_in_cip
                site.penro = _clean(row.get('PENRO')) or site.penro
                site.cenro = _clean(row.get('IMPLEMENTING CENRO')) or site.cenro
                site.congressional_district = _clean(row.get('CONGRESSIONAL DISTRICT')) or site.congressional_district
                site.land_classification = _clean(row.get('IDENTIFY IF WATERSHED, PA OR REGULAR')) or site.land_classification
                site.major_land_use = _clean(row.get('MAJOR LAND-USE LOCATION (Name of Watershed,PA or NA)')) or site.major_land_use
                site.contact_person = _clean(row.get('NAME OF GROUP CONTACT PERSON OF THE PARTNER GROUP')) or site.contact_person
                site.component = _clean(row.get('COMPONENT')) or site.component
                site.commodity = _clean(row.get('COMMODITY (if mixed,specify all commodities within the contracted Site)')) or site.commodity
                if is_new_site:
                    db.session.add(site)
                    db.session.flush()
                    sites_created += 1
                else:
                    sites_updated += 1

                # --- reforestation record (seedlings + survival rate) ---
                target_qty = _to_int(row.get('NO. OF SEEDLINGS TO BE PLANTED'))
                if target_qty:
                    date_planted = date_executed or dt.utcnow().date()

                    existing_record = ReforestationRecord.query.filter_by(
                        site_id=site.site_id,
                        tree_id=placeholder_tree.tree_id,
                        date_planted=date_planted
                    ).first()

                    if not existing_record:
                        record = ReforestationRecord(
                            site_id=site.site_id,
                            tree_id=placeholder_tree.tree_id,
                            date_planted=date_planted,
                            target_quantity=target_qty,
                            actual_quantity_planted=_to_int(row.get('NO. OF SEEDLINGS PLANTED')),
                            survival_rate=_to_float(row.get('SURVIVAL RATE ON THE 3RD YEAR')),
                            date_validated=_parse_date(
                                row.get('DATE OF PERFORMANCE VALIDATION REPORT (IAC REPORT)')
                            )
                        )
                        db.session.add(record)
                        records_created += 1

                db.session.commit()  # save THIS row's work now, before moving to the next row

            except Exception as e:
                db.session.rollback()  # undo just this row's half-done work, keep session usable
                rows_skipped += 1
                if len(error_samples) < 5:
                    error_samples.append(f"Sheet '{sheet_name}' row {idx + 4}: {e}")
                continue

    db.session.commit()

    flash(
        f"Import done. Sheets processed: {', '.join(sheets_processed) or 'none'}. "
        f"Sites created: {sites_created}, updated: {sites_updated}. "
        f"Reforestation records created: {records_created}. Rows skipped: {rows_skipped}.",
        "success"
    )
    if sheets_ignored:
        flash(
            f"Ignored (not contract-profile format): {', '.join(sheets_ignored)}",
            "warning"
        )
    if error_samples:
        flash("Sample issues: " + " | ".join(error_samples), "warning")

    return redirect(url_for('admin.reference_dataset'))


# ======================================================================
# BLOCK 2
# PASTE AT THE BOTTOM OF: app/routes/admin.py
#
# Imports needed at the top of admin.py:
#     from app.models import Request, Notification, Location
#     from datetime import datetime
#     from zoneinfo import ZoneInfo
#     from flask import jsonify
# ======================================================================


@admin_bp.route('/requests')
@admin_required
def review_requests():
    """
    All submitted requests, newest first, for review.
    """
    status_filter = request.args.get('status', '')

    status_filter = request.args.get('status', '')

    query = Request.query

    if status_filter == 'Pending':
        # unanswered: submitted but not yet decided
        query = query.filter(Request.status.in_(['Submitted', 'Under Review']))
    elif status_filter:
        query = query.filter(Request.status == status_filter)

    all_requests = query.order_by(Request.date_submitted.desc()).all()

    counts = {
        'Pending': Request.query.filter(
            Request.status.in_(['Submitted', 'Under Review'])).count(),
        'Approved': Request.query.filter_by(status='Approved').count(),
        'Rejected': Request.query.filter_by(status='Rejected').count(),
    }
    return render_template(
        'RequestsAdmin.html',
        active_page='review_requests',
        all_requests=all_requests,
        counts=counts,
        total_count=Request.query.count(),
        status_filter=status_filter,
    )


@admin_bp.route('/requests/<int:request_id>/review', methods=['POST'])
@admin_required
def review_request(request_id):
    """
    Set a request's status and notify the person who submitted it.

    The notification is what makes the Notifications page useful. Until
    now nothing in the system created one.
    """
    req = Request.query.get_or_404(request_id)

    new_status = (request.form.get('status') or '').strip()
    note = (request.form.get('review_note') or '').strip()

    allowed = {'Submitted', 'Under Review', 'Approved', 'Rejected'}
    if new_status not in allowed:
        flash("Invalid status.", "danger")
        return redirect(url_for('admin.review_requests'))

    if new_status == 'Rejected' and not note:
        flash("Give a reason when rejecting a request.", "danger")
        return redirect(url_for('admin.review_requests'))

    req.status = new_status
    req.review_note = note or None
    req.reviewed_by = session.get('user_id')
    req.date_reviewed = datetime.now(ZoneInfo("Asia/Manila"))

    where = "your requested site"
    if req.location:
        where = f"{req.location.barangay}, {req.location.municipality}"

    message = f"Your reforestation request for {where} is now {new_status}."
    if note:
        message += f" Note: {note}"

    db.session.add(Notification(
        user_id=req.user_id,
        notification_type='Request Update',
        message=message,
        is_read=False,
    ))

    db.session.commit()

    flash(f"Request #{req.request_id} marked {new_status}.", "success")
    return redirect(url_for('admin.review_requests'))

"""
DATASET PREVIEW - dry run before import

PASTE AT THE BOTTOM OF: app/routes/admin.py

WHAT THIS DOES
--------------
Parses the uploaded Excel exactly as the importer would, but writes
nothing. Returns what WOULD happen so the admin can check before
committing.

WHY IT MATTERS
--------------
The current importer accepts any text in the BARANGAY column. A section
header in the source file became a real 25-hectare site attached to a
location that does not exist, and it counted toward municipal totals
until it was found by accident.

The preview flags those rows before they reach the database.

NO TEMPORARY STORAGE
--------------------
The file is parsed and discarded. The browser still holds it in the file
input, so confirming submits the same file to the existing import route.
Nothing is written to disk or session.
"""

import re

# ======================================================================
# PASTE FROM HERE
# ======================================================================


def _norm_name(s):
    """Lowercase, expand Sta./Sto., strip spaces, dots, dashes."""
    s = str(s or "").lower()
    s = s.replace("sta.", "santa").replace("sto.", "santo")
    return re.sub(r"[\s.\-]", "", s)


@admin_bp.route('/reference-dataset/preview', methods=['POST'])
@admin_required
def preview_denr_data():
    """
    Dry run. Reports what an import would do. Writes nothing.
    """
    uploaded_file = request.files.get('excel_file')

    if not uploaded_file or uploaded_file.filename == '':
        return jsonify({"ok": False, "error": "No file selected."}), 400

    if not uploaded_file.filename.lower().endswith(('.xlsx', '.xls')):
        return jsonify({"ok": False, "error": "File must be .xlsx or .xls"}), 400

    try:
        xl = pd.ExcelFile(uploaded_file)
    except Exception as e:
        return jsonify({"ok": False, "error": f"Could not read file: {e}"}), 400

    # every known barangay, indexed by normalised municipality + barangay
    known = set()
    for loc in Location.query.all():
        known.add((_norm_name(loc.municipality), _norm_name(loc.barangay)))

    # site codes already in the database - these will be UPDATED not created
    existing_codes = {
        s.site_code for s in Site.query.filter(Site.site_code.isnot(None)).all()
    }

    sheets = []
    total_rows = 0
    would_create = 0
    would_update = 0
    would_skip = 0

    unmatched = {}        # (muni, brgy) -> row count
    duplicate_codes = {}  # site_code -> row count within this file
    samples = []

    for sheet_name in xl.sheet_names:
        try:
            df = xl.parse(sheet_name, header=2)
        except Exception as e:
            sheets.append({
                "name": sheet_name,
                "used": False,
                "reason": f"could not parse: {e}",
                "rows": 0,
            })
            continue

        df.columns = [str(c).strip() for c in df.columns]

        if not _is_denr_contract_sheet(df.columns):
            sheets.append({
                "name": sheet_name,
                "used": False,
                "reason": "no contract-profile headers on row 3",
                "rows": len(df),
            })
            continue

        sheet_rows = 0

        for idx, row in df.iterrows():
            municipality = _clean(row.get('MUNICIPALITY'))
            barangay = _clean(row.get('BARANGAY'))
            site_code = _clean(row.get('SITE CODE'))

            if not municipality or not barangay:
                would_skip += 1
                continue

            sheet_rows += 1
            total_rows += 1

            key = (_norm_name(municipality), _norm_name(barangay))
            is_known = key in known

            if not is_known:
                label = f"{barangay}, {municipality}"
                unmatched[label] = unmatched.get(label, 0) + 1

            if site_code:
                if site_code in existing_codes:
                    would_update += 1
                else:
                    would_create += 1
                    existing_codes.add(site_code)
                duplicate_codes[site_code] = duplicate_codes.get(site_code, 0) + 1
            else:
                would_create += 1

            if len(samples) < 8:
                samples.append({
                    "sheet": sheet_name,
                    "row": idx + 4,          # header on row 3, pandas is 0-based
                    "municipality": municipality,
                    "barangay": barangay,
                    "site_code": site_code or "—",
                    "site_name": _clean(row.get('SITE NAME')) or "—",
                    "area": _clean(row.get('AREA (HAS.)')) or "—",
                    "known_location": is_known,
                })

        sheets.append({
            "name": sheet_name,
            "used": True,
            "reason": "",
            "rows": sheet_rows,
        })

    repeats = {k: v for k, v in duplicate_codes.items() if v > 1}

    warnings = []

    if unmatched:
        n = sum(unmatched.values())
        warnings.append({
            "level": "danger",
            "title": f"{n} row(s) name a barangay that is not in the map data",
            "detail": (
                "These rows will create Location records with no coordinates "
                "and no site characteristics. They will not appear on the map "
                "and will not receive species recommendations. Check for "
                "spelling differences, or for section headers that are not "
                "barangay names."
            ),
            "items": [f"{k} ({v} row{'s' if v > 1 else ''})"
                      for k, v in sorted(unmatched.items(),
                                         key=lambda x: -x[1])][:15],
        })

    if repeats:
        warnings.append({
            "level": "warning",
            "title": f"{len(repeats)} site code(s) appear more than once in this file",
            "detail": (
                "Site code is unique, so later rows overwrite earlier ones. "
                "Only the last occurrence will survive."
            ),
            "items": [f"{k} ({v} rows)" for k, v in
                      sorted(repeats.items(), key=lambda x: -x[1])][:15],
        })

    if would_update:
        warnings.append({
            "level": "info",
            "title": f"{would_update} existing site(s) will be overwritten",
            "detail": (
                "These site codes already exist. Their current values will be "
                "replaced by whatever is in this file."
            ),
            "items": [],
        })

    if not total_rows:
        warnings.append({
            "level": "danger",
            "title": "No importable rows found",
            "detail": (
                "No sheet had the expected headers on row 3, or every row was "
                "missing a municipality or barangay."
            ),
            "items": [],
        })

    return jsonify({
        "ok": True,
        "filename": uploaded_file.filename,
        "sheets": sheets,
        "summary": {
            "total_rows": total_rows,
            "would_create": would_create,
            "would_update": would_update,
            "would_skip": would_skip,
            "unmatched_rows": sum(unmatched.values()),
        },
        "warnings": warnings,
        "samples": samples,
    })


# ======================================================================
# admin side reforestation monitoring/ reports
# 
# ======================================================================


@admin_bp.route('/reports')
@admin_required
def review_reports():
    """Monitoring reports awaiting review, newest first."""
    status_filter = request.args.get('status', '')
 
    query = MonitoringReport.query
    if status_filter:
        query = query.filter(MonitoringReport.approval_status == status_filter)
 
    reports = query.order_by(MonitoringReport.submitted_at.desc()).all()
 
    counts = {
        'Pending': MonitoringReport.query.filter_by(
            approval_status='Pending').count(),
        'Approved': MonitoringReport.query.filter_by(
            approval_status='Approved').count(),
        'Rejected': MonitoringReport.query.filter_by(
            approval_status='Rejected').count(),
    }
 
    return render_template(
        'ReportsAdmin.html',
        active_page='review_reports',
        reports=reports,
        counts=counts,
        total_count=MonitoringReport.query.count(),
        status_filter=status_filter,
    )
 
 
@admin_bp.route('/reports/<int:report_id>')
@admin_required
def review_report_detail(report_id):
    """Full preview of one report before deciding on it."""
    report = MonitoringReport.query.get_or_404(report_id)
 
    plot_photos = [p for p in report.photos if p.photo_type == 'plot']
    boundary_photos = [p for p in report.photos if p.photo_type == 'boundary']
 
    return render_template(
        'ReportDetail.html',
        active_page='review_reports',
        report=report,
        plots=sorted(report.plots, key=lambda p: p.plot_number),
        plot_photos=plot_photos,
        boundary_photos=boundary_photos,
    )
 
 
@admin_bp.route('/reports/<int:report_id>/review', methods=['POST'])
@admin_required
def review_report(report_id):
    """
    Approve or reject a report.
 
    APPROVING WRITES BACK to the reforestation record. This is the point
    of the whole feature: survival_rate and date_validated have existed
    as columns since the schema was written and nothing has ever filled
    them. After approval they carry field-verified numbers.
    """
    report = MonitoringReport.query.get_or_404(report_id)
 
    new_status = (request.form.get('status') or '').strip()
    note = (request.form.get('review_note') or '').strip()
    update_boundary = request.form.get('update_boundary') == 'yes'
 
    if new_status not in {'Pending', 'Approved', 'Rejected'}:
        flash("Invalid status.", "danger")
        return redirect(url_for('admin.review_report_detail',
                                report_id=report_id))
 
    if new_status == 'Rejected' and not note:
        flash("Give a reason when rejecting a report.", "danger")
        return redirect(url_for('admin.review_report_detail',
                                report_id=report_id))
 
    report.approval_status = new_status
    report.review_note = note or None
    report.reviewed_by = session.get('user_id')
    report.date_reviewed = datetime.now(ZoneInfo("Asia/Manila"))
 
    if new_status == 'Approved':
        record = ReforestationRecord.query.get(report.record_id)
        if record:
            record.survival_rate = report.survival_rate
            record.date_validated = report.monitoring_date
 
        if update_boundary and report.boundary_geojson and report.site:
            report.site.boundary_geojson = report.boundary_geojson
            report.site.boundary_area_ha = report.captured_area_ha
            report.site.boundary_captured_at = datetime.now(
                ZoneInfo("Asia/Manila")
            )
 
    where = (
        f"{report.site.location.barangay}, {report.site.location.municipality}"
        if report.site and report.site.location else "the site"
    )
 
    message = (
        f"Your monitoring report for {where} was {new_status.lower()}."
    )
    if note:
        message += f" Note: {note}"
 
    db.session.add(Notification(
        user_id=report.user_id,
        notification_type='Report',
        message=message,
        report_id=report.report_id,
        is_read=False,
    ))
 
    db.session.commit()
 
    flash(f"Report #{report.report_id} marked {new_status}.", "success")
    return redirect(url_for('admin.review_reports'))
 


































