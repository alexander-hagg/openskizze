import numpy as np
import pandas as pd
from backend.translation import T 
import matplotlib.pyplot as plt
from shapely.geometry import box, mapping
import geopandas as gpd
from sklearn.manifold import TSNE
from sklearn.cluster import DBSCAN
from sklearn_extra.cluster import KMedoids # <-- New Import
from sklearn.metrics import pairwise_distances
import pickle
import os

def heightmap_to_geojson(heightmap_2d: np.ndarray, grid_geojson: dict):
    """
    Converts a 2D numpy heightmap into a GeoJSON FeatureCollection of polygons,
    georeferenced to the provided grid GeoJSON.
    """
    if not grid_geojson or not grid_geojson.get('features'):
        return None

    grid_gdf = gpd.GeoDataFrame.from_features(grid_geojson, crs="EPSG:4326")
    min_lon, min_lat, max_lon, max_lat = grid_gdf.total_bounds
    
    res = heightmap_2d.shape[0]
    lon_step = (max_lon - min_lon) / res
    lat_step = (max_lat - min_lat) / res
    
    features = []
    non_zero_pixels = np.argwhere(heightmap_2d > 0)

    for r, c in non_zero_pixels:
        height = heightmap_2d[r, c]
        pixel_min_lon = min_lon + c * lon_step
        pixel_max_lon = pixel_min_lon + lon_step
        pixel_max_lat = max_lat - r * lat_step 
        pixel_min_lat = pixel_max_lat - lat_step
        
        pixel_poly = box(pixel_min_lon, pixel_min_lat, pixel_max_lon, pixel_max_lat)
        feature = {
            'type': 'Feature',
            'geometry': mapping(pixel_poly),
            'properties': {'height': int(height)}
        }
        features.append(feature)
        
    return {'type': 'FeatureCollection', 'features': features}

def cluster_and_analyze_solutions(results_path, algorithm='dbscan', params=None, feature_filters=None):
    """
    Loads solutions, filters them, and clusters them using the selected algorithm.
    - algorithm: 'dbscan' or 'kmedoids'
    - params: dict of parameters for the chosen algorithm
    """
    if not results_path or not os.path.exists(results_path):
        return []

    with open(results_path, 'rb') as f:
        list_of_elites = pickle.load(f)
    
    # 1. Filtering
    filtered_elites = []
    if feature_filters:
        for elite in list_of_elites:
            is_valid = True
            for feat_idx_str, (min_val, max_val) in feature_filters.items():
                feat_idx = int(feat_idx_str)
                if not (min_val <= elite['measures'][feat_idx] <= max_val):
                    is_valid = False
                    break
            if is_valid:
                filtered_elites.append(elite)
    else:
        filtered_elites = list_of_elites
    
    if not filtered_elites:
        return []

    heightmaps_flat = np.array([elite['heightmap'] for elite in filtered_elites])
    objectives = np.array([elite['objective'] for elite in filtered_elites])
    original_indices_in_filtered_list = np.arange(len(filtered_elites))

    # 2. t-SNE (used by both for consistency in the 2D space)
    if len(filtered_elites) < 2: return [] # t-SNE requires at least 2 samples
    tsne = TSNE(n_components=2, perplexity=min(30, len(filtered_elites) - 1), 
                random_state=42, n_iter=300, init='pca', learning_rate='auto')
    tsne_results = tsne.fit_transform(heightmaps_flat)

    # 3. Clustering
    cluster_labels = None
    central_solution_indices = {} # For K-Medoids, this is pre-calculated

    if algorithm == 'dbscan':
        min_samples = params.get('min_samples', 4)
        if len(filtered_elites) < min_samples: return []
        dbscan = DBSCAN(eps=params.get('eps', 0.5), min_samples=min_samples)
        cluster_labels = dbscan.fit_predict(tsne_results)

    elif algorithm == 'kmedoids':
        n_clusters = params.get('n_clusters', 3)
        if len(filtered_elites) < n_clusters: return []
        kmedoids = KMedoids(n_clusters=n_clusters, random_state=42)
        cluster_labels = kmedoids.fit_predict(tsne_results)
        # Store the medoid indices, which are the most central points
        for i, medoid_idx in enumerate(kmedoids.medoid_indices_):
            central_solution_indices[i] = medoid_idx
    
    unique_labels = set(cluster_labels)
    
    # 4. Analyze each cluster
    analysis_results = []
    for k in unique_labels:
        if k == -1: continue # Skip noise points from DBSCAN
            
        class_member_mask = (cluster_labels == k)
        cluster_indices = original_indices_in_filtered_list[class_member_mask]
        
        cluster_objectives = objectives[cluster_indices]
        best_solution_local_idx = np.argmax(cluster_objectives)
        best_solution_orig_idx = cluster_indices[best_solution_local_idx]
        
        cluster_heightmaps = heightmaps_flat[cluster_indices]

        # For K-Medoids, the central solution is the medoid. For DBSCAN, we calculate it.
        if algorithm == 'kmedoids':
            central_solution_orig_idx = central_solution_indices[k]
        else: # dbscan
            dist_matrix = pairwise_distances(cluster_heightmaps)
            medoid_local_idx = np.argmin(dist_matrix.sum(axis=0))
            central_solution_orig_idx = cluster_indices[medoid_local_idx]

        boolean_heightmaps = cluster_heightmaps > 0
        consensus_map = np.mean(boolean_heightmaps, axis=0)

        analysis_results.append({
            'cluster_id': int(k),
            'size': len(cluster_indices),
            'best_solution': filtered_elites[best_solution_orig_idx],
            'central_solution': filtered_elites[central_solution_orig_idx],
            'consensus_map': consensus_map.tolist()
        })

    analysis_results.sort(key=lambda x: x['size'], reverse=True)
    return analysis_results

