#
# pages/step2_constraints.py
#
from dash import dcc, html, Input, Output, State, callback, no_update, ALL
import dash_bootstrap_components as dbc
from backend.translation import T, translate_feature_labels
from backend.config import ENCODING_CONFIG, DOMAIN_CONFIG, QD_CONFIG
import numpy as np

def get_measures_options(lang='DE'):
    """Generate measures options with translated labels based on consolidated feature set"""
    feature_indices = list(range(8))  # All 8 features
    labels = translate_feature_labels(feature_indices, lang, 'consolidated')
    return [{'label': label, 'value': i} for i, label in enumerate(labels)]

def get_presets(lang):
    return {
        "suburban": {
            "name": T[lang]['STEP2_PRESET_SUBURBAN'],
            "features": [0, 1, 2, 4, 5, 7], # GRZ, GFZ, Height, Dist, Count, Park Factor
            "ranges": {
                '0': [0.1, 0.4],
                '1': [0.2, 0.8],
                '2': [3, 12],
                '4': [10, 30],
                '5': [2, 8],
                '7': [10, 40],
            }
        },
        "dense_urban": {
            "name": T[lang]['STEP2_PRESET_DENSE'],
            "features": [0, 1, 2, 4, 6, 7], # GRZ, GFZ, Height, Dist, Compactness, Park Factor
            "ranges": {
                '0': [0.4, 0.8],
                '1': [1.0, 3.0],
                '2': [12, 24],
                '4': [5, 15],
                '6': [0.2, 0.8],
                '7': [5, 20],
            }
        }
    }

