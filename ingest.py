#!/usr/bin/env python3
"""Process listed buildings CSV data with proper coordinate transformation"""

import pandas as pd
import json
from pathlib import Path
import subprocess
import tempfile

# Read CSV
df = pd.read_csv("data/listed_buildings.csv")

# Normalize columns
df.columns = [col.strip().lower().replace(' ', '_').replace('-', '_') for col in df.columns]

# Drop rows without coordinates
df = df.dropna(subset=['easting', 'northing'])

# Convert to numeric
df['easting'] = pd.to_numeric(df['easting'], errors='coerce')
df['northing'] = pd.to_numeric(df['northing'], errors='coerce')
df = df.dropna(subset=['easting', 'northing'])

print(f"Processing {len(df)} records...")

# Create a temporary GeoJSON in EPSG:27700
temp_27700 = tempfile.NamedTemporaryFile(mode='w', suffix='.geojson', delete=False)
features = []
for idx, row in df.iterrows():
    # Clean properties - replace NaN with None for JSON compatibility
    properties = {}
    for key, value in row.drop(['easting', 'northing']).items():
        if pd.isna(value):
            properties[key] = None
        else:
            properties[key] = value
    
    feature = {
        "type": "Feature",
        "properties": properties,
        "geometry": {
            "type": "Point",
            "coordinates": [float(row['easting']), float(row['northing'])]
        }
    }
    features.append(feature)

geojson_27700 = {
    "type": "FeatureCollection",
    "features": features
}

with open(temp_27700.name, 'w') as f:
    json.dump(geojson_27700, f)

# Save outputs
Path("build").mkdir(exist_ok=True)

# Use ogr2ogr to convert from OSGB 1936 British National Grid to EPSG:4326
# EPSG:27700 is OSGB 1936 / British National Grid
print("Converting coordinates from OSGB 1936 (EPSG:27700) to WGS84 (EPSG:4326)...")
cmd = [
    'ogr2ogr', '-f', 'GeoJSON',
    '-s_srs', '+proj=tmerc +lat_0=49 +lon_0=-2 +k=0.9996012717 +x_0=400000 +y_0=-100000 +ellps=airy +datum=OSGB36 +units=m +no_defs',
    '-t_srs', 'EPSG:4326',
    'build/listed_buildings.geojson',
    temp_27700.name
]
result = subprocess.run(cmd, capture_output=True, text=True)
if result.returncode != 0:
    print(f"Error in ogr2ogr: {result.stderr}")
    exit(1)

# Clean up temp file
Path(temp_27700.name).unlink()

print(f"Saved {len(df)} records to build/listed_buildings.geojson")

# Print bounds
with open('build/listed_buildings.geojson', 'r') as f:
    data = json.load(f)
    
min_lon = min_lat = float('inf')
max_lon = max_lat = float('-inf')
for feature in data['features']:
    lon, lat = feature['geometry']['coordinates']
    min_lon = min(min_lon, lon)
    max_lon = max(max_lon, lon)
    min_lat = min(min_lat, lat)
    max_lat = max(max_lat, lat)
    
print(f"Bounds: [{min_lon}, {min_lat}, {max_lon}, {max_lat}]")