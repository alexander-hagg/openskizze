from dash import dcc, html, Input, Output, State, callback, no_update, ALL
import dash_bootstrap_components as dbc
from backend.translation import T
from backend.analysis import generate_contest_requirements, cluster_and_analyze_solutions, generate_pdf_report, heightmap_to_geojson
from backend.config import ENCODING_CONFIG
import pickle
import os
import numpy as np
import dash_leaflet as dl
from dash_extensions.javascript import assign
import plotly.express as px
import base64 

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
        dbc.Row([
            dbc.Col(dbc.Button(T[LANG]['PREV_STEP'], href='/step4', color="secondary")),
            dbc.Col(dbc.Button(T[LANG]['NEXT_STEP'], href='/step6', color="primary"), className="text-end")
        ], className="mt-4"),

        
        dbc.Card(dbc.CardBody([
            html.H4(T[LANG]['STEP5_FILTER_HEADER']),
            html.P("Filtern Sie die Lösungen nach ihren Merkmalen und passen Sie die Clustering-Parameter an, um Entwurfstypen zu identifizieren.", className="text-muted"),
            html.Div(id='feature-filter-controls'),
            
            dbc.Label(T[LANG]['STEP5_ALGORITHM_LABEL']),
            dbc.RadioItems(
                id='algorithm-selector',
                options=[
                    {'label': 'K-Medoids (Partionierend)', 'value': 'kmedoids'},
                    {'label': 'HDBSCAN (Automatisch)', 'value': 'hdbscan'},
                    {'label': 'DBSCAN (Dichte-basiert)', 'value': 'dbscan'},
                ],
                value='kmedoids',
                inline=True,
                className="mb-3"
            ),
            
            html.Div(id='dbscan-params-div', children=[
                dbc.Row([
                    dbc.Col(dbc.Label("DBSCAN eps (Nachbarschaftsradius):"), width='auto'),
                    dbc.Col(dcc.Slider(id='dbscan-eps-slider', min=0.1, max=5, step=0.1, value=0.1, marks=None, tooltip={"placement": "bottom", "always_visible": True})),
                ], className="align-items-center mt-2"),
                dbc.Row([
                     dbc.Col(dbc.Label("DBSCAN min_samples (Min. Clustergröße):"), width='auto'),
                     dbc.Col(dcc.Slider(id='dbscan-minsamples-slider', min=2, max=20, step=1, value=4, marks=None, tooltip={"placement": "bottom", "always_visible": True})),
                ], className="align-items-center mt-2"),
            ]),

            html.Div(id='kmedoids-params-div', style={'display': 'none'}, children=[
                dbc.Row([
                    dbc.Col(dbc.Label(T[LANG]['STEP5_KMEDOIDS_K_LABEL']), width='auto'),
                    dbc.Col(dcc.Slider(id='kmedoids-k-slider', min=2, max=50, step=1, value=30, marks=None, tooltip={"placement": "bottom", "always_visible": True})),
                ], className="align-items-center mt-2"),
            ]),

            html.Div(id='hdbscan-params-div', style={'display': 'none'}, children=[
                dbc.Row([
                    dbc.Col(dbc.Label(T[LANG]['STEP5_HDBSCAN_MINCLUSTER']), width='auto'),
                    dbc.Col(dcc.Slider(id='hdbscan-minsamples-slider', min=2, max=20, step=1, value=5, marks=None, tooltip={"placement": "bottom", "always_visible": True})),
                ], className="align-items-center mt-2"),
            ]),


            dbc.Button(T[LANG]['STEP5_RUN_BUTTON'], id="run-analysis-btn", color="primary", className="mt-3"),

            # Add a "Compare" button and a store for selections
            dcc.Store(id='comparison-store', storage_type='session', data=[]),
            dbc.Button("Ausgewählte Designs vergleichen", id="compare-btn", href="/step6", color="success", className="mt-3", style={'display': 'none'}),
        ])),
        
        html.Hr(),
        
        html.H4(T[LANG]['STEP5_ANALYSIS_HEADER']),
        dcc.Loading(html.Div(id='cluster-results-container', children=[
             dbc.Alert(T[LANG]['STEP5_NO_SELECTION'], color="light")
        ])),
        
        # DEBUG: Display the content of the comparison-store
        html.Div([
            html.Hr(),
            html.P("Debug: In-page comparison-store content:"),
            html.Pre(id='debug-comparison-store-content-s5')
        ])
        
    ], fluid=True)


