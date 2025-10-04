# Enhanced Diagnostic Page - Solution Insertion Testing

## Problem
Even when parcel metrics look fine, the archive can still be empty after initialization. We need to understand **exactly why** solutions are not being inserted into the archive.

## Solution: Live Solution Generation Test

The diagnostic page now includes a **🧪 Solution Generation Test** that:

### What It Does

1. **Creates a test archive** with the same configuration as optimization
2. **Generates 100 random solutions** using the same encoding/evaluation pipeline
3. **Attempts to insert each solution** into the archive
4. **Tracks detailed statistics:**
   - Negative fitness count (constraint violations)
   - Zero fitness count
   - Positive fitness count
   - Actual insertion success count
   - Success rate percentage

5. **Analyzes failure modes:**
   - ALL solutions violate constraints
   - High constraint violation rate
   - Positive fitness but not inserted (range/archive issue)
   - Zero fitness (wind porosity issue)

6. **Shows sample solutions** with:
   - Fitness value
   - Feature values
   - Whether it was inserted (YES/NO)
   - Feature ranges for comparison

## Output Examples

### ❌ Scenario 1: ALL Constraints Violated
```
Critical: NO solutions can be inserted into archive!
Tested 100 random solutions, NONE were accepted.

Detailed Breakdown:
• Solutions with negative fitness (constraint violations): 100
• Solutions with zero fitness: 0
• Solutions with positive fitness: 0
• Solutions actually inserted: 0

Most Common Issue:
ALL solutions violate constraints (fitness = -1). This means NO solutions can meet the hard constraints.

Feature Values from Failed Solutions:
Sample 1:
  Fitness: -1.0000
  Features: ['450.23', '12.45', '3.21', '5.00']
  Inserted: NO
  Feature Ranges: [[0.0, 1200.0], [0.0, 15.0], [0.0, 7.5], [0.0, 20.0]]
...
```

### ⚠️ Scenario 2: Low Success Rate
```
Very Low Success Rate: 5.0%
Only 5 out of 100 solutions were inserted.

Breakdown:
• Constraint violations (negative fitness): 85
• Zero fitness: 10
• Positive fitness: 15
• Actually inserted: 5
```

### ✅ Scenario 3: Healthy Success Rate
```
Success Rate: 45.0%
45 out of 100 solutions were successfully inserted.

• Constraint violations: 35
• Valid solutions: 65
```

### 🔍 Scenario 4: Positive Fitness but Not Inserted
```
Solutions have positive fitness but are NOT being inserted. 
This indicates a feature range or archive configuration issue.

Sample 3:
  Fitness: 0.3456
  Features: ['1850.23', '18.45', '3.21', '5.00']  <-- OUTSIDE range!
  Inserted: NO
  Feature Ranges: [[0.0, 1200.0], [0.0, 15.0], [0.0, 7.5], [0.0, 20.0]]
```

## Common Issues Revealed

### Issue 1: Feature Range Mismatch
**Symptoms:** Positive fitness, but feature values exceed ranges
**Cause:** Dynamic range calculation doesn't account for actual solution space
**Fix:** Adjust feature ranges in `_calculate_dynamic_feat_ranges()`

### Issue 2: Min Distance Too Restrictive
**Symptoms:** 90%+ constraint violations
**Cause:** Buildings can't be placed without being too close
**Fix:** Reduce min_distance or select larger parcel

### Issue 3: Zero Fitness (Wind Porosity)
**Symptoms:** Many solutions with fitness = 0.0
**Cause:** Buildings block all wind (poor porosity)
**Fix:** Usually OK - optimizer will find better solutions

### Issue 4: Max Height Too Low
**Symptoms:** High constraint violation rate
**Cause:** Clipping removes all building mass
**Fix:** Increase max_height constraint

## Usage

1. **Select a parcel** in Step 1
2. **Navigate to diagnostic page** (click "🔍 Run Diagnostic")
3. **Click "Run Parcel Diagnostic"**
4. **Review the Solution Generation Test** section
5. **Examine sample solutions** to see exactly why they fail
6. **Adjust constraints** based on the specific issue identified

## Technical Details

The test uses:
- Same `GridArchive` configuration as optimization
- Same `ParametricEncoding` for genome → heightmap
- Same `eval_solution` function for fitness/features
- Same constraint checking logic
- Same feature calculation

This ensures **100% fidelity** to the actual optimization process.

## Benefits

✅ **Identifies exact failure mode** (constraints, ranges, fitness, etc.)
✅ **Shows actual feature values** that cause rejection
✅ **Reveals feature range mismatches** immediately
✅ **Tests before wasting computation** on full optimization
✅ **Provides actionable diagnostics** with sample data

## Files Modified

- `pages/step_diagnostic.py` - Added `_test_solution_insertion()` function and UI display

## Next Steps

If the diagnostic reveals:
1. **All constraint violations** → Relax constraints or select larger parcel
2. **Feature range issues** → Check `_calculate_dynamic_feat_ranges()` logic
3. **Zero fitness** → Usually OK, but verify wind direction settings
4. **Positive fitness not inserted** → Debug archive configuration or feature calculation
