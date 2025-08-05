# pages/step1_scope.py (Final Corrected Version with Wind Arrow)

import dash
from dash import dcc, html, Input, Output, State, callback, no_update
import dash_bootstrap_components as dbc
import dash_leaflet as dl
from dash_extensions.javascript import assign
from backend.translation import T
from backend.data_io import fetch_flurstuecke_data
from shapely.geometry import shape, mapping
from shapely.ops import unary_union
import base64

LANG = 'DE'

# SVG for a simple arrow, encoded for use in the marker icon
arrow_svg_str = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="black" width="48px" height="48px"><path d="M12 2L12 18M12 2C11.1716 2 9.5 4.5 7 7M12 2C12.8284 2 14.5 4.5 17 7" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>'
arrow_icon_url = f"data:image/svg+xml;base64,{base64.b64encode(arrow_svg_str.encode()).decode()}"

style_handle = assign("""
function(feature, context){
    const { selected } = context.hideout;
    if (selected.includes(feature.properties.id)) {
        return {color: '#ff7800', weight: 3, opacity: 1, fillOpacity: 0.5};
    } else {
        return {color: '#3388ff', weight: 2, opacity: 1, fillOpacity: 0.1};
    }
}
""")

def layout():
    return dbc.Container([
        html.H2(T[LANG]['STEP1_TITLE']),
        html.P(T[LANG]['STEP1_DATA_SOURCE_INFO'], className="text-muted mb-3"),
        dcc.Store(id='loaded-parcels-store'),
        dcc.Store(id='selected-parcels-store', data=[]),
        dcc.Store(id='preview-polygon-store'),

        dbc.Row([
            dbc.Col([
                dl.Map(
                    center=[50.734965, 7.055020], zoom=13,
                    children=[
                        dl.TileLayer(),
                        dl.GeoJSON(id='parcels-layer', options=dict(style=style_handle), hideout=dict(selected=[]), hoverStyle={'fillOpacity': 0.5, 'weight': 3}),
                        dl.GeoJSON(id='geltungsbereich-preview-layer', options=dict(style={'color': 'red', 'fillOpacity': 0.2, 'weight': 5})),
                        dl.FeatureGroup([dl.EditControl(id='edit-control', draw=True, edit=True)]),
                        # --- NEW COMPONENT: Wind Arrow Marker ---
                        dl.Marker(id="wind-arrow-marker",
                                  icon=dict(iconUrl=arrow_icon_url, iconSize=[48, 48], iconAnchor=[24, 24]),
                                  position=[50.734965, 7.055020])
                    ], id='map-step1', style={'width': '100%', 'height': '60vh'}
                )
            ], md=7),
            
            dbc.Col([
                dbc.Tabs([
                    dbc.Tab(label="Flurstücke auswählen", children=[
                        dbc.Card(dbc.CardBody([
                            html.P("1. Flurstücke laden und auswählen.", className="fw-bold"),
                            dbc.Button("Flurstücke für aktuellen Kartenausschnitt laden", id="load-parcels-btn", className="w-100 mb-3"),
                            html.P("2. Auswahl zur Bearbeitung übernehmen.", className="fw-bold"),
                            dbc.Button("Auswahl zur Bearbeitung übernehmen", id="copy-selection-btn", className="w-100 mb-3", color="success"),
                            html.P("3. Ggf. mit den Werkzeugen rechts auf der Karte anpassen.", className="small fst-italic")
                        ]))
                    ]),
                    dbc.Tab(label="Manuell zeichnen", children=[
                        dbc.Card(dbc.CardBody([html.P("Benutzen Sie die Zeichenwerkzeuge auf der rechten Seite der Karte, um den Geltungsbereich manuell zu definieren.")]))
                    ]),
                ]),
                html.Hr(),
                html.H5(T[LANG]['STEP1_WIND_HEADER']),
                dbc.Label(T[LANG]['STEP1_WIND_SLIDER_LABEL']),
                dcc.Slider(id='wind-direction-slider', min=0, max=360, step=1, value=180, marks={0: 'N', 90: 'E', 180: 'S', 270: 'W'}),
            ], md=5)
        ]),
        
        dbc.Button(T[LANG]['NEXT_STEP'], id='next-step1-btn', href='/step2', color="primary", className="mt-4")
    ], fluid=True)

