# Visualization Fixes: Step 4b & 4c

## User Feedback & Issues Fixed

### Issue 1: Step 4c Shows Red Where Building Has Low Floors

**User's Observation:**
> "The building design has a few parts with 1 floor and a few with 2 floors. In the side view (4c), I recognized the building but on the right, some of the columns are completely red, as if the building would have 8 floors. That is not correct."

**Root Cause:**
Step 4c shows `openness_per_xz`, which represents whether **each (X, Z) position has a completely unobstructed horizontal wind path**. This calculation uses `combined_env_3d`, which includes:
- Your designed building (1-2 floors in this case)
- **Existing buildings** from the environment

So red areas at Z=8 don't mean YOUR building is 8 floors tall - they mean there's an **existing building** blocking the wind path at that location!

**Fix Applied:**
1. Updated title: `"Step 4c: Wind Paths (Design + Existing Buildings)"`
2. Updated annotation: `"Green = open path | Red = blocked by design OR existing buildings"`
3. Added warning in description: `"⚠️ Note: Red areas in 4c may include blocking from existing buildings, not just your design!"`

**Why This Is Correct:**
The fitness function calculates wind porosity for the **entire urban environment** (your design + existing context). The visualization correctly shows this. If you want to see only your design, look at Step 1 (Generated Heightmap).

---

### Issue 2: Step 4b Axes Are Switched

**User's Observation:**
> "In step 4b, shouldn't the figure be rotated CW by 90°? X and Y axis (labels) seem to be switched."

**Root Cause:**
Plotly's heatmap convention uses:
- Rows (first dimension of Z data) → Y-axis
- Columns (second dimension of Z data) → X-axis

But `wind_flow_map` had shape `(X, Y)`, so when passed directly to Plotly:
- wind_flow_map rows (X dimension) → were plotted on Y-axis ❌
- wind_flow_map columns (Y dimension) → were plotted on X-axis ❌

**Fix Applied:**
```python
# Before (wrong):
fig4b = go.Figure(data=go.Heatmap(z=wind_flow_map, ...))

# After (correct):
fig4b = go.Figure(data=go.Heatmap(z=wind_flow_map.T, ...))  # Transpose!
```

Also updated:
- Annotation position indices swapped
- Description: "Horizontal stripes" → "Vertical stripes"

**Why This Matters:**
After transposing:
- Vertical stripes (constant X, varying Y) correctly show that each X position has one openness value
- X-axis is perpendicular to wind (left-right)
- Y-axis is parallel to wind (bottom-top)

---

## Visual Comparison

### Before Fix (Step 4b):
```
Y ↑  ═══════  ← Horizontal stripe (wrong!)
     ═══════
     ═══════
     ───────→ X
```
**Problem:** X and Y were swapped!

### After Fix (Step 4b):
```
Y ↑  ║║║║║║║
     ║║║║║║║  ← Vertical stripes (correct!)
     ║║║║║║║
     ───────→ X
```
**Correct:** Each X position (vertical stripe) has one color showing wind openness

---

## Summary

### Step 4b: Top View Wind Openness
- ✅ Fixed axis orientation (transposed)
- ✅ Now shows vertical stripes (each X position has one openness value)
- ✅ X-axis = perpendicular to wind
- ✅ Y-axis = wind direction

### Step 4c: Side View Wind Paths
- ✅ Clarified that red areas include existing buildings
- ✅ Updated title and annotations
- ✅ Added warning about existing buildings in description
- ⚠️ Red columns at high Z-levels = existing buildings, not your design!

### Key Insight
**Step 4c shows the combined environment (design + existing)**, which is what the fitness function actually evaluates. This is correct! If you see red at heights where your building doesn't exist, it's because there's an existing building blocking that wind path.
