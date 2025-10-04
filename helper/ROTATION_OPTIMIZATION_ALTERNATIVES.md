# Rotation Optimization for Arbitrary Wind Directions

## Problem Statement
- Need to support **ANY wind direction** (0-360°), not just 90° increments
- `scipy.ndimage.rotate` is expensive (0.8-2.5ms per call, ~80,000 calls per optimization)
- Current bottleneck: 10-30% of total evaluation time

## Alternative Solutions (All Support Arbitrary Angles)

---

### ✅ **Solution 1: Pre-compute Rotated Environments (RECOMMENDED)**
**Concept**: Rotate the fixed environment ONCE per wind direction, reuse across all evaluations

#### Current (Slow):
```python
# eval_solution() - called 80,000 times
rotated_env = rotate(heightmap_3d, angle=rotation_angle, ...)  # EXPENSIVE
```

#### Optimized (Fast):
```python
# ONCE per optimization (wind direction doesn't change during optimization)
env_config['env_3d_rotated'] = rotate(env_config['env_3d_fixed'], angle=rotation_angle, ...)

# eval_solution() - called 80,000 times  
# Just rotate the SMALL design, not the large environment
rotated_design = rotate(design_3d, angle=rotation_angle, ...)  # Much smaller array
combined = np.maximum(env_config['env_3d_rotated'], rotated_design)
```

**Performance Impact:**
- Environment rotation: 1 time instead of 80,000 times
- Design rotation: Still 80,000 times, but MUCH smaller array (design < 10% of environment typically)
- **Expected speedup: 5-15x** for rotation step (design is much sparser than full environment)

**Pros:**
✅ Supports ANY wind direction
✅ Massive speedup (rotate small array instead of large)
✅ No accuracy loss
✅ Simple to implement
✅ Low risk

**Cons:**
⚠️ Slightly more memory (one extra rotated environment copy)

---

### ✅ **Solution 2: Rotate in 2D Instead of 3D**
**Concept**: Work with 2D heightmaps, only create 3D for final fitness calculation

#### Current:
```python
# Create 3D mesh (32×32×30)
design_3d = (z_indices < heightmap_2d[..., np.newaxis]).astype(np.int8)
combined_3d = np.maximum(env_3d_fixed, design_3d)

# Rotate 3D (EXPENSIVE)
rotated_3d = rotate(combined_3d, angle=rotation_angle, axes=(0,1), ...)
```

#### Optimized:
```python
# Rotate 2D heightmaps (32×32 instead of 32×32×30)
rotated_heightmap_env = rotate(heightmap_2d_env, angle=rotation_angle, order=1)
rotated_heightmap_design = rotate(heightmap_2d_design, angle=rotation_angle, order=1)

# Combine in 2D
combined_heightmap = np.maximum(rotated_heightmap_env, rotated_heightmap_design)

# Create 3D ONCE from rotated 2D
combined_3d = (z_indices < combined_heightmap[..., np.newaxis]).astype(np.int8)
```

**Performance Impact:**
- Rotate 2D (1024 elements) instead of 3D (30,720 elements) = **30x less data**
- **Expected speedup: 10-20x** for rotation step

**Pros:**
✅ Supports ANY wind direction
✅ Massive speedup (30x less data to rotate)
✅ More memory efficient
✅ Maintains accuracy (heightmap representation is exact)

**Cons:**
⚠️ Requires refactoring fitness functions to work with 2D→3D workflow
⚠️ Need to ensure interpolation doesn't create artifacts (use order=1 for heightmaps)

---

### ✅ **Solution 3: Ray-Casting Instead of Rotation**
**Concept**: Calculate wind flow without rotating - cast rays in wind direction

#### Implementation:
```python
def compute_fitness_raycast(heightmap_3d, wind_direction):
    """
    No rotation needed - cast rays directly in wind direction.
    """
    rows, cols, height = heightmap_3d.shape
    
    # Convert wind direction to ray direction vector
    angle_rad = np.deg2rad(wind_direction)
    dx = np.cos(angle_rad)
    dy = np.sin(angle_rad)
    
    # For each column in wind direction, trace ray
    # Count penetration without rotating the array
    # Use line-drawing algorithm (Bresenham) or interpolation
    
    penetration_scores = []
    for start_y in range(rows):
        for start_x in range(cols):
            # Trace ray from (start_x, start_y) in direction (dx, dy)
            ray_path = trace_ray(heightmap_3d, start_x, start_y, dx, dy)
            penetration_scores.append(calculate_penetration(ray_path))
    
    return np.mean(penetration_scores)
```

**Performance Impact:**
- No rotation at all
- Ray-tracing overhead depends on implementation
- **Expected speedup: 3-10x** (eliminate rotation entirely)

**Pros:**
✅ Supports ANY wind direction (continuous angles)
✅ No rotation needed
✅ Physically more accurate (actual ray paths)
✅ Can add more sophisticated wind physics

**Cons:**
⚠️ Requires complete rewrite of fitness functions
⚠️ Ray-tracing implementation complexity
⚠️ May be slower if not optimized well
⚠️ Changes fitness landscape (results will differ)

---

### ✅ **Solution 4: Analytical Projection (Fastest)**
**Concept**: Use analytical geometry to project wind flow without rotation

