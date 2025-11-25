# OpenSKIZZE: Report Generation & Strategic Value Analysis

**Date**: November 25, 2025  
**Focus**: Reporting, Robustness, and Urban Planning Competitions

---

## 1. Executive Summary

The reporting module in OpenSKIZZE must evolve from a simple "summary of results" to a **strategic decision-support document**. For urban planners, the value isn't just seeing the *best* solution, but understanding the **robustness** of a design strategy and defining clear **guardrails** for subsequent planning phases (architectural competitions or B-Plans).

## 2. The Concept of Robustness & Adaptability

In urban planning, a design is never built exactly as drawn in the early phase. Investors will demand changes, costs will force adjustments, and architects will bring new ideas. Therefore, planners need **robustness**.

### 2.1 Cluster Size as a Proxy for "Spielraum" (Flexibility)
*   **The Insight**: In Quality-Diversity optimization, a "Cluster" represents a family of similar designs (a typology).
*   **Large Cluster**: Indicates a "wide peak" in the fitness landscape. There are many ways to configure buildings in this pattern while maintaining high performance.
    *   *Planner Interpretation*: "This typology is **Robust**. We can negotiate with investors or shift buildings by a few meters without breaking the climate concept."
*   **Small Cluster**: Indicates a "narrow peak". Only a very specific configuration works.
    *   *Planner Interpretation*: "This typology is **Fragile**. If we deviate even slightly (e.g., post-hoc adaptation), the ventilation might fail."

### 2.2 Reporting Requirement
The report must explicitly rank design families by an **"Adaptability Score"** (derived from cluster size and intra-cluster variance).
*   *High Score*: "Safe bet for B-Plan."
*   *Low Score*: "High risk, requires strict regulation."

---

## 3. Consensus Maps: From Analysis to Regulation

**Consensus Maps** (heatmaps showing where buildings are placed across *all* solutions in a cluster) are the bridge between abstract optimization and legal planning instruments.

### 3.1 The "Invariant" Structures
*   **High Consensus Areas (Red)**: "Buildings are *always* here in this typology." -> These become **Baufenster** (Buildable Areas).
*   **Low Consensus Areas (Blue/White)**: "Buildings are *never* here." -> These become **Ventilation Corridors** or **Public Spaces**.
*   **Fuzzy Areas**: "Buildings might be here." -> These represent the **Flexibility Zone** for architects.

### 3.2 Reporting Requirement
For each selected cluster, the report must generate a **"Regulatory Blueprint"**:
*   Overlay the Consensus Map on the parcel.
*   Auto-trace the "Hard Constraints" (where buildings *must not* go).
*   Auto-trace the "Soft Constraints" (where buildings *can* go).

---

## 4. Extracting Requirements for Urban Planning Competitions (*Wettbewerbe*)

One of the most powerful use cases for OpenSKIZZE is generating the **Auslobung** (Competition Brief). Instead of vague requirements, the city can provide data-backed constraints.

### 4.1 The "Data-Driven Brief"
The report should export a specific section for competition organizers:
1.  **Morphological Guardrails**: "Competitors must respect the ventilation corridor defined in Consensus Map A."
2.  **Performance Benchmarks**: "We know a Ventilation Score of 0.75 is possible on this site. Designs scoring below 0.60 will be disqualified."
3.  **Typology Recommendations**: "We identified three viable typologies (Courtyard, Row, Point). Competitors are encouraged to explore variations of these."

### 4.2 Strategic Advantage
This prevents the common problem where a competition winner looks great visually but fails basic climate or density checks, forcing expensive redesigns later.

---

## 5. Proposed Report Structure (PDF)

The report should be structured as a **"Handout for the City Council"**:

### Section A: Executive Summary
*   **The Dilemma**: "We analyzed 50,000 variants balancing Density (GFZ) vs. Climate."
*   **The Recommendation**: "We recommend pursuing **Typology B (Courtyard)** due to high robustness."
*   **Key Metrics**: GRZ: 0.4, GFZ: 1.2, Ventilation: High.

### Section B: Robustness Analysis
*   **Visual**: "Family Tree" of the top 3 clusters.
*   **Metric**: "Adaptability Score" for each.
*   **Narrative**: "Typology A offers highest density but is fragile. Typology B is slightly less dense but highly flexible for future changes."

### Section C: Competition Guidelines (The "Consensus" Section)
*   **Visual**: Consensus Maps for the recommended typology.
*   **Actionable Output**:
    *   "Defined Ventilation Corridors (Do Not Build)."
    *   "Recommended Building Heights (Range: 12-18m)."
    *   "Target Values for Competition Entries."

### Section D: Detailed Solution Gallery
*   Renderings of the "Centroid" (most representative) solution for each cluster.
*   Shadow analysis (2h check).

---

## 6. Implementation Roadmap

1.  **Cluster Metrics**: Update `backend/analysis.py` to calculate "Cluster Size" and "Intra-cluster Variance" as user-facing metrics.
2.  **Consensus Tracing**: Implement a simple image processing routine (thresholding) to convert Consensus Heatmaps into simplified polygons (GeoJSON) for the report.
3.  **Template Design**: Create a `jinja2` or `pylatex` template that follows the structure above, specifically the "Competition Guidelines" page.
