import dash
from dash import dcc, html, Input, Output, State, ALL
import dash_bootstrap_components as dbc
import dash_leaflet as dl
import dash_leaflet.express as dlx
import numpy as np
import plotly.express as px
import time

# Initialize the Dash app with Bootstrap CSS and suppress callback exceptions
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP], suppress_callback_exceptions=True)

# Mock functions for the back-end processes
def load_geodata(coordinates):
    # Mocking a delay for data retrieval
    time.sleep(0)
    return f"Mocked GIS data for area with coordinates: {coordinates}"

def run_optimization(morph_features):
    return np.random.rand(10, 10, 10)

def predict_airflow(selected_design):
    return np.random.rand(100, 100)

def cluster_designs(design_data):
    return np.random.randint(0, 3, size=(10,))

# Helper functions
def meters_to_lat_lon(center_lat, center_lon, meters):
    # Constants
    earth_radius = 6378137.0  # in meters

    # Latitude calculation
    delta_lat = meters / earth_radius
    delta_lat_deg = delta_lat * (180 / np.pi)

    # Longitude calculation (adjusted by latitude)
    delta_lon = meters / (earth_radius * np.cos(np.pi * center_lat / 180))
    delta_lon_deg = delta_lon * (180 / np.pi)

    return delta_lat_deg, delta_lon_deg

def rotate_and_map_points(center_lat, center_lon, wind_dir, side_length=200):
    wind_dir_rad = np.radians(wind_dir)
    
    # Calculate half the side length
    half_side_length = side_length / 2
    
    # Define the rectangle's points around the center (local coordinates)
    local_points = [
        [-half_side_length, -half_side_length],  # bottom-left
        [-half_side_length, half_side_length],   # top-left
        [half_side_length, half_side_length],    # top-right
        [half_side_length, -half_side_length]    # bottom-right
    ]

    # Rotate and map to geographic coordinates
    global_points = []
    for x, y in local_points:
        # Rotate the point by the wind direction
        x_rot = x * np.cos(wind_dir_rad) - y * np.sin(wind_dir_rad)
        y_rot = x * np.sin(wind_dir_rad) + y * np.cos(wind_dir_rad)
        
        # Map the rotated point to geographic coordinates
        delta_lat, delta_lon = meters_to_lat_lon(center_lat, center_lon, x_rot)
        mapped_lat = center_lat + delta_lat
        mapped_lon = center_lon + meters_to_lat_lon(center_lat, center_lon, y_rot)[1]
        
        global_points.append([mapped_lat, mapped_lon])

    return global_points

def generate_grid_overlay(polygon_points):
    """ Generate a grid overlay within the selected rectangle bounds, properly aligned with the rotated rectangle. """
    grid_lines = []
    num_lines = 20  # Example: 20x20 grid

    # Define the grid lines within the bounds of the rotated rectangle
    for i in range(1, num_lines):
        # Horizontal lines
        start_lat = polygon_points[0][0] + i * (polygon_points[1][0] - polygon_points[0][0]) / num_lines
        start_lon = polygon_points[0][1] + i * (polygon_points[1][1] - polygon_points[0][1]) / num_lines
        end_lat = polygon_points[3][0] + i * (polygon_points[2][0] - polygon_points[3][0]) / num_lines
        end_lon = polygon_points[3][1] + i * (polygon_points[2][1] - polygon_points[3][1]) / num_lines

        grid_lines.append(dl.Polyline(positions=[
            [start_lat, start_lon],
            [end_lat, end_lon]
        ], color="blue", weight=0.5))

        # Vertical lines
        start_lat = polygon_points[0][0] + i * (polygon_points[3][0] - polygon_points[0][0]) / num_lines
        start_lon = polygon_points[0][1] + i * (polygon_points[3][1] - polygon_points[0][1]) / num_lines
        end_lat = polygon_points[1][0] + i * (polygon_points[2][0] - polygon_points[1][0]) / num_lines
        end_lon = polygon_points[1][1] + i * (polygon_points[2][1] - polygon_points[1][1]) / num_lines

        grid_lines.append(dl.Polyline(positions=[
            [start_lat, start_lon],
            [end_lat, end_lon]
        ], color="blue", weight=0.5))

    return dl.LayerGroup(grid_lines)


def generate_affected_region(bounds):
    lat_start, lon_start = bounds[0]
    lat_end, lon_end = bounds[1]

    # Mock affected region as 50% larger
    lat_buffer = (lat_end - lat_start) * 0.5
    lon_buffer = (lon_end - lon_start) * 0.5

    affected_bounds = [
        [lat_start - lat_buffer, lon_start - lon_buffer],
        [lat_start - lat_buffer, lon_end + lon_buffer],
        [lat_end + lat_buffer, lon_end + lon_buffer],
        [lat_end + lat_buffer, lon_start - lon_buffer]
    ]

    return dl.Rectangle(bounds=affected_bounds, color="red", fillOpacity=0.2)

