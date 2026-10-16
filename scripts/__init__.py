"""
Data scripts for PuNoObservation. Run them as modules from the project
root, for example `python -m scripts.pipeline.get_climate`. See
README.md for the order.

Importing this package loads .env first, so every script sees the same
DATABASE_URL as the web app, whatever it imports next.
"""

from scripts.common import load_env

load_env()
