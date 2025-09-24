### Project Structure and Code

The following is a directory tree of the project, including only Python (.py) files.

.
├── ./app.py
├── ./backend
│   ├── ./backend/analysis.py
│   ├── ./backend/config.py
│   ├── ./backend/data_io.py
│   ├── ./backend/debugging_plots.py
│   ├── ./backend/encoding.py
│   ├── ./backend/evaluation.py
│   ├── ./backend/optimization_process.py
│   ├── ./backend/optimizer.py
│   └── ./backend/translation.py
├── ./pages
│   ├── ./pages/step1_scope.py
│   ├── ./pages/step2_constraints.py
│   ├── ./pages/step3_optimize.py
│   ├── ./pages/step4_explore.py
│   └── ./pages/step5_compare.py
└── ./run.py

3 directories, 16 files

---

### Code Content

The following sections contain the content of each Python file. Each section is clearly labeled with the file's path.

#### `./backend/data_io.py`

```python
# backend/data_io.py

import requests
import json
import geopandas
from shapely.geometry import box
import io

# --- Flurstücke (Parcels) Fetching ---
WFS_URL_PARCELS = "https://www.wfs.nrw.de/geobasis/wfs_nw_alkis_vereinfacht"
TYPE_NAME_PARCELS = "ave:Flurstueck"
NATIVE_CRS = "EPSG:25832"
WEB_CRS = "EPSG:4326"

def fetch_flurstuecke_data(bbox: tuple):
    # This function remains unchanged and is correct.
    min_lon, min_lat, max_lon, max_lat = bbox
    try:
        bbox_geom = box(min_lon, min_lat, max_lon, max_lat)
        gdf_bbox = geopandas.GeoDataFrame([1], geometry=[bbox_geom], crs=WEB_CRS)
        gdf_bbox_native = gdf_bbox.to_crs(NATIVE_CRS)
        min_x, min_y, max_x, max_y = gdf_bbox_native.total_bounds
        bbox_str = f"{min_x},{min_y},{max_x},{max_y},{NATIVE_CRS}"
        params = {
            'service': 'WFS', 'version': '1.1.0', 'request': 'GetFeature',
            'typeName': TYPE_NAME_PARCELS, 'outputFormat': 'text/xml; subtype=gml/3.2.1',
            'srsName': NATIVE_CRS, 'BBOX': bbox_str
        }
        response = requests.get(WFS_URL_PARCELS, params=params, timeout=45)
        response.raise_for_status()
        if "ExceptionReport" in response.text: return None
        gml_content = io.BytesIO(response.content)
        gdf_native = geopandas.read_file(gml_content)
        if gdf_native.empty: return {'type': 'FeatureCollection', 'features': []}
        gdf_web = gdf_native.to_crs(WEB_CRS)
        gdf_web['id'] = gdf_web.index.astype(str)
        return json.loads(gdf_web.to_json())
    except Exception as e:
        print(f"An error occurred during Flurstücke fetching: {e}. Returning a fake parcel.")

        # --- FAKE PARCEL GENERATION LOGIC ---
        # Calculate the center and a small size relative to the bbox
        center_lon = (min_lon + max_lon) / 2
        center_lat = (min_lat + max_lat) / 2
        width = max_lon - min_lon
        height = max_lat - min_lat
        
        # Make the fake parcel 10% of the bbox size
        fake_width = width * 0.1
        fake_height = height * 0.1

        # Define the bounds of the fake parcel
        fake_min_lon = center_lon - fake_width / 2
        fake_max_lon = center_lon + fake_width / 2
        fake_min_lat = center_lat - fake_height / 2
        fake_max_lat = center_lat + fake_height / 2

        # Create the geometry for the fake parcel
        fake_geom = box(fake_min_lon, fake_min_lat, fake_max_lon, fake_max_lat)

        # Create a GeoDataFrame in the same structure as a successful call
        fake_gdf = geopandas.GeoDataFrame([1], geometry=[fake_geom], crs=WEB_CRS)
        fake_gdf['id'] = "fake_0" # Assign a unique ID
        
        # Convert to the expected GeoJSON dictionary format and return
        return json.loads(fake_gdf.to_json())

# --- Existing Buildings Fetching (New Function) ---
WFS_URL_BUILDINGS = "https://www.wfs.nrw.de/geobasis/wfs_nw_alkis_vereinfacht"
TYPE_NAME_BUILDINGS = "ave:GebaeudeBauwerk"

def fetch_existing_buildings_data(bbox: tuple):
    """
    Fetches existing building footprints from the NRW WFS API for a given bounding box.
    """
    min_lon, min_lat, max_lon, max_lat = bbox
    try:
        # Transform BBOX to native CRS for the request
        bbox_geom = box(min_lon, min_lat, max_lon, max_lat)
        gdf_bbox = geopandas.GeoDataFrame([1], geometry=[bbox_geom], crs=WEB_CRS)
        gdf_bbox_native = gdf_bbox.to_crs(NATIVE_CRS)
        min_x, min_y, max_x, max_y = gdf_bbox_native.total_bounds
        bbox_str = f"{min_x},{min_y},{max_x},{max_y},{NATIVE_CRS}"
        params = {
            'service': 'WFS', 'version': '1.1.0', 'request': 'GetFeature',
            'typeName': TYPE_NAME_BUILDINGS, 'outputFormat': 'text/xml; subtype=gml/3.2.1',
            'srsName': NATIVE_CRS, 'BBOX': bbox_str
        }
        print("Fetching existing buildings from NRW API...")
        response = requests.get(WFS_URL_BUILDINGS, params=params, timeout=45)
        response.raise_for_status()
        if "ExceptionReport" in response.text: return None
        
        # Convert GML response to a GeoDataFrame in the native CRS
        gml_content = io.BytesIO(response.content)
        gdf_native = geopandas.read_file(gml_content)
        
        print(f"Found {len(gdf_native)} existing buildings.")
        return gdf_native if not gdf_native.empty else None
    except Exception as e:
        print(f"An error occurred during building fetching: {e}")
        return None```

#### `./backend/config.py`

```python
from backend.translation import T

QD_CONFIG = {
    'num_niches': 5,
    'num_generations': 1000,  # Drastically reduced for a fast web demo
    'num_emitters': 5,      # Reduced for a fast web demo
    'sigma': 0.1,
    'learning_rate': 0.01,
    'output_inv_frequency': 100,
    'batch_size': 16,
}

ENCODING_CONFIG = {
    'max_num_buildings': 10,
    'xy_length': 32, # This can be dynamically updated
    'z_length': 3,
}

DOMAIN_CONFIG = {
    'wind_direction': 180,
    'pixel_size_in_meters': 3,
    'features': [0, 1, 2, 3, 4, 5, 6, 7],
    'labels': [T['DE'][f'MEASURE_{i}'] for i in range(8)],
    # 'feat_ranges': [
    #     [0.0, 0.15], [0.0, 9.0], [0.0, 6.0], 
    #     [0.0, 5.0], [0.0, 60.0], [0.0, 0.3], 
    #     [0.0, 60.0], [0.0, 60.0],
    # ],
    'feat_ranges': [
        [0.0, 0.15], [0.0, 3.0], [0.0, 6.0], 
        [0.0, 10.0], [0.0, 1.0], [0.0, 1.0], 
        [0.0, 1.0], [0.0, 1.0],
    ],
    'environment_border_size': 1.2,
}```

#### `./backend/optimizer.py`

```python
# backend/optimizer.py
import numpy as np
from ribs.archives import GridArchive
from ribs.emitters import GaussianEmitter
from ribs.schedulers import Scheduler
import multiprocessing
import psutil
from backend.evaluation import eval_batch

def run_qd_optimization(encoding_obj, env_config: dict, qd_config: dict, progress_callback=None):
    solution_dim = encoding_obj.get_dimension()
    print(f"[DEBUG] Starting QD setup. Solution dimension: {solution_dim}")
    
    archive = GridArchive(
        solution_dim=solution_dim,
        dims=[qd_config['num_niches']] * len(env_config['labels']),
        ranges=env_config['feat_ranges'],
        learning_rate=qd_config['learning_rate'],
        threshold_min=0.0
    )
    
    bounds = np.array([[-5.0, 5.0]] * solution_dim)
    x0 = np.zeros(solution_dim)
    
    emitters = [
        GaussianEmitter(
            archive, x0=x0, sigma=qd_config['sigma'],
            batch_size=qd_config['batch_size'], bounds=bounds
        ) for _ in range(qd_config['num_emitters'])
    ]
    
    scheduler = Scheduler(archive, emitters)
    nb_cpus = max(1, psutil.cpu_count(logical=True) - 2)
    pool = multiprocessing.Pool(processes=nb_cpus)
    
    print("Starting QD Optimization...")
    for gen in range(1, qd_config['num_generations'] + 1):
        try:
            genomes = scheduler.ask()
            if gen == 1: print(f"[DEBUG] Gen 1: Asked for {len(genomes)} genomes. Shape of first genome: {genomes[0].shape}")

            results = eval_batch(genomes, encoding_obj, env_config, pool)
            
            objectives = results[:, 0]
            features = results[:, 1:len(env_config['labels']) + 1]
            
            if gen == 1:
                print(f"[DEBUG] Gen 1: Results received. Objectives shape: {objectives.shape}, Features shape: {features.shape}")

            scheduler.tell(objectives, features)
            
            if gen % qd_config['output_inv_frequency'] == 0:
                stats = archive.stats
                print(f"Gen {gen}/{qd_config['num_generations']} | QD Score: {stats.qd_score:.2f} | Coverage: {stats.coverage * 100:.2f}% | Elites: {stats.num_elites}")
            
            if progress_callback: progress_callback(100*gen/qd_config["num_generations"], f'Es wird {qd_config["num_generations"]} Generationen optimiert.')
        
        except Exception as e:
            print(f"!!!!!! ERROR during optimization loop at generation {gen} !!!!!!")
            print(f"Error: {e}")
            if isinstance(e, MemoryError):
                print("!!!!!! MEMORY ERROR DETECTED. This is likely due to an unstable emitter state. !!!!!!")
            pool.close()
            pool.join()
            raise e
            
    pool.close()
    pool.join()
    print("Finished QD Optimization.")
    return archive```

