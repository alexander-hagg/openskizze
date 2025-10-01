#
# pages/step2_constraints.py
#
from dash import dcc, html, Input, Output, State, callback, no_update, ALL
import dash_bootstrap_components as dbc
from backend.translation import T
from backend.config import ENCODING_CONFIG, DOMAIN_CONFIG
import numpy as np

MEASURES_OPTIONS = [{'label': label, 'value': i} for i, label in enumerate(DOMAIN_CONFIG['labels'])]

def get_presets(lang):
    return {
        "suburban": {
            "name": T[lang]['STEP2_PRESET_SUBURBAN'],
            "features": [0, 1, 3, 4, 5],
            "ranges": {
                '0': [0.1, 0.4],
                '1': [1, 3],
                '3': [5, 20],
                '4': [0.2, 0.8],
                '5': [0.3, 1.5],
            }
        },
        "dense_urban": {
            "name": T[lang]['STEP2_PRESET_DENSE'],
            "features": [0, 1, 2, 3, 5, 6, 7],
            "ranges": {
                '0': [0.4, 0.8],
                '1': [3, 8],
                '2': [1, 5],
                '3': [10, 50],
                '5': [1.5, 5.0],
            }
        }
    }

def layout(lang='DE'):
    PRESETS = get_presets(lang)
    return dbc.Container([
        html.H2(T[lang]['STEP2_TITLE']),
        dbc.Row([
            dbc.Col(dbc.Button(T[lang]['PREV_STEP'], href='/', color="secondary")),
            dbc.Col(dbc.Button(T[lang]['NEXT_STEP'], href='/step3', color="primary"), className="text-end")
        ], className="mt-4"),

        dbc.Card(dbc.CardBody([
            html.H5(T[lang]['STEP2_PRESETS_HEADER']),
            dbc.Select(
                id='presets-dropdown',
                options=[
                    {'label': T[lang]['STEP2_PRESET_CUSTOM'], 'value': 'custom'},
                    {'label': PRESETS['suburban']['name'], 'value': 'suburban'},
                    {'label': PRESETS['dense_urban']['name'], 'value': 'dense_urban'},
                ],
                value='custom'
            )
        ]), className="mb-4"),

        dbc.Row([
            dbc.Col([
                html.H5(T[lang]['STEP2_OBJECTIVES_HEADER']),
                dbc.Label(T[lang]['STEP2_MEASURES_LABEL']),
                dbc.Card(dbc.Checklist(
                    options=MEASURES_OPTIONS,
                    value=DOMAIN_CONFIG['features'],
                    id='measures-checklist',
                    switch=True,
                ), body=True)
            ], md=6),
            dbc.Col([
                html.H5(T[lang]['STEP2_OBJECTIVE_INFO_LABEL']),
                dbc.Alert(T[lang]['STEP2_OBJECTIVE_INFO_TEXT'], color="info"),
                html.H5(T[lang]['STEP2_TARGET_RANGES_HEADER']),
                html.P(T[lang]['STEP2_TARGET_RANGES_INFO'], className="text-muted small"),
                dcc.Loading(html.Div(id='feature-range-sliders-container')),
                # --- NEW: Hard Constraints Section ---
                html.H5(T[lang]['STEP2_HARD_CONSTRAINTS_HEADER'], className="mt-4"),
                dbc.Card(dbc.CardBody([
                    dbc.Label(T[lang]['STEP2_MAX_HEIGHT_LABEL']),
                    dbc.Input(id='max-height-constraint', type="number", placeholder=T[lang]['STEP2_MAX_HEIGHT_PLACEHOLDER'], min=1, step=1, value=ENCODING_CONFIG['z_length']),
                    dbc.Label(T[lang]['STEP2_MIN_DISTANCE_LABEL'], className="mt-2"),
                    dbc.Input(id='min-distance-constraint', type="number", placeholder=T[lang]['STEP2_MIN_DISTANCE_PLACEHOLDER'], min=0, step=1, value=0),
                ]), color="light")
            ], md=6),
        ])
    ], fluid=True)

@callback(
    Output('measures-checklist', 'value'),
    Output('feature-range-sliders-container', 'children', allow_duplicate=True),
    Input('presets-dropdown', 'value'),
    State('language-store', 'data'),
    prevent_initial_call=True
)
def apply_preset(preset_key, lang):
    if preset_key == 'custom':
        return no_update, no_update
    
    if lang is None: lang = 'DE'
    presets = get_presets(lang)
    preset = presets[preset_key]
    selected_indices = preset['features']
    
    # Re-generate sliders with preset values
    sliders = []
    num_buildings_original_index = 3  # The original index for 'Anzahl der Gebäude'
    
    for index in sorted(selected_indices):
        label = DOMAIN_CONFIG['labels'][index]
        # Use preset range if available, otherwise use default from config
        preset_range = preset['ranges'].get(str(index), DOMAIN_CONFIG['feat_ranges'][index])
        min_val, max_val = preset_range[0], preset_range[1]
        
        # Create slider based on whether it's the number of buildings (integer) or continuous
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
        
    return selected_indices, sliders


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

# Callback to restore settings from loaded session data
@callback(
    Output('measures-checklist', 'value', allow_duplicate=True),
    Output('max-height-constraint', 'value', allow_duplicate=True),
    Output('min-distance-constraint', 'value', allow_duplicate=True),
    Input('session-store', 'data'),
    Input('url', 'pathname'),
    prevent_initial_call=True
)
def restore_step2_from_session(session_data, pathname):
    if pathname != '/step2' or not session_data:
        return no_update, no_update, no_update
    
    selected_features = session_data.get('selected_features')
    hard_constraints = session_data.get('hard_constraints', {})
    
    max_height = hard_constraints.get('max_height', ENCODING_CONFIG['z_length'] * 3) / 3
    min_distance = hard_constraints.get('min_distance', 0)
    
    if selected_features is not None:
        return selected_features, int(max_height), min_distance
    
    return no_update, int(max_height), min_distance

# --- UPDATED: Callback to save both selections and ranges to the session ---
@callback(
    Output('session-store', 'data', allow_duplicate=True),
    Input('measures-checklist', 'value'),
    Input({'type': 'feature-range-slider', 'index': ALL}, 'value'),
    Input('max-height-constraint', 'value'), # New Input
    Input('min-distance-constraint', 'value'), # New Input
    State({'type': 'feature-range-slider', 'index': ALL}, 'id'),
    State('session-store', 'data'),
    prevent_initial_call=True
)
def update_session_with_features_and_ranges(
    selected_indices, slider_values, max_height, min_distance, 
    slider_ids, session_data
):
    session_data = session_data or {}
    
    # Save feature selections and ranges (unchanged)
    session_data['selected_features'] = selected_indices
    session_data['feature_ranges'] = {
        str(s_id['index']): s_val for s_id, s_val in zip(slider_ids, slider_values)
    }

    # --- NEW: Save hard constraints ---
    session_data['hard_constraints'] = {
        'max_height': 3*max_height,
        'min_distance': min_distance
    }
    
    print(f"[INFO] User defined hard constraints: {session_data['hard_constraints']}")
    
    return session_data