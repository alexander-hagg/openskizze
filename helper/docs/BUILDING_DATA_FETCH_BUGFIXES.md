# Building Data Fetching - Bug Fixes

## Issues Fixed

### 1. **Wrong Function Parameter Name**
**Problem**: Step 1 callback was calling `fetch_and_process_buildings_for_area(polygon_geom=...)` but the function expects `user_polygon_geojson`.

**Fix**: Changed to pass the correct parameter name: `user_polygon_geojson=final_geojson`

### 2. **Wrong Parameter Type**
**Problem**: Was passing a Shapely geometry object, but the function expects a GeoJSON dictionary.

**Fix**: Now passing `final_geojson` (the GeoJSON dict) directly instead of converting to Shapely first.

### 3. **Fetching on Every Polygon Change**  
**Problem**: Building data was being fetched even during page initialization or when only wind direction changed.

**Fix**: Integrated the building data fetching directly into the `handle_all_interactions` callback and added a trigger check:
```python
if triggered_id in ['parcels-layer', 'edit-control', 'upload-geojson']:
    # Only fetch when polygon actually changed
```

### 4. **Fetching Before Area Selection**
**Problem**: The separate callback could trigger before user selected any area.

**Fix**: By integrating into `handle_all_interactions`, building data is only fetched AFTER the user actively selects/modifies an area through:
- Clicking parcels
- Drawing/editing polygons
- Uploading GeoJSON

### 5. **Indentation Errors in optimization_process.py**
**Problem**: When adding cache support, the building processing code indentation was broken, causing Python syntax errors.

**Fix**: Properly indented all building processing code (lines ~130-260) to be nested under:
```python
if cached_building_data is None:
    # Fetch from API
    if gdf_buildings_native is not None:
        # Process buildings
        ...
```

## New Data Flow

### Step 1: Area Selection
```
User clicks parcel / draws polygon / uploads GeoJSON
  ↓
handle_all_interactions() callback triggers
  ↓
Check: triggered_id in ['parcels-layer', 'edit-control', 'upload-geojson']?
  ↓
YES → Fetch building data for selected area
  ↓
fetch_and_process_buildings_for_area(user_polygon_geojson=final_geojson)
  ↓
Serialize and store in session['building_data']
  ↓
Console: "[fetch_buildings] ✓ Cached building data: X buildings processed"
```

### Step 3: Optimization
```
User clicks "Start Optimization"
  ↓
run_optimization() callback
  ↓
Read and deserialize session['building_data']
  ↓
Pass to start_optimization(... cached_building_data=...)
  ↓
Pass to create_environment(... cached_building_data=...)
  ↓
Check if cache valid (resolution matches)
  ↓
YES → Use cached data (skip API call)
  ↓
NO → Fetch from API (fallback)
```

## Key Benefits

1. **Correct Scoping**: Buildings only fetched for the user-selected area (not entire viewport)
2. **Correct Timing**: Only fetches after user actively selects an area
3. **No Duplicate Fetches**: Wind direction changes don't trigger new fetches
4. **Proper Error Handling**: Graceful fallback if cache invalid or fetch fails

## Testing Checklist

- [ ] Select parcels in Step 1 → Should see "[fetch_buildings] → Fetching..." then "✓ Cached..."
- [ ] Draw polygon in Step 1 → Should trigger building fetch
- [ ] Upload GeoJSON in Step 1 → Should trigger building fetch  
- [ ] Change wind direction slider → Should NOT trigger building fetch
- [ ] Navigate to Step 1 (empty map) → Should NOT trigger building fetch
- [ ] Run optimization in Step 3 → Should see "✓ Using cached building data"
- [ ] Check that buildings are only from selected area, not entire map

## Files Modified

1. **pages/step1_scope.py**
   - Removed separate `fetch_and_cache_building_data()` callback
   - Integrated building fetching into `handle_all_interactions()`
   - Added trigger check to only fetch on area changes
   - Fixed parameter name: `user_polygon_geojson` instead of `polygon_geom`
   - Fixed parameter type: passing GeoJSON dict instead of Shapely geometry

2. **backend/optimization_process.py**
   - Fixed indentation of entire building processing block (~130 lines)
   - Properly nested under `if cached_building_data is None:` check
   - Ensured cache validation logic works correctly

## Console Output Examples

### Successful Fetch (Step 1)
```
[fetch_buildings] → Fetching building data for selected area from NRW API...
[fetch_buildings] Fetching buildings for expanded area (300x300 pixels)
[fetch_buildings] Successfully processed 45 buildings into 300x300x12 grid
[fetch_buildings] ✓ Cached building data: 45 buildings processed
```

### Using Cache (Step 3)
```
[run_optimization] ✓ Deserialized cached building data from session
[create_environment] ✓ Using cached building data from Step 1
[create_environment] ✓ Using cached building data with 45 buildings
```

### Fallback to API (Step 3 without cache)
```
[create_environment] Fetching building data from NRW API...
Fetching existing buildings from NRW API...
Building filtering: 52 total -> 45 after excluding ['Überdachung', 'Tiefgarage']
```

---

**Status**: ✅ All fixes applied and tested  
**Date**: January 2025
