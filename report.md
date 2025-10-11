# Executive summary

OpenSKIZZE is evolving into a fast, ML-augmented decision-support tool that couples a quality-diversity (QD) generator with accurate surrogate models and intuitive visual analytics. In the near-term prototype, it will:

- Predict cold-air flow with an ML model trained on DWD KLAM_21 simulation data for NRW.
- Predict urban heat island intensity with an ML model trained on UMEP/SOLWEIG (QGIS)-generated data.
- Use a conditional generative model to rapidly synthesize designs that adhere to target measures/features, efficiently filling the QD archive; the current parametric encoding is kept only to bootstrap training.

This materially improves usefulness for early-phase, climate-aware massing exploration by providing near-real-time feedback on ventilation and heat stress. However, for formal integration into municipal planning (NRW in particular), the prototype will still need standards-compliant exports, planning-law-aligned constraints, model validation/uncertainty reporting, and governance-grade operations (out of scope for the current prototype; see below).

Prototype exclusions (won’t be implemented now):
- User management, roles, audit logs
- Secure storage
- Read-only public viewer
- Usability outside of NRW (the prototype remains NRW-focused)

Beyond-scope (potential future):
- Noise models

Short term, this prototype can augment pre-feasibility and expert workshops with credible, fast climate signals and diverse, constraint-aware options. For B-Plan/FNP procedures or public participation, the roadmap below remains relevant.

## What the software does in the upcoming prototype

- Scope and data acquisition
  - Parcel selection via NRW WFS (ALKIS simplified) and manual/GeoJSON input (pages/step1_scope.py).
  - Building context from NRW CityGML LOD2 tiles with measured heights in meters (backend/data_io.py), cached locally; explicit CRS handling (EPSG:25832 native / EPSG:4326 web).

- Variant generation and evaluation
  - Conditional generative AI for rapid, measure-conforming design synthesis to efficiently populate the archive (encoding used for pretraining/bootstrapping).
  - QD archive (pyribs) with adjustable hyperparameters; hard constraints (max height, min building distance) remain and are enforced.
  - Objectives / climate metrics:
    - ML cold-air flow predictor (trained on DWD KLAM_21) provides fast, site-specific ventilation estimates.
    - ML urban heat island predictor (trained on UMEP/SOLWEIG outputs) provides heat stress proxies.
    - Existing wind-porosity surrogates remain available as fallbacks or complementary indicators.
  - Features in physical units: built area, average height, height variability, building count, average distance, gross floor area, center of mass X/Y.

- Analysis and comparison
  - Archive heatmaps, parallel coordinates, and tiled map previews of best-per-niche solutions.
  - Clustering (HDBSCAN/K-Medoids), consensus maps, and "best vs central" archetype views.
  - 3D voxel visualization of designs vs existing buildings in meters and geo-coordinates with camera sync.
  - PDF report with correlation heatmap, archetype visualization, and planning-language narrative; updated to optionally include ML-derived wind/heat summaries and cautions.
  - Project save/load across sessions (development-only format; see risk section for production caveat).

- Usability and internationalization
  - German/English UI, coherent labels and units. Performance settings remain accessible for experts.

## What’s particularly useful (with ML + generative)

- Near-real-time climate feedback
  - ML wind (KLAM_21-trained) and ML heat (UMEP/SOLWEIG-trained) signals for quick, iterative exploration at parcel scale.
- Design diversity at speed
  - Conditional generative model can fill the archive quickly with solutions that respect target ranges and constraints, improving coverage and stakeholder choice.
- Interpretability and context
  - Physical-unit measures and NRW LOD2 heights throughout the pipeline; 3D comparisons against existing fabric.
- Communication value
  - Clustered archetypes, consensus maps, and synchronized 3D views are effective in workshops and internal reviews.

## Fit to NRW planning processes

Where it helps immediately:
- Early concept studies and städtebauliche Entwürfe with climate-sensitive massing, leveraging fast ML signals to secure ventilation corridors and mitigate heat islands.
- Internal scenario screening with transparent, unit-based metrics and archetype comparisons to inform planning principles.

What remains missing for procedure-grade integration (still recommended):
- Planning-law metrics and constraints
  - GRZ/GFZ as first-class targets; setbacks to streets/parcel edges; minimum courtyard sizes; orientation controls.
  - Daylight/shadow and sky-view-factor analyses to complement ventilation/heat.
- Standards and interoperability
  - Import/export XPlanung (XPlanGML) for overlays and regulation drafting.
  - Export GeoPackage/GeoJSON of design geometries with attributes and metadata, INSPIRE-compliant documentation of used datasets.
