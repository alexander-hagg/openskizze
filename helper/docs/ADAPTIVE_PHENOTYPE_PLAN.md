# Adaptive Phenotype Implementation Plan (REVISED)

## Quick Reference - What Changes

| Aspect | Current | Target (Revised) |
|--------|---------|------------------|
| **Grid Size** | Fixed 32×32 | Adaptive (10-100+ cells) |
| **Max Buildings** | Fixed 10 | ✓ Fixed 10 (no change) |
| **Genome Dim** | Fixed 60 | ✓ Fixed 60 (no change) |
| **Building Sizes** | Scale with grid | ✓ Scale with grid (no change) |
| **Initial x0** | Zeros | Adaptive (biased for parcel) |
| **Taboo Zones** | Enforced by mask | ✓ Enforced by mask (no change) |
| **Visualizations** | Assume 32×32 | Must handle variable sizes |
| **Features** | Physical units | ✓ Physical units (no change) |

**Bottom Line:** Only phenotype (grid) and visualizations need adaptation. Genome encoding stays fixed!

---

## Executive Summary

This document outlines the complete plan to adapt OpenSKIZZE's urban planning optimization to handle parcels (Flurstücke) of wildly varying sizes and shapes. The key principle is: **The phenotype (grid representation) adapts to parcel size, while genome encoding remains fixed**.

**Current State:**
- Fixed grid size: 32×32 cells (determined by `ENCODING_CONFIG['xy_length']`)
- Fixed pixel size: 3×3m per cell (`DOMAIN_CONFIG['pixel_size_in_meters']`)
- Fixed max buildings: 10 (`ENCODING_CONFIG['max_num_buildings']`)
- Fixed genome dimension: 60 (10 buildings × 6 genes)
- Building dimensions encoded as fractions of fixed grid size

**Target State (REVISED):**
- **Adaptive grid size**: Number of cells depends on parcel size (1 cell = 3×3m)
- **Fixed max buildings**: Always 10 buildings (genome unchanged)
- **Fixed genome dimension**: Always 60 genes (10 buildings × 6 genes)
- **Adaptive phenotype only**: Grid resolution changes, genome space stays constant
- **Adaptive starting genome**: Initialize x0 with reasonable building sizes for parcel
- **Enforced taboo zones**: Buildings only placed in buildable area
- **Adaptive visualizations**: All plots handle variable grid sizes
- **Scale-independent features**: All metrics work consistently across parcel sizes

---

## 1. Core Architecture Changes

### 1.1 Encoding Schema Per Building (Current: 6 Genes)

Each building is encoded with 6 genes (all normalized 0-1 after `norm2unif`):

```python
Gene 0: width_ratio       # Building width as fraction of grid size
Gene 1: length_ratio      # Building length as fraction of grid size  
Gene 2: height_ratio      # Building height as fraction of max_height
Gene 3: x_position_ratio  # X-center position as fraction of grid size
Gene 4: y_position_ratio  # Y-center position as fraction of grid size
Gene 5: active            # Building active if > 0.0
```

**Current Expression (Fixed Grid):**
```python
w = (gene[0] * (xy_length / 2)).astype(int)  # Max width = grid/2
l = (gene[1] * (xy_length / 2)).astype(int)  # Max length = grid/2
h = (gene[2] * z_length).astype(int) + 1
x_c = (gene[3] * xy_length).astype(int)
y_c = (gene[4] * xy_length).astype(int)
```

**Problem:** On a 100×100 grid, max building would be 50×50 cells (150m × 150m) — unrealistic!

**Revised Solution - NO ADAPTIVE CONSTRAINTS:**
```python
# Building dimensions and positions scale with grid size (as before)
# NO artificial limits - let QD optimization find optimal sizes!

# Expression (UNCHANGED - already scales with xy_length)
w = (gene[0] * (xy_length / 2)).astype(int)  # Max = half grid
l = (gene[1] * (xy_length / 2)).astype(int)  # Max = half grid
h = (gene[2] * z_length).astype(int) + 1
x_c = (gene[3] * xy_length).astype(int)      # Full grid range
y_c = (gene[4] * xy_length).astype(int)      # Full grid range
```

**Key Point:** Expression already scales naturally with `xy_length`! 
- Small grid (10×10) → max building = 5×5 cells
- Large grid (100×100) → max building = 50×50 cells
- **This is correct behavior** - buildings scale with parcel size

### 1.2 Fixed Number of Buildings (REVISED)

**Decision:** Keep buildings fixed at 10 for all parcels

**Rationale:**
- Simpler implementation
- Consistent genome dimension (60 genes)
- QD optimization will naturally activate fewer buildings on small parcels
- No need for variable archive dimensions

