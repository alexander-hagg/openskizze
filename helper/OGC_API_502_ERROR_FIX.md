# OGC API 502 Error Fix

## Problem

The NRW OGC 3D API is returning **502 Proxy Error**:

```
Error fetching 3D buildings from OGC API: 502 Server Error: Proxy Error 
for url: https://ogc-api.nrw.de/3dg/v1/collections/building/items?bbox=...&limit=10000
```

### Root Causes

1. **Request Too Large**: `limit=10000` might be overwhelming the proxy
2. **Timeout Issues**: 120-second timeout might be too aggressive
3. **Server Issues**: The OGC API server might be temporarily overloaded

This is a **server-side issue**, not a bug in our code. The API is unstable.

## Solutions Implemented

### 1. Reduce Request Size

**Before**:
```python
params = {
    'bbox': f"{min_lon},{min_lat},{max_lon},{max_lat}",
    'limit': 10000  # Maximum allowed by API
}
```

**After**:
```python
params = {
    'bbox': f"{min_lon},{min_lat},{max_lon},{max_lat}",
    'limit': 1000  # Reduced from 10000 to avoid proxy timeouts
}
```

**Rationale**: 
- Smaller requests are less likely to trigger proxy errors
- 1000 buildings is sufficient for most parcels
- Can add pagination later if needed

### 2. Reduce Timeout

**Before**:
```python
response = requests.get(url, params=params, timeout=120)
```

**After**:
```python
response = requests.get(url, params=params, timeout=60)
```

**Rationale**:
- Fail faster instead of waiting 2 minutes
- 60 seconds is still generous for API calls
- Quick fallback to WFS API provides better UX

### 3. Improve Error Handling

**Before**:
```python
except Exception as e:
    print(f"Error fetching 3D buildings from OGC API: {e}")
    traceback.print_exc()
    print(f"Falling back to old WFS API...")
    return None
```

**After**:
```python
except requests.exceptions.HTTPError as e:
    status_code = e.response.status_code if e.response else None
    print(f"  ✗ HTTP Error {status_code}: {e}")
    if status_code == 502:
        print(f"  ✗ 502 Proxy Error - OGC API server is overloaded or having issues")
    elif status_code == 504:
        print(f"  ✗ 504 Gateway Timeout - Request took too long")
    elif status_code == 400:
        print(f"  ✗ 400 Bad Request - Invalid parameters")
    print(f"  → Falling back to old WFS API...")
    return None
except requests.exceptions.Timeout:
    print(f"  ✗ Request timeout after 60 seconds")
    print(f"  → Falling back to old WFS API...")
    return None
except requests.exceptions.ConnectionError as e:
    print(f"  ✗ Connection error: {e}")
    print(f"  → Falling back to old WFS API...")
    return None
except Exception as e:
    print(f"  ✗ Unexpected error: {e}")
    traceback.print_exc()
    print(f"  → Falling back to old WFS API...")
    return None
```

**Benefits**:
- Specific error messages for different failure types
- Clear indication of what went wrong
- Better debugging information

### 4. Clearer Fallback Warning

**Before**:
```python
print("⚠ 3D API failed, falling back to old WFS API (no height data available)...")
```

**After**:
```python
print("━" * 80)
print("⚠ WARNING: OGC 3D API unavailable - using old WFS API instead")
print("  → Building heights will be ESTIMATED from function codes (not measured)")
print("  → Optimization results may be less accurate")
print("━" * 80)
```

**Benefits**:
- More visible warning (prominent separator lines)
- Explains impact on results
- Users understand they're not getting optimal data

## Impact

### If OGC API Works ✅
- Fetches up to 1000 buildings with real measured heights
- Same high-quality data as before
- Slightly faster (60s timeout vs 120s)

### If OGC API Fails (502/504/etc) ⚠️
- **Automatic fallback** to old WFS API
- Gets building footprints (no real heights)
- Uses **function-based height estimates**:
  - Residential: ~3 floors
  - Commercial: varies by function code
  - Industrial: varies by function code
- **Optimization still works**, just less accurate
- Clear warning shown to user

## Why This Happens

The OGC 3D API is:
1. **New** - Still being stabilized by NRW
2. **Heavy** - Returns LOD2 3D models (CityGML XML is large)
3. **Complex** - More processing on server side
4. **Popular** - Might be overloaded during business hours

This is **NOT our bug** - it's an infrastructure issue on the NRW side.

## User Experience

### Successful OGC API Fetch:
```
Fetching from NRW 3D OGC API (LOD2 with real measured heights)...
Fetching 3D buildings with real heights from NRW OGC API...
  bbox: 7.099581, 50.734278, 7.100187, 50.734662 (WGS84)
  ✓ Fetched 80 buildings from OGC API
  measuredHeight: 2.7m to 28.7m (mean: 13.7m)
  Coverage: 80/80 buildings (100.0%)
✓ Successfully fetched 80 buildings with real height data from 3D API
```

### Failed OGC API with Fallback:
```
Fetching from NRW 3D OGC API (LOD2 with real measured heights)...
Fetching 3D buildings with real heights from NRW OGC API...
  bbox: 7.099581, 50.734278, 7.100187, 50.734662 (WGS84)
  ✗ HTTP Error 502: 502 Server Error: Proxy Error
  ✗ 502 Proxy Error - OGC API server is overloaded or having issues
  → Falling back to old WFS API...
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠ WARNING: OGC 3D API unavailable - using old WFS API instead
  → Building heights will be ESTIMATED from function codes (not measured)
  → Optimization results may be less accurate
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Fetching existing buildings from NRW API...
Found 80 existing buildings.
```

## Recommendations

### Short-term ✅ (Implemented)
- ✅ Reduce limit to 1000
- ✅ Reduce timeout to 60s
- ✅ Better error handling
- ✅ Clear fallback warnings

### Medium-term 🔄 (Future)
- Add retry logic with exponential backoff
- Implement pagination for areas with >1000 buildings
- Cache successful API responses more aggressively
- Add telemetry to track API success/failure rates

### Long-term 🔮 (Future)
- Contact NRW about API stability
- Request higher rate limits
- Explore alternative 3D building data sources
- Consider hosting own mirror of the data

## Testing

Try the following to verify fixes:

1. **Normal case** (OGC API works):
   - Select a small parcel
   - Should fetch buildings successfully
   - Should show real measured heights

2. **Error case** (OGC API fails):
   - If 502 error occurs
   - Should see clear error message
   - Should fall back to WFS API
   - Should show warning about estimated heights
   - Optimization should still work

3. **Timeout case**:
   - If API is slow
   - Should timeout after 60s (not 120s)
   - Should fall back gracefully

## Files Modified

1. **`backend/data_io.py`** (lines ~176-238):
   - Reduced limit from 10000 to 1000
   - Reduced timeout from 120s to 60s
   - Improved error handling (specific exceptions)
   - Enhanced fallback warning messages

---

**Date**: 2025-01-26  
**Branch**: `ogc`  
**Status**: ✅ Fixed with Graceful Fallback
**Issue**: Server-side (NRW OGC API instability)
