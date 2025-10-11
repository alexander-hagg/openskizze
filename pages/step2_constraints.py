#
# pages/step2_constraints.py
#
from dash import dcc, html, Input, Output, State, callback, no_update, ALL
import dash_bootstrap_components as dbc
from backend.translation import T, translate_feature_labels
from backend.config import ENCODING_CONFIG, DOMAIN_CONFIG, QD_CONFIG
import numpy as np

def get_measures_options(lang='DE', feature_set='original'):
    """Generate measures options with translated labels based on feature set"""
    feature_indices = list(range(8))  # All 8 features
    labels = translate_feature_labels(feature_indices, lang, feature_set)
    return [{'label': label, 'value': i} for i, label in enumerate(labels)]

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
    MEASURES_OPTIONS = get_measures_options(lang)
    return dbc.Container([
        html.H2(T[lang]['STEP2_TITLE']),
        dbc.Row([
            dbc.Col(dcc.Link(dbc.Button(T[lang]['PREV_STEP'], color="secondary"), href='/')),
            dbc.Col(dcc.Link(dbc.Button(T[lang]['NEXT_STEP'], color="primary"), href='/step3'), className="text-end")
        ], className="mt-4"),

        #dbc.Card(dbc.CardBody([
        #    html.H5(T[lang]['STEP2_PRESETS_HEADER']),
        #    dbc.Select(
        #        id='presets-dropdown',
        #        options=[
        #            {'label': T[lang]['STEP2_PRESET_CUSTOM'], 'value': 'custom'},
        #            {'label': PRESETS['suburban']['name'], 'value': 'suburban'},
        #            {'label': PRESETS['dense_urban']['name'], 'value': 'dense_urban'},
        #        ],
        #        value='custom'
        #    )
        #]), className="mb-4"),

        dbc.Row([
            dbc.Col([
                html.H5(T[lang]['STEP2_HARD_CONSTRAINTS_HEADER'], className="mt-4"),
                dbc.Card(dbc.CardBody([
                    dbc.Label([T[lang]['STEP2_MAX_HEIGHT_LABEL'], html.Span(id='max-height-value', className='ms-2 text-primary fw-bold')]),
                    dcc.Slider(
                        id='max-height-constraint',
                        min=3,
                        max=30,
                        step=3,
                        value=ENCODING_CONFIG['z_length'],
                        marks={3: '3m', 10: '10m', 20: '20m', 30: '30m'},
                        tooltip={"placement": "bottom", "always_visible": False}
                    ),
                    dbc.Label([T[lang]['STEP2_MIN_DISTANCE_LABEL'], html.Span(id='min-distance-value', className='ms-2 text-primary fw-bold')], className="mt-3"),
                    dcc.Slider(
                        id='min-distance-constraint',
                        min=0,
                        max=30,
                        step=1,
                        value=0,
                        marks={0: '0m', 10: '10m', 20: '20m', 30: '30m'},
                        tooltip={"placement": "bottom", "always_visible": False}
                    ),
                ]), color="light"),
                
                html.H5(T[lang]['STEP2_TARGET_RANGES_HEADER']),
                html.P(T[lang]['STEP2_TARGET_RANGES_INFO'], className="text-muted small"),
                dcc.Loading(html.Div(id='feature-range-sliders-container')),
                
                
            ], md=6),
            dbc.Col([
                
                html.H5(T[lang].get('STEP2_OBJECTIVE_FUNCTION_HEADER', 'Optimization Criteria'), className="mt-4"),
                dbc.Card(dbc.CardBody([
                    dbc.Label(T[lang].get('STEP2_OBJECTIVE_FUNCTION_LABEL', 'Wind Flow Objective')),
                    dbc.RadioItems(
                        id='objective-function-selector',
                        options=[
                            {
                                'label': html.Div([
                                    html.Strong('Simple Wind Porosity'),
                                    html.Br(),
                                    html.Small('Counts completely open vertical passages. Best for sparse environments.', className='text-muted')
                                ]),
                                'value': 'simple_porosity'
                            },
                            {
                                'label': html.Div([
                                    html.Strong('Street Canyon Ventilation'),
                                    html.Br(),
                                    html.Small('Considers horizontal gaps, lateral flow, and partial penetration. Better for dense urban contexts.', className='text-muted')
                                ]),
                                'value': 'street_canyon'
                            }
                        ],
                        value='simple_porosity',
                        className='mt-2'
                    ),
                ]), color="light"),

                # --- Feature Set Selector ---
                html.H5(T[lang]['STEP2_FEATURE_SET_HEADER'], className="mt-4"),
                dbc.Card(dbc.CardBody([
                    dbc.Label(T[lang]['STEP2_FEATURE_SET_LABEL']),
                    dbc.RadioItems(
                        id='feature-set-selector',
                        options=[
                            {
                                'label': html.Div([
                                    html.Strong(T[lang]['STEP2_FEATURE_SET_ORIGINAL']),
                                    html.Br(),
                                    html.Small(T[lang]['STEP2_FEATURE_SET_ORIGINAL_DESC'], className='text-muted')
                                ]),
                                'value': 'original'
                            },
                            {
                                'label': html.Div([
                                    html.Strong(T[lang]['STEP2_FEATURE_SET_PLANNING']),
                                    html.Br(),
                                    html.Small(T[lang]['STEP2_FEATURE_SET_PLANNING_DESC'], className='text-muted')
                                ]),
                                'value': 'planning'
                            }
                        ],
                        value='original',
                        className='mt-2'
                    ),
                ]), color="light"),

                dbc.Label(T[lang]['STEP2_MEASURES_LABEL'], className="mt-3"),
                dbc.Card(dbc.Checklist(
                    options=MEASURES_OPTIONS,
                    value=DOMAIN_CONFIG['features'],
                    id='measures-checklist',
                    switch=True,
                ), body=True),
                
                # --- Advanced Mode Toggle ---
                dbc.Row([
                    dbc.Col([
                        dbc.Checklist(
                            options=[{"label": T[lang]['STEP2_ADVANCED_MODE'], "value": 1}],
                            value=[],
                            id="advanced-mode-toggle",
                            switch=True,
                            className="mt-3"
                        ),
                    ]),
                ]),
                
                # --- NEW: QD Hyperparameters Section (shown only in advanced mode) ---
                html.Div(id='qd-hyperparams-container', children=[
                    html.H5(T[lang]['STEP2_QD_HYPERPARAMS_HEADER'], className="mt-4"),
                    dbc.Card(dbc.CardBody([
                    dbc.Row([
                        dbc.Col([
                            dbc.Label(T[lang]['STEP2_QD_GENERATIONS_LABEL']),
                            dbc.Input(id='qd-generations-input', type="number", min=100, max=10000, step=100, value=QD_CONFIG['num_generations']),
                        ], md=6),
                        dbc.Col([
                            dbc.Label(T[lang]['STEP2_QD_EMITTERS_LABEL']),
                            dbc.Input(id='qd-emitters-input', type="number", min=1, max=20, step=1, value=QD_CONFIG['num_emitters']),
                        ], md=6),
                    ]),
                    dbc.Row([
                        dbc.Col([
                            dbc.Label(T[lang]['STEP2_QD_NICHES_LABEL']),
                            dbc.Input(id='qd-niches-input', type="number", min=3, max=20, step=1, value=QD_CONFIG['num_niches']),
                        ], md=6),
                        dbc.Col([
                            dbc.Label(T[lang]['STEP2_QD_BATCH_SIZE_LABEL']),
                            dbc.Input(id='qd-batch-size-input', type="number", min=8, max=128, step=8, value=QD_CONFIG['batch_size']),
                        ], md=6),
                    ], className="mt-2"),
                    html.Small(T[lang]['STEP2_QD_HYPERPARAMS_INFO'], className="text-muted mt-2 d-block")
                    ]), color="light")
                ], style={'display': 'none'}),  # Hidden by default
            ], md=6),
        ])
    ], fluid=True)

