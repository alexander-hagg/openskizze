# CRITICAL FIX: threshold_min Preventing Archive Insertion

## Problem Discovered

Your diagnostic revealed the **root cause** of empty archives:

```
ALL solutions have ZERO fitness (wind porosity = 0.0)
```

### Why This Happened

1. **Wind Porosity = 0.0** means buildings completely block wind flow
2. **Archive threshold_min was set to 0.0**
3. **pyribs requires fitness > threshold_min** (strictly greater than)
4. **Solutions with fitness = 0.0 were REJECTED** ❌

### The Math
- Constraint violations: fitness = -1.0 ❌
- Zero porosity: fitness = 0.0 ❌ (rejected because 0.0 is NOT > 0.0)
- Positive porosity: fitness > 0.0 ✅ (but rare in dense urban contexts)

## Solution Applied

Changed `threshold_min` from `0.0` to `-0.5`:

```python
# backend/optimizer.py
archive = GridArchive(
    ...
    threshold_min=-0.5  # Allow zero-fitness solutions (0.0), but reject constraint violations (-1.0)
)
```

### Why -0.5?

- ✅ Accepts fitness = 0.0 (zero porosity, but valid design)
- ✅ Accepts fitness > 0.0 (positive porosity)
- ❌ Rejects fitness = -1.0 (constraint violations)
- Creates a buffer: -0.5 < 0.0 < positive values

## Impact

**Before:**
```
Solutions with fitness = 0.0 → REJECTED
Archive stays empty → Optimization fails
```

**After:**
```
Solutions with fitness = 0.0 → ACCEPTED ✅
Archive populates → Optimization succeeds
Optimizer can then evolve towards higher fitness
```

## Why Zero Fitness Is OK

Wind porosity of 0.0 is a **valid starting point**:

1. **QD algorithms explore diversity** across feature spaces
2. **Initial solutions can be poor** - that's expected
3. **Emitters will improve fitness** over generations
4. **Feature diversity matters** more than initial fitness
5. **Zero porosity designs** may have other desirable features

The optimizer will naturally:
- Keep exploring diverse feature combinations
- Gradually evolve towards better fitness
- Replace poor solutions with better ones in the same niches

## Files Modified

1. **backend/optimizer.py** - Changed `threshold_min` from 0.0 to -0.5
2. **pages/step_diagnostic.py** - Updated test archive to match
3. **pages/step_diagnostic.py** - Enhanced error messages to explain this issue

## Testing

Run the diagnostic again:
1. Go to `/diagnostic`
2. Click "Run Parcel Diagnostic"
3. Check the **🧪 Solution Generation Test** section
4. You should now see: **"Solutions with fitness = 0.0 → ACCEPTED ✅"**

Then run the actual optimization - it should now populate the archive!

## Alternative Solutions (if still problematic)

If zero-fitness solutions still cause issues:

### Option 1: Change Fitness Function
Instead of wind porosity, optimize for:
- Building coverage ratio
- Height diversity
- Spatial distribution
- Gross floor area

### Option 2: Offset Fitness
Add a constant offset so fitness is always > 0:
```python
fitness = porosity + 0.1  # Ensures fitness >= 0.1
```

### Option 3: Multi-Objective
Use a weighted sum:
```python
fitness = 0.5 * porosity + 0.5 * (built_area / max_area)
```

But with `threshold_min=-0.5`, none of these should be necessary!

## Lesson Learned

**Always check:** Is `threshold_min` excluding valid solutions?

In QD algorithms, especially with physical constraints:
- Valid solutions can have low/zero fitness
- threshold_min should be **below** the minimum valid fitness
- Reserve very negative values (like -1.0) for true violations
- Leave room for the optimizer to explore poor but valid solutions

## Expected Outcome

✅ Archive will now populate with solutions (even zero-fitness ones)
✅ Optimization will proceed through all generations
✅ Emitters will evolve towards higher fitness over time
✅ You'll see diverse solutions across feature spaces
✅ Coverage and QD score will increase as expected
