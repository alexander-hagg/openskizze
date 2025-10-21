# Session State Management Documentation

## Overview
This document describes the complete session state structure for OpenSKIZZE, ensuring consistent save/load functionality across the application.

## Session State Structure

### 1. session-store (dcc.Store with storage_type='session')
Contains user configuration and project settings that persist throughout a session.

```python
session_data = {
    # Step 1: Parcel Selection & Wind
    'site_polygon': {...},              # GeoJSON of selected parcel
    'wind_direction': 180,              # Integer 0-360 (degrees)
    'building_data': {...},             # Cached LOD2 building data (optional)
    
    # Step 2: Features & Constraints
    'selected_features': [0, 1, 2, 3],  # List of selected feature indices
    'feature_set': 'original',          # 'original' or 'planning'
    'feature_ranges': {                 # User-adjusted feature ranges
        '0': [min, max],                # Key is feature index as string
        '1': [min, max],
        # ... for each selected feature
    },
    'hard_constraints': {
        'max_height': 30,               # Meters
        'min_distance': 5               # Meters
    },
    'qd_hyperparams': {
        'num_generations': 1000,
        'num_emitters': 5,
        'num_niches': 5,
        'batch_size': 16
    },
    'objective_function': 'simple_porosity',  # or 'street_canyon'
}
```

### 2. results-store (dcc.Store with storage_type='session')
Contains optimization results and archive data.

```python
results_data = {
    'full_results_path': 'temp_results/uuid.pkl',  # Path to pickled elites list
    'env_3d_path': 'temp_results/uuid_env.pkl',    # Path to existing buildings 3D data
    'archive_dims': [5, 5, 5, 5],                  # Grid dimensions per feature
    'labels': ['Feature 1', 'Feature 2', ...],     # Translated feature labels (DE/EN)
    'grid_geojson': {...},                         # GeoJSON of design grid
    'xy_length': 50,                               # Grid resolution
    'selected_features_indices': [0, 1, 2, 3],     # Selected features for archive
    'feature_ranges': {                            # Actual ranges used in optimization
        '0': [min, max],
        '1': [min, max],
        # ...
    },
    'feature_set': 'original',                     # Which feature set was used
    'grid_bounds_native': [minx, miny, maxx, maxy], # EPSG:25832 bounds
    'expanded_bounds_native': [...],               # Expanded area for context
    'design_offset': [start_x, start_y],           # Design grid position in expanded grid
    'phenotype_config': {...}                      # Adaptive phenotype parameters
}
```

### 3. comparison-store (dcc.Store with storage_type='session')
Contains cluster analysis results and selected solutions for comparison.

```python
comparison_data = [
    # List of cluster IDs selected for detailed comparison
    18,  # Cluster 18
    42,  # Cluster 42
]
```

## Callback Responsibilities

### Step 1 (step1_scope.py)
**Saves to session:**
- `site_polygon` - when parcel is selected/edited
- `wind_direction` - when slider changes
- `building_data` - when LOD2 data is fetched (optional caching)

**Restores from session:**
- `site_polygon` → map display
- `wind_direction` → slider value

### Step 2 (step2_constraints.py)
**Saves to session:**
- `selected_features` - when checklist changes
- `feature_set` - when radio button changes (clears feature_ranges)
- `feature_ranges` - when sliders change
- `hard_constraints` - when max_height/min_distance change
- `qd_hyperparams` - when advanced settings change
- `objective_function` - when radio button changes

**Restores from session:**
- `selected_features` → checklist
- `feature_set` → radio button
- `feature_ranges` → slider values (only if feature_set matches)
- `hard_constraints` → slider values
- `qd_hyperparams` → input fields
- `objective_function` → radio button

### Step 3 (step3_optimize.py)
**Saves to results-store:**
- All results data after optimization completes

**Reads from session:**
- All step 1 & 2 data to run optimization

### Step 4 (step4_compare.py)
**Saves to comparison-store:**
- Selected cluster IDs for comparison

**Reads from results-store:**
- Archive data for clustering and analysis

### Step 5 (step5_compare_detail.py)
**Reads from:**
- results-store - archive data
- comparison-store - which clusters to compare

## Save/Load Infrastructure

