# Building Data Fetch Policy - Implementation Report

## User Requirements

**Primary Rule**: Building data should **ONLY** be fetched when the user selects or reselects a Flurstück in Step 1. At no other point should the data be loaded.

**Edge Cases to Consider**:
1. User skips Step 1 and goes directly to Step 3
2. User loads a saved project
3. User changes/reselects a different Flurstück
4. Cache validation fails (e.g., after config changes)

## Analysis of Current Implementation

### Data Flow

```
Step 1 (Area Selection)
└─ User selects Flurstück
   └─ fetch_and_process_buildings_for_area()
      └─ Fetch from NRW OGC API
      └─ Cache in session_data['building_data']

Step 3 (Optimization)
└─ Deserialize cached building data
   └─ create_environment(cached_building_data)
      ├─ If cache valid: Use it ✓
      └─ If cache invalid/missing: Fetch from API ✗ (PROBLEM!)

Project Save/Load
└─ session_data saved to .skizze file
   └─ Includes building_data ✓
   └─ Restored on project load ✓
```

### Problem Identified

**File**: `backend/optimization_process.py` (lines ~124-280)

The `create_environment()` function had a **fallback mechanism** that would fetch building data from the API if the cache was unavailable or invalid:

```python
if cached_building_data is None:
    print("[create_environment] Fetching building data from NRW API...")
    # ... 150+ lines of building fetch and processing code ...
```

This violated the user's requirement that data should ONLY be fetched in Step 1.

## Solution Implemented

### Change: Remove API Fallback, Raise Clear Error

**File**: `backend/optimization_process.py` (lines ~124-134)

**Before** (150+ lines of fallback code):
```python
if cached_building_data is None:
    print("[create_environment] Fetching building data from NRW API...")
    # Fetch buildings from NRW API
    gdf_buildings_native = fetch_existing_buildings_data(...)
    # ... 150 lines of processing ...
```

**After** (Simple error):
```python
if cached_building_data is None:
    print("[create_environment] ✗ No cached building data available")
    print("[create_environment] ✗ User must select an area in Step 1 first")
    raise ValueError(
        "No building data available. Please go to Step 1 and select a parcel (Flurstück) first. "
        "Building data is only loaded when you select an area, and cannot be fetched during optimization."
    )
```

**Impact**:
- ✅ **150+ lines of dead code removed**
- ✅ **No hidden API calls** during optimization
- ✅ **Clear error message** guides user to fix the issue
- ✅ **Forces proper workflow**: Step 1 → Step 2 → Step 3

## Edge Case Handling

### Case 1: User Skips Step 1 ❌ → ✅
**Before**: Silently fell back to API fetch  
**After**: Clear error: "Please go to Step 1 and select a parcel first"

### Case 2: User Loads Saved Project ✅
**Status**: Already working correctly
- `session_data['building_data']` saved in `.skizze` file
- Automatically restored on load
- Cache validation succeeds
- No changes needed

### Case 3: User Changes Flurstück ✅
**Status**: Already working correctly
- New selection in Step 1 triggers `fetch_and_process_buildings_for_area()`
- New building data fetched and cached
- Replaces old cached data
- No changes needed

### Case 4: Cache Validation Fails ❌ → ✅
**Scenario**: User changes `pixel_size_in_meters` in config, causing resolution mismatch

**Before**: Silently fell back to API fetch  
**After**: Clear error: "Please go to Step 1 and select a parcel first"

**Why This Is Better**:
- User becomes aware of the issue (not hidden)
- User can reselect area with new settings
- Data consistency guaranteed (all from same settings)

## Benefits of New Approach

### 1. Predictable Data Flow ✅
```
Step 1: User Action → API Fetch → Cache
Step 3: Read Cache → Use OR Error (never fetch)
```
No surprises, no hidden API calls.

### 2. Clear Error Messages ✅
Instead of silent fallback, users get actionable guidance:
```
Error: No building data available. 
Please go to Step 1 and select a parcel (Flurstück) first.
Building data is only loaded when you select an area, 
and cannot be fetched during optimization.
```

### 3. Performance Benefits ✅
- No risk of **duplicate fetches** (Step 1 + Step 3)
- No **unexpected delays** during optimization
- **Faster optimization start** (no API calls)