#### `./backend/optimization_process.py`

```python
#
# backend/optimization_process.py (Final Corrected Version with Shape Filtering and Rasterio)
#
import numpy as np
import geopandas as gpd
from shapely.geometry import Point, Polygon
from backend.config import QD_CONFIG, ENCODING_CONFIG, DOMAIN_CONFIG
from backend.data_io import fetch_existing_buildings_data
from backend.encoding import ParametricEncoding
from backend.optimizer import run_qd_optimization
from backend.debugging_plots import create_debug_plots
import math
from rasterio import features
from rasterio.transform import from_origin
import json


def create_environment(user_polygon_geojson: dict, selected_features: list, user_feature_ranges: dict):

    if not user_polygon_geojson or not user_polygon_geojson.get('features'):
        raise ValueError("User polygon is empty or invalid.")
        
    gdf_user_poly = gpd.GeoDataFrame.from_features(user_polygon_geojson, crs="EPSG:4326")
    gdf_user_poly_native = gdf_user_poly.to_crs("EPSG:25832")
    min_x, min_y, max_x, max_y = gdf_user_poly_native.total_bounds
    
    width = max_x - min_x
    height = max_y - min_y
    square_size = max(width, height)
    center_x = (min_x + max_x) / 2
    center_y = (min_y + max_y) / 2
    square_min_x = center_x - square_size / 2
    square_min_y = center_y - square_size / 2
    border = square_size * (DOMAIN_CONFIG['environment_border_size'] - 1.0) / 2.0
    grid_min_x = square_min_x - border
    grid_min_y = square_min_y - border
    grid_side_length = square_size + (2 * border)
    grid_max_x = grid_min_x + grid_side_length
    grid_max_y = grid_min_y + grid_side_length
    
    pixel_size = DOMAIN_CONFIG['pixel_size_in_meters']
    res = math.ceil(grid_side_length / pixel_size)
    ENCODING_CONFIG['xy_length'] = res
    
    x = np.linspace(grid_min_x, grid_max_x, res)
    y = np.linspace(grid_min_y, grid_max_y, res)
    xv, yv = np.meshgrid(x, y)
    points = [Point(px, py) for px, py in zip(xv.flatten(), yv.flatten())]
    gdf_points = gpd.GeoDataFrame(geometry=points, crs="EPSG:25832")
    
    joined = gpd.sjoin(gdf_points, gdf_user_poly_native, how="inner", predicate="within")
    buildable_mask = np.zeros((res, res), dtype=bool)
    indices = joined.index.to_numpy()
    rows, cols = np.unravel_index(indices, (res, res))
    buildable_mask[rows, cols] = True
    
    env_3d_fixed = np.zeros((res, res, ENCODING_CONFIG['z_length']), dtype=np.int8)
    grid_poly_native = gpd.GeoSeries([Polygon.from_bounds(grid_min_x, grid_min_y, grid_max_x, grid_max_y)], crs="EPSG:25832")
    grid_poly_web = grid_poly_native.to_crs("EPSG:4326")
    b_min_lon, b_min_lat, b_max_lon, b_max_lat = grid_poly_web.total_bounds
    
    gdf_buildings_native = fetch_existing_buildings_data((b_min_lon, b_min_lat, b_max_lon, b_max_lat))
    
    if gdf_buildings_native is not None:
        geom_types = gdf_buildings_native.geometry.type
        polygon_mask = geom_types.isin(['Polygon', 'MultiPolygon'])
        gdf_polygons = gdf_buildings_native[polygon_mask].copy()

        perimeter = gdf_polygons.geometry.length
        area = gdf_polygons.geometry.area
        perimeter[perimeter == 0] = 1e-9
        compactness = 4 * math.pi * area / (perimeter**2)
        compact_mask = compactness > 0.1
        gdf_building_polygons = gdf_polygons[compact_mask]
        
        if not gdf_building_polygons.empty:
            cell_size = grid_side_length / res
            transform = from_origin(grid_min_x, grid_max_y, cell_size, cell_size)
            
            building_footprints_2d = features.rasterize(
                shapes=gdf_building_polygons.geometry, out_shape=(res, res), transform=transform,
                fill=0, default_value=1, dtype='uint8'
            ).astype(bool)
            building_footprints_2d = np.flipud(building_footprints_2d)
            
            env_3d_fixed[building_footprints_2d, :3] = 1

    env_3d_fixed[buildable_mask, :] = 0
    
    # --- THE FIX IS HERE ---
    # Use the user-defined ranges to construct the final list of ranges for the optimizer.
    final_labels = [DOMAIN_CONFIG['labels'][i] for i in selected_features]
    # if the user_feature_ranges dict is empty
    if not user_feature_ranges:
        dynamic_ranges, buildable_area_m2 = _calculate_dynamic_feat_ranges(
        buildable_mask)
        final_feat_ranges = [dynamic_ranges[i] for i in selected_features]
    else:
        final_feat_ranges = [user_feature_ranges[str(i)] for i in selected_features]

    grid_geojson = json.loads(grid_poly_web.to_json())

    return {
        'buildable_mask': buildable_mask, 
        'env_3d_fixed': env_3d_fixed,
        'labels': final_labels,
        'feat_ranges': final_feat_ranges, # This now contains the user's ranges
        'buildable_area_in_sq_meters': 0, # Placeholder, calculation removed for brevity
        'selected_features': selected_features,
        'grid_geojson': grid_geojson,
    }


def _calculate_dynamic_feat_ranges(buildable_mask: np.ndarray) -> (list, float):
    pixel_size = DOMAIN_CONFIG['pixel_size_in_meters']
    z_len = ENCODING_CONFIG['z_length']
    buildable_pixels = np.sum(buildable_mask)
    if buildable_pixels == 0:
        return DOMAIN_CONFIG['feat_ranges'], 0.0
    buildable_area_sq_meters = buildable_pixels * (pixel_size ** 2)
    grid_res = buildable_mask.shape[0]
    new_ranges = [
        [0.0, 1.0], [0.0, z_len], [0.0, z_len / 2],
        [0.0, ENCODING_CONFIG['max_num_buildings']],
        [0.0, 1.0], [0.0, 1.0], [0.0, 1.0], [0.0, 1.0],
    ]
    return new_ranges, buildable_area_sq_meters


def start_optimization(user_polygon_geojson: dict, wind_direction: int, selected_features: list, user_feature_ranges: dict, progress_callback=None):
    progress_callback(5, "Creating environment...")
    env_config = create_environment(user_polygon_geojson, selected_features, user_feature_ranges)
    env_config['wind_direction'] = wind_direction
    encoding_obj = ParametricEncoding(ENCODING_CONFIG)
    sample_genome = np.random.randn(encoding_obj.get_dimension())
    create_debug_plots(env_config, sample_genome, encoding_obj)
    progress_callback(10, "Starting optimization...")
    archive = run_qd_optimization(
        encoding_obj, env_config, QD_CONFIG, progress_callback)
    progress_callback(100, "Optimization complete.")
    return archive, env_config['labels'], env_config
```

#### `./backend/debugging_plots.py`

