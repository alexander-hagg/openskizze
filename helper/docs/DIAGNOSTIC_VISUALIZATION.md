# Enhanced Diagnostic Visualization: Street Canyon Objective

## Overview
The diagnostic page now shows **detailed step-by-step visualizations** for BOTH objective functions side-by-side, making it easy to understand why one works and the other doesn't in your specific context.

---

## What's New

### 1. Structured Layout
Each sample solution now shows three sections:

#### Section 1: Common Steps (1-3)
- **Step 1**: Generated heightmap (design)
- **Step 2**: Combined with existing buildings
- **Step 3**: Rotated to align with wind direction

These steps are identical for both methods.

#### Section 2: Simple Wind Porosity
- **Step 4a**: Wind projection visualization
- Shows which columns are completely open (green) vs blocked (red)
- Clearly displays why fitness = 0.0 in dense contexts

#### Section 3: Street Canyon Ventilation (NEW!)
Four component visualizations showing how the fitness is calculated:

1. **Step 4b: Ground-level Street Canyons (35% weight)**
   - Green heatmap showing horizontal corridors at ground level
   - Brighter = more open space for pedestrian-level ventilation
   - Score displayed below

2. **Step 4c: Lateral Ventilation (25% weight)**
   - Blue heatmap showing cross-wind flow opportunities
   - Measures openness perpendicular to main wind direction
   - Score displayed below

3. **Step 4d: Height Variation (15% weight)**
   - Purple/viridis heatmap showing building height distribution
   - More variation = better turbulence and mixing
   - Score displayed below

4. **Step 4e: Partial Penetration (25% weight)**
   - Orange heatmap showing weighted wind penetration
   - Even partial penetration gets credit (not all-or-nothing)
   - Score displayed below

---

## Visual Comparison

### For Dense Urban Context (Your Case)

**Simple Wind Porosity (Step 4a):**
```
Projection: [All RED/YELLOW - completely blocked]
Open columns: 0 / 1600
Fitness: 0.0000 ❌
```

**Street Canyon Ventilation (Steps 4b-4e):**
```
Step 4b (Ground Canyons):     [GREEN corridors visible] → Score: 0.42
Step 4c (Lateral Ventilation): [BLUE openness areas]    → Score: 0.58
Step 4d (Height Variation):    [VARIED heights]         → Score: 0.31
Step 4e (Partial Penetration): [ORANGE gradients]       → Score: 0.44

Combined Fitness = 0.35×0.42 + 0.25×0.58 + 0.15×0.31 + 0.25×0.44
                 = 0.147 + 0.145 + 0.047 + 0.110
                 = 0.449 ✅
```

---

## Component Explanations

### 1. Ground-level Street Canyons (35%)
**What it shows:** Green heatmap (top-down view after rotation)
- Bright green = open ground space
- Dark/black = occupied by buildings
- Horizontal corridors are clearly visible

**What it measures:**
- Continuous open corridors along wind direction
- Longer corridors score higher
- Most important for street-level airflow

**Why it matters:**
- Pedestrian-level ventilation
- Street network connectivity
- Primary airflow pathways

### 2. Lateral Ventilation (25%)
**What it shows:** Blue heatmap (top-down view)
- Bright blue = high openness
- Dark blue = low openness
- Shows cross-ventilation potential

**What it measures:**
- Openness ratio for each column perpendicular to wind
- Creates turbulence and mixing
- Enables cross-ventilation

**Why it matters:**
- Prevents stagnant air pockets
- Multi-directional airflow
- Better air quality distribution

### 3. Height Variation (15%)
**What it shows:** Purple/viridis heatmap
- Shows maximum building height per cell
- Color gradient indicates height differences
- Standard deviation computed

**What it measures:**
- Building height diversity across site
- Normalized by maximum possible variation
- Higher variance = better score

**Why it matters:**
- Height differences create pressure gradients
- Drives vertical air movement
- Turbulence improves mixing

### 4. Partial Penetration (25%)
**What it shows:** Orange heatmap (projection view)
- Bright orange = high penetration (low blockage)
- Dark orange = low penetration (high blockage)
- Shows weighted wind passage

**What it measures:**
- Inverse of blockage depth
- 1.0 - (blockage / max_height)
- Gives credit for partial wind passage

**Why it matters:**
- Not all-or-nothing like simple porosity
- Even partial wind flow helps
- More realistic for dense contexts

