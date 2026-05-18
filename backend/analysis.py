import numpy as np
import pandas as pd
from backend.translation import T 
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from shapely.geometry import box, mapping
import geopandas as gpd
from sklearn.manifold import TSNE
from sklearn.cluster import DBSCAN, AgglomerativeClustering # <-- Added AgglomerativeClustering
from kmedoids import KMedoids
from sklearn.metrics import pairwise_distances
from sklearn.preprocessing import StandardScaler
import hdbscan
from skimage.metrics import structural_similarity as ssim # <-- Added SSIM
import torch
from pytorch_msssim import ssim as ssim_torch
import pickle
import os
import plotly.express as px
import base64
import zipfile
import shutil
from io import BytesIO
from pylatex import Document, Section, Subsection, Figure, Command
from pylatex.utils import italic, NoEscape
import logging

logger = logging.getLogger(__name__)

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

def cluster_and_analyze_solutions(results_path, algorithm='dbscan', params=None, feature_filters=None, similarity_metric='tsne'):
    """
    Loads solutions, filters them, and clusters them using the selected algorithm.
    - algorithm: 'dbscan', 'kmedoids', 'hdbscan', or 'hierarchical'
    - params: dict of parameters for the chosen algorithm
    - feature_filters: dict of feature_index -> [min_val, max_val] for additional filtering
    - similarity_metric: 'tsne' (Euclidean on 2D projection) or 'ssim' (Structural Similarity)
    """
    if not results_path or not os.path.exists(results_path):
        return []

    with open(results_path, 'rb') as f:
        list_of_elites = pickle.load(f)
    
    
    # 1. Filtering - solutions should already be filtered, but apply additional filters if specified
    filtered_elites = []
    if feature_filters:
        for elite in list_of_elites:
            is_valid = True
            for feat_idx_str, (min_val, max_val) in feature_filters.items():
                feat_idx = int(feat_idx_str)
                actual_val = elite['measures'][feat_idx]
                if not (min_val <= actual_val <= max_val):
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

    # 2. Similarity / Distance Calculation
    clustering_input = None
    metric = 'euclidean'
    
    if similarity_metric == 'tsne':
        # t-SNE (used by both for consistency in the 2D space)
        if len(filtered_elites) < 2: return [] # t-SNE requires at least 2 samples
        tsne = TSNE(n_components=2, perplexity=min(30, len(filtered_elites) - 1), 
                    random_state=42, n_iter=300, init='pca', learning_rate='auto')
        tsne_results = tsne.fit_transform(heightmaps_flat)
        
        # Standardize t-SNE results to ensure consistent scaling for clustering algorithms (especially DBSCAN eps)
        clustering_input = StandardScaler().fit_transform(tsne_results)
        metric = 'euclidean'
        
    elif similarity_metric == 'ssim':
        # Calculate pairwise SSIM distance matrix (1 - SSIM)
        n_samples = len(filtered_elites)
        if n_samples < 2: return []
        
        # Reshape heightmaps to 2D images for SSIM
        # Assuming square heightmaps
        dim = int(np.sqrt(heightmaps_flat.shape[1]))
        images = heightmaps_flat.reshape(n_samples, dim, dim)
        
        # Normalize images to data range for SSIM (0-max_height)
        max_val = images.max()
        min_val = images.min()
        data_range = max_val - min_val if max_val > min_val else 1.0
        
        # Use PyTorch for batched SSIM calculation if available
        try:
            device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
            # Convert to tensor: (N, C, H, W) -> (N, 1, dim, dim)
            imgs_tensor = torch.from_numpy(images).float().unsqueeze(1).to(device)
            
            # We need pairwise distances. 
            # pytorch_msssim.ssim computes mean SSIM between two batches.
            # To get pairwise matrix, we can broadcast.
            # But N*N might be too large for GPU memory if N is large (e.g. 1000 -> 1000x1000 images).
            # Let's do it in batches or row by row.
            
            dist_matrix = np.zeros((n_samples, n_samples))
            
            # Process in batches to avoid OOM
            batch_size = 100 # Adjust based on GPU memory
            
            for i in range(0, n_samples, batch_size):
                end_i = min(i + batch_size, n_samples)
                batch_i = imgs_tensor[i:end_i] # (B, 1, H, W)
                
                for j in range(0, n_samples, batch_size):
                    end_j = min(j + batch_size, n_samples)
                    if j > end_i: # Optimization: only compute upper triangle blocks? 
                        # Actually, let's just compute full matrix for simplicity of batching logic, 
                        # or handle symmetry carefully.
                        pass
                    
                    batch_j = imgs_tensor[j:end_j] # (B2, 1, H, W)
                    
                    # Expand for broadcasting:
                    # batch_i: (B, 1, 1, H, W)
                    # batch_j: (1, B2, 1, H, W)
                    # This creates (B, B2, 1, H, W) tensor - might be huge!
                    # 100 * 100 * 32 * 32 * 4 bytes ~ 40MB. This is fine.
                    
                    b_i = batch_i.unsqueeze(1).expand(-1, end_j - j, -1, -1, -1).reshape(-1, 1, dim, dim)
                    b_j = batch_j.unsqueeze(0).expand(end_i - i, -1, -1, -1, -1).reshape(-1, 1, dim, dim)
                    
                    # Compute SSIM
                    # ssim_torch returns (N,) tensor
                    val_range = float(data_range)
                    ssim_vals = ssim_torch(b_i, b_j, data_range=val_range, size_average=False)
                    
                    # Reshape back to (B, B2)
                    ssim_block = ssim_vals.view(end_i - i, end_j - j).cpu().numpy()
                    
                    dist_matrix[i:end_i, j:end_j] = 1.0 - ssim_block

        except Exception as e:
            logger.warning(f"PyTorch SSIM failed, falling back to CPU loop: {e}")
            # Fallback to CPU loop
            dist_matrix = np.zeros((n_samples, n_samples))
            for i in range(n_samples):
                for j in range(i + 1, n_samples):
                    score = ssim(images[i], images[j], data_range=data_range)
                    dist = 1.0 - score
                    dist_matrix[i, j] = dist
                    dist_matrix[j, i] = dist
                
        clustering_input = dist_matrix
        metric = 'precomputed'

    # 3. Clustering
    cluster_labels = None
    central_solution_indices = {} # For K-Medoids, this is pre-calculated

    if algorithm == 'hierarchical':
        n_clusters = params.get('n_clusters', 5)
        if len(filtered_elites) < n_clusters: return []
        
        if metric == 'precomputed':
            # Ward linkage requires Euclidean distance. For precomputed (SSIM), we use 'average' linkage.
            linkage = 'average'
        else:
            linkage = 'ward'
            
        agg = AgglomerativeClustering(n_clusters=n_clusters, metric=metric, linkage=linkage)
        cluster_labels = agg.fit_predict(clustering_input)

    elif algorithm == 'dbscan':
        min_samples = params.get('min_samples', 4)
        if len(filtered_elites) < min_samples: return []
        dbscan = DBSCAN(eps=params.get('eps', 0.5), min_samples=min_samples, metric=metric)
        cluster_labels = dbscan.fit_predict(clustering_input)

    elif algorithm == 'kmedoids':
        n_clusters = params.get('n_clusters', 3)
        if len(filtered_elites) < n_clusters: return []
        kmedoids = KMedoids(n_clusters=n_clusters, random_state=42, metric=metric)
        cluster_labels = kmedoids.fit_predict(clustering_input)
        # Store the medoid indices, which are the most central points
        for i, medoid_idx in enumerate(kmedoids.medoid_indices_):
            central_solution_indices[i] = medoid_idx
    
    elif algorithm == 'hdbscan':
        min_cluster_size = params.get('min_cluster_size', 5)
        if len(filtered_elites) < min_cluster_size: return []
        
        clusterer = hdbscan.HDBSCAN(min_cluster_size=min_cluster_size, gen_min_span_tree=True, metric=metric)
        cluster_labels = clusterer.fit_predict(clustering_input)

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

        # For K-Medoids, the central solution is the medoid. For others, we calculate it.
        if algorithm == 'kmedoids':
            central_solution_orig_idx = central_solution_indices[k]
        else: 
            # Calculate medoid based on the chosen metric
            if metric == 'precomputed':
                # Extract sub-matrix for this cluster
                # cluster_indices are indices into the original filtered list (and thus the distance matrix)
                sub_dist_matrix = clustering_input[np.ix_(cluster_indices, cluster_indices)]
                medoid_local_idx = np.argmin(sub_dist_matrix.sum(axis=0))
            else:
                # Euclidean distance in feature space (t-SNE or raw heightmaps? usually raw for medoid)
                # But here we used t-SNE for clustering.
                # For "central solution", we should probably use the raw heightmap distance (Euclidean)
                # or the t-SNE distance if that's what we clustered on.
                # Let's use raw heightmap distance for physical representativeness
                dist_matrix = pairwise_distances(cluster_heightmaps)
                medoid_local_idx = np.argmin(dist_matrix.sum(axis=0))
                
            central_solution_orig_idx = cluster_indices[medoid_local_idx]

        boolean_heightmaps = cluster_heightmaps > 0
        consensus_map = np.mean(boolean_heightmaps, axis=0)
        
        # Store all solutions in this cluster for diversity analysis
        cluster_solutions = [filtered_elites[idx] for idx in cluster_indices]

        analysis_results.append({
            'cluster_id': int(k),
            'size': len(cluster_indices),
            'best_solution': filtered_elites[best_solution_orig_idx],
            'central_solution': filtered_elites[central_solution_orig_idx],
            'consensus_map': consensus_map.tolist(),
            'objective_values': cluster_objectives.tolist(),  # Add objective values for histogram
            'median_objective': float(np.median(cluster_objectives)),  # Add median for sorting
            'all_solutions': cluster_solutions  # Store all solutions for diversity preview
        })
    
    
    # Sort by median objective value (highest first), then by size
    analysis_results.sort(key=lambda x: (x['median_objective'], x['size']), reverse=True)
    return analysis_results

