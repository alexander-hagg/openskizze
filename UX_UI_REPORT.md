# OpenSKIZZE: UX/UI Analysis & Improvement Report

**Date**: November 25, 2025  
**Target Audience**: Development Team, UI/UX Designers

---

## 1. Executive Summary

The current OpenSKIZZE interface is functional and structured logically for a scientific prototype. However, to succeed as a municipal tool for urban planners, it requires a shift from "Engineering Dashboard" to "Design Tool". The focus must be on clarity, precision, and guiding the user through complex decisions without overwhelming them with technical parameters.

## 2. Current State Analysis

*   **Framework**: Dash + Bootstrap Components (Default Theme).
*   **Navigation**: Linear 6-step wizard via URL routing.
*   **Visuals**: Interactive 3D plots (Plotly) and Maps (Leaflet).
*   **Interaction**: Client-side callbacks for 3D synchronization (excellent).
*   **Language**: Bilingual toggle (DE/EN).

## 3. Strengths

1.  **Linear Workflow**: The 6-step process aligns well with the mental model of a design study (Scope -> Define -> Generate -> Evaluate).
2.  **Synchronized Views**: The client-side camera sync in Step 5 is a "killer feature" for comparing design alternatives.
3.  **Bilingual Foundation**: The architecture supports instant language switching, critical for German municipal contexts.

## 4. Weaknesses & Gaps

### A. Visual Feedback & Error Handling
*   **Silent Failures**: In `app.py`, file loading errors are printed to the console (`print(f"Error loading project file: {e}")`). The user sees nothing.
*   **Generic Styling**: The default Bootstrap theme looks like a standard admin dashboard. It lacks the "architectural" polish expected by design professionals.
*   **Progress Visibility**: While inside a step, it's unclear where the user is in the overall process (e.g., "Step 3 of 6").

### B. Usability for Planners
*   **Parameter Overload**: "QD Hyperparameters" (Sigma, Emitters) are exposed. Planners don't care about the algorithm; they care about the *result*.
*   **Precision Input**: Sliders are good for exploration, but planners often need to type exact values (e.g., "Max Height: 22.5m").
*   **Lack of Context**: No tooltips explaining complex metrics (e.g., "What is 'Street Canyon' exactly?").

## 5. Recommendations

### Phase 1: Quick Wins (Low Effort)

1.  **User Feedback System**:
    *   Implement `dbc.Toast` or `dbc.Alert` components in `app.py` to display success/error messages (e.g., "Project loaded successfully" or "Invalid file format").
2.  **Visual Stepper**:
    *   Add a "Progress Bar" or "Stepper" component at the top of `page-content` to visualize the 6 steps and allow quick navigation to previous steps.
3.  **Theme Upgrade**:
    *   Switch from default Bootstrap to a cleaner, more modern theme like **`dbc.themes.LUX`** or **`dbc.themes.MINTY`** to give it a lighter, professional look.
4.  **Precise Inputs**:
    *   Pair every `dcc.Slider` with a `dcc.Input` (number) so users can type exact constraints.

### Phase 2: Professionalization (Medium Effort)

1.  **"Expert Mode" Toggle**:
    *   Hide technical QD parameters (Sigma, Batch Size) behind an "Advanced Settings" collapse. Show only "Exploration Strength" (Low/Medium/High) to the user.
2.  **Contextual Help**:
    *   Add `dbc.Tooltip` or `html.Abbr` elements to technical terms (GRZ, GFZ, Porosity) explaining them in plain German.
3.  **3D View Controls**:
    *   Add "Preset Views" buttons to the 3D viewer: "Top View" (Lageplan), "South View", "Isometric".

### Phase 3: "Design Tool" Feel (High Effort)

1.  **Interactive Tutorial**:
    *   Add a "Tour" feature (using a library like `dash-tour` or custom overlays) for first-time users.
2.  **Report Preview**:
    *   Make the PDF report generation interactive—allow users to select which charts/views to include before downloading.

---

## 6. Action Plan

**Immediate Task**: Update `app.py` to include a `dbc.Toast` container for error handling and switch the Bootstrap theme to `LUX`.
