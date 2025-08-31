# Data Sources and References

## Primary Data Source

### National Heritage List for England (NHLE)
- **Provider:** Historic England
- **Dataset:** Listed Buildings
- **Access URL:** https://opendata-historicengland.hub.arcgis.com/datasets/historicengland::national-heritage-list-for-england-nhle/explore?layer=0
- **License:** Open Government Licence v3.0
- **Last Updated:** Regularly updated by Historic England
- **Coverage:** All listed buildings in England (approximately 380,000 entries)

## Data Fields

The dataset includes the following key attributes:
- **List Entry Number:** Unique identifier for each listing
- **Name:** Official name of the listed building
- **Grade:** Classification (Grade I, Grade II*, Grade II)
- **Location:** Address and geographic coordinates (OSGB 1936 / British National Grid)
- **List Date:** Date when the building was first listed
- **Amended Date:** Date of most recent amendment to the listing

## Grading System

### Grade I
Buildings of exceptional interest, sometimes considered to be internationally important (2.5% of listed buildings)

### Grade II*
Particularly important buildings of more than special interest (5.8% of listed buildings)

### Grade II
Buildings of special interest, warranting every effort to preserve them (91.7% of listed buildings)

## Technical Implementation

### Coordinate System
- **Original:** EPSG:27700 (OSGB 1936 / British National Grid)
- **Transformed to:** EPSG:4326 (WGS84) for web mapping

### Data Processing
- CSV ingestion with coordinate transformation
- Spatial clustering using buffer operations (200m buffer, 180m negative buffer)
- Hotspot generation for areas with high density of listed buildings
- Vector tile generation using Tippecanoe
- PMTiles format for efficient web serving

### Technologies Used
- **Python:** GeoPandas, Shapely for spatial processing
- **GDAL/OGR:** Coordinate transformation
- **Tippecanoe:** Vector tile generation
- **PMTiles:** Static vector tile hosting
- **MapLibre GL JS:** Interactive web mapping
- **GitHub Actions:** Automated build and deployment

## Source Code

- **Repository:** https://github.com/sztanko/listed_buildings
- **License:** [Specify your license]
- **Author:** Dominik Stanisław Suchora

## Attribution

When using this data or visualization, please cite:
- Historic England for the original NHLE data
- This project repository for the visualization implementation

## Updates

The data pipeline automatically processes the latest available NHLE data through GitHub Actions on each push to the main branch.

## Contact

For questions about the data processing or visualization, please open an issue on the GitHub repository.