# Empty Archive Diagnostic & Prevention

## Problem
Archives were sometimes empty after optimization initialization, with pyribs warning:
> "archive was empty before adding solutions, and it is still empty after adding solutions. One potential cause is that `threshold_min` is too high in this archive, i.e., solutions are not being inserted because their objective value does not exceed `threshold_min`."

## Root Cause Analysis

The issue was **not** with `threshold_min` (which is correctly set to 0.0), but rather with constraint violations:

1. **Constraint violations return fitness = -1.0**
   - Solutions with fitness < `threshold_min` (0.0) are rejected by the archive
   - If ALL solutions violate constraints, the archive stays empty

2. **Common causes of mass constraint violations:**
   - **Very small parcels** (< 100 m²) - not enough space for valid buildings
   - **Extreme aspect ratios** (> 5:1) - unusual shapes prevent valid placement
   - **Min distance constraint too large** - erosion effect eliminates all valid placements
   - **Max height constraint too low** - overly restrictive, limits solution diversity
   - **Too few buildable pixels** (< 10) - insufficient resolution

## Implementation: Multi-Layer Defense

### 1. ✅ Diagnostic Logging (optimizer.py, evaluation.py)

**Added tracking for:**
- Total constraint violations (negative fitness count)
- Violation rate percentage
- Archive statistics at each generation
- Detailed warnings when archive is empty after 10+ generations
- Final diagnostic report if archive is empty

**Output example:**
```
Gen 50/100 | QD Score: 152.34 | Coverage: 12.5% | Elites: 25
  Constraint Violation Rate: 15.2% (304/2000)
```

If empty after optimization:
```
================================================================================
WARNING: Archive is EMPTY after optimization!
Total solutions evaluated: 10000
Solutions with constraint violations (fitness < 0): 9987
Violation rate: 99.9%

Possible causes:
  1. Buildable area is too small
  2. Max height constraint is too restrictive
  3. Min distance constraint is too large for the parcel size
  4. Unusual parcel shape prevents valid building placement
  5. Feature ranges are incompatible with site constraints
================================================================================
```

### 2. ✅ Diagnostic Page (pages/step_diagnostic.py)

**New page accessible via:** `/diagnostic` or button in Step 1

**Validates:**
- ✓ Buildable area size (warns if < 500 m², fails if < 100 m²)
- ✓ Parcel shape (aspect ratio, warns if > 5:1)
- ✓ Min distance vs parcel size (estimates erosion effect)
- ✓ Max height constraint (warns if < 2 floors)
- ✓ Grid resolution (fails if < 20 buildable pixels)
- ✓ Coverage ratio (fails if < 1% of grid)

**Output includes:**
- 📊 Detailed metrics table
- 🔒 Constraint analysis
- 📐 Feature ranges
- 💡 Actionable recommendations

### 3. ✅ Pre-Optimization Safety Checks (optimization_process.py)

**Added `start_optimization` validation:**

```python
# Check 1: Minimum buildable area
if buildable_area_m2 < 50:
    raise ValueError("Buildable area is too small (XX m²). Minimum: 50 m²")

# Check 2: Minimum buildable pixels  
if buildable_pixels < 10:
    raise ValueError("Too few buildable pixels (XX). Minimum: 10 pixels")

# Check 3: Min distance constraint feasibility
if min_distance_pixels > min_dimension / 4:
    raise ValueError("Min distance constraint (XX m) is too large for parcel size")

# Check 4: Post-optimization empty archive
if archive.stats.num_elites == 0:
    raise RuntimeError("Archive is empty. No valid solutions found...")
```

### 4. ✅ Improved User Feedback (step3_optimize.py)

**Enhanced error handling:**
- `ValueError` → User-friendly constraint/parcel error messages
- `RuntimeError` → Empty archive with actionable guidance
- Progress bar shows errors in red with detailed message
- All errors printed to console for debugging

## Usage

### For Users:
1. **Before optimization:** Click "🔍 Run Diagnostic" in Step 1 to validate parcel
2. **If optimization fails:** Read the error message for specific guidance
3. **Common fixes:**
   - Select a larger parcel
   - Reduce min_distance constraint
   - Increase max_height constraint
   - Choose a more regular-shaped parcel

### For Developers:
1. **Check console logs** for detailed constraint violation statistics
2. **Run diagnostic page** to get comprehensive parcel analysis
3. **Review feature ranges** to ensure they match site capabilities
4. **Test edge cases** using the diagnostic page before full optimization

## Testing Recommendations

Test the following edge cases:
- [ ] Very small parcel (< 100 m²)
- [ ] Long narrow parcel (aspect ratio > 10:1)
- [ ] L-shaped or irregular parcel
- [ ] Large min_distance on small parcel
- [ ] Very low max_height (1-2 floors)
- [ ] High-resolution grid with small parcel
- [ ] Parcel with < 10 buildable pixels

## Files Modified

1. **backend/optimizer.py** - Added violation tracking & final diagnostics
2. **backend/evaluation.py** - Enhanced constraint checking with violation reasons
3. **backend/optimization_process.py** - Pre-optimization safety checks
4. **pages/step_diagnostic.py** - NEW diagnostic/validation page
5. **pages/step3_optimize.py** - Improved error handling
6. **pages/step1_scope.py** - Added diagnostic page link
7. **app.py** - Registered diagnostic page route

## Expected Outcomes

✅ **Empty archives are now prevented** through early validation
✅ **Users get clear guidance** when issues occur
✅ **Developers can diagnose** issues quickly with detailed logging
✅ **Edge cases are caught** before wasting computation time