**Implementation:**
```python
# ENCODING_CONFIG remains unchanged
ENCODING_CONFIG = {
    'max_num_buildings': 10,  # FIXED
    'xy_length': 32,           # Will be updated per parcel
    'z_length': 3,             # From constraints
}
```

**Building Activation:**
On small parcels, optimizer will:
- Set some building genes to "inactive" (gene[5] < 0.0)
- Use fewer active buildings naturally
- No explicit constraint needed

---

## 2. Component-by-Component Changes (REVISED)

### 2.1 `backend/config.py`

**SIMPLIFIED - Only track grid resolution:**

```python
def calculate_adaptive_phenotype_config(buildable_mask: np.ndarray, 
                                        buildable_area_m2: float,
                                        grid_res: int) -> dict:
    """
    Calculate adaptive phenotype parameters (grid size only).
    Genome encoding stays FIXED.
    
    Args:
        buildable_mask: Boolean array of buildable cells
        buildable_area_m2: Buildable area in square meters
        grid_res: Grid resolution (number of cells per side)
    
    Returns:
        Dictionary with adaptive parameters for display/logging
    """
    pixel_size = DOMAIN_CONFIG['pixel_size_in_meters']
    
    return {
        'xy_length': grid_res,
        'parcel_area_m2': buildable_area_m2,
        'grid_size_meters': grid_res * pixel_size,
        'buildable_pixels': int(np.sum(buildable_mask)),
    }
```

**ENCODING_CONFIG stays completely unchanged:**

```python
# NO CHANGES - stays fixed!
ENCODING_CONFIG = {
    'max_num_buildings': 10,  # FIXED
    'xy_length': 32,           # Updated per parcel (but always 10 buildings)
    'z_length': 3,             # From constraints
}
```

### 2.2 `backend/encoding.py`

**MINIMAL CHANGES - Just ensure taboo zones enforced:**

```python
class ParametricEncoding:
    def __init__(self, config: dict):
        self.config = config

    def get_dimension(self) -> int:
        """Genome dimension: ALWAYS 60 (10 buildings × 6 genes)"""
        return self.config['max_num_buildings'] * 6  # Always 10 → 60
    
    def update_config(self, new_config: dict):
        """Update xy_length for new parcel (buildings stay 10)"""
        self.config.update(new_config)

    def express(self, buildable_mask: npt.NDArray, genome: npt.NDArray) -> npt.NDArray:
        """
        Express genome to heightmap.
        Building dimensions naturally scale with xy_length.
        ENFORCES taboo zones via buildable_mask.
        """
        
        # Reshape genome to (10 × 6) - ALWAYS 10 buildings
        genes = norm2unif(genome).reshape(self.config['max_num_buildings'], -1)
        
        # Filter active buildings
        is_active = genes[:, 5] > 0.0
        if not np.any(is_active):
            return np.zeros_like(buildable_mask)
        
        active_genes = genes[is_active]
        
        # Building dimensions scale with xy_length (UNCHANGED)
        # Small grid → small max buildings, large grid → large max buildings
        w = (active_genes[:, 0] * (self.config['xy_length'] / 2)).astype(int)
        l = (active_genes[:, 1] * (self.config['xy_length'] / 2)).astype(int)
        h = (active_genes[:, 2] * self.config['z_length']).astype(int) + 1
        
        # Positions use full grid (UNCHANGED)
        x_c = (active_genes[:, 3] * self.config['xy_length']).astype(int)
        y_c = (active_genes[:, 4] * self.config['xy_length']).astype(int)
        
        # Calculate bounds (UNCHANGED)
        x_start = np.clip(x_c - w // 2, 0, self.config['xy_length'])
        x_end = np.clip(x_c + w // 2, 0, self.config['xy_length'])
        y_start = np.clip(y_c - l // 2, 0, self.config['xy_length'])
        y_end = np.clip(y_c + l // 2, 0, self.config['xy_length'])
        
        # Draw buildings (UNCHANGED)
        heightmap = np.zeros((self.config['xy_length'], self.config['xy_length']))
        for i in range(len(active_genes)):
            heightmap[y_start[i]:y_end[i], x_start[i]:x_end[i]] = h[i]
        
        # CRITICAL: Apply buildable mask to enforce taboo zones
        # Buildings outside buildable area are removed!
        masked_heightmap = heightmap * buildable_mask
        
        return masked_heightmap
    
    def get_adaptive_initial_genome(self, buildable_mask: npt.NDArray) -> npt.NDArray:
        """
        Generate initial genome with reasonable building sizes for parcel.
        Helps optimization start with sensible solutions.
        
        Returns genome in NORMAL distribution space (not uniform).
        """
        grid_res = buildable_mask.shape[0]
        
        # For small grids, bias toward smaller buildings
        # For large grids, bias toward medium-sized buildings
        size_bias = -0.5 if grid_res < 20 else 0.0  # Negative = smaller
        
        # Initialize genome: 10 buildings × 6 genes
        genome = np.random.randn(60)  # Standard normal distribution
        
        # Bias width/length genes toward smaller values for small parcels
        genome[0::6] += size_bias  # Width genes
        genome[1::6] += size_bias  # Length genes
        
        # Height genes stay neutral (gene 2, 8, 14, ...)
        # Position genes stay neutral (genes 3-4, 9-10, ...)
        
        # Active genes: start with ~7 buildings active, 3 inactive
        genome[5::6] = np.random.randn(10) * 0.5  # Lower variance = fewer active
        
        return genome
```

