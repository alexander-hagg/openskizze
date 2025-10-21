# OpenSKIZZE Coding Agent Instructions

## Quick Start (Read This First!)

**What is this?** An interactive web app for urban planners to explore building layouts optimized for climate (wind flow, heat). Uses Quality-Diversity algorithms to generate 100-1000 diverse solutions.

**Tech at a glance**: Python 3.12, Dash web framework, PyRibs QD optimizer, GeoPandas for GIS, NumPy-heavy

**Critical constraints**:
- Genome dimension is FIXED at 60 (never change)
- Always use physical units (meters, m²)
- Always add bilingual strings (German + English)
- Performance matters: evaluation runs 50,000 to 500,000 times

**Before making any changes**:
1. Read the **Core Workflow** section (5 steps)
2. Check **Common Tasks** for your specific task
3. Review **Common Pitfalls** to avoid issues

**Getting started**:
```bash
cd /home/runner/work/openskizze-gui/openskizze-gui
python run.py  # Start at http://127.0.0.1:8050
```

---

## Project Overview

OpenSKIZZE is an interactive urban planning decision-support tool for climate-aware building massing exploration. It uses Quality-Diversity optimization (PyRibs) with ML surrogates to generate diverse urban design solutions optimized for ventilation and heat metrics.

**Target Users**: Urban planners in North Rhine-Westphalia (NRW), Germany
**Language**: Bilingual (German/English UI)

## Tech Stack

### Core Framework
- **Python 3.12** - Primary language
- **Dash 2.17** + Dash Bootstrap Components - Web UI framework
- **Flask** (via Dash) - Web server

### Key Libraries
- **PyRibs 0.6.1** - Quality-Diversity optimization (GridArchive, GaussianEmitter, Scheduler)
- **NumPy 1.26** + **SciPy 1.13** - Numerical computations, array operations
- **GeoPandas 0.14** + **Shapely 2.0** + **Fiona 1.9** - Geospatial data processing
- **Dash-Leaflet 1.0** - Interactive maps
- **Plotly 5.22** - 3D visualizations and charts
- **Pandas 2.2** - Data manipulation
- **scikit-learn + HDBSCAN** - Clustering analysis
- **Numba 0.59** - JIT compilation for performance-critical code
- **PyLaTeX 1.4** - PDF report generation

### Data Sources
- **NRW LOD2 CityGML** - Building geometries with measured heights (EPSG:25832)
- **NRW ALKIS WFS** - Parcel/land use data
- **OpenStreetMap** - Base maps

## Project Structure

```
openskizze-gui/
├── app.py                  # Dash app initialization, routing, callbacks
├── run.py                  # Entry point (python run.py)
├── requirements.txt        # Python dependencies
├── README.md              # High-level project info
├── BACKLOG.md             # Feature roadmap and epics
├── report.md              # Executive summary and planning context
├── backend/               # Core logic (11 modules)
│   ├── config.py          # QD, encoding, domain config
│   ├── encoding.py        # Parametric genome (60 genes: 10 buildings × 6)
│   ├── optimizer.py       # QD optimization loop (PyRibs)
│   ├── evaluation.py      # Fitness functions (wind porosity, street canyon)
│   ├── data_io.py         # NRW data fetching (LOD2, parcels)
│   ├── optimization_process.py # Main pipeline orchestration (26K LOC)
│   ├── analysis.py        # Archive analysis, clustering, exports
│   ├── units.py           # Physical unit conversions
│   ├── translation.py     # DE/EN text dictionaries
│   ├── project_state.py   # Save/load (.skizze files use pickle)
│   └── debugging_plots.py # Diagnostic visualizations
├── pages/                 # UI pages (6 modules)
│   ├── step1_scope.py     # Parcel selection + map
│   ├── step2_constraints.py # Feature/objective selection + constraints
│   ├── step3_optimize.py  # Run optimization with progress updates
│   ├── step4_compare.py   # Archive heatmaps, clustering, 3D previews
│   ├── step5_compare_detail.py # Side-by-side 3D comparison
│   └── step_diagnostic.py # Debug view for empty archives
├── assets/                # Static files
│   ├── style.css          # Custom CSS
│   ├── camera_sync.js     # Client-side 3D camera sync
│   └── logo.png           # Branding
├── tests/                 # Test scripts (22 files)
│   ├── test_*.py          # Unit/integration tests
│   └── benchmark_*.py     # Performance tests
└── helper/                # Documentation (60+ markdown files)
    ├── QUICK_START_GUIDE.md # Feature guides
    ├── QUICK_REFERENCE.md   # Performance optimizations
    └── *.md                 # Implementation notes
```

