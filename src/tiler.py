import subprocess
import json
import shutil
from pathlib import Path
from typing import Optional, Dict, Any
from src.logging_cfg import get_logger

logger = get_logger(__name__)

def check_command_exists(command: str) -> bool:
    """Check if a command exists in the system PATH."""
    return shutil.which(command) is not None

def run_tippecanoe(
    geojson_path: Path,
    output_path: Path,
    layer_name: str,
    min_zoom: int = 4,
    max_zoom: int = 14,
    drop_densest: bool = True,
    preserve_attributes: bool = True
) -> Path:
    """
    Run tippecanoe to build MBTiles from GeoJSON.
    
    Args:
        geojson_path: Input GeoJSON file
        output_path: Output MBTiles file path
        layer_name: Name for the vector tile layer
        min_zoom: Minimum zoom level
        max_zoom: Maximum zoom level
        drop_densest: Whether to drop densest features as needed
        preserve_attributes: Whether to preserve all attributes
    """
    if not check_command_exists("tippecanoe"):
        raise RuntimeError("tippecanoe not found in PATH")
    
    logger.info(f"Running tippecanoe for {geojson_path}")
    logger.info(f"Layer: {layer_name}, zoom range: {min_zoom}-{max_zoom}")
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    cmd = [
        "tippecanoe",
        "-o", str(output_path),
        "-l", layer_name,
        "-z", str(max_zoom),
        "-Z", str(min_zoom),
        "--force",
        "--no-feature-limit",
        "--no-tile-size-limit"
    ]
    
    if drop_densest:
        cmd.append("--drop-densest-as-needed")
    
    if preserve_attributes:
        cmd.extend(["-y", "", "-pC"])
    
    cmd.append(str(geojson_path))
    
    logger.debug(f"Command: {' '.join(cmd)}")
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        logger.error(f"Tippecanoe failed: {result.stderr}")
        raise RuntimeError(f"Tippecanoe failed: {result.stderr}")
    
    if output_path.exists():
        file_size_mb = output_path.stat().st_size / (1024 * 1024)
        logger.info(f"Created MBTiles at {output_path} ({file_size_mb:.2f} MB)")
    else:
        raise RuntimeError(f"MBTiles file not created: {output_path}")
    
    return output_path

def mbtiles_to_pmtiles(mbtiles_path: Path, pmtiles_path: Path) -> Path:
    """Convert MBTiles to PMTiles format."""
    if not check_command_exists("pmtiles"):
        logger.warning("pmtiles CLI not found, keeping MBTiles format")
        shutil.copy2(mbtiles_path, pmtiles_path.with_suffix('.mbtiles'))
        return pmtiles_path.with_suffix('.mbtiles')
    
    logger.info(f"Converting {mbtiles_path} to PMTiles")
    
    pmtiles_path.parent.mkdir(parents=True, exist_ok=True)
    
    cmd = ["pmtiles", "convert", str(mbtiles_path), str(pmtiles_path)]
    
    logger.debug(f"Command: {' '.join(cmd)}")
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        logger.error(f"PMTiles conversion failed: {result.stderr}")
        logger.warning("Falling back to MBTiles format")
        shutil.copy2(mbtiles_path, pmtiles_path.with_suffix('.mbtiles'))
        return pmtiles_path.with_suffix('.mbtiles')
    
    if pmtiles_path.exists():
        file_size_mb = pmtiles_path.stat().st_size / (1024 * 1024)
        logger.info(f"Created PMTiles at {pmtiles_path} ({file_size_mb:.2f} MB)")
    else:
        raise RuntimeError(f"PMTiles file not created: {pmtiles_path}")
    
    return pmtiles_path

def package_tiles(
    points_geojson: Path,
    polys_geojson: Path,
    docs_dir: Path,
    min_zoom: int = 4,
    max_zoom: int = 14,
    tippecanoe_options: Optional[Dict[str, Any]] = None
) -> Dict[str, Path]:
    """
    Package point and polygon data into vector tiles.
    
    Args:
        points_geojson: Path to points GeoJSON file
        polys_geojson: Path to polygons GeoJSON file
        docs_dir: Output directory for tiles
        min_zoom: Minimum zoom level
        max_zoom: Maximum zoom level
        tippecanoe_options: Additional options for tippecanoe
    
    Returns:
        Dictionary with paths to generated tiles
    """
    points_geojson = Path(points_geojson)
    polys_geojson = Path(polys_geojson)
    docs_dir = Path(docs_dir)
    
    if not points_geojson.exists():
        raise FileNotFoundError(f"Points GeoJSON not found: {points_geojson}")
    if not polys_geojson.exists():
        raise FileNotFoundError(f"Polygons GeoJSON not found: {polys_geojson}")
    
    temp_dir = Path("build/temp_tiles")
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    options = tippecanoe_options or {}
    
    # Process points layer
    points_mbtiles = temp_dir / "listed_buildings.mbtiles"
    run_tippecanoe(
        points_geojson,
        points_mbtiles,
        "listed_buildings",
        min_zoom=min_zoom,
        max_zoom=max_zoom,
        drop_densest=options.get("drop_densest_points", True),
        preserve_attributes=True
    )
    
    # Process hotspots layer
    hotspots_mbtiles = temp_dir / "hotspots.mbtiles"
    run_tippecanoe(
        polys_geojson,
        hotspots_mbtiles,
        "hotspots",
        min_zoom=min_zoom,
        max_zoom=max_zoom,
        drop_densest=options.get("drop_densest_hotspots", False),
        preserve_attributes=True
    )
    
    # Convert to PMTiles and move to docs directory
    docs_dir.mkdir(parents=True, exist_ok=True)
    
    points_pmtiles = docs_dir / "listed_buildings.pmtiles"
    points_final = mbtiles_to_pmtiles(points_mbtiles, points_pmtiles)
    
    hotspots_pmtiles = docs_dir / "hotspots.pmtiles"
    hotspots_final = mbtiles_to_pmtiles(hotspots_mbtiles, hotspots_pmtiles)
    
    # Clean up temp files
    try:
        points_mbtiles.unlink(missing_ok=True)
        hotspots_mbtiles.unlink(missing_ok=True)
    except Exception as e:
        logger.warning(f"Could not clean up temp files: {e}")
    
    logger.info(f"Packaging complete. Tiles saved to {docs_dir}")
    
    return {
        "points": points_final,
        "hotspots": hotspots_final
    }