def create_parallel_coords_fig(results_archive, measures_map):
    # ... (this function is unchanged) ...
    if not results_archive or not results_archive['objective']:
        return None
    df_data = {'objective': results_archive['objective']}
    df_data.update(results_archive['measures'])
    df = pd.DataFrame(df_data)
    dimensions = ['objective'] + list(results_archive['measures'].keys())
    labels = {'objective': 'Zielfunktion (Kaltluft)'}
    labels.update({key: measures_map[key] for key in results_archive['measures']})
    fig = pd.plotting.parallel_coordinates(df, 'objective', color=plt.cm.viridis)
    return fig

def get_solution_grid(results_archive, x_axis_measure, y_axis_measure, grid_resolution=10):
    # ... (this function is unchanged) ...
    if not all([results_archive, x_axis_measure, y_axis_measure]):
        return np.empty((grid_resolution, grid_resolution), dtype=object)
    x_values = np.array(results_archive['measures'][x_axis_measure])
    y_values = np.array(results_archive['measures'][y_axis_measure])
    objectives = np.array(results_archive['objective'])
    x_bins = np.linspace(x_values.min(), x_values.max(), grid_resolution + 1)
    y_bins = np.linspace(y_values.min(), y_values.max(), grid_resolution + 1)
    x_indices = np.digitize(x_values, x_bins) - 1
    y_indices = np.digitize(y_values, y_bins) - 1
    x_indices = np.clip(x_indices, 0, grid_resolution - 1)
    y_indices = np.clip(y_indices, 0, grid_resolution - 1)
    grid = np.full((grid_resolution, grid_resolution), None, dtype=object)
    for i in range(grid_resolution):
        for j in range(grid_resolution):
            grid[i, j] = {'solutions': [], 'best_solution_idx': -1, 'best_objective': -np.inf}
    for idx in range(len(objectives)):
        ix, iy = x_indices[idx], y_indices[idx]
        grid[iy, ix]['solutions'].append(idx)
        if objectives[idx] > grid[iy, ix]['best_objective']:
            grid[iy, ix]['best_objective'] = objectives[idx]
            grid[iy, ix]['best_solution_idx'] = idx
    return grid

def generate_contest_requirements(results_path: str, labels: list, selected_indices: list):
    # ... (this function is unchanged) ...
    if not results_path or not os.path.exists(results_path):
        return "Keine Daten zur Analyse vorhanden."
    with open(results_path, 'rb') as f:
        list_of_elites = pickle.load(f)
    if not list_of_elites:
        return "Keine Daten zur Analyse vorhanden."
    measure_keys = [f'MEASURE_{i}' for i in selected_indices]
    df_data = { 'objective': [e['objective'] for e in list_of_elites] }
    for i, key in enumerate(measure_keys):
        df_data[key] = [e['measures'][i] for e in list_of_elites]
    df = pd.DataFrame(df_data)
    top_10_percentile = df['objective'].quantile(0.9)
    top_solutions = df[df['objective'] >= top_10_percentile]
    if top_solutions.empty:
        return "Keine ausreichend performanten Lösungen gefunden, um Anforderungen abzuleiten."
    report = [
        "Basierend auf der Analyse von {} Lösungen wurden folgende Anforderungen für hochperformante Entwürfe (Top 10%) im Hinblick auf die Kaltluftförderung abgeleitet:".format(len(df)),
        "\n"
    ]
    all_measures_map = {key: val for key, val in T['DE'].items() if key.startswith('MEASURE_')}
    for measure_key, human_label in zip(measure_keys, labels):
        if measure_key in top_solutions.columns:
            mean_val = top_solutions[measure_key].mean()
            std_val = top_solutions[measure_key].std()
            min_val = top_solutions[measure_key].min()
            max_val = top_solutions[measure_key].max()
            report.append(f"- **{human_label}:** Optimale Ergebnisse wurden im Bereich von {min_val:.2f} bis {max_val:.2f} erzielt (Mittelwert: {mean_val:.2f} ± {std_val:.2f}).")
    return "\n".join(report)