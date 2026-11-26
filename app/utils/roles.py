"""Role labels. The one place that turns roles into words.

Labels only. Permissions live in decorators.py and organization.py.

Two separate things:
- System role: what the account can do in the system.
- Partner organization position: a normal user's place in their
  organization. Always shown with the organization's name.
"""

GUEST = 'Guest'
USER = 'User'
FIELD_OFFICER = 'Field Officer'
CENRO_ADMIN = 'CENRO Administrator'
PROVINCIAL_ADMIN = 'Provincial Administrator'
SYSTEM_ADMIN = 'System Administrator'

ORG_LEADER = 'Partner Org Leader'
ORG_MEMBER = 'Partner Org Member'
ORG_PENDING = 'Pending Member'
INDIVIDUAL = 'Individual'

# System roles an administrator can pick in User Management.
# 'admin' becomes CENRO or Provincial by its jurisdiction.
SYSTEM_ROLE_CHOICES = [
    ('normal_user', USER),
    ('field_officer', FIELD_OFFICER),
    ('admin', 'Administrator (CENRO or Provincial, by jurisdiction)'),
    ('superadmin', SYSTEM_ADMIN),
]


def system_role_label(role, cenro=None):
    """'superadmin' -> System Administrator; no role -> Guest."""
    if not role:
        return GUEST
    if role == 'superadmin':
        return SYSTEM_ADMIN
    if role == 'admin':
        return CENRO_ADMIN if cenro else PROVINCIAL_ADMIN
    if role == 'field_officer':
        return FIELD_OFFICER
    return USER


def org_position(role, org_role, org_status):
    """The bare position, or None for staff (positions are Users only)."""
    if role and role != 'normal_user':
        return None
    if not org_role:
        return INDIVIDUAL
    if org_status == 'pending':
        return ORG_PENDING
    return ORG_LEADER if org_role == 'leader' else ORG_MEMBER


def org_position_label(role, org_role, org_status, org_name=None):
    """'Partner Org Leader · San Vicente Farmers Assoc.', 'Individual',
    or None for staff."""
    pos = org_position(role, org_role, org_status)
    if pos is None or pos == INDIVIDUAL or not org_name:
        return pos
    return f'{pos} · {org_name}'


def user_role_label(user):
    if user is None:
        return GUEST
    return system_role_label(user.role, user.cenro)


def user_org_label(user):
    if user is None:
        return None
    org = user.organization if user.organization_id else None
    return org_position_label(user.role, user.org_role, user.org_status,
                              org.organization_name if org else None)
