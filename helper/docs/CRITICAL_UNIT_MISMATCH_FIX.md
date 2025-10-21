# CRITICAL ARCHITECTURAL FIX: Unified Z-Axis Unit System

## Problem Discovery

User reported that Step 4c visualization showed red columns at Z=8 (showing as 8 floors) even though:
- The user's design only had 1-2 floors
- The existing buildings in the region are known to be only 2-3 floors

Investigation revealed a fundamental architectural issue: **mixed unit systems** where:
- Existing buildings from NRW data were stored in **METERS**
- User's design was generated in **FLOORS**
- No consistent conversion between the two

## Design Decision: Unified Unit System

**NEW ARCHITECTURE: All Z-axes use FLOORS throughout the application**

### Rationale
1. **User mental model**: Urban planners think in floors, not meters
2. **Encoding output**: The parametric encoding naturally produces floor counts (0-10 typical)
3. **Simplicity**: One conversion point (at data loading) vs multiple conversion points throughout
4. **Consistency**: Same units everywhere makes debugging and visualization easier

### Unit Convention
- **Internal representation**: 1 voxel = 1 floor throughout all 3D arrays
- **Data loading**: Convert NRW data from meters to floors (÷ 3.0)
- **Visualization**: Show "floors" in labels, optionally add "1 floor ≈ 3 meters" note
- **Export**: Convert to meters when needed for external APIs (× 3.0)

## Implementation

### 1. Data Loading (optimization_process.py)

**Convert NRW building data from meters to floors:**

```python
# Extract building heights from NRW data
if 'hoehe' in gdf_building_polygons.columns:
    # Height in meters - convert to floors (1 floor = 3m)
    heights_floors = gdf_building_polygons['hoehe'].fillna(9.0) / 3.0
elif 'geschosszahl' in gdf_building_polygons.columns:
    # Already in floors
    heights_floors = gdf_building_polygons['geschosszahl'].fillna(3.0)
else:
    # Fallback: assume 3 floors
    heights_floors = pd.Series([3.0] * len(gdf_building_polygons))

# Clip to reasonable range (1-30 floors)
heights_floors = heights_floors.clip(1.0, 30.0)

# Fill 3D array with floor-based voxels
for r in range(res):
    for c in range(res):
        height_floors = building_heights_2d[r, c]
        if height_floors > 0:
            height_voxels = int(np.round(height_floors))  # 1 voxel = 1 floor
            env_3d_fixed[r, c, :min(height_voxels, env_3d_fixed.shape[2])] = 1
```

### 2. Evaluation (evaluation.py)

**No conversion needed - everything in floors:**

```python
# heightmap_2d_solution is in FLOORS, env_3d_fixed is in FLOORS
max_height = env_config['env_3d_fixed'].shape[2]
z_indices = np.arange(max_height)
design_3d = (z_indices < heightmap_2d_solution.astype(int)[:, :, np.newaxis]).astype(np.int8)
```

### 3. Visualization (step_diagnostic.py, debugging_plots.py)

**Show floors in labels, add clarifying note:**

```python
# Create 3D design array - all in floors
design_3d = (z_indices < heightmap_2d.astype(int)[:, :, np.newaxis]).astype(np.int8)

# Update visualization labels
yaxis_title='Z (Height in floors)',
annotations=[dict(text='1 floor ≈ 3 meters', ...)]
```

## Files Modified

1. **backend/optimization_process.py**
   - Lines 128-142: Convert NRW heights from meters to floors
   - Lines 166-190: Create 3D arrays with floor-based voxels
   - Lines 197-220: Same for original (non-expanded) grid
   
2. **backend/evaluation.py**
   - Lines 215-226: Remove meters conversion, add clarifying comment
   
3. **pages/step_diagnostic.py**
   - Lines 22-31: Remove meters conversion
   - Line 250: Update visualization label to "Height in floors"
   
4. **backend/debugging_plots.py**
   - Lines 16-30: Remove meters conversion

## Benefits of Unified System

1. **Consistency**: No more mental conversion between meters and floors
2. **Debuggability**: All 3D arrays use same units, easier to inspect
3. **User-friendly**: Matches how urban planners think about buildings
4. **Single conversion point**: Only convert at data loading, not throughout pipeline
5. **Visualization clarity**: Can show "3 floors" instead of "9 meters"

## Why This Approach

### Alternative Considered: Everything in Meters
- ❌ Encoding would need to output meters (unnatural: "generate 6-30 meters")
- ❌ QD features would be in mixed units (floors for count, meters for height)
- ❌ User inputs would need conversion ("max 5 floors" → "max 15 meters")

### Chosen Approach: Everything in Floors
- ✅ Encoding outputs natural range (0-10 floors)
- ✅ Single conversion at data loading (NRW meters → floors)
- ✅ Visualizations can show floors with meter note
- ✅ User thinks in floors throughout

## Migration Notes

**Previous optimizations are INVALID** if they had existing buildings because:
- Old system: Existing buildings at 6-9 meters (correct physical height)
- Old system: User designs at 2 floors (physically correct as 2 floors)
- Old system: Comparison wrong (2 voxels vs 6-9 voxels = design too short)

**New system**:
- Existing buildings: 2-3 floors (converted from 6-9 meters)
- User designs: 2 floors
- Comparison correct (2 voxels vs 2-3 voxels = realistic scale)

## Testing

Run tests to verify:
```bash
python tests/test_wind_porosity.py
python tests/test_diagnostic_consistency.py
```

Expected: All tests pass with same fitness values (voxel count unchanged, just interpretation)

## Reference: Unit Conventions Throughout Application

| Component | Z-Axis Unit | Conversion Point |
|-----------|-------------|------------------|
| `env_3d_fixed` | FLOORS | Data loading (NRW ÷ 3.0) |
| `design_3d` | FLOORS | Encoding output |
| `combined_env_3d` | FLOORS | No conversion needed |
| `heightmap_2d` | FLOORS | Encoding output |
| Visualization labels | FLOORS | Add "≈ 3m" note |
| NRW input data | METERS | Convert at load time |

## Date
October 7, 2025 - Complete architectural refactoring to unified floor-based system
