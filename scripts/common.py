"""
Shared by every script: where files live, and the Flask app context.

Run scripts as modules from the project root, so this package and `app`
both import without path tricks:

    python -m scripts.pipeline.get_climate

Moving a data file means editing this file only.
"""

import os

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPTS_DIR)
STATIC_DIR = os.path.join(PROJECT_ROOT, "app", "static")

# Supplied by hand. Scripts read these and never write them.
SOURCE_DIR = os.path.join(SCRIPTS_DIR, "data", "source")
SOIL_SHAPEFILE = os.path.join(SOURCE_DIR, "soil", "PhilSoilSeries.shp")
SPECIES_XLSX = os.path.join(SOURCE_DIR, "Philippine_Tree_main_species_Database.xlsx")
# CENRO use category per species, filled in by hand (tools/load_species_categories)
SPECIES_CATEGORIES_CSV = os.path.join(SOURCE_DIR, "species_categories.csv")

# Written by the pipeline, in the order the steps run.
GENERATED_DIR = os.path.join(SCRIPTS_DIR, "data", "generated")
COORDS_CSV = os.path.join(GENERATED_DIR, "barangay_coords.csv")
ELEVATION_CSV = os.path.join(GENERATED_DIR, "barangay_elevation.csv")
CLIMATE_CSV = os.path.join(GENERATED_DIR, "barangay_climate.csv")
SOIL_CSV = os.path.join(GENERATED_DIR, "barangay_soil.csv")


def load_env():
    """
    Load .env, the way run.py does. scripts/__init__.py calls this.

    It has to run before anything imports `app`: app/config.py reads
    DATABASE_URL once, when it is first imported.
    """
    from dotenv import load_dotenv
    load_dotenv(os.path.join(PROJECT_ROOT, ".env"))


def app_context():
    """
    The web app's context, for scripts that use the database.

        with app_context():
            ...
    """
    from app import create_app
    return create_app().app_context()
