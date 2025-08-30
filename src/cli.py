import typer
from pathlib import Path
from src.logging_cfg import get_logger
from src.io_utils import read_csv_to_gdf, save_gdf, load_gdf
from src.geom_ops import create_hotspots
from src.tiler import package_tiles
import pandas as pd
import geopandas as gpd

logger = get_logger(__name__)

app = typer.Typer(
    pretty_exceptions_enable=False,
    help="Listed Buildings Map CLI - Process and tile historic building data"
)

@app.command()
def ingest(
    csv_path: Path = typer.Option("data/listed_buildings.csv", help="Path to CSV file"),
    lon_col: str = typer.Option(None, help="Longitude column name"),
    lat_col: str = typer.Option(None, help="Latitude column name"),
    x_col: str = typer.Option(None, help="X/Easting column name"),
    y_col: str = typer.Option(None, help="Y/Northing column name"),
    src_crs: str = typer.Option("EPSG:27700", help="Source CRS for x/y coordinates")
):
    """
    Ingest CSV data and convert to GeoJSON/Parquet.
    
    Reads listed buildings CSV, auto-detects or uses specified coordinate columns,
    and outputs to build/listed_buildings.geojson and .parquet
    """
    logger.info("=" * 60)
    logger.info("INGEST: Starting CSV ingestion")
    logger.info("=" * 60)
    
    if lon_col and lat_col:
        logger.info(f"Using specified lon/lat columns: {lon_col}, {lat_col}")
        gdf = read_csv_to_gdf(csv_path, lon_col=lon_col, lat_col=lat_col)
    elif x_col and y_col:
        logger.info(f"Using specified x/y columns: {x_col}, {y_col} with CRS {src_crs}")
        gdf = read_csv_to_gdf(csv_path, x_col=x_col, y_col=y_col, src_crs=src_crs)
    else:
        logger.info("No coordinate columns specified, attempting auto-detection")
        df = pd.read_csv(csv_path, nrows=5)
        cols_lower = [col.lower().replace(' ', '_').replace('-', '_') for col in df.columns]
        
        if 'longitude' in cols_lower and 'latitude' in cols_lower:
            logger.info("Auto-detected: longitude/latitude columns")
            gdf = read_csv_to_gdf(csv_path, lon_col='longitude', lat_col='latitude')
        elif 'lon' in cols_lower and 'lat' in cols_lower:
            logger.info("Auto-detected: lon/lat columns")
            gdf = read_csv_to_gdf(csv_path, lon_col='lon', lat_col='lat')
        elif 'easting' in cols_lower and 'northing' in cols_lower:
            logger.info(f"Auto-detected: easting/northing columns with CRS {src_crs}")
            gdf = read_csv_to_gdf(csv_path, x_col='easting', y_col='northing', src_crs=src_crs)
        elif 'x' in cols_lower and 'y' in cols_lower:
            logger.info(f"Auto-detected: x/y columns with CRS {src_crs}")
            gdf = read_csv_to_gdf(csv_path, x_col='x', y_col='y', src_crs=src_crs)
        else:
            available_cols = list(df.columns)[:20]
            logger.error(f"Could not auto-detect coordinate columns. Available: {available_cols}")
            raise ValueError("Could not auto-detect coordinate columns. Please specify manually.")
    
    # Save outputs
    save_gdf(gdf, "build/listed_buildings.parquet", "build/listed_buildings.geojson")
    
    # Log summary statistics
    bounds = gdf.total_bounds
    logger.info(f"Ingested {len(gdf)} records")
    logger.info(f"Bounds: [{bounds[0]:.4f}, {bounds[1]:.4f}, {bounds[2]:.4f}, {bounds[3]:.4f}]")
    logger.info(f"CRS: {gdf.crs}")
    logger.info("=" * 60)
    logger.info("INGEST: Complete")
    logger.info("=" * 60)

