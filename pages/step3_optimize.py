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
    return dbc.Container([
        html.H2(T[lang]['STEP3_TITLE']),
        dbc.Row([
            dbc.Col(dbc.Button(T[lang]['PREV_STEP'], href='/step2', color="secondary")),
            dbc.Col(dbc.Button(T[lang]['NEXT_STEP'], href='/step4', color="primary"), className="text-end")
        ], className="mt-4"),

        dbc.Row([
            dbc.Col([
                dbc.Button(T[lang]['STEP3_START_BUTTON'], id='start-optimization-btn', color="success", size="lg", className="mb-3"),
            ], md=8),
            dbc.Col([
                dbc.Label(T[lang]['STEP3_UPDATE_INTERVAL_LABEL']),
                dbc.Input(id='live-update-interval-generations', type="number", min=1, max=500, step=1, value=50, size="sm"),
            ], md=4),
        ]),
        
        dcc.Store(id='opt-session-id', data=None),
        html.Div(id="progress-container", children=[
            dbc.Progress(id="progress-bar", label="0%", style={'height': '30px'}),
            html.Div(id="progress-text", className="text-center text-muted small mt-1")
        ], style={'visibility': 'hidden'}),
        
        html.Hr(),
        
        # Archive Visualization Section
        dbc.Card(dbc.CardBody([
            html.H4(T[lang]['STEP3_ARCHIVE_VIS_HEADER']),
            dbc.Row([
                dbc.Col([
                    dbc.Label(T[lang]['STEP3_X_AXIS_LABEL']),
                    dcc.Dropdown(id='x-axis-dropdown-s3'),
                ], md=6),
                dbc.Col([
                    dbc.Label(T[lang]['STEP3_Y_AXIS_LABEL']),
                    dcc.Dropdown(id='y-axis-dropdown-s3'),
                ], md=6),
            ]),
        ]), className="mb-3"),
        
        dbc.Row([
            dbc.Col([
                html.H5(T[lang]['STEP3_SOLUTION_GRID_HEADER']),
                dcc.Loading(html.Div(id='solution-map-grid-container-s3'))
            ], md=6),
            dbc.Col([
                html.H5(T[lang]['STEP3_PARALLEL_COORDS_HEADER']),
                dcc.Loading(dcc.Graph(id='parallel-coords-plot-s3'))
            ], md=6),
        ]),
        
        dcc.Interval(id='live-update-interval', interval=2*1000, n_intervals=0, disabled=True),  # Poll every 2 seconds
    ], fluid=True)

# --- NEW: Callback to start interval and generate session ID ---
@callback(
    Output('live-update-interval', 'disabled'),
    Output('opt-session-id', 'data'),
    Input('start-optimization-btn', 'n_clicks'),
    prevent_initial_call=True
)
def toggle_live_updates(n_clicks):
    session_id = str(uuid.uuid4())
    return False, session_id # Enable interval and set session ID

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
    
    if not results_data or 'selected_features_indices' not in results_data:
        return [], [], None, None
    
    # Get current language (default to 'DE')
    lang = language if language else 'DE'
    
    # Translate feature labels based on current language
    feature_indices = results_data['selected_features_indices']
    labels = translate_feature_labels(feature_indices, lang)
    
    options = [{'label': label, 'value': i} for i, label in enumerate(labels)]
    val1 = 0 if len(options) > 0 else None
    val2 = 1 if len(options) > 1 else None
    return options, options, val1, val2

