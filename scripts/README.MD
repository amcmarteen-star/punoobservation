# Data collection scripts

Run in this order:

1. get_elevation.py
   Reads barangay_coords.csv, writes barangay_elevation.csv
   Source: SRTM 30m DEM via OpenTopoData API

2. get_climate.py
   Reads barangay_elevation.csv, writes barangay_climate.csv
   Source: ERA5 reanalysis via Open-Meteo Archive API
   Period: 2014-2023 (10 years)

barangay_coords.csv was generated from
app/static/geojson/barangay.geojson by computing the
centroid of each barangay polygon.

Final output: barangay_climate.csv — 478 barangays with
elevation, average temperature, and annual rainfall.