```python
#
# backend/debugging_plots.py (Final Corrected Version - Flips for Visualization Only)
#
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
import os
from backend.config import ENCODING_CONFIG

def create_debug_plots(env_config: dict, sample_genome: np.ndarray, encoding_obj):
    print("[DEBUG] Creating debug plots...")
    output_dir = "debug_plots"
    os.makedirs(output_dir, exist_ok=True)
    
    buildable_mask = env_config['buildable_mask']
    env_3d_fixed = env_config['env_3d_fixed']
    sample_design_2d = encoding_obj.express(buildable_mask, sample_genome)
    
    zone_map = np.ones_like(buildable_mask, dtype=int)
    zone_map[~buildable_mask] = 2
    zone_map[buildable_mask] = 3
    
    design_3d = np.zeros_like(env_3d_fixed)
    for r in range(sample_design_2d.shape[0]):
        for c in range(sample_design_2d.shape[1]):
            h = int(sample_design_2d[r, c])
            if h > 0: design_3d[r, c, :h] = 1
    combined_env_3d = np.maximum(env_3d_fixed, design_3d)

    # --- THE CRITICAL FIX IS HERE ---
    # Flip all 2D arrays vertically *just before plotting* to match the map's orientation.
    # The actual data used in the optimization remains in the original NumPy orientation.
    cmap = ListedColormap(['#FFC300', '#C70039', '#FFFFFF'])

    plt.figure(figsize=(8, 8))
    plt.imshow(zone_map, cmap=cmap, origin='lower', vmin=1, vmax=3)
    plt.title("1. Buildable Area (White), Taboo (Red), Buffer (Orange)")
    plt.savefig(os.path.join(output_dir, "1_buildable_area_mask.png"))
    plt.close()

    existing_buildings_2d = (np.sum(env_3d_fixed, axis=2) > 0).astype(int)
    plt.figure(figsize=(8, 8))
    plt.imshow(zone_map, cmap=cmap, origin='lower', vmin=1, vmax=3)
    plt.imshow(np.ma.masked_where(existing_buildings_2d == 0, existing_buildings_2d), 
               cmap='Greys', origin='lower', alpha=0.7)
    plt.title("2. Existing Buildings in Context")
    plt.savefig(os.path.join(output_dir, "2_existing_buildings.png"))
    plt.close()

    plt.figure(figsize=(8, 8))
    plt.imshow(sample_design_2d, cmap='viridis', origin='lower', vmin=0, vmax=ENCODING_CONFIG['z_length'])
    plt.title("3. Sample Generated Design (Encoding Check)")
    plt.savefig(os.path.join(output_dir, "3_sample_generated_design.png"))
    plt.close()
    
    combined_env_2d = (np.sum(combined_env_3d, axis=2))
    plt.figure(figsize=(8, 8))
    plt.imshow(combined_env_2d, cmap='cividis', origin='lower')
    plt.title("4. Combined Scene for Porosity Calculation")
    plt.savefig(os.path.join(output_dir, "4_combined_for_fitness.png"))
    plt.close()

    plt.figure(figsize=(8, 8))
    plt.imshow(sample_design_2d, cmap='viridis', origin='lower', vmin=0, vmax=ENCODING_CONFIG['z_length'])
    plt.title("5. Area for Feature Calculation (Generated Design Only)")
    plt.savefig(os.path.join(output_dir, "5_feature_calculation_area.png"))
    plt.close()
    
    print(f"[DEBUG] Debug plots saved to '{output_dir}' directory.")```

#### `./backend/analysis.py`

```python
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
    return "\n".join(report)```

#### `./backend/evaluation.py`

```python
#
# backend/evaluation.py (Final Corrected Version)
#
import numpy as np
from scipy.ndimage import label, center_of_mass, rotate
import multiprocessing
from backend.config import DOMAIN_CONFIG, ENCODING_CONFIG

def compute_fitness(heightmap_3d: np.ndarray, wind_direction: int) -> float:
    rotation_angle = (wind_direction + 90) % 360
    rotated_env = rotate(heightmap_3d, angle=rotation_angle, axes=(0, 1), reshape=False, order=0)
    projection = np.sum(rotated_env, axis=1)
    open_columns = np.sum(projection == 0)
    total_columns = projection.shape[0] * projection.shape[1]
    porosity = open_columns / total_columns if total_columns > 0 else 0.0
    return np.clip(porosity, 0.0, 1.0)

def calculate_all_features(heightmap: np.ndarray, buildable_mask: np.ndarray, buildable_area_in_sq_meters: float) -> np.ndarray:
    grid_res_y, grid_res_x = heightmap.shape
    occupied = heightmap > 0
    buildable_pixels = np.sum(buildable_mask)
    
    building_coverage = np.sum(occupied) / buildable_pixels if buildable_pixels > 0 else 0.0
    
    building_heights = heightmap[occupied]
    if not building_heights.any():
        return np.zeros(len(DOMAIN_CONFIG['labels']))
        
    avg_height = np.mean(building_heights)
    height_variability = np.std(building_heights)
    _, num_buildings = label(occupied)
    
    if num_buildings > 1:
        centroids = np.array(center_of_mass(occupied, label(occupied)[0], range(1, num_buildings + 1)))
        diff = centroids[:, None, :] - centroids[None, :, :]
        dists = np.sqrt(np.sum(diff**2, axis=-1))
        avg_spacing_pixels = np.mean(dists[np.triu_indices(num_buildings, k=1)])
        max_dist = np.sqrt(grid_res_x**2 + grid_res_y**2)
        avg_spacing = avg_spacing_pixels / max_dist if max_dist > 0 else 0.0
    else: avg_spacing = 0.0
    
    pixel_area = DOMAIN_CONFIG['pixel_size_in_meters'] ** 2
    total_floor_area_sq_meters = np.sum(heightmap) * pixel_area
    floor_space_ratio = total_floor_area_sq_meters / buildable_area_in_sq_meters if buildable_area_in_sq_meters > 0 else 0.0
    
    center_y_px, center_x_px = center_of_mass(heightmap)
    center_x = center_x_px / grid_res_x if grid_res_x > 0 else 0.0
    center_y = center_y_px / grid_res_y if grid_res_y > 0 else 0.0

    return np.array([
        building_coverage, avg_height, height_variability, num_buildings,
        avg_spacing, floor_space_ratio, center_x, center_y
    ])

def eval_solution(genome: np.ndarray, encoding_obj, env_config: dict) -> np.ndarray:
    heightmap_2d_solution = encoding_obj.express(env_config['buildable_mask'], genome)
    
    # design_3d = np.zeros_like(env_config['env_3d_fixed'])
    # for r in range(heightmap_2d_solution.shape[0]):
    #     for c in range(heightmap_2d_solution.shape[1]):
    #         h = int(heightmap_2d_solution[r, c])
    #         if h > 0: design_3d[r, c, :h] = 1

    # --- OPTIMIZED 3D MESH GENERATION ---
    # Create an array of z-axis indices: [0, 1, 2, ..., max_height-1]
    max_height = env_config['env_3d_fixed'].shape[2]
    z_indices = np.arange(max_height)

    # Use NumPy broadcasting to compare the height at each (r, c) with the z_indices.
    # This creates a 3D boolean mask directly, which is 100-1000x faster than a loop.
    # We cast to a smaller integer type like int8 to save memory.
    design_3d = (z_indices < heightmap_2d_solution.astype(int)[:, :, np.newaxis]).astype(np.int8)
    
            
    combined_env_3d = np.maximum(env_config['env_3d_fixed'], design_3d)
    fitness = compute_fitness(combined_env_3d, env_config['wind_direction'])

    # Calculate buildable area in square meters from buildable mask
    buildable_area_in_sq_meters = np.sum(env_config['buildable_mask']) * (DOMAIN_CONFIG['pixel_size_in_meters'] ** 2)

    # --- DYNAMIC FEATURE SELECTION ---
    # 1. Calculate all 8 possible features.
    all_features = calculate_all_features(
        heightmap_2d_solution,
        env_config['buildable_mask'],
        buildable_area_in_sq_meters
    )
    # 2. Filter the features based on the indices provided in the env_config.
    selected_features = all_features[env_config['selected_features']]
    
    return np.concatenate(([fitness], selected_features, heightmap_2d_solution.flatten()))

def eval_batch(genomes: list, encoding_obj, env_config: dict, pool) -> np.ndarray:
    # results = [eval_solution(g, encoding_obj, env_config) for g in genomes]
    results = pool.starmap(eval_solution, [(g, encoding_obj, env_config) for g in genomes])

    return np.array(results)```

#### `./backend/encoding.py`

```python
# backend/encoding.py
import numpy as np
import numpy.typing as npt
from scipy.stats import norm, uniform

def norm2unif(x):
    p = norm.cdf(x, 0, 1)
    return uniform.ppf(p, 0, 1)

class ParametricEncoding:
    def __init__(self, config: dict):
        self.config = config

    def get_dimension(self) -> int:
        return self.config['max_num_buildings'] * 6

    def express(self, buildable_mask: npt.NDArray, genome: npt.NDArray) -> npt.NDArray:
        # --- THE PERFORMANCE OPTIMIZATION IS HERE ---

        # 1. Reshape the flat genome into a matrix where each row is a building's genes.
        #    Also convert all gene values from a normal to a uniform distribution at once.
        genes = norm2unif(genome).reshape(self.config['max_num_buildings'], -1)
        
        # 2. Vectorized Calculation: Calculate properties for ALL buildings simultaneously.
        #    Instead of looping, we operate on entire columns (e.g., genes[:, 0] is the
        #    width gene for all buildings). This is executed by NumPy's fast C code.
        
        # Check which buildings are active using the 6th gene.
        is_active = genes[:, 5] > 0.0
        if not np.any(is_active):
            return np.zeros_like(buildable_mask)

        # Filter to only active buildings before calculating properties
        active_genes = genes[is_active]

        w = (active_genes[:, 0] * (self.config['xy_length'] / 2)).astype(int)
        l = (active_genes[:, 1] * (self.config['xy_length'] / 2)).astype(int)
        h = (active_genes[:, 2] * self.config['z_length']).astype(int) + 1
        x_c = (active_genes[:, 3] * self.config['xy_length']).astype(int)
        y_c = (active_genes[:, 4] * self.config['xy_length']).astype(int)
        
        # Calculate start/end coordinates for all buildings, clipping to bounds
        x_start = np.clip(x_c - w // 2, 0, self.config['xy_length'])
        x_end = np.clip(x_c + w // 2, 0, self.config['xy_length'])
        y_start = np.clip(y_c - l // 2, 0, self.config['xy_length'])
        y_end = np.clip(y_c + l // 2, 0, self.config['xy_length'])
        
        # 3. Efficient Drawing: Now that all calculations are done, create the heightmap.
        #    This loop is now much faster because it only performs simple assignments.
        #    Building overlaps are handled correctly (last building drawn wins).
        heightmap = np.zeros((self.config['xy_length'], self.config['xy_length']))
        for i in range(len(active_genes)):
            heightmap[y_start[i]:y_end[i], x_start[i]:x_end[i]] = h[i]
        
        # 4. Final Masking: This is a fast, element-wise operation.
        masked_heightmap = heightmap * buildable_mask
        
        if masked_heightmap.shape != (self.config['xy_length'], self.config['xy_length']):
            print(f"  [DEBUG-ERROR] Heightmap shape is {masked_heightmap.shape}, expected {(self.config['xy_length'], self.config['xy_length'])}")
        
        return masked_heightmap```