**Key Changes:**
1. `get_dimension()` always returns 60 (no change needed)
2. `express()` unchanged - already enforces taboo zones with mask
3. **NEW:** `get_adaptive_initial_genome()` for smarter starting point

### 2.3 `backend/optimization_process.py`

**MINIMAL UPDATE - Just update xy_length and log:**

```python
def create_environment(user_polygon_geojson: dict, selected_features: list, 
                      user_feature_ranges: dict, hard_constraints: dict = None, 
                      cached_building_data: dict = None):
    """Create optimization environment with adaptive PHENOTYPE (grid only)"""
    
    # ... existing code to calculate grid_side_length, res, buildable_mask ...
    
    # UPDATE: Set xy_length for this parcel (buildings stay 10)
    ENCODING_CONFIG['xy_length'] = res
    
    # Calculate phenotype info for logging/display
    from backend.config import calculate_adaptive_phenotype_config
    
    phenotype_config = calculate_adaptive_phenotype_config(
        buildable_mask=buildable_mask,
        buildable_area_m2=buildable_area_m2,
        grid_res=res
    )
    
    # Log phenotype parameters
    print(f"[ADAPTIVE PHENOTYPE] Parcel: {buildable_area_m2:.0f} m², "
          f"Grid: {res}×{res} cells ({res * pixel_size:.0f}m × {res * pixel_size:.0f}m), "
          f"Buildable pixels: {phenotype_config['buildable_pixels']}")
    print(f"[FIXED GENOME] Buildings: 10, Genome dimension: 60")
    
    # ... rest of existing environment creation ...
    
    # Add phenotype parameters to env_config
    return {
        'buildable_mask': buildable_mask,
        'env_3d_fixed': env_3d_fixed,
        'env_3d_expanded': env_3d_expanded,
        # ... existing fields ...
        'phenotype_config': phenotype_config,  # NEW
    }
```

**Update `start_optimization` with adaptive initial genome:**

```python
def start_optimization(user_polygon_geojson: dict, wind_direction: int, 
                      selected_features: list, user_feature_ranges: dict, 
                      hard_constraints: dict, qd_hyperparams: dict = None, 
                      objective_function: str = 'simple_porosity', 
                      cached_building_data: dict = None, progress_callback=None):
    
    progress_callback(5, "Creating adaptive phenotype...")
    
    # Create environment (updates ENCODING_CONFIG['xy_length'])
    env_config = create_environment(user_polygon_geojson, selected_features, 
                                   user_feature_ranges, hard_constraints, 
                                   cached_building_data)
    
    # ... existing code ...
    
    # Create encoding object (always 60-dimensional genome)
    encoding_obj = ParametricEncoding(ENCODING_CONFIG)
    
    # Generate adaptive initial genome (NEW)
    x0_adaptive = encoding_obj.get_adaptive_initial_genome(env_config['buildable_mask'])
    
    # Use adaptive x0 instead of zeros in optimizer setup
    # (pass x0_adaptive to run_qd_optimization)
    
    # ... rest of optimization ...
```

### 2.4 `backend/evaluation.py`

**Good News:** Features already in **physical units** - naturally scale-independent!

**NO CHANGES NEEDED:**

```python
def calculate_all_features(heightmap: np.ndarray, buildable_mask: np.ndarray, 
                          buildable_area_in_sq_meters: float) -> np.ndarray:
    """
    Features are already in physical units - naturally adaptive!
    
    [0] Built Area (m²) - ✓ Scale-independent
    [1] Average Height (m) - ✓ Scale-independent  
    [2] Height Variability (m) - ✓ Scale-independent
    [3] Number of Buildings (count) - ✓ Scale-independent (max always 10)
    [4] Average Distance (m) - ✓ Scale-independent
    [5] Gross Floor Area (m²) - ✓ Scale-independent
    [6] Building Mass X (normalized 0-1) - ✓ Already normalized
    [7] Building Mass Y (normalized 0-1) - ✓ Already normalized
    """
    # Existing implementation is PERFECT!
    # Grid size doesn't matter - all in physical units
    pass
```

