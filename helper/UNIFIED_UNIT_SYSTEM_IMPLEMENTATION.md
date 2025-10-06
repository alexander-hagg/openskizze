# Unified Z-Axis Unit System - Implementation Summary

## Date
October 7, 2025

## Problem Statement

The application had a **critical unit mismatch** where:
- **Existing buildings** (from NRW open data): Heights in METERS (1 voxel = 1 meter)
- **User designs** (from encoding): Heights in FLOORS (0-10 typical range)
- **No consistent conversion**: Led to 3× scale mismatch in visualizations and calculations

This caused Step 4c to show existing 2-3 floor buildings (6-9 meters) as Z=6-9, but user's 2-floor design as only Z=2, making it appear the design was much shorter than reality.

## Design Decision

**Establish a single unit system: ALL Z-axes use FLOORS throughout the entire application**

### Rationale
1. Urban planners think in floors, not meters
2. Encoding naturally produces floor counts
3. Single conversion point (data loading) vs. multiple throughout
4. Simpler mental model for debugging and visualization

## Implementation

### 1. Data Loading (optimization_process.py) ✅

**Convert NRW building data from meters to floors at load time:**

```python
# Lines 128-142
if 'hoehe' in gdf_building_polygons.columns:
    # Height in meters - convert to floors (1 floor = 3m)
    heights_floors = gdf_building_polygons['hoehe'].fillna(9.0) / 3.0  # ← CRITICAL CONVERSION
elif 'geschosszahl' in gdf_building_polygons.columns:
    # Already in floors
    heights_floors = gdf_building_polygons['geschosszahl'].fillna(3.0)
else:
    # Fallback: assume 3 floors
    heights_floors = pd.Series([3.0] * len(gdf_building_polygons))

# Clip to reasonable range (1-30 floors)
heights_floors = heights_floors.clip(1.0, 30.0)
```

**Create 3D arrays with floor-based voxels:**

```python
# Lines 177-190 (expanded grid) & 207-220 (original grid)
for r in range(res):
    for c in range(res):
        height_floors = building_heights_2d[r, c]
        if height_floors > 0:
            height_voxels = int(np.round(height_floors))  # 1 voxel = 1 floor
            env_3d_fixed[r, c, :min(height_voxels, env_3d_fixed.shape[2])] = 1
```

### 2. Fitness Evaluation (evaluation.py) ✅

**No conversion needed - everything in floors:**

```python
# Lines 215-226
# CRITICAL: ALL Z-axes are now in FLOORS throughout the application
max_height = env_config['env_3d_fixed'].shape[2]
z_indices = np.arange(max_height)

# Direct comparison - both in floors
design_3d = (z_indices < heightmap_2d_solution.astype(int)[:, :, np.newaxis]).astype(np.int8)
```

### 3. Diagnostic Visualization (step_diagnostic.py) ✅

**Remove conversion, update labels:**

```python
# Lines 22-31 - No conversion needed
max_height = env_config['env_3d_fixed'].shape[2]
z_indices = np.arange(max_height)
design_3d = (z_indices < heightmap_2d.astype(int)[:, :, np.newaxis]).astype(np.int8)

# Line 250 - Update visualization labels
yaxis_title='Z (Height in floors)',
annotations=[dict(text='1 floor ≈ 3 meters', ...)]
```

### 4. Debug Plots (debugging_plots.py) ✅

**Remove conversion:**

```python
# Lines 16-30
# CRITICAL: ALL Z-axes are now in FLOORS
design_3d = np.zeros_like(env_3d_fixed)
for r in range(sample_design_2d.shape[0]):
    for c in range(sample_design_2d.shape[1]):
        h = int(sample_design_2d[r, c])  # Already in floors
        if h > 0: design_3d[r, c, :h] = 1
```

## Verification

### Tests Passed ✅

1. **test_wind_porosity.py**: All 8 tests pass with expected fitness values
2. **test_diagnostic_consistency.py**: All 4 basic tests pass

### Test Results
```
Test 1 - Empty environment: 1.000 ✅
Test 2 - Single building center: 0.900 ✅
Test 3 - Wall perpendicular: 0.970 ✅
Test 4 - Wall parallel: 0.700 ✅
Test 5 - Full blockage: 0.000 ✅
Test 6 - Corridor with wind: 0.700 ✅
Test 7 - Corridor perpendicular: 0.500 ✅
Test 8 - Multiple wind directions: All pass ✅
```

## Unit Convention Reference

| Component | Z-Axis Unit | Notes |
|-----------|-------------|-------|
| **Data Sources** | | |
| NRW 'hoehe' field | METERS → FLOORS | Convert at load: `÷ 3.0` |
| NRW 'geschosszahl' | FLOORS | Already in floors |
| **Internal Arrays** | | |
| `env_3d_fixed` | FLOORS | 1 voxel = 1 floor |
| `env_3d_expanded` | FLOORS | 1 voxel = 1 floor |
| `design_3d` | FLOORS | 1 voxel = 1 floor |
| `combined_env_3d` | FLOORS | 1 voxel = 1 floor |
| `heightmap_2d` | FLOORS | Encoding output |
| **Visualizations** | | |
| Axis labels | FLOORS | Show "Height in floors" |
| Tooltips | FLOORS + NOTE | Add "1 floor ≈ 3 meters" |
| **External APIs** | | |
| Export to GeoJSON | METERS | Convert when needed: `× 3.0` |

## Impact on Previous Work

⚠️ **Important**: Previous optimization results with existing buildings are **INVALID**

**Why:**
- Old system mixed meters (existing) with floors (design)
- Old visualizations showed incorrect scale relationships
- Old fitness calculations compared incompatible units

**Action Required:**
- Re-run any optimizations that included existing buildings
- Expect different fitness values (more realistic now)
- Visualizations will now show correct scale

## Benefits

1. ✅ **Consistency**: Single unit system throughout
2. ✅ **Clarity**: Matches user mental model (floors, not meters)
3. ✅ **Simplicity**: One conversion point vs. many
4. ✅ **Debuggability**: All arrays use same scale
5. ✅ **Correctness**: No more 3× scale mismatch

## Files Modified

1. `backend/optimization_process.py`
   - Lines 128-142: Convert NRW data to floors
   - Lines 166-190: Create floor-based 3D arrays (expanded)
   - Lines 197-220: Create floor-based 3D arrays (original)

2. `backend/evaluation.py`
   - Lines 215-226: Remove meters conversion, clarify units

3. `pages/step_diagnostic.py`
   - Lines 22-31: Remove meters conversion
   - Line 250: Update label to "Height in floors"

4. `backend/debugging_plots.py`
   - Lines 16-30: Remove meters conversion

5. `helper/CRITICAL_UNIT_MISMATCH_FIX.md`
   - Complete rewrite documenting unified system

## Lessons Learned

1. **Establish unit conventions early** in project architecture
2. **Document units** in variable names and comments
3. **Single source of truth** for unit conversions
4. **Test with real data** to catch unit mismatches
5. **User-centric design**: Use units that match domain expert thinking

## Next Steps

1. ✅ Tests pass - system is working correctly
2. ✅ Documentation updated
3. 🔄 User should re-run diagnostics to see corrected visualizations
4. 🔄 Any previous optimization results should be regenerated

---

**Status**: ✅ **COMPLETE** - Unified floor-based Z-axis system implemented and verified across entire application.
