# Backend Changes for OpenSKIZZE Frontend Integration

This document describes recent backend changes that require corresponding updates in the OpenSKIZZE GUI frontend.

---

## 1. Encoding System: Transition to Fast Encoding

### What Changed
The old `ParametricEncoding` class has been replaced with `NumbaFastEncoding`, providing **16× faster** genome-to-heightmap conversion using Numba JIT compilation.

### Backend Details
- **Old file removed**: `encodings/parametric/parametric.py` (deleted)
- **New file**: `encodings/parametric/fast_encoding.py` contains `NumbaFastEncoding`
- **Import path**: `from encodings.parametric import ParametricEncoding` (unchanged, but now aliases to `NumbaFastEncoding`)

### API Changes
The interface remains **backwards compatible**. All existing methods work identically:

```python
from encodings.parametric import ParametricEncoding

# Initialization options (all work)
enc = ParametricEncoding()                      # Default: 60m parcel
enc = ParametricEncoding(parcel_size=120)       # New: specify parcel size in meters
enc = ParametricEncoding(config=config_dict)    # Legacy: config dict

# Methods (unchanged)
enc.get_dimension()                             # Returns 60 (genome size)
enc.express(genome, as_height_map=True)         # Single genome → heightmap (floors)
enc.express_batch(genomes)                      # Batch genomes → heightmaps (meters) - NEW, faster
enc.generate_sobol_sequence_genome(n)           # Sobol sampling
enc.set_genome(genome)                          # Set genome for later express()
```

### Frontend Action Required
- **None if using existing API** - backwards compatible
- **Recommended**: Use `express_batch()` for batch operations (16× faster)
- **Update any direct imports** from `encodings.parametric.parametric` to `encodings.parametric`

---

## 2. Parcel Size System: Simplified to 3 Sizes

### What Changed
The parcel size options have been simplified from 13 sizes to 3 sizes for cleaner urban planning scales.

### Old System (13 sizes)
```
27, 33, 39, 45, 51, 57, 63, 69, 75, 81, 87, 93, 99 meters
(6m increments, all divisible by xy_scale=3)
```

### New System (3 sizes)
```python
PARCEL_SIZES = [60, 120, 240]  # meters
```

| Size | Grid Cells | Use Case |
|------|------------|----------|
| **60m** | 20×20 | Residential block / small plot |
| **120m** | 40×40 | Medium development |
| **240m** | 80×80 | Large mixed-use development |

### Grid Cell Calculation
```python
grid_cells = parcel_size_m // 3  # xy_scale = 3.0 meters per cell
```

### Frontend Action Required
- **Update parcel size dropdown/selector** to show only: 60, 120, 240 meters
- **Update any hardcoded references** to old sizes (27, 51, 69, etc.)
- **Default parcel size** should be `60` or `120` (was often 27 or 51)

---

## 3. KLAM_21 Physics: Pure Katabatic (Adiabatic) Flow

### What Changed
The KLAM_21 cold air simulation now uses **pure katabatic flow** (gravity-driven drainage) instead of forced wind flow.

### Old Configuration
```yaml
klam_config:
  wind_speed: 5.0        # Forced wind
  wind_direction: 270    # West wind
  terrain_slope: 1.0     # 1° slope, discontinuous
```

### New Configuration
```yaml
klam_config:
  wind_speed: 0.0        # NO forced wind (pure katabatic)
  wind_direction: 270    # Direction still set but no forcing
  terrain_slope: 2.0     # 2° continuous slope across entire domain
```

### Physical Interpretation
- **Old**: Wind-driven airflow at 5 m/s (unrealistic for nocturnal cold air drainage)
- **New**: Pure gravity-driven katabatic flow on 2° slope (realistic mountain/valley drainage)

### Terrain Generation
The entire simulation domain now has a **continuous 2° slope** from east to west:
```python
# Elevation increases linearly from right (east) to left (west)
elevation = distance_from_east_edge * tan(2°)
# At 100m distance: elevation ≈ 3.5m
```

### Frontend Action Required
- **Update any wind speed displays** to show 0 m/s or "Katabatic flow"
- **Update terrain visualization** if shown - now continuous slope
- **Update tooltips/help text** to explain "pure katabatic cold air drainage"
- **Remove wind direction controls** if they were user-adjustable (no longer relevant)

---

## 4. Summary of Default Values

### Encoding Defaults
| Parameter | Old | New |
|-----------|-----|-----|
| Default parcel size | 27m or 51m | **60m** |
| Grid cells (60m) | N/A | **20×20** |
| Genome dimension | 60 | 60 (unchanged) |
| Max buildings | 10 | 10 (unchanged) |
| Max floors | 10 | 10 (unchanged) |
| xy_scale | 3.0m | 3.0m (unchanged) |
| z_scale | 3.0m | 3.0m (unchanged) |

### KLAM_21 Defaults
| Parameter | Old | New |
|-----------|-----|-----|
| Wind speed | 5.0 m/s | **0.0 m/s** |
| Terrain slope | 1° (discontinuous) | **2° (continuous)** |
| Simulation duration | 14400s (4h) | 14400s (unchanged) |

### Parcel Size Options
| Old Options | New Options |
|-------------|-------------|
| 27, 33, 39, 45, 51, 57, 63, 69, 75, 81, 87, 93, 99 | **60, 120, 240** |

---

## 5. File Changes Reference

### Modified Files
- `domain_description/cfg.yml` - KLAM config (wind_speed, slope)
- `domain_description/evaluation_klam.py` - Terrain generation (continuous 2° slope)
- `encodings/parametric/__init__.py` - Exports NumbaFastEncoding as ParametricEncoding
- `encodings/parametric/fast_encoding.py` - Enhanced with full backwards compatibility

### Deleted Files
- `encodings/parametric/parametric.py` - Removed (replaced by fast_encoding.py)

### Key Constants Location
```python
# Parcel sizes defined in experiment files:
PARCEL_SIZES = [60, 120, 240]  # experiments/exp1_gp_training_data/*.py

# KLAM config:
# domain_description/cfg.yml
klam_config:
  wind_speed: 0.0
  wind_direction: 270
  sim_duration: 14400
```

---

## 6. Migration Checklist for Frontend

- [ ] Update parcel size selector: `[60, 120, 240]` meters
- [ ] Update default parcel size to `60` or `120`
- [ ] Remove or disable wind speed controls (now always 0)
- [ ] Update physics description text to "katabatic cold air drainage"
- [ ] Update any imports from `encodings.parametric.parametric` to `encodings.parametric`
- [ ] Test with new parcel sizes to ensure grid calculations correct
- [ ] Update any visualization of terrain to show continuous slope
- [ ] Update help/documentation to reflect pure gravity-driven flow

---

## 7. API Quick Reference

### Create Encoding
```python
from encodings.parametric import ParametricEncoding

# For specific parcel size
enc = ParametricEncoding(parcel_size=120)  # 120m parcel → 40×40 grid
```

### Express Genomes
```python
# Single genome → heightmap in FLOORS (for visualization)
heightmap_floors = enc.express(genome, as_height_map=True)  # (D, D)

# Batch genomes → heightmaps in METERS (for KLAM simulation)
heightmaps_meters = enc.express_batch(genomes)  # (N, D, D)
```

### Grid Size Calculation
```python
parcel_size_m = 120  # meters
xy_scale = 3.0       # meters per cell (fixed)
grid_cells = parcel_size_m // xy_scale  # = 40 cells
grid_shape = (grid_cells, grid_cells)   # = (40, 40)
```

---

*Document created: December 11, 2025*
*For questions, contact the backend development team.*