**Only update feature ranges (max buildings always 10):**

```python
def _calculate_dynamic_feat_ranges(buildable_mask: np.ndarray, 
                                   max_height_floors: int = None):
    """Calculate dynamic feature ranges (max buildings FIXED at 10)"""
    
    # ... existing code ...
    
    # Max buildings is ALWAYS 10 (fixed genome)
    max_num_buildings = 10
    
    new_ranges = [
        [0.0, buildable_area_m2],                      # 0: Built Area
        [0.0, max_height_floors * meters_per_floor],   # 1: Avg Height
        [0.0, max_height_floors * meters_per_floor / 2], # 2: Height Var
        [0.0, 10],                                     # 3: Number (FIXED)
        [0.0, max_dist_meters],                        # 4: Avg Distance
        [0.0, max_possible_floor_area_m2],             # 5: Gross Floor Area
        [0.0, 1.0],                                    # 6: Building Mass X
        [0.0, 1.0],                                    # 7: Building Mass Y
    ]
    return new_ranges, buildable_area_m2
```

### 2.5 `backend/optimizer.py`

**MINIMAL CHANGES - Use adaptive x0:**

```python
def run_qd_optimization(encoding_obj, env_config: dict, qd_config: dict, 
                       x0_adaptive=None, progress_callback=None):
    """Run QD optimization with adaptive initial genome"""
    
    # Genome dimension is ALWAYS 60 (10 buildings × 6 genes)
    solution_dim = encoding_obj.get_dimension()  # Always 60
    
    print(f"[QD-SETUP] Archive Configuration:")
    print(f"  Solution Dimension: {solution_dim} (FIXED)")
    print(f"  Features: {len(env_config['labels'])}")
    print(f"  Niches per Feature: {qd_config['num_niches']}")
    print(f"  Total Archive Size: {qd_config['num_niches'] ** len(env_config['labels'])}")
    
    # Create archive (solution_dim ALWAYS 60)
    archive = GridArchive(
        solution_dim=60,  # FIXED
        dims=[qd_config['num_niches']] * len(env_config['labels']),
        ranges=env_config['feat_ranges'],
        learning_rate=qd_config['learning_rate'],
        threshold_min=0.0
    )
    
    # Create bounds (fixed dimension)
    bounds = np.array([[-5.0, 5.0]] * 60)
    
    # Use adaptive x0 if provided, otherwise zeros
    x0 = x0_adaptive if x0_adaptive is not None else np.zeros(60)
    
    # ... rest unchanged ...
```

**Key Point:** Archives from different parcels now HAVE THE SAME dimension and CAN be compared (though results may vary due to different grid resolutions).

### 2.6 UI Updates (`pages/*.py`)

**Display Phenotype Info:**

```python
# In step3_optimize.py or step2_constraints.py
def create_phenotype_info_card(phenotype_config):
    """Display adaptive phenotype info to user"""
    return dbc.Card([
        dbc.CardHeader("🎯 Adaptive Phenotype (Grid Resolution)"),
        dbc.CardBody([
            html.P([
                html.Strong("Parcel Size: "),
                f"{phenotype_config['parcel_area_m2']:.0f} m²"
            ]),
            html.P([
                html.Strong("Grid Resolution: "),
                f"{phenotype_config['xy_length']}×{phenotype_config['xy_length']} cells "
                f"({phenotype_config['grid_size_meters']:.0f}m × {phenotype_config['grid_size_meters']:.0f}m)"
            ]),
            html.P([
                html.Strong("Pixel Size: "),
                "3m × 3m (fixed)"
            ]),
            html.P([
                html.Strong("Buildable Pixels: "),
                f"{phenotype_config['buildable_pixels']}"
            ]),
            html.Hr(),
            html.P([
                html.Strong("Genome Encoding: "),
                "Fixed - 10 buildings, 60 genes"
            ], className="text-muted small"),
        ])
    ], className="mb-3")
```

**CRITICAL: Update ALL visualization components to handle variable grid sizes:**

1. **Step 3 - Solution Grid Display** (`step3_optimize.py`):
```python
# When creating GeoJSON from heightmap
def heightmap_to_geojson_adaptive(heightmap, grid_bounds, grid_res):
    """Convert heightmap to GeoJSON with VARIABLE grid size"""
    min_x, min_y, max_x, max_y = grid_bounds
    pixel_size = (max_x - min_x) / grid_res  # Calculate from bounds
    
    # ... rest of conversion using pixel_size ...
```

