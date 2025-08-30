# CLAUDE.md

> Put this file at the repo root as `CLAUDE.md`.

```markdown
# CLAUDE.md — Listed Buildings Map

You are Claude Code. Please follow this plan precisely and keep changes small and reviewable (many small PRs > one huge PR). Use conventional commits. Prioritize reproducibility and fast iteration in Codespaces.

## Goal

Create a full-screen, mobile-friendly MapLibre app (served via GitHub Pages) that shows:
1) A pale, **hosted** vector basemap (no self-hosting),
2) **Hotspot polygons**: areas with high concentration of listed buildings, created by buffering points → unioning → (optional) negative buffer → filtering by min area,
3) **Listed buildings** as clickable points with popups showing all CSV attributes.

**Input:** `data/listed_buildings.csv` (Historic England export).  
**Output (served statically):** `/docs/index.html` + vector data as **PMTiles**.

---

## Tech constraints

- **Hosting:** GitHub Pages (`/docs`).
- **Processing:** Python 3.12, `virtualenv` (in `.venv` directory), **Typer** CLI (`pretty_exceptions_enable=False`), structured **logging**.
- **Spatial stack:** `geopandas`, `pyproj`, `shapely`, **GDAL/OGR** available in Codespaces.
- **Tiling:** Prefer **Tippecanoe** → **PMTiles** (static hosting friendly).
- **Basemap:** Hosted vector style; configurable via `/docs/config.js`. Default to MapLibre demo style `https://demotiles.maplibre.org/style.json` (no key). Allow switching to MapTiler style with an API key if the maintainer sets it.

---

## Repo layout

Create this structure:

```

.
├─ .devcontainer/
│  ├─ devcontainer.json
│  └─ Dockerfile
├─ data/
│  └─ listed\_buildings.csv                # (provided by user)
├─ src/
│  ├─ **init**.py
│  ├─ cli.py                              # Typer CLI
│  ├─ io\_utils.py                         # reading/writing, validation
│  ├─ geom\_ops.py                         # buffer/union/filters
│  ├─ tiler.py                            # tippecanoe/pmtiles helpers
│  └─ logging\_cfg.py                      # logging setup
├─ docs/
│  ├─ index.html
│  ├─ app.js
│  ├─ styles.css
│  ├─ config.js                           # basemap + layer config
│  └─ tiles/                              # output PMTiles lives here
├─ tests/
│  └─ test\_geom\_ops.py
├─ requirements.txt
├─ Makefile
├─ README.md
└─ CLAUDE.md

```

---

## Step 1 — Devcontainer (GDAL, Tippecanoe, PMTiles)

Create a Codespaces environment that includes:
- Python 3.12 (with `pip`, `virtualenv`)
- `gdal-bin`, `libgdal-dev` (ensure `ogr2ogr` present)
- `tippecanoe`
- `nodejs` (LTS) for local static serving
- `pmtiles` JS loader (client-side; install via `<script>` CDN in `index.html`)

**Action items:**
1. Add `.devcontainer/Dockerfile` that installs the above on top of `mcr.microsoft.com/devcontainers/base:ubuntu`.
2. Add `.devcontainer/devcontainer.json` to:
   - Run `python -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt`
   - Set default integrated terminal to use the venv.

---

## Step 2 — Python environment

Create `requirements.txt`:

```

typer==0.12.\*
geopandas==1.0.\*
shapely==2.0.\*
pyproj==3.6.\*
pandas==2.2.\*
pyogrio==0.9.\*           # faster vector IO (optional)
fiona==1.9.\*             # optional, GDAL-backed IO
loguru==0.7.\*

```

*(Keep GDAL installed at system level in the devcontainer. Don’t pin GDAL in pip.)*

---

## Step 3 — Typer CLI

Create `src/cli.py` with Typer (`pretty_exceptions_enable=False`) and subcommands:

- `ingest`
  - Inputs: `--csv-path data/listed_buildings.csv`, `--lon-col`, `--lat-col`, or if easting/northing, `--x-col/--y-col --src-crs EPSG:27700`.
  - Normalize column names, drop rows without valid coords.
  - Output: `build/listed_buildings.parquet` + `build/listed_buildings.geojson`
  - Log record count, bounds, CRS.

- `hotspots`
  - Inputs: 
    - `--buffer 200` (meters),
    - `--negative-buffer 0` (meters; if >0, apply after union),
    - `--min-area 1000` (square meters),
    - `--proj-crs EPSG:3857` (for metric ops),
  - Steps:
    1. Reproject to metric CRS.
    2. Buffer all points by `buffer`.
    3. `unary_union` to dissolve.
    4. If `negative-buffer > 0`, apply negative buffer.
    5. Filter polygons by `area >= min-area`.
    6. Save `build/hotspots.parquet` + `build/hotspots.geojson`.
  - Log polygon count, total area.