# Initial center coordinates
initial_center = {"lat": 50.734965, "lng": 7.055020}
initial_wind_dir = 180  # South wind

# Create the header and footer components
header = dbc.Navbar(
    dbc.Container(
        [
            html.A(
                dbc.Row(
                    [
                        dbc.Col(html.Img(src=dash.get_asset_url('logo.png'), height="50px")),
                        dbc.Col(dbc.NavbarBrand("Urban Planning Tool", className="ms-2")),
                    ],
                    align="center",
                    className="g-0",
                ),
                href="#",
                style={"textDecoration": "none"},
            ),
            dbc.NavbarToggler(id="navbar-toggler"),
            dbc.Collapse(
                dbc.Nav(
                    [
                        dbc.NavItem(dbc.NavLink("About", href="#")),
                        dbc.NavItem(dbc.NavLink("Sponsors", href="#")),
                    ],
                    className="ms-auto",
                    navbar=True,
                ),
                id="navbar-collapse",
                navbar=True,
            ),
        ]
    ),
    color="dark",
    dark=True,
    sticky="top",
)

footer = dbc.Container(
    dbc.Row(
        dbc.Col(
            html.P(
                [
                    html.Span("Documentation", className="me-2"),
                    html.A("Link 1", href="#", className="me-2"),
                    html.A("Link 2", href="#", className="me-2"),
                ],
                className="text-center",
            )
        )
    ),
    fluid=True,
    className="bg-dark text-light mt-5 p-3",
)

# Layouts for different steps
def get_step1_layout():
    # Calculate the initial affected region as a rotated rectangle (200m x 200m)
    polygon_points = rotate_and_map_points(initial_center['lat'], initial_center['lng'], initial_wind_dir)

    affected_region = dl.Polygon(positions=polygon_points, color="red", fillOpacity=0.2, id="affected-region")

    return dbc.Container(
        [
            html.H2("Step 1: Select a City Quarter"),
            html.P("Move the map to position the 200m x 200m area over the desired region."),
            dl.Map(center=initial_center, zoom=16, scrollWheelZoom='center', style={'width': '100%', 'height': '500px'}, id="map", children=[
                dl.TileLayer(),
                dl.LayerGroup(id="layer", children=[affected_region])
            ]),
            dcc.Store(id="stored-center", data=initial_center),
            dcc.Store(id="zoom-level-store", data=16),  # Store the initial zoom level            
            html.Br(),
            html.Div(id="selected-area", style={"marginTop": "20px"}),
            html.Div(id="gis-data-output", style={"marginTop": "20px"}),
            dbc.Label("Wind Direction"),
            dcc.Slider(
                id="wind-direction-slider",
                min=0,
                max=360,
                step=1,
                value=initial_wind_dir,
                marks={0: 'N', 90: 'E', 180: 'S', 270: 'W'},
                tooltip={"placement": "bottom", "always_visible": True}
            ),
            dbc.Button("Next Step", id={'type': 'next-step', 'index': 1}, color="primary", disabled=False),
        ],
        className="mt-4",
    )

def get_step2_layout():
    return dbc.Container(
        [
            html.H2("Step 2: Run Optimization"),
            dcc.Dropdown(id='morph-features', options=[{'label': 'Feature 1', 'value': 'feature1'}, {'label': 'Feature 2', 'value': 'feature2'}], value='feature1'),
            dbc.Button("Run Optimization", id="run-optimization-button", color="primary"),
            html.Div(id='optimization-view', style={'margin-top': '20px'}),
            html.Br(),
            dbc.Button("Next Step", id={'type': 'next-step', 'index': 2}, color="primary"),
            dbc.Button("Previous Step", id={'type': 'previous-step', 'index': 2}, color="secondary", className="ms-2"),
        ],
        className="mt-4",
    )

def get_step3_layout():
    return dbc.Container(
        [
            html.H2("Step 3: Analyze and Cluster Designs"),
            dcc.Dropdown(id='selected-design', options=[{'label': f'Design {i}', 'value': i} for i in range(10)], value=0),
            dbc.Button("Analyze Design", id="analyze-design-button", color="primary"),
            html.Div(id='analysis-view', style={'margin-top': '20px'}),
            html.Br(),
            dbc.Button("Next Step", id={'type': 'next-step', 'index': 3}, color="primary"),
            dbc.Button("Previous Step", id={'type': 'previous-step', 'index': 3}, color="secondary", className="ms-2"),
        ],
        className="mt-4",
    )

def get_step4_layout():
    return dbc.Container(
        [
            html.H2("Step 4: Compare Designs"),
            dcc.Dropdown(id='compare-designs', options=[{'label': f'Design {i}', 'value': i} for i in range(10)], multi=True),
            dbc.Button("Compare", id="compare-button", color="primary"),
            html.Div(id='compare-view', style={'margin-top': '20px'}),
            html.Br(),
            dbc.Button("Previous Step", id={'type': 'previous-step', 'index': 4}, color="secondary", className="ms-2"),
        ],
        className="mt-4",
    )