#### `./backend/translation.py`

```python
# backend/translation.py (Final Corrected Version)

T = {
    'DE': {
        'APP_TITLE': "OpenSKIZZE - Interaktiver Städtebau Explorer",
        'NEXT_STEP': "Nächster Schritt",
        'PREV_STEP': "Vorheriger Schritt",

        # Step 1
        'STEP1_TITLE': "Schritt 1: Geltungsbereich und klimatische Parameter festlegen",
        'STEP1_WIND_HEADER': "Klimatische Parameter",
        'STEP1_WIND_SLIDER_LABEL': "Windrichtung (TODO: importieren von Klimamodell)",
        'STEP1_DATA_SOURCE_INFO': "Kartengrundlage: OpenStreetMap. Zukünftig: Anbindung an Geodatenportal NRW.",

        # Step 2
        'STEP2_TITLE': "Schritt 2: Leistungsmerkmale und Optimierungsziele festlegen",
        'STEP2_OBJECTIVES_HEADER': "Leistungsmerkmale",
        'STEP2_MEASURES_LABEL': "Wählen Sie die Merkmale zur Generierung diverser Lösungen:",
        'STEP2_OBJECTIVE_INFO_LABEL': "Zielfunktion Optimierung",
        'STEP2_OBJECTIVE_INFO_TEXT': "Optimierung der Kaltluft-Porosität, basierend auf der in Schritt 1 gewählten Windrichtung.",
        
        'MEASURE_0': 'Bebaute Fläche',
        'MEASURE_1': 'Durchschnittliche Bauhöhe',
        'MEASURE_2': 'Variabilität Bauhöhe',
        'MEASURE_3': 'Anzahl der Gebäude',
        'MEASURE_4': 'Durchschnittliche Gebäudedistanz',
        'MEASURE_5': 'Brutto-Grundfläche',
        'MEASURE_6': 'Gebäudemasse X-Achse',
        'MEASURE_7': 'Gebäudemasse Y-Achse',

        # Step 3
        'STEP3_TITLE': "Schritt 3: Entwurfsvarianten generieren",
        'STEP3_START_BUTTON': "Optimierung starten",
        'STEP3_RESULTS_HEADER': "Ergebnis der Optimierung",

        # Step 4
        'STEP4_TITLE': "Schritt 4: Lösungsraum analysieren",
        'STEP4_X_AXIS_LABEL': "X-Achse auswählen:",
        'STEP4_Y_AXIS_LABEL': "Y-Achse auswählen:",
        'STEP4_GRID_HEADER': "Lösungsarchiv (Bester Entwurf pro Nische)",
        
        # Step 5
        'STEP5_TITLE': "Schritt 5: Varianten vergleichen und Anforderungen exportieren",
        'STEP5_EXPORT_BUTTON': "Planungsanforderungen für Wettbewerb exportieren",
        'STEP5_EXPORT_FILENAME': "planungsanforderungen.txt",
        'STEP5_FILTER_HEADER': "Designs filtern und analysieren",
        'STEP5_ANALYSIS_HEADER': "Analyse der Entwurfstypen (Cluster)",
        'STEP5_RUN_BUTTON': "Analyse starten / neu filtern",
        'STEP5_CLUSTER_CARD_TITLE': "Cluster {id} - Entwurfstyp (Größe: {size})",
        'STEP5_CLUSTER_CARD_TEXT': "Dieser Entwurfstyp ist robust, da er in {size} Varianten gefunden wurde.",
        'STEP5_BEST_SOLUTION_HEADER': "Beste Lösung (Höchste Porosität)",
        'STEP5_CENTRAL_SOLUTION_HEADER': "Zentralste Lösung (Repräsentativste)",
        'STEP5_CONSENSUS_MAP_HEADER': "Konsens-Karte (Bebauungswahrscheinlichkeit)",
        'STEP5_NO_CLUSTERS_FOUND': "Keine Cluster gefunden. Versuchen Sie, die Filter oder die Clustering-Parameter anzupassen.",
        'STEP5_NO_SELECTION': "Zum Starten bitte auf 'Analyse starten' klicken.",
        'STEP5_SELECT_LABEL': "Wählen Sie Designs aus der Analyse unten aus, um sie im Detail zu vergleichen (Zukünftige Funktion).",
        'STEP5_ALGORITHM_LABEL': "Clustering-Algorithmus:",
        'STEP5_KMEDOIDS_K_LABEL': "Anzahl der Cluster (k):"
    }
}
# Add English translations if needed
T['EN'] = T['DE']```

#### `./pages/step2_constraints.py`

```python
#
# pages/step2_constraints.py
#
from dash import dcc, html, Input, Output, State, callback, no_update, ALL
import dash_bootstrap_components as dbc
from backend.translation import T
from backend.config import DOMAIN_CONFIG
import numpy as np

LANG = 'DE'

MEASURES_OPTIONS = [{'label': label, 'value': i} for i, label in enumerate(DOMAIN_CONFIG['labels'])]

def layout():
    return dbc.Container([
        html.H2(T[LANG]['STEP2_TITLE']),
        dbc.Row([
            dbc.Col(dbc.Button(T[LANG]['PREV_STEP'], href='/', color="secondary")),
            dbc.Col(dbc.Button(T[LANG]['NEXT_STEP'], href='/step3', color="primary"), className="text-end")
        ], className="mt-4"),

        dbc.Row([
            dbc.Col([
                html.H5(T[LANG]['STEP2_OBJECTIVES_HEADER']),
                dbc.Label(T[LANG]['STEP2_MEASURES_LABEL']),
                dbc.Card(dbc.Checklist(
                    options=MEASURES_OPTIONS,
                    value=DOMAIN_CONFIG['features'], # Default features
                    id='measures-checklist',
                    switch=True,
                ), body=True),
            ], md=6),
            dbc.Col([
                html.H5(T[LANG]['STEP2_OBJECTIVE_INFO_LABEL']),
                dbc.Alert(T[LANG]['STEP2_OBJECTIVE_INFO_TEXT'], color="info"),
                
                # --- NEW: Container for the dynamic range sliders ---
                # html.H5("Zielbereiche für Merkmale festlegen"),
                # html.P("Definieren Sie die Wertebereiche, in denen der Optimierer nach diversen Lösungen suchen soll.", className="text-muted small"),
                # dcc.Loading(html.Div(id='feature-range-sliders-container'))

            ], md=6),
        ])
    ], fluid=True)

# --- NEW: Callback to dynamically generate the sliders based on the checklist ---
@callback(
    Output('feature-range-sliders-container', 'children'),
    Input('measures-checklist', 'value'),
    prevent_initial_call=True
)
def create_range_sliders(selected_indices):
    if not selected_indices:
        return dbc.Alert("Bitte mindestens ein Merkmal auswählen.", color="info")

    sliders = []
    num_buildings_original_index = 3 # The original index for 'Anzahl der Gebäude'

    for index in sorted(selected_indices):
        label = DOMAIN_CONFIG['labels'][index]
        default_range = DOMAIN_CONFIG['feat_ranges'][index]
        min_val, max_val = default_range[0], default_range[1]
        
        slider_div = None
        if index == num_buildings_original_index:
            min_v = int(np.floor(min_val))
            max_v = int(np.ceil(max_val))
            if min_v == max_v: max_v += 1
            slider_div = html.Div([
                dbc.Label(label),
                dcc.RangeSlider(
                    id={'type': 'feature-range-slider', 'index': index},
                    min=min_v, max=max_v, step=1, value=[min_v, max_v],
                    tooltip={"placement": "bottom", "always_visible": True}, marks=None
                )
            ], className="mb-3")
        else:
            min_v = round(min_val, 2)
            max_v = round(max_val, 2)
            if min_v == max_v: max_v += 0.01
            slider_div = html.Div([
                dbc.Label(label),
                dcc.RangeSlider(
                    id={'type': 'feature-range-slider', 'index': index},
                    min=min_v, max=max_v, step=0.01, value=[min_v, max_v],
                    tooltip={"placement": "bottom", "always_visible": True}, marks=None
                )
            ], className="mb-3")
        
        sliders.append(slider_div)
        
    return sliders

# --- UPDATED: Callback to save both selections and ranges to the session ---
@callback(
    Output('session-store', 'data', allow_duplicate=True),
    Input('measures-checklist', 'value'),
    Input({'type': 'feature-range-slider', 'index': ALL}, 'value'),
    State({'type': 'feature-range-slider', 'index': ALL}, 'id'),
    State('session-store', 'data'),
    prevent_initial_call=True
)
def update_session_with_features_and_ranges(
    selected_indices, slider_values, slider_ids, session_data
):
    session_data = session_data or {}
    
    # Save the list of selected feature indices
    session_data['selected_features'] = selected_indices
    
    # Create and save the dictionary of user-defined ranges
    feature_ranges = {
        str(s_id['index']): s_val for s_id, s_val in zip(slider_ids, slider_values)
    }
    session_data['feature_ranges'] = feature_ranges
    
    print(f"[INFO] User selected features: {selected_indices}")
    print(f"[INFO] User-defined ranges: {feature_ranges}")
    
    return session_data```

