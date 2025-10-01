#
# pages/step1_scope.py
#
import dash
from dash import dcc, html, Input, Output, State, callback, no_update, clientside_callback
import dash_bootstrap_components as dbc
import dash_leaflet as dl
from dash_extensions.javascript import assign
from backend.translation import T
from backend.data_io import fetch_flurstuecke_data
from shapely.geometry import shape, mapping, Polygon, MultiPolygon
from shapely.ops import unary_union
import math
import json
import base64
import io

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
    return dbc.Container([
        html.H2(T[lang]['STEP1_TITLE']),
        dbc.Button(T[lang]['NEXT_STEP'], id='next-step1-btn', href='/step2', color="primary", className="mt-4"),
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
                    # --- NEW: File Upload ---
                    dbc.Label(T[lang]['STEP1_UPLOAD_LABEL'], className="fw-bold"),
                    dcc.Upload(
                        id='upload-geojson',
                        children=html.Div([T[lang]['STEP1_UPLOAD_BUTTON_TEXT']]),
                        style={
                            'width': '100%', 'height': '60px', 'lineHeight': '60px',
                            'borderWidth': '1px', 'borderStyle': 'dashed',
                            'borderRadius': '5px', 'textAlign': 'center', 'margin-bottom': '10px'
                        },
                        multiple=False
                    ),
                    html.Hr(),
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
                html.H5(T[lang]['STEP1_WIND_HEADER']),
                html.Div(T[lang]['STEP1_WIND_SLIDER_LABEL'], className="text-center"),
                create_compass_component(),
                dcc.Slider(id='wind-direction-slider', min=0, max=360, step=1, value=180, marks={0: 'N', 90: 'E', 180: 'S', 270: 'W'}),
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
    session_data = session_data or {}
    ctx = dash.callback_context
    triggered_id = ctx.triggered_id

    last_active_geojson = session_data.get('site_polygon')
    base_geom = shape(last_active_geojson['features'][0]['geometry']) if last_active_geojson and last_active_geojson.get('features') else Polygon()

    new_selected_ids = selected_ids
    hideout = {'selected': selected_ids}
    final_geom = base_geom

    if triggered_id == 'parcels-layer':
        if click_data is None: return no_update
        
        parcel_id = click_data['properties']['id']
        new_selected_ids = selected_ids[:]
        if parcel_id in new_selected_ids:
            new_selected_ids.remove(parcel_id)
        else:
            new_selected_ids.append(parcel_id)
        
        hideout = {'selected': new_selected_ids}

        if all_parcels_data and new_selected_ids:
            selected_features = [f for f in all_parcels_data['features'] if f['properties']['id'] in new_selected_ids]
            geometries = [shape(f['geometry']) for f in selected_features]
            final_geom = unary_union(geometries)
        else:
            final_geom = Polygon()
            
    elif triggered_id == 'edit-control':
        if drawn_geojson and drawn_geojson['features']:
            newly_drawn_geom = shape(drawn_geojson['features'][-1]['geometry'])
            
            if edit_mode == 'add':
                final_geom = base_geom.union(newly_drawn_geom)
            else: # subtract
                final_geom = base_geom.difference(newly_drawn_geom)
            
            new_selected_ids = []
            hideout = {'selected': []}
    
    elif triggered_id == 'upload-geojson' and upload_contents is not None:
        content_type, content_string = upload_contents.split(',')
        decoded = base64.b64decode(content_string)
        try:
            geojson_data = json.load(io.StringIO(decoded.decode('utf-8')))
            geometries = [shape(feature['geometry']) for feature in geojson_data['features']]
            final_geom = unary_union(geometries)
            # Clear parcel selection when importing a file
            new_selected_ids = []
            hideout = {'selected': []}
        except Exception as e:
            print(f"Error parsing uploaded file: {e}")
            return no_update
    
    if final_geom.is_empty:
        final_geojson = None
    else:
        if isinstance(final_geom, Polygon):
            final_geom = MultiPolygon([final_geom])
        final_geojson = {'type': 'FeatureCollection', 'features': [{'type': 'Feature', 'geometry': mapping(final_geom), 'properties': {}}]}

    session_data['site_polygon'] = final_geojson
    session_data['wind_direction'] = wind_direction

    return session_data, final_geojson, new_selected_ids, hideout