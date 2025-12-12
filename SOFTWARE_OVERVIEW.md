# OpenSKIZZE: Software Overview

**Climate-Aware Urban Design Exploration with Quality-Diversity Optimization**

**Version**: December 2025  
**Authors**: Alexander Hagg et al.  
**Status**: Prototype / Research Software

---

## Table of Contents

1. [Introduction and Motivation](#1-introduction-and-motivation)
2. [System Architecture](#2-system-architecture)
3. [Core Algorithms](#3-core-algorithms)
4. [User Workflow](#4-user-workflow)
5. [Data Integration](#5-data-integration)
6. [Performance Optimization](#6-performance-optimization)
7. [Machine Learning Surrogates](#7-machine-learning-surrogates)
   - 7.1 KLAM_21 Background
   - 7.2 SVGP Model
   - 7.3 U-Net Model
   - 7.4 Hybrid Mode
8. [Visualization and Analysis](#8-visualization-and-analysis)
9. [Export and Reporting](#9-export-and-reporting)
10. [Internationalization](#10-internationalization)
11. [Validation and Benchmarks](#11-validation-and-benchmarks)
12. [Limitations and Future Work](#12-limitations-and-future-work)
13. [Installation and Usage](#13-installation-and-usage)
14. [Conclusion](#14-conclusion)

---

## 1. Introduction and Motivation

### 1.1 The Urban Planning Challenge

Urban planners face significant computational barriers when exploring design alternatives that simultaneously address:

- **Climate adaptation**: Wind flow for ventilation, heat mitigation, cold air preservation
- **Morphological diversity**: Exploring varied building configurations rather than converging on a single "optimal" solution
- **Planning regulations**: Compliance with German building codes (GRZ, GFZ, setbacks, height limits)
- **Stakeholder communication**: Transparent, interpretable metrics that non-technical stakeholders can understand

Traditional approaches suffer from fundamental limitations. Single-objective optimization converges to one "best" solution, failing to capture the diversity of viable alternatives that planners need for informed decision-making. Manual iteration is slow and subject to designer bias. Computational Fluid Dynamics (CFD) simulations, while accurate, require hours per evaluation—making them impractical for early-stage exploration where hundreds of alternatives should be considered.

### 1.2 The OpenSKIZZE Solution

OpenSKIZZE addresses these challenges through **Quality-Diversity (QD) optimization**—an approach that simultaneously optimizes for performance (climate metrics) while maintaining diversity across morphological characteristics. Rather than finding a single optimal design, OpenSKIZZE generates 100-1,000+ diverse solutions in a single optimization run, each representing a distinct design "strategy" that performs well within its morphological niche.

The system is purpose-built for urban planners in **North Rhine-Westphalia (NRW), Germany**, integrating directly with official German geodata sources (LOD2 CityGML building data, ALKIS parcel data) and using German planning terminology (*Grundflächenzahl*, *Geschossflächenzahl*, *städtebaulicher Entwurf*).

### 1.3 Target Users and Use Cases

**Primary Users**: Urban planners in municipal planning offices (*Stadtplanungsamt*)

**Typical Workflow Context**:
- Creating conceptual urban designs (*städtebauliche Entwürfe*)
- Early-phase B-Plan feasibility studies (*Bebauungsplan* preparation)
- Workshop facilitation with stakeholders
- Pre-feasibility screening of development sites

**User Expertise Profile**: High domain knowledge (planning law, urban morphology), low technical tolerance (no coding/scripting expected). German technical terminology (*Fachsprache*) is required.

---

## 2. System Architecture

### 2.1 Technology Stack

OpenSKIZZE is a web-based application built with Python, designed for local deployment on planning workstations.

**Core Framework**:
- **Python 3.12**: Primary programming language
- **Dash 2.17 + Flask**: Web application framework providing interactive UI
- **PyRibs 0.6.1**: Quality-Diversity optimization library (GridArchive, GaussianEmitter, Scheduler)
- **Numba 0.59**: JIT compilation for performance-critical numerical code

**Scientific Computing**:
- **NumPy 1.26, SciPy 1.13**: Numerical operations and array processing
- **scikit-learn, HDBSCAN**: Machine learning and clustering algorithms
- **PyTorch + GPyTorch**: Deep learning and Gaussian process models (for ML surrogates)

**Geospatial**:
- **GeoPandas 0.14, Shapely 2.0, Fiona 1.9**: GIS operations and geometry handling
- **Dash-Leaflet 1.0**: Interactive web maps with OpenStreetMap base layers
- **Plotly 5.22**: 3D visualization and interactive charts

**Data Sources**:
- **NRW LOD2 CityGML**: Building geometries with measured heights (3D city model)
- **NRW ALKIS WFS**: Parcel boundaries via Web Feature Service
- **OpenStreetMap**: Base cartography for map display

### 2.2 Repository Structure

The codebase is organized into distinct functional modules:

```
openskizze/
├── app.py                      # Dash application initialization, routing, callbacks
├── run.py                      # Application entry point
├── requirements.txt            # Python dependencies
│
├── backend/                    # Core logic (~8,000 lines of code)
│   ├── config.py               # QD and domain hyperparameters
│   ├── encoding.py             # Parametric genome (60 genes → heightmap)
│   ├── fast_encoding.py        # Optimized encoding with Numba JIT
│   ├── evaluation.py           # Fitness functions, feature calculations, constraints
│   ├── optimizer.py            # PyRibs QD optimization loop
│   ├── optimization_process.py # Pipeline orchestration
│   ├── data_io.py              # LOD2/ALKIS data fetching and parsing
│   ├── analysis.py             # Clustering, consensus maps, PDF reports
│   ├── model_evaluator.py      # ML surrogate model interface (SVGP, U-Net)
│   ├── surrogate_evaluator.py  # Wrapper for surrogate integration
│   ├── svgp.py                 # Sparse Variational Gaussian Process model
│   ├── unet.py                 # U-Net neural network architecture
│   ├── translation.py          # German/English UI strings
│   ├── units.py                # Physical unit conversions
│   └── project_state.py        # Session save/load functionality
│
├── pages/                      # UI pages (Step 1-6 workflow)
│   ├── step1_scope.py          # Parcel selection, wind direction
│   ├── step2_constraints.py    # Feature/constraint configuration
│   ├── step3_optimize.py       # QD execution with progress updates
│   ├── step4_analysis.py       # Archive exploration and visualization
│   ├── step5_clustering.py     # Solution clustering and archetypes
│   ├── step6_compare_detail.py # Side-by-side 3D comparison
│   ├── step_diagnostic.py      # Debug view for empty archives
│   └── step_model_diagnostics.py # ML model testing interface
│
├── models/                     # Pre-trained ML surrogate models
│   ├── svgp.pth                # SVGP model for cold air flux prediction
│   └── unet_*.pth              # U-Net models (size-specific)
│
├── cache/                      # Local cache for downloaded data
│   └── lod2_tiles/             # Downloaded LOD2 CityGML tiles
│
├── assets/                     # Static web assets
│   ├── style.css               # Custom CSS styling
│   ├── camera_sync.js          # Client-side 3D camera synchronization
│   └── logo.png                # Application branding
│
└── tests/                      # Benchmark and validation scripts
```

### 2.3 Data Flow

The system processes data through a sequential pipeline:

1. **User Input** (Steps 1-2): Parcel geometry, wind direction, constraints, feature selection → stored in `session-store`
2. **Optimization** (Step 3): QD algorithm generates diverse solutions → stored in `results-store`
3. **Analysis** (Steps 4-5): Clustering, archetype extraction → stored in `comparison-store`
4. **Export** (Step 6): PDF reports, GeoJSON exports

All geometry calculations maintain **physical units** (meters, square meters) throughout the pipeline, enabling direct comparison with German planning regulations.

---

## 3. Core Algorithms

### 3.1 Quality-Diversity Optimization

OpenSKIZZE uses **MAP-Elites** (Multi-dimensional Archive of Phenotypic Elites), a Quality-Diversity algorithm that maintains a grid-based archive of solutions. Unlike traditional optimization that finds a single optimum, MAP-Elites fills a multi-dimensional grid where each cell represents a unique combination of behavioral characteristics.

**Implementation via PyRibs**:
- **GridArchive**: Stores the best solution for each niche (behavior cell)
- **GaussianEmitter**: Generates new solutions by mutating existing elites
- **Scheduler**: Coordinates emitters and manages the optimization loop

**Typical Configuration**:
```python
archive = GridArchive(
    solution_dim=60,                    # Genome dimension (FIXED)
    dims=[5, 5, 5, 5, 5, 5, 5, 5],      # 5 niches × 8 features
    ranges=[(0, 1), (0, 3), ...],       # Physical-unit ranges
    learning_rate=0.01,
    threshold_min=0.0
)
```

**Key Properties**:
- Archive stores the **best-performing solution** in each behavioral niche
- New solutions that outperform existing niche occupants replace them
- Diversity is guaranteed by the grid structure (each cell = distinct behavior)
- Typical runs: 100-1,000 generations, producing 8,000-80,000 total evaluations

### 3.2 Parametric Encoding

The system uses a **parametric genome** that encodes building layouts as a fixed-length vector:

**Genome Structure**: 60 genes = 10 buildings × 6 parameters per building

For each building:
1. **Width** (gene 0): Building width in grid cells
2. **Length** (gene 1): Building length in grid cells  
3. **Height** (gene 2): Building height in floors (converted to meters via 3m/floor)
4. **X position** (gene 3): Centroid X coordinate
5. **Y position** (gene 4): Centroid Y coordinate
6. **Active** (gene 5): Whether building exists (>0 = active)

**Genotype-to-Phenotype Mapping**:
```
Genome (60 floats in N(0,1)) 
    → CDF transform to [0,1]
    → Scale to physical dimensions
    → 2D heightmap (meters) with buildable mask applied
```

The encoding is **JIT-optimized** with Numba, achieving 165× speedup over pure Python loops.

### 3.3 Fitness Functions (Climate Surrogates)

OpenSKIZZE provides multiple objective functions for evaluating wind flow and climate performance:

#### 3.3.1 Simple Porosity (Geometric)

Counts completely open horizontal wind corridors through a 3D voxel representation:
- Rotate environment to align with wind direction
- Count rows where wind can pass unobstructed at each height level
- Return fraction of open paths (0.0 = fully blocked, 1.0 = fully open)

**Best for**: Sparse, suburban layouts with significant open space.

**JIT Optimization**: 41× faster than scipy-based rotation.

#### 3.3.2 Street Canyon Ventilation (Geometric)

Multi-component surrogate capturing urban canyon aerodynamics:
- **Ground corridors** (35%): Open passages at pedestrian level
- **Lateral ventilation** (25%): Cross-street airflow potential
- **Height variation** (15%): Turbulence from stepped massing
- **Partial penetration** (25%): Weighted by blockage factor

**Best for**: Dense urban contexts where simple porosity returns 0.0.

**JIT Optimization**: 28× faster than scipy-based rotation.

#### 3.3.3 SVGP Surrogate (Machine Learning)

**Sparse Variational Gaussian Process** trained on KLAM_21 (German Weather Service cold air model) simulation data:
- Predicts cold air volume flow (m³/s) through the parcel
- Provides **uncertainty estimates** enabling UCB (Upper Confidence Bound) exploration
- Single model works for all parcel sizes (parcel dimensions as input features)
- Inference: <10ms per evaluation

**Advantage**: Physics-informed predictions aligned with official German climate assessment methodology.

#### 3.3.4 U-Net Surrogate (Machine Learning)

**Convolutional neural network** providing pixelwise flow field predictions:
- Trained on KLAM_21 simulation data (katabatic cold air flow)
- Returns full velocity field for visualization
- Size-specific models (60m, 120m, 240m parcels)
- Inference: ~1-5ms per evaluation

**Advantage**: Visual flow field output for stakeholder communication.

#### 3.3.5 Hybrid Mode

Combines U-Net fitness with SVGP uncertainty for optimal exploration-exploitation balance.

### 3.4 Feature Calculations (Archive Dimensions)

Solutions are characterized by **8 morphological features** serving as archive axes:

| Feature | Unit | Description |
|---------|------|-------------|
| **GRZ** | ratio (0-1) | *Grundflächenzahl* - site coverage (built footprint / parcel area) |
| **GFZ** | ratio | *Geschossflächenzahl* - floor area ratio (total floor area / parcel area) |
| **Average Height** | meters | Mean building height across all buildings |
| **Height Variability** | meters | Standard deviation of building heights |
| **Number of Buildings** | count | Total active buildings in layout |
| **Average Distance** | meters | Mean centroid-to-centroid spacing between buildings |
| **Compactness** | ratio | Surface-to-volume ratio (A/V) - lower = more energy efficient |
| **Park Factor** | meters | Largest inscribed open circle radius (green space potential) |

All features maintain **physical units** throughout the pipeline, enabling direct regulatory compliance checking.

### 3.5 Constraint Handling

**Hard Constraints** (violation → fitness = -1, solution rejected):
- **Maximum height**: User-defined limit in floors/meters, enforced via clipping
- **Minimum building distance**: Checked via binary erosion morphological operation
- **Buildable mask**: Only build within parcel boundary

**Soft Constraints** (target ranges):
- Users define acceptable ranges for each feature
- Archive grid is configured to span these ranges
- Solutions outside ranges still evaluated but may occupy peripheral niches

---

## 4. User Workflow

OpenSKIZZE implements a **6-step linear workflow** designed for urban planners with high domain expertise but low technical tolerance. The interface includes a visual **breadcrumb navigation** showing progress through steps, with completed steps marked for easy backtracking.

### 4.1 Step 1: Scope Definition (*Geltungsbereich*)

**Purpose**: Select the planning parcel and set climatic context.

**UI Components** (implemented in `pages/step1_scope.py`):

**Interactive Map** (Dash-Leaflet):
- OpenStreetMap base layer with zoom/pan controls
- Parcel overlay layer with click-to-select functionality
- Drawing tools (polygon, rectangle) for manual boundary definition
- Edit controls for adding/subtracting areas from selection
- Green highlighting of selected/active parcel

**Parcel Selection Methods**:
1. **GeoJSON Upload**: Direct file upload of parcel boundary geometry
2. **NRW ALKIS WFS Query**: "Load Parcels" button fetches cadastral data (*Flurstücke*) for the current map extent; click to select individual parcels
3. **Manual Drawing**: Use polygon/rectangle tools to draw custom boundaries
4. **Combined Workflow**: Start with ALKIS parcel, then add/subtract using drawing tools

**Wind Direction Compass**:
- Interactive compass widget with rotating needle
- Click-to-set wind direction (meteorological convention: 270° = wind from west)
- Visual feedback of selected direction
- Integration point for future climate model data import

**Parcel Information Panel**:
- Real-time display of selected area (m²)
- Bounding box dimensions (width × length in meters)
- Coordinate reference system handling (automatic WGS84 ↔ UTM conversion)

**Automatic Data Fetching**:
- On parcel selection, system automatically:
  - Calculates buildable area and grid resolution
  - Fetches LOD2 building tiles for the surrounding area
  - Parses building heights from CityGML `measuredHeight` attribute
  - Caches tiles locally for subsequent runs

**Model Diagnostics Link**:
- Button to open Model Diagnostics page (see Section 4.7)
- Allows testing objective functions on archetypal patterns before optimization

**Output**: Parcel geometry, grid parameters (xy_length, pixel_size), wind direction, existing building context (3D array in meters).

---

### 4.2 Step 2: Constraints and Features (*Randbedingungen*)

**Purpose**: Configure the optimization search space and evaluation method.

**UI Components** (implemented in `pages/step2_constraints.py`):

**Hard Constraints Panel**:
- **Maximum Building Height**: Slider from 3m to 60m (in 3m increments, representing floors)
  - Default: 12m (4 floors)
  - Visual display of current value
- **Minimum Building Distance**: Slider from 0m to 30m
  - Default: 5m
  - Enforced via binary erosion morphological operation

**Feature Selection**:
- Checklist of 8 morphological features (all selected by default)
- Switch toggles for each feature
- Selected features become archive dimensions

**Presets** (Quick Configuration):
- **Suburban** (*Vorstadt*): Lower density, more spacing
  - Features: GRZ, GFZ, Height, Distance, Count, Park Factor
  - Ranges: GRZ 0.1-0.4, GFZ 0.2-0.8, Heights 3-12m, Distance 10-30m
- **Dense Urban** (*Dichte Stadt*): Higher density, compact forms
  - Features: GRZ, GFZ, Height, Distance, Compactness, Park Factor
  - Ranges: GRZ 0.4-0.8, GFZ 1.0-3.0, Heights 12-24m, Distance 5-15m

**Target Range Sliders**:
- One dual-handle range slider per selected feature
- Shows physical units (m, m², ratio)
- Default ranges from DOMAIN_CONFIG, adjustable by user
- Defines the search space for QD optimization

**Evaluation Method Selector**:
- Radio buttons for objective function choice:
  - **Simple Porosity** (geometric): Fast, good for sparse layouts
  - **Street Canyon** (geometric): Better for dense urban contexts (default)
  - **SVGP** (ML): Provides uncertainty estimates, KLAM-aligned
  - **U-Net** (ML): Provides flow field visualization
  - **Hybrid** (ML): U-Net fitness + SVGP uncertainty
- Model availability indicator (checks for model files)
- UCB lambda slider (0.0-3.0) for exploration parameter (ML modes only)

**Advanced Mode Toggle**:
- Hidden by default to reduce complexity for non-technical users
- When enabled, exposes QD hyperparameters:
  - **Number of Generations**: 100-2000 (default: 1000)
  - **Number of Emitters**: 3-15 (default: 5-10)
  - **Niche Resolution**: 3-7 niches per dimension (default: 5)
  - **Batch Size**: 8-64 (default: 32)

**Output**: Complete optimization configuration stored in session-store.

---

### 4.3 Step 3: Optimization (*Optimierung*)

**Purpose**: Execute QD optimization and monitor progress.

**UI Components** (implemented in `pages/step3_optimize.py`):

**Start Button**:
- Large, prominent "Start Optimization" button
- Disabled while optimization is running
- Color changes to indicate state (green → gray during run)

**Progress Monitoring**:
- **Progress Bar**: Visual percentage complete with label
- **Progress Text**: "Generation X of Y" status message
- Updates at configurable interval (default: every 10 generations)
- Estimated time remaining (based on elapsed time)

**Background Execution**:
- Uses Dash DiskcacheManager for background callbacks
- Non-blocking UI during optimization
- Intermediate results saved to temp_results/ directory
- Automatic cleanup of old temporary files (>24 hours)

**Live Archive Updates** (optional):
- Archive heatmap updates every N generations
- Shows solution space filling in real-time
- Provides visual feedback during long runs

**Technical Details**:
- Multiprocessing pool for parallel evaluation
- CPU count auto-detection (uses N-2 cores)
- Memory management for large archives
- Error handling with informative messages

**Performance Metrics** (typical run):
- 1,000 generations: 3-8 minutes
- 50,000-80,000 candidate evaluations
- 20-80% archive coverage depending on constraints

**Output**: Populated archive saved to results-store and disk (pickle format).

---

### 4.4 Step 4: Results Analysis (*Ergebnisanalyse*)

**Purpose**: Explore the solution space and understand trade-offs.

**UI Components** (implemented in `pages/step4_analysis.py`):

**Filter Controls** (top row):
- Compact horizontal layout
- Range sliders for each feature to filter displayed solutions
- **Filter Statistics**: Shows "X of Y solutions" matching current filters
- Axis selection dropdowns (X-axis, Y-axis) for heatmap

**Three-Column Visualization Layout**:

*Column 1: Archive Visualizations*
- **Solution Archive Grid**: Tiled 2D miniature heightmaps showing solutions in each occupied niche
  - Click to select individual solutions
  - Color-coded by fitness value
- **Archive Heatmap**: 2D projection of archive occupancy
  - User-selectable X/Y axes from feature list
  - Color intensity = objective value (fitness)
  - Grid overlay shows niche boundaries
  - Interactive hover shows solution details

*Column 2: Distribution Analysis*
- **Parallel Coordinates Plot**: Multi-dimensional visualization
  - One vertical axis per feature
  - Lines connect feature values for each solution
  - Color-coded by fitness
  - Interactive: click axis to reorder
  - Brush selection to filter solutions
- **Correlation Heatmap**: Pairwise feature correlations
  - Pearson correlation coefficients
  - Color scale: red (negative) → white (zero) → blue (positive)
  - Helps identify redundant or conflicting features

*Column 3: Feature-Objective Analysis*
- **Feature vs. Objective Plots**: Scatter plots for each feature
  - X-axis: Feature value
  - Y-axis: Objective (fitness) value
  - Shows relationship between morphology and performance
  - Trend lines for correlation visualization

**Uncertainty Visualization** (ML modes only):
- Toggle switch to show/hide uncertainty heatmap
- Displays SVGP variance across solution space
- High uncertainty regions indicate areas for further exploration

**Output**: Visual understanding of solution landscape, filtered solution sets.

---

### 4.5 Step 5: Clustering (*Clusteranalyse*)

**Purpose**: Identify distinct "design families" (archetypes) for comparison.

**UI Components** (implemented in `pages/step5_clustering.py`):

**Similarity Metric Selection**:
- **t-SNE** (default): Dimensionality reduction to 2D, then Euclidean distance
  - Good for general morphological similarity
  - Fast computation
- **SSIM** (Structural Similarity Index): Topology-aware comparison
  - Better at identifying shifted/rotated but similar designs
  - Preserves structural relationships
  - Uses PyTorch for GPU-accelerated batch computation

**Clustering Algorithm Selection**:
- **Hierarchical** (default): Agglomerative clustering
  - User-specified number of clusters (2-20, slider)
  - Produces balanced, interpretable clusters
- **HDBSCAN**: Density-based clustering
  - Automatic cluster count detection
  - Identifies outliers as noise
  - Minimum cluster size: 5 (configurable)
- **K-Medoids**: Partition-based clustering
  - Cluster centers are actual solutions (not averages)
  - User-specified K (2-50)
  - Good for extracting representative archetypes

**Parameter Controls**:
- Dynamic slider visibility based on algorithm selection
- Real-time parameter adjustment
- "Run Analysis" button to execute clustering

**Cluster Results Display**:
- **Cluster Overview**: Summary statistics per cluster
  - Cluster size (number of solutions)
  - Average fitness
  - Feature ranges within cluster
- **Cluster Visualization**: 
  - t-SNE scatter plot with cluster coloring
  - Solution maps colored by cluster assignment
- **Archetype Extraction**:
  - Central solution (medoid) per cluster
  - Best-performing solution per cluster
  - Visual comparison of archetypes

**Compare Button**:
- Appears after clustering completes
- Links to Step 6 for detailed comparison
- Passes selected clusters to comparison view

**Output**: Cluster assignments, extracted archetypes stored in clustering-data-store.

---

### 4.6 Step 6: Comparison and Export (*Vergleich & Export*)

**Purpose**: Compare design archetypes side-by-side and generate deliverables.

**UI Components** (implemented in `pages/step6_compare_detail.py`):

**3D Visualization Panel**:
- **Synchronized 3D Views**: Multiple Plotly 3D plots with camera synchronization
  - Client-side JavaScript for real-time camera sync (camera_sync.js)
  - Rotate one view, all views update simultaneously
  - Essential for fair visual comparison
- **Voxel Building Representation**:
  - Buildings rendered as solid 3D blocks
  - Geographic coordinates (EPSG:25832) for accurate positioning
  - Height exaggeration option for emphasis
  - Wireframe edges for building delineation
- **Color Coding**:
  - New buildings: Blue tones (viridis colorscale by height)
  - Existing context: Gray/neutral tones
  - Distinct colors per cluster (HSV color generation avoiding blue)
- **Existing Buildings Context**:
  - LOD2 buildings shown as gray context
  - Toggle to show/hide existing buildings
  - Height-accurate representation from CityGML data

**Metrics Comparison Table**:
- Side-by-side feature values for selected archetypes
- All 8 features with physical units
- Objective function value (fitness)
- Cluster size as percentage of archive (**design robustness**)
- Highlighting of best values per metric

**Flow Field Visualization** (U-Net/Hybrid modes):
- Toggle to show/hide flow field overlay
- Velocity vectors or streamlines
- Color-coded by flow magnitude
- Overlaid on 3D building visualization

**Export Options**:

*PDF Report Generation* (via PyLaTeX):
- **Correlation Heatmap**: Feature relationships
- **Archetype Visualizations**: 3D renderings and 2D plans
- **Comparative Metrics Table**: All features and objectives
- **Planning Narrative**: German/English text describing findings
- **Provenance Information**: Settings, timestamps, model versions
- Automatic LaTeX compilation to PDF

*GeoJSON Export*:
- Georeferenced building polygons
- Height attributes per polygon
- CRS metadata (EPSG:25832)
- Compatible with QGIS, ArcGIS, CAD software

*Project Save*:
- Complete session state saved to `.skizze` file
- Includes archive, clustering results, settings
- Pickle format (development only; security considerations for production)

**Output**: PDF report, GeoJSON files, saved project state.

---

### 4.7 Auxiliary Pages

#### Model Diagnostics Page

**Purpose**: Test and compare objective functions on archetypal urban patterns before running full optimization.

**UI Components** (implemented in `pages/step_model_diagnostics.py`):

**Archetype Gallery**:
- Pre-defined test patterns representing common urban morphologies:
  - Single Block, Row Buildings, Perimeter Block, Tower Group
  - Scattered, Dense Grid, Open Courtyard, L-Shape
- 3D visualization of each archetype
- Description of morphological characteristics

**Objective Function Comparison**:
- Run all evaluation methods on selected archetypes
- Side-by-side fitness scores
- Correlation analysis between methods
- Helps users choose appropriate objective for their context

**Model Availability Check**:
- Shows which ML models are available for current parcel size
- Indicates missing model files
- Provides guidance on model selection

#### Diagnostic Page

**Purpose**: Debug empty archives and understand fitness calculation failures.

**UI Components** (implemented in `pages/step_diagnostic.py`):

**Step-by-Step Fitness Visualization**:
- Shows intermediate steps of fitness calculation
- 2D heightmap → 3D voxel grid → rotated environment → porosity calculation
- Side-by-side comparison of Simple Porosity vs Street Canyon methods

**Component Breakdown**:
- Street Canyon components: ground corridors, lateral ventilation, height variation, partial penetration
- Individual scores and weights for each component
- Helps identify why certain configurations score poorly

**Random Solution Testing**:
- Generate and evaluate random solutions
- Visualize distribution of fitness values
- Identify if constraints are too restrictive

This page is accessed from Step 1 and is particularly useful when optimization produces empty archives (all solutions have fitness = 0).

---

## 5. Data Integration

### 5.1 NRW LOD2 Building Data

OpenSKIZZE integrates with the **NRW Open Data Portal** for official 3D building data.

**Data Source**: LOD2 CityGML files from NRW Geobasis
- 1km × 1km tile grid covering all of NRW
- `measuredHeight` attribute provides actual building heights (meters above ground)
- CRS: EPSG:25832 (UTM Zone 32N)

**Implementation**:
```python
# Tile discovery based on parcel bounding box
tiles = bbox_to_tiles(min_x, min_y, max_x, max_y, tile_size=1000)

# Download and cache tiles
for (tile_x, tile_y) in tiles:
    gml_file = download_lod2_tile(tile_x, tile_y)
    buildings = parse_citygml_lod2_tile(gml_file, bbox=parcel_bbox)
```

**Features**:
- Automatic tile discovery based on parcel location
- Local caching to avoid repeated downloads (cache hit rate >90%)
- Graceful fallback if data unavailable
- Duplicate building detection and removal

### 5.2 NRW ALKIS Parcel Data

**Data Source**: ALKIS Vereinfacht WFS (simplified cadastral parcels)
- URL: `https://www.wfs.nrw.de/geobasis/wfs_nw_alkis_vereinfacht`
- Contains parcel boundaries (*Flurstücke*) for NRW

**Features**:
- Query by bounding box (current map extent)
- Automatic CRS conversion (EPSG:25832 ↔ EPSG:4326)
- Fallback to synthetic parcel if WFS unavailable

### 5.3 Coordinate Reference Systems

The system handles two CRS throughout:

| Context | CRS | Description |
|---------|-----|-------------|
| Native data | EPSG:25832 | UTM Zone 32N (meters), used for NRW geodata |
| Web display | EPSG:4326 | WGS84 (lat/lon), used for Leaflet maps |

All conversions performed via GeoPandas `to_crs()` with explicit CRS specification.

---

## 6. Performance Optimization

Extensive performance optimization enables interactive exploration speeds previously requiring hours.

### 6.1 JIT Compilation

The evaluation pipeline was profiled and optimized using Numba JIT compilation:

| Component | Original | Optimized | Speedup |
|-----------|----------|-----------|---------|
| Phenotype expression | 1.0 ms | 0.006 ms | **165×** |
| Wind porosity | 2.5 ms | 0.061 ms | **41×** |
| Street canyon | 15 ms | 0.54 ms | **28×** |
| 3D mesh generation | 3.0 ms | 0.2 ms | **15×** |
| SVF ray-casting | 52 ms | 1.44 ms | **36×** |

**Critical Finding**: `scipy.ndimage.rotate` was consuming 40-50% of evaluation time. Replacing with manual nearest-neighbor rotation in JIT code eliminated this bottleneck.

### 6.2 Aggregate Impact

For the complete evaluation pipeline:

| Configuration | Time per eval | Throughput | Notes |
|---------------|---------------|------------|-------|
| Planning features (no JIT) | 14.5 ms | 69 sol/s | Baseline |
| Planning features (with JIT) | 0.53 ms | 1,884 sol/s | **27× faster** |

**Production projection** (50,000 evaluations):
- Without JIT: 12.1 minutes
- With JIT: 0.4 minutes
- **Time saved**: 11.7 minutes per optimization run

### 6.3 Multiprocessing

The optimizer uses Python multiprocessing for batch evaluation:
```python
nb_cpus = max(1, psutil.cpu_count(logical=True) - 2)
pool = multiprocessing.Pool(processes=nb_cpus)
results = pool.map(eval_solution, batch)
```

For ML surrogate evaluation, batched GPU inference replaces multiprocessing for better throughput.

---

## 7. Machine Learning Surrogates

### 7.1 KLAM_21 Background

**KLAM_21** (Klimaanalyse für das Land Nordrhein-Westfalen) is a katabatic cold air flow model developed by the German Weather Service (DWD). It simulates nighttime cold air drainage patterns over complex terrain, crucial for urban climate assessment.

**Why Cold Air Matters for Urban Planning**:
- Nighttime cold air flows provide natural ventilation and cooling
- Buildings can block or channel these flows, affecting thermal comfort
- Dense development in cold air drainage paths creates heat islands
- German planning regulations increasingly require climate impact assessment

**Training Data Generation Strategy**:
OpenSKIZZE's ML surrogates are trained on KLAM_21 simulation data generated via the SAIL (Surrogate-Assisted Illumination) algorithm:

| Parcel Type | Sizes | Description |
|-------------|-------|-------------|
| Square | 25m, 30m, 35m, 45m, 55m, 65m, 80m, 95m, 120m, 145m | Cover 49%–0.3% of urban plots |
| Rectangular | 30×20m, 35×20m, 45×30m, 50×25m, 65×45m | Common aspect ratios (1.5:1, 2:1) |

**Training Dataset Composition**:
- 5,000 elite genomes per parcel size (SAIL-optimized)
- 1,500 random genomes per size (Sobol sequence for conservative prior)
- Total: 15 sizes × 6,500 = **97,500 KLAM_21 runs**
- Data augmentation with random samples prevents overestimation of fitness

### 7.2 SVGP Model (Sparse Variational Gaussian Process)

**Purpose**: Fast, uncertainty-aware prediction of cold air flux.

**Training Data**: KLAM_21 simulations (German Weather Service)
- Katabatic cold air flow over varied terrain and building configurations
- Target: Cold air volume flow (m³/s) through domain

**Architecture**:
- Sparse Variational Gaussian Process (GPyTorch)
- Matérn 2.5 kernel with Automatic Relevance Determination (ARD)
- Input: 62D (60 genome parameters + 2 parcel dimensions)
- Output: Mean prediction + variance (uncertainty)
- Inducing points: 1,024 (reduces computational complexity from O(N³) to O(NM²))

**Key Advantage**: Single model works for all parcel sizes (parcel dimensions as input features). Normalization statistics stored in checkpoint.

**Conservative Prior**: Mean initialized to worst observed fitness; random samples in training data ensure the model predicts conservatively for unexplored regions.

### 7.3 U-Net Model

**Purpose**: Pixelwise flow field prediction for visualization.

**Training Data**: KLAM_21 simulations
- 3-channel input: terrain elevation, building heights, land use
- Output: Velocity field (u, v components)

**Architecture**:
- U-Net convolutional encoder-decoder
- Fixed input dimensions (66×94 grid at 3m resolution)
- Size-specific models for 60m, 120m, 240m parcels
- Trained on paired heightmap → velocity field data

**Key Advantage**: Provides visual flow field overlay for stakeholder communication, enabling intuitive understanding of how building placement affects airflow patterns.

### 7.4 Hybrid Mode

Combines strengths of both models:
- **Fitness**: U-Net prediction (most accurate for pixelwise metrics)
- **Uncertainty**: SVGP variance (for UCB exploration)

This enables exploration-exploitation balance via Upper Confidence Bound:
```
UCB(x) = μ(x) + λ × σ(x)
```
where λ controls the exploration-exploitation trade-off. Higher λ encourages exploration of uncertain regions; lower λ exploits known good solutions.

**Model Selection Logic**:
```python
if evaluation_method == "ml_surrogate":
    fitness, uncertainty = model_evaluator.evaluate(genome, parcel_dims)
elif evaluation_method == "hybrid":
    unet_fitness = unet_model.predict(heightmap)
    _, svgp_uncertainty = svgp_model.predict(genome, parcel_dims)
    fitness = unet_fitness
else:  # geometric
    fitness = geometric_evaluation(heightmap)
```

---

## 8. Visualization and Analysis

OpenSKIZZE provides comprehensive visualization capabilities for exploring and communicating design alternatives.

### 8.1 3D Building Visualization

**Technology**: Plotly 3D with custom mesh generation

**Rendering Approach**:
- Buildings rendered as solid voxel blocks using `go.Mesh3d`
- Optimized mesh generation: adjacent cells with same height merged into single mesh
- Reduces visual seams and improves rendering performance
- Wireframe edges added for building delineation

**Geographic Coordinate Mapping**:
```python
# Buildings positioned in real-world coordinates (EPSG:25832)
x_coords_geo = np.linspace(min_x, max_x, cols + 1)
y_coords_geo = np.linspace(min_y, max_y, rows + 1)
```

**Color Schemes**:
- **Height-based** (viridis): New buildings colored by height level
- **Cluster-based**: HSV-generated distinct colors per cluster (blue avoided for new designs)
- **Existing buildings**: Gray/neutral tones to distinguish from proposed designs

**Camera Synchronization**:
- Client-side JavaScript (`camera_sync.js`) synchronizes camera across multiple 3D views
- When user rotates/zooms one view, all views update simultaneously
- Essential for fair side-by-side comparison of design alternatives

**Existing Building Context**:
- LOD2 buildings from NRW data shown as context
- Heights preserved exactly from `measuredHeight` attribute
- Toggle visibility on/off
- Distinct visual style (gray, reduced opacity) from new designs

### 8.2 Archive Heatmaps

**Purpose**: Visualize 2D slices of the multi-dimensional solution archive.

**Implementation**:
- User selects two features as X and Y axes
- Each cell represents a behavioral niche
- Color intensity indicates objective (fitness) value of best solution in that niche
- Empty cells (unoccupied niches) shown in white/gray

**Features**:
- Interactive axis selection via dropdowns
- Hover tooltips with solution details
- Click to select solutions for detailed view
- Physical-unit axis labels (m, m², ratio)

### 8.3 Parallel Coordinates Plot

**Purpose**: Visualize relationships across all features simultaneously.

**Implementation** (Plotly Express):
- One vertical axis per selected feature
- Each solution represented as a line connecting its feature values
- Lines colored by fitness value
- Brush selection for filtering

**Use Cases**:
- Identify feature combinations that lead to high fitness
- Discover trade-offs (features that can't be optimized simultaneously)
- Filter solutions meeting specific criteria

### 8.4 Feature-Objective Scatter Plots

**Purpose**: Understand how individual features affect the objective.

**Implementation**:
- Grid of scatter plots, one per feature
- X-axis: Feature value
- Y-axis: Objective (fitness) value
- Trend lines showing correlation direction

**Insights Provided**:
- Which features most strongly influence fitness
- Optimal ranges for each feature
- Diminishing returns or threshold effects

### 8.5 Correlation Heatmap

**Purpose**: Identify relationships between features.

**Implementation**:
- Pairwise Pearson correlation coefficients
- Color scale: red (negative) → white (zero) → blue (positive)
- Symmetric matrix with feature labels

**Use Cases**:
- Identify redundant features (high positive correlation)
- Identify conflicting features (high negative correlation)
- Simplify feature selection for future runs

### 8.6 Uncertainty Heatmap (ML Modes)

**Purpose**: Visualize model uncertainty across solution space.

**Available for**: SVGP and Hybrid evaluation modes

**Implementation**:
- SVGP variance mapped to 2D archive projection
- High uncertainty = bright colors
- Low uncertainty = dark colors

**Use Cases**:
- Identify under-explored regions of solution space
- Guide additional optimization runs
- Assess confidence in model predictions

### 8.7 Flow Field Visualization (U-Net Mode)

**Purpose**: Visualize predicted cold air flow patterns.

**Implementation**:
- U-Net outputs velocity field (u, v components)
- Rendered as streamlines or vector arrows
- Overlaid on 3D building visualization
- Color-coded by flow magnitude

**Use Cases**:
- Identify ventilation corridors
- Visualize blockage effects
- Communicate climate impact to stakeholders

### 8.8 Solution Archive Grid

**Purpose**: Thumbnail overview of all solutions in the archive.

**Implementation**:
- Small 2D heightmap renderings in grid layout
- Click to select for detailed view
- Color-coded by fitness or cluster assignment

**Benefits**:
- Quick visual scanning of solution diversity
- Identify distinct morphological families
- Select interesting solutions for comparison

---

## 9. Export and Reporting

### 9.1 PDF Report Generation

**Technology**: PyLaTeX with automatic LaTeX compilation

**Report Contents**:
- **Executive Summary**: Key findings and recommendations
- **Correlation Heatmap**: Feature relationships across all solutions
- **Archetype Visualizations**: 
  - 2D plan views (heightmap renderings)
  - 3D perspective views
  - Side-by-side comparison layout
- **Comparative Metrics Table**: All features with physical units
  - GRZ, GFZ, heights, distances, building counts
  - Objective values per archetype
  - Cluster sizes (design robustness indicator)
- **Planning-Language Narrative**: 
  - German or English text
  - Uses official planning terminology
  - Describes trade-offs and recommendations
- **Provenance Information**:
  - Optimization settings
  - Model versions
  - Timestamps
  - Data sources used

### 9.2 GeoJSON Export

**Format**: RFC 7946 compliant GeoJSON

**Contents**:
- Georeferenced building polygons
- Height attributes per polygon
- CRS metadata (EPSG:25832 → EPSG:4326 conversion)
- Feature properties: area, height, building ID

**Compatibility**:
- QGIS (direct import)
- ArcGIS Pro
- AutoCAD/Civil 3D (via conversion)
- Web GIS platforms

### 9.3 Project Files

**Format**: `.skizze` files (pickle-based, development only)

**Contents**:
- Complete session state
- Archive data (all solutions)
- Clustering results
- User settings and constraints
- Grid parameters and parcel geometry

**Limitations**:
- Pickle format has security implications
- Not suitable for multi-user or production deployment
- Future: migrate to JSON/SQLite for production

---

## 10. Internationalization

OpenSKIZZE provides full **German/English bilingual support**:

**Implementation**: Translation dictionary in `backend/translation.py`
```python
T = {
    'DE': {
        'GRZ_LABEL': 'Grundflächenzahl',
        'GFZ_LABEL': 'Geschossflächenzahl',
        ...
    },
    'EN': {
        'GRZ_LABEL': 'Site Coverage Ratio',
        'GFZ_LABEL': 'Floor Area Ratio',
        ...
    }
}
```

German uses official German planning terminology (*Fachsprache*) aligned with BauNVO and planning practice.

---

## 11. Validation and Benchmarks

### 11.1 Archive Quality

Test case: Medium parcel (100m × 100m), 1000 generations, 6 features

| Metric | Value |
|--------|-------|
| Archive size | 4,200 / 15,625 niches |
| Coverage | 26.9% |
| QD-Score | 2,847.3 |
| Best fitness | 0.92 |
| Runtime | 4.7 minutes |

### 11.2 Feature Diversity

Feature ranges explored in populated niches:
- Built Area: 800-7,500 m² (full range)
- Avg Height: 3-28 m (93% of range)
- Num Buildings: 1-9 (90% of genome capacity)
- Avg Distance: 5-85 m (full range)

### 11.3 Data Integration Accuracy

LOD2 tile parsing (Bonn test area, 5 tiles):
- Buildings fetched: 1,247
- Height range: 3.2m - 87.5m
- CRS position error: <2m (acceptable for early-stage)
- Height preservation: Exact match to `measuredHeight` attribute

### 11.4 Objective Function Comparison

Correlation with morphological features (1000 solutions):

| Objective | Built Area | Avg Height | Avg Distance |
|-----------|------------|------------|--------------|
| Simple Porosity | -0.87 | -0.45 | +0.71 |
| Street Canyon | -0.52 | -0.28 | +0.48 |

**Interpretation**: Simple porosity strongly penalizes built area (favors sparse); Street canyon allows denser configurations if well-arranged.

---

## 12. Limitations and Future Work

### 12.1 Current Limitations

**Climate Surrogates**:
- Wind porosity and street canyon are simplified geometric proxies, not full CFD
- ML surrogates validated only against KLAM_21 training data
- Heat stress prediction not yet integrated

**Encoding**:
- Fixed 10-building genome may be insufficient for large or complex sites
- Rectangular building footprints only (no L-shapes, curves)

**Planning Integration**:
- GRZ/GFZ calculated but not formally linked to B-Plan regulations
- No XPlanGML import/export
- No formal daylight/shadow analysis (beyond SVF approximation)

**Operations**:
- Project files use pickle (security risk for multi-user deployment)
- No authentication or audit logging
- Single-user local deployment only

### 12.2 Planned Improvements

**Near-term**:
- Heat stress prediction via UMEP/SOLWEIG-trained ML model
- GeoPackage/GeoJSON export with full metadata
- Provenance tracking (run manifests with model versions)

**Mid-term**:
- XPlanGML overlay import for automatic constraint setting
- Formal uncertainty visualization and confidence intervals
- Multi-provider architecture (CityJSON, OSM+DSM fusion)

**Long-term**:
- Multi-objective optimization (wind vs. heat vs. open space)
- Conditional generative AI for rapid archive filling
- Governance features (auth, audit logs, secure storage)

---

## 13. Installation and Usage

### 13.1 Prerequisites

- Python 3.12
- CUDA-capable GPU (optional, for ML acceleration)
- 8GB+ RAM recommended

### 13.2 Installation

```bash
# Clone repository
git clone https://github.com/alexander-hagg/openskizze.git
cd openskizze

# Create environment
mamba create -n openskizze python=3.12
mamba activate openskizze

# Install dependencies
mamba install --file requirements.txt
# OR: pip install -r requirements.txt
```

### 13.3 Running the Application

```bash
python run.py
```

Open browser to: **http://127.0.0.1:8050**

### 13.4 Typical Session

| Step | Task | Duration |
|------|------|----------|
| 1 | Select parcel, set wind | 2 min |
| 2 | Configure constraints/features | 3 min |
| 3 | Run optimization | 5 min |
| 4 | Explore archive | 8 min |
| 5 | Compare archetypes | 4 min |
| 6 | Generate report | 1 min |
| **Total** | **Complete analysis** | **~23 min** |

---

## 14. Conclusion

OpenSKIZZE demonstrates that Quality-Diversity optimization can be made practical for early-stage urban design through aggressive performance optimization (27× speedup via JIT compilation) and careful integration with official German geodata. The system generates hundreds of diverse, climate-aware building massing alternatives in 3-8 minutes—a task that would require hours of manual iteration or CFD simulation.

**Key Technical Achievements**:
- Real-time QD exploration (3-8 min for 1000 generations)
- Physical-unit consistency throughout pipeline (meters, m²)
- Seamless LOD2 CityGML integration with measured building heights
- Multiple validated climate surrogates (geometric and ML-based)
- Interactive 6-step workflow optimized for planning practitioners

**Unique Positioning**: OpenSKIZZE is the only system combining Quality-Diversity optimization with official German geodata and climate-aware objectives at interactive speeds. It fills a critical gap between academic QD research and real-world urban planning practice.

**Current Fit**: Early-stage concept studies (*Vorentwurf*, *städtebaulicher Entwurf*), internal scenario screening, workshop facilitation.

**Future Path**: With planned additions of XPlanGML interoperability, formal daylight analysis, and governance features, the system can progress toward integration with formal B-Plan procedures.

---

*Document generated: December 2025*