#### `./pages/step4_explore.py`

```python
#
# pages/step4_explore.py
#
from dash import dcc, html, Input, Output, State, callback, clientside_callback, MATCH, ALL, no_update
import dash_bootstrap_components as dbc
from backend.translation import T
from backend.config import ENCODING_CONFIG
from backend.analysis import heightmap_to_geojson
import numpy as np
import pickle
import os
import dash_leaflet as dl
from dash_extensions.javascript import assign

LANG = 'DE'

# JS for styling the building polygons based on height using chroma.js
style_handle = assign("""
function(feature, context){
    const { z_length } = context.hideout;
    const height = feature.properties.height;
    const colorscale = chroma.scale('viridis').domain([0, z_length]);
    return {
        fillColor: colorscale(height),
        color: '#333',
        weight: 1,
        opacity: 1,
        fillOpacity: 0.8
    };
}
""")

def layout():
    return dbc.Container([
        html.H2(T[LANG]['STEP4_TITLE']),
        dbc.Row([
            dbc.Col(dbc.Button(T[LANG]['PREV_STEP'], href='/step3', color="secondary")),
            dbc.Col(dbc.Button(T[LANG]['NEXT_STEP'], href='/step5', color="primary"), className="text-end")
        ], className="mt-4"),

        dbc.Card(dbc.CardBody([
            dbc.Row([
                dbc.Col(dbc.Label(T[LANG]['STEP4_X_AXIS_LABEL'])),
                dbc.Col(dcc.Dropdown(id='x-axis-dropdown-s4')),
            ]),
            dbc.Row([
                dbc.Col(dbc.Label(T[LANG]['STEP4_Y_AXIS_LABEL'])),
                dbc.Col(dcc.Dropdown(id='y-axis-dropdown-s4')),
            ])
        ])),
        html.Hr(),
        html.H4(T[LANG]['STEP4_GRID_HEADER']),
        dcc.Loading(html.Div(id='solution-map-grid-container'))
    ], fluid=True)

@callback(
    Output('x-axis-dropdown-s4', 'options'),
    Output('y-axis-dropdown-s4', 'options'),
    Output('x-axis-dropdown-s4', 'value'),
    Output('y-axis-dropdown-s4', 'value'),
    Input('results-store', 'data'),
)
def populate_dropdowns_s4(results_data):
    if not results_data or 'labels' not in results_data:
        return [], [], None, None
    
    options = [{'label': label, 'value': i} for i, label in enumerate(results_data['labels'])]
    val1 = 0 if len(options) > 0 else None
    val2 = 1 if len(options) > 1 else None
    return options, options, val1, val2

@callback(
    Output('solution-map-grid-container', 'children'),
    Input('x-axis-dropdown-s4', 'value'),
    Input('y-axis-dropdown-s4', 'value'),
    State('results-store', 'data'),
)
def update_solution_map_grid(x_axis_idx, y_axis_idx, results_data):
    if not all([isinstance(x_axis_idx, int), isinstance(y_axis_idx, int), results_data]):
        return dbc.Alert("Optimierungsergebnisse nicht gefunden oder Achsen nicht gewählt.", color="warning")

    results_path = results_data.get('full_results_path')
    grid_geojson = results_data.get('grid_geojson')
    if not results_path or not os.path.exists(results_path) or not grid_geojson:
        return dbc.Alert("Fehler: Große Ergebnisdatei oder Georeferenzierung nicht gefunden.", color="danger")

    with open(results_path, 'rb') as f:
        list_of_elites = pickle.load(f)

    grid_dims = results_data['archive_dims']
    grid_resolution_x = grid_dims[x_axis_idx]
    grid_resolution_y = grid_dims[y_axis_idx]
    
    vis_grid = np.full((grid_resolution_y, grid_resolution_x), None, dtype=object)
    
    for elite_dict in list_of_elites:
        ix = elite_dict['grid_indices'][x_axis_idx]
        iy = elite_dict['grid_indices'][y_axis_idx]
        if vis_grid[iy, ix] is None or elite_dict['objective'] > vis_grid[iy, ix]['objective']:
            vis_grid[iy, ix] = elite_dict
    
    grid_children = []
    heightmap_res = results_data['xy_length']
    
    lons = [c[0] for f in grid_geojson['features'] for c in f['geometry']['coordinates'][0]]
    lats = [c[1] for f in grid_geojson['features'] for c in f['geometry']['coordinates'][0]]
    map_center = [(min(lats) + max(lats)) / 2, (min(lons) + max(lons)) / 2]

    for row in range(grid_resolution_y):
        row_children = []
        for col in range(grid_resolution_x):
            elite_data = vis_grid[row, col]
            map_id = {'type': 'solution-map', 'index': f'{row}-{col}'}
            
            if elite_data is not None:
                heightmap = np.array(elite_data['heightmap']).reshape((heightmap_res, heightmap_res))
                design_geojson = heightmap_to_geojson(np.flipud(heightmap), grid_geojson)
                
                map_component = dl.Map(
                    center=map_center, zoom=14,
                    children=[
                        dl.TileLayer(url="https://{s}.basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}{r}.png",
                                     attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'),
                        dl.GeoJSON(data=design_geojson, id=f'geojson-{row}-{col}', 
                                   options=dict(style=style_handle), 
                                   hideout={'z_length': ENCODING_CONFIG['z_length']})
                    ], 
                    style={'width': '100%', 'height': '150px', 'min-height': '150px'},
                    id=map_id
                )
                col_child = dbc.Col(map_component)
            else:
                placeholder = html.Div(
                    dbc.Alert("Kein Entwurf", color="light", className="h-100 d-flex align-items-center justify-content-center m-0"),
                    style={'height': '150px', 'border': '1px solid #dee2e6'}
                )
                col_child = dbc.Col(placeholder)
            row_children.append(col_child)
        grid_children.append(dbc.Row(row_children, className="g-1 mb-1"))

    return grid_children

clientside_callback(
    """
    function(view, map_ids) {
        const triggered_id_str = dash_clientside.callback_context.triggered.map(t => t.prop_id).join(',');
        if (!triggered_id_str || !view) {
            return dash_clientside.no_update;
        }
        const updated_views = map_ids.map(id => view);
        return updated_views;
    }
    """,
    Output({'type': 'solution-map', 'index': ALL}, 'view'),
    Input({'type': 'solution-map', 'index': ALL}, 'view'),
    State({'type': 'solution-map', 'index': ALL}, 'id'),
    prevent_initial_call=True
)```

#### `./pages/step5_compare.py`