@app.command()
def hotspots(
    buffer: float = typer.Option(200, help="Buffer radius in meters"),
    negative_buffer: float = typer.Option(0, help="Negative buffer in meters (shrink after union)"),
    min_area: float = typer.Option(1000, help="Minimum area in square meters"),
    proj_crs: str = typer.Option("EPSG:3857", help="Projection CRS for metric operations")
):
    """
    Generate hotspot polygons from point data.
    
    Reads points, runs buffer→union→optional negative buffer→area filter pipeline,
    and outputs to build/hotspots.geojson and .parquet
    """
    logger.info("=" * 60)
    logger.info("HOTSPOTS: Starting hotspot generation")
    logger.info("=" * 60)
    
    # Load points
    parquet_path = Path("build/listed_buildings.parquet")
    if not parquet_path.exists():
        logger.error(f"Points file not found: {parquet_path}")
        logger.error("Run 'ingest' command first")
        raise typer.Exit(1)
    
    gdf = load_gdf(parquet_path)
    logger.info(f"Loaded {len(gdf)} points")
    
    # Generate hotspots
    hotspots_gdf = create_hotspots(
        gdf,
        buffer_meters=buffer,
        negative_buffer_meters=negative_buffer,
        min_area_sqm=min_area,
        proj_crs=proj_crs
    )
    
    # Save outputs
    save_gdf(hotspots_gdf, "build/hotspots.parquet", "build/hotspots.geojson")
    
    # Log summary
    if len(hotspots_gdf) > 0:
        bounds = hotspots_gdf.total_bounds
        logger.info(f"Generated {len(hotspots_gdf)} hotspot polygons")
        logger.info(f"Bounds: [{bounds[0]:.4f}, {bounds[1]:.4f}, {bounds[2]:.4f}, {bounds[3]:.4f}]")
        logger.info(f"Total area: {hotspots_gdf['area_m2'].sum():,.0f} sqm")
    else:
        logger.warning("No hotspots generated with current parameters")
    
    logger.info("=" * 60)
    logger.info("HOTSPOTS: Complete")
    logger.info("=" * 60)

@app.command()
def package(
    points: Path = typer.Option("build/listed_buildings.geojson", help="Points GeoJSON path"),
    polys: Path = typer.Option("build/hotspots.geojson", help="Polygons GeoJSON path"),
    docs_dir: Path = typer.Option("docs/tiles", help="Output directory for tiles"),
    min_zoom: int = typer.Option(4, help="Minimum zoom level"),
    max_zoom: int = typer.Option(14, help="Maximum zoom level")
):
    """
    Package GeoJSON into PMTiles for web serving.
    
    Calls tippecanoe to produce docs/tiles/listed_buildings.pmtiles
    and docs/tiles/hotspots.pmtiles, logging counts, bounds, and file sizes.
    """
    logger.info("=" * 60)
    logger.info("PACKAGE: Starting tile packaging")
    logger.info("=" * 60)
    
    # Check input files exist
    if not points.exists():
        logger.error(f"Points file not found: {points}")
        logger.error("Run 'ingest' command first")
        raise typer.Exit(1)
    
    if not polys.exists():
        logger.error(f"Polygons file not found: {polys}")
        logger.error("Run 'hotspots' command first")
        raise typer.Exit(1)
    
    # Load and log statistics
    points_gdf = gpd.read_file(points)
    polys_gdf = gpd.read_file(polys)
    
    logger.info(f"Points: {len(points_gdf)} features")
    logger.info(f"Polygons: {len(polys_gdf)} features")
    
    # Package tiles
    try:
        tile_paths = package_tiles(
            points_geojson=points,
            polys_geojson=polys,
            docs_dir=docs_dir,
            min_zoom=min_zoom,
            max_zoom=max_zoom
        )
        
        # Log output file sizes
        for name, path in tile_paths.items():
            if path.exists():
                size_mb = path.stat().st_size / (1024 * 1024)
                logger.info(f"{name}: {path} ({size_mb:.2f} MB)")
        
    except Exception as e:
        logger.error(f"Packaging failed: {e}")
        raise typer.Exit(1)
    
    logger.info("=" * 60)
    logger.info("PACKAGE: Complete")
    logger.info("=" * 60)

@app.command()
def all(
    buffer: float = typer.Option(200, help="Buffer radius in meters"),
    negative_buffer: float = typer.Option(0, help="Negative buffer in meters"),
    min_area: float = typer.Option(1000, help="Minimum area in square meters")
):
    """Run full pipeline: ingest → hotspots → package."""
    logger.info("Running full pipeline")
    
    # Run ingest
    ingest()
    
    # Run hotspots
    hotspots(buffer=buffer, negative_buffer=negative_buffer, min_area=min_area)
    
    # Run package
    package()
    
    logger.info("Full pipeline complete")

if __name__ == "__main__":
    app()