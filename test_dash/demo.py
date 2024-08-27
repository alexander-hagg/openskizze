import dash
from dash import dcc, html, Input, Output, State, ALL
import dash_bootstrap_components as dbc
import dash_leaflet as dl
import plotly.express as px

# Import internals from other files
from utils import rotate_and_map_points, find_nearest_grid_point
from api_calls import run_optimization, predict_airflow

# Initial center coordinates
initial_center = {"lat": 50.734965, "lng": 7.055020}
initial_wind_dir = 180  # South wind

# Initialize the Dash app with Bootstrap CSS and suppress callback exceptions
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP], suppress_callback_exceptions=True)

def generate_grid_overlay(polygon_points, num_grid_lines = 20):
    """ Generate a grid overlay within the selected rectangle bounds, properly aligned with the rotated rectangle. """
    grid_lines = []
    
    # Define the grid lines within the bounds of the rotated rectangle
    for i in range(1, num_grid_lines):
        # Horizontal lines
        start_lat = polygon_points[0][0] + i * (polygon_points[1][0] - polygon_points[0][0]) / num_grid_lines
        start_lon = polygon_points[0][1] + i * (polygon_points[1][1] - polygon_points[0][1]) / num_grid_lines
        end_lat = polygon_points[3][0] + i * (polygon_points[2][0] - polygon_points[3][0]) / num_grid_lines
        end_lon = polygon_points[3][1] + i * (polygon_points[2][1] - polygon_points[3][1]) / num_grid_lines

        grid_lines.append(dl.Polyline(positions=[
            [start_lat, start_lon],
            [end_lat, end_lon]
        ], color="blue", weight=0.5))

        # Vertical lines
        start_lat = polygon_points[0][0] + i * (polygon_points[3][0] - polygon_points[0][0]) / num_grid_lines
        start_lon = polygon_points[0][1] + i * (polygon_points[3][1] - polygon_points[0][1]) / num_grid_lines
        end_lat = polygon_points[1][0] + i * (polygon_points[2][0] - polygon_points[1][0]) / num_grid_lines
        end_lon = polygon_points[1][1] + i * (polygon_points[2][1] - polygon_points[1][1]) / num_grid_lines

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
            dbc.Button("Next Step", id={'type': 'next-step', 'index': 1}, color="primary", disabled=False),
            html.Br(),
            html.Br(),
            html.H2("Step 1: Select a City Quarter"),
            html.P("Move the map to position the 200m x 200m area over the desired region."),
            dl.Map(center=initial_center, zoom=16, scrollWheelZoom='center', style={'width': '100%', 'height': '500px'}, id="map", children=[
                dl.TileLayer(),
                dl.LayerGroup(id="layer", children=[affected_region])
            ]),
            dcc.Store(id="stored-center", data=initial_center),
            dcc.Store(id="zoom-level-store", data=16),  # Store the initial zoom level            
            dcc.Store(id="stored-polygon-coordinates"),  # Store for polygon coordinates            
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
        ],
        className="mt-4",
    )

def get_step2_layout():
    # Calculate the affected region and grid as in Step 1
    polygon_points = rotate_and_map_points(initial_center['lat'], initial_center['lng'], initial_wind_dir)
    affected_region = dl.Polygon(positions=polygon_points, color="red", fillOpacity=0.2, id="affected-region")
    grid_overlay = generate_grid_overlay(polygon_points, num_grid_lines=20)

    return dbc.Container(
        [
            dbc.Button("Previous Step", id={'type': 'previous-step', 'index': 2}, color="secondary", className="ms-2"),
            dbc.Button("Next Step", id={'type': 'next-step', 'index': 2}, color="primary"),
            html.Br(),
            html.Br(),
            html.H2("Step 2: Select Buildable Grid Cells"),
            html.P("Select the grid cells where building is allowed by clicking on them. Click again to deselect."),
            dl.Map(center=initial_center, zoom=16, scrollWheelZoom='center', style={'width': '100%', 'height': '500px'}, id="grid-map", children=[
                dl.TileLayer(),
                dl.LayerGroup(id="grid-layer", children=[affected_region, grid_overlay])
            ]),
            dcc.Store(id="stored-polygon-coordinates", data=polygon_points),
        ],
        className="mt-4",
    )

