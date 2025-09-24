#
# pages/step3_optimize.py
#
from dash import dcc, html, Input, Output, State, callback, no_update
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
from backend.encoding import ParametricEncoding
from backend.config import ENCODING_CONFIG
import atexit

import cProfile # Import the profiler
import pstats   # Import for saving stats

cache = diskcache.Cache("./cache")
background_callback_manager = DiskcacheManager(cache)
LANG = 'DE'

TEMP_RESULTS_DIR = "temp_results"
os.makedirs(TEMP_RESULTS_DIR, exist_ok=True)

# Cleanup temp files on exit
def cleanup_temp_files():
    for f in os.listdir(TEMP_RESULTS_DIR):
        os.remove(os.path.join(TEMP_RESULTS_DIR, f))
atexit.register(cleanup_temp_files)


def layout():
    return dbc.Container([
        html.H2(T[LANG]['STEP3_TITLE']),
        dbc.Row([
            dbc.Col(dbc.Button(T[LANG]['PREV_STEP'], href='/step2', color="secondary")),
            dbc.Col(dbc.Button(T[LANG]['NEXT_STEP'], href='/step4', color="primary"), className="text-end")
        ], className="mt-4"),

        dbc.Button(T[LANG]['STEP3_START_BUTTON'], id='start-optimization-btn', color="success", size="lg", className="mb-3"),
        dcc.Store(id='opt-session-id', data=None),
        html.Div(id="progress-container", children=[
            dbc.Progress(id="progress-bar", label="0%", style={'height': '30px'}),
            html.Div(id="progress-text", className="text-center text-muted small mt-1")
        ], style={'visibility': 'hidden'}),
        html.Hr(),
        html.H4(T[LANG]['STEP3_RESULTS_HEADER']),
        dcc.Interval(id='live-update-interval', interval=5*1000, n_intervals=0, disabled=True),
        dcc.Loading(id="loading-results", children=html.Div(id='results-output-div'))
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

@callback(
    Output('results-store', 'data'),
    Output('results-output-div', 'children'),
    Output('live-update-interval', 'disabled', allow_duplicate=True),
    Input('start-optimization-btn', 'n_clicks'),
    State('session-store', 'data'),
    State('opt-session-id', 'data'), # Get the session ID
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
def run_optimization(set_progress, n_clicks, session_data, opt_session_id):
    if not n_clicks or not session_data or not session_data.get('site_polygon'):
        return None, dbc.Alert("Bitte definieren Sie einen Geltungsbereich in Schritt 1.", color="warning"), True

    selected_features = session_data.get('selected_features', list(range(8)))
    user_feature_ranges = session_data.get('feature_ranges', {})


    def progress_callback(progress, text, archive=None):
        set_progress((progress, f"{progress}%", text, {'visibility': 'visible'}))
        if archive and not archive.empty:
            # Save a snapshot of the archive for the live plot
            live_update_path = os.path.join(TEMP_RESULTS_DIR, f"live_{opt_session_id}.pkl")
            df = archive.as_pandas()
            df.to_pickle(live_update_path)

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

            corr = df_for_plot.corr()
            heatmap_fig = px.imshow(corr, text_auto=True, aspect="auto",
                                color_continuous_scale="RdBu",
                                range_color=[-1, 1],
                                title="Korrelation der Lösungsmerkmale")
            
            parallel_fig = px.parallel_coordinates(
                df_for_plot, dimensions=['objective'] + labels, color="objective",
                labels={dim: dim.replace(" ", "<br>") for dim in ['objective'] + labels},
                title="Erkundung des Lösungsraums"
            )

            final_output = html.Div([
                dbc.Row([
                    dbc.Col(dcc.Graph(figure=heatmap_fig), md=5),
                    dbc.Col(dcc.Graph(figure=parallel_fig), md=7)
                ])
            ])

            # profiler.disable()
            # stats = pstats.Stats(profiler).sort_stats('cumtime')
            # stats.dump_stats('optimization_profile.prof') # Save the results to a file
            

            return results_summary_to_store, final_output, True
        
    except Exception as e:
        import traceback
        print("!!!!!! OPTIMIZATION FAILED in UI callback !!!!!!")
        traceback.print_exc()
        return None, dbc.Alert(f"Optimierung fehlgeschlagen: {e}", color="danger"), True
    
    return None, dbc.Alert("Optimierung fehlgeschlagen oder es wurden keine Lösungen gefunden.", color="warning"), True

# --- NEW: Callback for live plot updates ---
@callback(
    Output('results-output-div', 'children', allow_duplicate=True),
    Input('live-update-interval', 'n_intervals'),
    State('opt-session-id', 'data'),
    prevent_initial_call=True
)
def display_live_plot(n, opt_session_id):
    live_update_path = os.path.join(TEMP_RESULTS_DIR, f"live_{opt_session_id}.pkl")
    if not opt_session_id or not os.path.exists(live_update_path):
        return no_update

    df = pd.read_pickle(live_update_path)
    if df.empty:
        return no_update
        
    # Get labels from column names (e.g., 'measure_0', 'measure_1')
    dims = [col for col in df.columns if col.startswith('measure')]
    labels = {dim: T['DE'][f'MEASURE_{int(dim.split("_")[1])}'] for dim in dims}
    labels['objective'] = 'Zielfunktion (Kaltluft)'
    
    fig = px.parallel_coordinates(
        df, dimensions=['objective'] + dims, color="objective",
        labels=labels,
        title=f"Lösungsraum-Erkundung (Live-Update...)"
    )
    return dcc.Graph(figure=fig)