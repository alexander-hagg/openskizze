from dash import dcc, html, Input, Output, State, callback
import dash_bootstrap_components as dbc
from backend.translation import T
from backend.analysis import generate_contest_requirements

LANG = 'DE'

def layout():
    return dbc.Container([
        html.H2(T[LANG]['STEP5_TITLE']),
        dbc.Card(dbc.CardBody([
            dbc.Label(T[LANG]['STEP5_SELECT_LABEL']),
            dcc.Dropdown(id='design-selector-dropdown', multi=True, disabled=True),
            html.Div(id='comparison-view', className="mt-3")
        ])),
        html.Hr(),
        dbc.Button(T[LANG]['STEP5_EXPORT_BUTTON'], id="export-reqs-btn", color="info"),
        # Corrected usage here: dcc.Download instead of just Download
        dcc.Download(id="download-requirements"),
        
        dbc.Row([
            dbc.Col(dbc.Button(T[LANG]['PREV_STEP'], href='/step4', color="secondary")),
        ], className="mt-4")
    ], fluid=True)


@callback(
    Output('comparison-view', 'children'),
    Input('design-selector-dropdown', 'value'), # This would be populated by clicking the grid in a full implementation
)
def update_comparison_view(selected_designs):
    if not selected_designs:
        return dbc.Alert(T[LANG]['STEP5_NO_SELECTION'], color="light")
    # This is a placeholder for the comparison visualization
    return dbc.Alert(f"Vergleichsansicht für {len(selected_designs)} ausgewählte Designs (Zukünftige Funktion).", color="primary")


@callback(
    Output("download-requirements", "data"),
    Input("export-reqs-btn", "n_clicks"),
    State("results-store", "data"),
    prevent_initial_call=True,
)
def export_requirements(n_clicks, results_data):
    if not n_clicks or not results_data:
        return None
    
    report_text = generate_contest_requirements(results_data)
    
    return dict(content=report_text, filename=T[LANG]['STEP5_EXPORT_FILENAME'])