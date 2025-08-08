#
# pages/step1_scope.py (Final Corrected Version with Unified Workflow and Correct Wind Arrow)
#
import dash
from dash import dcc, html, Input, Output, State, callback, no_update
import dash_bootstrap_components as dbc
import dash_leaflet as dl
from dash_extensions.javascript import assign
from backend.translation import T
from backend.data_io import fetch_flurstuecke_data
from shapely.geometry import shape, mapping, Polygon, MultiPolygon
from shapely.ops import unary_union
import math

LANG = 'DE'

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

def layout():
    arrow_pattern = dict(
        offset='100%', repeat='0',
        arrowHead=dict(polygon=False, pathOptions=dict(stroke=True, color='black', weight=4))
    )

    return dbc.Container([
        html.H2(T[LANG]['STEP1_TITLE']),
        html.P(T[LANG]['STEP1_DATA_SOURCE_INFO'], className="text-muted mb-3"),
        dcc.Store(id='loaded-parcels-store'),
        dcc.Store(id='selected-parcels-store', data=[]),
        dcc.Store(id='active-polygon-store'), # Retained for potential future use, but not primary state

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
                            }, edit={'edit': False, 'remove': True}) # Allow deleting drawn shapes
                        ]),
                        dl.PolylineDecorator(
                            children=[dl.Polyline(id='wind-arrow-line', positions=[])],
                            patterns=[arrow_pattern]
                        )
                    ], id='map-step1', style={'width': '100%', 'height': '60vh'}
                )
            ], md=7),
            
            dbc.Col([
                html.Div([
                    html.H5("Werkzeuge"),
                    dbc.Label("1. Flurstücke von OpenData Portal NRW laden und auswählen/abwählen", className="fw-bold"),
                    dbc.Button("Flurstücke für aktuellen Kartenausschnitt laden", id="load-parcels-btn", className="w-100 mb-3"),
                    
                    dbc.Label("2. Manuelle Anpassung von Flurstücken", className="fw-bold"),
                    dbc.RadioItems(
                        options=[
                            {'label': 'Fläche hinzufügen', 'value': 'add'},
                            {'label': 'Fläche entfernen', 'value': 'subtract'},
                        ],
                        value='add', id='edit-mode-toggle', inline=True,
                    ),
                    html.P("Nutzen Sie die Werkzeuge links auf der Karte, um die grüne Auswahl anzupassen.", className="small fst-italic"),
                ]),
                html.Hr(),
                html.H5(T[LANG]['STEP1_WIND_HEADER']),
                dbc.Label(T[LANG]['STEP1_WIND_SLIDER_LABEL']),
                dcc.Slider(id='wind-direction-slider', min=0, max=360, step=1, value=180, marks={0: 'N', 90: 'E', 180: 'S', 270: 'W'}),
            ], md=5)
        ]),
        
        dbc.Button(T[LANG]['NEXT_STEP'], id='next-step1-btn', href='/step2', color="primary", className="mt-4")
    ], fluid=True)

# Callback to update the wind arrow's line, with the corrected angle calculation
@callback(
    Output('wind-arrow-line', 'positions'),
    Input('wind-direction-slider', 'value'),
    Input('map-step1', 'center')
)
def update_wind_arrow_line(direction_deg, center):
    if isinstance(center, list): center = {'lat': center[0], 'lng': center[1]}
    start_lat, start_lng = center['lat'], center['lng']
    length_in_meters = 200
    EARTH_RADIUS_M = 6378137.0
    
    # --- Corrected angle calculation ---
    # A "North wind" (0°) comes FROM the North, so the arrow should point South (180°).
    angle_math_deg = (450 - direction_deg + 180) % 360
    angle_math_rad = math.radians(angle_math_deg)
    
    delta_lat_rad = (length_in_meters * math.sin(angle_math_rad)) / EARTH_RADIUS_M
    delta_lon_rad = (length_in_meters * math.cos(angle_math_rad)) / (EARTH_RADIUS_M * math.cos(math.radians(start_lat)))
    end_lat = start_lat + math.degrees(delta_lat_rad)
    end_lng = start_lng + math.degrees(delta_lon_rad)
    
    return [[start_lat, start_lng], [end_lat, end_lng]]

# Callbacks for loading and displaying the blue selectable parcel layer
@callback(Output('loaded-parcels-store', 'data'), Input('load-parcels-btn', 'n_clicks'), State('map-step1', 'bounds'), prevent_initial_call=True)
def load_parcels_data(n_clicks, bounds):
    if not n_clicks or not bounds: return no_update
    bbox = (bounds[0][1], bounds[0][0], bounds[1][1], bounds[1][0])
    return fetch_flurstuecke_data(bbox)

@callback(Output('parcels-layer', 'data'), Input('loaded-parcels-store', 'data'))
def display_parcels(geojson_data):
    return geojson_data

# The single, authoritative callback that manages the active green polygon.
@callback(
    Output('session-store', 'data'),
    Output('active-polygon-layer', 'data'),
    Output('selected-parcels-store', 'data'),
    Output('parcels-layer', 'hideout'),
    Input('parcels-layer', 'clickData'),
    Input('edit-control', 'geojson'),
    Input('wind-direction-slider', 'value'),
    State('selected-parcels-store', 'data'),
    State('loaded-parcels-store', 'data'),
    State('session-store', 'data'),
    State('edit-mode-toggle', 'value'),
    prevent_initial_call=True
)
def handle_all_interactions(click_data, drawn_geojson, wind_direction, selected_ids, 
                            all_parcels_data, session_data, edit_mode):
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
    
    if final_geom.is_empty:
        final_geojson = None
    else:
        if isinstance(final_geom, Polygon):
            final_geom = MultiPolygon([final_geom])
        final_geojson = {'type': 'FeatureCollection', 'features': [{'type': 'Feature', 'geometry': mapping(final_geom), 'properties': {}}]}

    session_data['site_polygon'] = final_geojson
    session_data['wind_direction'] = wind_direction

    return session_data, final_geojson, new_selected_ids, hideout