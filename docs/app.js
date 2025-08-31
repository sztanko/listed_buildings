// Initialize PMTiles protocol
let protocol = new pmtiles.Protocol();
maplibregl.addProtocol('pmtiles', protocol.tile);

// Parse initial position from URL hash if present
function getInitialPosition() {
    const hash = window.location.hash.replace('#', '');
    if (hash) {
        const parts = hash.split('/');
        if (parts.length === 3) {
            const zoom = parseFloat(parts[0]);
            const lat = parseFloat(parts[1]);
            const lng = parseFloat(parts[2]);
            
            if (!isNaN(zoom) && !isNaN(lat) && !isNaN(lng)) {
                return {
                    center: [lng, lat],
                    zoom: zoom
                };
            }
        }
    }
    // Return default position if no valid hash
    return {
        center: window.MAP_CONFIG.center,
        zoom: window.MAP_CONFIG.zoom
    };
}

const initialPosition = getInitialPosition();

// Initialize map with raster basemap
const map = new maplibregl.Map({
    container: 'map',
    style: {
        version: 8,
        sources: {
            'carto-light': {
                type: 'raster',
                tiles: [window.MAP_CONFIG.basemapUrl],
                tileSize: 256,
                attribution: window.MAP_CONFIG.basemapAttribution
            }
        },
        layers: [
            {
                id: 'carto-light',
                type: 'raster',
                source: 'carto-light'
            }
        ]
    },
    center: initialPosition.center,
    zoom: initialPosition.zoom,
    maxZoom: 18,
    minZoom: 3
});

// Store data bounds for fit functionality
let dataBounds = null;

// Wait for map to load
map.on('load', () => {
    // Add hotspots source and layer
    map.addSource('hotspots', {
        type: 'vector',
        url: `pmtiles://${window.MAP_CONFIG.tiles.hotspots}`
    });
    
    map.addLayer({
        id: 'hotspots-fill',
        type: 'fill',
        source: 'hotspots',
        'source-layer': 'hotspots',
        paint: {
            'fill-color': window.MAP_CONFIG.colors.hotspotFill,
            'fill-opacity': 0.7
        }
    });
    
    map.addLayer({
        id: 'hotspots-outline',
        type: 'line',
        source: 'hotspots',
        'source-layer': 'hotspots',
        paint: {
            'line-color': window.MAP_CONFIG.colors.hotspotOutline,
            'line-width': 1.5
        }
    });
    
    // Add points source and layer
    map.addSource('points', {
        type: 'vector',
        url: `pmtiles://${window.MAP_CONFIG.tiles.points}`
    });
    
    map.addLayer({
        id: 'points-layer',
        type: 'circle',
        source: 'points',
        'source-layer': 'listed_buildings',
        minzoom: 11,  // Only show points at zoom level >= 11
        paint: {
            'circle-radius': [
                'interpolate',
                ['linear'],
                ['zoom'],
                11, 0.25,
                14, 2.5,
                16, 4,
                18, 12
            ],
            'circle-color': [
                'case',
                ['==', ['get', 'grade'], 'I'],
                window.MAP_CONFIG.colors.gradeIColor,
                ['==', ['get', 'grade'], 'II*'],
                window.MAP_CONFIG.colors.gradeIIStarColor,  // Grade II* uses darker blue
                window.MAP_CONFIG.colors.gradeIIColor  // Default for Grade II and others
            ],
            'circle-stroke-color': window.MAP_CONFIG.colors.pointOutline,
            'circle-stroke-width': 0.5
        }
    });
    
    // Add hover effect for hotspots
    let hoveredHotspotId = null;
    
    map.on('mousemove', 'hotspots-fill', (e) => {
        map.getCanvas().style.cursor = 'pointer';
        
        if (e.features.length > 0) {
            if (hoveredHotspotId !== null) {
                map.setFeatureState(
                    { source: 'hotspots', sourceLayer: 'hotspots', id: hoveredHotspotId },
                    { hover: false }
                );
            }
            
            hoveredHotspotId = e.features[0].id;
            map.setFeatureState(
                { source: 'hotspots', sourceLayer: 'hotspots', id: hoveredHotspotId },
                { hover: true }
            );
        }
    });
    
    map.on('mouseleave', 'hotspots-fill', () => {
        map.getCanvas().style.cursor = '';
        
        if (hoveredHotspotId !== null) {
            map.setFeatureState(
                { source: 'hotspots', sourceLayer: 'hotspots', id: hoveredHotspotId },
                { hover: false }
            );
        }
        hoveredHotspotId = null;
    });
    
    // Update hotspot fill color based on hover state
    map.setPaintProperty('hotspots-fill', 'fill-color', [
        'case',
        ['boolean', ['feature-state', 'hover'], false],
        window.MAP_CONFIG.colors.hotspotHover,
        window.MAP_CONFIG.colors.hotspotFill
    ]);
    
    // Add click handler for points
    map.on('click', 'points-layer', (e) => {
        if (e.features.length === 0) return;
        
        const feature = e.features[0];
        const coordinates = feature.geometry.coordinates.slice();
        const properties = feature.properties;
        
        // Build popup content
        let popupContent = '<h4>Listed Building Details</h4><table>';
        
        // Fields to skip in popup
        const skipFields = ['easting', 'northing', 'objectid', 'capture_scale', 'national_grid_reference'];
        
        // Generate NHLE link if we have a list entry number
        const listEntryNumber = properties['list_entry_number'];
        if (listEntryNumber && listEntryNumber !== 'null' && listEntryNumber !== '') {
            const nhleUrl = `https://historicengland.org.uk/listing/the-list/list-entry/${listEntryNumber}`;
            popupContent += `<tr><td>NHLE Link:</td><td><a href="${nhleUrl}" target="_blank" rel="noopener noreferrer" style="color: #0066cc;">View on NHLE</a></td></tr>`;
        }
        
        for (const [key, value] of Object.entries(properties)) {
            // Skip unwanted fields
            if (skipFields.includes(key.toLowerCase())) {
                continue;
            }
            
            if (value !== null && value !== undefined && value !== '') {
                // Format key name
                const formattedKey = key
                    .replace(/_/g, ' ')
                    .replace(/\b\w/g, l => l.toUpperCase());
                
                // Format dates nicely
                if (key.toLowerCase().includes('date') && value) {
                    // Parse and format date (assuming format like "11/5/1987 12:00:00 AM")
                    try {
                        const date = new Date(value);
                        if (!isNaN(date.getTime())) {
                            const options = { day: 'numeric', month: 'short', year: 'numeric' };
                            const formattedDate = date.toLocaleDateString('en-GB', options);
                            popupContent += `<tr><td>${formattedKey}:</td><td>${formattedDate}</td></tr>`;
                            continue;
                        }
                    } catch (e) {
                        // If date parsing fails, show original value
                    }
                }
                
                popupContent += `<tr><td>${formattedKey}:</td><td>${value}</td></tr>`;
            }
        }
        
        popupContent += '</table>';
        
        // Create and show popup
        new maplibregl.Popup({
            closeButton: true,
            closeOnClick: true,
            maxWidth: '350px'
        })
            .setLngLat(coordinates)
            .setHTML(popupContent)
            .addTo(map);
    });
    
    // Change cursor on hover over points
    map.on('mouseenter', 'points-layer', () => {
        map.getCanvas().style.cursor = 'pointer';
    });
    
    map.on('mouseleave', 'points-layer', () => {
        map.getCanvas().style.cursor = '';
    });
    
    // Try to get bounds from the data
    fetch(window.MAP_CONFIG.tiles.points)
        .then(response => response.arrayBuffer())
        .then(buffer => {
            const p = new pmtiles.PMTiles(new pmtiles.FetchSource(window.MAP_CONFIG.tiles.points));
            return p.getHeader();
        })
        .then(header => {
            if (header.minLon && header.maxLon && header.minLat && header.maxLat) {
                dataBounds = [[header.minLon, header.minLat], [header.maxLon, header.maxLat]];
            }
        })
        .catch(err => {
            console.log('Could not fetch data bounds:', err);
            // Default to UK bounds
            dataBounds = [[-8, 49], [2, 61]];
        });
});