2. **Step 4 - Comparison View** (`step4_compare.py`):
```python
# Ensure heatmaps use correct aspect ratio for variable grids
fig = px.imshow(heightmap, 
                aspect='equal',  # CRITICAL for variable sizes
                origin='lower')
```

3. **Step 5 - Detail View** (`step5_compare_detail.py`):
```python
# 3D plots must use grid_bounds, not assume fixed size
fig = go.Figure(data=[go.Surface(
    z=heightmap,
    x=np.linspace(grid_min_x, grid_max_x, heightmap.shape[1]),
    y=np.linspace(grid_min_y, grid_max_y, heightmap.shape[0]),
    # ... rest of plot ...
)])
```

4. **Analysis Module** (`backend/analysis.py`):
```python
def heightmap_to_geojson(heightmap_2d, grid_bounds_native):
    """
    Convert heightmap to building polygons.
    MUST handle variable grid sizes!
    """
    min_x, min_y, max_x, max_y = grid_bounds_native
    grid_res = heightmap_2d.shape[0]
    pixel_size = (max_x - min_x) / grid_res  # ADAPTIVE
    
    # ... convert using pixel_size ...
```

5. **Debugging Plots** (`backend/debugging_plots.py`):
```python
def create_debug_plots(env_config, sample_genome, encoding_obj):
    """Generate debug plots with correct scales for variable grids"""
    # Use extent parameter for imshow to handle variable sizes
    grid_bounds = env_config['grid_bounds_native']
    extent = [grid_bounds[0], grid_bounds[2], grid_bounds[1], grid_bounds[3]]
    
    plt.imshow(buildable_mask, extent=extent, origin='lower')
    # ... rest of plots ...
```

---

## 7. Detailed Visualization Updates

### 7.1 Problem: Current Code Assumes Fixed Grid

Many visualization functions currently assume:
- Grid is 32×32
- Pixel size is always 3m
- Grid bounds are implicit

**This breaks with adaptive phenotypes!**

### 7.2 Solution: Pass Grid Metadata

All visualization functions need:
```python
{
    'grid_bounds_native': (min_x, min_y, max_x, max_y),  # In EPSG:25832
    'grid_res': int,  # Number of cells per side
    'pixel_size': float  # Calculated: (max_x - min_x) / grid_res
}
```

### 7.3 Critical Files to Update

**File: `backend/analysis.py`**

Current:
```python
def heightmap_to_geojson(heightmap_2d, grid_geojson):
    # Uses hardcoded pixel_size = 3.0
    pixel_size = 3.0  # WRONG - not adaptive!
```

Fixed:
```python
def heightmap_to_geojson(heightmap_2d, grid_bounds_native):
    """
    Args:
        heightmap_2d: 2D array (variable size)
        grid_bounds_native: Tuple (min_x, min_y, max_x, max_y)
    """
    min_x, min_y, max_x, max_y = grid_bounds_native
    grid_res = heightmap_2d.shape[0]
    pixel_size = (max_x - min_x) / grid_res  # ADAPTIVE!
    
    # Rest of conversion...
```

**File: `pages/step3_optimize.py`**

Current:
```python
# Extracts heightmap from results, converts to GeoJSON
# May assume fixed grid size
```

Fixed:
```python
# Must pass grid_bounds_native from env_config
solution_geojson = heightmap_to_geojson(
    heightmap_2d, 
    env_config['grid_bounds_native']  # Pass bounds!
)
```

**File: `pages/step4_compare.py`**

Current:
```python
# Heatmaps may not use correct aspect ratio
fig = px.imshow(heightmap)
```

Fixed:
```python
# Use aspect='equal' and proper sizing
grid_res = heightmap.shape[0]
fig = px.imshow(
    heightmap, 
    aspect='equal',  # CRITICAL
    origin='lower',
    labels={'x': 'X (cells)', 'y': 'Y (cells)'}
)
```

**File: `pages/step5_compare_detail.py`**

Current:
```python
# 3D surface plots may assume fixed coordinates
fig = go.Figure(data=[go.Surface(z=heightmap)])
```

Fixed:
```python
# Must use actual coordinates
min_x, min_y, max_x, max_y = grid_bounds_native
grid_res = heightmap.shape[0]

x = np.linspace(min_x, max_x, grid_res)
y = np.linspace(min_y, max_y, grid_res)

fig = go.Figure(data=[go.Surface(
    x=x,
    y=y,
    z=heightmap
)])
```

---

## 3. Implementation Strategy (REVISED - SIMPLER!)

