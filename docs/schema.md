# Database schema notes

Changes applied by hand in Supabase (SQL editor), next to the Alembic
migrations in `migrations/versions/`. Each section gives the SQL and the
migration it matches. Apply **either** the SQL **or** `flask db upgrade`,
not both: each SQL block ends by moving `alembic_version` to that
migration, so Alembic knows it is done.

## species_category

CENRO use categories for tree species (Timber, Agroforestry; later Fuel
wood, Bamboo). One row per species and category, so a species can be in
several. Used by the purpose filter on the Species Recommendation page.

- Allowed category names: `SPECIES_CATEGORIES` in
  `app/services/recommender.py`. Written nowhere else.
- Filled from `scripts/data/source/species_categories.csv` by
  `python -m scripts.tools.load_species_categories`.
- Model: `SpeciesCategory` in `app/models.py`.
- Migration: `c4e8a2f6b9d1_add_species_category.py`.

| Column | Type | Notes |
|---|---|---|
| id | integer | primary key |
| species_id | integer | `tree_specie.tree_id`; rows go when the species is deleted |
| category | varchar(50) | one of `SPECIES_CATEGORIES` |

Unique on (species_id, category).

```sql
BEGIN;

CREATE TABLE species_category (
    id          SERIAL PRIMARY KEY,
    species_id  INTEGER NOT NULL
                REFERENCES tree_specie (tree_id) ON DELETE CASCADE,
    category    VARCHAR(50) NOT NULL,
    CONSTRAINT uq_species_category UNIQUE (species_id, category)
);

CREATE INDEX ix_species_category_species_id
    ON species_category (species_id);

-- Alembic: mark migration c4e8a2f6b9d1 as applied. Only if the database
-- was at b7c3e9a1d5f4 (check: SELECT version_num FROM alembic_version;).
UPDATE alembic_version SET version_num = 'c4e8a2f6b9d1'
 WHERE version_num = 'b7c3e9a1d5f4';

COMMIT;
```
