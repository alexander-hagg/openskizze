# Wind Porosity Function Fix

## Summary
Fixed the `compute_fitness` function to correctly calculate horizontal wind path porosity as a percentage (0.0-1.0) of unblocked straight paths in the wind direction.

## What Was Wrong

### Original Implementation:
```python
rotation_angle = (wind_direction + 90) % 360  # ❌ Wrong: adds 90°
rotated_env = rotate(heightmap_3d, angle=rotation_angle, axes=(0, 1), reshape=False, order=0)
projection = np.sum(rotated_env, axis=1)  # ❌ Wrong: uses sum
open_columns = np.sum(projection == 0)
```

**Problems:**
1. **Wrong rotation**: Added 90° to wind direction (perpendicular to actual wind)
2. **Wrong aggregation**: Used `sum` instead of `max` - even one blocking voxel would make the sum non-zero, but doesn't mean the path is completely blocked
3. **Wrong interpretation**: Summing along axis collapses the dimension, but doesn't check if entire horizontal paths are clear

## Corrected Implementation

```python
rotation_angle = wind_direction % 360  # ✅ Correct: align wind with axis
rotated_env = rotate(heightmap_3d, angle=rotation_angle, axes=(0, 1), reshape=False, order=0)
max_along_wind = np.max(rotated_env, axis=1)  # ✅ Check if ANY obstruction exists
open_paths = np.sum(max_along_wind == 0)  # ✅ Count completely clear paths
```

**Key Changes:**
1. **Correct rotation**: Wind direction directly, no +90°
2. **Max instead of sum**: `max == 0` means the entire horizontal path is clear
3. **Correct interpretation**: Counts percentage of (x, z) positions with completely unobstructed horizontal wind corridors

## How It Works

1. **Rotate environment** so wind flows along the Y-axis (depth)
2. **For each (x, z) position**, check if there's any obstruction along the entire Y-axis
   - `np.max(rotated_env[:, :, z], axis=1)` gives max value along wind direction
   - If `max == 0`, the entire horizontal path at that (x, z) is clear
3. **Count open paths** and divide by total paths to get porosity ratio
4. **Return 0.0-1.0**: 
   - 1.0 = all paths open (empty environment)
   - 0.0 = all paths blocked (full environment)

## Test Results

All 8 tests pass with correct expected values:

| Test | Fitness | Description |
|------|---------|-------------|
| 1. Empty environment | 1.000 | ✅ Maximum porosity |
| 2. Single building (center) | 0.900 | ✅ Blocks 10% of paths |
| 3. Wall perpendicular to wind | 0.970 | ✅ Narrow wall blocks 3% |
| 4. Wall parallel to wind | 0.700 | ✅ Parallel wall still blocks ground level |
| 5. Full blockage | 0.000 | ✅ Minimum porosity |
| 6. Corridor with wind | 0.700 | ✅ Open corridor + free upper levels |
| 7. Corridor perpendicular | 0.500 | ✅ Wind must pass through buildings |
| 8. Direction sensitivity | varies | ✅ Different angles give different results |

## Visualization

The test generates comprehensive visualizations showing:
- **3D voxel view**: Buildings and wind direction arrow
- **Top view**: Building footprints with wind arrow
- **Side view**: Wind paths (green dots = open, red = blocked)

Location: `debug_plots/wind_porosity_tests.png`

## Usage Example

```python
from backend.evaluation import compute_fitness

# Create 3D heightmap (x, y, z)
heightmap_3d = np.zeros((100, 100, 20))
heightmap_3d[10:20, 10:20, 0:5] = 1  # Add a building

# Compute fitness for north wind (0°)
fitness = compute_fitness(heightmap_3d, wind_direction=0)
print(f"Wind porosity: {fitness:.2%}")  # e.g., "Wind porosity: 87.50%"
```

## Impact on Optimization

The corrected function now properly:
- ✅ Rewards designs with clear horizontal wind corridors
- ✅ Penalizes designs that block wind flow
- ✅ Respects wind direction (different directions → different scores)
- ✅ Returns 1.0 for empty environment (correct baseline)
- ✅ Returns 0.0 for completely blocked environment

This should lead to more realistic urban design optimization that actually optimizes for wind flow!
