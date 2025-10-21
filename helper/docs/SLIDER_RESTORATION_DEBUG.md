# Feature Range Slider Restoration - Debugging Guide

## Issue
When reloading the page (F5) or navigating back from Step 3 to Step 2, the feature range sliders are being reset to default values instead of preserving the user's last settings.

## Implementation

### Changes Made

1. **Added URL trigger to `create_range_sliders` callback**
   - The callback now triggers both when `measures-checklist` changes AND when URL changes
   - This ensures sliders are recreated when navigating to the page

2. **Added logic to handle URL-triggered recreation**
   - When triggered by URL change, the callback checks if we're on '/step2'
   - It reads `selected_features` from `session_data` instead of from the Input
   - This ensures the correct features are used when the page is loaded

3. **Added debug logging**
   - Logs when feature ranges are saved to session
   - Logs when feature ranges are restored from session
   - This helps identify if data is being saved/restored correctly

### Code Flow

#### When User Adjusts Sliders:
1. User moves a range slider
2. `update_session_with_features_and_ranges` callback fires
3. Saves `feature_ranges` to `session-store`
4. Console: `[DEBUG] Saving feature ranges to session: {...}`

#### When User Navigates Back to Step 2:
1. URL changes to '/step2'
2. `restore_step2_from_session` callback fires
   - Updates `measures-checklist` with saved `selected_features`
3. `create_range_sliders` callback fires (triggered by both URL AND checklist change)
   - Reads `feature_ranges` from `session-store`
   - Creates sliders with saved values
   - Console: `[DEBUG] Restoring feature ranges from session: {...}`

#### When User Reloads Page (F5):
1. Browser reloads, preserving `session-store` (because storage_type='session')
2. Page renders, URL is '/step2'
3. `create_range_sliders` callback fires (triggered by URL)
   - Should read `feature_ranges` from persisted `session-store`
   - Creates sliders with saved values
   - Console: `[DEBUG] Restoring feature ranges from session: {...}`

## Testing Steps

### Test 1: Navigation Between Pages
1. Start the app
2. Go to Step 1, select a site
3. Go to Step 2
4. Adjust some feature range sliders (e.g., set Built Area to 200-400 m²)
5. Check console output: Should see `[DEBUG] Saving feature ranges to session: {...}`
6. Go to Step 3 (click Next)
7. Go back to Step 2 (click Previous)
8. **EXPECTED:** Sliders should show 200-400 m² (the values you set)
9. Check console output: Should see `[DEBUG] Restoring feature ranges from session: {...}`

### Test 2: Page Reload (F5)
1. After completing Test 1, while on Step 2
2. Press F5 to reload the page
3. Navigate to Step 2
4. **EXPECTED:** Sliders should still show 200-400 m² 
5. Check console output: Should see `[DEBUG] Restoring feature ranges from session: {...}`

### Test 3: Different Browser Tab (Same Session)
1. After completing Test 1
2. Open the same URL in a new tab (Ctrl+Click)
3. Navigate to Step 2
4. **EXPECTED:** Sliders should show default values (different browser tab = different session)

### Test 4: Project Save/Load
1. Complete Test 1
2. Click "Save Project"
3. Click "New Project" (clears session)
4. Go to Step 2
5. **EXPECTED:** Sliders show default values
6. Click "Load Project" and select the saved file
7. Navigate to Step 2
8. **EXPECTED:** Sliders show 200-400 m² (restored from project file)

## Potential Issues

### Issue 1: Sliders Still Reset
**Symptom:** Console shows "No saved feature ranges found in session_data"

**Possible Causes:**
1. The `update_session_with_features_and_ranges` callback is not firing
2. The session-store is being cleared somewhere
3. There's a race condition where sliders are created before session data is loaded

**Solution:** Check the console output carefully. If you see "Saving" but not "Restoring", the issue is with the restoration logic.

### Issue 2: Console Shows Correct Values But Sliders Wrong
**Symptom:** Console shows "Restoring feature ranges from session: {'0': [200, 400]}" but sliders show [0, 1000]

**Possible Causes:**
1. The saved values are in wrong format
2. Another callback is overwriting the slider values
3. The `apply_preset` callback is interfering

**Solution:** Check if `apply_preset` is firing unintentionally. It should only fire when preset dropdown changes.

### Issue 3: Only Works After Second Visit
**Symptom:** First visit to Step 2 shows defaults, but going away and coming back shows correct values

**Possible Causes:**
1. Session data is not available on first render
2. The `create_range_sliders` callback fires before `session-store` is populated

**Solution:** This might require adding an initial loading state or ensuring session-store is populated before page navigation.

## Additional Debugging

If issues persist, add more logging:

```python
# In create_range_sliders callback, add:
print(f"[DEBUG] ctx.triggered_id: {ctx.triggered_id}")
print(f"[DEBUG] selected_indices: {selected_indices}")
print(f"[DEBUG] session_data keys: {session_data.keys() if session_data else 'None'}")
print(f"[DEBUG] saved_ranges keys: {saved_ranges.keys() if saved_ranges else 'None'}")

# For each slider created:
print(f"[DEBUG] Creating slider for feature {index}: value={slider_value}, from saved={user_range is not None}")
```

This will help identify exactly where in the flow things go wrong.