#### Implementation:
```python
def compute_fitness_projection(heightmap_3d, wind_direction):
    """
    Project wind flow using coordinate transformation.
    No array rotation - just coordinate math.
    """
    angle_rad = np.deg2rad(wind_direction)
    
    # Create coordinate grids
    x_grid, y_grid = np.meshgrid(np.arange(cols), np.arange(rows))
    
    # Rotate coordinates (cheap) instead of rotating array (expensive)
    x_rot = x_grid * np.cos(angle_rad) - y_grid * np.sin(angle_rad)
    y_rot = x_grid * np.sin(angle_rad) + y_grid * np.cos(angle_rad)
    
    # Sample heightmap along rotated coordinates
    # Use np.interp or scipy.interpolate.RegularGridInterpolator
    from scipy.interpolate import RegularGridInterpolator
    interp = RegularGridInterpolator((np.arange(rows), np.arange(cols)), 
                                      heightmap_2d, 
                                      method='linear')
    
    # Project along wind direction
    projection = calculate_wind_projection(heightmap_3d, x_rot, y_rot)
    
    return projection_to_fitness(projection)
```

**Performance Impact:**
- Coordinate transformation is very cheap (just arithmetic)
- Interpolation is cheaper than full rotation
- **Expected speedup: 5-20x**

**Pros:**
✅ Supports ANY wind direction
✅ Very fast (coordinate math instead of data movement)
✅ Flexible (can add more complex wind models)

**Cons:**
⚠️ Requires mathematical restructuring
⚠️ Interpolation artifacts possible
⚠️ Complex to implement correctly

---

## Recommended Implementation: **Solution 1 + Solution 2 Hybrid**

### Strategy: Minimal Changes, Maximum Impact

```python
def prepare_rotated_environment(env_config, wind_direction):
    """
    Called ONCE at start of optimization.
    Pre-rotate the fixed environment.
    """
    rotation_angle = (wind_direction + 90) % 360
    
    # Rotate 2D heightmap of environment (CHEAP - only 2D)
    env_heightmap_2d = env_config['heightmap_2d_fixed']  # 32×32
    env_heightmap_rotated = rotate(env_heightmap_2d, 
                                    angle=rotation_angle, 
                                    axes=(0, 1), 
                                    reshape=False, 
                                    order=1)
    
    env_config['heightmap_2d_rotated'] = env_heightmap_rotated
    return env_config


def compute_fitness_optimized(design_heightmap_2d, env_config, wind_direction):
    """
    Called 80,000 times - optimized version.
    """
    rotation_angle = (wind_direction + 90) % 360
    
    # Rotate SMALL 2D design heightmap (CHEAP)
    design_rotated = rotate(design_heightmap_2d, 
                           angle=rotation_angle, 
                           axes=(0, 1), 
                           reshape=False, 
                           order=1)
    
    # Combine rotated heightmaps in 2D (CHEAP)
    env_rotated = env_config['heightmap_2d_rotated']
    combined_heightmap = np.maximum(env_rotated, design_rotated)
    
    # Create 3D from combined heightmap (CHEAP)
    z_indices = np.arange(env_config['max_height'])
    combined_3d = (z_indices < combined_heightmap[..., np.newaxis]).astype(np.int8)
    
    # Calculate fitness from 3D (same as before)
    projection = np.sum(combined_3d, axis=1)
    # ... rest of fitness calculation
```

### Performance Comparison

| Approach | Rotations per Optimization | Data Size | Expected Speedup |
|----------|---------------------------|-----------|------------------|
| **Current** | 80,000 × 3D (32×32×30) | 30,720 elements | 1x (baseline) |
| **Solution 1 (Pre-rotate env)** | 1 × 3D env + 80,000 × 3D design | ~3,000 elements avg | 5-10x |
| **Solution 2 (2D rotation)** | 80,000 × 2D (32×32) | 1,024 elements | 10-20x |
| **Solution 1+2 (Hybrid)** | 1 × 2D env + 80,000 × 2D design | ~100 elements avg | **15-30x** ⚡ |

### Implementation Steps

1. **Modify env_config preparation** (in optimizer.py or evaluation.py):
   - Add 2D heightmap extraction from env_3d_fixed
   - Pre-rotate environment heightmap once
   
2. **Modify eval_solution()**:
   - Accept design as 2D heightmap (already have this)
   - Rotate 2D design instead of 3D
   - Combine in 2D, then create 3D
   
3. **Update fitness functions**:
   - Accept combined heightmap OR combined 3D
   - If needed, create 3D inside fitness function

### Expected Results

**Before:**
- Rotation time: 0.8-2.5 ms per evaluation
- 80,000 evaluations: 64-200 seconds in rotation alone
- **10-30% of total time**

**After:**
- Rotation time: 0.05-0.15 ms per evaluation (2D design only)
- 80,000 evaluations: 4-12 seconds in rotation
- **<2% of total time**

**Total speedup: 1.5-2.5x overall** (rotation goes from 20% → 2% of time)

---

## Next Steps

1. ✅ Implement hybrid approach (Solution 1+2)
2. ✅ Benchmark with real optimization run
3. ✅ Validate fitness values match (within numerical precision)
4. ✅ Test with various wind directions (0°, 45°, 90°, 135°, etc.)

This approach maintains **full flexibility** for any wind direction while achieving **15-30x rotation speedup** and **1.5-2.5x overall optimization speedup**.
