#
# pages/step2_constraints.py (Final Corrected Version)
#
from dash import dcc, html, Input, Output, State, callback
import dash_bootstrap_components as dbc
from backend.translation import T
from backend.config import DOMAIN_CONFIG # Import config to get labels

LANG = 'DE'

# Create options for the checklist using the labels from the config
MEASURES_OPTIONS = [{'label': label, 'value': i} for i, label in enumerate(DOMAIN_CONFIG['labels'])]

def layout():
    return dbc.Container([
        html.H2(T[LANG]['STEP2_TITLE']),
        dbc.Row([
            dbc.Col([
                html.H5(T[LANG]['STEP2_OBJECTIVES_HEADER']),
                dbc.Label(T[LANG]['STEP2_MEASURES_LABEL']),
                # The checklist now uses the integer index as its value
                dbc.Card(dbc.Checklist(
                    options=MEASURES_OPTIONS,
                    value=DOMAIN_CONFIG['features'], # Default to all features selected
                    id='measures-checklist',
                    switch=True,
                ), body=True),
            ], md=6),
            dbc.Col([
                html.H5(T[LANG]['STEP2_OBJECTIVE_INFO_LABEL']),
                dbc.Alert(T[LANG]['STEP2_OBJECTIVE_INFO_TEXT'], color="info")
            ], md=6),
        ]),
        dbc.Row([
            dbc.Col(dbc.Button(T[LANG]['PREV_STEP'], href='/', color="secondary")),
            dbc.Col(dbc.Button(T[LANG]['NEXT_STEP'], href='/step3', color="primary"), className="text-end")
        ], className="mt-4")
    ], fluid=True)

# This callback's only job is to save the selected measure indices to the session
@callback(
    Output('session-store', 'data', allow_duplicate=True),
    Input('measures-checklist', 'value'),
    State('session-store', 'data'),
    prevent_initial_call=True
)
def update_selected_measures(selected_measure_indices, session_data):
    session_data = session_data or {}
    # Save the list of integer indices, e.g., [0, 1, 4, 5]
    session_data['selected_features'] = selected_measure_indices
    print(f"[INFO] User selected features: {selected_measure_indices}")
    return session_data