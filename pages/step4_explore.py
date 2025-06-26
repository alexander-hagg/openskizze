from dash import dcc, html, Input, Output, State, callback
import dash_bootstrap_components as dbc
from backend.translation import T
from backend.analysis import get_solution_grid
import plotly.express as px

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
    Input('session-store', 'data'),
)
def populate_dropdowns(session_data):
    if not session_data or 'measures_map' not in session_data:
        return [], [], None, None
    
    options = [{'label': v, 'value': k} for k, v in session_data['measures_map'].items()]
    
    # Set default values
    val1 = options[0]['value'] if options else None
    val2 = options[1]['value'] if len(options) > 1 else None
    
    return options, options, val1, val2


@callback(
    Output('solution-grid-container', 'children'),
    Output('solution-grid-container', 'style'),
    Input('x-axis-dropdown', 'value'),
    Input('y-axis-dropdown', 'value'),
    State('results-store', 'data'),
)
def update_solution_grid(x_axis, y_axis, results_data):
    if not all([x_axis, y_axis, results_data]):
        return dbc.Alert("Optimierungsergebnisse nicht gefunden. Bitte führen Sie Schritt 3 aus.", color="warning"), {}

    grid_resolution = 10
    grid = get_solution_grid(results_data, x_axis, y_axis, grid_resolution)
    
    grid_children = []
    for row in range(grid_resolution):
        for col in range(grid_resolution):
            cell = grid[row, col]
            if cell and cell['best_solution_idx'] != -1:
                idx = cell['best_solution_idx']
                heightmap = results_data['heightmaps'][idx]
                
                fig = px.imshow(heightmap, color_continuous_scale='viridis')
                fig.update_layout(margin=dict(l=0, r=0, t=0, b=0), coloraxis_showscale=False)
                fig.update_xaxes(showticklabels=False).update_yaxes(showticklabels=False)
                
                grid_children.append(
                    dbc.Card(dbc.CardBody(dcc.Graph(figure=fig, style={'height': '80px', 'width': '80px'})),
                             style={'padding': '5px'})
                )
            else:
                grid_children.append(html.Div(style={'backgroundColor': '#f8f9fa', 'border': '1px solid #dee2e6'}))

    grid_style = {
        'display': 'grid',
        'gridTemplateColumns': f'repeat({grid_resolution}, 1fr)',
        'gap': '5px'
    }

    return grid_children, grid_style