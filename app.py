import dash
import dash_bootstrap_components as dbc
from dash import dcc, html, Input, Output
from backend.translation import T

# --- THE FIX IS HERE ---
# Add external scripts for chroma.js (for map coloring)
external_scripts = [
    "https://cdnjs.cloudflare.com/ajax/libs/chroma-js/2.4.2/chroma.min.js"
]

# Initialize the Dash app with the external scripts
app = dash.Dash(
    __name__, 
    external_stylesheets=[dbc.themes.BOOTSTRAP], 
    suppress_callback_exceptions=True,
    external_scripts=external_scripts
)
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
    html.Div(id='page-content', className="container-fluid mt-4") # Use container-fluid for better grid layout
])

# Register page layouts
from pages import step1_scope, step2_constraints, step3_optimize, step4_explore, step5_compare, step6_compare_detail

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
    elif pathname == '/step6':
        return step6_compare_detail.layout()
    else:
        return step1_scope.layout()