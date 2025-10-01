#
# pages/step6_compare_detail.py
#
from dash import dcc, html, Input, Output, State, callback
import dash_bootstrap_components as dbc
from dash_extensions.javascript import assign
from backend.translation import T
import pickle
import os
import dash_leaflet as dl
import pandas as pd
import numpy as np
from backend.analysis import heightmap_to_geojson, generate_pdf_report
from backend.config import ENCODING_CONFIG

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
    return dbc.Container([
    dcc.Location(id='url-s6', refresh=False),
    html.H2(T[lang]['STEP6_TITLE']),
        dbc.Row([
            dbc.Col(dbc.Button(T[lang]['PREV_STEP'], href='/step5', color="secondary")),
            dbc.Col([
                dbc.Button(T[lang]['STEP6_EXPORT_PDF'], id="export-pdf-btn-s6", color="info"),
                dcc.Download(id="download-pdf-s6")
            ], className="text-end")
        ], className="mt-4 mb-4"),
        dcc.Loading(html.Div(id='comparison-content'))
    ], fluid=True)


@callback(
    Output('comparison-content', 'children'),
    Input('comparison-store', 'data'),
    Input('results-store', 'data'),
    State('language-store', 'data')
)
def display_comparison(selected_ids, results_data, lang):
    if lang is None: lang = 'DE'  # Default to German
    
    if not selected_ids:
        return dbc.Alert(T[lang]['STEP6_NO_SELECTION'], color="info")

    if not results_data:
        return dbc.Alert(T[lang]['STEP6_NO_RESULTS'], color="danger")
    
    results_path = results_data.get('full_results_path')
    grid_geojson = results_data.get('grid_geojson')
    if not os.path.exists(results_path) or not grid_geojson:
        return dbc.Alert(T[lang]['STEP6_FILE_NOT_FOUND'], color="danger")

    with open(results_path, 'rb') as f:
        list_of_elites = pickle.load(f)
    
    solutions_to_compare = [s for s in list_of_elites if s['id'] in selected_ids]
    if not solutions_to_compare:
        return dbc.Alert(T[lang]['STEP6_IDS_NOT_FOUND'], color="warning")
    
    lons = [c[0] for f in grid_geojson['features'] for c in f['geometry']['coordinates'][0]]
    lats = [c[1] for f in grid_geojson['features'] for c in f['geometry']['coordinates'][0]]
    map_center = [(min(lats) + max(lats)) / 2, (min(lons) + max(lons)) / 2]
    heightmap_res = results_data['xy_length']
    
    cols = []
    for i, sol in enumerate(solutions_to_compare):
        heightmap = np.array(sol['heightmap']).reshape(heightmap_res, heightmap_res)
        design_geojson = heightmap_to_geojson(np.flipud(heightmap), grid_geojson)
        map_component = dl.Map(
            center=map_center, zoom=14,
            children=[
                dl.TileLayer(url="https://{s}.basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}{r}.png"),
                dl.GeoJSON(data=design_geojson, options=dict(style=style_handle), 
                           hideout={'z_length': ENCODING_CONFIG['z_length']})
            ], 
            style={'width': '100%', 'height': '250px'},
            id={'type': 'compare-map', 'index': i}
        )
        
        metrics_data = {T[lang]['STEP6_FEATURE_LABEL']: results_data['labels'], T[lang]['STEP6_VALUE_LABEL']: [f"{v:.3f}" for v in sol['measures']]}
        metrics_df = pd.DataFrame(metrics_data)
        table = dbc.Table.from_dataframe(metrics_df, striped=True, bordered=True, hover=True)
        
        col = dbc.Col([
            html.H4(T[lang]['STEP6_DESIGN_TITLE'].format(num=i+1)),
            html.B(T[lang]['STEP6_OBJECTIVE_LABEL'].format(value=sol['objective'])),
            map_component,
            html.H5(T[lang]['STEP6_METRICS_HEADER'], className="mt-3"),
            table
        ], width=4)
        cols.append(col)
        
    return dbc.Row(cols)

@callback(
    Output("download-pdf-s6", "data"),
    Input("export-pdf-btn-s6", "n_clicks"),
    State('comparison-store', 'data'),
    State('results-store', 'data'),
    prevent_initial_call=True,
)
def export_pdf_report_s6(n_clicks, selected_ids, results_data):
    if not n_clicks or not selected_ids or not results_data:
        return None

    results_path = results_data.get('full_results_path')
    if not os.path.exists(results_path):
        return dict(content="Error: Results file not found.", filename="error.txt")

    with open(results_path, 'rb') as f:
        list_of_elites = pickle.load(f)

    solutions_to_compare = [s for s in list_of_elites if s['id'] in selected_ids]
    
    if not solutions_to_compare:
        return dict(content="Error: Selected solutions not found in results.", filename="error.txt")

    pdf_content = generate_pdf_report(
        solutions_to_compare,
        list_of_elites, # Pass all elites for correlation analysis
        results_data['labels'],
        results_data['grid_geojson'],
        results_data['xy_length']
    )

    if pdf_content:
        return dict(content=pdf_content, filename="OpenSKIZZE_Vergleichsbericht.zip", base64=True)
    else:
        return dict(content="Error: Failed to generate PDF report.", filename="error.txt")