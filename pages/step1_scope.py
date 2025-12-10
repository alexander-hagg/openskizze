#
# pages/step1_scope.py
#
import dash
from dash import dcc, html, Input, Output, State, callback, no_update, clientside_callback
import dash_bootstrap_components as dbc
import dash_leaflet as dl
from dash_extensions.javascript import assign
from backend.translation import T
from backend.data_io import fetch_flurstuecke_data, fetch_and_process_buildings_for_area
from shapely.geometry import shape, mapping, Polygon, MultiPolygon
from shapely.ops import unary_union, transform
import pyproj
import math
import json
import base64
import io
import pickle

def calculate_parcel_info(geometry, lang='DE'):
    """Calculate and format parcel information for display."""
    from backend.translation import T
    
    print(f"[parcel_info] Calculating parcel info for geometry (empty={geometry.is_empty})")
    
    if geometry.is_empty:
        print(f"[parcel_info] No parcel selected, returning alert")
        return dbc.Alert(T[lang]['STEP1_NO_PARCEL_SELECTED'], color="light", className="small")
    
    # Transform from WGS84 (EPSG:4326) to UTM Zone 32N (EPSG:25832) for accurate area calculation in NRW
    wgs84 = pyproj.CRS('EPSG:4326')
    utm32n = pyproj.CRS('EPSG:25832')
    project = pyproj.Transformer.from_crs(wgs84, utm32n, always_xy=True).transform
    
    # Transform the geometry to projected coordinates
    geometry_projected = transform(project, geometry)
    
    # Calculate area in square meters (now accurate because we're in UTM)
    area_m2 = geometry_projected.area
    
    # Get bounding box for dimensions (in projected coordinates)
    minx, miny, maxx, maxy = geometry_projected.bounds
    width = maxx - minx
    length = maxy - miny
    
    print(f"[parcel_info] Area: {area_m2:,.1f} m², Dimensions: {width:.1f} m × {length:.1f} m")
    
    # Format the display
    return dbc.Card(dbc.CardBody([
        html.Div([
            html.Strong(f"{T[lang]['STEP1_PARCEL_AREA']}: "),
            html.Span(f"{area_m2:,.1f} m²")
        ], className="mb-2"),
        html.Div([
            html.Strong(f"{T[lang]['STEP1_PARCEL_DIMENSIONS']}: "),
            html.Span(f"{width:.1f} m × {length:.1f} m")
        ])
    ]), className="mb-3", color="light")

# Client-side styling for the selectable parcel layer
style_handle = assign("""
function(feature, context){
    const { selected } = context.hideout;
    if (selected.includes(feature.properties.id)) {
        return {color: '#ff7800', weight: 3, opacity: 1, fillOpacity: 0.5}; // Orange for selected
    } else {
        return {color: '#3388ff', weight: 2, opacity: 1, fillOpacity: 0.1}; // Blue for available
    }
}
""")

def create_compass_component():
    """Creates the HTML structure for the interactive compass."""
    return html.Div(id='compass-container', className='compass-container', children=[
        html.Div(className='compass-rose', children=[
            html.Span('N', className='compass-label compass-label-n'),
            html.Span('E', className='compass-label compass-label-e'),
            html.Span('S', className='compass-label compass-label-s'),
            html.Span('W', className='compass-label compass-label-w'),
        ]),
        html.Div(id='compass-needle-container', className='compass-needle-container', children=[
            html.Div(className='compass-needle', id='compass-needle')
        ]),
        html.Div(className='compass-pivot')
    ])

