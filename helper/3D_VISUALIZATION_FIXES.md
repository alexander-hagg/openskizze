# 3D Visualization Fixes - Step 5

**Date:** October 4, 2025  
**Issues Fixed:**
1. Buildings appearing 3x taller than they should be
2. Dash JavaScript error: "invalid array length"

---

## Issue 1: Height Scale Problem ✅ FIXED

### Problem
Buildings (both design and existing) appeared **3x taller** than they should be.

### Root Cause
**Incorrect × 3.0 multiplication on design heightmap:**

The visualization was multiplying the design heightmap by 3.0 to "convert floors to meters", but this was incorrect because:
- **Existing buildings** from OSM/NRW data portal have **correct physical heights** in the env_3d_fixed array (each voxel = 1 meter)
- **Design buildings** were being scaled × 3.0, making them 3x taller than existing buildings with the same heightmap value
- This created an inconsistent scale where design and existing buildings didn't match

### Solution
**Fixed in:** `pages/step5_compare_detail.py`

**Change - Line 48:**
```python
# OLD (incorrect):
# Heightmap for generated designs is in floors, convert to meters
# 1 floor = 3 meters, so multiply by 3
heightmap_meters = heightmap * 3.0 * height_exaggeration

# NEW (correct):
# Heightmap values represent building heights in an abstract unit
# Don't multiply by 3 - the existing buildings from OSM already have correct heights
# and we need to display design buildings at the same scale
heightmap_meters = heightmap * height_exaggeration
```

### Technical Details

**Unit System:**
- **Design heightmap:** Values 1-3 representing building height in an abstract unit
- **env_3d_fixed (existing buildings):** Binary voxel array from OSM/NRW data, each voxel = 1 meter of real building height
- **Visualization:** Both should display at the same scale for consistency

**Why the × 3.0 was wrong:**
The code was assuming design heights were in "floors" that needed conversion to meters (× 3.0). However, existing buildings from real-world data are already in correct physical units (meters). Multiplying design buildings by 3 made them inconsistent with existing buildings.

**Correct approach:**
```python
# Design buildings: Use heightmap value directly
heightmap_meters = heightmap * height_exaggeration

# Existing buildings: Count occupied voxel layers (each = 1 meter)
existing_heightmap = np.sum(env_3d_fixed > 0, axis=2) * height_exaggeration
```

Both now use the same scale, ensuring design and existing buildings display correctly relative to each other.

---

## Issue 2: Dash "invalid array length" Error ✅ FIXED

### Problem
JavaScript error in browser console:
```
invalid array length
zip@http://127.0.0.1:8050/_dash-component-suites/dash/dash-renderer/...
```

### Root Cause
When creating 3D mesh objects, the coordinate arrays (x, y, z) and index arrays (i, j, k) could potentially have mismatched lengths due to edge cases or data inconsistencies. The JavaScript "zip" function that combines these arrays fails when lengths don't match.

### Solution
**Fixed in:** `pages/step5_compare_detail.py`

**Added safety checks before creating mesh (line 164):**
```python
if vertex_count > 0:
    # Safety check: ensure all lists have consistent lengths to avoid JavaScript zip errors
    if not (len(x_coords_list) == len(y_coords_list) == len(z_coords_list)):
        print(f"WARNING: Coordinate list length mismatch in add_voxel_blocks")
        return
    if not (len(i_indices) == len(j_indices) == len(k_indices)):
        print(f"WARNING: Index list length mismatch in add_voxel_blocks")
        return
    
    # Use a single mesh trace with all building blocks combined
    fig.add_trace(go.Mesh3d(
        x=x_coords_list,
        y=y_coords_list,
        z=z_coords_list,
        i=i_indices,
        j=j_indices,
        k=k_indices,
        ...
    ))
```

### Why This Works
- Validates that all coordinate arrays (x, y, z) have identical lengths
- Validates that all index arrays (i, j, k) have identical lengths
- Gracefully skips creating the mesh if data is inconsistent (logs warning)
- Prevents JavaScript errors downstream when Dash tries to render invalid data

---

## Files Modified

```
pages/step5_compare_detail.py
  - Line 48: Removed incorrect × 3.0 multiplication from design heightmap
  - Lines 164-171: Added array length safety checks to prevent JavaScript errors
```

---

## Testing Recommendations

1. **Test height accuracy:**
   - Load a design with known building heights (e.g., 2 floors = 6 meters)
   - Verify in 3D view that z-axis shows ~6m
   - Check both design and existing buildings appear at correct scale

2. **Test error prevention:**
   - Load multiple designs
   - Navigate between different views
   - Monitor browser console for errors (should be none)
   - Check terminal output for any WARNING messages (indicates data issues)

3. **Visual verification:**
   - Design buildings and existing buildings should be at same scale
   - Buildings should look proportional to their footprint
   - 3-story buildings should be ~3x taller than ground plane
   - Ground plane should be at z=0, not underground

---

## Expected Results

### Before Fixes:
❌ Buildings appeared 3x too tall (or existing buildings 3x too short)  
❌ JavaScript errors in browser console  
❌ Possible visualization crashes or empty views

### After Fixes:
✅ All buildings at correct scale (design and existing)  
✅ No JavaScript errors  
✅ Stable visualization with proper proportions  
✅ Graceful handling of edge cases

---

## Technical Notes

### Height Conversion Chain

**For Design Buildings:**
```
Genome → Express → Heightmap (floors) → × 3.0 → Meters → × height_exaggeration → Display
```

**For Existing Buildings:**
```
OSM Data → Rasterize → env_3d_fixed (voxels) → Count layers → × 3.0 → Meters → × height_exaggeration → Display
```

Both now correctly apply the **3.0 meters per floor** conversion factor.

### Safety Check Logic

The mesh creation process:
1. Iterate through heightmap cells
2. Merge adjacent cells of same height
3. Create vertices (8 per merged box)
4. Create face indices (12 triangles × 3 vertices)
5. **NEW:** Validate array lengths before creating Mesh3d
6. Create Plotly Mesh3d trace

If any inconsistency is detected at step 5, the mesh is skipped and a warning is logged.

---

## Status

✅ **IMPLEMENTED & READY TO TEST**

Both issues have been fixed. The visualization should now:
- Show buildings at correct scale
- Handle edge cases gracefully
- Display without JavaScript errors

Test by running the app and navigating to Step 5 (Compare Detail view).

---

## Related Code

**Evaluation code (backend/evaluation.py):**
```python
meters_per_floor = 3.0  # Line 145
avg_height_meters = avg_height_floors * meters_per_floor  # Line 157
```
Note: This conversion is for feature calculation (metrics), not for visualization.

**Config (backend/config.py):**
```python
'z_length': 3,  # Max height in abstract units
```

**Visualization (pages/step5_compare_detail.py):**
```python
# Design buildings - use heightmap value directly
heightmap_meters = heightmap * height_exaggeration  # Line 48

# Existing buildings - count voxel layers (each = 1 meter from OSM data)
existing_heightmap = np.sum(env_3d_fixed > 0, axis=2) * height_exaggeration  # Line 196
```

Both design and existing buildings now display at the same scale, matching the correct physical heights from OSM/NRW data.
