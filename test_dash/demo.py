import dash
from dash import dcc, html, Input, Output, State, ALL
import dash_bootstrap_components as dbc
import dash_leaflet as dl
import plotly.graph_objs as go
import numpy as np
import plotly.express as px
import pandas as pd
import threading

# Import internals from other files
from utils import rotate_and_map_points, find_nearest_grid_point
from api_calls import run_optimization# , predict_airflow


# Initial center coordinates
initial_center = {"lat": 50.734965, "lng": 7.055020}
initial_wind_dir = 180  # South wind
progress = {'value': 0}
optimization_result = None 
measures_labels = None


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
            # dcc.Dropdown(id='morph-features', options=[{'label': 'Feature 1', 'value': 'feature1'}, {'label': 'Feature 2', 'value': 'feature2'}], value='feature1'),
            dbc.Button("Run Optimization", id="run-optimization-button", color="primary"),
            dcc.Interval(id='progress-interval', interval=1000, n_intervals=0, disabled=True),
            dbc.Progress(id="optimization-progress", value=0, striped=True, animated=True, style={"margin-top": "20px"}),
            html.Div(id='optimization-view', style={'margin-top': '20px'}),
            html.Br(),
        ],
        className="mt-4",
    )

def get_step4_layout():

    return dbc.Container(
        [

            # Interval component to check for optimization_result updates
            dcc.Interval(
                id='interval-component',
                interval=1000,  # in milliseconds (e.g., check every second)
                n_intervals=0,
                disabled=True  # Start as disabled
            ),
            
            dbc.Button("Previous Step", id={'type': 'previous-step', 'index': 3}, color="secondary", className="ms-2"),
            dbc.Button("Next Step", id={'type': 'next-step', 'index': 3}, color="primary"),
            html.Br(),
            html.Br(),
            html.H2("Step 4: Analyze and Cluster Designs"),
           
            # Existing Dropdown and Button
            dbc.Button("Show Designs", id="analyze-design-button", color="primary"),
            html.Div(id='analysis-view', style={'margin-top': '20px'}),
            
            html.Br(),
            html.H3("Visualization of All Solutions' Height Maps"),
            
            # Dropdowns for selecting measure dimensions
            dbc.Row(
                [
                    dbc.Col(
                        [
                            html.Label("Select X-axis Measure"),
                            dcc.Dropdown(
                                id='measure-x',
                                options=[],  # To be populated dynamically
                                value=None  # Default to first measure
                            )
                        ],
                        width=6
                    ),
                    dbc.Col(
                        [
                            html.Label("Select Y-axis Measure"),
                            dcc.Dropdown(
                                id='measure-y',
                                options=[],  # To be populated dynamically
                                value=None  # Default to second measure
                            )
                        ],
                        width=6
                    ),
                ],
                className="mb-4",
            ),
            
            # Container for the grid of height maps
            html.Div(id='height-maps-grid', style={'display': 'flex', 'flexWrap': 'wrap', 'gap': '10px'}),
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





def run_optimization_in_background():
    global progress, optimization_result, measures_labels

    def progress_callback(current_iteration, total_iterations):
        progress['value'] = int((current_iteration / total_iterations) * 100)
    
    # Run optimization (this function call is blocking, so it's run in a separate thread)
    optimization_result, measures_labels = run_optimization(progress_callback)

def start_optimization():
    optimization_thread = threading.Thread(target=run_optimization_in_background)
    # , args=(morph_features,)
    optimization_thread.start()

# Callbacks for backend interactions
@app.callback(
    [Output('optimization-progress', 'value'),
     Output('optimization-view', 'children'),
     Output('progress-interval', 'disabled'),],
    [Input('run-optimization-button', 'n_clicks'),
     Input('progress-interval', 'n_intervals')],
    # State('morph-features', 'value'),
    prevent_initial_call=True
)
def update_optimization_view(n_clicks, n_intervals): 
    global progress, optimization_result

    if n_clicks is not None and n_intervals == 0:
        # Start the optimization in a background thread
        start_optimization()
        return 0, dash.no_update, False

    if n_intervals > 0:
        # Update the progress bar with the current progress
        if progress['value'] == 100:
            # Optimization is complete, display the results
            dat = optimization_result.data()
            df = pd.DataFrame({
                'feat1': dat['measures'][:, 0], 
                'feat2': dat['measures'][:, 1], 
                'feat3': dat['measures'][:, 2], 
                'feat4': dat['measures'][:, 3], 
                'objective': dat['objective']
            })
            fig = px.parallel_coordinates(df, color="objective", labels={
                "feat1": measures_labels[0],
                "feat2": measures_labels[1],
                "feat3": measures_labels[2],
                "feat4": measures_labels[3],
                "objective": "Objective"
            },
            color_continuous_scale=px.colors.diverging.Tealrose,
            color_continuous_midpoint=2)
            
            return 100, dcc.Graph(figure=fig), True  # Stop the interval and display results

        return progress['value'], dash.no_update, False

    return dash.no_update, dash.no_update, True



@app.callback(
    Output('compare-view', 'children'),
    Input('compare-button', 'n_clicks'),
    State('compare-designs', 'value')
)
def update_compare_view(n_clicks, compare_designs):
    if n_clicks is None:
        return None
    # comparison_data = [predict_airflow(design) for design in compare_designs]
    comparison_data = [0 for design in compare_designs]
    figs = [dcc.Graph(figure=px.imshow(data, title=f'Design {design}')) for design, data in zip(compare_designs, comparison_data)]
    return html.Div(figs)


# @app.callback(
#     Output('analysis-view', 'children'),
#     Input('analyze-design-button', 'n_clicks'),
#     State('selected-design', 'value')
# )

@app.callback(
    Output('height-maps-grid', 'children'),
    [
        Input('measure-x', 'value'),
        Input('measure-y', 'value'),
        Input('analyze-design-button', 'n_clicks'),
    ]
)
def update_height_maps_grid(measure_x, measure_y, n_clicks):
    global optimization_result, measures_labels
    if n_clicks is None:
        return None    
    if not optimization_result:
        return "No optimization_result available."
    
    dat = optimization_result.data()
    
    measures = dat['measures']
    solutions = dat['solution']
    heightmaps = dat['heightmaps']
    
    if isinstance(measures, np.ndarray):
        measure_x_values = [m[measure_x] for m in measures]
        measure_y_values = [m[measure_y] for m in measures]
    else:
        return "Invalid measures format."
    
    # Convert floating point measures to integers for grid positioning
    # Normalize measures to a grid size, e.g., 10x10
    grid_size = 10
    x_min, x_max = min(measure_x_values), max(measure_x_values)
    y_min, y_max = min(measure_y_values), max(measure_y_values)
    
    def normalize(value, min_val, max_val):
        if max_val - min_val == 0:
            return 0
        return int(((value - min_val) / (max_val - min_val)) * (grid_size - 1))
    
    positions = [
        (normalize(x, x_min, x_max), normalize(y, y_min, y_max))
        for x, y in zip(measure_x_values, measure_y_values)
    ]
    
    # Create a dictionary to hold grid cells
    grid_cells = {}
    for pos, sol_idx in zip(positions, range(len(solutions))):
        row, col = pos
        key = (row, col)
        if key not in grid_cells:
            grid_cells[key] = []
        grid_cells[key].append(sol_idx)
    
    # Generate grid layout
    grid_children = []
    for row in range(grid_size):
        for col in range(grid_size):
            sols_in_cell = grid_cells.get((row, col), [])
            if sols_in_cell:
                # Display thumbnails of height maps
                thumbnails = []
                for sol_idx in sols_in_cell:
                    solution = dat['solution'][sol_idx]
                    height_map = dat['heightmaps'][sol_idx]
                    nrows = np.sqrt(height_map.size).astype(int)
                    height_map = height_map.reshape(nrows,nrows)

                    # Convert height_map to an image using Plotly
                    fig = px.imshow(height_map, color_continuous_scale='Greys', aspect='auto')
                    fig.update_layout(
                        margin=dict(l=0, r=0, t=0, b=0),
                        coloraxis_showscale=False
                    )
                    fig.update_xaxes(showticklabels=False).update_yaxes(showticklabels=False)
                    
                    thumbnail = dcc.Graph(
                        figure=fig,
                        style={'height': '100px', 'width': '100px', 'display': 'inline-block'}
                    )
                    thumbnails.append(thumbnail)
                
                grid_children.append(
                    dbc.Card(
                        dbc.CardBody(thumbnails),
                        style={'width': '120px', 'height': '120px', 'overflow': 'auto'}
                    )
                )
            else:
                # Empty cell
                grid_children.append(
                    dbc.Card(
                        dbc.CardBody(""),
                        style={'width': '120px', 'height': '120px', 'backgroundColor': '#f8f9fa'}
                    )
                )
    
    # Arrange the grid using CSS Grid
    grid_style = {
        'display': 'grid',
        'gridTemplateColumns': f'repeat({grid_size}, 120px)',
        'gridGap': '10px',
        'justifyContent': 'center'
    }
    
    return html.Div(grid_children, style=grid_style)

@app.callback(
    [
        Output('measure-x', 'options'),
        Output('measure-x', 'value'),
        Output('measure-y', 'options'),
        Output('measure-y', 'value'),
        Output('interval-component', 'disabled')  # Disable the interval once data is loaded
    ],
    Input('interval-component', 'n_intervals')
)
def populate_measure_dropdowns(n_intervals):
    global optimization_result, measures_labels
    if optimization_result is None:
        # Data not ready yet; keep interval running
        return [], None, [], None, False  # Not disabled
    else:
        # Create dropdown options with separate 'label' and 'value'
        print(measures_labels)
        options = [{'label': label, 'value': idx} for idx, label in enumerate(measures_labels)]
        
        # Set default values to the first two measures, if available
        default_x = 0
        default_y = 1
        
        # Disable the interval since data is now available
        return options, default_x, options, default_y, True
        

# Run the app
if __name__ == '__main__':
    app.run_server(debug=True)
