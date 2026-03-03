from dash import dcc, html, Input, Output, State, callback, no_update, ALL
import dash_bootstrap_components as dbc
from backend.translation import T
from backend.analysis import cluster_and_analyze_solutions, heightmap_to_geojson
from backend.config import ENCODING_CONFIG
import pickle
import os
import numpy as np
import pandas as pd
import dash_leaflet as dl
from dash_extensions.javascript import assign
import plotly.express as px

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

def layout(lang='DE'):
    from backend.translation import create_breadcrumb
    return dbc.Container([
        create_breadcrumb(5, lang),
        html.H2(T[lang].get('STEP5_TITLE', 'Cluster Analysis')),
        
        # Single column layout (filtering removed - done in Step 4)
        dbc.Row([
            dbc.Col([
                dbc.Card(dbc.CardBody([
                    html.H5(T[lang]['STEP5_SIMILARITY_METRIC_LABEL']),
                    dbc.RadioItems(
                        id='similarity-metric-selector',
                        options=[
                            {'label': T[lang]['STEP5_METRIC_TSNE'], 'value': 'tsne'},
                            {'label': T[lang]['STEP5_METRIC_SSIM'], 'value': 'ssim'},
                        ],
                        value='tsne',
                        inline=True,
                        className="mb-3"
                    ),

                    html.H5(T[lang]['STEP5_ALGORITHM_LABEL']),
                    dbc.RadioItems(
                        id='algorithm-selector',
                        options=[
                            {'label': T[lang]['STEP5_ALG_HIERARCHICAL'], 'value': 'hierarchical'},
                            {'label': T[lang]['STEP5_ALG_HDBSCAN'], 'value': 'hdbscan'},
                            {'label': T[lang]['STEP5_ALG_KMEDOIDS'], 'value': 'kmedoids'},
                        ],
                        value='hierarchical',
                        inline=True,
                        className="mb-3"
                    ),

                    html.Div(id='hierarchical-params-div', children=[
                        dbc.Row([
                            dbc.Col(dbc.Label(T[lang]['STEP5_N_CLUSTERS_LABEL']), width='auto'),
                            dbc.Col(dcc.Slider(id='hierarchical-k-slider', min=2, max=20, step=1, value=5, marks={i: str(i) for i in range(2, 21, 2)}, tooltip={"placement": "bottom", "always_visible": True})),
                        ], className="align-items-center mt-2"),
                    ]),

                    html.Div(id='kmedoids-params-div', style={'display': 'none'}, children=[
                        dbc.Row([
                            dbc.Col(dbc.Label(T[lang]['STEP5_KMEDOIDS_K_LABEL']), width='auto'),
                            dbc.Col(dcc.Slider(id='kmedoids-k-slider', min=2, max=50, step=1, value=10, marks=None, tooltip={"placement": "bottom", "always_visible": True})),
                        ], className="align-items-center mt-2"),
                    ]),

                    html.Div(id='hdbscan-params-div', children=[
                        html.P(T[lang]['STEP5_HDBSCAN_AUTO_NOTE'] if 'STEP5_HDBSCAN_AUTO_NOTE' in T[lang] else 
                               "HDBSCAN uses a minimum cluster size of 5.",
                               className="text-muted small mt-2")
                    ]),

                    dbc.Button(T[lang]['STEP5_RUN_BUTTON'], id="run-analysis-btn", color="primary", className="mt-3"),

                    # Add a "Compare" button and link to comparison view
                    dbc.Button(T[lang]['STEP5_COMPARE_BUTTON'], id="compare-btn", href="/step6", color="success", className="mt-3 ms-2", style={'display': 'none'}),
                ]), className="mb-3"),
                
                # Filter info banner — shows how many solutions will be used for clustering
                html.Div(id='step5-filter-info-container'),
                
            ], md=4),
            
            dbc.Col([
                html.H4(T[lang]['STEP5_ANALYSIS_HEADER']),
                dcc.Loading(html.Div(id='cluster-results-container', children=[
                     dbc.Alert(T[lang]['STEP5_NO_SELECTION'], color="light")
                ])),
            ], md=8),
        ], className="mb-4"),
        
        # Hidden placeholder for filter controls (kept empty for layout compatibility)
        html.Div(id='feature-filter-controls', style={'display': 'none'}),
        
    ], fluid=True)


@callback(
    Output('hdbscan-params-div', 'style'),
    Output('kmedoids-params-div', 'style'),
    Output('hierarchical-params-div', 'style'),
    Input('algorithm-selector', 'value')
)
def toggle_parameter_sliders(selected_algorithm):
    if selected_algorithm == 'kmedoids':
        return {'display': 'none'}, {'display': 'block'}, {'display': 'none'}
    elif selected_algorithm == 'hdbscan':
        return {'display': 'block'}, {'display': 'none'}, {'display': 'none'}
    elif selected_algorithm == 'hierarchical':
        return {'display': 'none'}, {'display': 'none'}, {'display': 'block'}
    return {'display': 'none'}, {'display': 'none'}, {'display': 'none'}


