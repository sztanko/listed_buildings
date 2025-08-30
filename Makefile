.PHONY: env ingest hotspots package build serve clean help

# Default target
help:
	@echo "Listed Buildings Map - Build System"
	@echo ""
	@echo "Available targets:"
	@echo "  make env       - Create virtual environment and install dependencies"
	@echo "  make ingest    - Ingest CSV data to GeoJSON/Parquet"
	@echo "  make hotspots  - Generate hotspot polygons"
	@echo "  make package   - Create PMTiles from GeoJSON"
	@echo "  make build     - Run full pipeline (ingest → hotspots → package)"
	@echo "  make serve     - Start local web server"
	@echo "  make clean     - Remove build artifacts"

env:
	python3 -m venv .venv
	. .venv/bin/activate && pip install --upgrade pip
	. .venv/bin/activate && pip install -r requirements.txt

ingest:
	@echo "Ingesting CSV data..."
	. .venv/bin/activate && python ingest.py

hotspots:
	@echo "Generating hotspots in EPSG:27700 (native British National Grid)..."
	. .venv/bin/activate && python process_native.py

package:
	@echo "Packaging tiles..."
	@mkdir -p docs/tiles
	@if command -v tippecanoe >/dev/null 2>&1; then \
		echo "Using tippecanoe to create tiles..."; \
		tippecanoe -o build/listed_buildings.mbtiles -l listed_buildings -z14 -Z4 \
			--drop-densest-as-needed --force build/listed_buildings.geojson; \
		tippecanoe -o build/hotspots.mbtiles -l hotspots -z14 -Z4 \
			--force build/hotspots.geojson; \
		if command -v pmtiles >/dev/null 2>&1; then \
			echo "Converting to PMTiles..."; \
			pmtiles convert build/listed_buildings.mbtiles docs/tiles/listed_buildings.pmtiles; \
			pmtiles convert build/hotspots.mbtiles docs/tiles/hotspots.pmtiles; \
		else \
			echo "PMTiles not found, copying MBTiles..."; \
			cp build/listed_buildings.mbtiles docs/tiles/; \
			cp build/hotspots.mbtiles docs/tiles/; \
		fi \
	else \
		echo "Warning: tippecanoe not found. Tiles not created."; \
		echo "Install tippecanoe to generate vector tiles."; \
	fi

build: ingest hotspots package
	@echo "Build complete!"
	@ls -lh docs/tiles/ 2>/dev/null || echo "No tiles generated yet"

serve:
	@echo "Starting web server on http://localhost:8080"
	@cd docs && npx http-server -p 8080 -c-1

clean:
	rm -rf build/
	rm -rf docs/tiles/*.pmtiles
	rm -rf docs/tiles/*.mbtiles
	@echo "Cleaned build artifacts"