@callback(
    Output('measures-checklist', 'options'),
    Input('feature-set-selector', 'value'),
    State('language-store', 'data')
)
def update_measures_options(feature_set, lang):
    """Update measures checklist options when feature set changes"""
    if lang is None:
        lang = 'DE'
    return get_measures_options(lang, feature_set)

@callback(
    Output('max-height-value', 'children'),
    Input('max-height-constraint', 'value')
)
def update_max_height_display(value):
    """Update the displayed max height value"""
    if value is None:
        return ""
    return f"({value}m)"

@callback(
    Output('min-distance-value', 'children'),
    Input('min-distance-constraint', 'value')
)
def update_min_distance_display(value):
    """Update the displayed min distance value"""
    if value is None:
        return ""
    return f"({value}m)"

@callback(
    Output('measures-checklist', 'value'),
    Output('feature-range-sliders-container', 'children', allow_duplicate=True),
    Input('presets-dropdown', 'value'),
    State('language-store', 'data'),
    prevent_initial_call=True
)
def apply_preset(preset_key, lang):
    """Apply preset feature selections - uses default ranges, not preset-specific ranges"""
    from backend.units import get_unit_label
    
    if preset_key == 'custom':
        return no_update, no_update
    
    if lang is None: lang = 'DE'
    presets = get_presets(lang)
    preset = presets[preset_key]
    selected_indices = preset['features']
    
    # Re-generate sliders with default (physical unit) ranges from config
    # Note: Preset-specific ranges are intentionally not applied here anymore
    # as they were in old normalized format. Users can adjust after selecting preset.
    sliders = []
    num_buildings_original_index = 3  # The original index for 'Anzahl der Gebäude'
    
    # Get translated labels for sorted indices
    sorted_indices = sorted(selected_indices)
    labels = translate_feature_labels(sorted_indices, lang)
    
    for i, index in enumerate(sorted_indices):
        label = labels[i]
        unit = get_unit_label(index, lang)
        label_with_unit = f"{label} ({unit})" if unit else label
        
        # Use default ranges from config (these are now in physical units after our changes)
        default_range = DOMAIN_CONFIG['feat_ranges'][index]
        min_val, max_val = default_range[0], default_range[1]
        
        # Create slider based on feature type
        if index == num_buildings_original_index:  # Number of buildings
            min_v = int(np.floor(min_val))
            max_v = int(np.ceil(max_val))
            if min_v == max_v: max_v += 1
            slider_div = html.Div([
                dbc.Label(label_with_unit),
                dcc.RangeSlider(
                    id={'type': 'feature-range-slider', 'index': index},
                    min=min_v, max=max_v, step=1, value=[min_v, max_v],
                    tooltip={"placement": "bottom", "always_visible": True}, marks=None
                )
            ], className="mb-3")
        elif index in [6, 7]:  # Building Mass X/Y - normalized
            slider_div = html.Div([
                dbc.Label(label_with_unit),
                dcc.RangeSlider(
                    id={'type': 'feature-range-slider', 'index': index},
                    min=0.0, max=1.0, step=0.01, value=[0.0, 1.0],
                    tooltip={"placement": "bottom", "always_visible": True}, marks=None
                )
            ], className="mb-3")
        else:  # Physical units (m, m²)
            min_v = round(min_val, 1)
            max_v = round(max_val, 1)
            if min_v == max_v: max_v = min_v + 1.0
            
            # Determine step size
            if max_v - min_v > 100:
                step = 1.0
            elif max_v - min_v > 10:
                step = 0.5
            else:
                step = 0.1
                
            slider_div = html.Div([
                dbc.Label(label_with_unit),
                dcc.RangeSlider(
                    id={'type': 'feature-range-slider', 'index': index},
                    min=min_v, max=max_v, step=step, value=[min_v, max_v],
                    tooltip={"placement": "bottom", "always_visible": True}, marks=None
                )
            ], className="mb-3")
        
        sliders.append(slider_div)
        
    return selected_indices, sliders