## Core Workflow (5 Steps)

1. **Step 1**: Select parcel (GeoJSON upload or NRW WFS fetch) + set wind direction
2. **Step 2**: Select features (8 measures), set target ranges, hard constraints (max height, min distance), set number of generations
3. **Step 3**: Run QD optimization (multiprocess)
4. **Step 4**: Explore archive (heatmaps, clustering, tiled 3D previews)
5. **Step 5**: Compare solution clusters or "design families" side-by-side (synchronized 3D views)

## Coding Guidelines

### General Principles
- **Minimize changes**: Make surgical edits; avoid refactoring working code
- **Physical units everywhere**: Use meters for heights/distances, m² for areas
- **CRS handling**: EPSG:25832 (native) ↔ EPSG:4326 (web) conversions via GeoPandas
- **Bilingual**: Add both German and English strings to `backend/translation.py` T['DE'] and T['EN']
- **No external scripts**: Use standard tools; avoid helper scripts

### Python Style
- **Type hints**: Encouraged for new functions (e.g., `def foo(x: int) -> float:`)
- **Docstrings**: Add for complex logic (Google style)
- **Imports**: Group standard lib, third-party, local (`backend.*`)
- **NumPy vectorization**: Prefer over loops for array operations
- **Error handling**: Use try/except for network calls and file I/O

### Performance Critical
- **Evaluation loop**: `backend/evaluation.py` runs 50,000 to 500,000 times per optimization
  - Avoid: Python loops, redundant `scipy.ndimage.label()` calls altogether
  - Profile with `python -m cProfile` if adding compute-heavy code
- **Multiprocessing**: Optimizer uses `Pool(processes=N)` for batch evaluation where N depends on available CPU cores
- **Caching**: LOD2 tiles cached in `cache/lod2_tiles/`, building labels cached per evaluation

### Dash/UI Patterns
- **Callbacks**: Use `@app.callback` in page modules, register in `app.py`
- **Stores**: `dcc.Store` for session state (session-store, results-store, comparison-store)
- **Progress updates**: Use `dcc.Interval` with `progress_callback` in optimizer
- **Client-side callbacks**: For instant updates (e.g., 3D camera sync in `app.py`)
- **Pattern-matching callbacks**: Use `{'type': 'plot', 'index': ALL}` for dynamic components

### Data Flow
1. User input (step1/2) → `session-store` (Dash Store)
2. Optimization (step3) → `results-store` (archive + metadata)
3. Analysis (step4) → clustering/exports → `comparison-store` (selected solutions)
4. Comparison (step5) → 3D rendering

## Common Tasks

### Adding a New Feature/Measure
1. Define in `backend/config.py` DOMAIN_CONFIG['features']
2. Add label to `backend/translation.py` T['DE']/T['EN'] (e.g., MEASURE_8)
3. Add unit to `backend/units.py` FEATURE_UNITS
4. Implement calculation in `backend/evaluation.py` `extract_features()`
5. Update feature ranges in DOMAIN_CONFIG['feat_ranges']
6. Add UI controls in `pages/step2_constraints.py`
7. Test with `tests/test_feature_constraints.py` pattern

### Adding a New Objective
1. Implement function in `backend/evaluation.py` (e.g., `compute_fitness_X()`)
2. Add dispatch in `eval_solution()` based on `env_config['objective_function']`
3. Add UI selection in `pages/step2_constraints.py` (radio buttons)
4. Update `backend/optimization_process.py` to pass objective to env_config
5. Create test (see `tests/test_street_canyon.py` for example)

### Modifying the Genome
- **FIXED DIMENSION**: Always 60 genes (10 buildings × 6 genes)
- Genes: [width, length, height, x, y, active] per building
- Modify `backend/encoding.py` ParametricEncoding class
- Update `decode()` for new gene interpretation
- **Do not change** `get_dimension()` return value (breaks archive)

### Working with LOD2 Data
- Fetching: `backend/data_io.py` `fetch_and_process_buildings_for_area()`
- Tile discovery: Automatic via grid intersection (5km × 5km tiles)
- Parsing: CityGML 1.0 with namespaces (core, bldg, gml)
- Heights: Use `measuredHeight` attribute (meters above sea level)
- Caching: Tiles saved as `cache/lod2_tiles/LoD2_{grid_id}.gml`

### Debugging Empty Archives
1. Check diagnostic page (`/diagnostic`) - shows fitness values
2. Verify constraints aren't too restrictive (max_height, min_distance)
3. For dense urban: Use 'street_canyon' objective instead of 'simple_porosity'
4. Check feature ranges match actual solution space
5. Increase num_generations or num_emitters in QD config