@callback(
    Output('feature-filter-controls', 'children'),
    Input('results-store', 'data'),
)
def create_filter_controls(results_data):
    """Keep hidden filter controls empty — filtering is now handled via filter-store from Step 4."""
    return []


@callback(
    Output('step5-filter-info-container', 'children'),
    Input('filter-store', 'data'),
    Input('results-store', 'data'),
    Input('language-store', 'data'),
)
def update_filter_info_banner(filter_data, results_data, language):
    """Show an info banner indicating how many solutions will be used for clustering."""
    lang = language if language else 'DE'
    
    if not results_data or not results_data.get('full_results_path'):
        return []
    
    if filter_data and filter_data.get('filtered_count') is not None:
        total = filter_data['total_count']
        filtered = filter_data['filtered_count']
        
        if filtered < total:
            return dbc.Alert(
                T[lang].get('STEP5_FILTER_ACTIVE_INFO', 'Clustering will use {filtered} of {total} solutions (filtered in Step 4).').format(
                    filtered=filtered, total=total
                ),
                color="info",
                className="mb-0"
            )
        else:
            return dbc.Alert(
                T[lang].get('STEP5_NO_FILTER_INFO', 'All {total} solutions will be used for clustering.').format(
                    total=total
                ),
                color="light",
                className="mb-0"
            )
    
    # No filter data yet — count solutions from results
    try:
        results_path = results_data.get('full_results_path')
        if results_path and os.path.exists(results_path):
            with open(results_path, 'rb') as f:
                list_of_elites = pickle.load(f)
            total = len(list_of_elites) if list_of_elites else 0
            return dbc.Alert(
                T[lang].get('STEP5_NO_FILTER_INFO', 'All {total} solutions will be used for clustering.').format(
                    total=total
                ),
                color="light",
                className="mb-0"
            )
    except Exception:
        pass
    
    return []


