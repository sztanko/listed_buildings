import geopandas as gpd
from shapely.ops import unary_union
from shapely.geometry import Polygon, MultiPolygon
from typing import Union, Optional
from pathlib import Path
from src.logging_cfg import get_logger

logger = get_logger(__name__)

def reproject_to_metric(gdf: gpd.GeoDataFrame, proj_crs: str = "EPSG:3857") -> gpd.GeoDataFrame:
    """Reproject GeoDataFrame to a metric CRS."""
    logger.info(f"Reprojecting {len(gdf)} features from {gdf.crs} to {proj_crs}")
    gdf_proj = gdf.to_crs(proj_crs)
    return gdf_proj

def buffer_points(gdf: gpd.GeoDataFrame, buffer_meters: float) -> gpd.GeoSeries:
    """Buffer all points by specified distance in meters."""
    logger.info(f"Buffering {len(gdf)} points by {buffer_meters}m")
    buffered = gdf.geometry.buffer(buffer_meters)
    return buffered

def dissolve_geometries(geometries: gpd.GeoSeries) -> Union[Polygon, MultiPolygon]:
    """Dissolve overlapping geometries using unary union."""
    logger.info("Dissolving overlapping geometries")
    union_geom = unary_union(geometries)
    return union_geom

def apply_negative_buffer(geom: Union[Polygon, MultiPolygon], negative_buffer_meters: float) -> Union[Polygon, MultiPolygon]:
    """Apply negative buffer to shrink geometry."""
    if negative_buffer_meters > 0:
        logger.info(f"Applying {negative_buffer_meters}m negative buffer")
        geom = geom.buffer(-negative_buffer_meters)
    return geom

def explode_multipart(geom: Union[Polygon, MultiPolygon]) -> list:
    """Explode multipart geometries to individual parts."""
    if hasattr(geom, 'geoms'):
        polygons = list(geom.geoms)
        logger.info(f"Exploded multipart geometry to {len(polygons)} parts")
    else:
        polygons = [geom] if not geom.is_empty else []
    return polygons

def compute_areas(polygons: list, crs: str) -> list:
    """Compute area in square meters for each polygon."""
    areas = [p.area for p in polygons]
    return areas

def filter_by_area(polygons: list, areas: list, min_area_sqm: float) -> tuple:
    """Filter polygons by minimum area threshold."""
    filtered = [(p, a) for p, a in zip(polygons, areas) if a >= min_area_sqm]
    logger.info(f"Filtered from {len(polygons)} to {len(filtered)} polygons (min area: {min_area_sqm} sqm)")
    
    if filtered:
        polygons_filtered, areas_filtered = zip(*filtered)
        return list(polygons_filtered), list(areas_filtered)
    return [], []

def create_hotspots(
    gdf: gpd.GeoDataFrame,
    buffer_meters: float = 200,
    negative_buffer_meters: float = 0,
    min_area_sqm: float = 1000,
    proj_crs: str = "EPSG:3857"
) -> gpd.GeoDataFrame:
    """
    Create hotspot polygons from point data.
    
    Pipeline:
    1. Reproject to metric CRS
    2. Buffer all points
    3. Dissolve via unary_union
    4. Optional negative buffer
    5. Explode multipart geometries
    6. Compute areas
    7. Filter by min_area
    8. Return GeoDataFrame with id and area_m2
    """
    logger.info(
        f"Creating hotspots: buffer={buffer_meters}m, "
        f"negative_buffer={negative_buffer_meters}m, "
        f"min_area={min_area_sqm}sqm, proj_crs={proj_crs}"
    )
    
    # Step 1: Reproject to metric CRS
    gdf_proj = reproject_to_metric(gdf, proj_crs)
    
    # Step 2: Buffer all points
    buffered = buffer_points(gdf_proj, buffer_meters)
    
    # Step 3: Dissolve via unary union
    union_geom = dissolve_geometries(buffered)
    
    # Step 4: Optional negative buffer
    union_geom = apply_negative_buffer(union_geom, negative_buffer_meters)
    
    # Step 5: Explode multipart geometries
    polygons = explode_multipart(union_geom)
    
    if not polygons:
        logger.warning("No polygons created after buffering and union")
        return gpd.GeoDataFrame(
            {'id': [], 'area_m2': []},
            geometry=[],
            crs=proj_crs
        ).to_crs("EPSG:4326")
    
    # Step 6: Compute areas
    areas = compute_areas(polygons, proj_crs)
    
    # Step 7: Filter by minimum area
    polygons_filtered, areas_filtered = filter_by_area(polygons, areas, min_area_sqm)
    
    if not polygons_filtered:
        logger.warning(f"No polygons met minimum area threshold of {min_area_sqm} sqm")
        return gpd.GeoDataFrame(
            {'id': [], 'area_m2': []},
            geometry=[],
            crs=proj_crs
        ).to_crs("EPSG:4326")
    
    # Step 8: Create GeoDataFrame with id and area_m2
    hotspots_gdf = gpd.GeoDataFrame(
        {
            'id': range(len(polygons_filtered)),
            'area_m2': areas_filtered
        },
        geometry=polygons_filtered,
        crs=proj_crs
    )
    
    # Reproject back to WGS84
    hotspots_gdf = hotspots_gdf.to_crs("EPSG:4326")
    
    # Log statistics
    total_area = sum(areas_filtered)
    logger.info(
        f"Created {len(hotspots_gdf)} hotspot polygons, "
        f"total area: {total_area:,.0f} sqm"
    )
    
    return hotspots_gdf

def save_hotspots(
    hotspots_gdf: gpd.GeoDataFrame,
    parquet_path: Optional[Union[str, Path]] = None,
    geojson_path: Optional[Union[str, Path]] = None
):
    """Save hotspots to GeoParquet and/or GeoJSON."""
    from src.io_utils import save_gdf
    save_gdf(hotspots_gdf, parquet_path, geojson_path)