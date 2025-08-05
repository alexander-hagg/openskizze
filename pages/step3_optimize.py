#
# pages/step3_optimize.py (Final Corrected Version - Using archive.index_of)
#
from dash import dcc, html, Input, Output, State, callback
import dash_bootstrap_components as dbc
from backend.translation import T
from backend.optimization_process import start_optimization
import plotly.express as px
import pandas as pd
from dash import DiskcacheManager
import diskcache

cache = diskcache.Cache("./cache")
background_callback_manager = DiskcacheManager(cache)
LANG = 'DE'

def layout():
    return dbc.Container([
        html.H2(T[LANG]['STEP3_TITLE']),
        dbc.Button(T[LANG]['STEP3_START_BUTTON'], id='start-optimization-btn', color="success", size="lg", className="mb-3"),
        html.Div(id="progress-container", children=[
            dbc.Progress(id="progress-bar", label="0%", style={'height': '30px'}),
            html.Div(id="progress-text", className="text-center text-muted small mt-1")
        ], style={'visibility': 'hidden'}),
        html.Hr(),
        html.H4(T[LANG]['STEP3_RESULTS_HEADER']),
        dcc.Loading(id="loading-results", children=html.Div(id='results-output-div')),
        dbc.Row([
            dbc.Col(dbc.Button(T[LANG]['PREV_STEP'], href='/step2', color="secondary")),
            dbc.Col(dbc.Button(T[LANG]['NEXT_STEP'], href='/step4', color="primary"), className="text-end")
        ], className="mt-4")
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
    if not session_data or not session_data.get('site_polygon'):
        return None, dbc.Alert("Bitte definieren Sie einen Geltungsbereich in Schritt 1.", color="warning")
    if not n_clicks:
        return None, dbc.Alert("Führen Sie die Optimierung aus.", color="warning")

    def progress_callback(progress, text):
        set_progress((progress, f"{progress}%", text, {'visibility': 'visible'}))

    try:
        archive, labels, env_config = start_optimization(
            session_data['site_polygon'],
            session_data['wind_direction'],
            progress_callback=progress_callback
        )
        
        if archive and not archive.empty:
            # --- THE CRITICAL FIX IS HERE ---
            # 1. Extract the raw data arrays from the archive.
            objectives = archive.data('objective')
            measures = archive.data('measures')
            heightmaps = archive.data('heightmaps')
            
            # 2. Use the documented `index_of` method to get the grid indices for all elites.
            grid_indices = archive.index_of(measures)
            grid_indices = archive.int_to_grid_index(grid_indices)
            # 3. Assemble a clean, serializable list of dictionaries.
            list_of_elites = []
            for i in range(len(objectives)):
                list_of_elites.append({
                    "objective": objectives[i],
                    "measures": measures[i].tolist(),
                    "grid_indices": grid_indices[i].tolist(),  # Convert numpy array to list
                    "heightmap": heightmaps[i].tolist()
                })

            results_data_to_store = {
                'elites_data': list_of_elites,
                'archive_dims': archive.dims,
                'labels': labels,
                'buildable_mask': env_config['buildable_mask']
            }
            
            # For the plot, create a DataFrame from the clean list.
            df_for_plot = pd.DataFrame(list_of_elites)
            measures_df = pd.DataFrame(df_for_plot['measures'].tolist(), columns=labels)
            df_for_plot = pd.concat([df_for_plot['objective'], measures_df], axis=1).copy()

            fig = px.parallel_coordinates(
                df_for_plot, dimensions=['objective'] + labels, color="objective",
                labels={dim: dim.replace(" ", "<br>") for dim in ['objective'] + labels},
                title="Erkundung des Lösungsraums"
            )
            graph = dcc.Graph(figure=fig)
            
            return results_data_to_store, graph
        
    except Exception as e:
        import traceback
        print("!!!!!! OPTIMIZATION FAILED in UI callback !!!!!!")
        traceback.print_exc()
        return None, dbc.Alert(f"Optimierung fehlgeschlagen: {e}", color="danger")
    
    return None, dbc.Alert("Optimierung fehlgeschlagen oder es wurden keine Lösungen gefunden.", color="warning")