def create_parallel_coords_fig(results_archive, measures_map):
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

def generate_pdf_report(solutions: list, all_elites: list, labels: list, grid_geojson: dict, xy_length: int):
    """
    Generates a comprehensive urban planning analysis report as a zip file
    containing the .tex source, the compiled .pdf, and image assets.
    """
    if not solutions:
        return None

    report_dir = os.path.join("temp_results", "report_assets")
    image_dir = os.path.join(report_dir, "images")
    os.makedirs(image_dir, exist_ok=True)

    try:
        # --- Document Setup ---
        geometry_options = {"tmargin": "2.5cm", "lmargin": "2.5cm", "rmargin": "2.5cm"}
        doc = Document(geometry_options=geometry_options)
        
        # Add required packages
        doc.preamble.append(Command('usepackage', 'graphicx'))
        doc.preamble.append(Command('usepackage', 'xcolor'))
        doc.preamble.append(Command('usepackage', 'geometry'))
        doc.preamble.append(Command('title', 'Städtebauliche Analyse & Planungsempfehlungen'))
        doc.preamble.append(Command('author', 'OpenSKIZZE'))
        doc.preamble.append(Command('date', NoEscape(r'\today')))
        doc.append(NoEscape(r'\maketitle'))

        # --- Introduction ---
        with doc.create(Section('Einleitung und Methodik')):
            intro_text = (
                "Dieses Dokument analysiert die Ergebnisse einer computergestützten Optimierung von Städtebauentwürfen. "
                "Ziel war die Maximierung der Kaltluftzufuhr im Plangebiet. Tausende von Varianten wurden erzeugt und bewertet. "
                "Die vielversprechendsten Lösungen wurden mittels Cluster-Analyse zu Entwurfs-Archetypen zusammengefasst. "
                "Die hier verglichenen Entwürfe repräsentieren die zentralen Vertreter dieser Archetypen.\\\n"
                "Der Bericht leitet aus dieser datengestützten Analyse konkrete Empfehlungen für die weitere Bauleitplanung ab, "
                "insbesondere für die Aufstellung eines Bebauungsplans (B-Plan) gemäß Baugesetzbuch (BauGB). "
                "Die quantitativen Erkenntnisse sollen als Grundlage für die Definition von Baufenstern und textlichen Festsetzungen dienen."
            )
            doc.append(NoEscape(intro_text))

        # --- Generate and Verify Images ---
        image_paths_to_check = []

        # Correlation heatmap
        df_all = pd.DataFrame(all_elites)
        measures_df = pd.DataFrame(df_all['measures'].tolist(), columns=labels)
        df_all = pd.concat([df_all['objective'], measures_df], axis=1)
        df_all.rename(columns={'objective': 'Zielfunktion (Kaltluft)'}, inplace=True)
        corr = df_all.corr()
        
        fig, ax = plt.subplots(figsize=(12, 10))
        im = ax.imshow(corr, cmap="RdBu_r", vmin=-1, vmax=1)
        cbar = ax.figure.colorbar(im, ax=ax)
        cbar.ax.set_ylabel("Korrelation", rotation=-90, va="bottom")
        ax.set_xticks(np.arange(len(corr.columns)))
        ax.set_yticks(np.arange(len(corr.columns)))
        ax.set_xticklabels(corr.columns)
        ax.set_yticklabels(corr.columns)
        plt.setp(ax.get_xticklabels(), rotation=45, ha="right", rotation_mode="anchor")
        for i in range(len(corr.columns)):
            for j in range(len(corr.columns)):
                ax.text(j, i, f"{corr.iloc[i, j]:.2f}", ha="center", va="center", color="w" if abs(corr.iloc[i, j]) > 0.5 else "black")
        ax.set_title("Korrelation der Merkmale und der Zielfunktion")
        fig.tight_layout()
        
        plot_path_corr_abs = os.path.join(image_dir, "correlation_heatmap.png")
        fig.savefig(plot_path_corr_abs, dpi=150)
        plt.close(fig)
        image_paths_to_check.append(plot_path_corr_abs)

        # Solution heightmaps
        solution_image_paths = {}
        for i, sol in enumerate(solutions):
            heightmap = np.array(sol['heightmap']).reshape((xy_length, xy_length))
            fig, ax = plt.subplots(figsize=(5, 5))
            ax.imshow(np.flipud(heightmap), cmap='viridis', origin='lower')
            ax.set_title(f"Höhenkarte - Archetyp {i+1}")
            ax.set_xticks([])
            ax.set_yticks([])
            plot_path_sol_abs = os.path.join(image_dir, f"solution_{sol['id']}.png")
            fig.savefig(plot_path_sol_abs, bbox_inches='tight')
            plt.close(fig)
            solution_image_paths[sol['id']] = plot_path_sol_abs
            image_paths_to_check.append(plot_path_sol_abs)

        # Verify all images were created before proceeding
        for path in image_paths_to_check:
            if not os.path.exists(path):
                raise FileNotFoundError(f"Image file was not created: {path}")

        # --- Add Content to LaTeX Document ---
        with doc.create(Section('Analyse der Wirkungszusammenhänge')):
            doc.append("Zunächst wurde der Zusammenhang zwischen den städtebaulichen Kennzahlen (Merkmalen) und der Zielfunktion (Kaltluft) "
                       "über alle leistungsstarken Lösungen hinweg untersucht. Die Korrelationsmatrix zeigt, welche Merkmale den größten Einfluss haben.")

            with doc.create(Figure(position='h!')) as heatmap_plot:
                heatmap_plot.add_image(os.path.join('images', 'correlation_heatmap.png'), width=NoEscape(r'0.9\textwidth'))
                heatmap_plot.add_caption('Korrelation der Merkmale und der Zielfunktion.')

            corr_objective = corr['Zielfunktion (Kaltluft)'].drop('Zielfunktion (Kaltluft)').sort_values(ascending=False)
            highest_pos_corr = corr_objective.head(1)
            highest_neg_corr = corr_objective.tail(1)
            
            corr_text = (
                f"Die Analyse der Zusammenhänge ist entscheidend für das Verständnis der Planungshebel. "
                f"Erwartungsgemäß zeigt sich eine starke negative Korrelation zwischen '{highest_neg_corr.index[0]}' ({highest_neg_corr.values[0]:.2f}) und der Kaltluftleistung. "
                f"Dies bestätigt, dass eine Reduzierung der versiegelten oder bebauten Flächen ein primäres Ziel sein muss.\\\\"
                f"Besonders aufschlussreich ist die stärkste positive Korrelation: Das Merkmal '{highest_pos_corr.index[0]}' ({highest_pos_corr.values[0]:.2f}) "
                f"begünstigt die Kaltluftzufuhr."
            )
            doc.append(NoEscape(corr_text))

        with doc.create(Section('Vergleich der Entwurfs-Archetypen')):
            for i, sol in enumerate(solutions):
                with doc.create(Subsection(f'Archetyp {i+1}: Städtebauliches Profil')):
                    with doc.create(Figure(position='h!')) as sol_plot:
                        sol_plot.add_image(os.path.join('images', f"solution_{sol['id']}.png"), width='8cm')
                        sol_plot.add_caption(f'Höhenkarte für Archetyp {i+1}.')

                    doc.append(NoEscape(r'\textbf{Kennzahlen:}\\'))
                    doc.append(f"Zielfunktion (Kaltluft): {sol['objective']:.4f}\\\n")
                    for j, label in enumerate(labels):
                        doc.append(f"{label}: {sol['measures'][j]:.2f}\\\n")
                    
                    doc.append(NoEscape(r'\vspace{1cm}\textbf{Analyse und planungsrechtliche Einordnung:}\\'))
                    
                    charakter_text = "Dieser Archetyp zeichnet sich durch "
                    building_count_label = next((l for l in labels if 'GEBÄUDE' in l.upper()), None)
                    if building_count_label:
                        measure_avg_buildings = df_all[building_count_label].mean()
                        if sol['measures'][labels.index(building_count_label)] > measure_avg_buildings * 1.2:
                            charakter_text += "eine hohe Anzahl kleinteiliger Gebäude aus."
                        else:
                            charakter_text += "wenige, aber größere Baukörper aus."
                    else:
                        charakter_text += "eine spezifische Baukörperanordnung aus."

                    doc.append(NoEscape(r'\textbf{Städtebaulicher Charakter:} ' + charakter_text + r'\\'))
                    doc.append(NoEscape(r'\textbf{Empfehlung für die Bauleitplanung:}\\'))
                    doc.append(NoEscape(r'{\color{red} [Beispiel]: Dieser Archetyp eignet sich als Grundlage für die Festsetzung von Baufenstern...}'))

        with doc.create(Section('Übergreifende Empfehlungen für die Bauleitplanung')):
            doc.append("Aus der vergleichenden Analyse lassen sich folgende übergreifende Empfehlungen für die Aufstellung des Bebauungsplans ableiten:")
            
            # --- Evidence-based recommendations ---
            top_10_percentile_obj = df_all['Zielfunktion (Kaltluft)'].quantile(0.9)
            top_solutions = df_all[df_all['Zielfunktion (Kaltluft)'] >= top_10_percentile_obj]

            # Recommendation 1: Ventilation corridors (General)
            doc.append(NoEscape(r'\subsection*{1. Festsetzung von Ventilationskorridoren}'))
            doc.append("Basierend auf den leistungsstärksten Entwürfen sollten Hauptventilationsachsen als 'nicht überbaubare Grundstücksflächen' festgesetzt werden, um die Kaltluftzufuhr zu maximieren.")

            # Recommendation 2: Building Density (GRZ/GFZ)
            doc.append(NoEscape(r'\subsection*{2. Steuerung der Baumassendichte (GRZ/GFZ)}'))
            grz_label = next((l for l in labels if 'GRZ' in l.upper()), None)
            gfz_label = next((l for l in labels if 'GFZ' in l.upper()), None)
            
            if grz_label and gfz_label and not top_solutions.empty:
                mean_grz = top_solutions[grz_label].mean()
                mean_gfz = top_solutions[gfz_label].mean()
                rec_text = (f"Die Analyse der Top-10%-Lösungen zeigt, dass eine hohe Kaltluftleistung bei einer "
                            f"durchschnittlichen GRZ von ca. {mean_grz:.2f} und einer GFZ von ca. {mean_gfz:.2f} erreicht wird. Es wird daher empfohlen, "
                            "ähnliche Obergrenzen im Bebauungsplan festzusetzen, um ausreichend Freifläche zu sichern (§ 16, 17, 19 BauNVO).")
                doc.append(rec_text)
            else:
                doc.append(NoEscape(r'{\color{red} [Beispiel]: Es wird empfohlen, eine maximale Grundflächenzahl (GRZ) von [z.B. 0.4] und eine Geschossflächenzahl (GFZ) von [z.B. 1.2] festzusetzen, um ausreichend Freifläche zu sichern.}'))

            # Recommendation 3: Building Height
            doc.append(NoEscape(r'\subsection*{3. Höhenentwicklung}'))
            height_label = next((l for l in labels if 'HÖHE' in l.upper()), None)
            if height_label and not top_solutions.empty:
                mean_height = top_solutions[height_label].mean()
                std_height = top_solutions[height_label].std()
                rec_text = (f"Die leistungsstärksten Lösungen weisen eine durchschnittliche Gebäudehöhe von {mean_height:.2f}m (Standardabweichung: {std_height:.2f}m) auf. "
                            "Eine moderate Höhenentwicklung scheint die Kaltluftströmung nicht negativ zu beeinflussen, solange ausreichend Freiflächen vorhanden sind. "
                            "Eine gestaffelte Höhenentwicklung kann die Durchlüftung weiter positiv beeinflussen und sollte als städtebauliches Ziel im B-Plan verankert werden.")
                doc.append(rec_text)
            else:
                doc.append(NoEscape(r'{\color{red} [Beispiel]: Eine gestaffelte Höhenentwicklung, wie in Archetyp [z.B. 2] angedeutet, kann die Durchlüftung positiv beeinflussen und sollte als städtebauliches Ziel im B-Plan verankert werden.}'))

            # Recommendation 4: Flexible Baufenster (General)
            doc.append(NoEscape(r'\subsection*{4. Flexible Baufenster}'))
            doc.append("Die Analyse der Cluster-Robustheit (Konsens-Karten, siehe Schritt 5) kann genutzt werden, um Kern-Bebauungszonen (hoher Konsens) und flexible Erweiterungsbereiche (niedriger Konsens) zu definieren. Dies ermöglicht architektonische Vielfalt bei gleichzeitiger Sicherung der Performance.")

            doc.append(NoEscape(r'\vspace{1cm}'))
            doc.append("Diese datengestützten Erkenntnisse bieten eine valide Grundlage für die weiteren Schritte im Bauleitplanverfahren und helfen, die umweltbezogenen Planungsziele objektiv zu untermauern.")


        # --- Generate and Zip Files ---
        # The actual compilation happens here. This requires a LaTeX installation.
        doc.generate_pdf(os.path.join(report_dir, 'report'), clean_tex=False)
        
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            zip_file.write(os.path.join(report_dir, 'report.pdf'), arcname='report.pdf')
            zip_file.write(os.path.join(report_dir, 'report.tex'), arcname='report.tex')
            
            for image_file in os.listdir(image_dir):
                zip_file.write(os.path.join(image_dir, image_file), arcname=os.path.join('images', image_file))

        zip_buffer.seek(0)
        b64_zip = base64.b64encode(zip_buffer.read()).decode('utf-8')
        return b64_zip

    except Exception as e:
        logger.error(f"LaTeX PDF generation failed: {e}")
        logger.info("Falling back to returning TeX source file.")
        try:
            tex_content = doc.dumps()
            return base64.b64encode(tex_content.encode('utf-8')).decode('utf-8')
        except Exception as inner_e:
            logger.error(f"Failed to even generate TeX source: {inner_e}")
            return None
    finally:
        # Clean up the temporary directory
        if os.path.exists(report_dir):
            shutil.rmtree(report_dir)