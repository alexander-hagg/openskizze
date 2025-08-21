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
                html.H5("Zielbereiche für Merkmale festlegen"),
                html.P("Definieren Sie die Wertebereiche, in denen der Optimierer nach diversen Lösungen suchen soll.", className="text-muted small"),
                dcc.Loading(html.Div(id='feature-range-sliders-container'))

            ], md=6),
        ]),
        dbc.Row([
            dbc.Col(dbc.Button(T[LANG]['PREV_STEP'], href='/', color="secondary")),
            dbc.Col(dbc.Button(T[LANG]['NEXT_STEP'], href='/step3', color="primary"), className="text-end")
        ], className="mt-4")
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
    
    return session_data