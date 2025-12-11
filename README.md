# OpenSKIZZE

**Climate-Aware Urban Design Exploration with Quality-Diversity Optimization**

OpenSKIZZE is an interactive decision-support tool for urban planners exploring climate-optimized building layouts. Using Quality-Diversity (QD) algorithms, it generates hundreds of diverse design alternatives optimized for ventilation and microclimate, helping planners navigate trade-offs between urban form and environmental performance.

<img width="1512" height="437" alt="Screenshot from 2025-12-10 16-00-35" src="https://github.com/user-attachments/assets/956f3e8b-6059-440a-b162-4b8c5306d881" />

---

## 🎯 Key Features

### Quality-Diversity Optimization
- **PyRibs-based QD engine**: Generates 100-1,000+ diverse solutions per optimization run
- **Multi-objective support**: Wind porosity, street canyon ventilation, and ML-based climate predictions
- **Adaptive phenotype**: Automatically scales grid resolution based on parcel size

### Climate Simulation
- **Wind analysis**: Two validated methods (simple porosity, street canyon ventilation)
- **U-Net surrogate model**: Fast ML-based prediction of cold air flow (KLAM_21-trained)
- **Flow field visualization**: 3D streamlines and velocity heatmaps at 3m resolution

### Planning Features (8 dimensions)
1. **GRZ** (Grundflächenzahl) - Site coverage ratio
2. **GFZ** (Geschossflächenzahl) - Floor area ratio  
3. **Average building height** (meters)
4. **Height variability** (standard deviation)
5. **Number of buildings** (count)
6. **Average building distance** (meters)
7. **Street canyon aspect ratio** (H/W)
8. **Open space ratio** (1 - GRZ)

### Interactive Analysis
- **Archive heatmaps**: Explore 2D slices of the 8-dimensional solution space
- **Clustering**: Automatic identification of "design families" using HDBSCAN
- **Side-by-side comparison**: Compare representative solutions with synchronized 3D views
- **PDF export**: Generate reports with design metrics, visualizations, and flow fields

### GIS Integration (NRW-Focused)
- **LOD2 building data**: Fetch measured building heights from NRW open data
- **ALKIS parcel data**: Import land parcels via WFS
- **CRS handling**: Automatic conversion between EPSG:25832 (native) and EPSG:4326 (web)
- **Export formats**: GeoJSON for integration with QGIS and other GIS tools

---

## 🚀 Quick Start

### Prerequisites
- Python 3.12
- CUDA-capable GPU (optional, for U-Net acceleration)
- 8GB+ RAM recommended

### Installation

```bash
# Clone repository
git clone https://github.com/alexander-hagg/openskizze.git
cd openskizze

# Create environment (recommended: mamba)
mamba create -n openskizze python=3.12
mamba activate openskizze

# Install dependencies
mamba install --file requirements.txt
# OR: pip install -r requirements.txt
```

### Run the Application

```bash
python run.py
```

Open your browser to: **http://127.0.0.1:8050**

---

## 📖 Workflow (6 Steps)

### Step 1: Parcel Selection
- Upload GeoJSON or select from NRW cadastral data (ALKIS WFS)
- Set wind direction (meteorological convention, e.g., 270° = wind from west)
- LOD2 buildings automatically fetched for context

<img width="1671" height="878" alt="Screenshot from 2025-12-10 16-18-57" src="https://github.com/user-attachments/assets/798d26d4-b1dd-4c4c-a6e7-27a68544138c" />

### Step 2: Constraints & Features
- Select up to 8 features for archive dimensions
- Set target ranges (min/max) for each feature
- Define hard constraints:
  - Maximum building height
  - Minimum building distance
  - Minimum site coverage (GRZ)
- Choose objective function:
  - `simple_porosity` (sparse urban areas)
  - `street_canyon` (dense urban areas, recommended)
  - `unet` (requires trained model)

<img width="1671" height="878" alt="Screenshot from 2025-12-10 16-19-34" src="https://github.com/user-attachments/assets/e26ac163-cfb4-46dc-afdd-e4db348cb599" />

### Step 3: Optimize
- Configure QD parameters:
  - Number of generations (100-1000)
  - Population size per generation
  - Number of emitters (parallel search)
- Run optimization (multiprocessed)
- Monitor progress with live updates

<img width="1671" height="878" alt="Screenshot from 2025-12-10 16-19-56" src="https://github.com/user-attachments/assets/9a3f7451-9951-4b39-93dd-98cdf8b84b6d" />

