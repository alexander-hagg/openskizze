# OpenSKIZZE: MVP Requirements & Roadmap

**Date**: November 25, 2025  
**Status**: Draft  
**Target Audience**: Development Team, Stakeholders

---

## 1. Executive Summary

OpenSKIZZE is transitioning from a research prototype to a **municipal decision-support tool** for urban planners in North Rhine-Westphalia (NRW). The goal is to enable early-stage *städtebauliche Entwürfe* (urban design concepts) that balance investor density targets with climate resilience mandates.

The system uses **Quality-Diversity (QD) optimization** to generate diverse building massing variants, evaluated against real-time climate surrogates (wind flow, heat) and integrated with official GIS data.

---

## 2. Target User Profile

**Primary User**: Urban Planners in City Planning Offices (*Stadtplanungsamt*)
*   **Context**: Creating B-Plans (*Bebauungspläne*) and feasibility studies.
*   **Expertise**: High domain knowledge (planning law, morphology), low technical tolerance (no coding/scripting).
*   **Language**: German technical terminology (*Fachsprache*) is mandatory.
*   **Constraints**: High time pressure; need "coffee break" results (5-10 mins).

---

## 3. Critical User Needs

| Category | Need | Implementation Requirement |
| :--- | :--- | :--- |
| **Compliance** | **Legal Metrics** | Display *Grundflächenzahl* (GRZ) and *Geschossflächenzahl* (GFZ) for all solutions. |
| **Speed** | **Interactive Latency** | Optimization must complete in < 5 minutes for 1000 generations. |
| **Context** | **Seamless Data** | Automatic fetching of neighbor heights (LOD2) and parcel boundaries (ALKIS). |
| **Output** | **Defensibility** | Automated PDF reports justifying decisions to city councils. |
| **Workflow** | **Interoperability** | Export selected designs to CAD (DXF) or GIS (Shapefile) for detailed planning. |

---

## 4. Functional Requirements (The "MVP" Gap)

### A. Planning Law Integration
*   **B-Plan Constraints**: Allow users to define *Baugrenzen* (buildable boundaries) and *Baulinien* (mandatory lines), not just bounding boxes.
*   **Shadow Analysis**: Implement "2-hour shadow" checks (DIN 5034) alongside current Sky View Factor (SVF).
*   **Metric Visibility**: GRZ/GFZ must be primary sorting/filtering criteria.

### B. Performance & Robustness
*   **JIT-First Policy**: All new metrics (e.g., shadow analysis) must be Numba-optimized to maintain the <5 min runtime.
*   **Repair Heuristics**: Implement generative seeding to prevent "empty archives" in dense urban settings where random initialization fails.

### C. Data & Interoperability
*   **Export**: Add DXF/DWG and Shapefile/GeoJSON export for generated geometries.
*   **Import**: Support XPlanGML ingestion for automatic constraint setting (Future).
*   **State Management**: Replace Python `pickle` with JSON/SQLite for secure, version-independent project saving.

### D. User Experience (UX)
*   **Localization**: Complete German localization using correct *BauNVO* terminology (e.g., *Winddurchlässigkeit*, *Überbaute Fläche*).
*   **Wizard Workflow**: Maintain the linear 6-step process. Hide complex QD hyperparameters (sigma, mutation rates) behind an "Expert Mode".

---

## 5. Technical Roadmap

1.  **Phase 1: Compliance & Metrics** (Current Priority)
    *   Implement GRZ/GFZ calculation and visualization.
    *   Refine German localization.
    *   Replace `pickle` state saving.

2.  **Phase 2: Robustness & Speed**
    *   Implement repair heuristics for dense parcels.
    *   Optimize shadow analysis (JIT).

3.  **Phase 3: Interoperability**
    *   Develop DXF/Shapefile export modules.
    *   Package as standalone executable/container for local deployment.