@callback(
    Output('hdbscan-params-div', 'style'),
    Output('dbscan-params-div', 'style'),
    Output('kmedoids-params-div', 'style'),
    Input('algorithm-selector', 'value')
)
def toggle_parameter_sliders(selected_algorithm):
    if selected_algorithm == 'dbscan':
        return {'display': 'none'}, {'display': 'block'}, {'display': 'none'}
    elif selected_algorithm == 'kmedoids':
        return {'display': 'none'}, {'display': 'none'}, {'display': 'block'}
    elif selected_algorithm == 'hdbscan':
        return {'display': 'block'}, {'display': 'none'}, {'display': 'none'}
    return {'display': 'none'}, {'display': 'none'}, {'display': 'none'}

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
    selected_feature_indices = results_data.get('selected_features_indices', [])
    if not labels: return no_update
    
    measures_data = np.array([elite['measures'] for elite in list_of_elites])
    
    sliders = []
    # This is the original index from the config, not the index in the 'labels' list
    num_buildings_original_index = 3

    for i, label in enumerate(labels):
        # The actual index of the feature we are currently processing
        current_feature_original_index = selected_feature_indices[i]
        
        min_val, max_val = measures_data[:, i].min(), measures_data[:, i].max()
        
        # --- THE FIX IS HERE ---
        # Handle the "Number of Buildings" slider to be integer-only
        if current_feature_original_index == num_buildings_original_index:
            min_v = int(np.floor(min_val))
            max_v = int(np.ceil(max_val))
            if min_v == max_v: max_v += 1
            
            slider_div = html.Div([
                dbc.Label(label),
                dcc.RangeSlider(
                    id={'type': 'filter-slider', 'index': i},
                    min=min_v,
                    max=max_v,
                    step=1,  # Enforce integer steps
                    value=[min_v, max_v],
                    tooltip={"placement": "bottom", "always_visible": True},
                    marks=None,
                )
            ], className="mb-2")
        
        # Handle all other sliders to have two decimal places
        else:
            min_v = round(min_val, 2)
            max_v = round(max_val, 2)
            if min_v == max_v: max_v += 0.01

            slider_div = html.Div([
                dbc.Label(label),
                dcc.RangeSlider(
                    id={'type': 'filter-slider', 'index': i},
                    min=min_v,
                    max=max_v,
                    step=0.01,  # Enforce 2 decimal places
                    value=[min_v, max_v],
                    tooltip={"placement": "bottom", "always_visible": True},
                    marks=None,
                )
            ], className="mb-2")
        # --- END OF FIX ---
        sliders.append(slider_div)
        
    return sliders

