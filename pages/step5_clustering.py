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
        
        # Reorganized layout with filter controls in left column
        dbc.Row([
            # Left column: Filtering Controls
            dbc.Col([
                dbc.Card(dbc.CardBody([
                    html.H4(T[lang]['STEP5_FILTER_HEADER']),
                    html.P(T[lang]['STEP5_FILTER_INFO'], className="text-muted"),
                    html.Div(id='feature-filter-controls'),
                ])),
                
            ], md=5),
            
            # Right column: Clustering Results
            dbc.Col([
                dbc.Card(dbc.CardBody([
                    html.H4(T[lang]['STEP5_ALGORITHM_LABEL']),
                    dbc.RadioItems(
                        id='algorithm-selector',
                        options=[
                            {'label': T[lang]['STEP5_ALG_HDBSCAN'], 'value': 'hdbscan'},
                            {'label': T[lang]['STEP5_ALG_KMEDOIDS'], 'value': 'kmedoids'},
                        ],
                        value='hdbscan',
                        inline=True,
                        className="mb-3"
                    ),

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
                
                html.H4(T[lang]['STEP5_ANALYSIS_HEADER']),
                dcc.Loading(html.Div(id='cluster-results-container', children=[
                     dbc.Alert(T[lang]['STEP5_NO_SELECTION'], color="light")
                ])),
            ], md=7),
        ], className="mb-4"),
        
    ], fluid=True)


@callback(
    Output('hdbscan-params-div', 'style'),
    Output('kmedoids-params-div', 'style'),
    Input('algorithm-selector', 'value')
)
def toggle_parameter_sliders(selected_algorithm):
    if selected_algorithm == 'kmedoids':
        return {'display': 'none'}, {'display': 'block'}
    elif selected_algorithm == 'hdbscan':
        return {'display': 'block'}, {'display': 'none'}
    return {'display': 'none'}, {'display': 'none'}


@callback(
    Output('feature-filter-controls', 'children'),
    Input('results-store', 'data'),
    Input('language-store', 'data'),
)
def create_filter_controls(results_data, language):
    if not results_data or not results_data.get('full_results_path'):
        return []
    
    # Get current language (default to 'DE')
    lang = language if language else 'DE'
    
    results_path = results_data.get('full_results_path')
    if not os.path.exists(results_path):
        return []
    
    with open(results_path, 'rb') as f:
        list_of_elites = pickle.load(f)
    
    # Translate feature labels based on current language and feature set
    from backend.translation import translate_feature_labels
    from backend.units import get_unit_label
    selected_feature_indices = results_data.get('selected_features_indices', [])
    feature_set = results_data.get('feature_set', 'original')
    if not selected_feature_indices: return no_update
    
    labels = translate_feature_labels(selected_feature_indices, lang, feature_set)
    
    # Extract measures data to get actual ranges from optimization results
    measures_data = np.array([e['measures'] for e in list_of_elites if e is not None])
    if measures_data.size == 0:
        return []
    
    # Create filter sliders for each feature
    sliders = []
    num_buildings_original_index = 3  # Feature index for "Number of Buildings"
    
    for i, label in enumerate(labels):
        current_feature_index = selected_feature_indices[i]
        unit = get_unit_label(current_feature_index, lang)
        label_with_unit = f"{label} ({unit})" if unit else label
        
        # Get min/max from actual results data
        min_val, max_val = measures_data[:, i].min(), measures_data[:, i].max()
        
        # Integer slider for Number of Buildings
        if current_feature_index == num_buildings_original_index:
            min_v = int(np.floor(min_val))
            max_v = int(np.ceil(max_val))
            if min_v == max_v: max_v += 1
            
            slider_div = html.Div([
                dbc.Label(label_with_unit),
                dcc.RangeSlider(
                    id={'type': 'filter-slider', 'index': i},
                    min=min_v, max=max_v, step=1,
                    value=[min_v, max_v],
                    tooltip={"placement": "bottom", "always_visible": True},
                    marks=None,
                )
            ], className="mb-2")
        # Normalized sliders for Building Mass X/Y (0-1)
        elif current_feature_index in [6, 7]:
            slider_div = html.Div([
                dbc.Label(label_with_unit),
                dcc.RangeSlider(
                    id={'type': 'filter-slider', 'index': i},
                    min=0.0, max=1.0, step=0.01,
                    value=[0.0, 1.0],
                    tooltip={"placement": "bottom", "always_visible": True},
                    marks=None,
                )
            ], className="mb-2")
        # Physical unit sliders (m, m²)
        else:
            min_v = round(min_val, 1)
            max_v = round(max_val, 1)
            if min_v == max_v: max_v = min_v + 1.0
            
            # Determine appropriate step size
            if max_v - min_v > 100:
                step = 1.0
            elif max_v - min_v > 10:
                step = 0.5
            else:
                step = 0.1
            
            slider_div = html.Div([
                dbc.Label(label_with_unit),
                dcc.RangeSlider(
                    id={'type': 'filter-slider', 'index': i},
                    min=min_v, max=max_v, step=step,
                    value=[min_v, max_v],
                    tooltip={"placement": "bottom", "always_visible": True},
                    marks=None,
                )
            ], className="mb-2")
        
        sliders.append(slider_div)
    
    return sliders


@callback(
    Output('cluster-results-container', 'children'),
    Output('clustering-data-store', 'data'),  # Store ACTUAL cluster data for Step 6
    Input('run-analysis-btn', 'n_clicks'),
    State('results-store', 'data'),
    State({'type': 'filter-slider', 'index': ALL}, 'value'),
    State({'type': 'filter-slider', 'index': ALL}, 'id'),
    State('algorithm-selector', 'value'),
    State('kmedoids-k-slider', 'value'),
    State('language-store', 'data'),
    prevent_initial_call=True
)
def run_and_display_analysis(n_clicks, results_data, slider_values, slider_ids, 
                             algorithm, k, lang):
    if not n_clicks: return no_update, no_update
    if lang is None: lang = 'DE'  # Default to German

    results_path = results_data.get('full_results_path')
    grid_geojson = results_data.get('grid_geojson')
    if not results_path or not grid_geojson:
        return dbc.Alert(T[lang]['STEP5_NO_RESULTS_ERROR'], color="danger"), no_update
        
    feature_filters = {s_id['index']: s_val for s_id, s_val in zip(slider_ids, slider_values)}

    
    # Translate to show human-readable feature names
    from backend.translation import translate_feature_labels
    selected_feature_indices = results_data.get('selected_features_indices', [])
    feature_set = results_data.get('feature_set', 'original')
    feature_labels = translate_feature_labels(selected_feature_indices, lang, feature_set)
    

    params = {}
    if algorithm == 'kmedoids':
        params = {'n_clusters': k}
    elif algorithm == 'hdbscan':
        # Use fixed min_cluster_size of 5 to avoid classifying most samples as noise
        params = {'min_cluster_size': 5}

    clusters = cluster_and_analyze_solutions(results_path, algorithm, params, feature_filters)
    
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
