# Data Fetching Refactoring Plan

## Objective
Move all NRW API data fetching from `create_environment()` (called during optimization) to Step 1 (when user selects an area). This improves performance and user experience by:
1. Fetching data once instead of on every optimization run
2. Showing immediate feedback (3D preview) when area is selected
3. Reducing optimization wait time

## Current Flow
```
Step 1: User selects area
  ↓
Step 2: User sets constraints
  ↓
Step 3: User clicks "Optimize"
  ↓
start_optimization() called
  ↓
create_environment() called
  ↓
fetch_existing_buildings_data() ← API CALL HERE (slow!)
  ↓
Process buildings into env_3d arrays
  ↓
run_qd_optimization()
```

## New Flow
```
Step 1: User selects area
  ↓
fetch_and_process_buildings_for_area() ← API CALL HERE (async)
  ↓
Store in session-store['building_data']
  ↓
(Optional: Show 3D preview)
  ↓
Step 2: User sets constraints
  ↓
Step 3: User clicks "Optimize"
  ↓
start_optimization() called
  ↓
create_environment() called with cached_building_data
  ↓
Use cached data (no API call!)
  ↓
run_qd_optimization()
```

## Implementation Steps

### 1. ✅ Create data fetching function (DONE)
- `fetch_and_process_buildings_for_area()` in backend/data_io.py
- Returns dict with all processed building data

### 2. Modify create_environment() signature
```python
def create_environment(
    user_polygon_geojson: dict, 
    selected_features: list, 
    user_feature_ranges: dict, 
    hard_constraints: dict = None,
    cached_building_data: dict = None  # NEW parameter
):
```

### 3. Add cache usage logic to create_environment()
```python
# Early in function, after calculating grid parameters
if cached_building_data is not None:
    print("[create_environment] Using cached building data")
    # Extract from cache
    env_3d_expanded = cached_building_data['env_3d_expanded']
    building_function_map_exp = cached_building_data['building_function_map']
    id_to_function = cached_building_data['function_lookup']
    # ... etc
    
    # Still need to create env_3d_fixed from expanded by extracting design area
    # Still need to create buildable_mask (user polygon might have changed)
else:
    print("[create_environment] No cached data, fetching from API")
    # Existing fetching logic
    gdf_buildings_native = fetch_existing_buildings_data(...)
    # ... process buildings ...
```

### 4. Add callback to Step 1
```python
@callback(
    Output('session-store', 'data', allow_duplicate=True),
    Output('building-fetch-status', 'children'),
    Input('active-polygon-layer', 'data'),
    State('session-store', 'data'),
    background=True,
    prevent_initial_call=True
)
def fetch_buildings_for_selected_area(polygon_data, session_data):
    if not polygon_data:
        return no_update, ""
    
    building_data = fetch_and_process_buildings_for_area(polygon_data)
    
    if building_data:
        session_data = session_data or {}
        session_data['building_data'] = building_data
        return session_data, "✓ Buildings loaded"
    else:
        return no_update, "⚠ No buildings found"
```

### 5. Update start_optimization() call chain
```python
# In step3_optimize.py
def run_optimization(...):
    ...
    cached_building_data = session_data.get('building_data')
    
    archive, labels, env_config = start_optimization(
        session_data['site_polygon'],
        session_data['wind_direction'],
        selected_features,
        user_feature_ranges,
        hard_constraints,
        qd_hyperparams,
        objective_function,
        cached_building_data=cached_building_data,  # NEW
        progress_callback=progress_callback
    )
```

```python
# In optimization_process.py
def start_optimization(..., cached_building_data=None):
    ...
    env_config = create_environment(
        user_polygon_geojson, 
        selected_features, 
        user_feature_ranges, 
        hard_constraints,
        cached_building_data=cached_building_data  # NEW
    )
```

## Serialization Considerations

Building data needs to be serializable for session-store. NumPy arrays and GeoDataFrames are NOT directly serializable. Options:

### Option A: Serialize to pickle/base64 (RECOMMENDED)
```python
import pickle
import base64

# When storing
building_data_serialized = base64.b64encode(pickle.dumps(building_data)).decode('utf-8')
session_data['building_data'] = building_data_serialized

# When retrieving
building_data = pickle.loads(base64.b64decode(session_data['building_data']))
```

### Option B: Convert to JSON-serializable format
```python
# Convert numpy arrays to lists
building_data_json = {
    'env_3d_expanded': env_3d_expanded.tolist(),
    'building_function_map': building_function_map.tolist(),
    # ... etc
}

# When retrieving, convert back
env_3d_expanded = np.array(building_data['env_3d_expanded'])
```

Option A is cleaner and preserves types better.

## Testing Checklist

- [ ] Select area in Step 1
- [ ] Check console: Should see "[fetch_buildings] Fetching..."
- [ ] Navigate to Step 3, start optimization
- [ ] Check console: Should see "[create_environment] Using cached building data"
- [ ] Should NOT see "Fetching existing buildings from NRW API..." during optimization
- [ ] Test with fresh session (no cache): Should fall back to fetching during optimization
- [ ] Test saving/loading project: Cached data should persist

## Benefits

1. **Performance**: API call happens once, not on every optimization run
2. **User Experience**: Immediate feedback when area is selected
3. **Reliability**: Can retry fetch if it fails without restarting optimization
4. **Flexibility**: Opens door for 3D preview in Step 1
5. **Caching**: Data persists across optimization runs with same area
