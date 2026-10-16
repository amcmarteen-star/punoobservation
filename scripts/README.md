# Data scripts

Scripts that build the barangay reference data (map point, elevation,
climate, soil) and load it into the database, plus a few one-off tools.
They are not part of the running web app.

## Setup

From the project root, with the project's virtual environment active:

```
pip install -r scripts/requirements.txt
```

Every script runs as a module **from the project root**:

```
python -m scripts.pipeline.get_climate
```

The scripts read `.env` themselves, so they use the same database as
the web app.

## Layout

```
scripts/
├── README.md
├── requirements.txt     packages the scripts need on top of the app's
├── common.py            every file location, and the app context
├── pipeline/            barangay reference data, run in order (below)
├── tools/               one-off fixes and checks
└── data/
    ├── source/          supplied by hand; scripts only read these
    │   ├── soil/PhilSoilSeries.*          BSWM soil series shapefile
    │   ├── Philippine_Tree_main_species_Database.xlsx
    │   └── Urdaneta_All_Species_Biophysical_Limits.xlsx
    └── generated/       written by the pipeline; safe to rebuild
        ├── barangay_coords.csv
        ├── barangay_elevation.csv
        ├── barangay_climate.csv
        └── barangay_soil.csv
```

To move a data file, change its path in `common.py`. Nothing else
needs to change.

## Pipeline

Run in this order. Each step reads the file the step before it wrote.

| # | Command | Reads | Writes | Time |
|---|---------|-------|--------|------|
| 1 | `python -m scripts.pipeline.make_coords` | map outline files | `barangay_coords.csv` | seconds |
| 2 | `python -m scripts.pipeline.get_elevation` | coords | `barangay_elevation.csv` | about 1 minute |
| 3 | `python -m scripts.pipeline.get_climate` | elevation | `barangay_climate.csv` | about 12 s per new barangay |
| 4 | `python -m scripts.pipeline.get_soil` | coords + soil shapefile | `barangay_soil.csv` | a few minutes |
| 5 | `python -m scripts.pipeline.seed_reference_data` | climate + soil + species sheet | the database | under a minute |

Notes:

- **Step 1** keeps every barangay that already has climate data exactly
  as it is. Only new barangays get a new point, taken from their map
  outline (the same point the dataset import uses). Try `--dry-run`
  first.
- **Step 3** can be stopped and run again. It skips barangays already
  done. The service sometimes asks it to slow down; it waits and
  retries on its own.
- **Step 4** needs the whole shapefile: `.shp`, `.shx`, `.dbf` and
  `.prj`. The soil names are in the `.dbf`. Like step 3, it keeps every
  barangay that already has soil data and looks up only new ones, so a
  re-run never changes an existing barangay's soil.
- **Step 5** matches barangays by name, ignoring spaces and dots, and
  creates the ones the database does not have yet. Safe to re-run.

Sources: OpenTopoData (SRTM 30 m elevation), Open-Meteo archive (ERA5
climate, 2014–2023, CC BY 4.0), BSWM Philippine Soil Series.

### Adding a CENRO

1. Add its district and barangay outline files under
   `app/static/geojson/<area>/` and list the area in `CENRO_GEOJSON`
   (`app/utils/jurisdiction.py`).
2. Run the pipeline from step 1. Barangays already done are kept.

## Tools

| Command | What it does |
|---------|--------------|
| `python -m scripts.tools.fix_names --dry-run` | Shows barangay and town names written without spaces ("SanJuan") and what they would become. Drop `--dry-run` to apply, in the database and the generated CSVs. |
| `python -m scripts.tools.evaluate_recommender` | Scores the species recommender (Precision@K, NDCG@K). |

## Where the original data came from

The first 478 points (eastern Pangasinan) were the centroids of the
eastern barangay outlines, now
`app/static/geojson/eastern/district5_barangay.geojson` and
`district6_barangay.geojson`.
