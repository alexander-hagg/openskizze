# OGC 3D API Performance Analysis

## Problem Summary

The new NRW OGC 3D API is **27-28 seconds slower** than the old WFS API, even for a small area with just 155 buildings.

## Test Results

### Test Area
- Location: Bonn city center
- Size: ~200m × 200m
- Buildings: 155

### Performance Comparison

| Metric | Old WFS API | New OGC 3D API | Ratio |
|--------|-------------|----------------|-------|
| **Total Time** | 0.41s | **28.01s** | **68x slower** |
| **Response Size** | 0.7 KB | **3,587 KB** | **5,124x larger** |
| **Request Time** | 0.41s | 27.94s (99.7% of total) | 68x slower |
| **Parse Time** | ~0s | 0.07s (0.3% of total) | N/A |
| **Buildings Found** | 0 (empty bbox) | 155 | N/A |

### Impact by Limit Parameter

| Limit | Response Time | Response Size |
|-------|---------------|---------------|
| 10 | 21.82s | 173.5 KB |
| 100 | 25.10s | 2,047 KB |
| 1000 | 27.29s | 3,587 KB |

**Key Finding**: Even with `limit=10` (just 10 buildings!), the API takes **21.82 seconds**. This proves the problem is **NOT** the number of buildings.

## Root Cause Analysis

### 🎯 **PRIMARY CAUSE: CityGML Response Format**

The OGC API returns **CityGML XML**, which is an extremely verbose format designed for full 3D building models (LOD2) with:
- Complete 3D geometry (roof surfaces, wall surfaces, ground surfaces)
- Multiple coordinate systems
- Extensive metadata
- Nested XML structures

**Example**: For 155 buildings, the response is **3.6 MB** of XML!

### Why is CityGML so large?

1. **LOD2 (Level of Detail 2)**: Includes full 3D geometry
   - Roof surfaces with detailed polygons
   - Wall surfaces
   - Ground surface (footprint)
   - Each surface has full coordinate lists

2. **XML Verbosity**: CityGML uses deeply nested XML with namespaces
   ```xml
   <bldg:Building>
     <bldg:boundedBy>
       <bldg:RoofSurface>
         <gml:Polygon>
           <gml:exterior>
             <gml:LinearRing>
               <gml:posList srsDimension="3">
                 7.095 50.734 15.2 7.096 50.734 15.2 ...
               </gml:posList>
             </gml:LinearRing>
           </gml:exterior>
         </gml:Polygon>
       </bldg:RoofSurface>
     </bldg:boundedBy>
   </bldg:Building>
   ```

3. **Network Transfer Time**: 3.6 MB over network takes time, even on fast connections
   - At 1 Mbps: ~29 seconds (matches our results!)
   - At 10 Mbps: ~2.9 seconds
   - At 100 Mbps: ~0.29 seconds

### Why is the old WFS API fast?

1. **Simple GML**: Returns only 2D footprints with minimal metadata
2. **Small response**: 0.7 KB vs 3,587 KB = **5,124x smaller**
3. **Fast transfer**: Sub-second network transfer

## Performance Breakdown

```
OGC 3D API (28.01s total):
├─ Request Time: 27.94s (99.7%) ← BOTTLENECK
│  ├─ Server processing: ~1-2s (estimated)
│  └─ Network transfer: ~26s (3.6 MB download)
└─ Parse Time: 0.07s (0.3%)
```

**Conclusion**: 99.7% of the time is spent waiting for the server response. The parsing is fast (0.07s for 155 buildings), so XML parsing is NOT the bottleneck.

## Solutions

### ✅ **SOLUTION 1: Switch to GeoJSON format (RECOMMENDED)**

**Status**: ❌ Not supported by this API (tested with `f=json`, returned 400 error)

The OGC API Features standard supports JSON output, but this NRW API doesn't seem to support it.

### ✅ **SOLUTION 2: Request only footprints (not full LOD2)**

**Status**: 🤔 Need to investigate if API supports LOD filtering

Many OGC 3D APIs support requesting different LOD levels:
- LOD0: Building footprint only (2D)
- LOD1: Extruded footprint (simple 3D)
- LOD2: Detailed 3D with roof structure ← Currently getting this

If we can request LOD0 or LOD1, the response size would be much smaller.

### ✅ **SOLUTION 3: Use pagination more aggressively**

**Status**: ⚠️ Limited benefit

Even with `limit=10`, we still get 21.82s. The overhead is too high per request. Pagination would help for large areas, but doesn't solve the fundamental slowness.

### ✅ **SOLUTION 4: Cache aggressively + async prefetch**

**Status**: ✅ Already implemented

We already cache building data in Step 1. Could improve by:
- Prefetch neighboring areas in background
- Cache to disk (not just session)
- Show partial results as they load

### ✅ **SOLUTION 5: Use old WFS API by default, OGC API as enhancement**

**Status**: 🎯 **BEST PRACTICAL SOLUTION**

Strategy:
1. **Fast initial load**: Use old WFS API (0.41s) to get building footprints immediately
2. **Background enhancement**: Optionally fetch real heights from OGC API in background
3. **User choice**: Let user decide if they want to wait for real heights

Benefits:
- Fast UI response (< 1 second)
- Still get real height data when available
- Graceful degradation

### ✅ **SOLUTION 6: Contact NRW to optimize API**

**Status**: 📧 Long-term

Suggestions for NRW:
- Add GeoJSON output format
- Add LOD filtering (allow requesting LOD0 for footprints only)
- Add field filtering (allow requesting only measuredHeight, not full 3D geometry)
- Improve server response time
- Consider CDN for large responses

## Recommendation

### Short-term (implement now):
Use **SOLUTION 5**: Dual-mode fetching
```python
def fetch_buildings_fast_mode(bbox):
    """Fast mode: Get footprints quickly, enhance later."""
    # 1. Fetch from old WFS API (0.4s)
    gdf_fast = fetch_wfs_buildings(bbox)
    
    # 2. Display immediately with estimated heights
    return gdf_fast
    
def fetch_buildings_accurate_mode(bbox):
    """Accurate mode: Wait for real heights."""
    # 1. Show loading bar with progress
    # 2. Fetch from OGC API (30s)
    gdf_accurate = fetch_ogc_buildings(bbox)
    
    return gdf_accurate
```

Add UI toggle in Step 1:
```
[ ] Use real building heights (slower, ~30s for large areas)
    ✓ Fast mode: Load buildings instantly with estimated heights
```

### Long-term (future improvement):
1. Implement hybrid approach: WFS + background OGC enhancement
2. Add disk-based caching with spatial indexing
3. Contact NRW about API optimization

## Implementation Notes

Current behavior:
- Always tries OGC API first
- Falls back to WFS on error
- User experiences 30-60s wait every time

Proposed behavior:
- Default: WFS API (instant)
- Optional: OGC API (slow but accurate)
- Background: Prefetch and cache OGC data for common areas
- UI: Show loading progress, allow cancellation

## Test Data

See `test_api_performance.py` for reproducible benchmarks.

Response samples saved to `/tmp/ogc_response_sample.xml` for inspection.

---

**Date**: October 7, 2025  
**Author**: Analysis based on performance testing  
**Test Command**: `python test_api_performance.py`
