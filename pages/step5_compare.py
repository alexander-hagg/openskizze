from dash import dcc, html, Input, Output, State, callback, no_update, ALL
import dash_bootstrap_components as dbc
from backend.translation import T
from backend.analysis import generate_contest_requirements, cluster_and_analyze_solutions, heightmap_to_geojson
from backend.config import ENCODING_CONFIG
import pickle
import os
import numpy as np
import dash_leaflet as dl
from dash_extensions.javascript import assign

LANG = 'DE'

style_handle = assign("""
function(feature, context){
    const { z_length } = context.hideout;
    const height = feature.properties.height;
    const colorscale = chroma.scale('viridis').domain([0, z_length]);
    return {
        fillColor: colorscale(height),
        color: '#333',
        weight: 1,
        opacity: 1,
        fillOpacity: 0.8
    };
}
""")

def layout():
    return dbc.Container([
        html.H2(T[LANG]['STEP5_TITLE']),
        
        dbc.Card(dbc.CardBody([
            html.H4(T[LANG]['STEP5_FILTER_HEADER']),
            html.P("Filtern Sie die Lösungen nach ihren Merkmalen und passen Sie die Clustering-Parameter an, um Entwurfstypen zu identifizieren.", className="text-muted"),
            html.Div(id='feature-filter-controls'),
            dbc.Row([
                dbc.Col(dbc.Label("DBSCAN eps (Nachbarschaftsradius):"), width='auto'),
                dbc.Col(dcc.Slider(id='dbscan-eps-slider', min=1, max=5, step=0.1, value=1.5, marks=None, tooltip={"placement": "bottom", "always_visible": True})),
            ], className="align-items-center mt-2"),
            dbc.Row([
                 dbc.Col(dbc.Label("DBSCAN min_samples (Min. Clustergröße):"), width='auto'),
                 dbc.Col(dcc.Slider(id='dbscan-minsamples-slider', min=2, max=20, step=1, value=3, marks=None, tooltip={"placement": "bottom", "always_visible": True})),
            ], className="align-items-center mt-2"),
            dbc.Button(T[LANG]['STEP5_RUN_BUTTON'], id="run-analysis-btn", color="primary", className="mt-3")
        ])),
        
        html.Hr(),
        
        html.H4(T[LANG]['STEP5_ANALYSIS_HEADER']),
        dcc.Loading(html.Div(id='cluster-results-container', children=[
             dbc.Alert(T[LANG]['STEP5_NO_SELECTION'], color="light")
        ])),
        
        dbc.Button(T[LANG]['STEP5_EXPORT_BUTTON'], id="export-reqs-btn-s5", color="info", className="mt-3"),
        dcc.Download(id="download-requirements-s5"),
        
        dbc.Row([
            dbc.Col(dbc.Button(T[LANG]['PREV_STEP'], href='/step4', color="secondary")),
        ], className="mt-4")
    ], fluid=True)

@callback(
    Output('feature-filter-controls', 'children'),
    Input('results-store', 'data')
)
def create_filter_controls(results_data):
    if not results_data or not results_data.get('full_results_path'):
        return dbc.Alert("Bitte zuerst in Schritt 3 eine Optimierung durchführen.", color="warning")

    results_path = results_data.get('full_results_path')
    if not os.path.exists(results_path): return no_update
    
    with open(results_path, 'rb') as f:
        list_of_elites = pickle.load(f)
    
    labels = results_data.get('labels', [])
    if not labels: return no_update
    
    measures_data = np.array([elite['measures'] for elite in list_of_elites])
    
    sliders = []
    for i, label in enumerate(labels):
        min_val, max_val = measures_data[:, i].min(), measures_data[:, i].max()
        if min_val == max_val: max_val += 1.0 # Ensure slider has a range
        
        slider_div = html.Div([
            dbc.Label(label),
            dcc.RangeSlider(
                id={'type': 'filter-slider', 'index': i},
                min=min_val, max=max_val, value=[min_val, max_val],
                tooltip={"placement": "bottom", "always_visible": True},
                marks=None,
                step=(max_val - min_val) / 100 if (max_val - min_val) > 0 else 0.1
            )
        ], className="mb-2")
        sliders.append(slider_div)
        
    return sliders