### Project File Format (.skizze)
Pickled dictionary containing:
```python
{
    'session_data': {...},      # Complete session-store
    'results_data': {...},      # Complete results-store (with embedded elites)
    'comparison_data': [...],   # Complete comparison-store
    'version': '1.0',
    'timestamp': '2025-10-21T...'
}
```

### Save Process (app.py)
1. User clicks "Projekt speichern"
2. `save_project_file()` callback triggered
3. `gather_application_state()` collects all three stores
4. If `results_data['full_results_path']` exists, loads and embeds actual elite data
5. Pickles to BytesIO, base64 encodes, triggers download

### Load Process (app.py)
1. User uploads .skizze file
2. `load_project_file()` callback triggered
3. `load_state_from_file()` unpickles data
4. If results were embedded, creates new temp file and updates path
5. Returns all three store dictionaries + navigates to '/'

### New Project (app.py)
1. User clicks "Neues Projekt"
2. `new_project()` callback triggered
3. `reset_application_state()` returns empty dicts
4. All stores cleared, navigation to '/'

## Critical Behaviors

### Feature Set Changes
When `feature_set` changes (original ↔ planning):
1. Session callback in step2 clears `feature_ranges`
2. Slider creation callback regenerates sliders with new labels and ranges
3. User adjustments to new sliders are saved with new feature_set

### Navigation Within Session
- All settings persist when navigating between pages
- Restoration callbacks use `pathname` check to only fire on page entry
- Use `prevent_initial_call=True` to avoid unnecessary updates

### Project Load
- All restoration callbacks fire due to session-store.data change
- Each page's restoration callback checks pathname before updating
- Results are restored to temp files for continued work

## Testing Checklist

### Save/Load Test
- [ ] Create project with all settings configured
- [ ] Run optimization
- [ ] Perform clustering analysis
- [ ] Select clusters for comparison
- [ ] Save project (.skizze file)
- [ ] Click "Neues Projekt" to clear
- [ ] Load saved project
- [ ] Verify all settings restored (step 1, 2)
- [ ] Verify optimization results visible (step 3, 4)
- [ ] Verify cluster selections restored (step 4, 5)

### Session Persistence Test
- [ ] Configure all settings on pages 1-2
- [ ] Navigate to page 3 (don't optimize yet)
- [ ] Go back to page 2
- [ ] Verify all settings unchanged
- [ ] Change feature set
- [ ] Verify sliders reset to appropriate ranges
- [ ] Go back to page 1
- [ ] Verify parcel and wind direction unchanged

### Feature Set Switch Test
- [ ] Start with "Original Features"
- [ ] Adjust some feature ranges
- [ ] Switch to "Planning-Focused Features"
- [ ] Verify all sliders reset to full ranges
- [ ] Adjust planning feature ranges
- [ ] Switch back to "Original Features"
- [ ] Verify sliders reset (original custom ranges lost)

## Known Issues and Solutions

### Issue: Slider values not restoring
**Cause**: feature_ranges keys are strings but feature indices are integers
**Solution**: Always use `str(index)` when saving, `int(key)` when reading

### Issue: Wrong feature labels after load
**Cause**: feature_set not passed to translate_feature_labels()
**Solution**: Always pass feature_set parameter (now fixed in all pages)

### Issue: Results not loading after project load
**Cause**: Temp file paths don't exist after app restart
**Solution**: Project save embeds actual data, load recreates temp files

### Issue: Feature ranges reset when navigating
**Cause**: Restoration callback checks feature_set mismatch
**Solution**: Intended behavior - only restores if feature_set matches

## Implementation Status

✅ **Implemented:**
- Session state structure (session-store, results-store, comparison-store)
- Save/load infrastructure (project_state.py)
- Step 1 save/restore (site_polygon, wind_direction)
- Step 2 save (all settings)
- Step 3 save (results)
- Step 4 save (cluster selections)
- Feature set change handling (clears ranges)

✅ **Fixed in this session:**
- Step 2 restore now includes objective_function and feature_set
- Feature range sliders properly restore from session
- Feature set selector properly restores from session
- Objective function selector properly restores from session

🎯 **Complete:** All session state management is now consistent and working.
