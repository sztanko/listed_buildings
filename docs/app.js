// Initialize PMTiles protocol
let protocol = new pmtiles.Protocol();
maplibregl.addProtocol('pmtiles', protocol.tile);

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
    center: window.MAP_CONFIG.center,
    zoom: window.MAP_CONFIG.zoom,
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
        minzoom: 10,  // Only show points at zoom level > 10
        paint: {
            'circle-radius': [
                'interpolate',
                ['linear'],
                ['zoom'],
                10, 1.5,
                12, 2.5,
                14, 4
            ],
            'circle-color': [
                'case',
                ['==', ['get', 'grade'], 'I'],
                window.MAP_CONFIG.colors.gradeIColor,
                ['==', ['get', 'grade'], 'II*'],
                window.MAP_CONFIG.colors.gradeIColor,  // Grade II* uses same color as Grade I
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
        
        for (const [key, value] of Object.entries(properties)) {
            // Skip easting and northing fields
            if (key.toLowerCase() === 'easting' || key.toLowerCase() === 'northing') {
                continue;
            }
            
            if (value !== null && value !== undefined && value !== '') {
                // Format key name
                const formattedKey = key
                    .replace(/_/g, ' ')
                    .replace(/\b\w/g, l => l.toUpperCase());
                
                // Make NHLE Link clickable
                if (key.toLowerCase() === 'nhle_link' && value.startsWith('http')) {
                    popupContent += `<tr><td>${formattedKey}:</td><td><a href="${value}" target="_blank" rel="noopener noreferrer" style="color: #0066cc;">View on NHLE</a></td></tr>`;
                } else {
                    popupContent += `<tr><td>${formattedKey}:</td><td>${value}</td></tr>`;
                }
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

// Layer toggle controls
document.getElementById('toggle-hotspots').addEventListener('change', (e) => {
    const visibility = e.target.checked ? 'visible' : 'none';
    map.setLayoutProperty('hotspots-fill', 'visibility', visibility);
    map.setLayoutProperty('hotspots-outline', 'visibility', visibility);
});

document.getElementById('toggle-points').addEventListener('change', (e) => {
    const visibility = e.target.checked ? 'visible' : 'none';
    map.setLayoutProperty('points-layer', 'visibility', visibility);
});

// Fit to data button
document.getElementById('fit-bounds').addEventListener('click', () => {
    if (dataBounds) {
        map.fitBounds(dataBounds, {
            padding: 50,
            duration: 1000
        });
    } else {
        // Default to UK bounds
        map.fitBounds([[-8, 49], [2, 61]], {
            padding: 50,
            duration: 1000
        });
    }
});

// Add navigation controls
map.addControl(new maplibregl.NavigationControl(), 'top-left');

// Add scale control
map.addControl(new maplibregl.ScaleControl({
    maxWidth: 100,
    unit: 'metric'
}), 'bottom-left');