# LOD2 Tile System - Quick Reference

## 🎯 What It Does
Fetches real building heights from NRW's LOD2 tile system - LiDAR-measured 3D building data.

## ⚡ Performance
- **Initial download**: 60s for large area (one-time)
- **Cached access**: 2s (instant after first fetch)
- **30× faster** than OGC 3D API
- **91.5% coverage** of all NRW buildings

## 📊 Data Quality
- **Height range**: 0.3m - 181m (typical: 3-20m)
- **Source**: LiDAR measurements (real data, not estimates)
- **Coverage**: 100% of LOD2 buildings have height data
- **Format**: CityGML 1.0, EPSG:25832

## 🔧 How It Works

### Tile System
```
1km × 1km grid tiles
Naming: LoD2_32_<X>_<Y>_1_NW.gml
Example: LoD2_32_477_5727_1_NW.gml
  → X=477km, Y=5727km in EPSG:25832
```

### Data Flow
```
bbox (WGS84) → EPSG:25832 → tile grid → download/cache
→ parse CityGML → GeoDataFrame with measuredHeight
→ convert to floors (÷3) → 3D voxel grid
```

## 📁 Key Files

### Production Code
- **`backend/data_io.py`**: Main integration
  - `fetch_existing_buildings_data()` - Entry point
  - `fetch_lod2_buildings()` - Tile fetching
  - `bbox_to_tiles()` - Grid calculation
  - `download_lod2_tile()` - Download/cache
  - `parse_citygml_lod2_tile()` - Parse CityGML

### Cache
- **`cache/lod2_tiles/`**: Downloaded tiles (auto-created)

### Tests
- **`tests/test_lod2_integration.py`**: Basic fetching test
- **`tests/test_full_pipeline.py`**: Full processing test
- **`tests/download_lod2_tiles.py`**: Standalone downloader
- **`tests/compare_all_sources.py`**: WFS vs LOD2 comparison

### Documentation
- **`helper/LOD2_INTEGRATION_SUMMARY.md`**: Integration details
- **`helper/COMPLETE_LOD2_JOURNEY.md`**: Full journey
- **`helper/LOD2_TILES_FINAL_SOLUTION.md`**: Discovery docs

## 🧪 Quick Tests

```bash
# Test basic LOD2 fetching (227 buildings)
python3 tests/test_lod2_integration.py

# Test full pipeline (25k+ buildings)
python3 tests/test_full_pipeline.py

# Check cache size
du -sh cache/lod2_tiles/

# List cached tiles
ls -lh cache/lod2_tiles/
```

## 🔍 Debugging

### Check if LOD2 is being used
```python
# Look for this in console output:
[fetch_buildings] Using measuredHeight from LOD2 tiles (range: X-Y floors)
```

### Verify height data
```python
from backend.data_io import fetch_existing_buildings_data
buildings = fetch_existing_buildings_data((8.67, 51.70, 8.69, 51.72))
print(buildings['measuredHeight'].describe())
```

### Check cache
```bash
# Number of cached tiles
ls cache/lod2_tiles/ | wc -l

# Total cache size
du -sh cache/lod2_tiles/

# Most recent tiles
ls -lt cache/lod2_tiles/ | head
```

## 🚨 Common Issues

### "No buildings found"
- Check bbox is in WGS84 (EPSG:4326)
- Verify area is in NRW region
- Check internet connection (for first download)

### "Download failed"
- Tile might not exist (outside NRW)
- Network issue - retry
- Check URL in LOD2_BASE_URL

### "Slow performance"
- First download is slow (normal)
- Subsequent queries should be 2s
- Check if cache directory exists

## 📈 Data Sources Compared

| Source | Speed | Coverage | Heights | Status |
|--------|-------|----------|---------|--------|
| WFS ALKIS | 0.2s | 100% | ❌ | Replaced |
| OGC 3D API | 30s | 86% | ✓ | Removed |
| **LOD2 Tiles** | **2s** | **91.5%** | **✓** | **✓ Active** |

## 🎓 LOD2 Details

### Tile URL Pattern
```
https://www.opengeodata.nrw.de/produkte/geobasis/3dg/lod2_gml/lod2_gml/
LoD2_32_<X>_<Y>_1_NW.gml
```

### Tile Size
- Small tiles: ~100 KB (rural areas)
- Large tiles: ~50 MB (dense urban areas)
- Average: ~5-10 MB

### Building Attributes
- **measuredHeight**: Height in meters (LiDAR)
- **lod2TerrainIntersection**: Building footprint
- **function**: Building type (optional)
- **roofType**: Roof shape (optional)

### Coordinate Systems
- **Tiles**: EPSG:25832 (UTM Zone 32N)
- **Input bbox**: EPSG:4326 (WGS84)
- **Output**: EPSG:25832 (for processing)

## 💡 Best Practices

### Efficient Queries
```python
# ✓ Good: Query once, cache in session
buildings = fetch_existing_buildings_data(bbox)
# Store in session_state for reuse

# ✗ Bad: Query repeatedly
for i in range(10):
    buildings = fetch_existing_buildings_data(bbox)
```

### Cache Management
```bash
# Clean old tiles (optional)
find cache/lod2_tiles/ -mtime +30 -delete

# Backup cache before clearing
tar -czf lod2_cache_backup.tar.gz cache/lod2_tiles/
```

### Error Handling
```python
buildings = fetch_existing_buildings_data(bbox)
if buildings is None or buildings.empty:
    print("⚠ No buildings found, check area or connection")
    # Fall back to default behavior
```

## 🔗 Useful Links

- **NRW Open Data**: https://open.nrw/
- **LOD2 Product Page**: https://www.opengeodata.nrw.de/produkte/geobasis/3dg/lod2_gml/
- **CityGML Spec**: https://www.citygml.org/
- **EPSG:25832**: https://epsg.io/25832

## 📝 Notes

- Tiles are downloaded on-demand (lazy loading)
- Cache persists between application runs
- Heights are in meters, converted to floors (÷3)
- Buildings at tile boundaries may appear in multiple tiles (duplicates are removed)
- Coverage is 91.5% compared to WFS ALKIS (missing 8.5% are mostly small structures)

---

**Quick Start**: Just use `fetch_existing_buildings_data(bbox)` - it handles everything!