@callback(
    Output('cluster-results-container', 'children'),
    Input('run-analysis-btn', 'n_clicks'),
    State('results-store', 'data'),
    State({'type': 'filter-slider', 'index': ALL}, 'value'),
    State({'type': 'filter-slider', 'index': ALL}, 'id'),
    State('algorithm-selector', 'value'),
    State('dbscan-eps-slider', 'value'),
    State('dbscan-minsamples-slider', 'value'),
    State('kmedoids-k-slider', 'value'),
    prevent_initial_call=True
)
def run_and_display_analysis(n_clicks, results_data, slider_values, slider_ids, 
                             algorithm, eps, min_samples, k):
    if not n_clicks: return no_update

    results_path = results_data.get('full_results_path')
    grid_geojson = results_data.get('grid_geojson')
    if not results_path or not grid_geojson:
        return dbc.Alert("Ergebnisdatei oder Georeferenzierung nicht gefunden.", color="danger")
        
    feature_filters = {s_id['index']: s_val for s_id, s_val in zip(slider_ids, slider_values)}

    params = {}
    if algorithm == 'dbscan':
        params = {'eps': eps, 'min_samples': min_samples}
    elif algorithm == 'kmedoids':
        params = {'n_clusters': k}

    clusters = cluster_and_analyze_solutions(results_path, algorithm, params, feature_filters)

    if not clusters:
        return dbc.Alert(T[LANG]['STEP5_NO_CLUSTERS_FOUND'], color="warning")

    lons = [c[0] for f in grid_geojson['features'] for c in f['geometry']['coordinates'][0]]
    lats = [c[1] for f in grid_geojson['features'] for c in f['geometry']['coordinates'][0]]
    map_center = [(min(lats) + max(lats)) / 2, (min(lons) + max(lons)) / 2]
    heightmap_res = results_data['xy_length']

    cluster_cards = []
    for cluster in clusters:
        best_hm = np.array(cluster['best_solution']['heightmap']).reshape(heightmap_res, heightmap_res)
        best_geojson = heightmap_to_geojson(np.flipud(best_hm), grid_geojson)
        best_map = dl.Map(center=map_center, zoom=14, children=[
            dl.TileLayer(url="https://{s}.basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}{r}.png"),
            dl.GeoJSON(data=best_geojson, options=dict(style=style_handle), hideout={'z_length': ENCODING_CONFIG['z_length']})
        ], style={'height': '200px', 'width': '100%'})
        
        central_hm = np.array(cluster['central_solution']['heightmap']).reshape(heightmap_res, heightmap_res)
        central_geojson = heightmap_to_geojson(np.flipud(central_hm), grid_geojson)
        central_map = dl.Map(center=map_center, zoom=14, children=[
            dl.TileLayer(url="https://{s}.basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}{r}.png"),
            dl.GeoJSON(data=central_geojson, options=dict(style=style_handle), hideout={'z_length': ENCODING_CONFIG['z_length']})
        ], style={'height': '200px', 'width': '100%'})

        consensus_map_data = np.array(cluster['consensus_map']).reshape(heightmap_res, heightmap_res)
        consensus_fig = px.imshow(consensus_map_data, color_continuous_scale='Blues', origin='lower', zmin=0, zmax=1)
        consensus_fig.update_layout(margin=dict(l=0, r=0, t=0, b=0), coloraxis_showscale=False)
        consensus_fig.update_xaxes(showticklabels=False).update_yaxes(showticklabels=False)
        consensus_graph = dcc.Graph(figure=consensus_fig, style={'height': '200px', 'width': '100%'})
        
        card = dbc.Card(dbc.CardBody([
            dbc.Checkbox(
                id={'type': 'compare-checkbox', 'index': cluster['central_solution']['id']}, # Assuming solutions have a unique ID
                label=f"Zum Vergleich auswählen",
                value=False
            ),
            html.H5(T[LANG]['STEP5_CLUSTER_CARD_TITLE'].format(id=cluster['cluster_id'], size=cluster['size'])),
            html.P(T[LANG]['STEP5_CLUSTER_CARD_TEXT'].format(size=cluster['size']), className="text-muted small"),
            dbc.Row([
                dbc.Col([html.H6(T[LANG]['STEP5_BEST_SOLUTION_HEADER']), best_map], md=4),
                dbc.Col([html.H6(T[LANG]['STEP5_CENTRAL_SOLUTION_HEADER']), central_map], md=4),
                dbc.Col([html.H6(T[LANG]['STEP5_CONSENSUS_MAP_HEADER']), consensus_graph], md=4)
            ])
        ]), className="mb-3")
        cluster_cards.append(card)
        
    return cluster_cards

@callback(
    Output('comparison-store', 'data'),
    Output('compare-btn', 'style'),
    Input({'type': 'compare-checkbox', 'index': ALL}, 'value'),
    State({'type': 'compare-checkbox', 'index': ALL}, 'id'),
    prevent_initial_call=True
)
def update_comparison_list(checkbox_values, checkbox_ids):
    selected_ids = [
        cid['index'] for cid, is_checked in zip(checkbox_ids, checkbox_values) if is_checked
    ]
    button_style = {'display': 'inline-block'} if selected_ids else {'display': 'none'}
    return selected_ids, button_style