def layout(lang='DE'):
    from backend.translation import create_breadcrumb
    return dbc.Container([
        create_breadcrumb(1, lang),
        html.H2(T[lang]['STEP1_TITLE']),
        html.P(T[lang]['STEP1_DATA_SOURCE_INFO'], className="text-muted mb-3"),
        dcc.Store(id='loaded-parcels-store'),
        dcc.Store(id='selected-parcels-store', data=[]),
        dcc.Store(id='active-polygon-store'),

        dbc.Row([
            dbc.Col([
                dl.Map(
                    center=[50.734965, 7.055020], zoom=13,
                    children=[
                        dl.TileLayer(),
                        dl.GeoJSON(id='parcels-layer', options=dict(style=style_handle), hideout=dict(selected=[]), hoverStyle={'fillOpacity': 0.5, 'weight': 3}),
                        dl.GeoJSON(id='active-polygon-layer', options=dict(style={'color': 'green', 'fillOpacity': 0.6, 'weight': 3})),
                        dl.FeatureGroup([
                            dl.EditControl(id='edit-control', draw={
                                'polygon': True, 'rectangle': True, 'circle': False,
                                'marker': False, 'circlemarker': False, 'polyline': False
                            }, edit={'edit': False, 'remove': True})
                        ]),
                    ], id='map-step1', style={'width': '100%', 'height': '60vh'}
                )
            ], md=7),
            
            dbc.Col([
                html.Div([
                    html.H5(T[lang]['STEP1_TOOLS_HEADER']),
                    dbc.Label(T[lang]['STEP1_LOAD_PARCELS_LABEL'], className="fw-bold"),
                    dbc.Button(T[lang]['STEP1_LOAD_PARCELS_BUTTON'], id="load-parcels-btn", className="w-100 mb-3"),
                    
                    dbc.Label(T[lang]['STEP1_MANUAL_ADJUSTMENT_LABEL'], className="fw-bold"),
                    dbc.RadioItems(
                        options=[
                            {'label': T[lang]['STEP1_ADD_AREA'], 'value': 'add'},
                            {'label': T[lang]['STEP1_REMOVE_AREA'], 'value': 'subtract'},
                        ],
                        value='add', id='edit-mode-toggle', inline=True,
                    ),
                    html.P(T[lang]['STEP1_EDIT_INSTRUCTIONS'], className="small fst-italic"),
                ]),
                html.Hr(),
                html.Div([
                    html.H5(T[lang]['STEP1_PARCEL_INFO_HEADER']),
                    html.Div(id='parcel-info-display', children=[
                        dbc.Alert(T[lang]['STEP1_NO_PARCEL_SELECTED'], color="light", className="small")
                    ])
                ]),
                html.Hr(),
                # Wind Direction - moved above Model Diagnostics
                html.H5(T[lang]['STEP1_WIND_HEADER']),
                html.Div(T[lang]['STEP1_WIND_SLIDER_LABEL'], className="text-center"),
                create_compass_component(),
                dcc.Slider(id='wind-direction-slider', min=0, max=360, step=1, value=180, marks={0: 'N', 90: 'E', 180: 'S', 270: 'W'}),
                html.Hr(),
                # Model Diagnostics Button
                dbc.Card([
                    dbc.CardBody([
                        html.H6(T[lang].get('MODEL_DIAG_TITLE', 'Model Diagnostics'), className='mb-2'),
                        html.P(
                            T[lang].get('MODEL_DIAG_BUTTON_INFO', 
                                       'Test and compare objective functions on archetypical urban patterns.'),
                            className='small text-muted mb-3'
                        ),
                        dbc.Button(
                            T[lang].get('MODEL_DIAG_BUTTON', 'Open Model Diagnostics'),
                            id='open-model-diagnostics-btn',
                            color='info',
                            outline=True,
                            size='sm',
                            className='w-100'
                        )
                    ])
                ], className='mb-3'),
                # Hidden upload component (needed for callbacks but not displayed)
                dcc.Upload(id='upload-geojson', style={'display': 'none'}),
            ], md=5)
        ])
    ], fluid=True)

# --- INTERACTIVE COMPASS CLIENTSIDE CALLBACKS ---

clientside_callback(
    """
    function(slider_value) {
        // This callback syncs the slider's value TO the compass needle's rotation.
        const needle = document.getElementById('compass-needle');
        if (needle) {
            needle.style.transform = `rotate(${slider_value}deg)`;
        }
        return window.dash_clientside.no_update;
    }
    """,
    Output('compass-needle-container', 'data-dummy-output'), # Dummy output
    Input('wind-direction-slider', 'value')
)