### Step 4: Explore Archive
- View archive heatmaps (2D projections of solution space)
- Inspect 3D previews of high-performing solutions
- Check diversity metrics (coverage, density)

<img width="1671" height="878" alt="Screenshot from 2025-12-10 16-20-17" src="https://github.com/user-attachments/assets/fe1858de-4576-4a91-acdf-9d760a10862a" />

### Step 5: Clustering
- Automatic clustering identifies "design families"
- Select clusters for detailed comparison
- View representative (central) or best solutions per cluster

<img width="1671" height="878" alt="Screenshot from 2025-12-10 16-22-04" src="https://github.com/user-attachments/assets/387b0060-eedd-44a3-9c5e-ff4cc47aa139" />

### Step 6: Compare & Export
- Side-by-side 3D visualization with synchronized cameras
- View metrics: GRZ, GFZ, heights, distances, objectives
- **Design robustness**: Cluster size as % of total solutions
- Toggle U-Net flow field visualization (if available)
- Export PDF report with all visualizations and metrics

<img width="1671" height="878" alt="Screenshot from 2025-12-10 16-22-26" src="https://github.com/user-attachments/assets/ed157302-5647-467d-8beb-9fac42700e96" />

---

## 🛠️ Technical Architecture

### Backend
- **Framework**: Dash 2.17 + Flask
- **QD Optimizer**: PyRibs 0.6.1 (GridArchive, GaussianEmitter)
- **Encoding**: Parametric genome (60 genes: 10 buildings × 6 parameters)
- **Evaluation**: JIT-compiled with Numba 0.59 for performance
- **Geospatial**: GeoPandas 0.14, Shapely 2.0, Fiona 1.9

### ML Models (Optional)
- **U-Net**: PyTorch-based surrogate for cold air flux prediction
- **SVGP**: Sparse Variational Gaussian Process (GPyTorch) for uncertainty quantification
- **Input**: 66×94 grid at 3m resolution, 3 channels (terrain, buildings, landuse)
- **Output**: 6 channels (cold air energy, heat flux, wind velocity u/v at 2m and 10m)

### Frontend
- **Visualization**: Plotly 5.22 for 3D graphics and heatmaps
- **Maps**: Dash-Leaflet 1.0 with OpenStreetMap base layers
- **UI**: Dash Bootstrap Components 1.6
- **Localization**: Bilingual (German/English)

### Data Sources
- **NRW LOD2**: CityGML building geometries with measured heights
- **NRW ALKIS**: Parcel boundaries via WFS
- **Coordinate System**: EPSG:25832 (ETRS89 / UTM zone 32N)

---

## 📁 Project Structure

```
openskizze/
├── app.py                    # Dash app initialization & routing
├── run.py                    # Entry point (python run.py)
├── requirements.txt          # Python dependencies
├── backend/                  # Core logic (11 modules)
│   ├── config.py             # QD, encoding, domain configuration
│   ├── encoding.py           # Parametric genome (60 genes)
│   ├── optimizer.py          # QD optimization loop (PyRibs)
│   ├── evaluation.py         # Fitness functions (wind, street canyon)
│   ├── data_io.py            # NRW data fetching (LOD2, parcels)
│   ├── optimization_process.py  # Main pipeline orchestration
│   ├── analysis.py           # Archive analysis, clustering, exports
│   ├── model_evaluator.py    # U-Net/SVGP surrogate wrappers
│   ├── units.py              # Physical unit conversions
│   ├── translation.py        # DE/EN text dictionaries
│   └── project_state.py      # Save/load (.skizze files)
├── pages/                    # UI pages (7 modules)
│   ├── step1_scope.py        # Parcel selection + map
│   ├── step2_constraints.py  # Feature/objective selection
│   ├── step3_optimize.py     # Run optimization
│   ├── step4_analysis.py     # Archive heatmaps + 3D previews
│   ├── step5_clustering.py   # Clustering analysis
│   ├── step6_compare_detail.py  # Side-by-side comparison
│   ├── step_diagnostic.py    # Debug view for empty archives
│   └── step_model_diagnostics.py  # U-Net flow visualization
├── assets/                   # Static files
│   ├── style.css             # Custom CSS
│   ├── camera_sync.js        # Client-side 3D camera sync
│   └── logo.png              # Branding
├── tests/                    # Test scripts (22 files)
└── helper/                   # Documentation (60+ markdown files)
    ├── QUICK_START_GUIDE.md
    └── QUICK_REFERENCE.md
```

---

## ⚙️ Configuration

### Key Parameters (`backend/config.py`)

