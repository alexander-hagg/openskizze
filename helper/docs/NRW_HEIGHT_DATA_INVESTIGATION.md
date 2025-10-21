# NRW Open Data Portal - Building Height Data Investigation

## Date: October 4, 2025

## Question
Can we obtain actual building height data from the NRW Open Data Portal?

## Investigation Summary

### Data Source
- **Service**: NRW WFS (Web Feature Service)
- **Endpoint**: `https://www.wfs.nrw.de/geobasis/wfs_nw_alkis_vereinfacht`
- **Feature Type**: `ave:GebaeudeBauwerk` (Building Structures)
- **Dataset**: ALKIS-vereinfacht (Simplified Cadastral Information System)

### Available Attributes
The NRW ALKIS-vereinfacht building dataset provides the following attributes:
- `gml_id`: Unique identifier
- `identifier`: URN identifier  
- `oid`: Object ID
- `aktualit`: Last update date
- `gebnutzbez`: Building designation (Gebäude/Bauteil)
- `funktion`: Building function/type (Wohngebäude, Gewerbe, etc.)
- `gfkzshh`: Function key
- `gmdschl`: Municipality code
- `lagebeztxt`: Address text
- `name`: Building name (rarely populated)
- `rellage`: Relative position
- `geometry`: Building footprint polygon

### Height-Related Attributes: NOT AVAILABLE

#### Schema Definition vs. Actual Data
- **In Schema**: The field `anzahlgs` (Anzahl Geschosse = Number of Floors) is defined as `integer` type
- **In Actual Data**: This field is **NEVER populated** in the returned features

#### Testing Coverage
We tested building data from 5 major cities across NRW:
- Düsseldorf: 13,799 buildings - 0 with floor data (0.00%)
- Köln: 10,997 buildings - 0 with floor data (0.00%)
- Dortmund: 9,330 buildings - 0 with floor data (0.00%)
- Essen: 9,163 buildings - 0 with floor data (0.00%)
- Bonn: 11,645 buildings - 0 with floor data (0.00%)

**Total: 54,934 buildings tested - ZERO contain height or floor data**

### Alternative WFS Endpoints Checked
We also checked for 3D building model services:
- `wfs_nw_3d-gebaeudemodell_lod1` - **404 Not Found**
- `wfs_nw_3d-gebaeudemodell_lod2` - **404 Not Found**  
- `wfs_nw_inspire-bu-3d` - **404 Not Found**

These services either do not exist or are not publicly accessible.

## Conclusion

**❌ The NRW Open Data Portal does NOT provide building height information through the ALKIS-vereinfacht WFS service.**

The `anzahlgs` (number of floors) field exists in the schema definition but is not populated with actual data. All 54,934+ buildings tested across 5 major cities had no height information.

## Recommended Solution

Since real height data is unavailable, we should implement **function-based height estimation** using the `funktion` (building type) attribute:

### Proposed Height Estimates

| Building Function | German Name | Estimated Floors | Estimated Height (m) |
|-------------------|-------------|------------------|---------------------|
| Residential | Wohngebäude | 3 | 9.0 |
| Mixed Use Residential | Gemischt genutztes Gebäude mit Wohnen | 4 | 12.0 |
| High-rise Part | Hochhausgebäudeteil | 12 | 36.0 |
| Commercial/Industrial | Gebäude für Wirtschaft oder Gewerbe | 2 | 6.0 |
| Parking Structure | Parkhaus, Gebäude zum Parken | 4 | 12.0 |
| Educational | Allgemein bildende Schule | 3 | 9.0 |
| University | Hochschulgebäude | 4 | 12.0 |
| Administrative | Verwaltungsgebäude, Rathaus | 4 | 12.0 |
| Religious | Kirche, Kapelle, Gebäude für religiöse Zwecke | 6 | 18.0 |
| Cultural | Museum, Theater, Konzertgebäude | 3 | 9.0 |
| Healthcare | Gebäude für Gesundheitswesen | 4 | 12.0 |
| Canopy/Overhang | Überdachung, Auskragender Geschossteil | 1 | 3.0 |
| Passage | Durchfahrt | 1 | 3.0 |
| Other/Unknown | Sonstiges | 3 | 9.0 |

### Implementation Notes
- This provides more realistic variation than a flat 9m default
- Based on typical German building standards (3m per floor)
- Conservative estimates to avoid over-exaggeration
- Can be refined based on local building regulations or user preferences

## Alternative Data Sources (Future Work)

If actual height data is needed, consider:
1. **CityGML LOD2 data** - Some German cities provide 3D building models
2. **OpenStreetMap** - May have `building:levels` tags for some buildings
3. **Custom surveying** - Manual measurement or LiDAR data
4. **Commercial datasets** - Private providers may have more detailed 3D data

## Files Generated During Investigation
- `test_nrw_heights.py` - Initial height data check
- `investigate_nrw_3d_data.py` - WFS capabilities exploration
- `inspect_nrw_building_details.py` - Detailed attribute inspection
- `search_anzahlgs_data.py` - Comprehensive floor data search
- `nrw_buildings_sample.xml` - Raw GML response sample
- `nrw_buildings_schema.xml` - Feature type schema definition