- `package`
  - Inputs:
    - `--points build/listed_buildings.geojson`
    - `--polys build/hotspots.geojson`
    - `--docs-dir docs/tiles`
    - Tippecanoe config (e.g., `--max-zoom 14 --min-zoom 4 --drop-densest-as-needed`)
  - Actions:
    1. Run `tippecanoe` to produce `.mbtiles` for each layer with layer names: `listed_buildings`, `hotspots`.
    2. Convert `.mbtiles` → **PMTiles** (`.pmtiles`). (Simplest path: use `pmtiles` Go CLI if available; otherwise, use Tippecanoe’s `-o` per layer and concatenate via `tile-join` before PMTiles conversion.)
    3. Place final `.pmtiles` in `docs/tiles/`.
    4. Log sizes, layer summaries.

Add `src/logging_cfg.py` to configure `loguru` (JSON-ish logs to stdout).

---

## Step 4 — Web app (MapLibre + PMTiles)

Build a full-screen app:

- `docs/index.html`
  - Load **MapLibre GL JS**.
  - Load **pmtiles** JS library.
  - Load `app.js` and `config.js`.
  - Full-viewport container `<div id="map"></div>`; include mobile meta tags.

- `docs/config.js`
  - `window.MAP_CONFIG = {`
    - `styleUrl: 'https://demotiles.maplibre.org/style.json'` *(default, pale demo style)*,
    - `center: [-1.6, 53.5]` *(England-ish)*,
    - `zoom: 6`,
    - `tiles: { points: './tiles/listed_buildings.pmtiles', hotspots: './tiles/hotspots.pmtiles' }`,
  - `};`
  - Allow switching to MapTiler style via `styleUrl` and `?key=` if the maintainer wants.

- `docs/app.js`
  - Initialize MapLibre with `styleUrl`.
  - Register `pmtiles` protocol (`new pmtiles.PMTiles(url)` + `map.addSource({ type: 'vector', url: 'pmtiles://...' })`).
  - Add layers:
    - Hotspots fill (pale orange with outline), interactive hover highlight.
    - Points (circle layer) with size by zoom and light color.
  - On click (points), show a popup with **all properties** from the CSV.
  - Add a small control UI to toggle layers and tweak cluster on/off (if applied), and a “Fit to data” button.

- `docs/styles.css`
  - Full-screen map, mobile-friendly popups (wrap, large tap targets), a small top-right controls card.

---

## Step 5 — Makefile

Create a `Makefile` with these targets:

```

.PHONY: env ingest hotspots package build serve clean

env:
python -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt

ingest:
. .venv/bin/activate && python -m src.cli ingest --csv-path data/listed\_buildings.csv

hotspots:
. .venv/bin/activate && python -m src.cli hotspots --buffer 200 --negative-buffer 0 --min-area 1000

package:
. .venv/bin/activate && python -m src.cli package --points build/listed\_buildings.geojson --polys build/hotspots.geojson --docs-dir docs/tiles

build: ingest hotspots package

serve:
npx http-server docs -p 8080 -c-1

clean:
rm -rf build docs/tiles/\*.pmtiles

````

---

## Step 6 — Testing

- `tests/test_geom_ops.py` covering:
  - Buffer → union → filter pipeline produces expected counts and area thresholds.
  - Negative buffer behavior.
- Run with `pytest` (optional to add).

---

## Step 7 — GitHub Pages

- In repo Settings → Pages: build from `main` → `/docs`.
- After running `make build`, commit `/docs` changes (`index.html`, `app.js`, `styles.css`, `config.js`, and `docs/tiles/*.pmtiles`).

---

## Step 8 — Usage

Typical end-to-end run in Codespaces terminal:

```bash
make env
make build
make serve
# Open forwarded port to preview.
````

Tuning the hotspot algorithm:

```bash
python -m src.cli hotspots \
  --buffer 300 \
  --negative-buffer 50 \
  --min-area 2500 \
  --proj-crs EPSG:3857
```

If you switch to a MapTiler style, update `docs/config.js`:

```js
styleUrl: 'https://api.maptiler.com/maps/dataviz/style.json?key=YOUR_KEY'
```

---

## Implementation notes

* **CRS**: Perform buffers/areas in a **metric** CRS (default EPSG:3857). Input CSV might be WGS84 or British National Grid; expose CLI flags to select source CRS.
* **Attributes**: Preserve **all columns** from CSV in the point layer; show everything in the popup (render keys/values dynamically).
* **Performance**: Prefer PMTiles over raw GeoJSON for large datasets. If the dataset is small, you may temporarily wire GeoJSON sources to iterate quickly.
* **Accessibility**: Ensure popups are readable on small screens; use larger line-height and font sizes for mobile.

---

## Deliverables Checklist

* [ ] `.devcontainer` with GDAL + Tippecanoe working in Codespaces
* [ ] Typer CLI with `ingest`, `hotspots`, `package`
* [ ] Logging via `loguru`
* [ ] PMTiles outputs in `/docs/tiles/`
* [ ] MapLibre app loading basemap + PMTiles
* [ ] Mobile-friendly popups
* [ ] Makefile and README