clientside_callback(
    """
    function(_, slider_id) {
        // This callback handles the drag logic FOR the compass, updating the slider.
        const container = document.getElementById('compass-container');
        if (!container) return;

        let isDragging = false;

        const updateAngle = (e) => {
            e.preventDefault();
            const rect = container.getBoundingClientRect();
            const centerX = rect.left + rect.width / 2;
            const centerY = rect.top + rect.height / 2;

            const clientX = e.touches ? e.touches[0].clientX : e.clientX;
            const clientY = e.touches ? e.touches[0].clientY : e.clientY;

            const deltaX = clientX - centerX;
            const deltaY = clientY - centerY;

            // Calculate angle in degrees. Add 90 because 0 degrees in atan2 is East.
            let angle = Math.atan2(deltaY, deltaX) * (180 / Math.PI) + 90;
            if (angle < 0) {
                angle += 360; // Normalize to 0-360
            }
            
            // Find the slider and update its value.
            // This is a bit of a hack to communicate with Dash components.
            const slider = document.getElementById(slider_id);
            if(slider){
                // We need to find the hidden input element that holds the value
                const input = slider.querySelector('input[type="hidden"]');
                if(input){
                    const nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
                    nativeInputValueSetter.call(input, Math.round(angle));
                    const event = new Event('input', { bubbles: true });
                    input.dispatchEvent(event);
                }
            }
        };

        const startDrag = (e) => {
            isDragging = true;
            updateAngle(e);
        };

        const doDrag = (e) => {
            if (isDragging) {
                updateAngle(e);
            }
        };

        const stopDrag = () => {
            isDragging = false;
        };
        
        // Attach event listeners
        container.addEventListener('mousedown', startDrag);
        document.addEventListener('mousemove', doDrag);
        document.addEventListener('mouseup', stopDrag);
        container.addEventListener('touchstart', startDrag, { passive: false });
        document.addEventListener('touchmove', doDrag, { passive: false });
        document.addEventListener('touchend', stopDrag);
        
        return window.dash_clientside.no_update;
    }
    """,
    Output('compass-container', 'data-dummy-output'),
    Input('compass-container', 'n_clicks'),
    State('wind-direction-slider', 'id')
)

# Callbacks for loading and displaying the blue selectable parcel layer
@callback(Output('loaded-parcels-store', 'data'), Input('load-parcels-btn', 'n_clicks'), State('map-step1', 'bounds'), prevent_initial_call=True)
def load_parcels_data(n_clicks, bounds):
    if not n_clicks or not bounds: return no_update
    bbox = (bounds[0][1], bounds[0][0], bounds[1][1], bounds[1][0])
    return fetch_flurstuecke_data(bbox)

@callback(Output('parcels-layer', 'data'), Input('loaded-parcels-store', 'data'))
def display_parcels(geojson_data):
    return geojson_data

# Callback to restore the polygon and wind direction when a project is loaded
@callback(
    Output('active-polygon-layer', 'data', allow_duplicate=True),
    Output('wind-direction-slider', 'value', allow_duplicate=True),
    Input('session-store', 'data'),
    Input('url', 'pathname'),
    prevent_initial_call=True
)
def restore_from_session(session_data, pathname):
    if pathname != '/' or not session_data:
        return no_update, no_update
    
    ctx = dash.callback_context
    # Only restore when session-store changes (e.g., project load), not on every visit
    if not ctx.triggered or ctx.triggered[0]['prop_id'] != 'session-store.data':
        return no_update, no_update
    
    site_polygon = session_data.get('site_polygon')
    wind_direction = session_data.get('wind_direction', 180)
    
    return site_polygon, wind_direction

