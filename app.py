import dash
import dash_bootstrap_components as dbc
from dash import dcc, html, Input, Output, State, no_update
from backend.translation import T
import plotly.io as pio
from backend import project_state
import base64
import io
from datetime import datetime

# Configure kaleido to run without a sandbox. This is often required in
# containerized or restricted environments.
# The plotly error messages are contradictory, but this is the correct syntax
# for the installed version.
pio.defaults.chromium_args = ("--no-sandbox", "--disable-gpu")

# Add external scripts for chroma.js (for map coloring)
external_scripts = [
    "https://cdnjs.cloudflare.com/ajax/libs/chroma-js/2.4.2/chroma.min.js"
]

# Initialize the Dash app with the external scripts
app = dash.Dash(
    __name__, 
    external_stylesheets=[dbc.themes.LUX], 
    suppress_callback_exceptions=True,
    external_scripts=external_scripts
)

app.title = T['DE']['APP_TITLE']
server = app.server

# Define the main layout
app.layout = html.Div([
    dcc.Store(id='session-store', storage_type='memory'),  # Use memory to avoid localStorage quota errors with building data
    dcc.Store(id='results-store', storage_type='memory'),  # Use memory to avoid localStorage quota errors
    dcc.Store(id='comparison-store', storage_type='memory', data=[]),  # Use memory for large data
    dcc.Store(id='clustering-data-store', storage_type='memory'),  # Use memory for large cluster data
    dcc.Store(id='language-store', storage_type='session', data='DE'),
    dcc.Download(id="download-project-file"),

    html.Div(id='navbar-container'),
    dcc.Location(id='url', refresh=False),
    html.Div(id='page-content', className="container-fluid mt-4") # Use container-fluid for better grid layout
])

# Register page layouts
from pages import step1_scope, step2_constraints, step3_optimize, step4_analysis, step5_clustering, step6_compare_detail, step_diagnostic, step_model_diagnostics

# Callback to update navbar based on language
@app.callback(
    Output('navbar-container', 'children'),
    Input('language-store', 'data')
)
def update_navbar(language):
    lang = language if language else 'DE'
    return dbc.Navbar(
        dbc.Container([
            # Logo on the left
            html.A(
                html.Img(src='/assets/logo.png', height="40px", style={'marginRight': '15px'}),
                href="/",
                style={'display': 'flex', 'alignItems': 'center'}
            ),
            # Brand name
            dbc.NavbarBrand(T[lang]['APP_TITLE'], href="/", className="ms-2"),
            # Toggler for mobile
            dbc.NavbarToggler(id="navbar-toggler"),
            # Menu items
            dbc.Collapse(
                dbc.Nav([
                    dbc.DropdownMenu(
                        children=[
                            dbc.DropdownMenuItem(T[lang]['NEW_PROJECT'], id="new-project-btn", n_clicks=0),
                            dbc.DropdownMenuItem(T[lang]['SAVE_PROJECT'], id="save-project-btn", n_clicks=0),
                            dcc.Upload(
                                id='upload-project-file',
                                children=dbc.DropdownMenuItem(T[lang]['LOAD_PROJECT']),
                                accept='.skizze',
                            ),
                        ],
                        nav=True,
                        in_navbar=True,
                        label=T[lang]['FILE_MENU'],
                    ),
                    dbc.DropdownMenu(
                        children=[
                            dbc.DropdownMenuItem("🇩🇪 Deutsch", id="lang-de-btn", n_clicks=0),
                            dbc.DropdownMenuItem("🇬🇧 English", id="lang-en-btn", n_clicks=0),
                        ],
                        nav=True,
                        in_navbar=True,
                        label="Language" if lang == 'EN' else "Sprache",
                    ),
                ], navbar=True, className="ms-auto"),
                id="navbar-collapse",
                navbar=True,
            ),
        ], fluid=True),
        color="dark",
        dark=True,
        className="mb-3",
    )

# Callback to handle project file upload and load state
@app.callback(
    Output('session-store', 'data', allow_duplicate=True),
    Output('results-store', 'data', allow_duplicate=True),
    Output('comparison-store', 'data', allow_duplicate=True),
    Output('url', 'pathname'),
    Input('upload-project-file', 'contents'),
    State('upload-project-file', 'filename'),
    prevent_initial_call=True
)
def load_project_file(contents, filename):
    if contents is not None:
        content_type, content_string = contents.split(',')
        decoded = base64.b64decode(content_string)
        try:
            if 'skizze' in filename:
                state = project_state.load_state_from_file(io.BytesIO(decoded))
                return state['session_data'], state['results_data'], state['comparison_data'], '/'
        except Exception as e:
            print(f"Error loading project file: {e}")
            # Optionally, show an error message to the user
    return no_update, no_update, no_update, no_update

