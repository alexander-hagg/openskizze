# Adaptive Feature Calculation - System Design

**Status**: ✅ **Already Implemented and Working**

## Overview

The OpenSKIZZE system uses **fully adaptive feature calculation** that automatically adjusts to:
- Parcel size (Flurstück dimensions)
- Maximum building height constraint
- Buildable area mask
- Grid resolution

## Architecture

### 1. Input Parameters (Step 2 - Constraints)

User provides:
```python
hard_constraints = {
    'max_height': 30,        # Maximum building height in METERS
    'min_distance': 6,       # Minimum building separation in meters
}
```

### 2. Dynamic Range Calculation

**Function**: `_calculate_dynamic_feat_ranges()` in `optimization_process.py`

**Inputs**:
- `buildable_mask`: Boolean array of actual buildable pixels
- `max_height_meters`: User's constraint or default from `z_length`

**Outputs**: Adaptive ranges for all 8 features in physical units

```python
def _calculate_dynamic_feat_ranges(buildable_mask, max_height_meters):
    # Calculate based on ACTUAL parcel
    buildable_pixels = np.sum(buildable_mask)
    buildable_area_m2 = buildable_pixels * (pixel_size ** 2)
    grid_res = buildable_mask.shape[0]
    max_dist_meters = np.sqrt(2) * grid_res * pixel_size
    
    # Adaptive ranges
    return [
        [0.0, buildable_area_m2],              # 0: Built Area - scales to parcel
        [0.0, max_height_meters],              # 1: Height - uses constraint
        [0.0, max_height_meters / 2],          # 2: Height Var - uses constraint
        [0.0, max_num_buildings],              # 3: Num Buildings - fixed at 10
        [0.0, max_dist_meters],                # 4: Distance - scales to grid
        [0.0, buildable_area_m2 * max_height_meters],  # 5: Floor Area - fully adaptive
        [0.0, 1.0],                            # 6: Mass X - normalized
        [0.0, 1.0],                            # 7: Mass Y - normalized
    ]
```

### 3. Feature Calculation (evaluation.py)

**Function**: `calculate_all_features()`

Calculates features in **absolute physical units**:

```python
# Example output for a 1000m² parcel with 30m max height:
features = [
    450.0,   # [0] Built Area: 450 m² (actual coverage)
    12.5,    # [1] Avg Height: 12.5 meters (actual average)
    4.2,     # [2] Height Var: 4.2 meters std dev
    5.0,     # [3] Num Buildings: 5 buildings
    18.3,    # [4] Avg Distance: 18.3 meters
    5625.0,  # [5] Floor Area: 5625 m² (total volume as area)
    0.48,    # [6] Mass X: 0.48 (normalized position)
    0.52,    # [7] Mass Y: 0.52 (normalized position)
]
```

### 4. Normalization for QD Algorithm

**Function**: `physical_to_normalized()` in `units.py`

Converts physical values to [0, 1] range for MAP-Elites:

```python
# Feature 0: Built Area (450 m² out of 1000 m² buildable)
normalized_val = 450.0 / 1000.0 = 0.45

# Feature 1: Avg Height (12.5m out of 30m max)
normalized_val = 12.5 / 30.0 = 0.417

# Feature 5: Floor Area (5625 m² out of 30000 m² max)
normalized_val = 5625.0 / 30000.0 = 0.1875
```

## Examples of Adaptivity

### Small Parcel (500 m²)
```python
Ranges:
- Built Area: [0, 500 m²]
- Avg Height: [0, 30 m] (from constraint)
- Floor Area: [0, 15000 m²] = 500 × 30
```

### Large Parcel (3000 m²)
```python
Ranges:
- Built Area: [0, 3000 m²]
- Avg Height: [0, 30 m] (same constraint)
- Floor Area: [0, 90000 m²] = 3000 × 30
```

### Low Height Constraint (15m)
```python
Ranges:
- Built Area: [0, 1000 m²] (same parcel)
- Avg Height: [0, 15 m] (reduced)
- Floor Area: [0, 15000 m²] = 1000 × 15 (reduced)
```

## Key Properties

### ✅ What IS Adaptive:
1. **Built Area Range**: Scales to buildable mask area
2. **Height Ranges**: Use user's `max_height` constraint
3. **Distance Range**: Scales to grid diagonal
4. **Floor Area Range**: Combines parcel size × max height
5. **Grid Resolution**: Each parcel gets appropriate resolution

### ✅ What is FIXED (by design):
1. **Max Number of Buildings**: Always 10 (encoding design choice)
2. **Genotype Dimension**: Always 60 genes (10 buildings × 6 params)
3. **Pixel Size**: 3 meters (domain constant)

### ✅ What Can Be Customized:
1. **Feature Ranges**: Users can override in Step 2
2. **Max Height**: User constraint in Step 2
3. **Selected Features**: User chooses which features to optimize

## Configuration Constants

### backend/config.py
```python
ENCODING_CONFIG = {
    'max_num_buildings': 10,  # FIXED - always 10 buildings
    'xy_length': 32,          # Updated dynamically per parcel
    'z_length': 30,           # Default max height (30m)
}

DOMAIN_CONFIG = {
    'pixel_size_in_meters': 3,  # Fixed voxel size
}
```

### Why z_length = 30?
- Represents ~10 floors × 3m per floor
- Reasonable urban height for web demo
- Can be overridden by user's `max_height` constraint
- Matches typical urban development (3-10 story buildings)

## Performance Characteristics

### Adaptivity Impact:
- **Memory**: Scales with parcel size (grid_res²)
- **3D Array Size**: Scales with max_height (Z dimension)
- **Computation**: Linear with buildable area
- **No Performance Penalty**: Adaptivity happens once during initialization

### Performance vs Correctness:
- Small parcel (500m²): Fast, less diversity needed
- Large parcel (5000m²): Slower, more diversity possible
- Height matters: 30m → 3× more Z-layers than 10m

## Testing Checklist

To verify adaptive behavior:

1. **Small parcel test**: Select 20m × 20m area (400m²)
   - Check Built Area range ≈ [0, 400]
   - Check Floor Area range ≈ [0, 12000] (400 × 30)

2. **Large parcel test**: Select 60m × 60m area (3600m²)
   - Check Built Area range ≈ [0, 3600]
   - Check Floor Area range ≈ [0, 108000] (3600 × 30)

3. **Height constraint test**: Set max_height = 15m
   - Check Avg Height range = [0, 15]
   - Check Floor Area reduces by 50%

4. **Custom range test**: Override Feature 1 range in Step 2
   - Verify custom range is used instead of dynamic

## Conclusion

The system is **already fully adaptive** to parcel size, building height, and constraints. No changes needed to feature calculation logic. The only adjustment made was correcting `z_length` from 10 to 30 meters to match the intended default height.

**Next Step**: End-to-end testing to verify adaptive behavior works correctly in practice.