def get_step3_layout():
    return dbc.Container(
        [
            dbc.Button("Previous Step", id={'type': 'previous-step', 'index': 2}, color="secondary", className="ms-2"),
            dbc.Button("Next Step", id={'type': 'next-step', 'index': 2}, color="primary"),
            html.Br(),
            html.Br(),
            html.H2("Step 3: Run Optimization"),
            dcc.Dropdown(id='morph-features', options=[{'label': 'Feature 1', 'value': 'feature1'}, {'label': 'Feature 2', 'value': 'feature2'}], value='feature1'),
            dbc.Button("Run Optimization", id="run-optimization-button", color="primary"),
            html.Div(id='optimization-view', style={'margin-top': '20px'}),
            html.Br(),
        ],
        className="mt-4",
    )

def get_step4_layout():
    return dbc.Container(
        [
            dbc.Button("Previous Step", id={'type': 'previous-step', 'index': 3}, color="secondary", className="ms-2"),
            dbc.Button("Next Step", id={'type': 'next-step', 'index': 3}, color="primary"),
            html.Br(),
            html.Br(),
            html.H2("Step 4: Analyze and Cluster Designs"),
            dcc.Dropdown(id='selected-design', options=[{'label': f'Design {i}', 'value': i} for i in range(10)], value=0),
            dbc.Button("Analyze Design", id="analyze-design-button", color="primary"),
            html.Div(id='analysis-view', style={'margin-top': '20px'}),
            html.Br(),
        ],
        className="mt-4",
    )

def get_step5_layout():
    return dbc.Container(
        [
            dbc.Button("Previous Step", id={'type': 'previous-step', 'index': 4}, color="secondary", className="ms-2"),
            html.Br(),
            html.Br(),
            html.H2("Step 5: Compare Designs"),
            dcc.Dropdown(id='compare-designs', options=[{'label': f'Design {i}', 'value': i} for i in range(10)], multi=True),
            dbc.Button("Compare", id="compare-button", color="primary"),
            html.Div(id='compare-view', style={'margin-top': '20px'}),
            html.Br(),
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
    elif pathname == '/step5':
        return get_step5_layout()
    else:
        return get_step1_layout()

# Callback to update the map
@app.callback(
    [Output("selected-area", "children"),
     Output("gis-data-output", "children"),
     Output("layer", "children"),
     Output("stored-center", "data"),  
     Output("map", "center"),  
     Output("zoom-level-store", "data"),
     Output("stored-polygon-coordinates", "data")],  # Store the polygon coordinates
    [Input("map", "center"), Input("wind-direction-slider", "value"), Input("map", "zoom")],
    [State("stored-center", "data"), State("zoom-level-store", "data")]
)
def update_map(center, wind_dir, zoom, stored_center, previous_zoom, num_grid_lines=20):    

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
    layers = [affected_region, generate_grid_overlay(polygon_points, num_grid_lines)]
    
    # Return updated information, polygon, stored center, and the new zoom level, and the polygon coordinates
    return coordinates_text, gis_data_text, layers, {"lat": lat, "lng": lon}, {"lat": lat, "lng": lon}, zoom, polygon_points


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
        if pathname == '/step1' or pathname == '/':
            return '/step2'
        elif pathname == '/step2':
            return '/step3'
        elif pathname == '/step3':
            return '/step4'
        elif pathname == '/step4':
            return '/step5'
    elif 'previous-step' in button_id:
        if pathname == '/step5':
            return '/step4'
        elif pathname == '/step4':
            return '/step3'
        elif pathname == '/step3':
            return '/step2'
        elif pathname == '/step2':
            return '/step1'
    return pathname

@app.callback(
    Output("grid-layer", "children"),
    [Input("grid-map", "click_lat_lng"),
     Input("stored-polygon-coordinates", "data")],
    [State("grid-layer", "children")]
)
def update_grid_selection(click_lat_lng, polygon_points, existing_grid):
    print(f'click_lat_lng: {click_lat_lng}')  # Debugging print
    print(f'polygon_points: {polygon_points}')  # Debugging print

    if existing_grid is None:
        existing_grid = []

    if not polygon_points:
        return existing_grid

    if click_lat_lng:
        snapped_lat_lng = find_nearest_grid_point(click_lat_lng, polygon_points)
        clicked_cell = None

        for cell in existing_grid:
            if isinstance(cell, dl.CircleMarker) and cell['props']['center'] == snapped_lat_lng:
                clicked_cell = cell
                break

        if clicked_cell:
            existing_grid.remove(clicked_cell)
        else:
            new_cell = dl.CircleMarker(center=snapped_lat_lng, radius=5, color="green", fill=True, fillOpacity=0.6)
            existing_grid.append(new_cell)

    return [dl.Polygon(positions=polygon_points, color="red", fillOpacity=0.2, id="affected-region"),
            generate_grid_overlay(polygon_points, num_grid_lines=20)] + existing_grid




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
