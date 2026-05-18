# OpenSKIZZE

**Climate-Aware Urban Design Exploration with Quality-Diversity Optimization**

OpenSKIZZE is an interactive decision-support tool for urban planners exploring climate-optimized building layouts. Using Quality-Diversity (QD) algorithms, it generates hundreds of diverse design alternatives optimized for ventilation and microclimate, helping planners navigate trade-offs between urban form and environmental performance.

<img width="1512" height="437" alt="OpenSKIZZE screenshot" src="https://github.com/user-attachments/assets/956f3e8b-6059-440a-b162-4b8c5306d881" />

---

## Features

- **Quality-Diversity optimization** (PyRibs) — generates 100–1,000+ diverse solutions per run
- **Wind analysis** — street canyon ventilation (geometric) and U-Net surrogate (ML, KLAM_21-trained)
- **8 planning measures** — GRZ, GFZ, building height, height variability, building count, distance, aspect ratio, open space ratio
- **Interactive analysis** — archive heatmaps, HDBSCAN clustering, synchronized 3D comparison
- **NRW GIS integration** — LOD2 building heights, ALKIS parcels, automatic CRS conversion
- **PDF export** — reports with metrics, visualizations, and flow fields

---

## Prerequisites

- **Python 3.14** (3.13+ also works)
- **Conda or Mamba** (recommended for dependency management)
- ~2 GB disk space (including ML model files in `models/`)

### Optional: GPU acceleration

The U-Net surrogate model runs on CPU by default. For GPU acceleration, install PyTorch with CUDA support
after creating the conda environment:

```bash
conda activate openskizze
pip install torch --index-url https://download.pytorch.org/whl/cu128
```

---

## Installation

```bash
# 1. Create environment with mamba (preferred) or conda
mamba env create -f environment.yml
conda activate openskizze
```

---

## Usage

```bash
# Start the app
python run.py
```

Open **http://127.0.0.1:8050** in your browser.

### Workflow

1. **Step 1 — Scope**: Select a parcel on the map (click NRW parcels, draw, or upload GeoJSON). Set the prevailing wind direction.
2. **Step 2 — Constraints**: Choose an evaluation method (Street Canyon, Simple Porosity, or U-Net). Set target ranges for planning measures and hard constraints (max height, min distance).
3. **Step 3 — Optimize**: Run the QD optimization. Progress is shown in real time.
4. **Step 4 — Explore**: Browse the solution archive via heatmaps. Filter by measures and cluster into design families.
5. **Step 5 — Cluster**: View and compare design families (clusters). Select clusters for detailed comparison.
6. **Step 6 — Compare**: Side-by-side 3D comparison of representative solutions with synchronized camera. Toggle U-Net flow field overlays. Export PDF reports.

---

## Project Structure

```
openskizze/
├── run.py                     # Entry point
├── app.py                     # Dash app, routing, callbacks
├── requirements.txt           # Python dependencies
├── backend/
│   ├── config.py              # QD + domain configuration
│   ├── encoding.py            # Parametric genome (60 genes: 10 buildings × 6)
│   ├── fast_encoding.py       # Numba-accelerated encoding
│   ├── optimizer.py           # QD optimization loop (PyRibs)
│   ├── evaluation.py          # Fitness functions (wind porosity, street canyon)
│   ├── optimization_process.py# Pipeline orchestration
│   ├── surrogate_evaluator.py # U-Net surrogate bridge
│   ├── model_evaluator.py     # U-Net model loading + inference
│   ├── unet.py                # U-Net architecture
│   ├── data_io.py             # NRW data fetching (LOD2, parcels)
│   ├── analysis.py            # Archive analysis, clustering, PDF export
│   ├── translation.py         # DE/EN text dictionaries
│   ├── project_state.py       # Save/load .skizze files
│   ├── units.py               # Physical unit conversions
│   ├── domain_cfg.yml         # Domain configuration (YAML)
│   └── encoding_cfg.yml       # Encoding configuration (YAML)
├── pages/
│   ├── step1_scope.py         # Parcel selection + map
│   ├── step2_constraints.py   # Feature/objective selection
│   ├── step3_optimize.py      # Run optimization
│   ├── step4_analysis.py      # Archive heatmaps + filtering
│   ├── step5_clustering.py    # Clustering + family explorer
│   └── step6_compare_detail.py# Side-by-side 3D comparison
├── models/                    # Pre-trained U-Net weights
├── assets/                    # CSS, JS, static files
└── cache/                     # LOD2 tile cache (auto-populated)
```

---

## Configuration

Key parameters are in `backend/config.py`:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `num_generations` | 200 | QD optimization generations |
| `num_emitters` | 5 | Parallel CMA-ES emitters |
| `batch_size` | 36 | Solutions evaluated per generation |
| `pixel_size_in_meters` | 3.0 | Grid resolution |

The genome dimension is **fixed at 60** (10 buildings × 6 genes: width, length, height, x, y, active).

---

## License

AGPL-3.0 — see [LICENSE](LICENSE).

## Acknowledgements

Funded by the Deutsche Bundesstiftung Umwelt (AZ 39022/01).
Built with [PyRibs](https://pyribs.org/), [Dash](https://dash.plotly.com/), and NRW open geodata.

## Contact

Alexander Hagg — [Personal Webpage](https://alexander-hagg.github.io/)
OpenSKIZZE @ Bonn-Rhein-Sieg University of Applied Sciences - [Webpage](https://www.h-brs.de/en/openskizze)
