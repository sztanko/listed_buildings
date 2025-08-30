import pandas as pd
import geopandas as gpd
from pathlib import Path
from typing import Optional, Union
from shapely.geometry import Point
from pyproj import CRS
from src.logging_cfg import get_logger

logger = get_logger(__name__)

class IOError(Exception):
    pass

def normalize_column_names(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = [col.strip().lower().replace(' ', '_').replace('-', '_') for col in df.columns]
    return df

def read_csv_to_gdf(
    csv_path: Union[str, Path],
    lon_col: Optional[str] = None,
    lat_col: Optional[str] = None,
    x_col: Optional[str] = None,
    y_col: Optional[str] = None,
    src_crs: Optional[str] = None
) -> gpd.GeoDataFrame:
    csv_path = Path(csv_path)
    
    if not csv_path.exists():
        raise IOError(f"CSV file not found: {csv_path}")
    
    logger.info(f"Reading CSV from {csv_path}")
    
    try:
        df = pd.read_csv(csv_path)
        initial_count = len(df)
        logger.info(f"Read {initial_count} rows from CSV", extra={"rows": initial_count})
    except Exception as e:
        logger.error(f"Failed to read CSV: {e}")
        raise IOError(f"Failed to read CSV: {e}")
    
    df = normalize_column_names(df)
    logger.debug(f"Normalized column names: {list(df.columns)[:10]}")
    
    if lon_col and lat_col:
        lon_col_norm = lon_col.lower().replace(' ', '_').replace('-', '_')
        lat_col_norm = lat_col.lower().replace(' ', '_').replace('-', '_')
        
        if lon_col_norm not in df.columns or lat_col_norm not in df.columns:
            available_cols = list(df.columns)
            raise IOError(f"Columns {lon_col}/{lat_col} not found. Available: {available_cols[:20]}")
        
        logger.info(f"Using lon/lat columns: {lon_col_norm}, {lat_col_norm}")
        
        df_valid = df.dropna(subset=[lon_col_norm, lat_col_norm])
        dropped = len(df) - len(df_valid)
        if dropped > 0:
            logger.warning(f"Dropped {dropped} rows with missing coordinates")
        
        try:
            df_valid = df_valid.copy()
            df_valid[lon_col_norm] = pd.to_numeric(df_valid[lon_col_norm], errors='coerce')
            df_valid[lat_col_norm] = pd.to_numeric(df_valid[lat_col_norm], errors='coerce')
            df_valid = df_valid.dropna(subset=[lon_col_norm, lat_col_norm])
            
            if df_valid[lon_col_norm].min() < -180 or df_valid[lon_col_norm].max() > 180:
                logger.warning("Longitude values outside [-180, 180] range")
            if df_valid[lat_col_norm].min() < -90 or df_valid[lat_col_norm].max() > 90:
                logger.warning("Latitude values outside [-90, 90] range")
            
            geometry = gpd.points_from_xy(df_valid[lon_col_norm], df_valid[lat_col_norm])
            gdf = gpd.GeoDataFrame(df_valid, geometry=geometry, crs="EPSG:4326")
        except Exception as e:
            logger.error(f"Failed to create geometry from lon/lat: {e}")
            raise IOError(f"Failed to create geometry from lon/lat: {e}")
            
    elif x_col and y_col and src_crs:
        x_col_norm = x_col.lower().replace(' ', '_').replace('-', '_')
        y_col_norm = y_col.lower().replace(' ', '_').replace('-', '_')
        
        if x_col_norm not in df.columns or y_col_norm not in df.columns:
            available_cols = list(df.columns)
            raise IOError(f"Columns {x_col}/{y_col} not found. Available: {available_cols[:20]}")
        
        logger.info(f"Using x/y columns: {x_col_norm}, {y_col_norm} with CRS: {src_crs}")
        
        df_valid = df.dropna(subset=[x_col_norm, y_col_norm])
        dropped = len(df) - len(df_valid)
        if dropped > 0:
            logger.warning(f"Dropped {dropped} rows with missing coordinates")
        
        try:
            df_valid = df_valid.copy()
            df_valid[x_col_norm] = pd.to_numeric(df_valid[x_col_norm], errors='coerce')
            df_valid[y_col_norm] = pd.to_numeric(df_valid[y_col_norm], errors='coerce')
            df_valid = df_valid.dropna(subset=[x_col_norm, y_col_norm])
            
            # Workaround for Python 3.13 pyproj issue: 
            # Create GeoDataFrame, save with GDAL, read back
            geometry = gpd.points_from_xy(df_valid[x_col_norm], df_valid[y_col_norm])
            gdf = gpd.GeoDataFrame(df_valid, geometry=geometry)
            
            # Save to temporary file with CRS
            import tempfile
            import subprocess
            
            with tempfile.NamedTemporaryFile(suffix='.geojson', delete=False) as tmp:
                temp_path = tmp.name
            
            # Save without CRS first - use fiona to avoid pyproj
            import json
            features = []
            for idx, row in df_valid.iterrows():
                features.append({
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [float(row[x_col_norm]), float(row[y_col_norm])]
                    },
                    "properties": {k: v for k, v in row.items() if k not in [x_col_norm, y_col_norm]}
                })
            
            geojson_dict = {
                "type": "FeatureCollection",
                "features": features
            }
            
            with open(temp_path, 'w') as f:
                json.dump(geojson_dict, f)
            
            # Use ogr2ogr to assign and transform CRS
            temp_out = temp_path.replace('.geojson', '_4326.geojson')
            cmd = [
                'ogr2ogr', '-f', 'GeoJSON',
                '-s_srs', src_crs,
                '-t_srs', 'EPSG:4326',
                temp_out, temp_path
            ]
            subprocess.run(cmd, check=True, capture_output=True)
            
            # Read back the transformed file
            gdf = gpd.read_file(temp_out)
            
            # Clean up temp files
            Path(temp_path).unlink(missing_ok=True)
            Path(temp_out).unlink(missing_ok=True)
            
            logger.info(f"Transformed {len(gdf)} points from {src_crs} to WGS84 using GDAL")
        except Exception as e:
            logger.error(f"Failed to create geometry from x/y: {e}")
            raise IOError(f"Failed to create geometry from x/y: {e}")
    else:
        raise IOError("Must provide either lon_col/lat_col or x_col/y_col/src_crs")
    
    valid_geom = gdf.geometry.is_valid
    if not valid_geom.all():
        invalid_count = (~valid_geom).sum()
        logger.warning(f"Found {invalid_count} invalid geometries, removing them")
        gdf = gdf[valid_geom]
    
    final_count = len(gdf)
    logger.info(
        f"Successfully loaded {final_count} records from {initial_count} total",
        extra={
            "records_loaded": final_count,
            "records_dropped": initial_count - final_count,
            "bounds": list(gdf.total_bounds),
            "crs": str(gdf.crs)
        }
    )
    
    return gdf

