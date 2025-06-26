from dash import dcc, html, Input, Output, State, callback, CeleryManager, DiskcacheManager
import dash_bootstrap_components as dbc
from backend.translation import T
from backend.optimization import run_optimization_mock
import plotly.express as px
import pandas as pd

# Background Callback Manager
# For local development, Diskcache is easiest. For production, use Celery.
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
    if not n_clicks:
        return None, "Klicken Sie auf 'Optimierung starten', um zu beginnen."

    def progress_callback(progress, text):
        set_progress((progress, f"{progress}%", text, {'visibility': 'visible'}))

    # --- This is the long-running backend call ---
    results_archive = run_optimization_mock(
        session_data.get('site_polygon'),
        session_data.get('taboo_zones'),
        session_data.get('selected_measures'),
        progress_callback
    )

    # --- Generate visualization after backend completes ---
    if results_archive and results_archive['objective']:
        df_data = {'objective': results_archive['objective'], **results_archive['measures']}
        df = pd.DataFrame(df_data)
        
        labels = {'objective': 'Zielfunktion (Kaltluft)'}
        labels.update(session_data.get('measures_map', {}))
        
        fig = px.parallel_coordinates(
            df,
            color="objective",
            labels=labels,
            color_continuous_scale=px.colors.diverging.Tealrose
        )
        graph = dcc.Graph(figure=fig)
    else:
        graph = dbc.Alert("Optimierung fehlgeschlagen oder keine Ergebnisse.", color="danger")
    
    set_progress((100, "100%", "Fertig!", {'visibility': 'visible'}))
    return results_archive, graph