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
from backend.analysis import heightmap_to_geojson
from backend.config import ENCODING_CONFIG

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
        html.H2("Detailvergleich der ausgewählten Entwürfe"),
        dbc.Row([
            dbc.Col(dbc.Button(T[LANG]['PREV_STEP'], href='/step5', color="secondary")),
        ], className="mt-4 mb-4"),
        dcc.Loading(html.Div(id='comparison-content'))
    ], fluid=True)


@callback(
    Output('comparison-content', 'children'),
    Input('comparison-store', 'data'), # Triggered by page load via data in store
    State('results-store', 'data')
)
def display_comparison(selected_ids, results_data):
    if not selected_ids or not results_data:
        return dbc.Alert("Keine Entwürfe zum Vergleich ausgewählt.", color="warning")

    results_path = results_data.get('full_results_path')
    grid_geojson = results_data.get('grid_geojson')
    if not os.path.exists(results_path) or not grid_geojson:
        return dbc.Alert("Ergebnisdatei oder Georeferenzierung nicht gefunden.", color="danger")

    with open(results_path, 'rb') as f:
        list_of_elites = pickle.load(f)
    
    # Find the selected solutions
    solutions_to_compare = [s for s in list_of_elites if s['id'] in selected_ids]
    lons = [c[0] for f in grid_geojson['features'] for c in f['geometry']['coordinates'][0]]
    lats = [c[1] for f in grid_geojson['features'] for c in f['geometry']['coordinates'][0]]
    map_center = [(min(lats) + max(lats)) / 2, (min(lons) + max(lons)) / 2]
    heightmap_res = results_data['xy_length']
    
    # Create the comparison layout
    cols = []
    for i, sol in enumerate(solutions_to_compare):
        # Map component
        heightmap = np.array(sol['heightmap']).reshape(...)
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
        
        # Metrics table
        metrics_data = {'Merkmal': results_data['labels'], 'Wert': [f"{v:.3f}" for v in sol['measures']]}
        metrics_df = pd.DataFrame(metrics_data)
        table = dbc.Table.from_dataframe(metrics_df, striped=True, bordered=True, hover=True)
        
        col = dbc.Col([
            html.H4(f"Entwurf {i+1}"),
            html.B(f"Zielfunktion (Kaltluft): {sol['objective']:.4f}"),
            map_component,
            html.H5("Leistungsmerkmale", className="mt-3"),
            table
        ], width=4)
        cols.append(col)
        
    return dbc.Row(cols)