# --- Update solution grid visualization ---
@callback(
    Output('solution-map-grid-container-s3', 'children'),
    Input('x-axis-dropdown-s3', 'value'),
    Input('y-axis-dropdown-s3', 'value'),
    Input('results-store', 'data'),
    Input('live-update-interval', 'n_intervals'),
    State('opt-session-id', 'data'),
)
def update_solution_map_grid_s3(x_axis_idx, y_axis_idx, results_data, n_intervals, opt_session_id):
    from dash import ctx
    
    # Determine which data source to use
    if ctx.triggered_id == 'live-update-interval' and opt_session_id:
        # Live update during optimization
        live_results_path = os.path.join(TEMP_RESULTS_DIR, f"live_{opt_session_id}.pkl")
        if not os.path.exists(live_results_path):
            return no_update
        
        # Load live results
        with open(live_results_path, 'rb') as f:
            live_data = pickle.load(f)
        
        if not results_data or 'grid_geojson' not in results_data:
            return no_update
            
        # Use live elite list
        list_of_elites = live_data.get('elites', [])
        if not list_of_elites:
            return html.Div("Warte auf erste Lösungen...", className="text-muted")
    else:
        # Final results or axis change
        if not results_data or not isinstance(x_axis_idx, int) or not isinstance(y_axis_idx, int):
            return dbc.Alert("Optimierungsergebnisse nicht gefunden oder Achsen nicht gewählt.", color="warning")

        results_path = results_data.get('full_results_path')
        if not results_path or not os.path.exists(results_path):
            return dbc.Alert("Fehler: Große Ergebnisdatei nicht gefunden.", color="danger")

        with open(results_path, 'rb') as f:
            list_of_elites = pickle.load(f)
    
    # Common visualization code
    grid_geojson = results_data.get('grid_geojson')
    if not grid_geojson:
        return dbc.Alert("Fehler: Georeferenzierung nicht gefunden.", color="danger")
    
    if not isinstance(x_axis_idx, int) or not isinstance(y_axis_idx, int):
        return no_update

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
    Input('live-update-interval', 'n_intervals'),
    Input('language-store', 'data'),
    State('opt-session-id', 'data'),
)
def update_parallel_coords_s3(results_data, n_intervals, language, opt_session_id):
    from dash import ctx
    from backend.translation import translate_feature_labels
    
    # Get current language (default to 'DE')
    lang = language if language else 'DE'
    
    # Determine which data source to use
    if ctx.triggered_id == 'live-update-interval' and opt_session_id:
        # Live update during optimization
        live_results_path = os.path.join(TEMP_RESULTS_DIR, f"live_{opt_session_id}.pkl")
        if not os.path.exists(live_results_path):
            return no_update
        
        # Load live results
        with open(live_results_path, 'rb') as f:
            live_data = pickle.load(f)
        
        list_of_elites = live_data.get('elites', [])
        if not list_of_elites or not results_data:
            return {}
        
        # Translate labels based on current language
        feature_indices = results_data.get('selected_features_indices', [])
        labels = translate_feature_labels(feature_indices, lang)
    else:
        # Final results
        if not results_data:
            return {}
        
        results_path = results_data.get('full_results_path')
        if not results_path or not os.path.exists(results_path):
            return {}

        with open(results_path, 'rb') as f:
            list_of_elites = pickle.load(f)
        
        # Translate labels based on current language
        feature_indices = results_data.get('selected_features_indices', [])
        labels = translate_feature_labels(feature_indices, lang)
    
    # Create parallel coordinates plot
    df_for_plot = pd.DataFrame(list_of_elites)
    if df_for_plot.empty:
        return {}
    
    measures_df = pd.DataFrame(df_for_plot['measures'].tolist(), columns=labels)
    df_for_plot = pd.concat([df_for_plot['objective'], measures_df], axis=1).copy()
    df_for_plot.rename(columns={'objective': 'Zielfunktion (Kaltluft)'}, inplace=True)
    
    parallel_fig = px.parallel_coordinates(
        df_for_plot, dimensions=['Zielfunktion (Kaltluft)'] + labels, color="Zielfunktion (Kaltluft)",
        labels={dim: dim.replace(" ", "<br>") for dim in ['Zielfunktion (Kaltluft)'] + labels}, # TODO fix translation of objective function
        title="Erkundung des Lösungsraums" + (" (Live)" if ctx.triggered_id == 'live-update-interval' else "")
    )
    
    return parallel_fig

