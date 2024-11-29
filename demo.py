import numpy as np
import pandas as pd

import dash
from dash import dcc, ctx, html, Input, Output, State, ALL
import dash_bootstrap_components as dbc
import dash_leaflet as dl
from dash_extensions.javascript import assign

import plotly.graph_objs as go
import plotly.express as px

import json
import base64
import pickle
import threading

# Import internals from other files
from utils import rotate_and_map_points, find_nearest_grid_point, generate_grid_overlay
from api_calls import run_optimization


# Initial center coordinates
initial_center = {"lat": 50.734965, "lng": 7.055020}
initial_wind_dir = 180  # South wind
progress = {'value': 0}
result_archive = None 
measures_labels = None


# Initialize the Dash app with Bootstrap CSS and suppress callback exceptions
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP], suppress_callback_exceptions=True)

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

# App layout with header, footer, and dynamic content
app.layout = html.Div([
    dcc.Location(id='url', refresh=False),
    header,
    html.Div(id='page-content'),
    dcc.Store(id="stored-grid-size", data=100),  # Default grid size
    dcc.Store(id="stored-polygon-coordinates", data=None),  # Default empty polygon coordinates
    dcc.Store(id="grid-matrix", data=None),
    footer
])

@app.callback(
    Output('page-content', 'children'),
    [Input('url', 'pathname')],
    [State('stored-grid-size', 'data'),
     State('stored-polygon-coordinates', 'data')]
)
def display_page(pathname, grid_size, polygon_points):
    # Default polygon points if not yet defined
    if not polygon_points:
        polygon_points = rotate_and_map_points(initial_center['lat'], initial_center['lng'], initial_wind_dir, grid_size)

    if pathname == '/step2':
        return get_step2_layout(grid_size, polygon_points)
    elif pathname == '/step3':
        return get_step3_layout(grid_size, polygon_points)
    elif pathname == '/step4':
        return get_step4_layout(grid_size, polygon_points)
    elif pathname == '/step5':
        return get_step5_layout(grid_size, polygon_points)
    else:
        return get_step1_layout(grid_size, polygon_points)


#####################################################################################
# Layouts for each step
#####################################################################################