```python
from dash import dcc, html, Input, Output, State, callback, no_update, ALL
import dash_bootstrap_components as dbc
from backend.translation import T
from backend.analysis import generate_contest_requirements, cluster_and_analyze_solutions, heightmap_to_geojson
from backend.config import ENCODING_CONFIG
import pickle
import os
import numpy as np
import dash_leaflet as dl
from dash_extensions.javascript import assign
import plotly.express as px

LANG = 'DE'

style_handle = assign("""
function(feature, context){
    const { z_length } = context.hideout;
    const height = feature.properties.height;
    const colorscale = chroma.scale('viridis').domain([0, z_length]);
    return {
        fillColor: colorscale(height),
        color: '#333',
        weight: 1,
        opacity: 1,
        fillOpacity: 0.8
    };
}
""")

def layout():
    return dbc.Container([
        html.H2(T[LANG]['STEP5_TITLE']),
        dbc.Row([
            dbc.Col(dbc.Button(T[LANG]['PREV_STEP'], href='/step4', color="secondary")),
        ], className="mt-4"),

        
        dbc.Card(dbc.CardBody([
            html.H4(T[LANG]['STEP5_FILTER_HEADER']),
            html.P("Filtern Sie die Lösungen nach ihren Merkmalen und passen Sie die Clustering-Parameter an, um Entwurfstypen zu identifizieren.", className="text-muted"),
            html.Div(id='feature-filter-controls'),
            
            dbc.Label(T[LANG]['STEP5_ALGORITHM_LABEL']),
            dbc.RadioItems(
                id='algorithm-selector',
                options=[
                    {'label': 'DBSCAN (Dichte-basiert)', 'value': 'dbscan'},
                    {'label': 'K-Medoids (Partionierend)', 'value': 'kmedoids'},
                ],
                value='dbscan',
                inline=True,
                className="mb-3"
            ),
            
            html.Div(id='dbscan-params-div', children=[
                dbc.Row([
                    dbc.Col(dbc.Label("DBSCAN eps (Nachbarschaftsradius):"), width='auto'),
                    dbc.Col(dcc.Slider(id='dbscan-eps-slider', min=0.1, max=5, step=0.1, value=0.1, marks=None, tooltip={"placement": "bottom", "always_visible": True})),
                ], className="align-items-center mt-2"),
                dbc.Row([
                     dbc.Col(dbc.Label("DBSCAN min_samples (Min. Clustergröße):"), width='auto'),
                     dbc.Col(dcc.Slider(id='dbscan-minsamples-slider', min=2, max=20, step=1, value=4, marks=None, tooltip={"placement": "bottom", "always_visible": True})),
                ], className="align-items-center mt-2"),
            ]),

            html.Div(id='kmedoids-params-div', style={'display': 'none'}, children=[
                dbc.Row([
                    dbc.Col(dbc.Label(T[LANG]['STEP5_KMEDOIDS_K_LABEL']), width='auto'),
                    dbc.Col(dcc.Slider(id='kmedoids-k-slider', min=2, max=50, step=1, value=30, marks=None, tooltip={"placement": "bottom", "always_visible": True})),
                ], className="align-items-center mt-2"),
            ]),

            dbc.Button(T[LANG]['STEP5_RUN_BUTTON'], id="run-analysis-btn", color="primary", className="mt-3")
        ])),
        
        html.Hr(),
        
        html.H4(T[LANG]['STEP5_ANALYSIS_HEADER']),
        dcc.Loading(html.Div(id='cluster-results-container', children=[
             dbc.Alert(T[LANG]['STEP5_NO_SELECTION'], color="light")
        ])),
        
        dbc.Button(T[LANG]['STEP5_EXPORT_BUTTON'], id="export-reqs-btn-s5", color="info", className="mt-3"),
        dcc.Download(id="download-requirements-s5")
        
    ], fluid=True)


@callback(
    Output('dbscan-params-div', 'style'),
    Output('kmedoids-params-div', 'style'),
    Input('algorithm-selector', 'value')
)
def toggle_parameter_sliders(selected_algorithm):
    if selected_algorithm == 'dbscan':
        return {'display': 'block'}, {'display': 'none'}
    elif selected_algorithm == 'kmedoids':
        return {'display': 'none'}, {'display': 'block'}
    return {'display': 'none'}, {'display': 'none'}

@callback(
    Output('feature-filter-controls', 'children'),
    Input('results-store', 'data')
)
def create_filter_controls(results_data):
    if not results_data or not results_data.get('full_results_path'):
        return dbc.Alert("Bitte zuerst in Schritt 3 eine Optimierung durchführen.", color="warning")

    results_path = results_data.get('full_results_path')
    if not os.path.exists(results_path): return no_update
    
    with open(results_path, 'rb') as f:
        list_of_elites = pickle.load(f)
    
    labels = results_data.get('labels', [])
    selected_feature_indices = results_data.get('selected_features_indices', [])
    if not labels: return no_update
    
    measures_data = np.array([elite['measures'] for elite in list_of_elites])
    
    sliders = []
    # This is the original index from the config, not the index in the 'labels' list
    num_buildings_original_index = 3

    for i, label in enumerate(labels):
        # The actual index of the feature we are currently processing
        current_feature_original_index = selected_feature_indices[i]
        
        min_val, max_val = measures_data[:, i].min(), measures_data[:, i].max()
        
        # --- THE FIX IS HERE ---
        # Handle the "Number of Buildings" slider to be integer-only
        if current_feature_original_index == num_buildings_original_index:
            min_v = int(np.floor(min_val))
            max_v = int(np.ceil(max_val))
            if min_v == max_v: max_v += 1
            
            slider_div = html.Div([
                dbc.Label(label),
                dcc.RangeSlider(
                    id={'type': 'filter-slider', 'index': i},
                    min=min_v,
                    max=max_v,
                    step=1,  # Enforce integer steps
                    value=[min_v, max_v],
                    tooltip={"placement": "bottom", "always_visible": True},
                    marks=None,
                )
            ], className="mb-2")
        
        # Handle all other sliders to have two decimal places
        else:
            min_v = round(min_val, 2)
            max_v = round(max_val, 2)
            if min_v == max_v: max_v += 0.01

            slider_div = html.Div([
                dbc.Label(label),
                dcc.RangeSlider(
                    id={'type': 'filter-slider', 'index': i},
                    min=min_v,
                    max=max_v,
                    step=0.01,  # Enforce 2 decimal places
                    value=[min_v, max_v],
                    tooltip={"placement": "bottom", "always_visible": True},
                    marks=None,
                )
            ], className="mb-2")
        # --- END OF FIX ---
        sliders.append(slider_div)
        
    return sliders

@callback(
    Output('cluster-results-container', 'children'),
    Input('run-analysis-btn', 'n_clicks'),
    State('results-store', 'data'),
    State({'type': 'filter-slider', 'index': ALL}, 'value'),
    State({'type': 'filter-slider', 'index': ALL}, 'id'),
    State('algorithm-selector', 'value'),
    State('dbscan-eps-slider', 'value'),
    State('dbscan-minsamples-slider', 'value'),
    State('kmedoids-k-slider', 'value'),
    prevent_initial_call=True
)
def run_and_display_analysis(n_clicks, results_data, slider_values, slider_ids, 
                             algorithm, eps, min_samples, k):
    if not n_clicks: return no_update

    results_path = results_data.get('full_results_path')
    grid_geojson = results_data.get('grid_geojson')
    if not results_path or not grid_geojson:
        return dbc.Alert("Ergebnisdatei oder Georeferenzierung nicht gefunden.", color="danger")
        
    feature_filters = {s_id['index']: s_val for s_id, s_val in zip(slider_ids, slider_values)}

    params = {}
    if algorithm == 'dbscan':
        params = {'eps': eps, 'min_samples': min_samples}
    elif algorithm == 'kmedoids':
        params = {'n_clusters': k}

    clusters = cluster_and_analyze_solutions(results_path, algorithm, params, feature_filters)

    if not clusters:
        return dbc.Alert(T[LANG]['STEP5_NO_CLUSTERS_FOUND'], color="warning")

    lons = [c[0] for f in grid_geojson['features'] for c in f['geometry']['coordinates'][0]]
    lats = [c[1] for f in grid_geojson['features'] for c in f['geometry']['coordinates'][0]]
    map_center = [(min(lats) + max(lats)) / 2, (min(lons) + max(lons)) / 2]
    heightmap_res = results_data['xy_length']

    cluster_cards = []
    for cluster in clusters:
        best_hm = np.array(cluster['best_solution']['heightmap']).reshape(heightmap_res, heightmap_res)
        best_geojson = heightmap_to_geojson(np.flipud(best_hm), grid_geojson)
        best_map = dl.Map(center=map_center, zoom=14, children=[
            dl.TileLayer(url="https://{s}.basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}{r}.png"),
            dl.GeoJSON(data=best_geojson, options=dict(style=style_handle), hideout={'z_length': ENCODING_CONFIG['z_length']})
        ], style={'height': '200px', 'width': '100%'})
        
        central_hm = np.array(cluster['central_solution']['heightmap']).reshape(heightmap_res, heightmap_res)
        central_geojson = heightmap_to_geojson(np.flipud(central_hm), grid_geojson)
        central_map = dl.Map(center=map_center, zoom=14, children=[
            dl.TileLayer(url="https://{s}.basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}{r}.png"),
            dl.GeoJSON(data=central_geojson, options=dict(style=style_handle), hideout={'z_length': ENCODING_CONFIG['z_length']})
        ], style={'height': '200px', 'width': '100%'})

        consensus_map_data = np.array(cluster['consensus_map']).reshape(heightmap_res, heightmap_res)
        consensus_fig = px.imshow(consensus_map_data, color_continuous_scale='Blues', origin='lower', zmin=0, zmax=1)
        consensus_fig.update_layout(margin=dict(l=0, r=0, t=0, b=0), coloraxis_showscale=False)
        consensus_fig.update_xaxes(showticklabels=False).update_yaxes(showticklabels=False)
        consensus_graph = dcc.Graph(figure=consensus_fig, style={'height': '200px', 'width': '100%'})
        
        card = dbc.Card(dbc.CardBody([
            html.H5(T[LANG]['STEP5_CLUSTER_CARD_TITLE'].format(id=cluster['cluster_id'], size=cluster['size'])),
            html.P(T[LANG]['STEP5_CLUSTER_CARD_TEXT'].format(size=cluster['size']), className="text-muted small"),
            dbc.Row([
                dbc.Col([html.H6(T[LANG]['STEP5_BEST_SOLUTION_HEADER']), best_map], md=4),
                dbc.Col([html.H6(T[LANG]['STEP5_CENTRAL_SOLUTION_HEADER']), central_map], md=4),
                dbc.Col([html.H6(T[LANG]['STEP5_CONSENSUS_MAP_HEADER']), consensus_graph], md=4)
            ])
        ]), className="mb-3")
        cluster_cards.append(card)
        
    return cluster_cards

@callback(
    Output("download-requirements-s5", "data"),
    Input("export-reqs-btn-s5", "n_clicks"),
    State("results-store", "data"),
    prevent_initial_call=True,
)
def export_requirements_s5(n_clicks, results_data):
    if not n_clicks or not results_data:
        return None
    results_path = results_data.get('full_results_path')
    labels = results_data.get('labels')
    selected_indices = results_data.get('selected_features_indices')
    if not all([results_path, labels, selected_indices is not None]):
         return dict(content="Error: Could not find all necessary data for export.", filename="error.txt")
    report_text = generate_contest_requirements(results_path, labels, selected_indices)
    return dict(content=report_text, filename=T[LANG]['STEP5_EXPORT_FILENAME'])```

