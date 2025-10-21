# Feature Constraints Implementation Summary

## Overview
This document describes the implementation of feature constraint saving, restoration, and enforcement in the OpenSKIZZE application. Feature constraints (Zielbereiche für Merkmale) are the user-defined ranges set via sliders on Step 2 (Constraints page).

## Implementation Details

### 1. Saving Feature Constraints ✓

**File:** `pages/step2_constraints.py`

Feature constraints are automatically saved to the session store whenever the user adjusts the range sliders:

```python
@callback(
    Output('session-store', 'data', allow_duplicate=True),
    Input({'type': 'feature-range-slider', 'index': ALL}, 'value'),
    ...
)
def update_session_with_features_and_ranges(...):
    session_data['feature_ranges'] = {
        str(s_id['index']): s_val for s_id, s_val in zip(slider_ids, slider_values)
    }
```

**Storage format:** 
- Key: `feature_ranges` in `session-store`
- Value: Dictionary mapping feature indices (as strings) to [min, max] ranges
- Example: `{"0": [100.0, 500.0], "1": [3.0, 15.0], ...}`

**Project file persistence:**
Feature constraints are automatically included when saving/loading projects because they are stored in `session_data`, which is handled by `backend/project_state.py`.

### 2. Restoring Feature Constraints on Page Reload ✓

**File:** `pages/step2_constraints.py`

When the user navigates to Step 2, feature constraints are automatically restored:

**Callback flow:**
1. `restore_step2_from_session` callback fires when pathname changes to '/step2'
2. This updates `measures-checklist` with saved `selected_features`
3. The change in `measures-checklist` triggers `create_range_sliders`
4. `create_range_sliders` reads saved ranges from `session_data.get('feature_ranges', {})`
5. Sliders are created with saved values: `slider_value = user_range if user_range else [min_v, max_v]`

**Key code:**
```python
@callback(
    Output('feature-range-sliders-container', 'children'),
    Input('measures-checklist', 'value'),
    State('session-store', 'data'),
    ...
)
def create_range_sliders(selected_indices, lang, session_data, max_height_input):
    saved_ranges = session_data.get('feature_ranges', {}) if session_data else {}
    
    for i, index in enumerate(sorted_indices):
        # Get saved value if available
        user_range = saved_ranges.get(str(index), None)
        slider_value = user_range if user_range else [min_v, max_v]
        # Create slider with slider_value
```

### 3. Using Feature Constraints in QD Optimization ✓

**File:** `backend/optimization_process.py`

Feature constraints define the bounds of the QD archive:

```python
def create_environment(user_polygon_geojson, selected_features, user_feature_ranges, hard_constraints):
    # Build final ranges list using user-defined ranges
    for feature_index in selected_features:
        user_range = user_feature_ranges.get(str(feature_index))
        if user_range:
            final_feat_ranges.append(user_range)  # Use user's custom range
        else:
            final_feat_ranges.append(dynamic_ranges[feature_index])  # Use default
```

**File:** `backend/optimizer.py`

The archive is created with these ranges:

```python
def run_qd_optimization(encoding_obj, env_config, qd_config, progress_callback=None):
    archive = GridArchive(
        solution_dim=solution_dim,
        dims=[qd_config['num_niches']] * len(env_config['labels']),
        ranges=env_config['feat_ranges'],  # User-defined ranges from Step 2
        learning_rate=qd_config['learning_rate'],
        threshold_min=0.0
    )
```

### 4. Filtering Solutions from Archive ✓

**File:** `pages/step3_optimize.py`

Solutions are filtered when extracted from the archive to ensure they strictly respect user-defined constraints:

```python
@callback(
    Output('results-store', 'data', allow_duplicate=True),
    Input('start-optimization-btn', 'n_clicks'),
    ...
)
def run_optimization(...):
    # Extract solutions from archive
    objectives = archive.data('objective')
    measures = archive.data('measures')
    solutions = archive.data('solution')
    
    # Filter solutions to ensure they respect user-defined feature constraints
    full_list_of_elites = []
    for i in range(len(objectives)):
        # Check if this solution respects all feature constraints
        is_valid = True
        if user_feature_ranges:
            for feat_idx_str, (min_val, max_val) in user_feature_ranges.items():
                feat_idx = int(feat_idx_str)
                if feat_idx in selected_features:
                    pos = selected_features.index(feat_idx)
                    measure_value = measures[i][pos]
                    if not (min_val <= measure_value <= max_val):
                        is_valid = False
                        break
        
        if is_valid:
            # Only include solutions that meet ALL constraints
            full_list_of_elites.append({...})
    
    # Store feature_ranges in results for later use
    results_summary_to_store = {
        ...
        'feature_ranges': user_feature_ranges,  # Store for downstream filtering
        ...
    }
```

**Why filtering is needed:**
The ribs archive may contain solutions slightly outside the specified ranges due to:
- Numerical precision issues at boundaries
- Archive's internal grid discretization
- Boundary handling in the optimization algorithm

Filtering ensures that only solutions strictly within user-defined ranges are presented to the user.

**File:** `backend/analysis.py`

Additional filtering capability is maintained in the clustering analysis:

```python
def cluster_and_analyze_solutions(results_path, algorithm='dbscan', params=None, feature_filters=None):
    # Solutions should already be filtered, but apply additional filters if specified
    filtered_elites = []
    if feature_filters:
        for elite in list_of_elites:
            is_valid = True
            for feat_idx_str, (min_val, max_val) in feature_filters.items():
                feat_idx = int(feat_idx_str)
                if not (min_val <= elite['measures'][feat_idx] <= max_val):
                    is_valid = False
                    break
            if is_valid:
                filtered_elites.append(elite)
```

## Summary

The implementation ensures that:

1. ✅ **User-defined feature constraints are saved** in the session store when sliders are adjusted
2. ✅ **Feature constraints are automatically restored** when the page is reloaded or a project is opened
3. ✅ **Feature constraints define the QD archive bounds** during optimization
4. ✅ **Solutions outside constraints are filtered out** when extracting from the archive
5. ✅ **Feature constraints are persisted** in project files for future sessions

## Testing Recommendations

To verify the implementation works correctly:

1. **Test saving:** 
   - Set custom ranges on Step 2
   - Navigate away and back to Step 2
   - Verify sliders show the same values

2. **Test persistence:**
   - Set custom ranges on Step 2
   - Save project
   - Start new project
   - Load saved project
   - Navigate to Step 2
   - Verify sliders show the saved values

3. **Test optimization:**
   - Set narrow feature constraints (e.g., Built Area: 200-300 m²)
   - Run optimization
   - Check that all solutions in results have Built Area between 200-300 m²
   - Verify no solutions exceed the specified ranges

4. **Test filtering:**
   - Run optimization with default ranges
   - Navigate to Step 4 (Compare)
   - Adjust filter sliders to narrow ranges
   - Verify clustering only includes solutions within the filtered ranges

## Technical Notes

- Feature ranges are stored with feature **indices** (0-7) as string keys
- Ranges are in **physical units** (m, m², count) not normalized values
- Feature indices 6 and 7 (Building Mass X/Y) use normalized ranges [0.0, 1.0]
- The filtering uses `<=` comparisons, so boundary values are included
- Re-indexing occurs after filtering to ensure contiguous IDs
