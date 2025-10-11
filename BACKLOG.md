# OpenSKIZZE Backlog

This backlog distills the plan from `report.md` into actionable epics, user stories, and milestones. It reflects the NRW-focused prototype with ML surrogates and a conditional generative model, and clearly separates prototype vs post-prototype scope.

## Principles & scope
- Prototype scope (NRW-only):
  - ML wind (KLAM_21-trained) and ML heat (UMEP/SOLWEIG-trained) predictors
  - Conditional generative design to rapidly fill the QD archive under constraints
  - Planning metrics in physical units; export to GeoPackage/GeoJSON
  - Run manifest for reproducibility
- Out of scope for prototype: user management/roles/audit logs, secure storage, read-only public viewer, non-NRW usability
- Keep ML surrogates as objectives; archive uses design descriptors

## Milestones
- M1 (0–3 months): Prototype ML + Generative Release
  - ML wind/heat scorers integrated with calibration & uncertainty
  - Conditional generative filling strategies wired to archive & constraints
  - GRZ/GFZ + setbacks as first-class constraints/targets
  - GeoPackage/GeoJSON exports with CRS, metadata, ML confidence
  - Minimal run manifest captured and embedded
- M2 (3–6 months): Validation & Standards
  - Cross-validation for ML models, spot CFD checks for candidates
  - Uncertainty overlays and confidence badges in UI/exports
  - Provider architecture scaffold (NRW adapter + CityGML generic + OSM/DSM fusion)
  - XPlanGML overlays import and export of constraint zones
- M3 (6–12 months): Analytics & Multi-objective
  - Sky view factor (SVF), daylight/shadow estimators; multi-objective QD
  - Deployment hardening (job queue, optional HPC/CFD), governance (post-prototype)

## Recommended 8-feature archive (prototype)
Use these 8 archive axes (design descriptors):
1) GRZ (site coverage, ratio 0–1)
2) GFZ (floor area ratio, ratio)
3) Average building height (m)
4) Height variability (m)
5) Number of buildings (count)
6) Average building distance (m)
7) Street canyon aspect ratio (H/W, dimensionless)
8) Sky view factor (SVF, 0–1)

Notes: If GRZ/GFZ aren’t computed yet, normalize built area/GFA by site area. Keep ML wind/heat as objectives.

---

## Epics and user stories

### Epic E1 — ML climate scoring (prototype)
Why: Near-real-time, credible climate feedback for design exploration.

Stories
- [ ] S1.1 Integrate ML wind scorer (KLAM_21-trained)
  - Acceptance: Given a site grid and heightmap, return wind score in [0,1] with inference time < 300 ms for typical parcels; include model/version and uncertainty.
- [ ] S1.2 Integrate ML heat scorer (UMEP/SOLWEIG-trained)
  - Acceptance: Given the same inputs, return heat metric (e.g., PET proxy or Δ°C) with uncertainty; inference < 300 ms.
- [ ] S1.3 Calibration & diagnostics
  - Acceptance: Provide calibration plots vs reference tiles; log MAE/R²; display model validity warnings for OOD.
- [ ] S1.4 Uncertainty surfacing
  - Acceptance: Show uncertainty ranges in UI and include in exports/reports.

Dependencies: Training artifacts available; data licensing cleared.

### Epic E2 — Conditional generative design (prototype)
Why: Efficient archive coverage aligned to user feature ranges and hard constraints.

Stories
- [ ] S2.1 Training bootstrapping from parametric encoding
  - Acceptance: Train conditional model on genomes/heightmaps + measures; document dataset split and seeds.
- [ ] S2.2 Constrained sampling and repair
  - Acceptance: Generate designs satisfying selected ranges and hard constraints ≥95% of the time; fallback repair path documented.
- [ ] S2.3 Archive filling strategies
  - Acceptance: Provide coverage-first and diversity-first modes; report coverage metrics per dimension.

Dependencies: E1 optional for reward shaping; E3 constraints.

### Epic E3 — Planning metrics & exports (prototype)
Why: Align with NRW planning practice and GIS workflows.

Stories
- [ ] S3.1 GRZ/GFZ as first-class features/targets
  - Acceptance: Compute GRZ, GFZ; expose sliders; reflect in archive axes when selected.
- [ ] S3.2 Setbacks and constraint masks
  - Acceptance: Import/export setbacks and non-buildable zones as GIS layers; enforce as hard constraints.
- [ ] S3.3 GeoPackage/GeoJSON export
  - Acceptance: Export candidate designs with geometries, CRS, attributes (incl. objectives, uncertainty, archive indices), and metadata manifest.

### Epic E4 — Provenance & reproducibility (prototype)
Why: Auditability and trust.

Stories
- [ ] S4.1 Run manifest capture
  - Acceptance: Store objectives, constraints, feature ranges, QD params, model names/versions/hashes, data timestamps, git SHA; embed into exports and report.

### Epic E5 — Validation & reliability (post-prototype)
Why: Confidence and defensibility.

Stories
- [ ] S5.1 Cross-validation on held-out tiles (wind/heat)
  - Acceptance: Report MAE/R² on held-out datasets; publish a validation note.
- [ ] S5.2 Spot CFD checks for top candidates
  - Acceptance: Pipeline to export candidates for CFD; compare surrogate vs CFD on a few cases; document gaps.
- [ ] S5.3 Uncertainty overlays in UI
  - Acceptance: Visual overlays for uncertainty percentiles; confidence badges in cluster/comparison views.

### Epic E6 — Provider architecture (post-prototype)
Why: Extensibility beyond NRW LOD2.

Stories
- [ ] S6.1 BuildingDataProvider interface
  - Acceptance: Common interface + NRW adapter; add CityGML generic and OSM/DSM fusion adapters.
- [ ] S6.2 Caching & provenance for providers
  - Acceptance: Cache indexing; data source metadata in manifest.

### Epic E7 — Standards (post-prototype)
Why: Planning process integration.

Stories
- [ ] S7.1 XPlanGML overlay import
- [ ] S7.2 Export of constraint zones and corridors as planning layers

### Epic E8 — Analytics & multi-objective (post-prototype)
Why: Richer analysis and trade-offs.

Stories
- [ ] S8.1 Sky view factor (SVF) estimator
  - Acceptance: Mean/percentile SVF across ground/courtyards within 5–10% of a raytraced reference.
- [ ] S8.2 Daylight/shadow quick estimator
  - Acceptance: Sun hours/overshadowing for key dates; performance suitable for interactive use.
- [ ] S8.3 Multi-objective QD
  - Acceptance: Pareto front exploration across ventilation/heat/open space.

### Epic E9 — Governance & deployment (post-prototype)
Why: Operational readiness.

Stories
- [ ] S9.1 Safe project storage format
  - Acceptance: Replace pickle before any multi-user demo, or clearly gate as single-user/offline.
- [ ] S9.2 Job queue & optional HPC/CFD hooks

---

## Cross-cutting acceptance criteria
- Units and CRS are explicit in UI and exports; physical-unit labels everywhere.
- Performance: Prototype archive build and analysis within acceptable wall-time on a mid-range workstation.
- Accessibility/UX: Clear warnings when models/data are out-of-distribution or incomplete.

## References
- See `report.md` for rationale, risk analysis, and evidence anchors.
