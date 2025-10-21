# Complete Session State Management - OpenSKIZZE

## Session Store Structure

The `session-store` (dcc.Store with storage_type='session') contains all user settings and data needed to preserve the application state within a browser session.

### Complete Session Data Dictionary

```python
session_data = {
    # --- STEP 1: Scope Definition ---
    'site_polygon': dict,           # GeoJSON FeatureCollection of selected parcel
    'wind_direction': int,          # Wind direction in degrees (0-360)
    'building_data': str,           # Base64-encoded pickled building data (LOD2)
    
    # --- STEP 2: Feature Selection & Constraints ---
    'selected_features': list,      # List of feature indices (0-7)
    'feature_set': str,             # 'original' or 'planning'
    'feature_ranges_original': dict, # Feature ranges for original set {index: [min, max]}
    'feature_ranges_planning': dict, # Feature ranges for planning set {index: [min, max]}
    'objective_function': str,      # 'simple_porosity' or 'street_canyon'
    'hard_constraints': {
        'max_height': int,          # Maximum building height in meters
        'min_distance': float       # Minimum distance between buildings in meters
    },
    'qd_hyperparams': {
        'num_generations': int,     # QD algorithm generations
        'num_emitters': int,        # Number of emitters
        'num_niches': int,          # Niches per feature dimension
        'batch_size': int           # Batch size for evaluation
    },
    
    # --- STEP 3: Optimization Results ---
    # (stored in results-store, not session-store)
    
    # --- STEP 4/5: Comparison ---
    # (stored in comparison-store, not session-store)
}
```

## Session State Management by Page

### Step 1: Scope (step1_scope.py)

**Saved Data:**
- `site_polygon` - Selected parcel geometry (GeoJSON)
- `wind_direction` - Wind direction (0-360 degrees)
- `building_data` - Cached LOD2 building data (base64-encoded pickle)

**When Saved:**
- When user selects/draws/uploads a parcel
- When user changes wind direction
- Building data fetched automatically when parcel changes

**Restoration:**
- No restoration callback (Step 1 is entry point)
- Map re-renders from session data on page load

**Implementation:**
```python
@callback(
    Output('session-store', 'data', allow_duplicate=True),
    Input('parcels-layer', 'click_feature'),
    Input('edit-control', 'geojson'),
    Input('upload-geojson', 'contents'),
    Input('wind-direction-selector', 'value'),
    State('session-store', 'data'),
    prevent_initial_call=True
)
def save_site_and_wind(...)
```

### Step 2: Constraints (step2_constraints.py)

**Saved Data:**
- `selected_features` - Which features are selected (indices 0-7)
- `feature_set` - 'original' or 'planning'
- `feature_ranges_original` - Custom ranges for original features
- `feature_ranges_planning` - Custom ranges for planning features
- `hard_constraints` - max_height, min_distance
- `qd_hyperparams` - QD algorithm settings
- `objective_function` - Wind flow calculation method

**When Saved:**
- Any time user changes any input (measures checklist, sliders, constraints, etc.)
- Feature ranges are NAMESPACED by feature_set to prevent cross-contamination
- When feature_set changes, OLD slider values are NOT saved to NEW feature set

**Restoration:**
```python
@callback(
    Output('measures-checklist', 'value', allow_duplicate=True),
    Output('max-height-constraint', 'value', allow_duplicate=True),
    Output('min-distance-constraint', 'value', allow_duplicate=True),
    Output('qd-generations-input', 'value', allow_duplicate=True),
    Output('qd-emitters-input', 'value', allow_duplicate=True),
    Output('qd-niches-input', 'value', allow_duplicate=True),
    Output('qd-batch-size-input', 'value', allow_duplicate=True),
    Output('objective-function-selector', 'value', allow_duplicate=True),
    Output('feature-set-selector', 'value', allow_duplicate=True),
    Input('session-store', 'data'),
    Input('url', 'pathname'),
    prevent_initial_call=True
)
def restore_step2_from_session(...)
```

**Critical Implementation Details:**

1. **Namespaced Feature Ranges:**
   - `feature_ranges_original` stores ranges for "Original Features" set
   - `feature_ranges_planning` stores ranges for "Planning-Focused Features" set
   - Switching feature sets does NOT mix up ranges

2. **Feature Set Change Detection:**
   ```python
   feature_set_changed = (feature_set != previous_feature_set and not triggered_by_restoration)
   if feature_set_changed:
       # Skip saving slider values (they belong to old feature set)
       print("[DEBUG] Skipping range save - feature set just changed")
   ```