def layout(lang='DE'):
    from backend.translation import create_breadcrumb
    PRESETS = get_presets(lang)
    MEASURES_OPTIONS = get_measures_options(lang)
    return dbc.Container([
        create_breadcrumb(2, lang),
        html.Div([
            html.H2(T[lang]['STEP2_TITLE'], className="d-inline-block mb-0"),
            dbc.Button(
                [html.I(className="bi bi-arrow-counterclockwise me-2"), T[lang]['STEP2_RESET_BUTTON']],
                id='reset-all-button',
                color="secondary",
                outline=True,
                size="sm",
                className="float-end"
            ),
        ], className="mb-3 clearfix"),
        
        dbc.Row([
            dbc.Col([
                html.H5(T[lang]['STEP2_HARD_CONSTRAINTS_HEADER'], className="mt-4"),
                dbc.Card(dbc.CardBody([
                    dbc.Label([T[lang]['STEP2_MAX_HEIGHT_LABEL'], html.Span(id='max-height-value', className='ms-2 text-primary fw-bold')]),
                    dcc.Slider(
                        id='max-height-constraint',
                        min=3,
                        max=60,
                        step=3,
                        value=int(ENCODING_CONFIG['max_building_floors'] * ENCODING_CONFIG['meters_per_floor']),
                        marks={3: '3m', 12: '12m', 24: '24m', 36: '36m', 48: '48m', 60: '60m'},
                        tooltip={"placement": "bottom", "always_visible": False}
                    ),
                    dbc.Label([T[lang]['STEP2_MIN_DISTANCE_LABEL'], html.Span(id='min-distance-value', className='ms-2 text-primary fw-bold')], className="mt-3"),
                    dcc.Slider(
                        id='min-distance-constraint',
                        min=0,
                        max=30,
                        step=1,
                        value=5,
                        marks={0: '0m', 10: '10m', 20: '20m', 30: '30m'},
                        tooltip={"placement": "bottom", "always_visible": False}
                    ),
                ]), color="light"),
                
                html.H5(T[lang]['STEP2_TARGET_RANGES_HEADER']),
                html.P(T[lang]['STEP2_TARGET_RANGES_INFO'], className="text-muted small"),
                dcc.Loading(html.Div(id='feature-range-sliders-container')),
                
                
            ], md=6),
            dbc.Col([
                
                # --- Feature Set Selector REMOVED (Consolidated Set is now standard) ---
                # --- Objective Function Selector REMOVED (Street Canyon is now standard) ---

                dbc.Label(T[lang]['STEP2_MEASURES_LABEL'], className="mt-3"),
                dbc.Card(dbc.Checklist(
                    options=MEASURES_OPTIONS,
                    value=DOMAIN_CONFIG['features'],
                    id='measures-checklist',
                    switch=True,
                ), body=True),
                
                # --- Evaluation Method Selector (always visible) ---
                html.Div(id='surrogate-model-container', children=[
                    html.H5(T[lang]['STEP2_SURROGATE_MODEL_HEADER'], className="mt-4"),
                    dbc.Card(dbc.CardBody([
                        dbc.Label(T[lang]['STEP2_MODEL_TYPE_LABEL']),
                        dbc.RadioItems(
                            id='model-type-selector',
                            options=[
                                {'label': T[lang]['STEP2_MODEL_SIMPLE_POROSITY'], 'value': 'simple_porosity'},
                                {'label': T[lang]['STEP2_MODEL_STREET_CANYON'], 'value': 'street_canyon'},
                                {'label': T[lang]['STEP2_MODEL_SVGP'], 'value': 'svgp'},
                                {'label': T[lang]['STEP2_MODEL_UNET'], 'value': 'unet'},
                                {'label': T[lang]['STEP2_MODEL_HYBRID'], 'value': 'hybrid'},
                            ],
                            value='street_canyon',
                            inline=False,
                        ),
                        html.Div(id='model-info-card', className="mt-3"),
                        html.Div(id='ucb-lambda-container', children=[
                            dbc.Label([T[lang]['STEP2_UCB_LAMBDA_LABEL'], html.Span(id='ucb-lambda-value', className='ms-2 text-primary fw-bold')], className="mt-3"),
                            dcc.Slider(
                                id='ucb-lambda-slider',
                                min=0.0,
                                max=3.0,
                                step=0.1,
                                value=1.0,
                                marks={0: '0', 1: '1', 2: '2', 3: '3'},
                                tooltip={"placement": "bottom", "always_visible": False}
                            ),
                            html.Small(T[lang]['STEP2_UCB_LAMBDA_INFO'], className="text-muted mt-1 d-block")
                        ], style={'display': 'none'}),
                    ]), color="light")
                ]),  # Always visible now
                
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
                
                # --- QD Hyperparameters Section (shown only in advanced mode) ---
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
    Output('measures-checklist', 'value'),
    Output('feature-range-sliders-container', 'children', allow_duplicate=True),
    Input('presets-dropdown', 'value'),
    State('language-store', 'data'),
    State('session-store', 'data'),
    prevent_initial_call=True
)
def apply_preset(preset_key, lang, session_data):
    """Apply preset feature selections - uses default ranges, not preset-specific ranges"""
    from backend.units import get_unit_label
    
    if preset_key == 'custom':
        return no_update, no_update
    
    if lang is None: lang = 'DE'
    
    # Always use consolidated feature set
    feature_set = 'consolidated'
    
    presets = get_presets(lang)
    preset = presets[preset_key]
    selected_indices = preset['features']
    
    # Re-generate sliders with default (physical unit) ranges from config
    sliders = []
    num_buildings_index = 5  # Consolidated index for 'Number of Buildings'
    
    # Get translated labels for sorted indices
    sorted_indices = sorted(selected_indices)
    labels = translate_feature_labels(sorted_indices, lang, feature_set)
    
    for i, index in enumerate(sorted_indices):
        label = labels[i]
        unit = get_unit_label(index, lang, feature_set)
        label_with_unit = f"{label} ({unit})" if unit else label
        
        # Use default ranges from config
        default_range = DOMAIN_CONFIG['feat_ranges'][index]
        min_val, max_val = default_range[0], default_range[1]
        
        # Create slider based on feature type
        if index == num_buildings_index:  # Number of buildings
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
        elif index in [0, 1, 6]:  # GRZ, GFZ, Compactness (ratios/small values)
            # Determine step size
            step = 0.01 if index == 0 else 0.1
            slider_div = html.Div([
                dbc.Label(label_with_unit),
                dcc.RangeSlider(
                    id={'type': 'feature-range-slider', 'index': index},
                    min=min_val, max=max_val, step=step, value=[min_val, max_val],
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
    from backend.optimization_process import _calculate_dynamic_feat_ranges
    import geopandas as gpd
    import math
    from dash import ctx
    
    if lang is None: lang = 'DE'
    
    # Always use consolidated feature set
    feature_set = 'consolidated'
    
    # Determine feature_set with correct priority:
    # The restoration callback will fire shortly after URL navigation and set the correct value
    # So on URL trigger, we should skip if session has data (let restoration handle it)
    if ctx.triggered_id == 'url':
        # If we have session data with a feature_set, skip this URL trigger
        # The restore_step2_from_session callback will fire next and trigger us again with correct values
        if session_data and 'feature_set' in session_data:
            return no_update
        # No session data - use defaults
        if pathname == '/step2':
            return dbc.Alert(T[lang]['STEP2_NO_FEATURES_SELECTED'] if 'STEP2_NO_FEATURES_SELECTED' in T[lang] else "Bitte mindestens ein Merkmal auswählen.", color="info")
        return no_update
    else:
        # Also get selected features from session if available
        if session_data and 'selected_features' in session_data and not selected_indices:
            selected_indices = session_data['selected_features']
    
    if not selected_indices:
        return dbc.Alert(T[lang]['STEP2_NO_FEATURES_SELECTED'] if 'STEP2_NO_FEATURES_SELECTED' in T[lang] else "Bitte mindestens ein Merkmal auswählen.", color="info")

    sliders = []
    # Number of Buildings index depends on feature set
    num_buildings_index = 5  # Consolidated index

    # Get translated labels for sorted indices with correct feature set
    sorted_indices = sorted(selected_indices)
    labels = translate_feature_labels(sorted_indices, lang, feature_set)
    
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
            default_max_height_meters = int(ENCODING_CONFIG['max_building_floors'] * ENCODING_CONFIG['meters_per_floor'])            
            max_height_meters = max_height_input if max_height_input else default_max_height_meters
            min_distance_meters = min_distance_input if min_distance_input else 0.0
            
            # Calculate dynamic ranges based on feature set
            dynamic_ranges, _ = _calculate_dynamic_feat_ranges(buildable_mask, max_height_meters, min_distance_meters, feature_set='consolidated')
        except Exception as e:
            print(f"Warning: Could not calculate dynamic ranges: {e}")
            dynamic_ranges = None

    # Get saved feature ranges from session if available
    # Use namespaced ranges for the current feature set
    saved_ranges = {}
    ranges_key = f'feature_ranges_{feature_set}'
    if session_data and ranges_key in session_data:
        saved_ranges = session_data[ranges_key]
    
    for i, index in enumerate(sorted_indices):
        label = labels[i]
        unit = get_unit_label(index, lang, feature_set)
        
        # ALWAYS use config defaults for slider min/max limits
        default_range = DOMAIN_CONFIG['feat_ranges'][index]
        min_val, max_val = default_range[0], default_range[1]
        
        # Add unit to label
        label_with_unit = f"{label} ({unit})" if unit else label
        
        # Check if user has previously set a custom range for this feature
        user_range = saved_ranges.get(str(index), None)
        
        # GRZ and GFZ (indices 0 and 1) should NEVER use dynamic ranges
        is_percentage_ratio = (index in [0, 1])
        
        # If no saved range exists, use dynamic range as initial value suggestion (if available)
        if user_range is None and dynamic_ranges is not None and not is_percentage_ratio:
            dyn_min, dyn_max = dynamic_ranges[index]
            # Use dynamic range as suggested initial value, but keep it within config limits
            suggested_range = [max(min_val, dyn_min), min(max_val, dyn_max)]
            user_range = suggested_range
        
        slider_div = None
        # Integer sliders for count-based features
        if index == num_buildings_index:  # Number of Buildings
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
        # Normalized sliders for position features (0-1) or small ratios
        elif index in [0, 1, 6]: # GRZ, GFZ, Compactness
            step = 0.01 if index == 0 else 0.1
            slider_value = user_range if user_range else [min_val, max_val]
            slider_div = html.Div([
                dbc.Label(label_with_unit),
                dcc.RangeSlider(
                    id={'type': 'feature-range-slider', 'index': index},
                    min=min_val, max=max_val, step=step, value=slider_value,
                    tooltip={"placement": "bottom", "always_visible": True}, marks=None
                )
            ], className="mb-3")
        # Physical unit sliders for area/distance/height features
        else:
            min_v = round(min_val, 1)
            max_v = round(max_val, 1)
            if min_v == max_v: max_v = min_v + 1.0
            
            # OVERRIDE: For height features, use max_height_constraint as the max value
            # Index 2 (Avg Height)
            is_height_feature = (index == 2)
            
            if is_height_feature and max_height_input:
                max_v = float(max_height_input)
                # Ensure min_v doesn't exceed max_v
                if min_v >= max_v:
                    min_v = 0.0
                # Ensure saved slider value doesn't exceed new max
                if user_range and user_range[1] > max_v:
                    user_range = [user_range[0], max_v]
                    if user_range[0] > max_v:
                        user_range[0] = 0.0
            
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

# Callback to toggle advanced mode visibility (only QD hyperparams now, model is always visible)
@callback(
    Output('qd-hyperparams-container', 'style'),
    Input('advanced-mode-toggle', 'value')
)
def toggle_advanced_mode(advanced_mode):
    if advanced_mode and 1 in advanced_mode:
        return {'display': 'block'}
    return {'display': 'none'}

@callback(
    Output('model-info-card', 'children'),
    Output('ucb-lambda-container', 'style'),
    Input('model-type-selector', 'value'),
    State('language-store', 'data'),
    State('session-store', 'data')
)
def update_model_info_card(model_type, lang, session_data):
    """Update model info card and toggle UCB lambda slider"""
    from backend.surrogate_evaluator import get_available_models, get_parcel_size_bins_from_session
    
    print("\n[STEP2 DEBUG] update_model_info_card callback triggered")
    print(f"  - model_type: {model_type}")
    print(f"  - lang: {lang}")
    print(f"  - session_data keys: {list(session_data.keys()) if session_data else 'None'}")
    
    if lang is None:
        lang = 'DE'
    
    # Check model availability for current parcel
    parcel_size_bins = None
    if session_data:
        parcel_size_bins = get_parcel_size_bins_from_session(session_data)
        print(f"  - parcel_size_bins from session: {parcel_size_bins}")
    
    # Always check model availability (SVGP works for all sizes, will report if found)
    available_models = get_available_models(parcel_size_bins)
    print(f"  - available_models: {available_models}")
    
    # Create info card based on model type
    if model_type == 'simple_porosity':
        card = dbc.Alert([
            html.H6(T[lang]['MODEL_INFO_SIMPLE_POROSITY_TITLE'], className="alert-heading"),
            html.P(T[lang]['MODEL_INFO_SIMPLE_POROSITY_DESC'])
        ], color="info", className="mb-0")
        ucb_style = {'display': 'none'}
    
    elif model_type == 'street_canyon':
        card = dbc.Alert([
            html.H6(T[lang]['MODEL_INFO_STREET_CANYON_TITLE'], className="alert-heading"),
            html.P(T[lang]['MODEL_INFO_STREET_CANYON_DESC'])
        ], color="info", className="mb-0")
        ucb_style = {'display': 'none'}
    
    elif model_type == 'svgp':
        is_available = available_models.get('svgp', False)
        if is_available:
            card = dbc.Alert([
                html.H6(T[lang]['MODEL_INFO_SVGP_TITLE'], className="alert-heading"),
                html.P(T[lang]['MODEL_INFO_SVGP_DESC']),
                html.Small(T[lang]['MODEL_INFO_SVGP_SPEED'], className="text-muted")
            ], color="success", className="mb-0")
        else:
            card = dbc.Alert([
                html.H6(T[lang]['MODEL_INFO_SVGP_TITLE'], className="alert-heading"),
                html.P(T[lang]['MODEL_UNAVAILABLE'])
            ], color="warning", className="mb-0")
        ucb_style = {'display': 'block'}
    
    elif model_type == 'unet':
        is_available = available_models.get('unet', False)
        if is_available:
            card = dbc.Alert([
                html.H6(T[lang]['MODEL_INFO_UNET_TITLE'], className="alert-heading"),
                html.P(T[lang]['MODEL_INFO_UNET_DESC']),
                html.Small(T[lang]['MODEL_INFO_UNET_SPEED'], className="text-muted")
            ], color="success", className="mb-0")
        else:
            card = dbc.Alert([
                html.H6(T[lang]['MODEL_INFO_UNET_TITLE'], className="alert-heading"),
                html.P(T[lang]['MODEL_UNAVAILABLE'])
            ], color="warning", className="mb-0")
        ucb_style = {'display': 'none'}
    
    elif model_type == 'hybrid':
        is_available = available_models.get('hybrid', False)
        if is_available:
            card = dbc.Alert([
                html.H6(T[lang]['MODEL_INFO_HYBRID_TITLE'], className="alert-heading"),
                html.P(T[lang]['MODEL_INFO_HYBRID_DESC']),
                html.Small(T[lang]['MODEL_INFO_HYBRID_SPEED'], className="text-muted")
            ], color="success", className="mb-0")
        else:
            card = dbc.Alert([
                html.H6(T[lang]['MODEL_INFO_HYBRID_TITLE'], className="alert-heading"),
                html.P(T[lang]['MODEL_UNAVAILABLE'])
            ], color="warning", className="mb-0")
        ucb_style = {'display': 'block'}
    
    else:
        card = dbc.Alert("Unknown model type", color="danger", className="mb-0")
        ucb_style = {'display': 'none'}
    
    return card, ucb_style

@callback(
    Output('ucb-lambda-value', 'children'),
    Input('ucb-lambda-slider', 'value')
)
def update_ucb_lambda_display(value):
    """Update UCB lambda display value"""
    if value is None:
        return "1.0"
    return f"{value:.1f}"

# Callback to restore settings from loaded session data
@callback(
    Output('measures-checklist', 'value', allow_duplicate=True),
    Output('max-height-constraint', 'value', allow_duplicate=True),
    Output('min-distance-constraint', 'value', allow_duplicate=True),
    Output('qd-generations-input', 'value', allow_duplicate=True),
    Output('qd-emitters-input', 'value', allow_duplicate=True),
    Output('qd-niches-input', 'value', allow_duplicate=True),
    Output('qd-batch-size-input', 'value', allow_duplicate=True),
    Output('model-type-selector', 'value', allow_duplicate=True),
    Output('ucb-lambda-slider', 'value', allow_duplicate=True),
    Input('session-store', 'data'),
    Input('url', 'pathname'),
    prevent_initial_call=True
)
def restore_step2_from_session(session_data, pathname):
    if pathname != '/step2' or not session_data:
        return (no_update,) * 9
    
    selected_features = session_data.get('selected_features')
    hard_constraints = session_data.get('hard_constraints', {})
    qd_params = session_data.get('qd_hyperparams', {})
    
    # Determine which max height to use:
    # Priority 1: User has explicitly set a constraint (stored AND different from any adaptive value)
    # Priority 2: Fresh adaptive height from new parcel selection
    # Priority 3: Default value
    adaptive_height = session_data.get('adaptive_max_height')
    stored_max_height = hard_constraints.get('max_height')
    user_has_set_constraint = session_data.get('user_set_max_height', False)
    
    if user_has_set_constraint and stored_max_height:
        # User explicitly set this value - respect it
        max_height = stored_max_height
    elif adaptive_height:
        # Use the adaptive height calculated for this parcel
        max_height = adaptive_height
    elif stored_max_height:
        # Fallback to stored value
        max_height = stored_max_height
    else:
        # Fallback to default
        max_height = int(ENCODING_CONFIG['max_building_floors'] * ENCODING_CONFIG['meters_per_floor'])

    min_distance = hard_constraints.get('min_distance', 0)
        
    qd_generations = qd_params.get('num_generations', QD_CONFIG['num_generations'])
    qd_emitters = qd_params.get('num_emitters', QD_CONFIG['num_emitters'])
    qd_niches = qd_params.get('num_niches', QD_CONFIG['num_niches'])
    qd_batch_size = qd_params.get('batch_size', QD_CONFIG['batch_size'])
    
    model_type = session_data.get('model_type', 'street_canyon')
    ucb_lambda = session_data.get('ucb_lambda', 1.0)
    
    if selected_features is not None:
        return (selected_features, int(max_height), min_distance, 
                qd_generations, qd_emitters, qd_niches, qd_batch_size,
                model_type, ucb_lambda)
    
    return (no_update, int(max_height), min_distance, 
            qd_generations, qd_emitters, qd_niches, qd_batch_size,
            model_type, ucb_lambda)

# --- UPDATED: Callback to save selections, ranges, constraints, QD hyperparameters to the session ---
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
    Input('model-type-selector', 'value'),
    Input('ucb-lambda-slider', 'value'),
    State({'type': 'feature-range-slider', 'index': ALL}, 'id'),
    State('session-store', 'data'),
    State('url', 'pathname'),
    prevent_initial_call=True
)
def update_session_with_features_and_ranges(
    selected_indices, slider_values, max_height, min_distance,
    qd_generations, qd_emitters, qd_niches, qd_batch_size,
    model_type, ucb_lambda,
    slider_ids, session_data, pathname
):
    from dash import ctx
    session_data = session_data or {}
    
    # Always use consolidated feature set and street canyon objective
    feature_set = 'consolidated'
    objective_function = 'street_canyon'
    
    # Detect if we're in restoration phase:
    # When returning to page 2, constraint components fire with their default values BEFORE restoration callback sets correct values
    # Key insight: During restoration, the constraint input values DON'T MATCH the session values
    # During normal user interaction, we're updating the session to MATCH the input
    on_step2 = (pathname == '/step2')
    triggered_by_constraint = (ctx.triggered_id in ['max-height-constraint', 'min-distance-constraint'])
    
    # Check if this was triggered by restoration (not user interaction)
    triggered_by_restoration = False
    if ctx.triggered:
        # If multiple inputs triggered at once, it's likely restoration
        if len(ctx.triggered) > 3:
            triggered_by_restoration = True
        # OR if a constraint fired with the system default value while we have a different saved value
        elif triggered_by_constraint and session_data.get('hard_constraints'):
            saved_max = session_data['hard_constraints'].get('max_height', int(ENCODING_CONFIG['max_building_floors'] * ENCODING_CONFIG['meters_per_floor']))
            saved_min = session_data['hard_constraints'].get('min_distance', 0)
            
            if ctx.triggered_id == 'max-height-constraint':
                if max_height == int(ENCODING_CONFIG['max_building_floors'] * ENCODING_CONFIG['meters_per_floor']) and saved_max != max_height:
                    triggered_by_restoration = True
            elif ctx.triggered_id == 'min-distance-constraint':
                if min_distance == 0 and saved_min != 0:
                    triggered_by_restoration = True
    
    # Use namespaced feature ranges
    ranges_key = f'feature_ranges_{feature_set}'
    
    # Save feature selections
    session_data['selected_features'] = selected_indices
    
    # Save feature_ranges to the appropriate namespace
    if slider_ids and slider_values:
        new_feature_ranges = {
            str(s_id['index']): s_val for s_id, s_val in zip(slider_ids, slider_values)
        }
        # Only save if we have actual data (not empty dict)
        if new_feature_ranges:
            session_data[ranges_key] = new_feature_ranges

    # Save hard constraints (max_height is already in meters, no conversion needed)
    # Preserve existing values if new values are None
    # ALWAYS save constraints, even if feature_set changed (constraints are independent of feature set)
    # BUT: Skip saving if triggered during restoration phase (values are stale component defaults)
    existing_constraints = session_data.get('hard_constraints', {})
    if not (triggered_by_restoration and triggered_by_constraint):
        # Normal operation - save the constraint values
        session_data['hard_constraints'] = {
            'max_height': max_height if max_height is not None else existing_constraints.get('max_height', ),
            'min_distance': min_distance if min_distance is not None else existing_constraints.get('min_distance', 0)
        }
        # Mark that user has explicitly set max height if it differs from adaptive height
        if ctx.triggered_id == 'max-height-constraint' and max_height is not None:
            adaptive_height = session_data.get('adaptive_max_height')
            if not adaptive_height or max_height != adaptive_height:
                session_data['user_set_max_height'] = True
    else:
        # Restoration phase - keep existing values
        if 'hard_constraints' not in session_data:
            session_data['hard_constraints'] = existing_constraints
    
    # Save QD hyperparameters - preserve existing values if new values are None
    existing_qd = session_data.get('qd_hyperparams', {})
    session_data['qd_hyperparams'] = {
        'num_generations': qd_generations if qd_generations is not None else existing_qd.get('num_generations', QD_CONFIG['num_generations']),
        'num_emitters': qd_emitters if qd_emitters is not None else existing_qd.get('num_emitters', QD_CONFIG['num_emitters']),
        'num_niches': qd_niches if qd_niches is not None else existing_qd.get('num_niches', QD_CONFIG['num_niches']),
        'batch_size': qd_batch_size if qd_batch_size is not None else existing_qd.get('batch_size', QD_CONFIG['batch_size']),
    }
    
    # Save objective function selection
    session_data['objective_function'] = objective_function
    
    # Save feature set selection
    session_data['feature_set'] = feature_set
    
    # Save surrogate model settings
    session_data['model_type'] = model_type if model_type is not None else 'street_canyon'
    session_data['ucb_lambda'] = ucb_lambda if ucb_lambda is not None else 1.0
    
    return session_data


# Reset all parameters to default values - clear session except parcel data
@callback(
    Output('session-store', 'data', allow_duplicate=True),
    Input('reset-all-button', 'n_clicks'),
    State('session-store', 'data'),
    prevent_initial_call=True
)
def reset_all_parameters(n_clicks, session_data):
    """
    Reset all parameters to default values by clearing the session.
    This simulates a fresh start as if the user just selected the parcel.
    Only preserves the parcel selection data.
    """
    if not n_clicks:
        return no_update
    
    session_data = session_data or {}
    
    # Preserve only the parcel/area selection data
    preserved_keys = [
        'selected_parcel',
        'selected_bbox', 
        'parcel_geometry',
        'parcel_area_sqm',
        'grid_params',
        'buildable_mask',
        'existing_buildings_grid',
        'wind_direction'
    ]
    
    new_session = {}
    for key in preserved_keys:
        if key in session_data:
            new_session[key] = session_data[key]
    
    
    return new_session