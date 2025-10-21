# Street Canyon Ventilation Objective Function

## Overview
The **Street Canyon Ventilation** objective is an improved wind flow surrogate designed for dense urban environments, where the original **Simple Wind Porosity** objective returns zero fitness for all solutions.

## Problem with Simple Wind Porosity
- **Algorithm**: Counts completely open vertical passages (columns with zero occupation)
- **Works well**: Sparse suburban environments with significant gaps
- **Fails**: Dense urban contexts where buildings block all vertical passages
- **Result**: fitness = 0.0 for all solutions → no optimization gradient

## Street Canyon Ventilation Solution

### Components (Weighted Combination)

#### 1. Ground-Level Street Canyons (35% weight)
- **What it measures**: Horizontal gaps at ground level along wind direction
- **How**: Scans bottom 2 layers for continuous open corridors
- **Weight**: Longer corridors score higher (better ventilation)
- **Why it matters**: Street-level airflow is most important for pedestrian comfort

#### 2. Lateral Ventilation (25% weight)
- **What it measures**: Cross-wind flow opportunities perpendicular to main wind
- **How**: Calculates openness ratio for each column perpendicular to wind
- **Why it matters**: Creates turbulence and mixing for better air circulation

#### 3. Height Variation (15% weight)
- **What it measures**: Standard deviation of building heights
- **How**: Computes height variability across the site
- **Why it matters**: Height differences create pressure gradients that drive airflow

#### 4. Partial Penetration (25% weight)
- **What it measures**: Weighted wind penetration based on blockage depth
- **How**: Inverts projection depth (less blockage = better score)
- **Why it matters**: Even partially penetrating wind is better than complete blockage

### Performance
- **100% NumPy vectorized** - no Python loops
- **Same computational complexity** as simple porosity
- **Robust gradient** - provides meaningful differences even in dense contexts

## Usage

### 1. Select in Step 2 (Constraints)
In the **Optimization Criteria** section:
- **Simple Wind Porosity**: For sparse environments with large gaps
- **Street Canyon Ventilation**: For dense urban contexts (recommended for most cases)

### 2. Automatic Application
The selected objective is automatically:
- Saved to session storage
- Passed to optimization process
- Used in fitness evaluation
- Displayed in diagnostic page

### 3. Visual Comparison
The diagnostic page shows **side-by-side comparison**:
- Simple Wind Porosity fitness
- Street Canyon Ventilation fitness
- Helps understand which objective is appropriate for your context

## When to Use Which

### Use Simple Wind Porosity when:
- Suburban/low-density environment
- Large open spaces between buildings
- Goal: Maximize through-ventilation

### Use Street Canyon Ventilation when:
- Dense urban context (most common)
- Existing buildings fill much of the site
- Street-level ventilation is priority
- Simple porosity returns 0.0 for all solutions

## Technical Details

### Input
- `heightmap_3d`: 3D voxel array (rows × cols × height)
- `wind_direction`: Integer 0-359 degrees

### Output
- Float fitness in range [0.0, 1.0]
- Higher = better ventilation

### Algorithm Steps
1. Rotate environment to align wind direction
2. Compute 4 component scores (see above)
3. Weighted combination: `0.35×S + 0.25×L + 0.15×H + 0.25×P`
4. Clip to [0.0, 1.0] range

## Example Comparison

For a dense urban parcel with existing buildings:

| Metric | Simple Porosity | Street Canyon |
|--------|----------------|---------------|
| Fitness | 0.0000 | 0.4523 |
| Open columns | 0 / 1600 | N/A |
| Street corridors | N/A | 3 corridors, avg 8m |
| Lateral openness | N/A | 0.62 |
| Height variation | N/A | σ = 4.2 floors |
| Penetration | N/A | 0.38 |

**Result**: Street Canyon objective provides optimization gradient where Simple Porosity fails.

## Code References
- Implementation: `backend/evaluation.py` → `compute_fitness_street_canyon()`
- Selection UI: `pages/step2_constraints.py` → `objective-function-selector`
- Dispatch: `backend/evaluation.py` → `eval_solution()`
- Visualization: `pages/step_diagnostic.py` → `_visualize_fitness_calculation()`