@callback(
    Output('cluster-results-container', 'children'),
    Output('clustering-data-store', 'data'),  # Store ACTUAL cluster data for Step 6
    Input('run-analysis-btn', 'n_clicks'),
    State('results-store', 'data'),
    State('filter-store', 'data'),
    State('algorithm-selector', 'value'),
    State('kmedoids-k-slider', 'value'),
    State('hierarchical-k-slider', 'value'),
    State('similarity-metric-selector', 'value'),
    State('language-store', 'data'),
    prevent_initial_call=True
)
def run_and_display_analysis(n_clicks, results_data, filter_data,
                             algorithm, k_medoids, k_hierarchical, similarity_metric, lang):
    if not n_clicks: return no_update, no_update
    if lang is None: lang = 'DE'  # Default to German

    results_path = results_data.get('full_results_path')
    grid_geojson = results_data.get('grid_geojson')
    if not results_path or not grid_geojson:
        return dbc.Alert(T[lang]['STEP5_NO_RESULTS_ERROR'], color="danger"), no_update
    
    # Build feature_filters from filter-store (Step 4 slider state) using positional indices
    feature_filters = {}
    if filter_data and filter_data.get('slider_values'):
        slider_values = filter_data['slider_values']
        for i, s_val in enumerate(slider_values):
            if s_val is not None:
                feature_filters[i] = s_val

    
    # Translate to show human-readable feature names
    from backend.translation import translate_feature_labels
    selected_feature_indices = results_data.get('selected_features_indices', [])
    feature_set = results_data.get('feature_set', 'consolidated')
    feature_labels = translate_feature_labels(selected_feature_indices, lang, feature_set)
    

    params = {}
    if algorithm == 'kmedoids':
        params = {'n_clusters': k_medoids}
    elif algorithm == 'hdbscan':
        # Use fixed min_cluster_size of 5 to avoid classifying most samples as noise
        params = {'min_cluster_size': 5}
    elif algorithm == 'hierarchical':
        params = {'n_clusters': k_hierarchical}

    clusters = cluster_and_analyze_solutions(results_path, algorithm, params, feature_filters, similarity_metric=similarity_metric)
    
    if not clusters:
        return dbc.Alert(T[lang]['STEP5_NO_CLUSTERS_FOUND'], color="warning"), no_update
    
    # Store the ACTUAL cluster data for Step 6 (not re-clustering params!)
    # This way Step 6 uses the exact same clusters without recomputing
    clustering_data = {
        'clusters': clusters,  # The actual cluster results
        'algorithm': algorithm,  # Store for display purposes only
        'params': params,  # Store for display purposes only
        'feature_filters': feature_filters
    }
    

    lons = [c[0] for f in grid_geojson['features'] for c in f['geometry']['coordinates'][0]]
    lats = [c[1] for f in grid_geojson['features'] for c in f['geometry']['coordinates'][0]]
    map_center = [(min(lats) + max(lats)) / 2, (min(lons) + max(lons)) / 2]
    heightmap_res = results_data['xy_length']

    # Calculate max count across all clusters for uniform y-axis scaling
    max_count = 0
    for cluster in clusters:
        objective_values = cluster['objective_values']
        hist, _ = np.histogram(objective_values, bins=20, range=(0, 1))
        max_count = max(max_count, hist.max())

    cluster_cards = []
    for cluster in clusters:
        best_hm = np.array(cluster['best_solution']['heightmap']).reshape(heightmap_res, heightmap_res)
        best_geojson = heightmap_to_geojson(np.flipud(best_hm), grid_geojson)
        best_map = dl.Map(center=map_center, zoom=14, children=[
            dl.TileLayer(url="https://{s}.basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}{r}.png"),
            dl.GeoJSON(data=best_geojson, options=dict(style=style_handle), hideout={'z_length': int(ENCODING_CONFIG['max_building_floors'] * ENCODING_CONFIG['meters_per_floor'])})
        ], style={'height': '200px', 'width': '100%'})
        
        central_hm = np.array(cluster['central_solution']['heightmap']).reshape(heightmap_res, heightmap_res)
        central_geojson = heightmap_to_geojson(np.flipud(central_hm), grid_geojson)
        central_map = dl.Map(center=map_center, zoom=14, children=[
            dl.TileLayer(url="https://{s}.basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}{r}.png"),
            dl.GeoJSON(data=central_geojson, options=dict(style=style_handle), hideout={'z_length': int(ENCODING_CONFIG['max_building_floors'] * ENCODING_CONFIG['meters_per_floor'])})
        ], style={'height': '200px', 'width': '100%'})

        consensus_map_data = np.array(cluster['consensus_map']).reshape(heightmap_res, heightmap_res)
        consensus_fig = px.imshow(consensus_map_data, color_continuous_scale='Blues', origin='lower', zmin=0, zmax=1, aspect='equal')
        consensus_fig.update_layout(margin=dict(l=0, r=0, t=0, b=0), coloraxis_showscale=False)
        consensus_fig.update_xaxes(showticklabels=False).update_yaxes(showticklabels=False)
        consensus_graph = dcc.Graph(figure=consensus_fig, style={'height': '200px', 'width': '100%'})
        
        # Create histogram of objective function values for this cluster
        objective_values = cluster['objective_values']  # List of objective values for solutions in this cluster
        objective_label = T[lang].get('OBJECTIVE_FUNCTION', 'Objective Function')
        count_label = T[lang].get('COUNT', 'Count')
        
        # Create dataframe for proper histogram plotting
        df_hist = pd.DataFrame({objective_label: objective_values})
        
        histogram_fig = px.histogram(
            df_hist,
            x=objective_label,
            nbins=20,
            range_x=[0, 1],  # Fixed range for objective function (0 to 1)
            title=None
        )
        histogram_fig.update_layout(
            margin=dict(l=10, r=10, t=10, b=30),
            showlegend=False,
            height=200,
            xaxis_title=objective_label,
            yaxis_title=count_label,
            yaxis_range=[0, max_count * 1.05],  # Uniform y-axis across all clusters with 5% padding
            bargap=0.05,
            plot_bgcolor='white',
            paper_bgcolor='white'
        )
        histogram_fig.update_traces(
            marker_color='rgb(55, 126, 184)',  # Brighter blue
            marker_line_width=0.5,
            marker_line_color='rgb(30, 70, 120)',  # Darker blue outline
            opacity=0.85
        )
        histogram_graph = dcc.Graph(figure=histogram_fig, style={'height': '200px', 'width': '100%'})
        
        card = dbc.Card(dbc.CardBody([
            dbc.Checkbox(
                id={'type': 'compare-checkbox', 'index': cluster['cluster_id']},  # Use stable cluster_id
                label=T[lang]['STEP5_SELECT_FOR_COMPARISON'],
                value=False
            ),
            html.H5(T[lang]['STEP5_CLUSTER_CARD_TITLE'].format(id=cluster['cluster_id'], size=cluster['size'])),
            html.P(T[lang]['STEP5_CLUSTER_CARD_TEXT'].format(size=cluster['size']), className="text-muted small"),
            dbc.Row([
                dbc.Col([html.H6(T[lang]['STEP5_BEST_SOLUTION_HEADER']), best_map], md=3),
                dbc.Col([html.H6(T[lang]['STEP5_CENTRAL_SOLUTION_HEADER']), central_map], md=3),
                dbc.Col([html.H6(T[lang]['STEP5_CONSENSUS_MAP_HEADER']), consensus_graph], md=3),
                dbc.Col([html.H6(T[lang].get('OBJECTIVE_DISTRIBUTION', 'Objective Distribution')), histogram_graph], md=3)
            ])
        ]), className="mb-3")
        cluster_cards.append(card)
        
    return cluster_cards, clustering_data


@callback(
    Output('comparison-store', 'data', allow_duplicate=True),
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