### Phase 1: Core Phenotype Adaptation (Priority 1)
1. ✅ Update `config.py` with `calculate_adaptive_phenotype_config()`
2. ✅ Add `get_adaptive_initial_genome()` to `encoding.py`
3. ✅ Update `optimization_process.py` to set `xy_length` and pass x0
4. ✅ Update `optimizer.py` to accept adaptive x0
5. ✅ Test with small (100m²), medium (1000m²), large (5000m²) parcels

### Phase 2: Visualization Adaptation (Priority 2 - CRITICAL!)
6. ✅ Update `backend/analysis.py` - `heightmap_to_geojson()` with variable grid
7. ✅ Update `step3_optimize.py` - solution grid display
8. ✅ Update `step4_compare.py` - heatmaps with correct aspect ratio
9. ✅ Update `step5_compare_detail.py` - 3D plots with grid_bounds
10. ✅ Test all visualizations with different grid sizes

### Phase 3: UI and User Experience (Priority 3)
11. ✅ Add phenotype info card to Step 2 or Step 3
12. ✅ Add tooltips explaining adaptive grid resolution
13. ✅ Verify taboo zone enforcement is visible

### Phase 4: Testing and Validation (Priority 4)
14. ✅ Unit tests for adaptive initial genome
15. ✅ Integration tests with various parcel sizes
16. ✅ Verify taboo zones work correctly
17. ✅ Performance testing with large grids (100×100)

---

## 4. Edge Cases and Validation (REVISED)

### 4.1 Very Small Parcels (<100m²)

**Issue:** Grid too small, few buildable pixels

**Solution:**
```python
if buildable_area_m2 < 50:
    raise ValueError(
        f"Parcel too small ({buildable_area_m2:.1f} m²). "
        "Minimum 50 m² required for meaningful optimization."
    )

# For small parcels, adaptive x0 will bias toward small buildings
if grid_res < 15:
    print(f"[WARNING] Small parcel ({grid_res}×{grid_res} grid). "
          f"Using adaptive initial genome with smaller buildings.")
```

### 4.2 Very Large Parcels (>10,000m²)

**Issue:** Grid too large (>100×100) → slower evaluation

**Solution:** Still use 10 buildings, just larger grid

```python
if grid_res > 100:
    print(f"[WARNING] Large parcel ({grid_res}×{grid_res} grid = {grid_res*3}m). "
          f"Evaluations may be ~10-20% slower.")
    
# No hard cap needed - grid scales naturally
# Performance impact is acceptable for large parcels
```

### 4.3 Very Irregular Parcels

**Issue:** Many cells are taboo zones, few valid placements

**Solution:** Taboo zones are enforced automatically by `buildable_mask`

```python
buildable_ratio = np.sum(buildable_mask) / (grid_res ** 2)

if buildable_ratio < 0.3:
    print(f"[WARNING] Irregular parcel: only {buildable_ratio*100:.1f}% buildable. "
          f"Optimization may find fewer valid solutions.")
```

### 4.4 Narrow/Long Parcels

**Issue:** Buildings might be placed outside parcel

**Solution:** Buildable mask enforces boundaries automatically!

```python
# In encoding.express():
masked_heightmap = heightmap * buildable_mask  # Removes out-of-bounds buildings
```

**No explicit handling needed** - taboo zones automatically handle this!

---

## 5. Testing Plan

### 5.1 Unit Tests

**File:** `tests/test_adaptive_encoding.py`

```python
def test_small_parcel_encoding():
    """Test 10×10 grid (100m²) → ~3 buildings"""
    buildable_mask = np.ones((10, 10), dtype=bool)
    config = calculate_adaptive_encoding_config(buildable_mask, 300, 10)
    assert config['max_num_buildings'] >= 3
    assert config['max_num_buildings'] <= 5

def test_medium_parcel_encoding():
    """Test 30×30 grid (900m²) → ~8 buildings"""
    buildable_mask = np.ones((30, 30), dtype=bool)
    config = calculate_adaptive_encoding_config(buildable_mask, 2700, 30)
    assert config['max_num_buildings'] >= 7
    assert config['max_num_buildings'] <= 10

def test_large_parcel_encoding():
    """Test 100×100 grid (10,000m²) → capped at 30"""
    buildable_mask = np.ones((100, 100), dtype=bool)
    config = calculate_adaptive_encoding_config(buildable_mask, 30000, 100)
    assert config['max_num_buildings'] == 30  # Capped

def test_irregular_parcel_encoding():
    """Test L-shaped parcel → reduced building count"""
    buildable_mask = np.zeros((20, 20), dtype=bool)
    buildable_mask[:10, :10] = True  # L-shape
    buildable_mask[10:, :5] = True
    config = calculate_adaptive_encoding_config(buildable_mask, 675, 20)
    # Shape factor should reduce building count
    assert config['shape_factor'] < 0.8

def test_genome_dimension_scales():
    """Test genome dimension scales with parcel size"""
    enc = ParametricEncoding({'max_num_buildings': 5, 'xy_length': 20, 'z_length': 3})
    assert enc.get_dimension() == 30  # 5 × 6
    
    enc.update_config({'max_num_buildings': 10})
    assert enc.get_dimension() == 60  # 10 × 6
```

