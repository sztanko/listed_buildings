# Listed Buildings Map

Interactive map visualization of Historic England's listed buildings dataset using MapLibre GL JS and PMTiles.

## Quick Start

```bash
# Build everything
make build

# Start local server
make serve
```

Then open http://localhost:8080 in your browser.

## Features

- 379,596 listed buildings as interactive points
- Hotspot areas showing building concentrations
- Click buildings for full details
- Mobile-responsive design
- Fast PMTiles vector rendering

## Customization

Edit `docs/config.js` to change basemap style or adjust hotspot generation parameters in the Makefile.

## Technical Notes

- Python 3.13 compatibility workarounds included
- Data source: Historic England Listed Buildings
- Original coordinates in British National Grid (EPSG:27700)
- Deployable to GitHub Pages