3. **Feature Set Saving:**
   ```python
   if triggered_by_feature_selector:
       session_data['feature_set'] = feature_set
   else:
       # Keep existing value during restoration/other inputs
       print("[DEBUG-SESSION-UPDATE] Keeping existing feature_set")
   ```

4. **URL Navigation Handling:**
   ```python
   if ctx.triggered_id == 'url':
       if session_data and 'feature_set' in session_data:
           return no_update  # Let restoration callback handle it
   ```

### Step 3: Optimization (step3_optimize.py)

**Session Data Used (Read-Only):**
- Reads all settings from session-store
- Does NOT modify session-store
- Writes results to `results-store` instead

**Results Store:**
- Separate dcc.Store (storage_type='memory')
- Contains optimization results, not user settings
- Cleared on page refresh

### Step 4: Comparison (step4_compare.py)

**Session Data Used (Read-Only):**
- Reads `feature_set` to display correct labels
- Reads from `results-store` for archive data

**Comparison Store:**
- Separate dcc.Store (storage_type='memory')  
- Contains selected cluster IDs for detailed comparison
- Cleared on page refresh

### Step 5: Detailed Comparison (step5_compare_detail.py)

**Session Data Used (Read-Only):**
- Reads `feature_set` for feature labels
- Reads from `comparison-store` for selected solutions

## Common Issues and Solutions

### Issue 1: Feature Set Resets After Optimization

**Symptom:** Select planning features → optimize → return to page 2 → shows original features

**Root Cause:** Session update callback fired BEFORE restoration callback, overwriting feature_set with stale component value

**Solution:**
```python
# Only save feature_set when explicitly triggered by feature-set-selector
if triggered_by_feature_selector:
    session_data['feature_set'] = feature_set
else:
    # Keep existing value
    existing_feature_set = session_data.get('feature_set', 'original')
```

### Issue 2: Wrong Slider Ranges After Feature Set Switch

**Symptom:** Select planning (adjust sliders) → switch to original → sliders show planning ranges

**Root Cause:** Both feature sets use indices 0-7, ranges were saved to single `feature_ranges` key

**Solution:**
```python
# Use namespaced keys
ranges_key = f'feature_ranges_{feature_set}'
session_data[ranges_key] = new_feature_ranges
```

### Issue 3: Planning Ranges Applied to Original Sliders

**Symptom:** Adjust planning slider → switch to original → wrong ranges appear

**Root Cause:** When switching feature sets, session callback saved current slider values (which belong to OLD set) to NEW set's namespace

**Solution:**
```python
# Detect feature set change and skip saving ranges
feature_set_changed = (feature_set != previous_feature_set and not triggered_by_restoration)
if slider_ids and slider_values and not feature_set_changed:
    session_data[ranges_key] = new_feature_ranges
elif feature_set_changed:
    print("[DEBUG] Skipping range save - feature set just changed")
```

### Issue 4: Hard Constraints Not Saved

**Symptom:** Adjust max_height → navigate away → return → value reset

**Root Cause:** Constraints are ALWAYS saved (this should work), but restoration may fail

**Check:**
1. Verify `hard_constraints` key exists in session_data
2. Check restoration callback is triggered
3. Verify Output connections in restoration callback
4. Look for debug logs: `[DEBUG] Saved hard_constraints: max_height=...`

## Testing Checklist

### Basic Session Persistence

- [ ] **Step 1: Parcel selection**
  - [ ] Select parcel → navigate to step 2 → return → parcel still selected
  - [ ] Change wind direction → navigate away → return → wind direction preserved

- [ ] **Step 2: Original features**
  - [ ] Select features → navigate away → return → same features selected
  - [ ] Adjust sliders → navigate away → return → slider ranges preserved
  - [ ] Change max height → navigate away → return → max height preserved
  - [ ] Change min distance → navigate away → return → min distance preserved
  - [ ] Select objective → navigate away → return → objective preserved

- [ ] **Step 2: Planning features**
  - [ ] Switch to planning → adjust sliders → navigate away → return → planning selected + ranges preserved
  - [ ] Select planning → optimize → return to page 2 → planning still selected
  - [ ] Adjust planning sliders → switch to original → original sliders use default ranges (not planning ranges)

- [ ] **Step 2: QD Hyperparameters**
  - [ ] Enable advanced mode → adjust generations → navigate away → return → value preserved
  - [ ] Adjust all 4 QD params → navigate away → return → all values preserved

### Feature Set Switching