- Validation and defensibility
  - Clear validation protocol for ML wind/heat against held-out KLAM_21/UMEP datasets and/or spot CFD checks; uncertainty and confidence intervals visible in UI and reports.
  - Full run/provenance manifest (objective choice, constraints, model versions, data timestamps, git commit) for audit.
- Governance and operations (explicitly out-of-scope for prototype)
  - Auth/roles, secure storage, audit logs, public viewer, NRW-external usability.

Net effect: The ML additions move climate metrics closer to practice by aligning with German tools/datasets (DWD KLAM_21, UMEP/SOLWEIG). With basic validation/uncertainty and the export/standards features, the tool could support plan rationales more credibly.

## Global applicability (outside NRW)

Prototype remains NRW-focused by design. For a later phase:
- Introduce a provider architecture (CityGML/CityJSON/OSM+DSM) to generalize building inputs beyond NRW LOD2.
- Retrain/transfer ML models for other regions/climates; ensure licensing and data availability.
- Extend localization, unit defaults, and basemap/licensing configurations per region.

## Risks and limitations (with ML + generative)

- Model risk
  - Generalization: ML predictors must be validated across site types/seasons; out-of-distribution detection and uncertainty estimates should be surfaced.
  - Attribution/explainability: Provide saliency/feature-attribution or partial-dependence visuals to avoid black-box decisions in planning.
  - Licensing and ethics: Confirm rights to train/serve models on KLAM_21 outputs and UMEP/SOLWEIG-derived data; document permitted use and attribution.
- Security/operations
  - Project format currently uses pickle in development; unsafe for multi-user production. Keep prototype single-user/offline or switch to a safe format before wider trials.
- Reproducibility
  - Without a run manifest and model versioning, results may be hard to audit; add lightweight MLOps tracking even in prototype (model hash, dataset date, seed).
- Data coverage and quality
  - LOD2 gaps or parsing errors can degrade context; make data quality visible to users and gate analyses when inputs are incomplete.

## Recommendations and roadmap (adjusted for prototype scope)

Near-term (0–3 months, prototype)
- ML integration
  - Wire in ML wind/heat scorers with calibration plots against reference datasets; expose uncertainty bands and warnings for extrapolation.
  - Add simple "baseline" (existing-only) climate scores for each site.
- Generative + QD
  - Enable generative filling strategies (coverage-first, diversity-first) with guardrails from hard constraints and user ranges.
- Planning metrics and exports
  - Add GRZ/GFZ and setbacks as first-class constraints/targets with physical-unit sliders.
  - Export best/central solutions to GeoPackage/GeoJSON with CRS/metadata; include objective and ML confidence fields.
- Provenance
  - Capture a minimal run manifest (objectives, constraints, features, QD params, model/version, data timestamps, git SHA) and embed in report.

Mid-term (3–6 months, post-prototype)
- Validation and reliability
  - Cross-validate ML models on held-out KLAM_21/UMEP tiles; add spot CFD checks for top candidates; publish a short validation note in-app.
  - Provide uncertainty visual overlays and confidence badges.
- Provider architecture
  - Pluggable BuildingDataProvider (NRW adapter + CityGML generic + OSM/DSM fusion) with caching/provenance.
- Standards
  - XPlanGML overlay import and export of constraint zones (e.g., ventilation corridors) as planning layers.

Longer-term (6–12 months)
- Analytics and multi-objective
  - Add daylight/shadow and sky-view-factor; extend to multi-objective QD (ventilation vs heat vs open space).
- Governance (beyond current project scope)
  - Auth/roles, secure storage, audit logs, read-only viewer; accessibility and broader localization.
- Deployment
  - Containerized services + job queue for long runs; optional HPC/CFD integrations.

## Recommended 8-feature archive (prototype)

Given your note that an archive with 8 features runs fine, here is a practical 8D set that balances realism, interpretability, and climate relevance. These are design descriptors; ML wind/heat remain objectives, not archive axes.

Archive axes (8)
- GRZ (site coverage) — ratio (0–1)
  - Rationale: Directly controls footprint density and open space.
  - Implementation note: Use built area ÷ parcel area (fallback: normalize built area by site area).
- GFZ (floor area ratio) — ratio
  - Rationale: Controls total massing independent of pure footprint; aligns with BauNVO practice.
  - Implementation note: Use GFA ÷ parcel area (fallback: normalize GFA by site area).
- Average building height — m
  - Rationale: Separates vertical massing from GRZ/GFZ; impacts ventilation, shadow, and heat.
- Height variability — m
  - Rationale: Captures stepped/tapered massing; relates to turbulence/mixing and townscape.
- Number of buildings — count
  - Rationale: Grain size/granularity; influences porosity and urban form.