// Legend collapse functionality
document.getElementById('toggle-legend').addEventListener('click', () => {
    const legendCard = document.getElementById('legend');
    const toggleButton = document.getElementById('toggle-legend');
    
    legendCard.classList.toggle('collapsed');
    toggleButton.textContent = legendCard.classList.contains('collapsed') ? '▶' : '▼';
});

// Add navigation controls
map.addControl(new maplibregl.NavigationControl(), 'top-left');

// Add geolocation control
const geolocateControl = new maplibregl.GeolocateControl({
    positionOptions: {
        enableHighAccuracy: true
    },
    trackUserLocation: true,
    showUserHeading: true,
    showAccuracyCircle: true,
    fitBoundsOptions: {
        maxZoom: 15
    }
});
map.addControl(geolocateControl, 'top-left');

// Optional: Auto-trigger geolocation on load (uncomment if desired)
// map.on('load', () => {
//     geolocateControl.trigger();
// });

// Add event listeners for geolocation events
geolocateControl.on('geolocate', (e) => {
    console.log('User location found:', e.coords);
});

geolocateControl.on('error', (error) => {
    console.error('Geolocation error:', error);
});

// Add scale control
map.addControl(new maplibregl.ScaleControl({
    maxWidth: 100,
    unit: 'metric'
}), 'bottom-left');

// Update URL hash when map moves
function updateHash() {
    const center = map.getCenter();
    const zoom = map.getZoom();
    const hash = `#${zoom.toFixed(2)}/${center.lat.toFixed(4)}/${center.lng.toFixed(4)}`;
    window.history.replaceState(null, null, hash);
}

// Debounce hash updates to avoid too frequent updates
let hashUpdateTimeout;
map.on('moveend', () => {
    clearTimeout(hashUpdateTimeout);
    hashUpdateTimeout = setTimeout(updateHash, 100);
});

// Listen for hash changes (e.g., when user navigates back/forward)
window.addEventListener('hashchange', () => {
    const hash = window.location.hash.replace('#', '');
    if (hash) {
        const parts = hash.split('/');
        if (parts.length === 3) {
            const zoom = parseFloat(parts[0]);
            const lat = parseFloat(parts[1]);
            const lng = parseFloat(parts[2]);
            
            if (!isNaN(zoom) && !isNaN(lat) && !isNaN(lng)) {
                map.jumpTo({
                    center: [lng, lat],
                    zoom: zoom
                });
            }
        }
    }
});