#
# pages/step1_scope.py (Final Corrected Version with Centralized Callback)
#
import dash
from dash import dcc, html, Input, Output, State, callback, no_update
import dash_bootstrap_components as dbc
import dash_leaflet as dl
from dash_extensions.javascript import assign
from backend.translation import T
from backend.data_io import fetch_flurstuecke_data
from shapely.geometry import shape, mapping
from shapely.ops import unary_union

LANG = 'DE'

# Client-side styling for parcel selection (unchanged)
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

        dbc.Row([
            dbc.Col([
                dl.Map(
                    center=[50.734965, 7.055020], zoom=13,
                    children=[
                        dl.TileLayer(),
                        dl.GeoJSON(id='parcels-layer', options=dict(style=style_handle), hideout=dict(selected=[]), hoverStyle={'fillOpacity': 0.5, 'weight': 3}),
                        dl.FeatureGroup([dl.EditControl(id='edit-control', draw=True, edit=True)])
                    ], id='map-step1', style={'width': '100%', 'height': '60vh'}
                )
            ], md=7),
            
            dbc.Col([
                dbc.Tabs([
                    dbc.Tab(label="Flurstücke auswählen", children=[
                        dbc.Card(dbc.CardBody([
                            html.P("1. Flurstücke laden."),
                            dbc.Button("Flurstücke für aktuellen Kartenausschnitt laden", id="load-parcels-btn", className="w-100 mb-3"),
                            html.P("2. Flurstücke durch Klicken auswählen/abwählen."),
                            html.P("3. Die Auswahl erscheint als editierbares Polygon auf der Karte.", className="small fst-italic")
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

# Callbacks for loading and displaying the base parcel layer
@callback(Output('loaded-parcels-store', 'data'), Input('load-parcels-btn', 'n_clicks'), State('map-step1', 'bounds'), prevent_initial_call=True)
def load_parcels_data(n_clicks, bounds):
    if not n_clicks or not bounds: return no_update
    bbox = (bounds[0][1], bounds[0][0], bounds[1][1], bounds[1][0])
    return fetch_flurstuecke_data(bbox)

@callback(Output('parcels-layer', 'data'), Input('loaded-parcels-store', 'data'))
def display_parcels(geojson_data):
    return geojson_data

# This is the single, authoritative callback that manages all user interactions for this step.
@callback(
    Output('session-store', 'data'),
    Output('edit-control', 'geojson'),
    Output('selected-parcels-store', 'data'),
    Output('parcels-layer', 'hideout'),
    Input('parcels-layer', 'clickData'),
    Input('edit-control', 'geojson'),
    Input('wind-direction-slider', 'value'),
    State('selected-parcels-store', 'data'),
    State('loaded-parcels-store', 'data'),
    State('session-store', 'data'),
    prevent_initial_call=True
)
def handle_all_interactions(click_data, edited_geojson, wind_direction, selected_ids, all_parcels_data, session_data):
    session_data = session_data or {}
    ctx = dash.callback_context
    triggered_id = ctx.triggered_id

    # Default to the current state
    new_selected_ids = selected_ids
    hideout = {'selected': selected_ids}
    final_geojson = edited_geojson

    if triggered_id == 'parcels-layer':
        if click_data is None:
            return no_update
        
        # Logic to select/deselect parcels
        parcel_id = click_data['properties']['id']
        new_selected_ids = selected_ids[:]  # Create a copy to ensure Dash detects the change
        if parcel_id in new_selected_ids:
            new_selected_ids.remove(parcel_id)
        else:
            new_selected_ids.append(parcel_id)
        
        # Update the visual styling of the parcel layer
        hideout = {'selected': new_selected_ids}

        # Logic to merge selected parcels and push to the editable layer
        if all_parcels_data and new_selected_ids:
            selected_features = [f for f in all_parcels_data['features'] if f['properties']['id'] in new_selected_ids]
            if selected_features:
                geometries = [shape(f['geometry']) for f in selected_features]
                merged_geometry = unary_union(geometries)
                final_geojson = {'type': 'FeatureCollection', 'features': [{'type': 'Feature', 'geometry': mapping(merged_geometry), 'properties': {}}]}
            else:
                final_geojson = {'type': 'FeatureCollection', 'features': []}
        else:
            final_geojson = {'type': 'FeatureCollection', 'features': []}
    
    # If the trigger was a manual edit, `edited_geojson` is the new truth. We just need to save it.
    # If the trigger was the wind slider, the `final_geojson` remains unchanged from its state.
    
    session_data['site_polygon'] = final_geojson
    session_data['wind_direction'] = wind_direction

    return session_data, final_geojson, new_selected_ids, hideout