# --- NEW CALLBACK to update the wind arrow ---
@callback(
    Output('wind-arrow-marker', 'position'),
    Output('wind-arrow-marker', 'rotationAngle'),
    Input('wind-direction-slider', 'value'),
    Input('map-step1', 'center')
)
def update_wind_arrow(direction, center):
    # The rotation angle directly corresponds to the slider value
    rotation = direction
    # The arrow will always be in the center of the current map view
    position = [center['lat'], center['lng']]
    return position, rotation

# All other callbacks in this file remain unchanged and correct.
@callback(Output('loaded-parcels-store', 'data'), Input('load-parcels-btn', 'n_clicks'), State('map-step1', 'bounds'), prevent_initial_call=True)
def load_parcels_data(n_clicks, bounds):
    if not n_clicks or not bounds: return no_update
    bbox = (bounds[0][1], bounds[0][0], bounds[1][1], bounds[1][0])
    return fetch_flurstuecke_data(bbox)

@callback(Output('parcels-layer', 'data'), Input('loaded-parcels-store', 'data'))
def display_parcels(geojson_data):
    return geojson_data

@callback(
    Output('selected-parcels-store', 'data'),
    Output('parcels-layer', 'hideout'),
    Input('parcels-layer', 'clickData'),
    State('selected-parcels-store', 'data'),
    prevent_initial_call=True
)
def update_selection_store(click_data, selected_ids):
    if click_data is None: return no_update, no_update
    parcel_id = click_data['properties']['id']
    new_selected_ids = selected_ids[:]
    if parcel_id in new_selected_ids:
        new_selected_ids.remove(parcel_id)
    else:
        new_selected_ids.append(parcel_id)
    hideout = dict(selected=new_selected_ids)
    return new_selected_ids, hideout

@callback(
    Output('geltungsbereich-preview-layer', 'data'),
    Output('preview-polygon-store', 'data'),
    Input('selected-parcels-store', 'data'),
    State('loaded-parcels-store', 'data'),
)
def update_preview_layer(selected_ids, all_parcels_data):
    if all_parcels_data and selected_ids:
        selected_features = [f for f in all_parcels_data['features'] if f['properties']['id'] in selected_ids]
        if selected_features:
            geometries = [shape(f['geometry']) for f in selected_features]
            merged_geometry = unary_union(geometries)
            merged_geojson = {'type': 'FeatureCollection', 'features': [{'type': 'Feature', 'geometry': mapping(merged_geometry), 'properties': {}}]}
            return merged_geojson, merged_geojson
    return None, None

@callback(
    Output('edit-control', 'geojson'),
    Input('copy-selection-btn', 'n_clicks'),
    State('preview-polygon-store', 'data'),
    prevent_initial_call=True
)
def copy_preview_to_editable_layer(n_clicks, preview_geojson):
    if n_clicks and preview_geojson:
        return preview_geojson
    return no_update

@callback(
    Output('session-store', 'data'),
    Input('edit-control', 'geojson'),
    Input('preview-polygon-store', 'data'),
    Input('wind-direction-slider', 'value'),
    State('session-store', 'data'),
)
def save_final_polygon_to_session(edited_geojson, preview_geojson, wind_direction, session_data):
    session_data = session_data or {}
    ctx = dash.callback_context
    triggered_id = ctx.triggered_id
    if triggered_id == 'edit-control':
        final_polygon = edited_geojson
    elif triggered_id == 'preview-polygon-store':
        final_polygon = preview_geojson
    else:
        final_polygon = session_data.get('site_polygon')
    session_data['site_polygon'] = final_polygon
    session_data['wind_direction'] = wind_direction
    return session_data