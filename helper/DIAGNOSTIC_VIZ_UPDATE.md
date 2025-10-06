# Diagnostic Page Wind Porosity Visualization Update

## Changes Made

Updated the diagnostic page (`pages/step_diagnostic.py`) to correctly visualize the **horizontal wind path porosity** calculation, matching the fixed `compute_fitness` function.

## Key Updates

### 1. **Corrected Simple Porosity Calculation**

**Before (Incorrect):**
```python
rotation_angle = (wind_direction + 90) % 360  # ❌ Wrong angle
projection = np.sum(rotated_env, axis=1)      # ❌ Sum instead of max
open_columns = np.sum(projection == 0)
```

**After (Correct):**
```python
rotation_angle_simple = wind_direction % 360                    # ✅ Correct angle
rotated_env_simple = rotate(..., angle=rotation_angle_simple)  # ✅ Align wind with Y-axis
max_along_wind = np.max(rotated_env_simple, axis=1)           # ✅ Check for ANY obstruction
open_paths = np.sum(max_along_wind == 0)                       # ✅ Count completely clear paths
```

### 2. **Separated Two Methods**

The diagnostic page now clearly separates two different objective functions:

#### **Method 1: Simple Horizontal Wind Porosity** (Default)
- **Rotation**: Aligns wind direction with Y-axis (no +90°)
- **Metric**: Counts percentage of (X, Z) positions with completely unobstructed horizontal paths
- **Visualization Steps**:
  - **Step 3**: Rotated environment (correct angle)
  - **Step 4a**: Building footprints (top view)
  - **Step 4b**: Horizontal wind path openness map
    - Green = completely open path through entire depth
    - Red = blocked somewhere along the path
    - Shows average openness per X position across all heights

#### **Method 2: Street Canyon Ventilation** (Alternative)
- **Rotation**: Uses +90° offset (different approach)
- **Metric**: Weighted combination of 4 components:
  1. Ground-level street canyons (35%)
  2. Lateral ventilation (25%)
  3. Height variation (15%)
  4. Partial penetration (25%)
- **Visualization Steps**:
  - **Step 5a-d**: Shows each component separately
  - Labeled as "Alternative Method" to avoid confusion

### 3. **Updated Visualizations**

#### **Step 4b: Horizontal Wind Paths**
- **Title**: Now shows porosity percentage: `"Horizontal Wind Paths (Porosity: 87.50%)"`
- **Colormap**: Green = open paths, Red = blocked paths
- **Data**: Based on `max_along_wind == 0` (completely clear paths)
- **Axes**: Clearly labeled as perpendicular vs parallel to wind direction

#### **Wind Direction Arrows**
- Added blue arrows showing wind direction on all relevant plots
- Consistent "Wind Direction ↑" annotations

### 4. **Updated Statistics Output**

```python
'wind_stats': {
    'rotation_angle_simple': 0,      # Angle for simple porosity method
    'rotation_angle_street': 90,     # Angle for street canyon method
    'open_paths': 8750,              # Number of completely open (x,z) paths
    'total_paths': 10000,            # Total (x,z) positions
    'porosity': 0.875,               # Ratio: 87.5% open
    'fitness_simple_porosity': 0.875,
    'fitness_street_canyon': 0.652
}
```

## Visual Interpretation Guide

### **Understanding the Visualizations**

1. **Step 1: Generated Heightmap**
   - Your designed buildings (2D height values)

2. **Step 2: Combined with Existing**
   - Your design + existing buildings (top view, max height)

3. **Step 3: Rotated (Simple Porosity)**
   - Environment rotated so wind flows along Y-axis
   - Shows buildings from above after rotation

4. **Step 4a: Building Footprints**
   - Top-down view with wind flowing bottom-to-top
   - Gray scale shows building heights

5. **Step 4b: Horizontal Wind Paths** ⭐ **Main Fitness Visualization**
   - **Green areas**: Wind can flow completely unobstructed through entire site depth
   - **Red areas**: Wind is blocked somewhere along its horizontal path
   - **X-axis**: Perpendicular to wind (different lateral positions)
   - **Y-axis**: With wind direction (depth through the site)
   - **Value = Fitness**: Percentage of green area = porosity fitness score

6. **Step 5a-d: Street Canyon Components** (Alternative Method)
   - Shows 4 different urban ventilation metrics
   - Uses different rotation angle and calculation
   - For comparison purposes

## Testing the Visualization

To test the updated visualizations:

1. Run the app: `python app.py`
2. Navigate to the "Diagnostic" page
3. Click "Test Fitness Calculation"
4. Observe:
   - Step 4b should show meaningful green/red patterns
   - Fitness score should match the porosity percentage
   - Empty environment → 100% green
   - Dense environment → mostly red
   - Wind direction arrows should point in consistent direction

## Consistency Check

The diagnostic page now calculates fitness **exactly the same way** as:
- `backend/evaluation.py::compute_fitness()` function
- `tests/test_wind_porosity.py` test suite

All three should produce identical fitness values for the same input.
