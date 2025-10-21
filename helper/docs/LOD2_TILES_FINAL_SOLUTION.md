# NRW Building Height Data - Final Solution

**Date:** February 2025  
**Status:** ✅ SOLVED - LOD2 Tiles Recommended

## Problem Statement

The OpenSKIZZE application requires complete building height data for cold airflow simulation in NRW (North Rhine-Westphalia, Germany). Initial investigation found multiple data sources with different trade-offs.

## Data Sources Evaluated

### 1. WFS ALKIS ❌ Rejected
- **URL:** `https://www.wfs.nrw.de/geobasis/wfs_nw_alkis_vereinfacht`
- **Performance:** ⚡ Very Fast (0.2s)
- **Coverage:** ✅ 100% complete (2655 buildings in test area)
- **Height Data:** ❌ None
- **Verdict:** Cannot be used - missing critical height information

### 2. OGC 3D API ❌ Rejected
- **URL:** `https://ogc-api.nrw.de/3dg/v1/collections/building/items`
- **Performance:** 🐌 Very Slow (30+ seconds)
- **Coverage:** ⚠️ Incomplete (2291 buildings, 86% coverage)
- **Height Data:** ✅ Yes (measuredHeight attribute)
- **Verdict:** Too slow and incomplete - missing 364 buildings (14%)

### 3. LOD2 Tiles ✅ RECOMMENDED
- **URL:** `https://www.opengeodata.nrw.de/produkte/geobasis/3dg/lod2_gml/`
- **Performance:** ⚡ Fast (cached tiles, ~2s after initial download)
- **Coverage:** ✅ 91.5% complete (2428 buildings)
- **Height Data:** ✅ Yes (measuredHeight for all buildings)
- **Format:** CityGML 1.0 LOD2
- **Verdict:** **BEST SOLUTION** - fast, nearly complete, includes heights

## LOD2 Tile System

### Tile Grid Structure
- **Tile Size:** 1km × 1km
- **Naming Convention:** `LoD2_32_<X>_<Y>_1_NW.gml`
  - `32` = UTM Zone 32 (EPSG:25832)
  - `<X>` = Easting / 1000 (tile column)
  - `<Y>` = Northing / 1000 (tile row)
  - `1` = Dataset version
  - `NW` = Nordrhein-Westfalen

### Example: Bonn City Center
- **Coordinates (EPSG:25832):** 365204-365938 E, 5621522-5622652 N
- **Required Tiles:**
  - `LoD2_32_365_5621_1_NW.gml` (51.4 MB)
  - `LoD2_32_365_5622_1_NW.gml` (76.6 MB)
- **Total Buildings:** 2428 with heights
- **Coverage:** 91.5% of WFS ALKIS footprints

## Implementation

### Download Script
File: `tests/download_lod2_tiles.py`

```python
from download_lod2_tiles import fetch_lod2_tiles_for_bbox

# Fetch buildings for a bbox
buildings = fetch_lod2_tiles_for_bbox(min_x, min_y, max_x, max_y)
# Returns: GeoDataFrame with geometry, measuredHeight, building_id
```

### Key Features
- ✅ Automatic tile discovery from bbox
- ✅ Tile caching (no re-download)
- ✅ CityGML 1.0 parsing (lod2TerrainIntersection footprints)
- ✅ Bbox filtering (only returns buildings in area)
- ✅ Duplicate removal (buildings on tile boundaries)

## Performance Comparison

| Source | Response Time | Coverage | Buildings | Height Data |
|--------|--------------|----------|-----------|-------------|
| WFS ALKIS | 0.2s | 100% | 2655 | ❌ No |
| OGC 3D API | 30s | 86% | 2291 | ✅ Yes |
| **LOD2 Tiles** | **2s*** | **91.5%** | **2428** | **✅ Yes** |

\* After initial download; tiles are cached locally

## Height Statistics (LOD2 Tiles)

- **Min Height:** 1.0 m
- **Mean Height:** 12.3 m
- **Max Height:** 81.4 m
- **Std Deviation:** 7.1 m

## Data Quality Notes

### Underground Buildings Filtered
WFS ALKIS includes 37 underground structures that were filtered out:
- `rellage = "Unter der Erdoberfläche"` (underground)
- `funktion = "Tiefgarage"` (underground parking)

These don't affect cold airflow and were excluded from the comparison.

### Missing Buildings
LOD2 Tiles have 227 fewer buildings (8.5% gap) compared to WFS ALKIS. Possible reasons:
- New construction not yet in LiDAR data
- Small buildings below minimum size threshold
- Buildings under construction/demolition
- Data processing differences

## Recommendation

**Use LOD2 Tiles as the primary data source for OpenSKIZZE:**

1. **Fast Performance:** Cached tiles load in ~2 seconds
2. **Nearly Complete:** 91.5% coverage is sufficient for cold airflow modeling
3. **Full Height Data:** Every building has measuredHeight
4. **Better than OGC:** 137 more buildings, 15x faster
5. **Production Ready:** Stable, reliable, cacheable

### Implementation Steps

1. ✅ Download relevant tiles based on simulation bbox
2. ✅ Parse CityGML LOD2 format
3. ✅ Extract building footprints from `lod2TerrainIntersection`
4. ✅ Use `measuredHeight` for all buildings
5. ✅ Cache tiles locally to avoid re-downloading

## Files

- `tests/download_lod2_tiles.py` - Tile download and parsing
- `tests/compare_all_sources.py` - Data source comparison
- `tests/all_sources_comparison.png` - Visual comparison
- `tests/lod2_tiles_cache/` - Cached tile directory

## References

- **OpenGeoData.NRW Portal:** https://www.opengeodata.nrw.de/
- **LOD2 Data:** https://www.opengeodata.nrw.de/produkte/geobasis/3dg/lod2_gml/
- **Download Client:** https://www.geoportal.nrw/?activetab=map&openDownloadclient=true
- **CityGML Specification:** OGC CityGML 1.0 (building/1.0)

---

**Conclusion:** LOD2 Tiles are the optimal solution for OpenSKIZZE building height data. The system is fast, reliable, and provides nearly complete coverage with full height information for cold airflow simulation.