@callback(
    Output('feature-range-sliders-container', 'children'),
    Input('measures-checklist', 'value'),
    Input('url', 'pathname'),
    Input('max-height-constraint', 'value'),
    Input('min-distance-constraint', 'value'),
    State('language-store', 'data'),
    State('session-store', 'data'),
    prevent_initial_call=True
)
def create_range_sliders(selected_indices, pathname, max_height_input, min_distance_input, lang, session_data):
    from backend.units import calculate_dynamic_ranges_physical, get_unit_label
    import geopandas as gpd
    import math
    from dash import ctx
    
    if lang is None: lang = 'DE'
    
    # If triggered by URL change, get selected_indices from session_data
    if ctx.triggered_id == 'url':
        if pathname != '/step2':
            return no_update
        if session_data and 'selected_features' in session_data:
            selected_indices = session_data['selected_features']
        else:
            return no_update
    
    if not selected_indices:
        return dbc.Alert(T[lang]['STEP2_NO_FEATURES_SELECTED'] if 'STEP2_NO_FEATURES_SELECTED' in T[lang] else "Bitte mindestens ein Merkmal auswählen.", color="info")

    sliders = []
    num_buildings_original_index = 3 # The original index for 'Anzahl der Gebäude'

    # Get translated labels for sorted indices
    sorted_indices = sorted(selected_indices)
    labels = translate_feature_labels(sorted_indices, lang)
    
    # Try to calculate dynamic ranges based on selected site from Step 1
    dynamic_ranges = None
    if session_data and 'site_polygon' in session_data:
        try:
            # Recreate the buildable mask to calculate proper ranges
            from backend.config import ENCODING_CONFIG
            from shapely.geometry import Point
            user_polygon_geojson = session_data['site_polygon']
            gdf_user_poly = gpd.GeoDataFrame.from_features(user_polygon_geojson, crs="EPSG:4326")
            gdf_user_poly_native = gdf_user_poly.to_crs("EPSG:25832")
            min_x, min_y, max_x, max_y = gdf_user_poly_native.total_bounds
            
            width = max_x - min_x
            height = max_y - min_y
            square_size = max(width, height)
            border = square_size * (DOMAIN_CONFIG['environment_border_size'] - 1.0) / 2.0
            grid_side_length = square_size + (2 * border)
            
            pixel_size = DOMAIN_CONFIG['pixel_size_in_meters']
            res = math.ceil(grid_side_length / pixel_size)
            
            # Calculate grid bounds (centered on parcel)
            center_x = (min_x + max_x) / 2
            center_y = (min_y + max_y) / 2
            grid_min_x = center_x - grid_side_length / 2
            grid_max_x = center_x + grid_side_length / 2
            grid_min_y = center_y - grid_side_length / 2
            grid_max_y = center_y + grid_side_length / 2
            
            # Create precise buildable mask using spatial join (same as optimization_process.py)
            x = np.linspace(grid_min_x, grid_max_x, res)
            y = np.linspace(grid_min_y, grid_max_y, res)
            xv, yv = np.meshgrid(x, y)
            points = [Point(px, py) for px, py in zip(xv.flatten(), yv.flatten())]
            gdf_points = gpd.GeoDataFrame(geometry=points, crs="EPSG:25832")
            
            joined = gpd.sjoin(gdf_points, gdf_user_poly_native, how="inner", predicate="within")
            buildable_mask = np.zeros((res, res), dtype=bool)
            indices = joined.index.to_numpy()
            rows, cols = np.unravel_index(indices, (res, res))
            buildable_mask[rows, cols] = True
            
            # Count actual buildable pixels from precise mask
            buildable_pixels = np.sum(buildable_mask)
            
            # Get constraints from inputs (already in meters)
            max_height_meters = max_height_input if max_height_input else ENCODING_CONFIG['z_length']
            min_distance_meters = min_distance_input if min_distance_input else 0.0
            
            # Calculate dynamic ranges in physical units, respecting hard constraints
            dynamic_ranges = calculate_dynamic_ranges_physical(buildable_mask, max_height_meters, min_distance_meters)
        except Exception as e:
            print(f"Warning: Could not calculate dynamic ranges: {e}")
            dynamic_ranges = None

    # Get saved feature ranges from session if available
    saved_ranges = session_data.get('feature_ranges', {}) if session_data else {}
    
    # Debug: Print what we're restoring
    if saved_ranges:
        print(f"[DEBUG] Restoring feature ranges from session: {saved_ranges}")
    else:
        print(f"[DEBUG] No saved feature ranges found in session_data")
    
    for i, index in enumerate(sorted_indices):
        label = labels[i]
        unit = get_unit_label(index, lang)
        
        # Use dynamic ranges if available, otherwise fall back to default
        if dynamic_ranges is not None:
            min_val, max_val = dynamic_ranges[index]
        else:
            default_range = DOMAIN_CONFIG['feat_ranges'][index]
            min_val, max_val = default_range[0], default_range[1]
        
        # Add unit to label
        label_with_unit = f"{label} ({unit})" if unit else label
        
        # Check if user has previously set a custom range for this feature
        user_range = saved_ranges.get(str(index), None)
        
        slider_div = None
        # Integer sliders for count-based features
        if index == num_buildings_original_index:  # Number of Buildings
            min_v = int(np.floor(min_val))
            max_v = int(np.ceil(max_val))
            if min_v == max_v: max_v += 1
            # Use saved value if available, otherwise use full range
            slider_value = user_range if user_range else [min_v, max_v]
            slider_div = html.Div([
                dbc.Label(label_with_unit),
                dcc.RangeSlider(
                    id={'type': 'feature-range-slider', 'index': index},
                    min=min_v, max=max_v, step=1, value=slider_value,
                    tooltip={"placement": "bottom", "always_visible": True}, marks=None
                )
            ], className="mb-3")
        # Normalized sliders for position features (0-1)
        elif index in [6, 7]:  # Building Mass X/Y
            min_v = 0.0
            max_v = 1.0
            slider_value = user_range if user_range else [0.0, 1.0]
            slider_div = html.Div([
                dbc.Label(label_with_unit),
                dcc.RangeSlider(
                    id={'type': 'feature-range-slider', 'index': index},
                    min=min_v, max=max_v, step=0.01, value=slider_value,
                    tooltip={"placement": "bottom", "always_visible": True}, marks=None
                )
            ], className="mb-3")
        # Physical unit sliders for area/distance/height features
        else:
            min_v = round(min_val, 1)
            max_v = round(max_val, 1)
            if min_v == max_v: max_v = min_v + 1.0
            
            # Determine appropriate step size based on magnitude
            if max_v - min_v > 100:
                step = 1.0  # Large ranges (areas, distances)
            elif max_v - min_v > 10:
                step = 0.5  # Medium ranges
            else:
                step = 0.1  # Small ranges (heights)
            
            # Use saved value if available, otherwise use full range
            slider_value = user_range if user_range else [min_v, max_v]
            slider_div = html.Div([
                dbc.Label(label_with_unit),
                dcc.RangeSlider(
                    id={'type': 'feature-range-slider', 'index': index},
                    min=min_v, max=max_v, step=step, value=slider_value,
                    tooltip={"placement": "bottom", "always_visible": True}, marks=None
                )
            ], className="mb-3")
        
        sliders.append(slider_div)
        
    return sliders