def get_step1_layout(grid_size, polygon_points):
    polygon_points = rotate_and_map_points(initial_center['lat'], initial_center['lng'], initial_wind_dir, grid_size)

    affected_region = dl.Polygon(positions=polygon_points, color="red", fillOpacity=0.2, id="affected-region")

    return dbc.Container(
        [
            dbc.Button("Next Step", id={'type': 'next-step', 'index': 1}, color="primary", disabled=False),
            html.Br(),
            html.Br(),
            html.H2("Step 1: Select a City Quarter"),
            html.P(
                id="grid-size-text",
                children=f"Move the map to position the {grid_size}m x {grid_size}m area over the desired region."
            ),
            dl.Map(center=initial_center, zoom=16, scrollWheelZoom='center', style={'width': '100%', 'height': '500px'}, id="map", children=[
                dl.TileLayer(),
                dl.LayerGroup(id="layer", children=[affected_region, generate_grid_overlay(polygon_points, grid_size)])
            ]),
            dbc.Row([
                dbc.Col(dbc.Label("Set Square Grid Size (meters):")),
                dbc.Col(dcc.Input(id="grid-size-input", type="number", value=grid_size, min=10, step=10)),
                dbc.Col(dbc.Button("Reset to Default", id="reset-grid-size", color="secondary")),
                dbc.Col(dbc.Button("Save Grid", id="save-grid-btn", color="success", style={"marginLeft": "10px"}))  # Save Grid Button                
            ]),
            dcc.Store(id="stored-center", data=initial_center),
            dcc.Store(id="zoom-level-store", data=16),
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


def get_step2_layout(grid_size, polygon_points):
    # Assign style to selected cells
    style_handle = assign("""function(feature, context){
        const {selected} = context.hideout;
        if(selected.includes(feature.properties.name)){
            return {fillColor: 'red', color: 'grey'}
        }
        return {fillColor: 'grey', color: 'grey'}
    }""")

    # Calculate the center of the polygon
    lat_min, lon_min = polygon_points[0]
    lat_max, lon_max = polygon_points[2]
    center_lat = (lat_min + lat_max) / 2
    center_lon = (lon_min + lon_max) / 2

    # Calculate the number of grid cells
    print(f'Step 2. grid size: {grid_size}')
    
    return dbc.Container(
        [
            dbc.Button("Previous Step", id={'type': 'previous-step', 'index': 2}, color="secondary", className="ms-2"),
            dbc.Button("Next Step", id={'type': 'next-step', 'index': 2}, color="primary"),
            html.Br(),
            html.Br(),
            html.H2("Step 2: Select Buildable Grid Cells"),
            html.P("Click on a cell or drag a selection to toggle buildable areas."),
            dl.Map(
                center=[center_lat, center_lon],
                zoom=16,
                dragging=False,  # Disable dragging
                doubleClickZoom=False,  # Disable double-click zoom
                scrollWheelZoom=True,  # Disable scroll wheel zoom
                style={'width': '100%', 'height': '500px'},
                id="grid-map",
                children=[
                    dl.TileLayer(),
                    dl.GeoJSON(
                        url="/assets/selected_grid.json",
                        zoomToBounds=True,
                        id="geojson",
                        hideout=dict(selected=[]),
                        style=style_handle
                    ),
                ],
            ),
            # dbc.Button("Save as PBM", id="save-pbm-btn", color="primary", style={"marginTop": "10px"}),            
        ],
        className="mt-4",
    )




def get_step3_layout(grid_size, polygon_points):
    return dbc.Container(
        [
            dbc.Button("Previous Step", id={'type': 'previous-step', 'index': 2}, color="secondary", className="ms-2"),
            dbc.Button("Next Step", id={'type': 'next-step', 'index': 2}, color="primary"),
            html.Br(),
            html.Br(),
            html.H2("Step 3: Run Optimization"),
            html.P("The grid matrix has been loaded. You can now proceed with the optimization."),
            html.Div(id="matrix-output"),  # For debugging or visualization
            dcc.Store(id="grid-matrix"),  # Include the grid matrix
            dbc.Button("Run Optimization", id="run-optimization-button", color="primary"),
            dcc.Interval(id='progress-interval', interval=1000, n_intervals=0, disabled=True),
            dbc.Progress(id="optimization-progress", value=0, striped=True, animated=True, style={"margin-top": "20px"}),
            html.Div(id='optimization-view', style={'margin-top': '20px'}),
            html.Br(),
            # New addition for loading previous results
            html.H5("Load Previous Optimization Run"),
            dcc.Upload(
                id='upload-optimization-file',
                children=html.Div([
                    'Drag and Drop or ',
                    html.A('Select a File')
                ]),
                style={
                    'width': '100%',
                    'height': '60px',
                    'lineHeight': '60px',
                    'borderWidth': '1px',
                    'borderStyle': 'dashed',
                    'borderRadius': '5px',
                    'textAlign': 'center',
                    'margin': '10px'
                },
                multiple=False
            ),
            html.Div(id='file-upload-feedback', style={'margin-top': '10px'}),
        ],
        className="mt-4",
    )


def get_step4_layout(grid_size, polygon_points):

    return dbc.Container(
        [

            # Interval component to check for result_archive updates
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

def get_step5_layout(grid_size, polygon_points):
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


#####################################################################################
# Callback functions
#####################################################################################

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

#####################################################################################
# Step 1 callback functions
#####################################################################################

@app.callback(
    [Output("selected-area", "children"),
     Output("gis-data-output", "children"),
     Output("layer", "children"),
     Output("stored-center", "data"),  
     Output("map", "center"),  
     Output("zoom-level-store", "data"),
     Output("stored-polygon-coordinates", "data")],  # Store the polygon coordinates
    [Input("map", "center"), Input("wind-direction-slider", "value"), Input("map", "zoom"), Input("grid-size-input", "value")],
    [State("stored-center", "data"), State("zoom-level-store", "data")]
)
def update_map(center, wind_dir, zoom, grid_size, stored_center, previous_zoom):    
    if grid_size is None:
        return "Invalid grid size.", "", [], stored_center, center, zoom, None
    if zoom != previous_zoom:
        # If the zoom level changed, it means we're zooming, so keep the stored center
        lat, lon = stored_center['lat'], stored_center['lng']
    else:
        # If the zoom level hasn't changed, we're panning, so update the stored center
        lat, lon = center['lat'], center['lng']

    # Calculate the rotated and mapped rectangle points based on the current wind direction
    polygon_points = rotate_and_map_points(lat, lon, wind_dir, grid_size)

    coordinates_text = f"Selected area coordinates: {polygon_points}"

    # Mock loading of GIS data
    gis_data = f"Mocked GIS data for area with coordinates: {polygon_points}"
    gis_data_text = f"GIS Data Loaded: {gis_data}"

    # Create the polygon layer
    affected_region = dl.Polygon(positions=polygon_points, color="red", fillOpacity=0.2, id="affected-region")

    # Combine all layers
    layers = [affected_region, generate_grid_overlay(polygon_points, grid_size)]
    
    # Return updated information, polygon, stored center, and the new zoom level, and the polygon coordinates
    return coordinates_text, gis_data_text, layers, {"lat": lat, "lng": lon}, {"lat": lat, "lng": lon}, zoom, polygon_points

@app.callback(
    [Output("grid-size-text", "children", allow_duplicate=True),
     Output("stored-grid-size", "data", allow_duplicate=True),
     Output("layer", "children", allow_duplicate=True),
     Output("grid-matrix", "data")
     ],
    [Input("grid-size-input", "value"),
     Input("reset-grid-size", "n_clicks"),
     Input("wind-direction-slider", "value")],
    [State("stored-center", "data"), State("stored-grid-size", "data")],
    prevent_initial_call=True
)
def update_grid_size(grid_size, reset_clicks, wind_dir, stored_center, current_grid_size):
    ctx_trigger = ctx.triggered_id
    if ctx_trigger == "reset-grid-size":
        grid_size = 100  # Reset to default
    if grid_size is None:
        return "Invalid grid size.", current_grid_size, [], None
    grid_matrix = [[0] * grid_size for _ in range(grid_size)]  # 0 = empty, 1 = filled
    lat, lon = stored_center['lat'], stored_center['lng']
    polygon_points = rotate_and_map_points(lat, lon, wind_dir, grid_size)
    if polygon_points is None:
        return "Invalid grid size.", current_grid_size, [],

    grid_size_text = f"Move the map to position the {grid_size}m x {grid_size}m area over the desired region."
    affected_region = dl.Polygon(positions=polygon_points, color="red", fillOpacity=0.2, id="affected-region")
    grid_overlay = generate_grid_overlay(polygon_points, grid_size)

    current_grid_size = grid_size

    return grid_size_text, grid_size, [affected_region, grid_overlay] , grid_matrix

@app.callback(
    Output("selected-area", "children", allow_duplicate=True),
    [Input("save-grid-btn", "n_clicks")],
    [State("stored-polygon-coordinates", "data"),
     State("stored-grid-size", "data")],
    prevent_initial_call=True
)
def save_grid_as_geojson(n_clicks, polygon_points, grid_size):
    if not polygon_points:
        return "No grid to save."

    # Generate GeoJSON features for the grid cells
    num_cells = int(grid_size / 3) # One cell every 3 meters
    lat_min, lon_min = polygon_points[0]
    lat_max, lon_max = polygon_points[2]
    cell_size_lat = (lat_max - lat_min) / num_cells
    cell_size_lon = (lon_max - lon_min) / num_cells

    features = []
    for row in range(num_cells):
        for col in range(num_cells):
            cell = {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[
                        [lon_min + col * cell_size_lon, lat_min + row * cell_size_lat],
                        [lon_min + (col + 1) * cell_size_lon, lat_min + row * cell_size_lat],
                        [lon_min + (col + 1) * cell_size_lon, lat_min + (row + 1) * cell_size_lat],
                        [lon_min + col * cell_size_lon, lat_min + (row + 1) * cell_size_lat],
                        [lon_min + col * cell_size_lon, lat_min + row * cell_size_lat]
                    ]]
                },
                "properties": {"name": f"cell-{row}-{col}"}
            }
            features.append(cell)

    geojson = {
        "type": "FeatureCollection",
        "features": features
    }

    # Save to /assets/selected_grid.json
    with open("assets/selected_grid.json", "w") as f:
        json.dump(geojson, f)

    return "Grid saved to /assets/selected_grid.json."


#####################################################################################
# Step 2 callback functions
#####################################################################################

@app.callback(
    Output("geojson", "hideout"),
    Input("geojson", "n_clicks"),
    State("geojson", "clickData"),
    State("geojson", "hideout"),
    prevent_initial_call=True
)
def toggle_geojson_cell(n_clicks, click_data, hideout):
    if click_data is None:
        return hideout

    selected = hideout.get("selected", [])
    clicked_name = click_data["properties"]["name"]

    if clicked_name in selected:
        selected.remove(clicked_name)  # Deselect if already selected
    else:
        selected.append(clicked_name)  # Select otherwise

    # Save the updated GeoJSON file
    with open("assets/selected_grid.json", "r") as f:
        geojson = json.load(f)

    for feature in geojson["features"]:
        feature_name = feature["properties"]["name"]
        feature["properties"]["selected"] = feature_name in selected

    with open("assets/selected_grid.json", "w") as f:
        json.dump(geojson, f)

    return {"selected": selected}


#####################################################################################
# Step 3 callback functions
#####################################################################################

@app.callback(
    [Output('file-upload-feedback', 'children'),
     Output('optimization-view', 'children')],
    Input('upload-optimization-file', 'contents'),
    State('upload-optimization-file', 'filename'),
    prevent_initial_call=True
)
def load_optimization_file(contents, filename):
    global result_archive, measures_labels

    if not contents:
        return "No file selected.", dash.no_update

    content_type, content_string = contents.split(',')
    decoded = base64.b64decode(content_string)

    try:
        # Load the data using pickle
        loaded_data = pickle.loads(decoded)
        result_archive = loaded_data['data']
        measures_labels = loaded_data['measures_labels']

        # Show feedback and visualization of the loaded data
        df = pd.DataFrame(
            {f'feat{i+1}': result_archive.data()['measures'][:, i] for i in range(len(measures_labels))}
        )
        df['Objective'] = result_archive.data()['objective']
        labels = {f'feat{i+1}': label for i, label in enumerate(measures_labels)}
        labels['Objective'] = 'Objective'  # Label for the objective axis

        # Generate the parallel coordinates plot
        fig = px.parallel_coordinates(
            df,
            color="Objective",
            labels=labels,
            color_continuous_scale=px.colors.diverging.Tealrose,
            color_continuous_midpoint=df["Objective"].mean()
        )

        return f"Successfully loaded {filename}.", dcc.Graph(figure=fig)

    except Exception as e:
        return f"Error processing the file {filename}: {str(e)}", dash.no_update


@app.callback(
    [Output('optimization-progress', 'value'),
     Output('optimization-view', 'children', allow_duplicate=True),
     Output('progress-interval', 'disabled'),],
    [Input('run-optimization-button', 'n_clicks'),
     Input('progress-interval', 'n_intervals')],
    # State('morph-features', 'value'),
    prevent_initial_call=True
)
def update_optimization_view(n_clicks, n_intervals): 
    global progress, result_archive

    if n_clicks is not None and n_intervals == 0:
        # Start the optimization in a background thread

        # Load the GeoJSON file
        with open("assets/selected_grid.json", "r") as f:
            geojson = json.load(f)

        # Extract the selected cells
        selected_cells = [
            feature for feature in geojson["features"]
            if feature["properties"].get("selected", True)
        ]

        # Get the grid dimensions
        num_cells = len(geojson["features"])  # Assume square grid
        print(f'num_cells: {num_cells}')
        cell_dim = int(num_cells ** 0.5)      # Assume perfect square

        # Initialize the PBM matrix
        pbm_matrix = np.zeros((cell_dim, cell_dim), dtype=int)  # Default to 1 (white)

        # Update matrix based on selected cells
        for cell in selected_cells:
            name = cell["properties"]["name"]
            print(f'name: {name}')
            row, col = map(int, name.split("-")[1:])  # Extract row and col from name
            pbm_matrix[row, col] = 1  # Set selected cells to black (0)

        pbm_matrix = np.fliplr(pbm_matrix) # flip left-right to match the visualization
        # Save the PBM file
        pbm_path = "assets/selected_grid.pbm"
        with open(pbm_path, "wb") as f:
            f.write(f"P1\n{cell_dim} {cell_dim}\n".encode())  # PBM header
            np.savetxt(f, pbm_matrix, fmt="%d", delimiter="")

        print(f"PBM file saved to {pbm_path}")
        start_optimization()
        return 0, dash.no_update, False

    if n_intervals > 0:
        # Update the progress bar with the current progress
        if progress['value'] == 100:
            # Optimization is complete, display the results
            dat = result_archive.data()

            df = pd.DataFrame(
                    {f'feat{i+1}': dat['measures'][:, i] for i in range(len(measures_labels))}
            )
            df['Objective'] = dat['objective']
            labels = {f'feat{i+1}': label for i, label in enumerate(measures_labels)}
            labels['Objective'] = 'Objective'  # Label for the objective axis

            # Generate the parallel coordinates plot
            fig = px.parallel_coordinates(
                df,
                color="Objective",
                labels=labels,
                color_continuous_scale=px.colors.diverging.Tealrose,
                color_continuous_midpoint=df["Objective"].mean()
            )
            
            return 100, dcc.Graph(figure=fig), True  # Stop the interval and display results

        return progress['value'], dash.no_update, False

    return dash.no_update, dash.no_update, True

def run_optimization_in_background():
    global progress, result_archive, measures_labels

    def progress_callback(current_iteration, total_iterations):
        progress['value'] = int((current_iteration / total_iterations) * 100)
    
    # Run optimization (this function call is blocking, so it's run in a separate thread)
    result_archive, measures_labels = run_optimization(progress_callback=progress_callback)

    # Save result to file using pickle
    with open('last_optimization_run.pkl', 'wb') as f:
        pickle.dump({'data': result_archive, 'measures_labels': measures_labels}, f)

def start_optimization():
    optimization_thread = threading.Thread(target=run_optimization_in_background)
    optimization_thread.start()

#####################################################################################
# Step 4 callback functions
#####################################################################################

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
    global result_archive, measures_labels
    if result_archive is None:
        # Data not ready yet; keep interval running
        return [], None, [], None, False  # Not disabled
    else:
        # Create dropdown options with separate 'label' and 'value'
        options = [{'label': label, 'value': idx} for idx, label in enumerate(measures_labels)]
        
        # Set default values to the first two measures, if available
        default_x = 0
        default_y = 1
        
        # Disable the interval since data is now available
        return options, default_x, options, default_y, True

@app.callback(
    Output('height-maps-grid', 'children'),
    [
        Input('measure-x', 'value'),
        Input('measure-y', 'value'),
        Input('analyze-design-button', 'n_clicks'),
    ]
)
def update_height_maps_grid(measure_x, measure_y, n_clicks):
    global result_archive, measures_labels
    if n_clicks is None:
        return None    
    if not result_archive:
        return "No result_archive available."
    
    dat = result_archive.data()
    
    # Determine number of cells per dimension from boundaries
    num_cells_per_dim_x = len(result_archive.boundaries[measure_x]) - 1
    num_cells_per_dim_y = len(result_archive.boundaries[measure_y]) - 1
    visualization_grid_size_x = num_cells_per_dim_x
    visualization_grid_size_y = num_cells_per_dim_y
    
    measures = dat['measures']
    objective = dat['objective']
    solutions = dat['solution']
    heightmaps = dat['heightmaps']
    
    if isinstance(measures, np.ndarray):
        # Assuming measures is a 2D ndarray where each row corresponds to a solution
        measure_x_values = measures[:, measure_x]
        measure_y_values = measures[:, measure_y]
    else:
        return "Invalid measures format."
    
    # Retrieve boundaries for each measure
    boundaries_x = result_archive.boundaries[measure_x]
    boundaries_y = result_archive.boundaries[measure_y]
    
    # Assign measure values to grid cell indices using predefined boundaries
    measure_x_bins = boundaries_x
    measure_y_bins = boundaries_y
    
    measure_x_indices = np.digitize(measure_x_values, measure_x_bins, right=False) - 1
    measure_y_indices = np.digitize(measure_y_values, measure_y_bins, right=False) - 1
    
    # Ensure indices are within valid range
    measure_x_indices = np.clip(measure_x_indices, 0, visualization_grid_size_x - 1)
    measure_y_indices = np.clip(measure_y_indices, 0, visualization_grid_size_y - 1)
    
    # Map solutions to grid cells
    grid_cells = {}
    for row, col, sol_idx in zip(measure_y_indices, measure_x_indices, range(len(solutions))):
        key = (row, col)
        if key not in grid_cells:
            grid_cells[key] = []
        grid_cells[key].append(sol_idx)
    
    # Generate grid layout
    grid_children = []
    for row in range(visualization_grid_size_y):
        for col in range(visualization_grid_size_x):
            sols_in_cell = grid_cells.get((row, col), [])
            if sols_in_cell:
                # Select best solution in the cell based on objective
                best_id_in_cell = sols_in_cell[np.argmax(objective[sols_in_cell])]
                height_map = heightmaps[best_id_in_cell]
                
                # If height_map is not already a 2D array, reshape it
                if height_map.ndim != 2:
                    nrows = int(np.sqrt(height_map.size))
                    height_map = height_map.reshape(nrows, nrows)
                
                # Check if all values are zero
                if np.all(height_map == 0):
                    # Define a single-color scale mapping to white
                    color_scale = [
                        [0.0, 'white'],
                        [1.0, 'white']
                    ]
                else:
                    color_scale = 'Greys'

                # Convert height_map to an image using Plotly
                fig = px.imshow(height_map, color_continuous_scale=color_scale, aspect='auto')
                fig.update_layout(
                    margin=dict(l=0, r=0, t=0, b=0),
                    coloraxis_showscale=False
                )
                fig.update_xaxes(showticklabels=False).update_yaxes(showticklabels=False)
                
                thumbnail = dcc.Graph(
                    figure=fig,
                    style={'height': '100px', 'width': '100px', 'display': 'inline-block'}
                )
                
                grid_children.append(
                    dbc.Card(
                        dbc.CardBody(thumbnail),
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
        'gridTemplateColumns': f'repeat({visualization_grid_size_x}, 120px)',
        'gridGap': '10px',
        'justifyContent': 'center'
    }
    
    return html.Div(grid_children, style=grid_style)


# Run the app
if __name__ == '__main__':
    app.run_server(debug=True)
