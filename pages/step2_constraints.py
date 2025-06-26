from dash import dcc, html, Input, Output, State, callback
import dash_bootstrap_components as dbc
import dash_leaflet as dl
from backend.translation import T

LANG = 'DE'

MEASURES_OPTIONS = {
    'MEASURE_FOOTPRINT': T[LANG]['MEASURE_FOOTPRINT'],
    'MEASURE_LIVING_SPACE': T[LANG]['MEASURE_LIVING_SPACE'],
    'MEASURE_DENSITY': T[LANG]['MEASURE_DENSITY'],
    'MEASURE_PERMEABILITY': T[LANG]['MEASURE_PERMEABILITY'],
    'MEASURE_OPEN_SPACE': T[LANG]['MEASURE_OPEN_SPACE'],
    'MEASURE_NUM_BUILDINGS': T[LANG]['MEASURE_NUM_BUILDINGS'],
}

def layout():
    return dbc.Container([
        html.H2(T[LANG]['STEP2_TITLE']),
        dbc.Row([
            dbc.Col([
                html.H5(T[LANG]['STEP2_TABOO_HEADER']),
                dl.Map(
                    id='map-step2',
                    center=[50.734965, 7.055020], zoom=13,
                    children=[
                        dl.TileLayer(),
                        dl.FeatureGroup(id='site-polygon-group-step2'),
                        dl.FeatureGroup([
                            dl.EditControl(
                                id='edit-control-taboo',
                                draw={'polygon': True, 'polyline': False, 'circle': False, 'marker': False, 'circlemarker': False, 'rectangle': True},
                                edit=True
                            )
                        ])
                    ], style={'width': '100%', 'height': '50vh'}
                )
            ], md=6),
            dbc.Col([
                html.H5(T[LANG]['STEP2_OBJECTIVES_HEADER']),
                dbc.Label(T[LANG]['STEP2_MEASURES_LABEL']),
                dbc.Card(dbc.Checklist(
                    options=[{'label': v, 'value': k} for k, v in MEASURES_OPTIONS.items()],
                    value=list(MEASURES_OPTIONS.keys()), # Select all by default
                    id='measures-checklist',
                    switch=True,
                ), body=True),
                html.Hr(),
                dbc.Label(T[LANG]['STEP2_OBJECTIVE_INFO_LABEL']),
                dbc.Alert(T[LANG]['STEP2_OBJECTIVE_INFO_TEXT'], color="info")
            ], md=6),
        ]),
        dbc.Row([
            dbc.Col(dbc.Button(T[LANG]['PREV_STEP'], href='/', color="secondary")),
            dbc.Col(dbc.Button(T[LANG]['NEXT_STEP'], href='/step3', color="primary"), className="text-end")
        ], className="mt-4")
    ], fluid=True)

@callback(
    Output('site-polygon-group-step2', 'children'),
    Input('session-store', 'data')
)
def display_site_polygon(session_data):
    if session_data and session_data.get('site_polygon'):
        return dl.GeoJSON(data=session_data['site_polygon'], style={'color': 'blue', 'fillOpacity': 0.1})
    return None

@callback(
    Output('session-store', 'data', allow_duplicate=True),
    Input('edit-control-taboo', 'geojson'),
    Input('measures-checklist', 'value'),
    State('session-store', 'data'),
    prevent_initial_call=True
)
def update_session_constraints(taboo_geojson, selected_measures, session_data):
    if session_data is None:
        session_data = {}
    session_data['taboo_zones'] = taboo_geojson if taboo_geojson else []
    session_data['selected_measures'] = selected_measures
    session_data['measures_map'] = {k: v for k, v in MEASURES_OPTIONS.items() if k in selected_measures}
    return session_data