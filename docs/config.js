window.MAP_CONFIG = {
    // Using Carto Light basemap (raster tiles)
    basemapUrl: 'https://a.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png',
    basemapAttribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors © <a href="https://carto.com/attributions">CARTO</a>',
    
    // Initial map center (roughly centered on England)
    center: [-1.6, 53.5],
    zoom: 6,
    
    // Tile paths (PMTiles for static hosting)
    tiles: {
        points: './tiles/listed_buildings.pmtiles',
        hotspots: './tiles/hotspots.pmtiles'
    },
    
    // Style configuration
    colors: {
        hotspotFill: 'rgba(255, 200, 100, 0.3)',
        hotspotOutline: 'rgba(255, 150, 50, 0.8)',
        hotspotHover: 'rgba(255, 200, 100, 0.5)',
        gradeIColor: 'rgba(200, 50, 50, 0.8)',  // Red for Grade I
        gradeIIColor: 'rgba(50, 100, 200, 0.7)', // Blue for Grade II
        pointOutline: 'rgba(255, 255, 255, 0.8)'
    }
};