## Environment Setup

### Installation
```bash
# Install dependencies using mamba (recommended)
mamba create -n openskizze python=3.12
mamba activate openskizze
mamba install --file requirements.txt

# Alternative: Use pip within mamba environment
mamba create -n openskizze python=3.12
mamba activate openskizze
pip install -r requirements.txt
```

### Running the App
```bash
python run.py  # Starts Flask dev server on http://127.0.0.1:8050
```

### Running Tests
```bash
# Individual test (many have hardcoded paths, may need adjustment)
python tests/test_feature_constraints.py

# Note: Test files often have hardcoded sys.path.insert statements
# pointing to specific developer machines. You may need to:
# 1. Comment out sys.path.insert lines
# 2. Run from repo root: python tests/test_X.py
# 3. Or add repo to PYTHONPATH: export PYTHONPATH=$PWD:$PYTHONPATH

# Run all tests (no pytest/tox configured)
for f in tests/test_*.py; do python "$f" 2>&1 | grep -E "PASS|FAIL|Error"; done
```

### Building Dependencies
- **No build step** - Pure Python app
- **No linting configured** - No flake8, black, or pylint in repo
- **No CI/CD** - No .github/workflows

## Known Issues and Workarounds

### Dependency Conflicts
- **Issue**: `dash-extensions==1.1.1` not available for Python 3.12
- **Workaround**: Use `dash-extensions>=1.0.0,<2.0.0` or manually install 2.0.x

### Performance
- **Issue**: 8 minutes for 1000 generations on mid-range hardware
- **Status**: Optimized (label caching, 2D rotation) - now ~3-4 minutes
- **See**: `helper/QUICK_REFERENCE.md` for details

### Empty Archive
- **Issue**: Dense urban parcels with simple_porosity return 0.0 fitness
- **Fix**: Use 'street_canyon' objective (see `helper/QUICK_START_GUIDE.md`)

### Project Files
- **Issue**: `.skizze` files use pickle (unsafe for production)
- **Status**: Development only; switch to JSON before multi-user deployment

### Three.js Requirement
- **Note**: README mentions three.js for 3D but not in repo
- **Actual**: Plotly handles 3D (no three.js needed currently)

## Testing Strategy

- **No formal test framework** - Tests are standalone Python scripts
- **Integration tests**: `tests/test_full_pipeline.py`, `tests/test_3d_api_integration.py`
- **Unit tests**: `tests/test_feature_constraints.py`, `tests/test_wind_porosity.py`
- **Benchmarks**: `tests/benchmark_street_canyon.py`
- **Run all tests** before major changes (no single command)

## Git Workflow

- **No pre-commit hooks**
- **Manual testing** required before commits
- **Branch naming**: Use descriptive names (e.g., `feature/add-svf-metric`)
- **Commit messages**: Clear, concise, imperative mood

## Resources

- **PyRibs docs**: https://docs.pyribs.org/ (GridArchive, Emitters, Scheduler)
- **Dash docs**: https://dash.plotly.com/ (callbacks, components)
- **GeoPandas**: https://geopandas.org/ (CRS, spatial joins)
- **NRW Open Data**: https://www.opengeodata.nrw.de/ (LOD2, ALKIS)

## Common Pitfalls and Solutions

### 1. Test Files with Hardcoded Paths
**Problem**: Tests have `sys.path.insert(0, '/home/alex/Documents/...')`
**Solution**: Comment out or adjust to `/home/runner/work/openskizze-gui/openskizze-gui`

### 2. Empty Archive After Optimization
**Problem**: All solutions have fitness 0.0, archive stays empty
**Solutions**:
- Switch from `simple_porosity` to `street_canyon` objective (dense urban)
- Reduce constraints (max_height, min_distance)
- Check `/diagnostic` page for fitness values
- Verify feature ranges aren't too narrow

### 3. CRS Confusion
**Problem**: Buildings/parcels appear in wrong location
**Solution**: Always convert to/from correct CRS:
- NRW data native: EPSG:25832 (UTM)
- Web map display: EPSG:4326 (WGS84)
- Use `geopandas.to_crs()` for all conversions

### 4. Missing Bilingual Strings
**Problem**: New UI shows undefined or English-only text
**Solution**: Always add both:
```python
T['DE']['MY_NEW_LABEL'] = "Deutscher Text"
T['EN']['MY_NEW_LABEL'] = "English Text"
```

