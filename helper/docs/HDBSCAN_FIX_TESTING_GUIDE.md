# Testing Guide: HDBSCAN Cluster Fix

## Quick Test

### Prerequisites
- OpenSKIZZE application running
- Optimization results available from Step 3

### Test Steps

#### 1. Navigate to Step 4 (Compare & Cluster)
```
→ Go to Step 4 in the application
```

#### 2. Select HDBSCAN Algorithm
```
→ Choose "HDBSCAN" from algorithm selector
→ Note: It uses min_cluster_size=5 automatically
```

#### 3. Run Clustering
```
→ Click "Run Analysis" button
→ Wait for clusters to appear
→ Note the cluster IDs displayed (e.g., Cluster 0, Cluster 1, Cluster 2...)
```

#### 4. Select Some Clusters
```
→ Check the boxes for 2-3 clusters
→ Example: Select Cluster 0, Cluster 1
→ "Compare Selected Clusters" button should appear
```

#### 5. Navigate to Step 5
```
→ Click "Compare Selected Clusters" button OR click "Next Step"
→ You should be taken to Step 5 (Detailed Comparison)
```

#### 6. Verify Fix
```
✓ EXPECTED: 3D visualizations of selected clusters appear
✓ EXPECTED: No error message about "IDs not found"
✓ EXPECTED: Cluster information matches Step 4
```

### ❌ OLD BEHAVIOR (Before Fix)
```
Error message:
"Fehler: Die ausgewählten Entwurfs-IDs wurden in der aktuellen 
Ergebnisdatei nicht gefunden..."
```

### ✅ NEW BEHAVIOR (After Fix)
```
- 3D visualizations load correctly
- Selected clusters are displayed
- No error messages
```

## Detailed Test Cases

### Test Case 1: HDBSCAN Basic Workflow

**Steps:**
1. Step 4 → Select HDBSCAN
2. Click "Run Analysis"
3. Select Cluster 0 and Cluster 1
4. Click "Compare Selected Clusters"
5. Step 5 should open with both clusters

**Expected Result:**
- ✓ Both clusters displayed in 3D
- ✓ Can switch between "Best" and "Central" solutions
- ✓ Feature values shown correctly

**If this fails:**
- Check browser console (F12) for JavaScript errors
- Check terminal for Python errors
- Verify clustering-params-store is populated

---

### Test Case 2: K-Medoids Workflow (Verify No Regression)

**Steps:**
1. Step 4 → Select K-Medoids
2. Set K=8 using slider
3. Click "Run Analysis"
4. Select 2-3 clusters
5. Go to Step 5

**Expected Result:**
- ✓ Works exactly as before
- ✓ No errors

---

### Test Case 3: Feature Filters + HDBSCAN

**Steps:**
1. Step 4 → Select HDBSCAN
2. Adjust feature filter sliders (e.g., "Number of Buildings" = 5-15)
3. Click "Run Analysis"
4. Select a cluster
5. Go to Step 5

**Expected Result:**
- ✓ Cluster displayed correctly
- ✓ Same filtering applied in Step 5

---

### Test Case 4: Multiple Cluster Selection

**Steps:**
1. Step 4 → Select HDBSCAN
2. Click "Run Analysis"
3. Select 4-5 clusters
4. Go to Step 5

**Expected Result:**
- ✓ All selected clusters displayed side-by-side
- ✓ Can compare multiple clusters simultaneously

---

### Test Case 5: Back and Forth Navigation

**Steps:**
1. Step 4 → Select HDBSCAN → Run → Select clusters
2. Go to Step 5
3. Go back to Step 4
4. Change selection (select different clusters)
5. Go to Step 5 again

**Expected Result:**
- ✓ New selection displayed correctly
- ✓ No stale data from previous selection

---

## Debugging

### If Error Still Occurs

**Check 1: Browser Console (F12)**
```javascript
// Look for clustering-params-store
// Should contain:
{
  algorithm: "hdbscan",
  params: {min_cluster_size: 5},
  feature_filters: {...}
}
```

**Check 2: Terminal/Server Logs**
```python
# Should see:
[fetch_buildings] Using measuredHeight from LOD2 tiles...
# NOT:
Error: The selected design IDs were not found...
```

**Check 3: Verify Clustering Params Are Saved**
```python
# In Step 4 callback, verify return statement:
return cluster_cards, clustering_params  # Must return BOTH
```

**Check 4: Verify Clustering Params Are Used**
```python
# In Step 5 callback, verify:
if clustering_params:
    algorithm = clustering_params.get('algorithm', 'kmedoids')
    # Should use SAME algorithm as Step 4
```

---

## Common Issues

### Issue 1: "Store not found" error
**Cause:** clustering-params-store not initialized
**Fix:** Verify `dcc.Store(id='clustering-params-store')` exists in step4_compare.py layout

### Issue 2: Still getting "IDs not found" error
**Cause:** Clustering params not being saved or loaded
**Fix:** Check both callbacks updated correctly (Step 4 saves, Step 5 loads)

### Issue 3: Different clusters shown in Step 5 vs Step 4
**Cause:** Clustering params not matching exactly
**Fix:** Verify feature_filters are also stored and applied

---

## Expected Performance

- **Step 4 clustering:** 1-3 seconds (depends on number of solutions)
- **Step 5 re-clustering:** 1-3 seconds (same as Step 4, since same operation)
- **3D visualization:** <1 second per cluster
- **Total time:** Should be fast and seamless

---

## Success Criteria

✅ **Primary Goal:** No more "design IDs not found" error when using HDBSCAN
✅ **Secondary Goal:** Works with all clustering algorithms (HDBSCAN, K-Medoids)
✅ **Tertiary Goal:** Feature filters preserved across steps
✅ **Bonus:** Backward compatibility with old sessions

---

## Manual Verification Checklist

After testing, verify:

- [ ] HDBSCAN clustering in Step 4 works
- [ ] Can select multiple clusters
- [ ] Step 5 displays selected clusters correctly
- [ ] No error messages about missing IDs
- [ ] 3D visualizations render properly
- [ ] Can switch between "Best" and "Central" solutions
- [ ] Feature values displayed correctly
- [ ] K-Medoids still works (no regression)
- [ ] Feature filters are preserved
- [ ] Back/forward navigation works smoothly

---

## Rollback Plan

If the fix causes issues:

1. Revert changes to `pages/step4_compare.py`:
   - Remove `clustering-params-store` from layout
   - Remove second output from callback
   - Change return to just `cluster_cards`

2. Revert changes to `pages/step5_compare_detail.py`:
   - Remove `clustering-params-store` input
   - Revert to hardcoded `'kmedoids', {'n_clusters': 10}, {}`

3. Restart application

---

## Additional Notes

- The fix uses **session storage**, so clustering params persist only within the current browser session
- If user opens application in new tab, they'll need to re-run clustering
- Clustering params are lightweight (<1 KB), no performance impact
- The fallback to K-Medoids k=10 ensures old sessions continue working

---

**Status:** Ready for testing
**Expected outcome:** ✅ HDBSCAN cluster selection bug fixed