#### `./pages/step3_optimize.py`

```python
#
# pages/step3_optimize.py
#
from dash import dcc, html, Input, Output, State, callback
import dash_bootstrap_components as dbc
from backend.translation import T
from backend.optimization_process import start_optimization
import plotly.express as px
import pandas as pd
from dash import DiskcacheManager
import diskcache
import pickle
import uuid
import os
# --- New imports for the fix ---
from backend.encoding import ParametricEncoding
from backend.config import ENCODING_CONFIG

import cProfile # Import the profiler
import pstats   # Import for saving stats

cache = diskcache.Cache("./cache")
background_callback_manager = DiskcacheManager(cache)
LANG = 'DE'

TEMP_RESULTS_DIR = "temp_results"
os.makedirs(TEMP_RESULTS_DIR, exist_ok=True)

def layout():
    return dbc.Container([
        html.H2(T[LANG]['STEP3_TITLE']),
        dbc.Row([
            dbc.Col(dbc.Button(T[LANG]['PREV_STEP'], href='/step2', color="secondary")),
            dbc.Col(dbc.Button(T[LANG]['NEXT_STEP'], href='/step4', color="primary"), className="text-end")
        ], className="mt-4"),

        dbc.Button(T[LANG]['STEP3_START_BUTTON'], id='start-optimization-btn', color="success", size="lg", className="mb-3"),
        html.Div(id="progress-container", children=[
            dbc.Progress(id="progress-bar", label="0%", style={'height': '30px'}),
            html.Div(id="progress-text", className="text-center text-muted small mt-1")
        ], style={'visibility': 'hidden'}),
        html.Hr(),
        html.H4(T[LANG]['STEP3_RESULTS_HEADER']),
        dcc.Loading(id="loading-results", children=html.Div(id='results-output-div'))
    ], fluid=True)

@callback(
    Output('results-store', 'data'),
    Output('results-output-div', 'children'),
    Input('start-optimization-btn', 'n_clicks'),
    State('session-store', 'data'),
    background=True,
    manager=background_callback_manager,
    prevent_initial_call=True,
    progress=[
        Output("progress-bar", "value"),
        Output("progress-bar", "label"),
        Output("progress-text", "children"),
        Output("progress-container", "style")
    ],
)
def run_optimization(set_progress, n_clicks, session_data):
    if not n_clicks or not session_data or not session_data.get('site_polygon'):
        return None, dbc.Alert("Bitte definieren Sie einen Geltungsbereich in Schritt 1.", color="warning")

    selected_features = session_data.get('selected_features', list(range(8)))
    user_feature_ranges = session_data.get('feature_ranges', {})


    def progress_callback(progress, text):
        set_progress((progress, f"{progress}%", text, {'visibility': 'visible'}))

    try:
        # profiler = cProfile.Profile()
        # profiler.enable()
    
        archive, labels, env_config = start_optimization(
            session_data['site_polygon'],
            session_data['wind_direction'],
            selected_features,
            user_feature_ranges,
            progress_callback=progress_callback
        )
        
        if archive and not archive.empty:
            # 1. Instantiate an encoder object to regenerate heightmaps from the genomes.
            encoding_obj = ParametricEncoding(ENCODING_CONFIG)
            
            # 2. Retrieve all necessary data from the archive, including the compact
            #    'solution' (genome) instead of the non-existent 'heightmaps'.
            objectives = archive.data('objective')
            measures = archive.data('measures')
            solutions = archive.data('solution') # The compact genomes
            
            grid_indices = archive.index_of(measures)
            grid_indices = archive.int_to_grid_index(grid_indices)
            
            full_list_of_elites = []
            for i in range(len(objectives)):
                # 3. For each elite solution, regenerate its full heightmap. This is fast
                #    and memory-efficient as it's done only for the final best solutions.
                genome = solutions[i]
                heightmap = encoding_obj.express(env_config['buildable_mask'], genome)

                full_list_of_elites.append({
                    "objective": objectives[i],
                    "measures": measures[i].tolist(),
                    "grid_indices": grid_indices[i].tolist(),
                    "heightmap": heightmap.flatten().tolist() # Store the regenerated map
                })

            session_id = str(uuid.uuid4())
            full_results_path = os.path.join(TEMP_RESULTS_DIR, f"{session_id}.pkl")
            with open(full_results_path, 'wb') as f:
                pickle.dump(full_list_of_elites, f)

            results_summary_to_store = {
                'full_results_path': full_results_path,
                'archive_dims': archive.dims,
                'labels': labels,
                'grid_geojson': env_config['grid_geojson'],
                'xy_length': ENCODING_CONFIG['xy_length'],
                'selected_features_indices': selected_features,
            }

            df_for_plot = pd.DataFrame(full_list_of_elites)
            measures_df = pd.DataFrame(df_for_plot['measures'].tolist(), columns=labels)
            df_for_plot = pd.concat([df_for_plot['objective'], measures_df], axis=1).copy()
            
            fig = px.parallel_coordinates(
                df_for_plot, dimensions=['objective'] + labels, color="objective",
                labels={dim: dim.replace(" ", "<br>") for dim in ['objective'] + labels},
                title="Erkundung des Lösungsraums"
            )
            graph = dcc.Graph(figure=fig)

            # profiler.disable()
            # stats = pstats.Stats(profiler).sort_stats('cumtime')
            # stats.dump_stats('optimization_profile.prof') # Save the results to a file
            

            return results_summary_to_store, graph
        
    except Exception as e:
        import traceback
        print("!!!!!! OPTIMIZATION FAILED in UI callback !!!!!!")
        traceback.print_exc()
        return None, dbc.Alert(f"Optimierung fehlgeschlagen: {e}", color="danger")
    
    return None, dbc.Alert("Optimierung fehlgeschlagen oder es wurden keine Lösungen gefunden.", color="warning")```

#### `./pages/step1_scope.py`