### 5. Performance Regression in Evaluation
**Problem**: Optimization becomes slow after changes
**Solution**:
- Profile: `python -m cProfile -o out.prof your_script.py`
- Avoid: `scipy.ndimage.label()` calls (use cached result)
- Avoid: Python loops over arrays (use NumPy broadcasting)
- Check: 2D rotation before 3D conversion (not after)

### 6. Dash Callback Errors
**Problem**: Callback not triggering or multiple updates
**Solution**:
- Use `prevent_initial_call=True` to avoid startup triggers
- Check Output/Input/State IDs match component IDs exactly
- Use `no_update` to skip updates conditionally
- Pattern-matching: `{'type': 'plot', 'index': ALL}` for dynamic components

## Anti-Patterns to Avoid

1. **Breaking the genome dimension** (must stay 60)
2. **Modifying working tests** unrelated to your task
3. **Changing CRS** without updating all conversions
4. **Adding Python loops** in evaluation.py (use NumPy)
5. **Forgetting bilingual strings** (DE + EN required)
6. **Removing caching** (critical for performance)
7. **Using pickle for new features** (security risk)
8. **Ignoring physical units** (always meters, m²)
9. **Calling `scipy.ndimage.label()` multiple times** (cache it)
10. **Rotating 3D arrays** instead of 2D heightmaps

## File Modification Checklist

Use this checklist to ensure you haven't forgotten anything:

**Adding a new feature/measure:**
- [ ] `backend/config.py` - Add to DOMAIN_CONFIG['features'] and feat_ranges
- [ ] `backend/evaluation.py` - Implement in calculate_all_features()
- [ ] `backend/translation.py` - Add T['DE']['MEASURE_X'] and T['EN']['MEASURE_X']
- [ ] `backend/units.py` - Add to FEATURE_UNITS dictionary
- [ ] Test with sample optimization

**Adding a new objective function:**
- [ ] `backend/evaluation.py` - Implement compute_fitness_X()
- [ ] `backend/evaluation.py` - Add dispatch in eval_solution()
- [ ] `pages/step2_constraints.py` - Add UI radio button
- [ ] `backend/translation.py` - Add bilingual labels
- [ ] `backend/optimization_process.py` - Pass to env_config
- [ ] Create test file (see test_street_canyon.py)

**Adding a new constraint:**
- [ ] `backend/evaluation.py` - Add check in check_constraints()
- [ ] `pages/step2_constraints.py` - Add UI input field
- [ ] `backend/translation.py` - Add bilingual labels
- [ ] Wire callback to pass constraint to optimizer

**Adding a new UI page:**
- [ ] Create `pages/stepX_name.py` with layout() function
- [ ] Register callbacks in the page module
- [ ] Add navigation link in app.py
- [ ] Add route in app.py display_page() callback
- [ ] Add bilingual page title to backend/translation.py

**Modifying data fetching:**
- [ ] `backend/data_io.py` - Update fetch functions
- [ ] Test with different bounding boxes
- [ ] Check CRS conversions (EPSG:25832 ↔ EPSG:4326)
- [ ] Verify cache directory handling

## Quick Reference Commands

```bash
# Start app
python run.py

# Run single test
python tests/test_feature_constraints.py

# Check imports (no linting)
python -c "from backend.evaluation import *; print('OK')"

# Profile optimization (if needed)
python -m cProfile -o output.prof tests/test_full_pipeline.py

# Clean cache
rm -rf cache/lod2_tiles/*

# Check git status
git status --short

# Quick smoke test (check all imports work)
python -c "from app import app; print('App imports OK')"

# Check if feature calculation works
python -c "from backend.evaluation import calculate_all_features; import numpy as np; print(calculate_all_features(np.random.rand(32,32)*10, np.ones((32,32), bool), 3072.0))"
```

## Troubleshooting Flowchart

### Problem: "Archive is empty after optimization"
1. Check `/diagnostic` page - are fitness values 0.0?
   - YES → Switch objective from 'simple_porosity' to 'street_canyon'
   - NO → Check if feature ranges are too narrow
2. Are constraints too restrictive?
   - Increase max_height or decrease min_distance
3. Still empty?
   - Increase num_generations (100 → 500)
   - Check buildable mask isn't too small

### Problem: "Code is too slow"
1. Did you modify `backend/evaluation.py`?
   - YES → Profile with `python -m cProfile`
   - Check if you added Python loops (use NumPy instead)
   - Check if you call `scipy.ndimage.label()` multiple times (cache it)
2. Did you change rotation logic?
   - Ensure rotating 2D heightmaps, NOT 3D arrays
