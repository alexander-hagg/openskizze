# NRW API Height Data Search Prompt

## Goal
Find the most performant and efficient API/WFS endpoint from the NRW (Germany) open data portal to consistently retrieve **building height** data.

## Background
We are currently using the older **WFS** endpoint `https://www.wfs.nrw.de/geobasis/wfs_nw_alkis_vereinfacht` which provides adequate speed. We have tested the newer **OGC API Features** endpoint `https://ogc-api.nrw.de/3dg/v1` but found it to be too slow, with initial response times often exceeding 22 seconds.

## Current Status
- **Current WFS Endpoint:** `https://www.wfs.nrw.de/geobasis/wfs_nw_alkis_vereinfacht`
  - Feature Type: `ave:GebaeudeBauwerk`
  - Status: ✓ Fast, but **no height data** available
  - Available attributes: `funktion` (building function/type), geometry
  
- **3D OGC API Endpoint:** `https://ogc-api.nrw.de/3dg/v1`
  - Feature Type: CityGML LOD2 building models
  - Status: ✗ Has `measuredHeight` data, but **too slow** (22+ seconds)
  - Issue: No proper BBOX spatial filtering support

## Task

### 1. Identify Height Data Sources
Find the exact feature type, property name, and schema that contains **building height** information:
- Primary target: `measuredHeight`, `hoehe`, `geschosszahl` (number of floors)
- Likely sources:
  - ALKIS (Automatisierte Liegenschaftskarte) simplified schema
  - 3D building models (3DG) - LOD1, LOD2, or LOD3
  - Building register (Gebäuderegister)

### 2. Explore API Capabilities
For **both** WFS and OGC API endpoints:
- Confirm direct query methods for height attributes
- Test BBOX filtering performance
- Verify property/attribute filtering capabilities
- Document response formats (GML, GeoJSON, CityGML)

### 3. Search for Performance Solutions
Look for:
- Alternative endpoints or service views
- OGC API Tiles (pre-rendered, faster access)
- WFS with height data (if available)
- Batch query optimizations
- Performance comparison documentation
- Known workarounds for slow OGC API responses

### 4. Specify Recommended Query
Provide:
- Fastest endpoint URL and parameters
- Expected response format
- Query structure for ~1 km² bounding box
- Typical response time benchmarks

## Key Questions to Answer

1. **Does the WFS ALKIS endpoint have ANY height data?**
   - Check `GetCapabilities` for all available properties
   - Look for `hoehe`, `geschosszahl`, `dachhoehe`, etc.

2. **Can the OGC API be optimized?**
   - Does it support CQL filtering to reduce payload?
   - Can we use property selection (`select` parameter)?
   - Are there cached/tiled versions available?

3. **Are there alternative NRW endpoints?**
   - WFS for 3D buildings with height data?
   - Direct download of building datasets?
   - Tile services (WMTS/OGC Tiles) with height attributes?

4. **What about other German federal states?**
   - Do other states have better-performing APIs we can learn from?
   - Are there standardized approaches we should adopt?

## Success Criteria

The ideal solution should:
- ✓ Provide reliable building height data (measured or floor-based)
- ✓ Respond in < 5 seconds for typical queries
- ✓ Support BBOX spatial filtering
- ✓ Return data in a parsable format (GeoJSON preferred)
- ✓ Be stable and officially maintained

## Related Documentation

- **NRW Geobasis Portal:** https://www.geobasis.nrw.de/
- **OGC API Docs:** https://ogc-api.nrw.de/
- **WFS Capabilities:** https://www.wfs.nrw.de/geobasis/wfs_nw_alkis_vereinfacht?service=WFS&request=GetCapabilities
- **ALKIS Specification:** Search for "ALKIS Objektartenkatalog"

## Test Area

For all performance tests, use this consistent bounding box:
- **Location:** Bonn, Germany (city center)
- **BBOX (EPSG:4326):** `7.09, 50.73, 7.10, 50.74` (~1 km²)
- **BBOX (EPSG:25832):** `356000, 5622000, 357000, 5623000`

This area should contain 100-300 buildings for representative testing.