```python
#
# pages/step1_scope.py
#
import dash
from dash import dcc, html, Input, Output, State, callback, no_update, clientside_callback
import dash_bootstrap_components as dbc
import dash_leaflet as dl
from dash_extensions.javascript import assign
from backend.translation import T
from backend.data_io import fetch_flurstuecke_data
from shapely.geometry import shape, mapping, Polygon, MultiPolygon
from shapely.ops import unary_union
import math

LANG = 'DE'

# Client-side styling for the selectable parcel layer
style_handle = assign("""
function(feature, context){
    const { selected } = context.hideout;
    if (selected.includes(feature.properties.id)) {
        return {color: '#ff7800', weight: 3, opacity: 1, fillOpacity: 0.5}; // Orange for selected
    } else {
        return {color: '#3388ff', weight: 2, opacity: 1, fillOpacity: 0.1}; // Blue for available
    }
}
""")

def create_compass_component():
    """Creates the HTML structure for the interactive compass."""
    return html.Div(id='compass-container', className='compass-container', children=[
        html.Div(className='compass-rose', children=[
            html.Span('N', className='compass-label compass-label-n'),
            html.Span('E', className='compass-label compass-label-e'),
            html.Span('S', className='compass-label compass-label-s'),
            html.Span('W', className='compass-label compass-label-w'),
        ]),
        html.Div(id='compass-needle-container', className='compass-needle-container', children=[
            html.Div(className='compass-needle', id='compass-needle')
        ]),
        html.Div(className='compass-pivot')
    ])

def layout():
    return dbc.Container([
        html.H2(T[LANG]['STEP1_TITLE']),
        dbc.Button(T[LANG]['NEXT_STEP'], id='next-step1-btn', href='/step2', color="primary", className="mt-4"),
        html.P(T[LANG]['STEP1_DATA_SOURCE_INFO'], className="text-muted mb-3"),
        dcc.Store(id='loaded-parcels-store'),
        dcc.Store(id='selected-parcels-store', data=[]),
        dcc.Store(id='active-polygon-store'),

        dbc.Row([
            dbc.Col([
                dl.Map(
                    center=[50.734965, 7.055020], zoom=13,
                    children=[
                        dl.TileLayer(),
                        dl.GeoJSON(id='parcels-layer', options=dict(style=style_handle), hideout=dict(selected=[]), hoverStyle={'fillOpacity': 0.5, 'weight': 3}),
                        dl.GeoJSON(id='active-polygon-layer', options=dict(style={'color': 'green', 'fillOpacity': 0.6, 'weight': 3})),
                        dl.FeatureGroup([
                            dl.EditControl(id='edit-control', draw={
                                'polygon': True, 'rectangle': True, 'circle': False,
                                'marker': False, 'circlemarker': False, 'polyline': False
                            }, edit={'edit': False, 'remove': True})
                        ]),
                    ], id='map-step1', style={'width': '100%', 'height': '60vh'}
                )
            ], md=7),
            
            dbc.Col([
                html.Div([
                    html.H5("Werkzeuge"),
                    dbc.Label("1. Flurstücke von OpenData Portal NRW laden und auswählen/abwählen", className="fw-bold"),
                    dbc.Button("Flurstücke für aktuellen Kartenausschnitt laden", id="load-parcels-btn", className="w-100 mb-3"),
                    
                    dbc.Label("2. Manuelle Anpassung von Flurstücken", className="fw-bold"),
                    dbc.RadioItems(
                        options=[
                            {'label': 'Fläche hinzufügen', 'value': 'add'},
                            {'label': 'Fläche entfernen', 'value': 'subtract'},
                        ],
                        value='add', id='edit-mode-toggle', inline=True,
                    ),
                    html.P("Nutzen Sie die Werkzeuge links auf der Karte, um die grüne Auswahl anzupassen.", className="small fst-italic"),
                ]),
                html.Hr(),
                html.H5(T[LANG]['STEP1_WIND_HEADER']),
                html.Div(T[LANG]['STEP1_WIND_SLIDER_LABEL'], className="text-center"),
                
                # --- NEW COMPASS COMPONENT ---
                create_compass_component(),

                # --- SLIDER IS NOW THE CONTROLLER, DRIVEN BY THE COMPASS ---
                dcc.Slider(id='wind-direction-slider', min=0, max=360, step=1, value=180, marks={0: 'N', 90: 'E', 180: 'S', 270: 'W'}),
            ], md=5)
        ])
        
    ], fluid=True)


# --- INTERACTIVE COMPASS CLIENTSIDE CALLBACKS ---

clientside_callback(
    """
    function(slider_value) {
        // This callback syncs the slider's value TO the compass needle's rotation.
        const needle = document.getElementById('compass-needle');
        if (needle) {
            needle.style.transform = `rotate(${slider_value}deg)`;
        }
        return window.dash_clientside.no_update;
    }
    """,
    Output('compass-needle-container', 'data-dummy-output'), # Dummy output
    Input('wind-direction-slider', 'value')
)

clientside_callback(
    """
    function(_, slider_id) {
        // This callback handles the drag logic FOR the compass, updating the slider.
        const container = document.getElementById('compass-container');
        if (!container) return;

        let isDragging = false;

        const updateAngle = (e) => {
            e.preventDefault();
            const rect = container.getBoundingClientRect();
            const centerX = rect.left + rect.width / 2;
            const centerY = rect.top + rect.height / 2;

            const clientX = e.touches ? e.touches[0].clientX : e.clientX;
            const clientY = e.touches ? e.touches[0].clientY : e.clientY;

            const deltaX = clientX - centerX;
            const deltaY = clientY - centerY;

            // Calculate angle in degrees. Add 90 because 0 degrees in atan2 is East.
            let angle = Math.atan2(deltaY, deltaX) * (180 / Math.PI) + 90;
            if (angle < 0) {
                angle += 360; // Normalize to 0-360
            }
            
            // Find the slider and update its value.
            // This is a bit of a hack to communicate with Dash components.
            const slider = document.getElementById(slider_id);
            if(slider){
                // We need to find the hidden input element that holds the value
                const input = slider.querySelector('input[type="hidden"]');
                if(input){
                    const nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
                    nativeInputValueSetter.call(input, Math.round(angle));
                    const event = new Event('input', { bubbles: true });
                    input.dispatchEvent(event);
                }
            }
        };

        const startDrag = (e) => {
            isDragging = true;
            updateAngle(e);
        };

        const doDrag = (e) => {
            if (isDragging) {
                updateAngle(e);
            }
        };

        const stopDrag = () => {
            isDragging = false;
        };
        
        // Attach event listeners
        container.addEventListener('mousedown', startDrag);
        document.addEventListener('mousemove', doDrag);
        document.addEventListener('mouseup', stopDrag);
        container.addEventListener('touchstart', startDrag, { passive: false });
        document.addEventListener('touchmove', doDrag, { passive: false });
        document.addEventListener('touchend', stopDrag);
        
        return window.dash_clientside.no_update;
    }
    """,
    Output('compass-container', 'data-dummy-output'),
    Input('compass-container', 'n_clicks'),
    State('wind-direction-slider', 'id')
)

# Callbacks for loading and displaying the blue selectable parcel layer
@callback(Output('loaded-parcels-store', 'data'), Input('load-parcels-btn', 'n_clicks'), State('map-step1', 'bounds'), prevent_initial_call=True)
def load_parcels_data(n_clicks, bounds):
    if not n_clicks or not bounds: return no_update
    bbox = (bounds[0][1], bounds[0][0], bounds[1][1], bounds[1][0])
    return fetch_flurstuecke_data(bbox)

@callback(Output('parcels-layer', 'data'), Input('loaded-parcels-store', 'data'))
def display_parcels(geojson_data):
    return geojson_data

# The single, authoritative callback that manages the active green polygon.
@callback(
    Output('session-store', 'data'),
    Output('active-polygon-layer', 'data'),
    Output('selected-parcels-store', 'data'),
    Output('parcels-layer', 'hideout'),
    Input('parcels-layer', 'clickData'),
    Input('edit-control', 'geojson'),
    Input('wind-direction-slider', 'value'),
    State('selected-parcels-store', 'data'),
    State('loaded-parcels-store', 'data'),
    State('session-store', 'data'),
    State('edit-mode-toggle', 'value'),
    prevent_initial_call=True
)
def handle_all_interactions(click_data, drawn_geojson, wind_direction, selected_ids, 
                            all_parcels_data, session_data, edit_mode):
    session_data = session_data or {}
    ctx = dash.callback_context
    triggered_id = ctx.triggered_id

    last_active_geojson = session_data.get('site_polygon')
    base_geom = shape(last_active_geojson['features'][0]['geometry']) if last_active_geojson and last_active_geojson.get('features') else Polygon()

    new_selected_ids = selected_ids
    hideout = {'selected': selected_ids}
    final_geom = base_geom

    if triggered_id == 'parcels-layer':
        if click_data is None: return no_update
        
        parcel_id = click_data['properties']['id']
        new_selected_ids = selected_ids[:]
        if parcel_id in new_selected_ids:
            new_selected_ids.remove(parcel_id)
        else:
            new_selected_ids.append(parcel_id)
        
        hideout = {'selected': new_selected_ids}

        if all_parcels_data and new_selected_ids:
            selected_features = [f for f in all_parcels_data['features'] if f['properties']['id'] in new_selected_ids]
            geometries = [shape(f['geometry']) for f in selected_features]
            final_geom = unary_union(geometries)
        else:
            final_geom = Polygon()
            
    elif triggered_id == 'edit-control':
        if drawn_geojson and drawn_geojson['features']:
            newly_drawn_geom = shape(drawn_geojson['features'][-1]['geometry'])
            
            if edit_mode == 'add':
                final_geom = base_geom.union(newly_drawn_geom)
            else: # subtract
                final_geom = base_geom.difference(newly_drawn_geom)
            
            new_selected_ids = []
            hideout = {'selected': []}
    
    if final_geom.is_empty:
        final_geojson = None
    else:
        if isinstance(final_geom, Polygon):
            final_geom = MultiPolygon([final_geom])
        final_geojson = {'type': 'FeatureCollection', 'features': [{'type': 'Feature', 'geometry': mapping(final_geom), 'properties': {}}]}

    session_data['site_polygon'] = final_geojson
    session_data['wind_direction'] = wind_direction

    return session_data, final_geojson, new_selected_ids, hideout```

#### `./run.py`

```python
from app import app

# This is the entry point for running the application
if __name__ == '__main__':
    app.run(debug=True)```

#### `./app.py`

```python
import dash
import dash_bootstrap_components as dbc
from dash import dcc, html, Input, Output
from backend.translation import T

# --- THE FIX IS HERE ---
# Add external scripts for chroma.js (for map coloring)
external_scripts = [
    "https://cdnjs.cloudflare.com/ajax/libs/chroma-js/2.4.2/chroma.min.js"
]

# Initialize the Dash app with the external scripts
app = dash.Dash(
    __name__, 
    external_stylesheets=[dbc.themes.BOOTSTRAP], 
    suppress_callback_exceptions=True,
    external_scripts=external_scripts
)
app.title = T['DE']['APP_TITLE']
server = app.server

# Define the main layout
app.layout = html.Div([
    dcc.Store(id='session-store', storage_type='session'),
    dcc.Store(id='results-store', storage_type='session'),

    dbc.NavbarSimple(
        brand=T['DE']['APP_TITLE'],
        color="dark",
        dark=True,
        fluid=True,
    ),
    dcc.Location(id='url', refresh=False),
    html.Div(id='page-content', className="container-fluid mt-4") # Use container-fluid for better grid layout
])

# Register page layouts
from pages import step1_scope, step2_constraints, step3_optimize, step4_explore, step5_compare

# Callback to control page navigation
@app.callback(
    Output('page-content', 'children'),
    Input('url', 'pathname')
)
def display_page(pathname):
    if pathname == '/step2':
        return step2_constraints.layout()
    elif pathname == '/step3':
        return step3_optimize.layout()
    elif pathname == '/step4':
        return step4_explore.layout()
    elif pathname == '/step5':
        return step5_compare.layout()
    else:
        return step1_scope.layout()```

---

### Instructions for the LLM

Please analyze the provided project structure and code to provide a comprehensive summary.

- **Goals:** Summarize the main purpose and goals of this application.
- **Methods:** Describe the core functionalities, key algorithms, and libraries used.
- **User Interaction:** Explain how a user would interact with the application, including inputs, outputs, and any user interface elements.

Thank you for your assistance.