# The single, authoritative callback that manages the active green polygon.
@callback(
    Output('session-store', 'data', allow_duplicate=True),
    Output('active-polygon-layer', 'data', allow_duplicate=True),
    Output('selected-parcels-store', 'data'),
    Output('parcels-layer', 'hideout'),
    Output('parcel-info-display', 'children'),
    Input('parcels-layer', 'clickData'),
    Input('edit-control', 'geojson'),
    Input('wind-direction-slider', 'value'),
    Input('upload-geojson', 'contents'), # --- NEW INPUT ---
    State('upload-geojson', 'filename'), # --- NEW STATE ---
    State('selected-parcels-store', 'data'),
    State('loaded-parcels-store', 'data'),
    State('session-store', 'data'),
    State('edit-mode-toggle', 'value'),
    prevent_initial_call=True
)
def handle_all_interactions(click_data, drawn_geojson, wind_direction, upload_contents, upload_filename,
                            selected_ids, all_parcels_data, session_data, edit_mode):
    from backend.translation import T
    session_data = session_data or {}
    ctx = dash.callback_context
    triggered_id = ctx.triggered_id
    
    print(f"[handle_all_interactions] Triggered by: {triggered_id}")

    last_active_geojson = session_data.get('site_polygon')
    base_geom = shape(last_active_geojson['features'][0]['geometry']) if last_active_geojson and last_active_geojson.get('features') else Polygon()

    new_selected_ids = selected_ids
    hideout = {'selected': selected_ids}
    final_geom = base_geom
    
    # If only wind direction changed, skip parcel info update
    if triggered_id == 'wind-direction-slider':
        print(f"[handle_all_interactions] Wind direction changed to {wind_direction}, keeping geometry unchanged")
        session_data['wind_direction'] = wind_direction
        return session_data, no_update, no_update, no_update, no_update

    if triggered_id == 'parcels-layer':
        if click_data is None: return no_update
        
        parcel_id = click_data['properties']['id']
        new_selected_ids = selected_ids[:]
        if parcel_id in new_selected_ids:
            new_selected_ids.remove(parcel_id)
            print(f"[handle_all_interactions] Deselected parcel {parcel_id}")
        else:
            new_selected_ids.append(parcel_id)
            print(f"[handle_all_interactions] Selected parcel {parcel_id}")
        
        hideout = {'selected': new_selected_ids}

        if all_parcels_data and new_selected_ids:
            selected_features = [f for f in all_parcels_data['features'] if f['properties']['id'] in new_selected_ids]
            geometries = [shape(f['geometry']) for f in selected_features]
            final_geom = unary_union(geometries)
            print(f"[handle_all_interactions] Combined {len(new_selected_ids)} parcels, area: {final_geom.area:.1f}")
        else:
            final_geom = Polygon()
            print(f"[handle_all_interactions] No parcels selected, empty geometry")
            
    elif triggered_id == 'edit-control':
        if drawn_geojson and drawn_geojson['features']:
            newly_drawn_geom = shape(drawn_geojson['features'][-1]['geometry'])
            print(f"[handle_all_interactions] Edit control triggered, mode={edit_mode}, drawn area={newly_drawn_geom.area:.1f}")
            
            if edit_mode == 'add':
                final_geom = base_geom.union(newly_drawn_geom)
                print(f"[handle_all_interactions] Added area, new total: {final_geom.area:.1f}")
            else: # subtract
                final_geom = base_geom.difference(newly_drawn_geom)
                print(f"[handle_all_interactions] Subtracted area, new total: {final_geom.area:.1f}")
            
            new_selected_ids = []
            hideout = {'selected': []}
    
    elif triggered_id == 'upload-geojson' and upload_contents is not None:
        content_type, content_string = upload_contents.split(',')
        decoded = base64.b64decode(content_string)
        try:
            geojson_data = json.load(io.StringIO(decoded.decode('utf-8')))
            geometries = [shape(feature['geometry']) for feature in geojson_data['features']]
            final_geom = unary_union(geometries)
            print(f"[handle_all_interactions] Uploaded GeoJSON with {len(geometries)} features, total area: {final_geom.area:.1f}")
            # Clear parcel selection when importing a file
            new_selected_ids = []
            hideout = {'selected': []}
        except Exception as e:
            print(f"[handle_all_interactions] Error parsing uploaded file: {e}")
            return no_update
    
    if final_geom.is_empty:
        final_geojson = None
    else:
        if isinstance(final_geom, Polygon):
            final_geom = MultiPolygon([final_geom])
        final_geojson = {'type': 'FeatureCollection', 'features': [{'type': 'Feature', 'geometry': mapping(final_geom), 'properties': {}}]}

    session_data['site_polygon'] = final_geojson
    session_data['wind_direction'] = wind_direction
    
    # Calculate and store grid parameters for model selection
    if final_geojson and final_geojson.get('features'):
        from backend.config import DOMAIN_CONFIG
        import math
        import geopandas as gpd
        
        gdf_user_poly = gpd.GeoDataFrame.from_features(final_geojson, crs="EPSG:4326")
        gdf_user_poly_native = gdf_user_poly.to_crs("EPSG:25832")
        min_x, min_y, max_x, max_y = gdf_user_poly_native.total_bounds
        
        width = max_x - min_x
        height = max_y - min_y
        square_size = max(width, height)
        border = square_size * (DOMAIN_CONFIG['environment_border_size'] - 1.0) / 2.0
        grid_side_length = square_size + (2 * border)
        
        pixel_size = DOMAIN_CONFIG['pixel_size_in_meters']
        xy_length = math.ceil(grid_side_length / pixel_size)
        
        session_data['grid_params'] = {
            'xy_length': xy_length,
            'grid_side_length': grid_side_length,
            'pixel_size': pixel_size
        }
        print(f"[grid_params] Calculated grid: {xy_length} bins ({grid_side_length:.1f}m)")
    
    # =========================================================================
    # Fetch and cache building data when area is selected/modified
    # =========================================================================
    # Only fetch building data when the polygon actually changed (not just wind direction)
    if triggered_id in ['parcels-layer', 'edit-control', 'upload-geojson']:
        if final_geojson and final_geojson.get('features'):
            # Fetch and process building data for the selected area
            print(f"[fetch_buildings] → Fetching building data for selected area from NRW API...")
            try:
                building_data = fetch_and_process_buildings_for_area(
                    user_polygon_geojson=final_geojson
                )
                
                if building_data:
                    # Serialize the building data for storage in session
                    # We need to handle NumPy arrays - use pickle + base64 encoding
                    serialized_data = base64.b64encode(pickle.dumps(building_data)).decode('utf-8')
                    session_data['building_data'] = serialized_data
                    
                    # Count buildings from the GeoDataFrame
                    num_buildings = len(building_data.get('gdf_buildings_filtered', []))
                    print(f"[fetch_buildings] ✓ Cached building data: {num_buildings} buildings processed")
                    
                    # Calculate adaptive max height based on nearby buildings
                    from backend.data_io import calculate_adaptive_max_height
                    from shapely.geometry import shape as geom_shape
                    try:
                        gdf_buildings = building_data.get('gdf_buildings_filtered')
                        if gdf_buildings is not None and not gdf_buildings.empty:
                            parcel_shape = geom_shape(final_geojson['features'][0]['geometry'])
                            parcel_centroid = parcel_shape.centroid
                            adaptive_height = calculate_adaptive_max_height(
                                gdf_buildings, 
                                parcel_centroid, 
                                num_closest=20,
                                default_height=10
                            )
                            session_data['adaptive_max_height'] = int(adaptive_height)
                            # Clear user override flag for new parcel
                            if 'user_set_max_height' in session_data:
                                del session_data['user_set_max_height']
                            print(f"[fetch_buildings] ✓ Calculated adaptive max height: {adaptive_height}m")
                        else:
                            # No buildings found - use default 10m
                            session_data['adaptive_max_height'] = 10
                            # Clear user override flag for new parcel
                            if 'user_set_max_height' in session_data:
                                del session_data['user_set_max_height']
                            print(f"[fetch_buildings] ℹ No buildings in vicinity, using default max height: 10m")
                    except Exception as e:
                        print(f"[fetch_buildings] Warning: Could not calculate adaptive height: {e}")
                        session_data['adaptive_max_height'] = 10  # Fallback to default
                        # Clear user override flag for new parcel
                        if 'user_set_max_height' in session_data:
                            del session_data['user_set_max_height']
                else:
                    print("[fetch_buildings] ✗ No building data returned")
                    # No buildings - use default 10m
                    session_data['adaptive_max_height'] = 10
                    # Clear user override flag for new parcel
                    if 'user_set_max_height' in session_data:
                        del session_data['user_set_max_height']
                    print(f"[fetch_buildings] ℹ No buildings in vicinity, using default max height: 10m")
                    # Clear cache if fetch returned None
                    if 'building_data' in session_data:
                        del session_data['building_data']
                    
            except Exception as e:
                print(f"[fetch_buildings] ✗ Error fetching building data: {e}")
                import traceback
                traceback.print_exc()
                # Don't fail - optimization will fall back to fetching directly
                if 'building_data' in session_data:
                    del session_data['building_data']
        else:
            # No polygon selected, clear cached building data
            if 'building_data' in session_data:
                del session_data['building_data']
                print(f"[fetch_buildings] ✗ No polygon selected - cleared building cache")

    # Calculate parcel information
    lang = session_data.get('language', 'DE')
    parcel_info_component = calculate_parcel_info(final_geom, lang)

    return session_data, final_geojson, new_selected_ids, hideout, parcel_info_component

# Callback to navigate to model diagnostics page
@callback(
    Output('url', 'pathname', allow_duplicate=True),
    Input('open-model-diagnostics-btn', 'n_clicks'),
    prevent_initial_call=True
)
def open_model_diagnostics(n_clicks):
    """Navigate to model diagnostics page."""
    if n_clicks:
        return '/model_diagnostics'
    return no_update