@callback(
    Output('results-store', 'data', allow_duplicate=True),
    Output('live-update-interval', 'disabled', allow_duplicate=True),
    Input('start-optimization-btn', 'n_clicks'),
    State('session-store', 'data'),
    State('opt-session-id', 'data'), # Get the session ID
    State('results-store', 'data'), # Check existing results
    State('live-update-interval-generations', 'value'), # Get generation interval
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
def run_optimization(set_progress, n_clicks, session_data, opt_session_id, existing_results, live_update_generations):
    if n_clicks:
        cleanup_old_files(TEMP_RESULTS_DIR)
        
    if not n_clicks or not session_data or not session_data.get('site_polygon'):
        # Don't overwrite existing results, just show no update
        if existing_results:
            return no_update, no_update
        return None, True

    selected_features = session_data.get('selected_features', list(range(8)))
    user_feature_ranges = session_data.get('feature_ranges', {})
    hard_constraints = session_data.get('hard_constraints', {})
    qd_hyperparams = session_data.get('qd_hyperparams', {})
    
    # Add live update interval to qd_hyperparams
    if live_update_generations and live_update_generations > 0:
        qd_hyperparams['live_update_interval'] = int(live_update_generations)
    else:
        qd_hyperparams['live_update_interval'] = 50  # Default

    # Shared state for live updates
    live_state = {'buildable_mask': None, 'encoding_obj': ParametricEncoding(ENCODING_CONFIG)}

    def progress_callback(progress, text, archive=None):
        set_progress((progress, f"{progress}%", text, {'visibility': 'visible'}))
        if archive and not archive.empty and live_state['buildable_mask'] is not None:
            try:
                # Save a snapshot of the archive for the live visualization
                live_update_path = os.path.join(TEMP_RESULTS_DIR, f"live_{opt_session_id}.pkl")
                
                # Get archive data
                objectives = archive.data('objective')
                measures = archive.data('measures')
                solutions = archive.data('solution')
                grid_indices = archive.index_of(measures)
                grid_indices = archive.int_to_grid_index(grid_indices)
                
                # Create elite list for visualization with regenerated heightmaps
                live_elites = []
                # Limit to 200 elites for performance during live updates
                num_to_process = min(len(objectives), 200)
                for i in range(num_to_process):
                    genome = solutions[i]
                    heightmap = live_state['encoding_obj'].express(live_state['buildable_mask'], genome)
                    live_elites.append({
                        "objective": objectives[i],
                        "measures": measures[i].tolist(),
                        "grid_indices": grid_indices[i].tolist(),
                        "heightmap": heightmap.flatten().tolist()
                    })
                
                with open(live_update_path, 'wb') as f:
                    pickle.dump({'elites': live_elites}, f)
            except Exception as e:
                print(f"Error saving live update: {e}")

    try:
        # profiler = cProfile.Profile()
        # profiler.enable()
        
        # Pre-create environment to get buildable_mask for live updates
        from backend.optimization_process import create_environment
        set_progress((5, "5%", "Creating environment...", {'visibility': 'visible'}))
        env_config = create_environment(
            session_data['site_polygon'],
            selected_features,
            user_feature_ranges
        )
        live_state['buildable_mask'] = env_config['buildable_mask']
        
        # Start optimization
        archive, labels, env_config = start_optimization(
            session_data['site_polygon'],
            session_data['wind_direction'],
            selected_features,
            user_feature_ranges,
            hard_constraints,
            qd_hyperparams,
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
                genome = solutions[i]
                heightmap = encoding_obj.express(env_config['buildable_mask'], genome)

                full_list_of_elites.append({
                    "id": i,
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

            # profiler.disable()
            # stats = pstats.Stats(profiler).sort_stats('cumtime')
            # stats.dump_stats('optimization_profile.prof') # Save the results to a file
            
            # Visualization is now handled by separate callbacks for parallel-coords-plot-s3 and solution-map-grid-container-s3
            return results_summary_to_store, True
        
    except Exception as e:
        import traceback
        print("!!!!!! OPTIMIZATION FAILED in UI callback !!!!!!")
        traceback.print_exc()
        return None, True
    
    return None, True

# Note: Live visualization is now handled by update_parallel_coords_s3 and update_solution_map_grid_s3 callbacks
# which update parallel-coords-plot-s3 and solution-map-grid-container-s3 respectively