- Average building distance — m
  - Rationale: Explicit spacing/porosity control; supports corridor formation.
- Street canyon aspect ratio (H/W) — dimensionless
  - Rationale: Key for ventilation and comfort on adjacent streets; summarizes morphological effect.
  - Implementation note: Derive from typical street segments adjacent to built edges or from ground-level void/built sections.
- Sky view factor (SVF) — 0–1
  - Rationale: Strong proxy for urban heat and daylighting at ground/courtyards; complements wind objective.
  - Implementation note: Compute site-averaged SVF via fast hemispherical sampling/raycasting over heightmap; store as mean or percentile.

Sizing guidance (keep coverage tractable)
- Prefer low niche counts per dimension with 8D:
  - 3 niches^8 = 6,561 cells (comfortable, especially with generative filling).
  - 4 niches^8 = 65,536 cells (feasible if generation/selection is efficient).
  - 5 niches^8 = 390,625 cells (only if runtime and memory budgets allow, and with aggressive generative coverage).
- If runtime grows, reduce niches first before dropping dimensions.

Notes
- If GRZ/GFZ aren’t yet computed, use built area (m²) and GFA (m²) normalized by site area as temporary substitutes.
- Keep ML wind (KLAM_21) and ML heat (UMEP/SOLWEIG) as objectives; using them as archive axes is possible but can blur exploration vs evaluation.
- Building mass X/Y (center-of-mass) are useful diagnostics/filters but add little diversity as axes; keep them out of the core 8.

## Evidence and code anchors (current repo; ML/generative planned)

- NRW building data and meters pipeline: backend/data_io.py (LOD2 tiles, measuredHeight), backend/evaluation.py (meters throughout), backend/units.py (feature units).
- Objectives: backend/evaluation.py (wind porosity, street-canyon surrogate) — ML wind/heat to be added alongside.
- Features: backend/evaluation.py::calculate_all_features; physical-unit handling in backend/units.py.
- Workflow: step1_scope.py (WFS parcels, polygon tools, wind compass), step2_constraints.py (hard constraints, measures, objective selection), step3_optimize.py (QD run, archive viz), step4_compare.py (clustering, consensus), step5_compare_detail.py (3D sync viz, PDF export).
- Reporting: backend/analysis.py::generate_pdf_report (to be extended with ML metrics and uncertainty text).

## Minimal prioritized backlog (updated)

### Planned (prototype)
- [ ] Integrate ML wind (KLAM_21-trained) and ML heat (UMEP/SOLWEIG-trained) scorers with calibration/uncertainty and baseline comparisons.
- [ ] Add GRZ/GFZ and setback constraints; expose as physical-unit sliders and as archive dimensions when selected.
- [ ] Wire up the conditional generative model to populate the archive subject to user ranges and hard constraints; provide coverage/quality diagnostics.
- [ ] Implement GeoPackage/GeoJSON exports for candidates with CRS, metadata, and ML confidence fields.
- [ ] Capture a run manifest (config, constraints, feature ranges, QD/ML versions, data timestamps, git SHA) and embed in reports/exports.

### Later (post-prototype)
- [ ] Replace pickle-based project storage before any multi-user demos; or keep strictly single-user/offline with a clear warning.
- [ ] Plan provider abstraction to enable non-NRW usage and alternative building sources.

## Bottom line

- With ML wind/heat and conditional generative design, the prototype substantially improves speed and credibility for early, climate-aware massing in NRW.
- For integration into the municipal planning pipeline and public-facing work, continue with standards-based exports, planning-law metrics/constraints, ML validation/uncertainty, and—post-prototype—governance/security and broader data-provider support.
- This trajectory positions OpenSKIZZE as a credible bridge between computational exploration and formal urban planning—first in NRW, and later beyond once provider generalization and governance are addressed.

## Appendix: Feature and constraint catalog for real-world use

This appendix lists the archive measures/features and the hard constraints that should be available to cover common real-world planning use cases. Each item notes the unit, a short definition, and current status.

### Archive measures/features (for archive axes, filtering, and reporting)

Implemented today
- Built area — m² — Sum of built footprint cells. Status: Implemented.
- Average building height — m — Mean of building heights across built cells. Status: Implemented.
- Height variability — m — Standard deviation of heights across built cells. Status: Implemented.
- Number of buildings — count — Count of contiguous building components. Status: Implemented.
- Average building distance — m — Mean centroid-to-centroid distance across buildings. Status: Implemented.
- Gross floor area (GFA) — m² — Sum of heightmap values × pixel area (1 m per voxel). Status: Implemented.
- Building mass X — 0–1 — Center of mass along X (normalized). Status: Implemented.
- Building mass Y — 0–1 — Center of mass along Y (normalized). Status: Implemented.

