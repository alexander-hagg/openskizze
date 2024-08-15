import dash
from dash import dcc, html, Input, Output, State, ALL
import dash_bootstrap_components as dbc
import dash_leaflet as dl
import dash_leaflet.express as dlx
import numpy as np
import plotly.express as px
import time
import math

# Initialize the Dash app with Bootstrap CSS and suppress callback exceptions
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP], suppress_callback_exceptions=True)

# Mock functions for the back-end processes
def load_geodata(coordinates):
    # Mocking a delay for data retrieval
    time.sleep(2)
    return f"Mocked GIS data for area with coordinates: {coordinates}"

def run_optimization(morph_features):
    return np.random.rand(10, 10, 10)

def predict_airflow(selected_design):
    return np.random.rand(100, 100)

def cluster_designs(design_data):
    return np.random.randint(0, 3, size=(10,))

def generate_grid_overlay(bounds):
    """ Generate a grid overlay within the selected rectangle bounds. """
    lat_start, lon_start = bounds[0]
    lat_end, lon_end = bounds[1]
    grid_lines = []

    # Create horizontal and vertical lines for the grid
    num_lines = 10  # Example: 10x10 grid
    lat_step = (lat_end - lat_start) / num_lines
    lon_step = (lon_end - lon_start) / num_lines

    for i in range(1, num_lines):
        grid_lines.append(dl.Polyline(positions=[
            [lat_start + i * lat_step, lon_start],
            [lat_start + i * lat_step, lon_end]
        ], color="blue", weight=1))
        grid_lines.append(dl.Polyline(positions=[
            [lat_start, lon_start + i * lon_step],
            [lat_end, lon_start + i * lon_step]
        ], color="blue", weight=1))

    return dl.LayerGroup(grid_lines)



def generate_affected_region(bounds):
    """ Generate a larger rectangle around the selected area to mock the affected region. """
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
    return dbc.Container(
        [
            html.H2("Step 1: Select a City Quarter"),
            html.P("Move the map to position the 200m x 200m area over the desired region."),
            dl.Map(center=[50.7344, 7.0955], zoom=16, style={'width': '100%', 'height': '500px'}, id="map", children=[
                dl.TileLayer(),
                dl.LayerGroup(id="layer")
            ]),
            html.Br(),
            html.Div(id="selected-area", style={"marginTop": "20px"}),
            html.Div(id="gis-data-output", style={"marginTop": "20px"}),
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
    [Input("map", "center")],
)
def update_map(center):
    if not center:
        raise dash.exceptions.PreventUpdate

    if isinstance(center, (list, tuple)) and len(center) >= 2:
        lat, lon = float(center[0]), float(center[1])
    elif isinstance(center, dict):
        lat = float(center.get("lat", 0))
        lon = float(center.get("lon", 0))
    else:
        raise dash.exceptions.PreventUpdate

    # Calculate the bounds of the rectangle based on the new center
    delta = 0.001  # 200m x 200m rectangle in degrees
    bounds = [[lat - delta, lon - delta], [lat + delta, lon + delta]]

    coordinates_text = f"Selected area coordinates: {bounds}"

    # Mock loading of GIS data
    gis_data = load_geodata(bounds)
    gis_data_text = f"GIS Data Loaded: {gis_data}"

    # Create the rectangle layer
    rectangle_layer = dl.Rectangle(bounds=bounds, color="#ff7800", weight=2)

    # Generate grid overlay for marking taboo regions
    grid_overlay = generate_grid_overlay(bounds)

    # Generate the affected region rectangle
    affected_region = generate_affected_region(bounds)

    # Combine all layers
    layers = [rectangle_layer, grid_overlay, affected_region]

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