# App layout with header, footer, and dynamic content
app.layout = html.Div([
    dcc.Location(id='url', refresh=False),
    header,
    html.Div(id='page-content'),
    footer
])

# Callback to handle navigation between steps and dynamically load content
@app.callback(
    Output('page-content', 'children'),
    Input('url', 'pathname')
)
def display_page(pathname):
    if pathname == '/step2':
        return get_step2_layout()
    elif pathname == '/step3':
        return get_step3_layout()
    elif pathname == '/step4':
        return get_step4_layout()
    else:
        return get_step1_layout()

# Callback to update the map
@app.callback(
    [Output("selected-area", "children"),
     Output("gis-data-output", "children"),
     Output("layer", "children"),
     Output("stored-center", "data"),  
     Output("map", "center"),  
     Output("zoom-level-store", "data")],  # Store the current zoom level
    [Input("map", "center"), Input("wind-direction-slider", "value"), Input("map", "zoom")],
    [State("stored-center", "data"), State("zoom-level-store", "data")]
)
def update_map(center, wind_dir, zoom, stored_center, previous_zoom):    

    if zoom != previous_zoom:
        # If the zoom level changed, it means we're zooming, so keep the stored center
        lat, lon = stored_center['lat'], stored_center['lng']
    else:
        # If the zoom level hasn't changed, we're panning, so update the stored center
        lat, lon = center['lat'], center['lng']

    # Calculate the rotated and mapped rectangle points based on the current wind direction
    polygon_points = rotate_and_map_points(lat, lon, wind_dir)

    coordinates_text = f"Selected area coordinates: {polygon_points}"

    # Mock loading of GIS data
    gis_data = f"Mocked GIS data for area with coordinates: {polygon_points}"
    gis_data_text = f"GIS Data Loaded: {gis_data}"

    # Create the polygon layer
    affected_region = dl.Polygon(positions=polygon_points, color="red", fillOpacity=0.2, id="affected-region")

    # Combine all layers
    layers = [affected_region, generate_grid_overlay(polygon_points)]
    
    # Return updated information, polygon, stored center, and the new zoom level
    return coordinates_text, gis_data_text, layers, {"lat": lat, "lng": lon}, {"lat": lat, "lng": lon}, zoom

# Callbacks for navigation buttons using pattern matching
@app.callback(
    Output('url', 'pathname'),
    Input({'type': 'next-step', 'index': ALL}, 'n_clicks'),
    Input({'type': 'previous-step', 'index': ALL}, 'n_clicks'),
    State('url', 'pathname'),
)
def navigate_steps(next_steps, previous_steps, pathname):
    ctx = dash.callback_context

    if not ctx.triggered:
        return pathname

    button_id = ctx.triggered[0]['prop_id'].split('.')[0]
    if 'next-step' in button_id:
        if pathname == '/':
            return '/step2'
        elif pathname == '/step2':
            return '/step3'
        elif pathname == '/step3':
            return '/step4'
    elif 'previous-step' in button_id:
        if pathname == '/step4':
            return '/step3'
        elif pathname == '/step3':
            return '/step2'
        elif pathname == '/step2':
            return '/'
    return pathname

# Callbacks for backend interactions
@app.callback(
    Output('optimization-view', 'children'),
    Input('run-optimization-button', 'n_clicks'),
    State('morph-features', 'value')
)
def update_optimization_view(n_clicks, morph_features):
    if n_clicks is None:
        return None
    optimization_result = run_optimization(morph_features)
    fig = px.imshow(optimization_result.mean(axis=0), title=f'Optimization Results for {morph_features}')
    return dcc.Graph(figure=fig)

@app.callback(
    Output('analysis-view', 'children'),
    Input('analyze-design-button', 'n_clicks'),
    State('selected-design', 'value')
)
def update_analysis_view(n_clicks, selected_design):
    if n_clicks is None:
        return None
    airflow = predict_airflow(selected_design)
    fig = px.imshow(airflow, title=f'Airflow Prediction for Design {selected_design}')
    return dcc.Graph(figure=fig)

@app.callback(
    Output('compare-view', 'children'),
    Input('compare-button', 'n_clicks'),
    State('compare-designs', 'value')
)
def update_compare_view(n_clicks, compare_designs):
    if n_clicks is None:
        return None
    comparison_data = [predict_airflow(design) for design in compare_designs]
    figs = [dcc.Graph(figure=px.imshow(data, title=f'Design {design}')) for design, data in zip(compare_designs, comparison_data)]
    return html.Div(figs)

# Run the app
if __name__ == '__main__':
    app.run_server(debug=True)