@callback(
    Output('cluster-results-container', 'children'),
    Input('run-analysis-btn', 'n_clicks'),
    State('results-store', 'data'),
    State({'type': 'filter-slider', 'index': ALL}, 'value'),
    State({'type': 'filter-slider', 'index': ALL}, 'id'),
    State('dbscan-eps-slider', 'value'),
    State('dbscan-minsamples-slider', 'value'),
    prevent_initial_call=True
)
def run_and_display_analysis(n_clicks, results_data, slider_values, slider_ids, eps, min_samples):
    if not n_clicks: return no_update

    results_path = results_data.get('full_results_path')
    grid_geojson = results_data.get('grid_geojson')
    if not results_path or not grid_geojson:
        return dbc.Alert("Ergebnisdatei oder Georeferenzierung nicht gefunden.", color="danger")
        
    feature_filters = {s_id['index']: s_val for s_id, s_val in zip(slider_ids, slider_values)}

    clusters = cluster_and_analyze_solutions(results_path, eps, min_samples, feature_filters)

    if not clusters:
        return dbc.Alert(T[LANG]['STEP5_NO_CLUSTERS_FOUND'], color="warning")

    lons = [c[0] for f in grid_geojson['features'] for c in f['geometry']['coordinates'][0]]
    lats = [c[1] for f in grid_geojson['features'] for c in f['geometry']['coordinates'][0]]
    map_center = [(min(lats) + max(lats)) / 2, (min(lons) + max(lons)) / 2]
    heightmap_res = results_data['xy_length']

    cluster_cards = []
    for cluster in clusters:
        best_hm = np.array(cluster['best_solution']['heightmap']).reshape(heightmap_res, heightmap_res)
        best_geojson = heightmap_to_geojson(best_hm, grid_geojson)
        best_map = dl.Map(center=map_center, zoom=14, children=[
            dl.TileLayer(url="https://{s}.basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}{r}.png"),
            dl.GeoJSON(data=best_geojson, options=dict(style=style_handle), hideout={'z_length': ENCODING_CONFIG['z_length']})
        ], style={'height': '200px', 'width': '100%'})
        
        central_hm = np.array(cluster['central_solution']['heightmap']).reshape(heightmap_res, heightmap_res)
        central_geojson = heightmap_to_geojson(central_hm, grid_geojson)
        central_map = dl.Map(center=map_center, zoom=14, children=[
            dl.TileLayer(url="https://{s}.basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}{r}.png"),
            dl.GeoJSON(data=central_geojson, options=dict(style=style_handle), hideout={'z_length': ENCODING_CONFIG['z_length']})
        ], style={'height': '200px', 'width': '100%'})

        card = dbc.Card(dbc.CardBody([
            html.H5(T[LANG]['STEP5_CLUSTER_CARD_TITLE'].format(id=cluster['cluster_id'], size=cluster['size'])),
            html.P(T[LANG]['STEP5_CLUSTER_CARD_TEXT'].format(size=cluster['size']), className="text-muted small"),
            dbc.Row([
                dbc.Col([html.H6(T[LANG]['STEP5_BEST_SOLUTION_HEADER']), best_map], md=6),
                dbc.Col([html.H6(T[LANG]['STEP5_CENTRAL_SOLUTION_HEADER']), central_map], md=6),
            ])
        ]), className="mb-3")
        cluster_cards.append(card)
        
    return cluster_cards

@callback(
    Output("download-requirements-s5", "data"),
    Input("export-reqs-btn-s5", "n_clicks"),
    State("results-store", "data"),
    prevent_initial_call=True,
)
def export_requirements_s5(n_clicks, results_data):
    if not n_clicks or not results_data:
        return None
    
    results_path = results_data.get('full_results_path')
    labels = results_data.get('labels')
    selected_indices = results_data.get('selected_features_indices')

    if not all([results_path, labels, selected_indices is not None]):
         return dict(content="Error: Could not find all necessary data for export.", filename="error.txt")

    report_text = generate_contest_requirements(results_path, labels, selected_indices)
    
    return dict(content=report_text, filename=T[LANG]['STEP5_EXPORT_FILENAME'])