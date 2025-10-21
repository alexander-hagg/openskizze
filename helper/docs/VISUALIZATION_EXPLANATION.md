# Understanding the Wind Path Visualizations

## Why Do You See Horizontal Lines in Step 4b?

You asked a great question: "Why horizontal lines when wind comes from the south?"

### The Answer: It's Correct, But Confusing!

The horizontal lines are **actually correct** for what Step 4b is showing, but the visualization is non-intuitive. Let me explain:

## What Each Visualization Shows

### Step 4a: Building Footprints (Top View)
- **What it shows**: Buildings from above (bird's eye view)
- **Axes**: X (left-right) × Y (bottom-top, wind direction)
- **Colors**: Grayscale = building height

### Step 4b: Wind Path Openness (Top View with Horizontal Stripes)
- **What it shows**: For each X position, the average wind path openness across all heights
- **Why horizontal stripes?** Because each X position has ONE openness value (averaged across Z), which is then repeated across all Y positions
- **Physical meaning**: "Can wind flow through this X slice?"
  - Green stripe = wind can flow through this X position at multiple heights
  - Red stripe = wind is blocked at this X position across most heights
- **Why this is confusing**: The Y-axis shows depth in wind direction, but the color doesn't vary with Y (because we already checked the entire Y-depth!)

### Step 4c: Side View - Unobstructed Wind Corridors ⭐ **MOST INTUITIVE**
- **What it shows**: Direct visualization of which (X, Z) positions have completely unobstructed horizontal wind paths
- **Axes**: X (left-right) × Z (height)
- **Wind direction**: INTO the page (along Y-axis, which is the depth dimension)
- **Colors**: 
  - Green = wind can flow through ENTIRE depth at this (X, Z) coordinate without hitting any obstacle
  - Red = wind hits an obstacle somewhere along the depth at this (X, Z) coordinate
- **This is the actual fitness metric!** Count of green cells / total cells = porosity fitness

## Visual Example

```
Top View (Step 4b - confusing):
   Y (wind direction ↑)
   │ ████████ ← Red stripe (X=0 blocked)
   │ ████████
   │ ▓▓▓▓▓▓▓▓ ← Yellow stripe (X=1 partially open)
   │ ▓▓▓▓▓▓▓▓
   │ ░░░░░░░░ ← Green stripe (X=2 open)
   │ ░░░░░░░░
   └─────────→ X (perpendicular to wind)
   
Why horizontal? Each X position gets ONE color based on 
whether wind can flow through it across all heights.

Side View (Step 4c - intuitive):
   Z (height ↑)
   │ ████▓▓░░ ← Different (X,Z) have different openness
   │ ████░░░░
   │ ██▓▓░░░░
   └─────────→ X (perpendicular to wind)
   
Wind flows INTO page (along Y). Each cell shows if that
specific (X,Z) position has a completely open path.
```

## Key Insight

**Step 4b** answers: "Can wind flow through each X position?" (averaged over heights, repeated over Y)  
**Step 4c** answers: "Can wind flow through each (X, Z) position?" (the actual fitness calculation!)

**Step 4c is the one you should focus on** - it directly shows the `max_along_wind == 0` check that determines fitness!

## How to Read Step 4c

1. **Green cells**: Completely unobstructed horizontal wind corridors
   - Wind can flow from Y=0 to Y=max without hitting any building at this (X, Z)
   
2. **Red cells**: Blocked wind paths  
   - Wind hits a building somewhere along the Y-axis at this (X, Z)

3. **Fitness = Green cells / Total cells**
   - E.g., 87 green cells out of 100 total = 0.87 fitness

## Summary

- **Step 4b**: Top view with horizontal stripes (correct but confusing)
- **Step 4c**: Side view (X vs Z) showing actual open/blocked paths ⭐ **USE THIS ONE!**

The horizontal stripes in 4b are mathematically correct, but 4c is much more intuitive for understanding wind porosity!
