from dash import dcc, html, Input, Output, State, callback
import dash_bootstrap_components as dbc
import dash_leaflet as dl
from backend.translation import T

LANG = 'DE'

def layout():
    return dbc.Container([
        html.H2(T[LANG]['STEP1_TITLE']),
        html.P(T[LANG]['STEP1_DATA_SOURCE_INFO'], className="text-muted"),
        dbc.Row([
            dbc.Col([
                html.H5(T[LANG]['STEP1_MAP_HEADER']),
                dl.Map(
                    center=[50.734965, 7.055020], zoom=13,
                    children=[
                        dl.TileLayer(),
                        dl.FeatureGroup([
                            dl.EditControl(
                                id='edit-control',
                                draw=True,
                                edit=True
                            )
                        ])
                    ], style={'width': '100%', 'height': '50vh'}
                ),
                dcc.Upload(
                    id='upload-shape',
                    children=html.Div(['Drag and Drop or ', html.A('Select a File')]),
                    style={'textAlign': 'center', 'border': '1px dashed grey', 'padding': '10px', 'marginTop': '10px'},
                )
            ], md=6),
            dbc.Col([
                html.H5(T[LANG]['STEP1_WIND_HEADER']),
                dbc.Label(T[LANG]['STEP1_WIND_SLIDER_LABEL']),
                dcc.Slider(id='wind-direction-slider', min=0, max=360, step=1, value=180,
                           marks={0: 'N', 90: 'E', 180: 'S', 270: 'W'}),
                html.Hr(),
                dbc.Button(T[LANG]['STEP1_UPLOAD_KLAM'], disabled=True, className="w-100"),
            ], md=6)
        ]),
        html.Div(id='debug-output-step1'),
        dbc.Button(T[LANG]['NEXT_STEP'], id='next-step1-btn', href='/step2', color="primary", className="mt-4")
    ], fluid=True)

@callback(
    Output('session-store', 'data'),
    Input('edit-control', 'geojson'),
    Input('wind-direction-slider', 'value'),
    State('session-store', 'data')
)
def update_session_data(site_geojson, wind_direction, session_data):
    if session_data is None:
        session_data = {}
    session_data['site_polygon'] = site_geojson
    session_data['wind_direction'] = wind_direction
    return session_data