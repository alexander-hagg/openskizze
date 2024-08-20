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


def rotate_and_elongate_polygon(center_lat, center_lon, wind_dir, initial_length=100, elongation_factor=2):
    # Convert wind direction to radians
    wind_dir_rad = np.radians(wind_dir)
    
    # Calculate the original rectangle's dimensions (before rotation)
    lat_delta, lon_delta = meters_to_lat_lon(center_lat, center_lon, initial_length)
    
    # Calculate the elongation based on the elongation factor
    elongated_lat_delta, elongated_lon_delta = meters_to_lat_lon(center_lat, center_lon, initial_length * elongation_factor)

    # Calculate rotated polygon corners
    sin_wind_dir = np.sin(wind_dir_rad)
    cos_wind_dir = np.cos(wind_dir_rad)

    # Four corners of the polygon
    top_left = [center_lat - lat_delta * cos_wind_dir + lon_delta * sin_wind_dir, 
                center_lon - lat_delta * sin_wind_dir - lon_delta * cos_wind_dir]

    top_right = [center_lat - lat_delta * cos_wind_dir - lon_delta * sin_wind_dir, 
                 center_lon - lat_delta * sin_wind_dir + lon_delta * cos_wind_dir]

    bottom_right = [center_lat + elongated_lat_delta * cos_wind_dir - elongated_lon_delta * sin_wind_dir, 
                    center_lon + elongated_lat_delta * sin_wind_dir + elongated_lon_delta * cos_wind_dir]

    bottom_left = [center_lat + elongated_lat_delta * cos_wind_dir + elongated_lon_delta * sin_wind_dir, 
                   center_lon + elongated_lat_delta * sin_wind_dir - elongated_lon_delta * cos_wind_dir]

    # Return the list of corners to form the polygon
    return [top_left, top_right, bottom_right, bottom_left]

def generate_grid_overlay(bounds):
    """ Generate a grid overlay within the selected rectangle bounds. """
    lat_start, lon_start = bounds[0]
    lat_end, lon_end = bounds[1]
    grid_lines = []

    # Create horizontal and vertical lines for the grid
    num_lines = 20  # Example: 20x20 grid (every 10 m)
    lat_step = (lat_end - lat_start) / num_lines
    lon_step = (lon_end - lon_start) / num_lines

    for i in range(1, num_lines):
        grid_lines.append(dl.Polyline(positions=[
            [lat_start + i * lat_step, lon_start],
            [lat_start + i * lat_step, lon_end]
        ], color="blue", weight=0.5))
        grid_lines.append(dl.Polyline(positions=[
            [lat_start, lon_start + i * lon_step],
            [lat_end, lon_start + i * lon_step]
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
    # Calculate the initial affected region as a polygon
    polygon_points = rotate_and_elongate_polygon(initial_center['lat'], initial_center['lng'], initial_wind_dir)

    affected_region = dl.Polygon(positions=polygon_points, color="red", fillOpacity=0.2, id="affected-region")

    return dbc.Container(
        [
            html.H2("Step 1: Select a City Quarter"),
            html.P("Move the map to position the 200m x 200m area over the desired region."),
            dl.Map(center=initial_center, zoom=16, style={'width': '100%', 'height': '500px'}, id="map", children=[
                dl.TileLayer(),
                dl.LayerGroup(id="layer", children=[affected_region])
            ]),
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

# Callback to capture the rectangle selection and retrieve GIS data
@app.callback(
    [Output("selected-area", "children"),
     Output("gis-data-output", "children"),
     Output("layer", "children")],
    [Input("map", "center"), Input("wind-direction-slider", "value")]
)
def update_map(center, wind_dir):
    if not center:
        raise dash.exceptions.PreventUpdate
    
    # Extract latitude and longitude from the center
    if isinstance(center, dict) and 'lat' in center and 'lng' in center:
        lat, lon = center['lat'], center['lng']
    else:
        raise dash.exceptions.PreventUpdate

    # Calculate the rotated rectangle points based on the current wind direction
    polygon_points = rotate_and_elongate_polygon(lat, lon, wind_dir)

    coordinates_text = f"Selected area coordinates: {polygon_points}"

    # Mock loading of GIS data
    gis_data = f"Mocked GIS data for area with coordinates: {polygon_points}"
    gis_data_text = f"GIS Data Loaded: {gis_data}"

    # Create the polygon layer
    affected_region = dl.Polygon(positions=polygon_points, color="red", fillOpacity=0.2, id="affected-region")

    # Combine all layers
    layers = [affected_region]

    return coordinates_text, gis_data_text, layers

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