# Callback to save project state and trigger download
@app.callback(
    Output('download-project-file', 'data'),
    Input('save-project-btn', 'n_clicks'),
    State('session-store', 'data'),
    State('results-store', 'data'),
    State('comparison-store', 'data'),
    prevent_initial_call=True
)
def save_project_file(n_clicks, session_data, results_data, comparison_data):
    if n_clicks > 0:
        state = project_state.gather_application_state(session_data, results_data, comparison_data)
        
        # Use a BytesIO object to hold the pickled data in memory
        in_memory_file = io.BytesIO()
        project_state.save_state_to_file(state, in_memory_file)
        in_memory_file.seek(0) # Rewind the file-like object to the beginning
        
        # Encode the binary data to a base64 string for the download component
        encoded_data = base64.b64encode(in_memory_file.read()).decode('utf-8')
        
        filename = f"OpenSKIZZE_Project_{datetime.now().strftime('%Y-%m-%d')}.skizze"
        
        return dict(content=encoded_data, filename=filename, base64=True)
    return no_update

# Callback to reset the application state
@app.callback(
    Output('session-store', 'data', allow_duplicate=True),
    Output('results-store', 'data', allow_duplicate=True),
    Output('comparison-store', 'data', allow_duplicate=True),
    Output('url', 'pathname', allow_duplicate=True),
    Input('new-project-btn', 'n_clicks'),
    prevent_initial_call=True
)
def new_project(n_clicks):
    if n_clicks > 0:
        empty_state = project_state.reset_application_state()
        return empty_state['session_data'], empty_state['results_data'], empty_state['comparison_data'], '/'
    return no_update, no_update, no_update, no_update

# Callback to handle language selection
@app.callback(
    Output('language-store', 'data'),
    Input('lang-de-btn', 'n_clicks'),
    Input('lang-en-btn', 'n_clicks'),
    State('language-store', 'data'),
    prevent_initial_call=True
)
def change_language(de_clicks, en_clicks, current_lang):
    ctx = dash.callback_context
    if not ctx.triggered:
        return current_lang
    
    button_id = ctx.triggered[0]['prop_id'].split('.')[0]
    
    if button_id == 'lang-de-btn':
        return 'DE'
    elif button_id == 'lang-en-btn':
        return 'EN'
    
    return current_lang

# Client-side callback for camera synchronization in 3D plots (step 5)
# This runs in the browser for instant synchronization without server roundtrips
app.clientside_callback(
    """
    function(relayoutDataList, figureList) {
        // Find which plot was updated
        const triggered = dash_clientside.callback_context.triggered;
        if (!triggered || triggered.length === 0) {
            return window.dash_clientside.no_update;
        }
        
        // Get the triggered input info
        const triggeredProp = triggered[0].prop_id;
        
        // Extract the index from the triggered prop_id
        // Format: {"index":0,"type":"3d-plot"}.relayoutData
        let triggerIndex = -1;
        try {
            const match = triggeredProp.match(/"index":(\\d+)/);
            if (match) {
                triggerIndex = parseInt(match[1]);
            }
        } catch (e) {
            return window.dash_clientside.no_update;
        }
        
        if (triggerIndex < 0 || triggerIndex >= relayoutDataList.length) {
            return window.dash_clientside.no_update;
        }
        
        // Get the relayout data from the triggered plot
        const relayoutData = relayoutDataList[triggerIndex];
        
        // Check if camera was updated (and not just dragmode or other properties)
        if (!relayoutData || !relayoutData['scene.camera']) {
            return window.dash_clientside.no_update;
        }
        
        // Get the new camera state
        const newCamera = relayoutData['scene.camera'];
        
        // Update all other plots with the new camera position
        const updatedFigures = figureList.map((fig, index) => {
            if (index === triggerIndex) {
                // Don't update the plot that triggered the change
                return window.dash_clientside.no_update;
            }
            
            // Deep clone the figure to avoid mutation
            const updatedFig = JSON.parse(JSON.stringify(fig));
            
            // Update the camera in the scene
            if (updatedFig.layout && updatedFig.layout.scene) {
                updatedFig.layout.scene.camera = newCamera;
            }
            
            return updatedFig;
        });
        
        return updatedFigures;
    }
    """,
    Output({'type': '3d-plot', 'index': dash.ALL}, 'figure'),
    Input({'type': '3d-plot', 'index': dash.ALL}, 'relayoutData'),
    State({'type': '3d-plot', 'index': dash.ALL}, 'figure'),
    prevent_initial_call=True
)

# Callback to control page navigation
@app.callback(
    Output('page-content', 'children'),
    Input('url', 'pathname'),
    Input('language-store', 'data')
)
def display_page(pathname, lang):
    if lang is None:
        lang = 'DE'
    
    if pathname == '/step2':
        return step2_constraints.layout(lang)
    elif pathname == '/step3':
        return step3_optimize.layout(lang)
    elif pathname == '/step4':
        return step4_analysis.layout(lang)
    elif pathname == '/step5':
        return step5_clustering.layout(lang)
    elif pathname == '/step6':
        return step6_compare_detail.layout(lang)
    elif pathname == '/diagnostic':
        return step_diagnostic.layout(lang)
    elif pathname == '/model_diagnostics':
        return step_model_diagnostics.layout(lang)
    else:
        return step1_scope.layout(lang)