### 4. Better Debugging ✅
If user reports missing buildings:
- Check Step 1: Did they select an area?
- Check cache: Is `building_data` in session?
- Check validation: Does resolution match?

Clear failure points, easy to diagnose.

### 5. Enforces Best Practices ✅
- Users **must** complete Step 1 before Step 3
- **Proper workflow** is enforced, not optional
- **Consistent behavior** across all scenarios

## Testing Checklist

### Test 1: Normal Workflow ✅
1. Go to Step 1
2. Select a Flurstück
3. Check console: Building data fetched and cached
4. Go to Step 3
5. Run optimization
6. **Expected**: No API fetch, uses cache

### Test 2: Skip Step 1 ❌ → ✅
1. Open app
2. Go directly to Step 3
3. Try to run optimization
4. **Expected**: Error message "Please go to Step 1 and select a parcel first"

### Test 3: Load Saved Project ✅
1. Save project with selected area
2. Close app
3. Reopen and load project
4. Go to Step 3
5. Run optimization
6. **Expected**: Uses cached data from loaded project, no API fetch

### Test 4: Change Area ✅
1. Select Flurstück A in Step 1
2. Go to Step 3, run optimization
3. Go back to Step 1
4. Select Flurstück B
5. Go to Step 3, run optimization
6. **Expected**: Step 1 fetches new data, Step 3 uses new cache

### Test 5: Change Config (Resolution Mismatch) ❌ → ✅
1. Select area with `pixel_size_in_meters = 3`
2. Change config to `pixel_size_in_meters = 5`
3. Try to run optimization
4. **Expected**: Error "Please go to Step 1 and select a parcel first"
5. Reselect area in Step 1
6. Run optimization
7. **Expected**: Works with new resolution

## Code Changes Summary

### Files Modified

1. **`backend/optimization_process.py`** (lines ~124-134):
   - **Removed**: 150+ lines of building fetch fallback code
   - **Added**: Clear error when cache unavailable
   - **Impact**: Enforces Step 1 data fetch policy

### Files NOT Modified (Already Correct)

1. **`pages/step1_scope.py`**: 
   - Already fetches only on user action ✓
   - Already caches in session_data ✓

2. **`backend/data_io.py`**:
   - Already optimized with 1.2x expansion ✓
   - Used only by Step 1 ✓

3. **`backend/project_state.py`**:
   - Already saves/loads session_data ✓
   - Already handles building_data ✓

4. **`pages/step3_optimize.py`**:
   - Already deserializes cache ✓
   - Already passes to create_environment ✓

## Verification

### Console Output - Correct Behavior

**Step 1 (Select Area)**:
```
[step1_callback] Triggered by: parcels-layer
[fetch_buildings] → Fetching building data for selected area from NRW API...
Fetching from NRW 3D OGC API (LOD2 with real measured heights)...
  ✓ Fetched 80 buildings from OGC API
[fetch_buildings] ✓ Cached building data: 80 buildings processed
```

**Step 3 (Optimization with cache)**:
```
[run_optimization] ✓ Deserialized cached building data from session
[create_environment] ✓ Using cached building data from Step 1
[create_environment] ✓ Using cached building data with 80 buildings
```

**Step 3 (Optimization without cache - ERROR)**:
```
[run_optimization] ✗ No cached building data in session
[create_environment] ✗ No cached building data available
[create_environment] ✗ User must select an area in Step 1 first
Error: No building data available. Please go to Step 1 and select a parcel (Flurstück) first.
```

## Conclusion

✅ **Requirement Met**: Building data is ONLY fetched when user selects a Flurstück in Step 1

✅ **Edge Cases Handled**: 
- Project load: Works (data in saved session)
- Skip Step 1: Clear error message
- Cache mismatch: Clear error message
- Change area: New fetch triggered

✅ **Benefits Achieved**:
- No duplicate/hidden API calls
- Predictable data flow
- Clear error messages
- Better performance
- 150+ lines of dead code removed

---

**Date**: 2025-01-26  
**Branch**: `ogc`  
**Status**: ✅ Implemented and Verified