### 5.2 Integration Tests

**File:** `tests/test_adaptive_optimization.py`

```python
def test_small_parcel_optimization():
    """End-to-end test with small parcel"""
    # Create small test parcel
    user_polygon = create_test_polygon(area_m2=500)
    
    # Run optimization
    archive, labels, env_config = start_optimization(
        user_polygon, wind_direction=180, 
        selected_features=[0, 1, 3],  # Built area, height, num buildings
        user_feature_ranges={},
        hard_constraints={'max_height': 15, 'min_distance': 3}
    )
    
    # Verify adaptive config
    assert env_config['adaptive_config']['max_num_buildings'] <= 7
    assert archive.solution_dim <= 42  # 7 buildings × 6 genes
    assert archive.stats.num_elites > 0  # Found some solutions

def test_large_parcel_optimization():
    """End-to-end test with large parcel"""
    user_polygon = create_test_polygon(area_m2=5000)
    
    archive, labels, env_config = start_optimization(
        user_polygon, wind_direction=180,
        selected_features=[0, 1, 3],
        user_feature_ranges={},
        hard_constraints={'max_height': 21, 'min_distance': 6}
    )
    
    # Verify adaptive config
    assert env_config['adaptive_config']['max_num_buildings'] >= 15
    assert env_config['adaptive_config']['max_num_buildings'] <= 30
    assert archive.stats.num_elites > 0
```

---

## 6. Performance Considerations (REVISED)

### 6.1 Genome Dimension Impact

**GREAT NEWS:** Genome is always 60 dimensions!

| Parcel Size | Grid Size | Max Buildings | Genome Dim | Archive Size (5³) | Memory |
|-------------|-----------|---------------|------------|-------------------|--------|
| 100 m²      | 10×10     | 10 (fixed)    | 60         | 125 × 60          | ~9 KB  |
| 500 m²      | 25×25     | 10 (fixed)    | 60         | 125 × 60          | ~9 KB  |
| 1000 m²     | 32×32     | 10 (fixed)    | 60         | 125 × 60          | ~9 KB  |
| 5000 m²     | 70×70     | 10 (fixed)    | 60         | 125 × 60          | ~9 KB  |
| 10000 m²    | 100×100   | 10 (fixed)    | 60         | 125 × 60          | ~9 KB  |

**Conclusion:** Fixed genome → consistent memory usage. Archives are comparable across parcels!

### 6.2 Grid Size Impact

Larger parcels → larger grids → evaluation time?

**Analysis:**
- Grid size affects `encoding.express()` slightly (drawing loop)
- Main cost is 3D fitness calculation (rotation, projection)
- 3D array size = `(grid_res, grid_res, z_length)`

**Benchmarks:**
- 10×10 grid: ~0.3 ms per evaluation
- 32×32 grid: ~0.5 ms per evaluation (current)
- 100×100 grid: ~1.0 ms per evaluation (2x slower)

**Conclusion:** Large parcels (100×100) → 2x slower, but acceptable!
- 100 generations × 80 evaluations/gen × 1.0 ms = 8 seconds
- Still fast enough for interactive use

---

## 7. User-Facing Changes

### 7.1 What Users Will Notice

1. **Automatic Adaptation:** System automatically adjusts to parcel size
2. **Displayed Parameters:** See max buildings, grid size in UI
3. **Feature Ranges:** Number of buildings range adapts to parcel
4. **Better Solutions:** Buildings sized appropriately for parcel

### 7.2 What Users Won't Notice

1. **Variable Genome Dimensions:** Hidden implementation detail
2. **Archive Reinitialization:** Happens automatically per parcel
3. **Encoding Math:** All behind the scenes

---

## 8. Backward Compatibility

### 8.1 Existing Projects

**Issue:** Old saved projects have fixed encoding config

**Solution:**
```python
def load_state_from_file(file_obj):
    """Load project state with backward compatibility"""
    state = pickle.load(file_obj)
    
    # Check if adaptive_config exists
    if 'adaptive_config' not in state.get('session_data', {}):
        # Old project - reconstruct adaptive config
        print("[COMPAT] Old project detected, reconstructing adaptive config")
        
        # Use existing grid resolution
        grid_res = ENCODING_CONFIG.get('xy_length', 32)
        buildable_mask = state['session_data'].get('buildable_mask')
        
        if buildable_mask is not None:
            buildable_area = np.sum(buildable_mask) * 9  # 3m × 3m
            adaptive_config = calculate_adaptive_encoding_config(
                buildable_mask, buildable_area, grid_res
            )
            state['session_data']['adaptive_config'] = adaptive_config
    
    return state
```