# Callback to toggle advanced mode visibility
@callback(
    Output('qd-hyperparams-container', 'style'),
    Input('advanced-mode-toggle', 'value'),
)
def toggle_advanced_mode(advanced_mode):
    if advanced_mode and 1 in advanced_mode:
        return {'display': 'block'}
    return {'display': 'none'}

# Callback to restore settings from loaded session data
@callback(
    Output('measures-checklist', 'value', allow_duplicate=True),
    Output('max-height-constraint', 'value', allow_duplicate=True),
    Output('min-distance-constraint', 'value', allow_duplicate=True),
    Output('qd-generations-input', 'value', allow_duplicate=True),
    Output('qd-emitters-input', 'value', allow_duplicate=True),
    Output('qd-niches-input', 'value', allow_duplicate=True),
    Output('qd-batch-size-input', 'value', allow_duplicate=True),
    Input('session-store', 'data'),
    Input('url', 'pathname'),
    prevent_initial_call=True
)
def restore_step2_from_session(session_data, pathname):
    if pathname != '/step2' or not session_data:
        return no_update, no_update, no_update, no_update, no_update, no_update, no_update
    
    selected_features = session_data.get('selected_features')
    hard_constraints = session_data.get('hard_constraints', {})
    qd_params = session_data.get('qd_hyperparams', {})
    
    max_height = hard_constraints.get('max_height', ENCODING_CONFIG['z_length'])  # Already in meters
    min_distance = hard_constraints.get('min_distance', 0)
    
    qd_generations = qd_params.get('num_generations', QD_CONFIG['num_generations'])
    qd_emitters = qd_params.get('num_emitters', QD_CONFIG['num_emitters'])
    qd_niches = qd_params.get('num_niches', QD_CONFIG['num_niches'])
    qd_batch_size = qd_params.get('batch_size', QD_CONFIG['batch_size'])
    
    if selected_features is not None:
        return selected_features, int(max_height), min_distance, qd_generations, qd_emitters, qd_niches, qd_batch_size
    
    return no_update, int(max_height), min_distance, qd_generations, qd_emitters, qd_niches, qd_batch_size

