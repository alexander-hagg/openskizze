# HDBSCAN Cluster Selection Fix

## Date: 2024-10-09

## Problem

When using HDBSCAN clustering in Step 4, selecting clusters, and then going to Step 5 for 3D visualization, the following error occurred:

```
Fehler: Die ausgewählten Entwurfs-IDs wurden in der aktuellen Ergebnisdatei nicht gefunden. 
Dies kann passieren, wenn nach der Auswahl eine neue Optimierung gestartet wurde. 
Bitte gehen Sie zu Schritt 5 zurück und treffen Sie eine neue Auswahl.
```

**Translation**: "Error: The selected design IDs were not found in the current results file. This can happen if a new optimization was started after selection. Please return to Step 5 and make a new selection."

## Root Cause

The issue was a **clustering algorithm mismatch** between Step 4 and Step 5:

### Step 4 (Cluster Selection)
- User selects clustering algorithm: **HDBSCAN** (or K-Medoids)
- User configures parameters: e.g., `min_cluster_size=5` for HDBSCAN
- Clustering is performed with these settings
- Cluster IDs are generated: 0, 1, 2, 3... (based on HDBSCAN's density-based grouping)
- User selects clusters by their IDs (e.g., clusters 0, 1, 3)

### Step 5 (3D Visualization) - BEFORE FIX
- **Hardcoded clustering**: Always used **K-Medoids with k=10**
- This creates completely different clusters!
- Cluster IDs from Step 4 don't match cluster IDs in Step 5
- Result: Selected cluster IDs not found → Error message

### Example of the Problem

**Step 4 (HDBSCAN):**
```
Cluster 0: 150 solutions (dense urban designs)
Cluster 1: 200 solutions (low-rise designs)
Cluster 2: 75 solutions (mixed-use designs)
Cluster 3: 50 solutions (green space emphasis)
```

**Step 5 (K-Medoids, k=10) - OLD BEHAVIOR:**
```
Cluster 0: 100 solutions (random group 1)
Cluster 1: 80 solutions (random group 2)
...
Cluster 9: 60 solutions (random group 10)
```

→ Cluster IDs don't correspond! Cluster 0 in HDBSCAN ≠ Cluster 0 in K-Medoids

## Solution

Created a **clustering parameters store** that preserves the exact clustering configuration from Step 4 and uses it in Step 5.

### Changes Made

#### 1. **pages/step4_compare.py**

**Added clustering parameters store:**
```python
def layout(lang='DE'):
    return dbc.Container([
        # Store for clustering parameters (algorithm, params, feature_filters)
        dcc.Store(id='clustering-params-store', storage_type='session'),
        ...
```

**Updated clustering callback to save parameters:**
```python
@callback(
    Output('cluster-results-container', 'children'),
    Output('clustering-params-store', 'data'),  # NEW: Save clustering params
    Input('run-analysis-btn', 'n_clicks'),
    ...
)
def run_and_display_analysis(...):
    ...
    # Store clustering parameters for Step 5 to use the SAME clustering
    clustering_params = {
        'algorithm': algorithm,        # 'hdbscan' or 'kmedoids'
        'params': params,             # {'min_cluster_size': 5} or {'n_clusters': k}
        'feature_filters': feature_filters  # User's filter slider values
    }
    ...
    return cluster_cards, clustering_params
```

#### 2. **pages/step5_compare_detail.py**

**Updated visualization callback to use stored clustering parameters:**
```python
@callback(
    Output('comparison-content', 'children'),
    Input('comparison-store', 'data'),
    Input('results-store', 'data'),
    Input('solution-mode-store', 'data'),
    Input('clustering-params-store', 'data'),  # NEW: Get clustering params from Step 4
    State('language-store', 'data'),
    State('camera-sync-store', 'data')
)
def display_comparison(selected_ids, results_data, solution_modes, clustering_params, lang, camera_state):
    ...
    # Use the SAME clustering algorithm and parameters from Step 4
    # Fall back to k-medoids with k=10 if clustering params not available (old sessions)
    if clustering_params:
        algorithm = clustering_params.get('algorithm', 'kmedoids')
        params = clustering_params.get('params', {'n_clusters': 10})
        feature_filters = clustering_params.get('feature_filters', {})
    else:
        algorithm = 'kmedoids'
        params = {'n_clusters': 10}
        feature_filters = {}
    
    clusters = cluster_and_analyze_solutions(results_path, algorithm, params, feature_filters)
```

## How It Works Now

### Step 4: Cluster and Select
1. User selects algorithm: HDBSCAN
2. User configures: `min_cluster_size=5`
3. User applies feature filters (optional)
4. Click "Run Analysis"
5. **Clustering params stored in session:**
   ```json
   {
     "algorithm": "hdbscan",
     "params": {"min_cluster_size": 5},
     "feature_filters": {0: [10, 50], 3: [5, 20]}
   }
   ```
6. Clusters displayed with IDs: 0, 1, 2, 3...
7. User selects clusters: [0, 1, 3]

### Step 5: Visualize Selected Clusters
1. Load selected cluster IDs: [0, 1, 3]
2. **Load clustering params from session**
3. **Re-run SAME clustering**: HDBSCAN with `min_cluster_size=5`
4. **Re-apply SAME feature filters**
5. Find clusters with IDs 0, 1, 3
6. Display their 3D visualizations

→ **Cluster IDs now match perfectly!**

## Benefits

✅ **Consistency**: Step 5 uses the exact same clustering as Step 4
✅ **Flexibility**: Works with any clustering algorithm (HDBSCAN, K-Medoids, DBSCAN)
✅ **Preserves filters**: Feature filter sliders also applied in Step 5
✅ **Backward compatible**: Falls back to K-Medoids k=10 for old sessions
✅ **Session persistence**: Clustering params stored in browser session

## Testing

### Test Case 1: HDBSCAN Workflow
```
1. Step 4: Select HDBSCAN, run analysis
2. Select clusters 0, 1, 2
3. Go to Step 5
4. ✓ All 3 clusters found and displayed
```

### Test Case 2: K-Medoids Workflow
```
1. Step 4: Select K-Medoids with k=5, run analysis
2. Select clusters 1, 3
3. Go to Step 5
4. ✓ Both clusters found and displayed
```

### Test Case 3: With Feature Filters
```
1. Step 4: Select HDBSCAN
2. Set filter: "Number of Buildings" = 5-15
3. Run analysis, select cluster 0
4. Go to Step 5
5. ✓ Cluster 0 found with same filtering applied
```

### Test Case 4: Backward Compatibility
```
1. Use old session (no clustering params stored)
2. Try to view comparison
3. ✓ Falls back to K-Medoids k=10 (old behavior)
```

## Technical Details

### Storage
- **Type**: `dcc.Store` with `storage_type='session'`
- **Location**: Browser session storage
- **Lifetime**: Persists across page navigation within session
- **Size**: Very small (<1 KB)

### Data Structure
```python
{
    'algorithm': str,           # 'hdbscan', 'kmedoids', or 'dbscan'
    'params': dict,            # Algorithm-specific parameters
    'feature_filters': dict    # {feature_index: [min, max], ...}
}
```

### Fallback Behavior
If `clustering-params-store` is empty (old sessions):
- Algorithm: K-Medoids
- Parameters: `{'n_clusters': 10}`
- Feature filters: `{}` (none)

This ensures backward compatibility with existing sessions.

## Files Modified

1. **pages/step4_compare.py**
   - Added `clustering-params-store`
   - Updated `run_and_display_analysis()` callback to save params
   - Returns clustering params along with cluster cards

2. **pages/step5_compare_detail.py**
   - Added `clustering-params-store` as input
   - Updated `display_comparison()` to use stored params
   - Added fallback for backward compatibility

## Related Issues

This fix also resolves potential issues with:
- Different number of clusters between steps
- Feature filter discrepancies
- Algorithm-specific cluster behavior differences

## Future Enhancements

Possible improvements:
1. Display clustering algorithm info in Step 5 UI
2. Allow re-clustering in Step 5 with different params
3. Cache clustering results to avoid re-computation
4. Add clustering consistency check/warning

## Conclusion

✅ **HDBSCAN cluster selection bug is fixed!**

The issue was caused by Step 5 using different clustering parameters than Step 4. By storing and reusing the exact same clustering configuration, cluster IDs now match perfectly across both steps, allowing seamless navigation from cluster selection to 3D visualization.

**User impact**: No more "design IDs not found" errors when using HDBSCAN or changing clustering parameters!