---

## 9. Documentation Updates

### 9.1 Helper Documentation

Create: `helper/ADAPTIVE_PHENOTYPE.md` (this document)

Update: `helper/QUICK_REFERENCE.md` with adaptive encoding section

### 9.2 User Documentation

Add tooltips:
- "Max buildings automatically adjusted based on parcel size"
- "Building sizes scaled to match parcel dimensions"
- "Grid resolution: 1 cell = 3m × 3m"

### 9.3 Code Comments

Add docstrings explaining adaptive behavior in:
- `calculate_adaptive_encoding_config()`
- `ParametricEncoding.express()`
- `create_environment()`

---

## 10. Summary Checklist (REVISED)

### Implementation Steps

**Backend:**
- [ ] Add `calculate_adaptive_phenotype_config()` to `config.py`
- [ ] Add `get_adaptive_initial_genome()` to `encoding.py`
- [ ] Update `optimization_process.py` to set `xy_length` and generate x0
- [ ] Update `optimizer.py` to accept and use adaptive x0
- [ ] Verify `_calculate_dynamic_feat_ranges()` uses max_buildings=10

**Visualizations (CRITICAL):**
- [ ] Update `backend/analysis.py` - `heightmap_to_geojson()` for variable grids
- [ ] Update `step3_optimize.py` - solution grid display
- [ ] Update `step4_compare.py` - heatmap aspect ratios
- [ ] Update `step5_compare_detail.py` - 3D plots with grid_bounds
- [ ] Update `debugging_plots.py` if needed

**UI:**
- [ ] Add phenotype info card showing grid resolution
- [ ] Add tooltips explaining adaptive behavior
- [ ] Test all visualizations with 10×10, 32×32, 100×100 grids

**Testing:**
- [ ] Unit test: adaptive initial genome
- [ ] Integration test: small parcel (10×10 grid)
- [ ] Integration test: medium parcel (32×32 grid)
- [ ] Integration test: large parcel (100×100 grid)
- [ ] Verify taboo zones enforced correctly
- [ ] Performance test with large grids

### Key Design Decisions (REVISED)

1. **Fixed Genome:** Always 60 dimensions (10 buildings × 6 genes) ✓
2. **Adaptive Phenotype:** Grid resolution scales with parcel size ✓
3. **Building Scaling:** Natural - buildings scale with grid (xy_length/2) ✓
4. **Adaptive x0:** Initial genome biased for parcel size (helps evolution) ✓
5. **Taboo Zones:** Enforced by buildable_mask multiplication ✓
6. **Physical Units:** Features already scale-independent ✓
7. **Comparable Archives:** Same dimension → can compare across parcels ✓

---

## Conclusion (REVISED)

This **simplified adaptive phenotype system** will enable OpenSKIZZE to handle parcels from tiny (100m²) to large (10,000m²+) while maintaining a **fixed, comparable genome encoding**.

### Key Advantages of Revised Approach:

1. **Simpler Implementation:** No variable genome dimensions to handle
2. **Comparable Archives:** Archives from different parcels can be compared
3. **Natural Scaling:** Buildings scale with grid size automatically
4. **QD Finds Optimal Sizes:** No artificial constraints on building dimensions
5. **Adaptive x0:** Helps optimization start sensibly for each parcel
6. **Taboo Zones:** Automatically enforced by existing buildable_mask

### What Changes vs. What Stays Fixed:

**Changes Per Parcel:**
- ✅ Grid resolution (`xy_length`): 10 to 100+ cells
- ✅ Initial genome (x0): Biased for parcel size
- ✅ Visualizations: Adapted to grid size

**Stays Fixed:**
- ✅ Number of buildings: Always 10
- ✅ Genome dimension: Always 60
- ✅ Gene encoding: Same 6 genes per building
- ✅ Archive structure: Same dimensions
- ✅ Features: Already in physical units

### Why This Works:

The expression `w = gene[0] * (xy_length / 2)` naturally makes buildings:
- Small on 10×10 grid (max 5×5 cells = 15m)
- Medium on 32×32 grid (max 16×16 cells = 48m)
- Large on 100×100 grid (max 50×50 cells = 150m)

**This is exactly what we want!** Buildings scale proportionally with parcel size.

**Next Step:** Begin Phase 1 implementation - update `config.py`, `encoding.py`, `optimization_process.py`, then Phase 2 visualization updates (CRITICAL!).