# --- UPDATED: Callback to save selections, ranges, constraints, QD hyperparameters, objective function, and feature set to the session ---
@callback(
    Output('session-store', 'data', allow_duplicate=True),
    Input('measures-checklist', 'value'),
    Input({'type': 'feature-range-slider', 'index': ALL}, 'value'),
    Input('max-height-constraint', 'value'),
    Input('min-distance-constraint', 'value'),
    Input('qd-generations-input', 'value'),
    Input('qd-emitters-input', 'value'),
    Input('qd-niches-input', 'value'),
    Input('qd-batch-size-input', 'value'),
    Input('objective-function-selector', 'value'),
    Input('feature-set-selector', 'value'),
    State({'type': 'feature-range-slider', 'index': ALL}, 'id'),
    State('session-store', 'data'),
    prevent_initial_call=True
)
def update_session_with_features_and_ranges(
    selected_indices, slider_values, max_height, min_distance,
    qd_generations, qd_emitters, qd_niches, qd_batch_size,
    objective_function, feature_set,
    slider_ids, session_data
):
    session_data = session_data or {}
    
    # Save feature selections
    session_data['selected_features'] = selected_indices
    
    # Only update feature_ranges if we have valid slider data
    # This prevents overwriting saved ranges when sliders are being recreated
    if slider_ids and slider_values:
        new_feature_ranges = {
            str(s_id['index']): s_val for s_id, s_val in zip(slider_ids, slider_values)
        }
        # Only save if we have actual data (not empty dict)
        if new_feature_ranges:
            session_data['feature_ranges'] = new_feature_ranges

    # Save hard constraints (max_height is already in meters, no conversion needed)
    # Preserve existing values if new values are None
    existing_constraints = session_data.get('hard_constraints', {})
    session_data['hard_constraints'] = {
        'max_height': max_height if max_height is not None else existing_constraints.get('max_height', ENCODING_CONFIG['z_length']),
        'min_distance': min_distance if min_distance is not None else existing_constraints.get('min_distance', 0)
    }
    
    # Save QD hyperparameters - preserve existing values if new values are None
    existing_qd = session_data.get('qd_hyperparams', {})
    session_data['qd_hyperparams'] = {
        'num_generations': qd_generations if qd_generations is not None else existing_qd.get('num_generations', QD_CONFIG['num_generations']),
        'num_emitters': qd_emitters if qd_emitters is not None else existing_qd.get('num_emitters', QD_CONFIG['num_emitters']),
        'num_niches': qd_niches if qd_niches is not None else existing_qd.get('num_niches', QD_CONFIG['num_niches']),
        'batch_size': qd_batch_size if qd_batch_size is not None else existing_qd.get('batch_size', QD_CONFIG['batch_size']),
    }
    
    # Save objective function selection
    session_data['objective_function'] = objective_function if objective_function else 'simple_porosity'
    
    # Save feature set selection
    session_data['feature_set'] = feature_set if feature_set else 'original'
    
    return session_data