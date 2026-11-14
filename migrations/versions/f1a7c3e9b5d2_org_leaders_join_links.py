"""Organization leaders, join links and a CENRO for each organization.

Revision ID: f1a7c3e9b5d2
Revises: e4a9c1d7b2f8
Create Date: 2026-11-14

Schema
- organization.join_token   one invite link per organization (unique)
- organization.cenro        the CENRO covering the organization
- users.org_role            'leader' or 'member'; NULL for individuals
- users.org_status          'pending' or 'active'; NULL for individuals

Existing data (done by this migration)
- Every user with an organization becomes a member, pending approval.
- Every organization gets a join link.
- An organization gets a CENRO only when all of its sites sit in one
  CENRO. A site's recorded CENRO wins; otherwise its municipality decides.
  Organizations with sites in two CENROs, with a site nobody can place,
  or with no sites stay NULL. NULL means the provincial office handles them.

Leaders are NOT set here. Run the SQL below after `flask db upgrade`.

LEADER SETUP (after upgrade)

    -- 1. Find the members who can be made leader.
    SELECT o.organization_id, o.organization_name, u.user_id, u.username,
           u.email_verified
    FROM users u
    JOIN organization o ON o.organization_id = u.organization_id
    WHERE u.org_status = 'pending'
    ORDER BY o.organization_name, u.username;

    -- 2. Make a leader. Use a user_id and organization_id from step 1.
    --    Leaders must be active, so this sets both fields. A leader who
    --    has not verified their email still cannot sign in until they do.
    UPDATE users
       SET org_role = 'leader', org_status = 'active'
     WHERE user_id = <USER_ID>
       AND organization_id = <ORGANIZATION_ID>;

    -- 3. Check the leaders.
    SELECT o.organization_name, u.username
    FROM users u
    JOIN organization o ON o.organization_id = u.organization_id
    WHERE u.org_role = 'leader'
    ORDER BY o.organization_name;

    -- 4. Organizations with no CENRO. The provincial office handles them.
    SELECT organization_id, organization_name
    FROM organization
    WHERE cenro IS NULL
    ORDER BY organization_name;
"""

import secrets

import sqlalchemy as sa
from alembic import op

revision = 'f1a7c3e9b5d2'
down_revision = 'e4a9c1d7b2f8'
branch_labels = None
depends_on = None

# Copied from app/utils/jurisdiction.py CENRO_MUNICIPALITIES on 2026-11-14.
# A migration must not import app code that can change later.
CENRO_MUNICIPALITIES = {
    "Urdaneta City": [
        "Alcala", "Asingan", "Balungao", "Bautista", "Binalonan",
        "Laoac", "Natividad", "Pozorrubio", "Rosales", "San Manuel",
        "San Nicolas", "San Quintin", "Santa Maria", "Santo Tomas",
        "Sison", "Tayug", "Umingan", "Urdaneta City", "Villasis",
    ],
    "Dagupan": [
        "Aguilar", "Basista", "Bayambang", "Binmaley", "Bugallon",
        "Calasiao", "Dagupan City", "Labrador", "Lingayen", "Malasiqui",
        "Manaoag", "Mangaldan", "Mangatarem", "Mapandan", "San Carlos City",
        "San Fabian", "San Jacinto", "Santa Barbara", "Urbiztondo",
    ],
    "Alaminos": [
        "Agno", "Alaminos City", "Anda", "Bani", "Bolinao", "Burgos",
        "Dasol", "Infanta", "Mabini", "Sual",
    ],
}


def fill_existing_data(conn):
    """The data half of the migration. Takes a connection so it can be
    tested against a scratch database."""
    # 1. Anyone already attached to an organization waits for approval.
    conn.execute(sa.text(
        "UPDATE users SET org_role = 'member', org_status = 'pending' "
        "WHERE organization_id IS NOT NULL"
    ))

    # 2. Every organization gets a join link.
    org_ids = [row[0] for row in conn.execute(
        sa.text("SELECT organization_id FROM organization")).fetchall()]
    for org_id in org_ids:
        conn.execute(
            sa.text("UPDATE organization SET join_token = :t "
                    "WHERE organization_id = :id"),
            {"t": secrets.token_urlsafe(32), "id": org_id},
        )

    # 3. CENRO per organization, only when every site agrees.
    municipality_to_cenro = {
        m: c for c, ms in CENRO_MUNICIPALITIES.items() for m in ms
    }
    rows = conn.execute(sa.text(
        "SELECT s.organization_id, s.cenro, l.municipality "
        "FROM site s LEFT JOIN location l ON l.location_id = s.location_id"
    )).fetchall()
    per_org = {}
    for org_id, site_cenro, municipality in rows:
        cenro = site_cenro or municipality_to_cenro.get(municipality)
        per_org.setdefault(org_id, set()).add(cenro)
    for org_id, cenros in per_org.items():
        if len(cenros) == 1 and None not in cenros:
            (cenro,) = cenros
            conn.execute(
                sa.text("UPDATE organization SET cenro = :c "
                        "WHERE organization_id = :id"),
                {"c": cenro, "id": org_id},
            )


def upgrade():
    op.add_column('organization', sa.Column(
        'join_token', sa.String(length=64), nullable=True))
    op.add_column('organization', sa.Column(
        'cenro', sa.String(length=100), nullable=True))
    op.create_unique_constraint(
        'uq_organization_join_token', 'organization', ['join_token'])

    op.add_column('users', sa.Column(
        'org_role', sa.String(length=10), nullable=True))
    op.add_column('users', sa.Column(
        'org_status', sa.String(length=10), nullable=True))

    fill_existing_data(op.get_bind())


def downgrade():
    op.drop_column('users', 'org_status')
    op.drop_column('users', 'org_role')
    op.drop_constraint('uq_organization_join_token', 'organization',
                       type_='unique')
    op.drop_column('organization', 'cenro')
    op.drop_column('organization', 'join_token')