---

## Reading the Visualizations

### Color Scales

**Simple Porosity (Step 4a):**
- Green = 0 (completely open)
- Yellow = medium blockage
- Red = high blockage
- Scale: 0 to max_height

**Ground Canyons (Step 4b):**
- Bright green = open ground space
- Dark/black = building footprint
- Binary: open vs occupied

**Lateral Ventilation (Step 4c):**
- Bright blue = high openness (0.8-1.0)
- Dark blue = low openness (0.0-0.2)
- Continuous scale

**Height Variation (Step 4d):**
- Purple = low/no building
- Yellow/white = tall buildings
- Shows actual heights (floors)

**Partial Penetration (Step 4e):**
- Bright orange = high penetration (0.8-1.0)
- Dark orange = low penetration (0.0-0.2)
- Continuous scale

---

## Formula Display

Each sample shows the complete calculation:

```
Combined Fitness = 0.449
= (0.35 × 0.420) + (0.25 × 0.580) + (0.15 × 0.310) + (0.25 × 0.440)
   ↑       ↑         ↑       ↑         ↑       ↑         ↑       ↑
  35%   Canyons    25%   Lateral    15%   Height    25%   Penetration
```

This makes it crystal clear how each component contributes to the final fitness.

---

## Interpretation Guide

### When Street Canyon Works Better

**You'll see:**
- Step 4a (Simple): ALL red, fitness = 0.0
- Step 4b (Canyons): Some green corridors visible
- Step 4c (Lateral): Blue patches showing openness
- Step 4d (Height): Varied colors showing height diversity
- Step 4e (Penetration): Orange gradients (not all dark)
- **Final fitness**: 0.3-0.6 range

**This means:**
- Dense environment blocks vertical passages
- But horizontal corridors exist
- Cross-ventilation is possible
- Height variation helps
- Partial wind penetration occurs
- **Use Street Canyon objective!**

### When Simple Porosity Works

**You'll see:**
- Step 4a (Simple): Some green columns, fitness > 0.2
- Step 4b-4e: Also show high scores
- **Final fitness**: Both methods > 0.3

**This means:**
- Sparse enough for vertical passages
- Either objective will work fine
- Simple Porosity may be faster

### When Both Fail

**You'll see:**
- Step 4a: All red, fitness = 0.0
- Steps 4b-4e: All dark/minimal features
- **Final fitness**: Both < 0.1

**This means:**
- Extremely dense environment
- No ventilation possible
- Consider different parcel or objectives

---

## Example Output

```
Sample Solution 1
├─ Heightmap Stats: 3-8 floors, mean 5.2, 145 occupied cells
├─ 3D Stats: 1250 design voxels, 3400 existing, 4650 total
└─ Wind Analysis: 0° rotation, 0/1600 open columns

Fitness Comparison:
├─ 🏙️ Simple Wind Porosity: 0.0000 ❌
└─ 🌬️ Street Canyon Ventilation: 0.4523 ✅

📊 Common Steps (Both Methods):
[Heightmap] [Combined] [Rotated]

🏙️ Simple Wind Porosity Method:
[Projection - ALL RED]
Result: 0/1600 open. Fitness = 0.0000

🌬️ Street Canyon Ventilation (4 Components):
[Ground Canyons]  [Lateral Flow]  [Height Var]  [Penetration]
    0.420            0.580           0.310          0.440

Combined = 0.35×0.420 + 0.25×0.580 + 0.15×0.310 + 0.25×0.440 = 0.4523
```

---

## Benefits

### 1. Clear Understanding
- See exactly why Simple Porosity fails
- Understand what Street Canyon detects
- Visual proof that horizontal flow exists

### 2. Component Breakdown
- Know which component contributes most
- Identify weak points
- Potential for tuning weights

### 3. Debugging Aid
- Verify fitness calculation is correct
- Check if rotation is working
- Validate component logic

### 4. Decision Support
- Visual evidence for choosing objective
- Helps explain to stakeholders
- Documents why method selection matters

---

## Next Steps

1. **Run diagnostic page** with your dense urban parcel
2. **Review visualizations** for 3 sample solutions
3. **Compare Step 4a vs Steps 4b-4e**
4. **Check if recommendation appears** to use Street Canyon
5. **Proceed to optimization** with selected objective

The enhanced visualization will clearly show you whether Street Canyon Ventilation can provide a better gradient for your specific context! 🎯
