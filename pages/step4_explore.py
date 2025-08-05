#
# pages/step4_explore.py (Final Corrected Version)
#
from dash import dcc, html, Input, Output, State, callback
import dash_bootstrap_components as dbc
from backend.translation import T
from backend.config import ENCODING_CONFIG
import plotly.express as px
import numpy as np

LANG = 'DE'

def layout():
    return dbc.Container([
        html.H2(T[LANG]['STEP4_TITLE']),
        dbc.Card(dbc.CardBody([
            dbc.Row([
                dbc.Col(dbc.Label(T[LANG]['STEP4_X_AXIS_LABEL'])),
                dbc.Col(dcc.Dropdown(id='x-axis-dropdown')),
            ]),
            dbc.Row([
                dbc.Col(dbc.Label(T[LANG]['STEP4_Y_AXIS_LABEL'])),
                dbc.Col(dcc.Dropdown(id='y-axis-dropdown')),
            ])
        ])),
        html.Hr(),
        html.H4(T[LANG]['STEP4_GRID_HEADER']),
        dcc.Loading(html.Div(id='solution-grid-container')),
        dbc.Row([
            dbc.Col(dbc.Button(T[LANG]['PREV_STEP'], href='/step3', color="secondary")),
            dbc.Col(dbc.Button(T[LANG]['NEXT_STEP'], href='/step5', color="primary"), className="text-end")
        ], className="mt-4")
    ], fluid=True)

@callback(
    Output('x-axis-dropdown', 'options'),
    Output('y-axis-dropdown', 'options'),
    Output('x-axis-dropdown', 'value'),
    Output('y-axis-dropdown', 'value'),
    Input('results-store', 'data'),
)
def populate_dropdowns(results_data):
    if not results_data or 'labels' not in results_data:
        return [], [], None, None
    
    options = [{'label': label, 'value': i} for i, label in enumerate(results_data['labels'])]
    val1 = 0 if len(options) > 0 else None
    val2 = 1 if len(options) > 1 else None
    return options, options, val1, val2

@callback(
    Output('solution-grid-container', 'children'),
    Output('solution-grid-container', 'style'),
    Input('x-axis-dropdown', 'value'),
    Input('y-axis-dropdown', 'value'),
    State('results-store', 'data'),
)
def update_solution_grid(x_axis_idx, y_axis_idx, results_data):
    if not all([isinstance(x_axis_idx, int), isinstance(y_axis_idx, int), results_data]):
        return dbc.Alert("Optimierungsergebnisse nicht gefunden oder Achsen nicht gewählt.", color="warning"), {}

    # The data structure is now a clean list of dictionaries.
    list_of_elites = results_data['elites_data']
    grid_dims = results_data['archive_dims']
    grid_resolution = grid_dims[x_axis_idx]
    
    vis_grid = np.full((grid_resolution, grid_resolution), None, dtype=object)
    
    for elite_dict in list_of_elites:
        # Access the grid indices directly from the dictionary key. This is now guaranteed to work.
        ix = elite_dict['grid_indices'][x_axis_idx]
        iy = elite_dict['grid_indices'][y_axis_idx]
        
        if vis_grid[iy, ix] is None or elite_dict['objective'] > vis_grid[iy, ix]['objective']:
            vis_grid[iy, ix] = elite_dict

    grid_children = []
    heightmap_res = ENCODING_CONFIG['xy_length']
    
    for row in range(grid_resolution):
        for col in range(grid_resolution):
            elite_data = vis_grid[row, col]
            if elite_data is not None:
                heightmap = np.array(elite_data['heightmap']).reshape((heightmap_res, heightmap_res))
                
                fig = px.imshow(heightmap, color_continuous_scale='viridis', origin='lower', zmin=0, zmax=ENCODING_CONFIG['z_length'])
                fig.update_layout(margin=dict(l=0, r=0, t=0, b=0), coloraxis_showscale=False)
                fig.update_xaxes(showticklabels=False).update_yaxes(showticklabels=False)
                
                grid_children.append(dcc.Graph(figure=fig, style={'height': '80px', 'width': '80px'}))
            else:
                grid_children.append(html.Div(style={'backgroundColor': '#f8f9fa', 'border': '1px solid #dee2e-6', 'width': '80px', 'height': '80px'}))

    grid_style = {
        'display': 'grid',
        'gridTemplateColumns': f'repeat({grid_resolution}, 1fr)',
        'gap': '5px'
    }

    return grid_children, grid_style