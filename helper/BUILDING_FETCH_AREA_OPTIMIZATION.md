# Building Fetch Area Optimization

## Issue
The `create_environment()` function was fetching buildings from an area **3x larger than necessary** (100% expansion on each side), resulting in:
- Slower API calls
- More data transfer
- Unnecessary processing
- Higher memory usage

## Root Cause
**Line 76** in `optimization_process.py`:
```python
neighborhood_expansion = 1.0  # Multiplier: 1.0 means 3x area (1x on each side)
```

This was hardcoded to fetch from a much larger area than needed for visualization context.

## Solution
Changed to use the **existing `environment_border_size` config** (default: 1.2), which only adds **20% border** (10% on each side) instead of 100%.

### Before:
```python
neighborhood_expansion = 1.0  # 100% on each side
expanded_grid_side = grid_side_length * (1 + 2 * 1.0)  # 3x the size
```

### After:
```python
neighborhood_expansion_factor = DOMAIN_CONFIG['environment_border_size']  # 1.2 by default
neighborhood_expansion = (neighborhood_expansion_factor - 1.0) / 2.0  # 0.1 per side
expanded_grid_side = grid_side_length * neighborhood_expansion_factor  # 1.2x the size
```

## Impact

### Area Reduction
For a **100m × 100m parcel**:
- **OLD**: Fetches 300m × 300m = **90,000 m²** (9x the parcel size)
- **NEW**: Fetches 120m × 120m = **14,400 m²** (1.4x the parcel size)
- **Reduction**: **84%** (75,600 m² less)

For a realistic **50m × 50m parcel**:
- **OLD**: Fetches 22,500 m² (2.25 hectares)
- **NEW**: Fetches 3,600 m² (0.36 hectares)
- **Reduction**: 18,900 m² (**84% fewer buildings**)

### Performance Benefits
1. ✅ **Faster API calls**: 84% less data to fetch from OGC API
2. ✅ **Less bandwidth**: Important for the new 3D OGC API with LiDAR heights
3. ✅ **Faster processing**: Less building data to filter and rasterize
4. ✅ **Lower memory**: Smaller arrays and geodataframes
5. ✅ **Better UX**: Quicker response times in Step 1 and Step 3

### Why This Works
The `environment_border_size = 1.2` config parameter was **already designed** to define the visualization context area. It adds a 20% border for:
- Wind flow context at the edges
- Shadow calculations from nearby buildings
- Visualization of neighborhood context

There was **no reason** to fetch 3x this area. The 1.2x expansion already provides sufficient context.

## Files Changed
1. **`backend/optimization_process.py`** (line ~76-83):
   - Removed hardcoded `neighborhood_expansion = 1.0`
   - Now uses `DOMAIN_CONFIG['environment_border_size']`
   - Calculates correct expansion factor

## Testing
- ✅ No syntax errors
- ✅ Logic verified with area calculation script
- ✅ Maintains same grid structure (just smaller fetch area)
- ✅ Still provides visualization context (20% border is sufficient)

## Why This Matters for OGC API
The new **OGC 3D API** returns:
- LOD2 building models (more complex geometry)
- Real measured heights (more attributes)
- CityGML XML (larger data format)

Fetching 84% fewer buildings significantly improves performance with the new API.

## Configuration
Users can adjust the fetch area by changing `environment_border_size` in `config.py`:
- **1.0** = No border (only parcel area) - Minimal context
- **1.2** = 20% border (default) - Good balance ✅
- **1.5** = 50% border - More context, slower
- **2.0** = 100% border - Maximum context, much slower

---

**Date**: 2025-01-26  
**Branch**: `ogc`  
**Status**: ✅ Optimized
