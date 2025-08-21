#
# pages/step4_explore.py
#
from dash import dcc, html, Input, Output, State, callback, clientside_callback, MATCH, ALL, no_update
import dash_bootstrap_components as dbc
from backend.translation import T
from backend.config import ENCODING_CONFIG
from backend.analysis import heightmap_to_geojson
import numpy as np
import pickle
import os
import dash_leaflet as dl
from dash_extensions.javascript import assign

LANG = 'DE'

# JS for styling the building polygons based on height using chroma.js
style_handle = assign("""
function(feature, context){
    const { z_length } = context.hideout;
    const height = feature.properties.height;
    const colorscale = chroma.scale('viridis').domain([0, z_length]);
    return {
        fillColor: colorscale(height),
        color: '#333',
        weight: 1,
        opacity: 1,
        fillOpacity: 0.8
    };
}
""")

def layout():
    return dbc.Container([
        html.H2(T[LANG]['STEP4_TITLE']),
        dbc.Card(dbc.CardBody([
            dbc.Row([
                dbc.Col(dbc.Label(T[LANG]['STEP4_X_AXIS_LABEL'])),
                dbc.Col(dcc.Dropdown(id='x-axis-dropdown-s4')),
            ]),
            dbc.Row([
                dbc.Col(dbc.Label(T[LANG]['STEP4_Y_AXIS_LABEL'])),
                dbc.Col(dcc.Dropdown(id='y-axis-dropdown-s4')),
            ])
        ])),
        html.Hr(),
        html.H4(T[LANG]['STEP4_GRID_HEADER']),
        dcc.Loading(html.Div(id='solution-map-grid-container')),
        dbc.Row([
            dbc.Col(dbc.Button(T[LANG]['PREV_STEP'], href='/step3', color="secondary")),
            dbc.Col(dbc.Button(T[LANG]['NEXT_STEP'], href='/step5', color="primary"), className="text-end")
        ], className="mt-4")
    ], fluid=True)

@callback(
    Output('x-axis-dropdown-s4', 'options'),
    Output('y-axis-dropdown-s4', 'options'),
    Output('x-axis-dropdown-s4', 'value'),
    Output('y-axis-dropdown-s4', 'value'),
    Input('results-store', 'data'),
)
def populate_dropdowns_s4(results_data):
    if not results_data or 'labels' not in results_data:
        return [], [], None, None
    
    options = [{'label': label, 'value': i} for i, label in enumerate(results_data['labels'])]
    val1 = 0 if len(options) > 0 else None
    val2 = 1 if len(options) > 1 else None
    return options, options, val1, val2

@callback(
    Output('solution-map-grid-container', 'children'),
    Input('x-axis-dropdown-s4', 'value'),
    Input('y-axis-dropdown-s4', 'value'),
    State('results-store', 'data'),
)
def update_solution_map_grid(x_axis_idx, y_axis_idx, results_data):
    if not all([isinstance(x_axis_idx, int), isinstance(y_axis_idx, int), results_data]):
        return dbc.Alert("Optimierungsergebnisse nicht gefunden oder Achsen nicht gewählt.", color="warning")

    results_path = results_data.get('full_results_path')
    grid_geojson = results_data.get('grid_geojson')
    if not results_path or not os.path.exists(results_path) or not grid_geojson:
        return dbc.Alert("Fehler: Große Ergebnisdatei oder Georeferenzierung nicht gefunden.", color="danger")

    with open(results_path, 'rb') as f:
        list_of_elites = pickle.load(f)

    grid_dims = results_data['archive_dims']
    grid_resolution_x = grid_dims[x_axis_idx]
    grid_resolution_y = grid_dims[y_axis_idx]
    
    vis_grid = np.full((grid_resolution_y, grid_resolution_x), None, dtype=object)
    
    for elite_dict in list_of_elites:
        ix = elite_dict['grid_indices'][x_axis_idx]
        iy = elite_dict['grid_indices'][y_axis_idx]
        if vis_grid[iy, ix] is None or elite_dict['objective'] > vis_grid[iy, ix]['objective']:
            vis_grid[iy, ix] = elite_dict
    
    grid_children = []
    heightmap_res = results_data['xy_length']
    
    lons = [c[0] for f in grid_geojson['features'] for c in f['geometry']['coordinates'][0]]
    lats = [c[1] for f in grid_geojson['features'] for c in f['geometry']['coordinates'][0]]
    map_center = [(min(lats) + max(lats)) / 2, (min(lons) + max(lons)) / 2]

    for row in range(grid_resolution_y):
        row_children = []
        for col in range(grid_resolution_x):
            elite_data = vis_grid[row, col]
            map_id = {'type': 'solution-map', 'index': f'{row}-{col}'}
            
            if elite_data is not None:
                heightmap = np.array(elite_data['heightmap']).reshape((heightmap_res, heightmap_res))
                design_geojson = heightmap_to_geojson(np.flipud(heightmap), grid_geojson)
                
                map_component = dl.Map(
                    center=map_center, zoom=14,
                    children=[
                        dl.TileLayer(url="https://{s}.basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}{r}.png",
                                     attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'),
                        dl.GeoJSON(data=design_geojson, id=f'geojson-{row}-{col}', 
                                   options=dict(style=style_handle), 
                                   hideout={'z_length': ENCODING_CONFIG['z_length']})
                    ], 
                    style={'width': '100%', 'height': '150px', 'min-height': '150px'},
                    id=map_id
                )
                col_child = dbc.Col(map_component)
            else:
                placeholder = html.Div(
                    dbc.Alert("Kein Entwurf", color="light", className="h-100 d-flex align-items-center justify-content-center m-0"),
                    style={'height': '150px', 'border': '1px solid #dee2e6'}
                )
                col_child = dbc.Col(placeholder)
            row_children.append(col_child)
        grid_children.append(dbc.Row(row_children, className="g-1 mb-1"))

    return grid_children

clientside_callback(
    """
    function(view, map_ids) {
        const triggered_id_str = dash_clientside.callback_context.triggered.map(t => t.prop_id).join(',');
        if (!triggered_id_str || !view) {
            return dash_clientside.no_update;
        }
        const updated_views = map_ids.map(id => view);
        return updated_views;
    }
    """,
    Output({'type': 'solution-map', 'index': ALL}, 'view'),
    Input({'type': 'solution-map', 'index': ALL}, 'view'),
    State({'type': 'solution-map', 'index': ALL}, 'id'),
    prevent_initial_call=True
)