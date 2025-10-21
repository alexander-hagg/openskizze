# Feature Selection and Range Fixes

## Issues Fixed

### 1. Wrong Feature Labels on Page 3 (FIXED ✅)

**Problem**: When deselecting features, wrong labels appeared on page 3 after optimization.

**Root Cause**: The `translate_feature_labels()` function requires 3 parameters:
- `feature_indices`: List of selected feature indices (e.g., `[0, 2, 4]`)
- `lang`: Language ('DE' or 'EN')
- `feature_set`: Either 'original' or 'planning'

Multiple callbacks were missing the `feature_set` parameter, causing planning features to use original feature labels.

**Files Fixed**:
- `pages/step3_optimize.py` (3 locations)
- `pages/step4_compare.py` (3 locations)  
- `pages/step5_compare_detail.py` (2 locations)

**Changes Made**:
```python
# BEFORE (wrong - missing feature_set)
labels = translate_feature_labels(feature_indices, lang)

# AFTER (correct - includes feature_set)
feature_set = results_data.get('feature_set', 'original')
labels = translate_feature_labels(feature_indices, lang, feature_set)
```

---

### 2. Low Archive Coverage with Planning Features

**Problem**: Planning features produce only 0.01% coverage (32 elites) vs expected 5-10% (hundreds of elites).

**Root Causes Identified**:

#### A. GFZ Calculation Error (FIXED ✅)
- **File**: `backend/evaluation.py`
- **Issue**: GFZ was calculated as `sum(heightmap) * pixel_area / buildable_area`
  - This treated height in meters as floor area directly
  - Should divide height by 3.0 first (3m per floor)
- **Fix**: Changed to:
  ```python
  num_floors_per_pixel = heightmap / 3.0  # Convert height to floors
  total_floor_area_m2 = np.sum(num_floors_per_pixel) * pixel_area
  gfz = total_floor_area_m2 / buildable_area_in_sq_meters
  ```
- **Impact**: GFZ values now in correct range [0, ~4] instead of [0, ~12]

#### B. H/W Aspect Ratio Range Too Wide (FIXED ✅)
- **File**: `backend/optimization_process.py`
- **Issue**: Range was [0, 5.0] but actual values are [0, 0.67]
  - With typical building spacing (20-100m) and heights (5-30m), ratios are 0.1-2.0 in practice
  - Wide range causes solutions to cluster in small portion of feature space
- **Fix**: Changed max_aspect_ratio from 5.0 to 2.0
  ```python
  # BEFORE
  max_aspect_ratio = 5.0 if min_distance_meters < 3 else max_height_meters / min_distance_meters
  
  # AFTER  
  max_aspect_ratio = 2.0  # Conservative max matching real distributions
  ```

#### C. Feature Ranges Depend on Parcel Parameters (DOCUMENTED ⚠️)
- **File**: `diagnose_feature_ranges.py` (updated to accept separate width/length)
- **Issue**: Default diagnostic used fixed 34×34 grid, but actual parcels vary
- **Fix**: Updated diagnostic script to accept command-line arguments:
  ```bash
  python diagnose_feature_ranges.py [grid_width] [grid_length] [max_height] [min_distance]
  
  # Examples:
  python diagnose_feature_ranges.py 50 50 25 5    # Square 150m×150m, 25m height, 5m distance
  python diagnose_feature_ranges.py 67 33 30 3    # Rectangular 200m×100m
  ```

---

## Testing Recommendations

### Test Feature Label Fixes
1. Start app: `python run.py`
2. Go to Step 2
3. Switch to "Planning-Focused Features"
4. Select only features 0, 2, 4 (GRZ, Avg Height, Num Buildings)
5. Run optimization
6. **Verify**: Step 3 axis dropdowns show correct planning labels:
   - Feature 0 = "GRZ (Grundflächenzahl)" not "Bebaute Fläche"
   - Feature 2 = "Durchschnittliche Bauhöhe" (same for both sets)
   - Feature 4 = "Anzahl der Gebäude" (same for both sets)

### Test Planning Feature Ranges
1. Run diagnostic with your actual parameters:
   ```bash
   python diagnose_feature_ranges.py [width] [length] [max_height] [min_distance]
   ```
2. Check output:
   - **GFZ**: Should be in range [0.3, 4.0] (not exceeding expected max)
   - **H/W Aspect Ratio**: Should use 1-2 bins out of 5 (20-40%) - this is normal
   - **All features**: Should have "✓" not "⚠ OUT OF RANGE!"

3. Run actual optimization with planning features:
   - Expected coverage: 1-5% (not 0.01%)
   - Expected elites: 50-500 (not 32)
   - If still low coverage, check which features are too narrow

---

## Remaining Issues to Investigate

### If Coverage Still Low After Fixes:

**Check narrow feature distributions**:
- Run `python diagnose_feature_ranges.py [your_params]`
- Look for features using < 20% of bins
- Likely culprits:
  - **SVF (Sky View Factor)**: May cluster around 0.6-0.8
  - **Number of Buildings**: Random solutions produce 1-6, not 1-10
  - **GFZ**: Even with fix, may cluster around 1.0-2.0

**Potential Solutions**:

1. **Reduce archive dimensions** (use fewer features):
   - Instead of 4 features × 5 bins = 625 cells
   - Use 3 features × 5 bins = 125 cells
   - This increases effective coverage

2. **Adjust QD hyperparameters** for more exploration:
   ```python
   QD_CONFIG = {
       'num_generations': 500,  # More generations
       'num_emitters': 10,      # More emitters
       'sigma': 0.15,           # Larger mutations (was 0.1)
       'batch_size': 32,        # Larger batches (was 16)
   }
   ```

3. **Tighten feature ranges** to match actual distributions:
   - If GFZ actually ranges [0.5, 3.0], don't use [0, 10]
   - If H/W actually ranges [0.1, 0.8], don't use [0, 2.0]
   - Modify `_calculate_dynamic_feat_ranges()` accordingly

4. **Switch to simpler features**:
   - Replace H/W (narrow) with Avg Distance (wider)
   - Replace SVF (narrow) with GFA (wider)

---

## Files Modified

1. **backend/evaluation.py** - Fixed GFZ calculation
2. **backend/optimization_process.py** - Fixed H/W aspect ratio range
3. **diagnose_feature_ranges.py** - Added width/length parameters
4. **pages/step3_optimize.py** - Fixed 3 translate_feature_labels() calls
5. **pages/step4_compare.py** - Fixed 3 translate_feature_labels() calls
6. **pages/step5_compare_detail.py** - Fixed 2 translate_feature_labels() calls

---

## Summary

**Issue #1 (Wrong Labels)**: ✅ **FIXED**
- All visualization pages now pass `feature_set` to `translate_feature_labels()`
- Planning features will show correct German/English labels

**Issue #2 (Low Coverage)**: ⚠️ **PARTIALLY FIXED**
- GFZ calculation corrected (was 3× too high)
- H/W aspect ratio range reduced (5.0 → 2.0)
- **But**: Some planning features have naturally narrow distributions
- **Next**: Run diagnostic with your actual parameters to see if coverage improves
- **If not**: Consider adjusting QD hyperparams or using fewer features

Run the diagnostic and let me know the results!
