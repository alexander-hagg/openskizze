#
# pages/step3_optimize.py
#
import dash
from dash import dcc, html, Input, Output, State, callback, no_update, clientside_callback, ALL
import dash_bootstrap_components as dbc
from backend.translation import T
from backend.optimization_process import start_optimization
from backend.analysis import heightmap_to_geojson
from backend.config import ENCODING_CONFIG
import plotly.express as px
import pandas as pd
from dash import DiskcacheManager
import diskcache
import pickle
import uuid
import os
import numpy as np
import base64
import dash_leaflet as dl
from dash_extensions.javascript import assign
from backend.encoding import ParametricEncoding
from backend.config import ENCODING_CONFIG
import time

import cProfile # Import the profiler
import pstats   # Import for saving stats

cache = diskcache.Cache("./cache")
background_callback_manager = DiskcacheManager(cache)

TEMP_RESULTS_DIR = "temp_results"
os.makedirs(TEMP_RESULTS_DIR, exist_ok=True)

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

# Cleanup temp files on exit
def cleanup_old_files(directory: str, max_age_hours: int = 24):
    """
    Removes files from a directory if they are older than max_age_hours.
    """
    print(f"Running cleanup on '{directory}' for files older than {max_age_hours} hours...")
    try:
        max_age_seconds = max_age_hours * 3600
        current_time = time.time()
        for filename in os.listdir(directory):
            file_path = os.path.join(directory, filename)
            if os.path.isfile(file_path):
                file_age_seconds = current_time - os.path.getmtime(file_path)
                if file_age_seconds > max_age_seconds:
                    print(f"Deleting stale file: {file_path}")
                    os.remove(file_path)
    except Exception as e:
        print(f"Error during file cleanup: {e}")


def layout(lang='DE'):
    from backend.translation import create_breadcrumb
    return dbc.Container([
        create_breadcrumb(3, lang),
        html.H2(T[lang]['STEP3_TITLE']),
        
        dbc.Row([
            dbc.Col([
                dbc.Button(T[lang]['STEP3_START_BUTTON'], id='start-optimization-btn', color="success", size="lg", className="mb-3"),
            ], md=12),
        ]),
        
        html.Div(id="progress-container", children=[
            dbc.Progress(id="progress-bar", label="0%", style={'height': '30px'}),
            html.Div(id="progress-text", className="text-center text-muted small mt-1")
        ], style={'visibility': 'hidden'}),
        
        # Hidden placeholder components for callbacks that still reference them
        # These will be properly implemented in Step 4
        html.Div([
            dcc.Dropdown(id='x-axis-dropdown-s3', style={'display': 'none'}),
            dcc.Dropdown(id='y-axis-dropdown-s3', style={'display': 'none'}),
            dcc.Graph(id='archive-heatmap-s3', style={'display': 'none'}),
            html.Div(id='solution-map-grid-container-s3', style={'display': 'none'}),
            dcc.Graph(id='parallel-coords-plot-s3', style={'display': 'none'}),
        ], style={'display': 'none'}),
        
    ], fluid=True)

# --- Populate axis dropdowns from results ---
@callback(
    Output('x-axis-dropdown-s3', 'options'),
    Output('y-axis-dropdown-s3', 'options'),
    Output('x-axis-dropdown-s3', 'value'),
    Output('y-axis-dropdown-s3', 'value'),
    Input('results-store', 'data'),
    Input('language-store', 'data'),
)
def populate_dropdowns_s3(results_data, language):
    from backend.translation import translate_feature_labels
    
    # Get feature indices from final results only
    if not results_data or 'selected_features_indices' not in results_data:
        return [], [], None, None
    
    feature_indices = results_data['selected_features_indices']
    feature_set = results_data.get('feature_set', 'consolidated')
    
    # Get current language (default to 'DE')
    lang = language if language else 'DE'
    
    # Translate feature labels based on current language and feature set
    labels = translate_feature_labels(feature_indices, lang, feature_set)
    
    options = [{'label': label, 'value': i} for i, label in enumerate(labels)]
    val1 = 0 if len(options) > 0 else None
    val2 = 1 if len(options) > 1 else None
    return options, options, val1, val2