**Genome Encoding** (FIXED dimension: 60 genes)
- 10 buildings × 6 genes: [width, length, height, x, y, active]
- Never change genome dimension (breaks archive compatibility)

**Domain Configuration**
- `pixel_size_in_meters`: 3.0 (grid resolution)
- `max_building_floors`: 12 (default height limit)
- `meters_per_floor`: 3.0 (floor-to-floor height)

**QD Archive**
- `grid_dims`: [20, 20] (400 cells for 2D archive)
- `feat_ranges`: Auto-computed or user-specified

---

## 🐛 Troubleshooting

### Empty Archive
**Symptom**: No solutions accepted after optimization  
**Causes**:
1. Constraints too restrictive (max_height, min_distance)
2. Feature ranges too narrow
3. Wrong objective for parcel density

**Solutions**:
- Use `/diagnostic` page to check fitness values
- Switch from `simple_porosity` to `street_canyon` for dense urban areas
- Relax constraints or widen feature ranges
- Increase `num_generations` (100 → 500)

### Slow Performance
**Symptom**: 8+ minutes for 1000 generations  
**Optimizations applied**:
- Label caching in evaluation loop
- 2D rotation before 3D conversion (not after)
- Numba JIT compilation for hot paths

**Expected**: 3-4 minutes for 1000 generations on mid-range hardware

### U-Net Model Not Found
**Symptom**: Flow visualization unavailable  
**Solution**: U-Net model is optional. Use `simple_porosity` or `street_canyon` objectives instead.

---

## 📊 Performance Benchmarks

- **Evaluation speed**: ~50,000 fitness evaluations in 3-4 minutes (street_canyon)
- **Archive size**: 100-1,000 elite solutions per run
- **Coverage**: Typically 30-70% of archive cells filled
- **Memory**: ~2GB for optimization + ~4GB for U-Net (if GPU)

---

## 🌍 Use Cases

### Urban Planning Offices
- Explore building layout options for new development areas
- Balance density (GRZ/GFZ) with ventilation requirements
- Generate alternatives for stakeholder discussions

### Climate Adaptation
- Identify designs that promote cold air flow from hillsides
- Optimize street canyon geometry for urban heat mitigation
- Compare ventilation performance across design families

### Research & Education
- Study trade-offs in urban form and microclimate
- Validate ML surrogate models against CFD simulations
- Demonstrate Quality-Diversity optimization in applied contexts

---

## 🔬 Scientific Background

**Quality-Diversity (QD)**: Unlike single-objective optimization, QD maintains a diverse archive of high-performing solutions across multiple behavioral dimensions (features). This enables:
- Exploration of design space beyond local optima
- Discovery of surprising/creative solutions
- Resilience to changing constraints

**Implementation**: MAP-Elites algorithm via PyRibs
- Feature space discretized into grid cells
- Each cell stores best solution for that region
- Emitters generate variations around promising areas

**References**:
- Mouret & Clune (2015): "Illuminating the search space..."
- Fontaine et al. (2021): "Covariance Matrix Adaptation MAP-Elites"
- PyRibs documentation: https://docs.pyribs.org/

---

## 📝 Citation

```bibtex
@software{openskizze2024,
  title = {OpenSKIZZE: Climate-Aware Urban Design with Quality-Diversity},
  author = {Hagg, Alexander and others},
  year = {2024},
  url = {https://github.com/alexander-hagg/openskizze}
}
```

---

## 🤝 Contributing

OpenSKIZZE is research software under active development. Contributions welcome!

**Before contributing**:
1. Read `.github/copilot-instructions.md` for coding guidelines
2. Check `BACKLOG.md` for planned features
3. Run tests: `python tests/test_feature_constraints.py` (example)

**Key principles**:
- Minimize changes (surgical edits, avoid refactoring)
- Use physical units (meters, m²) everywhere
- Add bilingual strings (DE + EN) to `backend/translation.py`
- Never change genome dimension (60 genes FIXED)

---

## 📄 License

AGPL-3.0 license 
[https://github.com/alexander-hagg/openskizze-gui?tab=AGPL-3.0-1-ov-file#readme]

---

## 🔗 Links

- **Project website**: [Add URL if available]
- **Documentation**: See `helper/` directory for detailed guides
- **NRW Open Data**: https://www.opengeodata.nrw.de/
- **PyRibs**: https://pyribs.org/

---

## 📧 Contact

Alexander Hagg - [[Personal Webpage](https://alexander-hagg.github.io/)]

**Funding**: [Deutsche Bundesstiftung Umwelt] (AZ 39022/01)

---

*Last updated: December 2025*