def save_gdf(
    gdf: gpd.GeoDataFrame,
    parquet_path: Optional[Union[str, Path]] = None,
    geojson_path: Optional[Union[str, Path]] = None
):
    if not parquet_path and not geojson_path:
        raise IOError("Must provide at least one output path")
    
    if parquet_path:
        parquet_path = Path(parquet_path)
        parquet_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            gdf.to_parquet(parquet_path)
            file_size_mb = parquet_path.stat().st_size / (1024 * 1024)
            logger.info(
                f"Saved {len(gdf)} records to {parquet_path}",
                extra={"records": len(gdf), "size_mb": round(file_size_mb, 2)}
            )
        except Exception as e:
            logger.error(f"Failed to save Parquet: {e}")
            raise IOError(f"Failed to save Parquet: {e}")
    
    if geojson_path:
        geojson_path = Path(geojson_path)
        geojson_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            gdf.to_file(geojson_path, driver="GeoJSON")
            file_size_mb = geojson_path.stat().st_size / (1024 * 1024)
            logger.info(
                f"Saved {len(gdf)} records to {geojson_path}",
                extra={"records": len(gdf), "size_mb": round(file_size_mb, 2)}
            )
        except Exception as e:
            logger.error(f"Failed to save GeoJSON: {e}")
            raise IOError(f"Failed to save GeoJSON: {e}")

def load_gdf(
    file_path: Union[str, Path]
) -> gpd.GeoDataFrame:
    file_path = Path(file_path)
    
    if not file_path.exists():
        raise IOError(f"File not found: {file_path}")
    
    try:
        if file_path.suffix == '.parquet':
            gdf = gpd.read_parquet(file_path)
        elif file_path.suffix in ['.geojson', '.json']:
            gdf = gpd.read_file(file_path)
        else:
            raise IOError(f"Unsupported file format: {file_path.suffix}")
        
        logger.info(
            f"Loaded {len(gdf)} records from {file_path}",
            extra={"records": len(gdf), "crs": str(gdf.crs)}
        )
        return gdf
        
    except Exception as e:
        logger.error(f"Failed to load file: {e}")
        raise IOError(f"Failed to load file: {e}")