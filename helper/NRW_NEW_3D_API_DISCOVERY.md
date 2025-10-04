# NRW Open Data Portal - NEW 3D Building API Discovery

## Date: October 4, 2025

## BREAKTHROUGH: Real 3D Building Data Available!

### New API Discovered
- **Endpoint**: `https://ogc-api.nrw.de/3dg/v1`
- **Collection**: `building` (Gebäude)
- **Format**: CityGML LOD2 (XML)
- **Coverage**: 11,477,725 buildings across NRW
- **Data**: Level of Detail 2 (LOD2) 3D building models

###✓ REAL HEIGHT DATA IS AVAILABLE!

Example from API response:
```xml
<bldg:Building gml:id="DENW43AL00001j6b">
    <bldg:function>31001_2724</bldg:function>
    <bldg:roofType>2100</bldg:roofType>
    <bldg:measuredHeight uom="urn:adv:uom:m">3.987</bldg:measuredHeight>
    <bldg:lod2Solid>
        <!-- Full 3D geometry with walls, roofs, ground surfaces -->
    </bldg:lod2Solid>
</bldg:Building>
```

### Available Attributes (from queryables)
- **`measuredHeight`** (number) - Building height in meters ⭐
- **`storeysAboveGround`** (integer) - Number of floors ⭐
- **`function`** (string) - Building function/type
- **`roofType`** (string) - Roof shape type
- **`creationDate`** (date) - Data creation date
- **`name`** (string) - Building name (if available)
- **`gml_id`** (string) - Unique ALKIS identifier
- **Full 3D geometry** - LOD2 models with walls, roofs, terrain intersection

### Data Quality
- Based on **LiDAR data** (airborne laser scanning)
- Ground surface from **Digital Terrain Model (DGM1)** at 1m resolution
- Building footprints from **ALKIS** cadastre
- **LOD2 quality**: Includes standardized roof forms (e.g., gable, hip roof)

### API Usage

#### Basic Query
```bash
GET https://ogc-api.nrw.de/3dg/v1/collections/building/items?limit=100
```

#### With Bounding Box (needs testing - bbox parameters unclear)
```bash
GET https://ogc-api.nrw.de/3dg/v1/collections/building/items?bbox=6.76,51.22,6.79,51.25&limit=100
```

#### Response Format
- **Default**: CityGML XML (LOD2 3D models)
- **Alternative**: Need to test if GeoJSON is supported

### Implementation Challenge

The API returns **CityGML XML** format by default, which is:
- ✅ Complete 3D building models with real heights
- ✅ High quality LOD2 data with roofs
- ❌ Complex XML structure (not simple GeoJSON)
- ❌ Requires CityGML parsing

### Next Steps for Implementation

1. **Parse CityGML XML** to extract:
   - Building footprint (ground surface coordinates)
   - `measuredHeight` attribute
   - `function` attribute
   - Transform coordinates to EPSG:25832

2. **Bbox query testing** - Need to determine correct bbox parameter format

3. **Performance considerations**:
   - CityGML files are large (full 3D geometry)
   - May need to extract only footprint + height
   - Consider caching for performance

4. **Alternative approach**:
   - Check if API supports simpler output format
   - Or parse LOD2 and extract just what we need

### Comparison: Old WFS vs New OGC API

| Feature | Old WFS (ALKIS-vereinfacht) | New OGC API (3DG) |
|---------|---------------------------|-------------------|
| Height data | ❌ None | ✅ measuredHeight in meters |
| Floor count | ❌ None | ✅ storeysAboveGround |
| 3D geometry | ❌ 2D footprints only | ✅ Full LOD2 3D models |
| Roof data | ❌ None | ✅ Roof type and geometry |
| Format | GML 3.2 (simple) | CityGML LOD2 (complex) |
| Coverage | All buildings | All buildings |

### Recommendation

**Switch to the new NRW OGC 3D API** to get real building heights!

**Implementation priority:**
1. Test bbox query parameters
2. Implement CityGML parsing to extract footprint + height
3. Update `fetch_existing_buildings_data()` in `backend/data_io.py`
4. Remove fallback to 9m default height

This will give us **REAL measured building heights from LiDAR data** instead of estimates!

### License
- **Datenlizenz Deutschland - Zero - Version 2.0**
- Free to use, attribution required: "Bezirksregierung Köln, Geobasis NRW"

### References
- API Landing Page: https://ogc-api.nrw.de/3dg/v1
- Collections: https://ogc-api.nrw.de/3dg/v1/collections
- Building Collection: https://ogc-api.nrw.de/3dg/v1/collections/building
- Queryables: https://ogc-api.nrw.de/3dg/v1/collections/building/queryables
