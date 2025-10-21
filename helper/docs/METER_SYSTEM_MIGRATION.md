# Complete Migration to Meter-Based System

**Date**: 2025
**Issue**: Buildings displayed 3× too tall in visualizations due to mixed floor/meter units
**Solution**: Standardized entire application to use meters throughout

## Problem Summary

The application was using a confusing "unified floor system" where:
- LOD2 data came in meters, got divided by 3 to convert to "floors"
- Encoding produced heights in "floors" (1-4)
- Evaluation converted back to meters by multiplying by 3
- Visualization multiplied by 3 again for display
- Result: Buildings appeared 3× too tall

## Solution

**Single Unit System: METERS EVERYWHERE**

### Key Principle
> "Measure in meters, store in meters, calculate in meters, display in meters"

## Changes Made

### 1. **backend/config.py**
- Changed `z_length: 3` → `z_length: 30`
- Updated comment: "Max height in METERS (default 30m)"

### 2. **backend/encoding.py** (Line 86)
```python
# OLD: h = (genes * 3).astype(int) + 1  # 1-4 floors
# NEW: h = (genes * 30).astype(int) + 3  # 3-33 meters
```
- Encoding now outputs meter values directly
- Building heights range from 3m to 33m

### 3. **backend/data_io.py**
#### LOD2 Data Loading (Lines 508-570)
```python
# OLD: heights_floors = measuredHeight / 3.0
# NEW: heights_meters = measuredHeight  # Keep in meters
```
- Removed all ÷3.0 conversions
- 3D voxel arrays: 1 voxel = 1 meter (not 1 floor)
- Height clipping: 3.0-90.0 meters (not 1.0-30.0 floors)

#### Fetch Function (Line 399)
```python
# OLD: max_height_floors parameter
# NEW: max_height_meters parameter
```

### 4. **backend/evaluation.py** (Lines 151-169, 217-225)
```python
# OLD: avg_height_meters = avg_height_floors * 3.0
# NEW: avg_height_meters = np.mean(building_heights)  # Already meters
```
- Removed `meters_per_floor = 3.0` constant
- Height features calculated directly without conversion
- Updated all comments: "heightmap is already in METERS"

### 5. **backend/units.py**
#### Physical to Normalized (Lines 40-64)
```python
# OLD: physical_values[i] = val * meters_per_floor
# NEW: physical_values[i] = val  # Already in meters
```
- Features 1 & 2 (height, variability) pass through without conversion
- Normalization now divides by `max_height_meters` instead of converting

#### Dynamic Range Calculation (Lines 197-234)
```python
# OLD: max_height_floors parameter
# NEW: max_height_meters parameter
```
- Removed floor-to-meter conversions
- Ranges calculated directly in meters

### 6. **backend/optimization_process.py**
#### Constraint Handling (Line 293)
```python
# OLD: max_height_voxels = hard_constraints.get('max_height', z_length * 3)
#      max_height_floors = max_height_voxels // 3
# NEW: max_height_meters = hard_constraints.get('max_height', z_length)
```

#### Dynamic Range Function (Line 358)
```python
# OLD: _calculate_dynamic_feat_ranges(mask, max_height_floors)
# NEW: _calculate_dynamic_feat_ranges(mask, max_height_meters)
```

#### Fallback Building Data (Lines 160-240)
```python
# OLD: heights_floors = hoehe / 3.0  # Convert meters to floors
# NEW: heights_meters = hoehe  # Keep in meters
```
- When LOD2 data unavailable, fallback assumes 9m (not 3 floors)
- Floor counts converted to meters: `geschosszahl * 3.0`
- All 3D arrays use meter-based voxels

### 7. **Visualization Comments**
- Updated `pages/step5_compare_detail.py`: "Heightmap values are already in METERS"
- Updated `backend/debugging_plots.py`: "ALL Z-axes are now in METERS"

## Verification Checklist

✅ **Data Input**: LOD2 measuredHeight kept in meters
✅ **Encoding**: Genotype to phenotype produces meters (3-33m)
✅ **Evaluation**: Features calculated directly in meters
✅ **Constraints**: Max height handled in meters
✅ **3D Arrays**: 1 voxel = 1 meter consistently
✅ **Visualization**: Heights displayed in meters
✅ **No Conversions**: All ×3.0 and ÷3.0 operations removed

## Testing

### Expected Behavior
1. **Step 1**: Existing buildings show correct heights from LOD2
2. **Step 5**: Generated designs show 3-33 meter buildings
3. **Comparison**: Existing buildings and new designs at same scale
4. **3D View**: Heights match real-world expectations

### Visual Check
- 3-story building = ~9 meters
- 10-story building = ~30 meters
- No buildings should appear 3× too tall

## Impact on Constraints

The `max_height` constraint in Step 2 now expects **meters** not floors:
- Old: `max_height: 10` meant 10 floors = 30m
- New: `max_height: 30` means 30 meters

**Backwards Compatibility**: None needed - users set constraints in UI which uses meters

## Files Modified

1. `backend/config.py` - z_length: 3 → 30
2. `backend/encoding.py` - Height gene output in meters
3. `backend/data_io.py` - LOD2 data kept in meters
4. `backend/evaluation.py` - Feature calculations in meters
5. `backend/units.py` - Removed floor conversions
6. `backend/optimization_process.py` - Constraints and fallback in meters
7. `pages/step5_compare_detail.py` - Updated comments
8. `backend/debugging_plots.py` - Updated comments

## Performance Impact

**Neutral**: No performance change, just different numerical values

## Migration Notes

- No database migrations needed
- No cached data format changes
- UI already used meters for display
- Only internal representation changed

## Success Criteria

✅ All compilation errors resolved
✅ No undefined variable references
✅ All unit conversions removed
✅ Consistent meter system throughout
✅ Ready for end-to-end testing

## Next Steps

1. Test complete workflow Step 1 → Step 5
2. Verify 3D visualization shows correct scales
3. Compare existing buildings vs new designs visually
4. Ensure constraints still work correctly
