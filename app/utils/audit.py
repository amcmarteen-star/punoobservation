"""
Audit logging.

One function. Call it after an action succeeds.

DESIGN NOTE - it never raises.

A logging failure must not roll back the action being logged. If writing
the audit row fails, the approval or import that triggered it still
stands. The alternative - an exception in the logger undoing a completed
review - is worse than a missing log line.
"""

from flask import request, session

from app.extensions import db
from app.models import AuditLog


def log_action(action, entity_type=None, entity_id=None, detail=None,
               commit=False):
    """
    Record one action.

    action       short verb, e.g. 'publish_boundary'
    entity_type  table the action touched
    entity_id    primary key of the row
    detail       human-readable description, shown in the log page
    commit       True only when the caller is not about to commit anyway

    The actor's username, role and CENRO are copied in rather than read
    through the relationship, so the log still reads correctly after an
    account is renamed or deleted.
    """
    try:
        entry = AuditLog(
            user_id=session.get('user_id'),
            username=session.get('username'),
            role=session.get('role'),
            cenro=session.get('cenro'),
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            detail=detail,
            ip_address=request.remote_addr if request else None,
        )
        db.session.add(entry)
        if commit:
            db.session.commit()
    except Exception:
        # deliberately silent. See the note above.
        db.session.rollback()


def log_login(username, success, role=None, user_id=None):
    """
    Login attempts, including failures.

    Failed attempts are the reason this is separate: session is empty at
    that point, so the username has to be passed in.
    """
    try:
        entry = AuditLog(
            user_id=user_id,
            username=username,
            role=role,
            action='login' if success else 'login_failed',
            entity_type='users',
            entity_id=user_id,
            detail=None if success else 'Incorrect username or password',
            ip_address=request.remote_addr if request else None,
        )
        db.session.add(entry)
        db.session.commit()
    except Exception:
        db.session.rollback()