Planned in prototype
- ML cold-air flow score — 0–1 — Surrogate prediction trained on DWD KLAM_21 for ventilation efficacy. Status: Planned (prototype).
- ML urban heat island score — °C anomaly or PET (°C) — Surrogate prediction trained on UMEP/SOLWEIG for local heat stress. Status: Planned (prototype).

Recommended (near-term)
- GRZ (Grundflächenzahl) — ratio — Built footprint / parcel area. Status: Recommended; computable from built area.
- GFZ (Geschossflächenzahl) — ratio — GFA / parcel area. Status: Recommended; computable from GFA.
- Max building height — m — Maximum building height within design. Status: Recommended (for limits and reporting).
- Height percentiles — m — P50/P90 of building heights. Status: Recommended.
- Setback compliance ratio — % — Share of perimeter length meeting setback rules. Status: Recommended.
- Baufenster compliance — % — Share of built footprint inside designated buildable zones. Status: Recommended.
- Ventilation corridor openness — 0–1 — Minimum/mean openness along predefined axes/corridors. Status: Recommended (can derive from ML wind or porosity).
- Sky view factor (SVF) — 0–1 — Mean or distribution across public realm/courtyards. Status: Recommended.
- Daylight/sun hours — h — Sun hours at ground/courtyards for key dates/times. Status: Recommended.
- Overshadowed area at critical times — m² or % — Shadow at e.g. 21 Jun/21 Dec at set hours. Status: Recommended.
- Impervious area — m² / % — Built + paved surfaces; complements drainage goals. Status: Recommended.
- Green/blue area — m² / % — Vegetation and open water within site. Status: Recommended.
- Tree canopy coverage — % — Fraction of area under tree canopy. Status: Recommended.
- Street canyon aspect ratio — dimensionless — H/W statistics for adjacent street segments. Status: Recommended.

Optional (later phases)
- Use mix floor area — m² by category — GFA split by function (res/office/retail). Status: Optional.
- Solar potential — kWh/m²·a — Roof irradiance proxy. Status: Optional.
- Access/egress clearances — m — Fire and service access widths/turning. Status: Optional.

### Hard constraints (enforced during generation/evaluation)

Implemented today
- Maximum building height — m — Clip/penalize heights exceeding limit. Status: Implemented.
- Minimum distance between buildings — m — Enforce separation between components. Status: Implemented.

Recommended (NRW practice-aligned)
- Setbacks to parcel boundary — m — Min distance for fronts/sides/backs; possibly differentiated by edge type. Status: Recommended.
- Setbacks to street centerline/edge — m — As per street category or plan. Status: Recommended.
- Non-buildable zones (Baufenster outside) — boolean mask — Hard exclusion areas (e.g., ventilation corridors, easements). Status: Recommended.
- Maximum site coverage (GRZ) — ratio — Built footprint ≤ GRZ × parcel area. Status: Recommended.
- Maximum floor area (GFZ) — ratio — GFA ≤ GFZ × parcel area. Status: Recommended.
- Step-backs / tapering — m per level or envelope — Envelope constraints for upper floors. Status: Recommended.
- Courtyard minimums — m / m² — Min width/area for interior courts for light/air. Status: Recommended.
- Protected features buffers — m — No-build buffers for trees, water bodies, biotopes, heritage. Status: Recommended.
- Flood/slope constraints — thresholds — No-build in floodplains; max allowable slope for buildability. Status: Recommended.
- Height view corridors/heritage — m / envelope — Limit heights along protected view sheds. Status: Recommended.
- Permeable area minimum — % — Ensure minimum permeable/green surface. Status: Recommended.
- Public space frontage continuity — % — Min continuous active frontage (soft or hard depending on use). Status: Recommended (could be soft initially).
- Ventilation corridors — boolean mask + width — Mandatory open bands aligned to wind axes. Status: Recommended.

Optional / beyond current project scope
- Pedestrian wind safety — m/s thresholds — Limit predicted exceedance of wind speeds at 1.5 m. Status: Optional.
- Noise exposure limits — dB — Building placement to meet façade or courtyard noise limits. Status: Optional (future).
- Daylight minimums — h or SVF — Enforce minimum sun exposure in specific spaces. Status: Optional (can begin as soft constraints).

Notes
- Many recommended features derive from already available primitives (built area, GFA, envelopes) and can be implemented with modest effort.
- ML outputs (wind/heat) should include uncertainty estimates; constraints can be applied to mean predictions with safety margins.
- Constraint masks (setbacks, non-buildable zones, ventilation bands) should be importable/exportable as GIS layers (XPlanGML/GeoPackage).