#!/usr/bin/env python3
"""
Process listed buildings data natively in EPSG:27700.
Buffers and unions in British National Grid, only reprojects at the end.
"""

import json
from shapely.geometry import Point, shape, mapping
from shapely.ops import unary_union
from pathlib import Path
import subprocess

def process_in_27700(input_geojson="build/listed_buildings.geojson",
                     buffer_meters=200,
                     negative_buffer_meters=180,
                     min_area_sqm=5000,
                     min_points=10):
    """
    Process points in EPSG:27700 (British National Grid).
    Assumes input is already in WGS84 but needs to be processed in BNG.
    """
    
    print("Step 1: Convert input to EPSG:27700 for processing...")
    
    # Use ogr2ogr to convert to OSGB 1936 British National Grid
    temp_27700 = "build/temp_27700.geojson"
    cmd = [
        'ogr2ogr', '-f', 'GeoJSON',
        '-s_srs', 'EPSG:4326',
        '-t_srs', '+proj=tmerc +lat_0=49 +lon_0=-2 +k=0.9996012717 +x_0=400000 +y_0=-100000 +ellps=airy +datum=OSGB36 +units=m +no_defs',
        temp_27700, input_geojson
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    
    # Read the EPSG:27700 GeoJSON
    with open(temp_27700, 'r') as f:
        data = json.load(f)
    
    points = []
    for feature in data['features']:
        geom = shape(feature['geometry'])
        points.append(geom)
    
    print(f"Step 2: Processing {len(points)} points in EPSG:27700...")
    print(f"  Buffer: {buffer_meters}m")
    print(f"  Negative buffer: {negative_buffer_meters}m")
    print(f"  Min area: {min_area_sqm} sqm")
    print(f"  Min points: {min_points}")
    
    # Process in chunks for better performance
    chunk_size = 5000
    chunks = [points[i:i + chunk_size] for i in range(0, len(points), chunk_size)]
    print(f"  Processing {len(points)} points in {len(chunks)} chunks...")
    
    chunk_unions = []
    for idx, chunk in enumerate(chunks):
        print(f"  Processing chunk {idx + 1}/{len(chunks)}...")
        buffered = [p.buffer(buffer_meters) for p in chunk]
        chunk_union = unary_union(buffered)
        if negative_buffer_meters > 0:
            # Apply negative buffer to each chunk first (faster)
            chunk_union = chunk_union.buffer(-negative_buffer_meters)
        chunk_unions.append(chunk_union)
    
    print("Step 3: Merging all chunks...")
    union = unary_union(chunk_unions)
    
    # Final cleanup pass if needed
    # if negative_buffer_meters > 0:
    #     print(f"Step 4: Final cleanup with {negative_buffer_meters}m negative buffer...")
    #     union = union.buffer(-negative_buffer_meters / 2)  # Smaller final pass
    
    # Split into parts
    if hasattr(union, 'geoms'):
        parts = list(union.geoms)
    else:
        parts = [union] if not union.is_empty else []
    
    print(f"Step 5: Filtering {len(parts)} polygons by area AND point count...")
    
    # We want to keep polygons that have EITHER:
    # 1. Large area (>= min_area_sqm), OR
    # 2. Enough points (>= min_points)
    # But we should exclude small polygons with few points
    
    filtered = []
    excluded_count = 0
    
    for idx, poly in enumerate(parts):
        if idx % 1000 == 0 and idx > 0:
            print(f"  Processed {idx}/{len(parts)} polygons...")
        
        # Large polygons are always kept
        if poly.area >= min_area_sqm:
            # But check if it has enough points - if area is large but very few points, exclude it
            # Use bounding box first for faster filtering
            bbox = poly.bounds
            potential_points = [p for p in points if bbox[0] <= p.x <= bbox[2] and bbox[1] <= p.y <= bbox[3]]
            
            # Quick check: if there are fewer potential points than min_points, exclude
            if len(potential_points) < min_points:
                excluded_count += 1
                continue
                
            # For large areas with potentially enough points, do actual containment check
            if len(potential_points) < min_points * 2:  # Only check if close to threshold
                points_within = sum(1 for point in potential_points if poly.contains(point))
                if points_within < min_points:
                    excluded_count += 1
                    continue
            
            filtered.append(poly)
        else:
            # Small polygons must have enough points
            bbox = poly.bounds
            potential_points = [p for p in points if bbox[0] <= p.x <= bbox[2] and bbox[1] <= p.y <= bbox[3]]
            
            if len(potential_points) >= min_points:
                points_within = sum(1 for point in potential_points if poly.contains(point))
                if points_within >= min_points:
                    filtered.append(poly)
                else:
                    excluded_count += 1
            else:
                excluded_count += 1
    
    print(f"  Kept {len(filtered)} polygons, excluded {excluded_count} (min area: {min_area_sqm} sqm, min points: {min_points})")
    
    # Create GeoJSON in EPSG:27700 with point counts
    print("Step 6: Creating GeoJSON features...")
    features = []
    for i, poly in enumerate(filtered):
        # Skip point counting for now (too slow for large datasets)
        # Could be added as a post-processing step if needed
        features.append({
            "type": "Feature",
            "properties": {
                "id": i,
                "area_m2": poly.area,
                "point_count": -1  # Placeholder, would need optimization for production
            },
            "geometry": mapping(poly)
        })
    
    output_27700 = {
        "type": "FeatureCollection",
        "features": features
    }
    
    # Save EPSG:27700 version
    with open("build/hotspots_27700.geojson", 'w') as f:
        json.dump(output_27700, f)
    
    print("Step 7: Reprojecting hotspots to WGS84...")
    
    # Use ogr2ogr to convert back to WGS84 from OSGB 1936
    cmd = [
        'ogr2ogr', '-f', 'GeoJSON',
        '-s_srs', '+proj=tmerc +lat_0=49 +lon_0=-2 +k=0.9996012717 +x_0=400000 +y_0=-100000 +ellps=airy +datum=OSGB36 +units=m +no_defs',
        '-t_srs', 'EPSG:4326',
        'build/hotspots.geojson',
        'build/hotspots_27700.geojson'
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    
    # Clean up temp file
    Path(temp_27700).unlink(missing_ok=True)
    
    total_area = sum([p.area for p in filtered])
    print(f"\nComplete! Generated {len(filtered)} hotspots")
    print(f"Total area: {total_area:,.0f} sqm ({total_area/1e6:.2f} sq km)")

if __name__ == "__main__":
    # Check if we have the input file
    input_file = Path("build/listed_buildings.geojson")
    if not input_file.exists():
        print("Error: build/listed_buildings.geojson not found")
        print("Please run the original ingest first")
        exit(1)
    
    # Process with default parameters
    process_in_27700()