3. Normal slowness:
   - 3-4 minutes for 1000 generations is expected

### Problem: "Import errors or module not found"
1. Check Python version: `python3 --version` (need 3.12)
2. Install dependencies using mamba: `mamba install --file requirements.txt`
3. Alternative: Use pip within mamba environment: `pip install -r requirements.txt`
4. Check repo is in path:
   - `export PYTHONPATH=/home/runner/work/openskizze-gui/openskizze-gui:$PYTHONPATH`

### Problem: "Buildings/parcels in wrong location"
1. Check CRS conversions:
   - NRW native data: EPSG:25832
   - Web map: EPSG:4326
2. Use `geopandas.to_crs()` for all conversions
3. Check `backend/data_io.py` for conversion patterns

### Problem: "UI not showing my changes"
1. Check Dash callback:
   - Output/Input/State IDs match component IDs?
   - Using `prevent_initial_call=True`?
   - Callback registered in correct page module?
2. Clear browser cache (Ctrl+Shift+R)
3. Restart app: kill `python run.py` and restart

### Problem: "Tests failing with path errors"
1. Check sys.path.insert statements in test files
2. Comment out hardcoded paths
3. Run from repo root: `python tests/test_X.py`
4. Or set: `export PYTHONPATH=$PWD:$PYTHONPATH`

## When You're Stuck

1. **Empty archive**: Check `/diagnostic` page, review constraints
2. **Slow optimization**: Profile with cProfile, check `helper/QUICK_REFERENCE.md`
3. **CRS errors**: Verify EPSG:25832 ↔ EPSG:4326 conversions
4. **Import errors**: Check requirements.txt versions, Python 3.12 compatibility
5. **UI not updating**: Check Dash callback dependencies, use `prevent_initial_call=True`
6. **Data fetching fails**: NRW APIs may be slow/down, check `backend/data_io.py` for fake parcel fallback

## Practical Example: Adding a Simple Check

Here's a step-by-step example following the instructions to add a minimum GRZ (site coverage) check:

```python
# 1. Add constraint to backend/config.py (if needed for defaults)
# No changes needed - constraints come from UI

# 2. Update backend/evaluation.py check_constraints()
def check_constraints(heightmap: np.ndarray, constraints: dict):
    is_violated = False
    
    # ... existing max_height and min_distance checks ...
    
    # NEW: Min GRZ (site coverage ratio) check
    min_grz = constraints.get('min_grz')
    if min_grz is not None and min_grz > 0:
        pixel_size = DOMAIN_CONFIG['pixel_size_in_meters']
        occupied_pixels = np.sum(heightmap > 0)
        total_pixels = heightmap.shape[0] * heightmap.shape[1]
        actual_grz = occupied_pixels / total_pixels if total_pixels > 0 else 0
        
        if actual_grz < min_grz:
            is_violated = True
    
    return heightmap, is_violated

# 3. Add UI control in pages/step2_constraints.py
# In hard constraints section:
dbc.Label(T[lang]['STEP2_MIN_GRZ_LABEL']),
dbc.Input(
    id='min-grz-input',
    type='number',
    min=0.0, max=1.0, step=0.05,
    placeholder=T[lang]['STEP2_MIN_GRZ_PLACEHOLDER']
),

# 4. Add translations to backend/translation.py
T['DE']['STEP2_MIN_GRZ_LABEL'] = "Minimale Grundflächenzahl (GRZ):"
T['DE']['STEP2_MIN_GRZ_PLACEHOLDER'] = "z.B. 0.2 (= 20% Bebauung)"
T['EN']['STEP2_MIN_GRZ_LABEL'] = "Minimum site coverage (GRZ):"
T['EN']['STEP2_MIN_GRZ_PLACEHOLDER'] = "e.g. 0.2 (= 20% coverage)"

# 5. Wire up callback to pass constraint to optimizer
# (in step2_constraints.py or step3_optimize.py)
```

This example demonstrates:
- Physical units (ratio 0-1)
- Bilingual strings
- Minimal changes (only 4 files)
- Following existing patterns

## Success Criteria for Changes

- [ ] Code runs without errors (test with `python run.py`)
- [ ] No breaking changes to existing features
- [ ] Physical units used correctly (meters, m²)
- [ ] Bilingual strings added (DE + EN)
- [ ] Performance not degraded (profile if touching evaluation.py)
- [ ] Documentation updated (if user-facing feature)
- [ ] Tests pass (run relevant test_*.py files)
- [ ] Git diff minimal (only changed files committed)
