# Sky View Factor (SVF) Implementation

## Overview
Implemented proper Sky View Factor calculation for the planning-focused feature set. SVF represents the fraction of the sky hemisphere visible from ground level and is crucial for:
- **Urban heat island assessment** (lower SVF = more heat retention)
- **Thermal comfort analysis**
- **Solar access evaluation**
- **Night-time cooling potential**

## Implementation Details

### Algorithm: Optimized Ray-Casting with Hemisphere Sampling

**Location:** `backend/evaluation.py` - `calculate_sky_view_factor()`

**Method:**
1. **Hemisphere Sampling**: Generate uniformly distributed ray directions covering the sky hemisphere
   - 4 elevation rings (15°, 35°, 55°, 75°)
   - Avoids horizon noise (low elevation) and zenith edge cases (90°)
   - Each ring has equal number of azimuth samples (0° to 360°)
   - Total: 16 rays by default (configurable)

2. **Ground Point Sampling**: Sample observer locations on unoccupied ground
   - Default stride: every 5th pixel (reduces computation by 96%)
   - Only samples ground points (heightmap value = 0)
   - Observer eye level: 1.5m above ground

3. **Ray Traversal**: Cast rays from each observer point
   - Pixel-by-pixel grid traversal (not sub-pixel for performance)
   - Check intersection with buildings along ray path
   - Early termination when ray is well above max building height
   - Maximum 50 steps per ray (sufficient for typical grids)

4. **Solid Angle Weighting**: Weight each ray by cos(elevation)
   - Accounts for varying solid angles at different elevations
   - Ensures physically accurate hemisphere integration

5. **Aggregation**: Average SVF across all sampled ground points

### Performance Optimizations

1. **Reduced ray count**: 16 rays (vs initial 32) - minimal accuracy loss
2. **Increased stride**: every 5th pixel (vs initial 3rd) - 2.8× speedup
3. **Pixel-level traversal**: Full pixel steps instead of sub-pixel marching
4. **Early termination**: Stop ray once well above all buildings
5. **Pre-cached max height**: Avoids repeated np.max() calls
6. **Limited steps**: Max 50 steps per ray regardless of grid size

**Performance Results:**
- 20×20 grid: ~4ms
- 30×30 grid: ~5-9ms
- 50×50 grid: ~25ms

Target: <10ms for typical 30×30 grids during optimization ✓

### Parameters

```python
calculate_sky_view_factor(
    heightmap: np.ndarray,      # 2D building heights in meters
    pixel_size: float = 3.0,    # Pixel size in meters
    num_rays: int = 16,         # Number of ray directions
    sample_stride: int = 5      # Sample every Nth pixel
)
```

**Tuning Trade-offs:**
- **num_rays**: Higher = more accurate but slower (16 provides good balance)
- **sample_stride**: Lower = more accurate but slower (5 provides 96% speedup)

## Test Results

### Test Cases (from `tests/test_features_visual.py`)

| Test Case | SVF Value | Expected Range | Status | Time |
|-----------|-----------|----------------|--------|------|
| Empty space | 1.000 | 1.000 | ✓ PASS | <1ms |
| Single building (30m) | 0.968 | 0.92-0.98 | ✓ PASS | 9ms |
| Street canyon (18m) | 0.867 | 0.80-0.90 | ✓ PASS | 5ms |
| Dense urban (9 buildings) | 0.855 | 0.80-0.90 | ✓ PASS | 3ms |
| Performance (50×50 grid) | 0.929 | N/A | ✓ PASS | 25ms |

### Interpretation of Results

**Why SVF values are relatively high (0.85-0.97):**
- Test grids are small (20×30 pixels) with limited building coverage
- Most ground points have clear view to sky in multiple directions
- Open-ended street canyons allow sky visibility at ends
- Grid pattern with gaps between buildings increases sky access
- This is physically realistic for the test geometries

**Real urban environments:**
- Dense city centers: SVF = 0.3-0.6 (tall buildings, narrow streets)
- Typical urban areas: SVF = 0.6-0.8 (mixed heights, moderate spacing)
- Suburban areas: SVF = 0.8-0.95 (low buildings, wide spacing)
- Open spaces: SVF = 0.95-1.0 (minimal obstruction)

## Integration

### Usage in Feature Calculation

The SVF is calculated as feature [7] in the planning-focused feature set:

```python
def calculate_all_features_planning(heightmap, buildable_mask, buildable_area):
    # ... other features ...
    
    # [7] Sky View Factor (0-1 scale)
    pixel_size = get_pixel_size_meters(heightmap, buildable_area)
    svf = calculate_sky_view_factor(heightmap, pixel_size)
    
    return np.array([grz, gfz, avg_height, height_var, num_buildings, 
                     avg_distance, hw_ratio, svf])
```

### Feature Set Selection

Users can select between feature sets in the GUI (Step 2: Constraints):
- **Original features**: Built area, height, GFA, etc. (no SVF)
- **Planning features**: GRZ, GFZ, H/W ratio, **SVF**, etc.

The selected feature set is stored in session data and used throughout the optimization pipeline.

## Validation

Visual tests confirm:
1. ✓ Empty space returns SVF = 1.0
2. ✓ Single building produces high SVF (minimal obstruction)
3. ✓ Street canyon produces moderate SVF (side obstruction)
4. ✓ Dense urban produces lower SVF (more obstruction)
5. ✓ Performance meets requirements (<10ms for typical grids)
6. ✓ All test visualizations saved to `debug_plots/feature_test_svf_calculation.png`

## Future Enhancements (Optional)

If further optimization is needed:
1. **Numba JIT compilation**: Could provide 5-10× speedup
2. **Adaptive ray count**: Fewer rays for simple geometries
3. **Caching**: Pre-compute ray directions once globally
4. **Vectorization**: Process multiple sample points in parallel
5. **GPU acceleration**: For very large grids (>100×100)

However, current performance (3-25ms) is sufficient for QD optimization which requires thousands of evaluations.

## References

- Watson & Johnson (1987): "Graphical estimation of sky view-factors in urban environments"
- Oke (1988): "Street design and urban canopy layer climate"
- Chen et al. (2012): "Sky view factor analysis of street canyons and its implications for daytime intra-urban air temperature differentials"
- Unger (2009): "Connection between urban heat island and sky view factor"