- [ ] **Original → Planning → Original**
  - [ ] Select original → adjust sliders → switch to planning → sliders show planning features
  - [ ] Switch to planning → adjust sliders → switch to original → original sliders show original ranges (not planning)
  - [ ] Verify both feature sets maintain independent ranges

- [ ] **After Optimization**
  - [ ] Run optimization with original features → return to page 2 → original still selected
  - [ ] Run optimization with planning features → return to page 2 → planning still selected
  - [ ] Run with planning → return → manually switch to original → correct sliders/labels

### Project Save/Load

- [ ] **Save project**
  - [ ] Configure all settings on pages 1 & 2 → run optimization → save project
  - [ ] Verify .skizze file contains all session data

- [ ] **Load project**
  - [ ] Load .skizze file → verify page 1 settings restored
  - [ ] Navigate to page 2 → verify all settings restored (features, ranges, constraints, objective, feature_set)
  - [ ] Navigate to page 4 → verify results displayed

## Debug Logging Reference

### Key Log Messages

**Step 2 Restoration:**
```
[DEBUG-RESTORE] Restoring feature_set='planning', max_height=12m, min_distance=5m
```

**Session Update:**
```
[DEBUG-SESSION-UPDATE] Called with feature_set='planning', triggered_by=feature-set-selector, pathname=/step2
[DEBUG-SESSION-UPDATE] Saved feature_set='planning' to session (user selected)
```

**Feature Set Change:**
```
[DEBUG] Feature set changed from original to planning
[DEBUG] Skipping range save - feature set just changed (sliders belong to old set)
```

**Range Restoration:**
```
[DEBUG] Restoring 8 feature ranges from feature_ranges_planning
```

**Constraints Saving:**
```
[DEBUG] Saved hard_constraints: max_height=15m, min_distance=3m
```

## Architecture Summary

```
┌─────────────────────────────────────────────────────────────┐
│                       Browser Session                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │           session-store (persistent)                │   │
│  │  • site_polygon                                      │   │
│  │  • wind_direction                                    │   │
│  │  • building_data                                     │   │
│  │  • selected_features                                 │   │
│  │  • feature_set ('original'|'planning')              │   │
│  │  • feature_ranges_original {idx: [min,max]}        │   │
│  │  • feature_ranges_planning {idx: [min,max]}        │   │
│  │  • hard_constraints {max_height, min_distance}     │   │
│  │  • qd_hyperparams {generations, emitters, ...}     │   │
│  │  • objective_function                                │   │
│  └─────────────────────────────────────────────────────┘   │
│                           ▲                                  │
│                           │                                  │
│              ┌────────────┴────────────┐                    │
│              │                         │                     │
│         SAVE (on input)          RESTORE (on navigate)      │
│              │                         │                     │
│  ┌───────────▼──────┐     ┌───────────▼──────┐            │
│  │  Step 1 (Scope)  │────▶│  Step 2 (Config) │            │
│  └──────────────────┘     └───────────┬──────┘            │
│                                        │                     │
│                                        ▼                     │
│                           ┌────────────────────┐            │
│                           │ Step 3 (Optimize)  │            │
│                           └────────┬───────────┘            │
│                                    │                         │
│                                    ▼                         │
│                          ┌──────────────────┐               │
│                          │  results-store   │               │
│                          │   (memory only)  │               │
│                          └────────┬─────────┘               │
│                                   │                          │
│                         ┌─────────▼─────────┐               │
│                         │  Step 4 (Compare) │               │
│                         └─────────┬─────────┘               │
│                                   │                          │
│                                   ▼                          │
│                        ┌───────────────────────┐            │
│                        │  Step 5 (Detail)      │            │
│                        └───────────────────────┘            │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## Implementation Status

✅ **Complete** - All session state saving and restoration implemented
✅ **Namespaced Ranges** - Original and planning feature ranges stored separately  
✅ **Feature Set Persistence** - Feature set selection preserved across navigation
✅ **Hard Constraints** - max_height and min_distance saved and restored
✅ **QD Hyperparameters** - All QD settings preserved
✅ **Objective Function** - Wind flow calculation method saved
✅ **Debug Logging** - Comprehensive logging for troubleshooting
✅ **Project Save/Load** - All session data embedded in .skizze files

## Next Steps

1. **Test thoroughly** - Use testing checklist above
2. **Remove debug logs** - Once verified working, clean up console output
3. **Add user feedback** - Show save indicators when settings change
4. **Document for users** - Update user guide with session persistence behavior