# --- Update archive heatmap ---
@callback(
    Output('archive-heatmap-s3', 'figure'),
    Input('x-axis-dropdown-s3', 'value'),
    Input('y-axis-dropdown-s3', 'value'),
    Input('results-store', 'data'),
    State('language-store', 'data'),
)
def update_archive_heatmap_s3(x_axis_idx, y_axis_idx, results_data, language):
    """Create a heatmap of the archive showing objective values with proper axis labels and ranges"""
    lang = language if language else 'DE'
    
    if not isinstance(x_axis_idx, int) or not isinstance(y_axis_idx, int):
        return px.imshow([[0]], title=T[lang].get('STEP3_NO_AREA', 'Select axes'))
    
    # Load final results only
    if not results_data:
        return px.imshow([[0]], title=T[lang].get('STEP3_NO_SOLUTIONS', 'No results found'))
    
    results_path = results_data.get('full_results_path')
    if not results_path or not os.path.exists(results_path):
        return px.imshow([[0]], title=T[lang].get('STEP3_NO_SOLUTIONS', 'No results found'))
    
    with open(results_path, 'rb') as f:
        list_of_elites = pickle.load(f)
    
    # Get dimensions and feature ranges from final results
    grid_dims = results_data['archive_dims']
    selected_features = results_data['selected_features_indices']
    user_feature_ranges = results_data.get('feature_ranges', {})
    
    # Get the actual feature ranges used by the archive
    from backend.config import DOMAIN_CONFIG
    
    # Build feature ranges for selected features
    feat_ranges = []
    for feature_index in selected_features:
        user_range = user_feature_ranges.get(str(feature_index))
        if user_range:
            feat_ranges.append(user_range)
        else:
            # This shouldn't happen if optimization_process.py is working correctly
            feat_ranges.append(DOMAIN_CONFIG['feat_ranges'][feature_index])
    
    grid_resolution_x = grid_dims[x_axis_idx]
    grid_resolution_y = grid_dims[y_axis_idx]
    
    # Create grid for objectives
    heatmap_grid = np.full((grid_resolution_y, grid_resolution_x), np.nan)
    
    for elite_dict in list_of_elites:
        ix = elite_dict['grid_indices'][x_axis_idx]
        iy = elite_dict['grid_indices'][y_axis_idx]
        if np.isnan(heatmap_grid[iy, ix]) or elite_dict['objective'] > heatmap_grid[iy, ix]:
            heatmap_grid[iy, ix] = elite_dict['objective']
    
    # Get feature labels
    from backend.translation import translate_feature_labels
    feature_set = results_data.get('feature_set', 'consolidated')
    labels = translate_feature_labels(selected_features, 'DE', feature_set)
    
    # Calculate axis tick positions and labels
    x_range = feat_ranges[x_axis_idx]
    y_range = feat_ranges[y_axis_idx]
    
    # Create tick positions (cell centers)
    x_tick_positions = np.arange(grid_resolution_x)
    y_tick_positions = np.arange(grid_resolution_y)
    
    # Create tick labels (feature values at cell centers)
    x_tick_values = np.linspace(x_range[0], x_range[1], grid_resolution_x)
    y_tick_values = np.linspace(y_range[0], y_range[1], grid_resolution_y)
    
    # Format tick labels
    x_tick_labels = [f"{val:.1f}" for val in x_tick_values]
    y_tick_labels = [f"{val:.1f}" for val in y_tick_values]
    
    # Calculate max objective for color range
    max_objective = np.nanmax(heatmap_grid)
    if np.isnan(max_objective) or max_objective <= 0:
        max_objective = 1.0
    max_objective_ceil = float(np.ceil(max_objective))
    
    # Create heatmap
    fig = px.imshow(
        heatmap_grid,
        aspect='equal',
        color_continuous_scale='Viridis',
        labels={'x': labels[x_axis_idx], 'y': labels[y_axis_idx], 'color': T[lang]['STEP3_HEATMAP_OBJECTIVE_LABEL']},
        title=T[lang]['STEP3_ARCHIVE_HEATMAP_COVERAGE'],
        zmin=0.0,
        zmax=max_objective_ceil
    )
    
    # Update axes with proper labels
    fig.update_xaxes(
        tickmode='array',
        tickvals=x_tick_positions[::max(1, grid_resolution_x // 10)],  # Show ~10 ticks
        ticktext=[x_tick_labels[i] for i in range(0, grid_resolution_x, max(1, grid_resolution_x // 10))],
        title=labels[x_axis_idx]
    )
    
    fig.update_yaxes(
        tickmode='array',
        tickvals=y_tick_positions[::max(1, grid_resolution_y // 10)],  # Show ~10 ticks
        ticktext=[y_tick_labels[i] for i in range(0, grid_resolution_y, max(1, grid_resolution_y // 10))],
        title=labels[y_axis_idx]
    )
    
    fig.update_layout(height=500)
    
    return fig

# --- Update solution grid visualization ---
@callback(
    Output('solution-map-grid-container-s3', 'children'),
    Input('x-axis-dropdown-s3', 'value'),
    Input('y-axis-dropdown-s3', 'value'),
    Input('results-store', 'data'),
)
def update_solution_map_grid_s3(x_axis_idx, y_axis_idx, results_data):
    if not isinstance(x_axis_idx, int) or not isinstance(y_axis_idx, int):
        return dbc.Alert("Optimierungsergebnisse nicht gefunden oder Achsen nicht gewählt.", color="warning")
    
    # Load final results only
    if not results_data:
        return dbc.Alert("Optimierungsergebnisse nicht gefunden.", color="warning")
    
    results_path = results_data.get('full_results_path')
    if not results_path or not os.path.exists(results_path):
        return dbc.Alert("Fehler: Große Ergebnisdatei nicht gefunden.", color="danger")
    
    with open(results_path, 'rb') as f:
        list_of_elites = pickle.load(f)
    
    # Get grid_geojson from results_data
    grid_geojson = results_data.get('grid_geojson')
    xy_length = results_data.get('xy_length', ENCODING_CONFIG.get('xy_length'))
    
    if not grid_geojson:
        return dbc.Alert("Keine Grid-Daten verfügbar.", color="warning")

    # Get dimensions from final results
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
    # Get xy_length from the loaded metadata (already set earlier)
    heightmap_res = xy_length
    
    lons = [c[0] for f in grid_geojson['features'] for c in f['geometry']['coordinates'][0]]
    lats = [c[1] for f in grid_geojson['features'] for c in f['geometry']['coordinates'][0]]
    map_center = [(min(lats) + max(lats)) / 2, (min(lons) + max(lons)) / 2]

    for row in range(grid_resolution_y):
        row_children = []
        for col in range(grid_resolution_x):
            elite_data = vis_grid[row, col]
            map_id = {'type': 'solution-map-s3', 'index': f'{row}-{col}'}
            
            if elite_data is not None:
                heightmap = np.array(elite_data['heightmap']).reshape((heightmap_res, heightmap_res))
                design_geojson = heightmap_to_geojson(np.flipud(heightmap), grid_geojson)
                
                map_component = dl.Map(
                    center=map_center, zoom=14,
                    children=[
                        dl.TileLayer(url="https://{s}.basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}{r}.png",
                                     attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'),
                        dl.GeoJSON(data=design_geojson, id=f'geojson-s3-{row}-{col}', 
                                   options=dict(style=style_handle), 
                                   hideout={'z_length': int(ENCODING_CONFIG['max_building_floors'] * ENCODING_CONFIG['meters_per_floor'])})
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

# --- Sync map views (clientside callback) ---
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
    Output({'type': 'solution-map-s3', 'index': ALL}, 'view'),
    Input({'type': 'solution-map-s3', 'index': ALL}, 'view'),
    State({'type': 'solution-map-s3', 'index': ALL}, 'id'),
    prevent_initial_call=True
)

# --- Update parallel coordinates plot ---
@callback(
    Output('parallel-coords-plot-s3', 'figure'),
    Input('results-store', 'data'),
    Input('language-store', 'data'),
)
def update_parallel_coords_s3(results_data, language):
    from backend.translation import translate_feature_labels
    
    # Get current language (default to 'DE')
    lang = language if language else 'DE'
    
    # Load final results only
    if not results_data:
        return {}
    
    results_path = results_data.get('full_results_path')
    if not results_path or not os.path.exists(results_path):
        return {}
    
    with open(results_path, 'rb') as f:
        list_of_elites = pickle.load(f)
    
    # Get feature indices and feature set from final results
    feature_indices = results_data.get('selected_features_indices', [])
    feature_set = results_data.get('feature_set', 'consolidated')
    
    # Translate labels based on current language and feature set
    labels = translate_feature_labels(feature_indices, lang, feature_set)
    
    # Create parallel coordinates plot
    df_for_plot = pd.DataFrame(list_of_elites)
    if df_for_plot.empty:
        return {}
    
    # Add units to feature labels
    from backend.units import get_unit_label
    labels_with_units = []
    for i, label in enumerate(labels):
        feature_idx = feature_indices[i]
        unit = get_unit_label(feature_idx, lang)
        if unit:
            labels_with_units.append(f"{label}<br>({unit})")
        else:
            labels_with_units.append(label)
    
    measures_df = pd.DataFrame(df_for_plot['measures'].tolist(), columns=labels_with_units)
    df_for_plot = pd.concat([df_for_plot['objective'], measures_df], axis=1).copy()
    
    # Use translated objective label
    objective_label = T[lang]['STEP6_OBJECTIVE'].replace(':', '')  # Remove colon
    df_for_plot.rename(columns={'objective': objective_label}, inplace=True)
    
    # Calculate max objective for color range
    max_objective = df_for_plot[objective_label].max()
    if pd.isna(max_objective) or max_objective <= 0:
        max_objective = 1.0
    max_objective_ceil = float(np.ceil(max_objective))
    
    # Create dimension labels with line breaks
    all_dims = [objective_label] + labels_with_units
    dim_labels = {dim: dim.replace(" ", "<br>") for dim in all_dims}
    
    parallel_fig = px.parallel_coordinates(
        df_for_plot, dimensions=all_dims, color=objective_label,
        labels=dim_labels,
        title=T[lang]['STEP3_PARALLEL_COORDS_HEADER'],
        color_continuous_scale='Viridis',
        range_color=[0.0, max_objective_ceil]
    )
    
    return parallel_fig

@callback(
    Output('results-store', 'data', allow_duplicate=True),
    Input('start-optimization-btn', 'n_clicks'),
    State('session-store', 'data'),
    State('results-store', 'data'), # Check existing results
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
def run_optimization(set_progress, n_clicks, session_data, existing_results):
    if n_clicks:
        cleanup_old_files(TEMP_RESULTS_DIR)
    
    # Validate prerequisites before starting optimization
    if not n_clicks:
        print("[run_optimization] No button click detected")
        if existing_results:
            return no_update
        return None
    
    if not session_data:
        print("[run_optimization] ✗ ERROR: No session data available")
        print("[run_optimization] Please go back to Step 1 and select a parcel")
        return no_update
    
    if not session_data.get('site_polygon'):
        print("[run_optimization] ✗ ERROR: No parcel selected")
        print("[run_optimization] Please go back to Step 1 and select a parcel")
        return no_update
    
    print(f"[run_optimization] ✓ Starting optimization (click #{n_clicks})")

    selected_features = session_data.get('selected_features', list(range(8)))
    user_feature_ranges = session_data.get('feature_ranges', {})
    hard_constraints = session_data.get('hard_constraints', {})
    qd_hyperparams = session_data.get('qd_hyperparams', {})
    feature_set = session_data.get('feature_set', 'consolidated')
    model_type = session_data.get('model_type', 'street_canyon')
    ucb_lambda = session_data.get('ucb_lambda', 1.0)
    
    print(f"[run_optimization] Model settings: type={model_type}, ucb_lambda={ucb_lambda}")
    
    # Retrieve and deserialize cached building data from Step 1 (if available)
    cached_building_data = None
    serialized_building_data = session_data.get('building_data', None)
    if serialized_building_data:
        try:
            cached_building_data = pickle.loads(base64.b64decode(serialized_building_data))
            print("[run_optimization] ✓ Deserialized cached building data from session")
        except Exception as e:
            print(f"[run_optimization] ✗ Error deserializing building data: {e}")
            cached_building_data = None

    # Simple progress callback - only updates the progress bar
    def progress_callback(progress, text, archive=None):
        set_progress((progress, f"{progress:.0f}%", text, {'visibility': 'visible'}))

    try:
        # profiler = cProfile.Profile()
        # profiler.enable()
        
        # Start optimization with cached building data, feature set, and grid params
        grid_params = session_data.get('grid_params')  # Use pre-calculated grid from step 1
        archive, labels, env_config = start_optimization(
            session_data['site_polygon'],
            session_data['wind_direction'],
            selected_features,
            user_feature_ranges,
            hard_constraints,
            qd_hyperparams,
            objective_function='street_canyon',  # Keep for backward compatibility, but model_type takes precedence
            cached_building_data=cached_building_data,
            feature_set=feature_set,
            progress_callback=progress_callback,
            model_type=model_type,
            ucb_lambda=ucb_lambda,
            grid_params=grid_params
        )
        
        if archive and not archive.empty:
            # 1. Instantiate an encoder object with the SAME config used during optimization
            # CRITICAL: Use the encoding config from env_config, NOT the default ENCODING_CONFIG!
            # This ensures max_building_floors matches what was used during optimization.
            encoding_config_for_saving = env_config.get('encoding_config', ENCODING_CONFIG.copy())
            encoding_obj = ParametricEncoding(encoding_config_for_saving)
            
            # 2. Retrieve all necessary data from the archive, including the compact
            #    'solution' (genome) instead of the non-existent 'heightmaps'.
            objectives = archive.data('objective')
            measures = archive.data('measures')
            solutions = archive.data('solution') # The compact genomes
            
            grid_indices = archive.index_of(measures)
            grid_indices = archive.int_to_grid_index(grid_indices)
            
            # Filter solutions to ensure they respect user-defined feature constraints
            # This is needed because the archive might contain solutions slightly outside bounds
            #
            # CRITICAL: Use the same encoding that was used during evaluation!
            # If surrogate model was used, it uses NumbaFastEncoding, not ParametricEncoding
            use_surrogate = env_config.get('use_surrogate', False)
            surrogate_wrapper = env_config.get('surrogate_wrapper', None)
            
            if use_surrogate and surrogate_wrapper is not None:
                # Use the fast_encoding from the surrogate wrapper
                regeneration_encoding = surrogate_wrapper.evaluator.fast_encoding
            else:
                # Use the standard ParametricEncoding
                regeneration_encoding = encoding_obj
            
            full_list_of_elites = []
            for i in range(len(objectives)):
                genome = solutions[i]
                
                # Use correct encoding based on evaluation method
                if use_surrogate and surrogate_wrapper is not None:
                    # NumbaFastEncoding uses express_batch, so wrap in batch
                    heightmaps = regeneration_encoding.express_batch(genome.reshape(1, -1))
                    heightmap = heightmaps[0]
                else:
                    # ParametricEncoding uses express with buildable mask
                    heightmap = regeneration_encoding.express(env_config['buildable_mask'], genome)

                
                # Check if this solution respects all feature constraints
                is_valid = True
                if user_feature_ranges:
                    for feat_idx_str, (min_val, max_val) in user_feature_ranges.items():
                        feat_idx = int(feat_idx_str)
                        # Find the position of this feature in selected_features
                        if feat_idx in selected_features:
                            pos = selected_features.index(feat_idx)
                            measure_value = measures[i][pos]
                            if not (min_val <= measure_value <= max_val):
                                is_valid = False
                                break
                
                if is_valid:
                    full_list_of_elites.append({
                        "id": len(full_list_of_elites),  # Re-index after filtering
                        "objective": objectives[i],
                        "measures": measures[i].tolist(),
                        "grid_indices": grid_indices[i].tolist(),
                        "heightmap": heightmap.flatten().tolist(), # Store the regenerated map
                        "genome": genome.tolist()  # Store genome for flow field generation
                    })

            session_id = str(uuid.uuid4())
            full_results_path = os.path.join(TEMP_RESULTS_DIR, f"{session_id}.pkl")
            with open(full_results_path, 'wb') as f:
                pickle.dump(full_list_of_elites, f)
            
            # Save env_3d_expanded and building metadata separately for visualization
            env_3d_path = os.path.join(TEMP_RESULTS_DIR, f"{session_id}_env.pkl")
            with open(env_3d_path, 'wb') as f:
                # Save the expanded version and building function data
                env_data = {
                    'env_3d_expanded': env_config.get('env_3d_expanded', env_config.get('env_3d_fixed')),
                    'building_function_map': env_config.get('building_function_map'),
                    'function_lookup': env_config.get('function_lookup', {})
                }
                pickle.dump(env_data, f)

            results_summary_to_store = {
                'full_results_path': full_results_path,
                'env_3d_path': env_3d_path,  # Store path to existing buildings data
                'archive_dims': archive.dims,
                'labels': labels,
                'grid_geojson': env_config['grid_geojson'],
                'xy_length': ENCODING_CONFIG['xy_length'],
                'selected_features_indices': selected_features,
                'feature_ranges': user_feature_ranges,  # Store feature constraints for filtering
                'feature_set': feature_set,  # Store which feature set was used
                'grid_bounds_native': env_config.get('grid_bounds_native'),  # Design area bounds
                'expanded_bounds_native': env_config.get('expanded_bounds_native'),  # Expanded visualization bounds
                'design_offset': env_config.get('design_offset'),  # Design position within expanded grid
                'phenotype_config': env_config.get('phenotype_config'),  # NEW: Adaptive phenotype parameters
            }

            # profiler.disable()
            # stats = pstats.Stats(profiler).sort_stats('cumtime')
            # stats.dump_stats('optimization_profile.prof') # Save the results to a file
            
            # Visualization is now handled by separate callbacks for parallel-coords-plot-s3 and solution-map-grid-container-s3
            return results_summary_to_store
        
    except ValueError as e:
        # User-friendly error for constraint/parcel issues
        import traceback
        print("!!!!!! OPTIMIZATION FAILED - User Error !!!!!!")
        print(str(e))
        traceback.print_exc()
        set_progress((0, "Error", str(e), {'visibility': 'visible', 'color': 'red'}))
        return None
    except RuntimeError as e:
        # Runtime error (e.g., empty archive)
        import traceback
        print("!!!!!! OPTIMIZATION FAILED - Empty Archive !!!!!!")
        print(str(e))
        traceback.print_exc()
        set_progress((0, "Error", str(e), {'visibility': 'visible', 'color': 'red'}))
        return None
    except Exception as e:
        import traceback
        print("!!!!!! OPTIMIZATION FAILED - Unexpected Error !!!!!!")
        traceback.print_exc()
        set_progress((0, "Error", f"Unexpected error: {str(e)}", {'visibility': 'visible', 'color': 'red'}))
        return None
    
    return None