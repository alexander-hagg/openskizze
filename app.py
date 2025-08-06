import dash
import dash_bootstrap_components as dbc
from dash import dcc, html, Input, Output
from backend.translation import T

# Initialize the Dash app
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP], suppress_callback_exceptions=True)
app.title = T['DE']['APP_TITLE']
server = app.server

# Define the main layout
app.layout = html.Div([
    dcc.Store(id='session-store', storage_type='session'),
    dcc.Store(id='results-store', storage_type='session'),

    dbc.NavbarSimple(
        brand=T['DE']['APP_TITLE'],
        color="dark",
        dark=True,
        fluid=True,
    ),
    dcc.Location(id='url', refresh=False),
    html.Div(id='page-content', className="container mt-4")
])

# Register page layouts
from pages import step1_scope, step2_constraints, step3_optimize, step4_explore, step5_compare

# Callback to control page navigation
@app.callback(
    Output('page-content', 'children'),
    Input('url', 'pathname')
)
def display_page(pathname):
    if pathname == '/step2':
        return step2_constraints.layout()
    elif pathname == '/step3':
        return step3_optimize.layout()
    elif pathname == '/step4':
        return step4_explore.layout()
    elif pathname == '/step5':
        return step5_compare.layout()
    else:
        return step1_scope.layout()