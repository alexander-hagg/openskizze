# Fitness Calculation Visualization

## Overview

The diagnostic page now includes **🔬 Fitness Calculation Visualization** that shows step-by-step how wind porosity (fitness) is calculated for 3 sample solutions.

## What It Shows

For each of 3 random solutions, you'll see:

### Step 1: Generated Heightmap
- Heatmap showing building heights (in floors)
- Color: Dark = low, Bright = high
- Shows where the design places buildings

### Step 2: Combined with Existing (Top View)
- Combines your design with existing buildings
- Shows the complete urban environment
- Grey = occupied, Black = empty

### Step 3: Rotated Environment
- Rotates the 3D environment to align with wind direction
- Shows a mid-height horizontal slice
- Rotation angle = wind_direction + 90°

### Step 4: Wind Projection
- Projects the 3D environment along the wind axis (Y-axis)
- **This is the critical step!**
- Shows depth of obstacles in each vertical column
- Colors:
  - **Green/White (value = 0)**: Completely open passage ✅
  - **Yellow/Orange (value > 0)**: Partially blocked
  - **Red (high values)**: Heavily blocked ❌

### Fitness Calculation

```python
open_columns = count of columns where projection == 0
total_columns = total number of columns
porosity = open_columns / total_columns
fitness = porosity  # Clipped to [0.0, 1.0]
```

**Zero fitness means**: NO columns are completely open (all have obstacles)

## Example Output

```
Sample Solution 1

Heightmap Stats:
• Height range: 0.0 - 8.5 floors
• Mean height: 2.3 floors
• Occupied cells: 145

3D Building Stats:
• Design voxels: 1,234
• Existing voxels: 3,456
• Total voxels: 4,690

Wind Porosity:
• Wind direction: 90°
• Open columns: 0 / 15,625
• Porosity: 0.0000
• FITNESS: 0.0000 ❌

Problem: If all columns in Step 4 have non-zero values (shown in red/yellow), 
it means buildings completely block the wind, resulting in zero fitness.
```

## Why Fitness = 0.0

### Root Cause

Wind porosity measures **complete vertical passages** through the environment:
1. Take the 3D building array
2. Rotate it to align with wind direction
3. Project along the wind axis (sum voxels)
4. Count how many vertical columns have **zero depth** (no obstacles)

If **every column** has at least one voxel (even partially occupied), porosity = 0.0

### Common Scenarios Leading to Zero Fitness

#### Scenario 1: Dense Existing Buildings
```
Existing buildings already fill most of the grid
→ Design adds more buildings
→ No open vertical passages remain
→ Fitness = 0.0
```

#### Scenario 2: Large Buildable Area
```
Buildable area covers most of the grid
→ Random designs fill it substantially
→ Few/no gaps between buildings
→ Fitness = 0.0
```

#### Scenario 3: Wrong Wind Direction
```
Buildings aligned perpendicular to wind
→ Creates solid walls blocking wind
→ No passages along that axis
→ Fitness = 0.0
```

#### Scenario 4: Low Grid Resolution
```
Coarse grid (e.g., 50x50 cells)
→ Each cell is large (e.g., 3m x 3m)
→ Buildings span multiple cells
→ Hard to create narrow gaps
→ Fitness = 0.0
```

## Interpretation Guide

### If Step 4 Shows:
- **All red/yellow (no white)**: Zero fitness - total blockage
- **Some white patches**: Positive fitness - partial porosity
- **Mostly white**: High fitness - good wind flow

### Visual Indicators:
- **Open columns stat = 0**: Zero fitness guaranteed
- **Open columns > 0**: Positive fitness (porosity > 0)
- **Projection values all > 0**: No open passages

## Solutions to Zero Fitness Problem

### Option 1: Change Objective Function ⭐ RECOMMENDED
Don't optimize for wind porosity. Use alternatives:

```python
# Built area ratio
fitness = built_area / max_buildable_area

# Gross floor area
fitness = total_floor_area / max_floor_area

# Height diversity
fitness = std(building_heights)

# Multi-objective weighted sum
fitness = 0.3*coverage + 0.3*height_diversity + 0.4*gfa
```

### Option 2: Modify Wind Porosity Calculation
Make it less strict:

```python
# Instead of counting fully open columns, use average penetration
avg_depth = np.mean(projection)
max_depth = projection.shape[2]  # Grid height
fitness = 1.0 - (avg_depth / max_depth)  # Invert: less depth = more porosity
```

### Option 3: Reduce Existing Building Density
Filter or subsample existing buildings:

```python
# Keep only every 2nd building
env_3d_fixed[::2, ::2, :] = 0

# Or reduce height
env_3d_fixed[:, :, 5:] = 0  # Cap at 5 floors
```

### Option 4: Try Different Wind Directions
Test all cardinal directions in the diagnostic:
- 0° (North)
- 90° (East)
- 180° (South)
- 270° (West)

One direction might naturally have better porosity due to existing urban layout.

### Option 5: Increase Grid Resolution
Finer grid allows narrower gaps:

```python
DOMAIN_CONFIG['pixel_size_in_meters'] = 1.5  # Instead of 3.0
```

**Trade-off**: Higher computational cost

## Usage

1. **Select your parcel** in Step 1
2. **Go to diagnostic page** (`/diagnostic`)
3. **Click "Run Parcel Diagnostic"**
4. **Scroll to "🔬 Fitness Calculation Visualization"**
5. **Examine the 4 step visualizations** for each sample
6. **Look at Step 4**: Are there any white/green areas (open columns)?
7. **Check the stats**: Is "Open columns" = 0?

## What to Look For

### Good Signs ✅
- Step 4 shows some white/light areas
- Open columns > 0
- Fitness > 0.0
- Variation between samples

### Bad Signs ❌
- Step 4 is all red/yellow (no white)
- Open columns = 0 for all samples
- Fitness = 0.0 consistently
- "All columns blocked" message

## Expected Outcome

After viewing the visualization, you'll understand:
1. ✅ **Exactly why** fitness = 0.0
2. ✅ **Which step** causes the problem
3. ✅ **How buildings block wind** in your specific case
4. ✅ **What to change** to improve fitness

You can then decide:
- Change objective function (easiest)
- Modify wind porosity calculation
- Adjust environment parameters
- Try different wind directions

## Files Modified

- `pages/step_diagnostic.py` - Added `_visualize_fitness_calculation()` function and visualization UI

## Technical Details

Uses:
- `scipy.ndimage.rotate` - Same rotation as actual fitness function
- `plotly` heatmaps - Interactive visualizations
- Exact same calculation pipeline as `compute_fitness()` in `evaluation.py`

Ensures **100% fidelity** to the actual optimization fitness calculation.
