#
# pages/step6_compare_detail.py
#
from dash import dcc, html, Input, Output, State, callback, ALL, MATCH, ctx, no_update
import dash_bootstrap_components as dbc
from dash_extensions.javascript import assign
from backend.translation import T
import pickle
import os
import dash_leaflet as dl
import pandas as pd
import numpy as np
import plotly.graph_objects as go
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

def create_3d_building_plot(heightmap, grid_geojson, height_exaggeration=1.0, 
                            camera_state=None, pixel_size_m=3.0):
    """
    Create a 3D visualization of the building design as voxel blocks
    
    Args:
        heightmap: 2D numpy array of building heights (in floors)
        grid_geojson: GeoJSON with spatial reference
        height_exaggeration: Factor to exaggerate building heights for visualization
        camera_state: Dict with camera position/orientation to sync across views
        pixel_size_m: Size of each grid pixel in meters (default 3m per floor)
    """
    # Convert heightmap to meters (3m per floor)
    heightmap_meters = heightmap * pixel_size_m * height_exaggeration
    
    # Create grid coordinates
    rows, cols = heightmap_meters.shape
    
    # Create the 3D figure
    fig = go.Figure()
    
    # Create voxel blocks using Mesh3d
    # For each non-zero cell, create a box from 0 to its height
    x_coords = []
    y_coords = []
    z_coords = []
    i_indices = []
    j_indices = []
    k_indices = []
    colors = []
    
    # Color scale for heights
    max_height = heightmap_meters.max() if heightmap_meters.max() > 0 else 1
    
    vertex_count = 0
    for row in range(rows):
        for col in range(cols):
            height = heightmap_meters[row, col]
            if height > 0:
                # Define the 8 vertices of the box
                x0, x1 = col * pixel_size_m, (col + 1) * pixel_size_m
                y0, y1 = row * pixel_size_m, (row + 1) * pixel_size_m
                z0, z1 = 0, height
                
                # 8 vertices of the box
                vertices = [
                    [x0, y0, z0], [x1, y0, z0], [x1, y1, z0], [x0, y1, z0],  # bottom
                    [x0, y0, z1], [x1, y0, z1], [x1, y1, z1], [x0, y1, z1]   # top
                ]
                
                for v in vertices:
                    x_coords.append(v[0])
                    y_coords.append(v[1])
                    z_coords.append(v[2])
                
                # 12 triangles (2 per face, 6 faces)
                faces = [
                    [0, 1, 2], [0, 2, 3],  # bottom
                    [4, 5, 6], [4, 6, 7],  # top
                    [0, 1, 5], [0, 5, 4],  # front
                    [2, 3, 7], [2, 7, 6],  # back
                    [0, 3, 7], [0, 7, 4],  # left
                    [1, 2, 6], [1, 6, 5]   # right
                ]
                
                for face in faces:
                    i_indices.append(vertex_count + face[0])
                    j_indices.append(vertex_count + face[1])
                    k_indices.append(vertex_count + face[2])
                
                # Color based on height (normalized)
                color_val = height / max_height
                colors.extend([color_val] * 8)  # One color per vertex
                
                vertex_count += 8
    
    # Add the mesh if there are any buildings
    if vertex_count > 0:
        fig.add_trace(go.Mesh3d(
            x=x_coords,
            y=y_coords,
            z=z_coords,
            i=i_indices,
            j=j_indices,
            k=k_indices,
            intensity=colors,
            colorscale='Viridis',
            showscale=False,
            name='Buildings',
            hovertemplate='X: %{x:.1f}m<br>Y: %{y:.1f}m<br>Höhe: %{z:.1f}m<extra></extra>',
            flatshading=True,  # Sharp edges for voxel look
            lighting=dict(ambient=0.6, diffuse=0.8, specular=0.1, roughness=0.9)
        ))
    
    # Add ground plane
    x_ground = [0, cols * pixel_size_m, cols * pixel_size_m, 0]
    y_ground = [0, 0, rows * pixel_size_m, rows * pixel_size_m]
    z_ground = [0, 0, 0, 0]
    
    fig.add_trace(go.Mesh3d(
        x=x_ground,
        y=y_ground,
        z=z_ground,
        i=[0, 0],
        j=[1, 2],
        k=[2, 3],
        color='lightgray',
        opacity=0.3,
        name='Ground',
        hoverinfo='skip',
        showlegend=False
    ))
    
    # Calculate scene bounds
    x_range = [0, cols * pixel_size_m]
    y_range = [0, rows * pixel_size_m]
    z_range = [0, max(heightmap_meters.max() * 1.2, 30)]  # At least 30m for empty scenes
    
    # Set camera
    if camera_state:
        # Use provided camera state for syncing
        camera = camera_state
    else:
        # Aerial oblique view
        camera = dict(
            eye=dict(x=1.5, y=1.5, z=1.2),
            center=dict(x=0.5, y=0.5, z=0.2),
            up=dict(x=0, y=0, z=1)
        )
    
    # Update layout
    fig.update_layout(
        scene=dict(
            xaxis=dict(title='X (m)', range=x_range, showgrid=True),
            yaxis=dict(title='Y (m)', range=y_range, showgrid=True),
            zaxis=dict(title='Z (m)', range=z_range, showgrid=True),
            camera=camera,
            aspectmode='manual',
            aspectratio=dict(x=1, y=1, z=0.5)
        ),
        height=600,
        margin=dict(l=0, r=0, t=30, b=0),
        hovermode='closest'
    )
    
    return fig

def layout(lang='DE'):
    return dbc.Container([
    dcc.Location(id='url-s6', refresh=False),
    html.H2(T[lang]['STEP6_TITLE']),
        dbc.Row([
            dbc.Col(dbc.Button(T[lang]['PREV_STEP'], href='/step4', color="secondary")),
            dbc.Col([
                dbc.Button(T[lang]['STEP6_EXPORT_PDF'], id="export-pdf-btn-s6", color="info"),
                dcc.Download(id="download-pdf-s6")
            ], className="text-end")
        ], className="mt-4 mb-4"),
        
        # Store for syncing camera state
        dcc.Store(id='camera-sync-store', data={}),
        # Store for solution display mode (central vs best) per cluster
        dcc.Store(id='solution-mode-store', data={}),
        
        dcc.Loading(html.Div(id='comparison-content'))
    ], fluid=True)


@callback(
    Output('comparison-content', 'children'),
    Input('comparison-store', 'data'),
    Input('results-store', 'data'),
    Input('solution-mode-store', 'data'),
    State('language-store', 'data'),
    State('camera-sync-store', 'data')
)
def display_comparison(selected_ids, results_data, solution_modes, lang, camera_state):
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
    
    # Load cluster data to get both best and central solutions
    from backend.analysis import cluster_and_analyze_solutions
    
    # Get clustering results (use default k-medoids with k=10)
    clusters = cluster_and_analyze_solutions(results_path, 'kmedoids', {'n_clusters': 10}, {})
    
    # Map selected IDs to their clusters
    solutions_to_compare = []
    solution_modes = solution_modes or {}  # Initialize if None
    
    for idx, cluster_id in enumerate(selected_ids):
        # Find the cluster with this central solution ID
        matching_cluster = None
        for cluster in clusters:
            if cluster['central_solution']['id'] == cluster_id:
                matching_cluster = cluster
                break
        
        if matching_cluster:
            # Get the display mode for this cluster (default to 'best')
            display_mode = solution_modes.get(str(idx), 'best')
            solutions_to_compare.append({
                'cluster': matching_cluster,
                'display_mode': display_mode,
                'index': idx
            })
    
    if not solutions_to_compare:
        return dbc.Alert(T[lang]['STEP6_IDS_NOT_FOUND'], color="warning")
    
    from backend.config import DOMAIN_CONFIG
    
    heightmap_res = results_data['xy_length']
    pixel_size = DOMAIN_CONFIG.get('pixel_size_in_meters', 3.0)  # Default 3m per pixel
    
    # Get feature translation setup
    from backend.translation import translate_feature_labels
    from backend.units import format_value_with_unit
    feature_indices = results_data.get('selected_features_indices', [])
    labels = translate_feature_labels(feature_indices, lang)
    
    cols = []
    for sol_data in solutions_to_compare:
        cluster = sol_data['cluster']
        display_mode = sol_data.get('display_mode', 'best')
        i = sol_data['index']
        
        # Get the solution to display (central or best)
        sol = cluster['central_solution'] if display_mode == 'central' else cluster['best_solution']
        
        # Create heightmap
        heightmap = np.array(sol['heightmap']).reshape(heightmap_res, heightmap_res)
        
        # Create 3D visualization
        fig_3d = create_3d_building_plot(
            heightmap, 
            grid_geojson, 
            height_exaggeration=1.0,
            camera_state=camera_state,
            pixel_size_m=pixel_size
        )
        
        # Format values with physical units
        formatted_values = []
        for j, value in enumerate(sol['measures']):
            if j < len(feature_indices):
                feature_idx = feature_indices[j]
                formatted_values.append(format_value_with_unit(value, feature_idx, lang))
            else:
                formatted_values.append(f"{value:.3f}")  # Fallback
        
        metrics_data = {T[lang]['STEP6_FEATURE_LABEL']: labels, T[lang]['STEP6_VALUE_LABEL']: formatted_values}
        metrics_df = pd.DataFrame(metrics_data)
        table = dbc.Table.from_dataframe(metrics_df, striped=True, bordered=True, hover=True, size='sm')
        
        # Format objective with unit
        objective_unit = T[lang].get('OBJECTIVE_UNIT', '')
        objective_formatted = T[lang]['STEP6_OBJECTIVE_LABEL'].format(value=sol['objective'])
        if objective_unit:
            objective_formatted = f"{objective_formatted} {objective_unit}"
        
        # Create toggle for best/central solution
        toggle_radio = dbc.RadioItems(
            id={'type': 'solution-toggle', 'index': i},
            options=[
                {'label': 'Zentrale Lösung' if lang == 'DE' else 'Central Solution', 'value': 'central'},
                {'label': 'Beste Lösung' if lang == 'DE' else 'Best Solution', 'value': 'best'}
            ],
            value=display_mode,
            inline=True,
            className="mb-2"
        )
        
        col = dbc.Col([
            html.H5(f"Cluster {cluster['cluster_id']} ({cluster['size']} " + 
                   ("Lösungen" if lang == 'DE' else "solutions") + ")"),
            toggle_radio,
            html.B(objective_formatted, className="d-block mb-2"),
            dcc.Graph(
                figure=fig_3d,
                id={'type': '3d-plot', 'index': i},
                config={'displayModeBar': True, 'displaylogo': False},
                style={'height': '600px'}
            ),
            html.H6(T[lang]['STEP6_METRICS_HEADER'], className="mt-3"),
            html.Div(table, style={'maxHeight': '200px', 'overflowY': 'auto'})
        ], md=4)
        cols.append(col)
    
    return dbc.Row(cols)

# Callback to sync camera positions across all 3D plots
@callback(
    Output('camera-sync-store', 'data'),
    Input({'type': '3d-plot', 'index': ALL}, 'relayoutData'),
    State('camera-sync-store', 'data'),
    prevent_initial_call=True
)
def sync_camera_positions(relayout_data_list, current_camera_state):
    """Synchronize camera position across all 3D views"""
    # Find which plot triggered the callback
    triggered = ctx.triggered_id
    
    if not triggered or not relayout_data_list:
        return no_update
    
    # Get the index of the plot that was updated
    trigger_idx = triggered.get('index', 0)
    
    # Get the relayout data from the triggered plot
    relayout_data = relayout_data_list[trigger_idx] if trigger_idx < len(relayout_data_list) else {}
    
    # Check if camera was updated
    if relayout_data and 'scene.camera' in relayout_data:
        # Extract camera state
        new_camera = relayout_data['scene.camera']
        return new_camera
    
    return no_update


# Callback to handle solution toggle (central vs best)
@callback(
    Output('solution-mode-store', 'data'),
    Input({'type': 'solution-toggle', 'index': ALL}, 'value'),
    State('solution-mode-store', 'data'),
    prevent_initial_call=True
)
def toggle_solution_mode(values_list, current_modes):
    """Update which solution mode is active for each cluster"""
    if not ctx.triggered_id:
        return no_update
    
    # Get which radio was changed
    trigger_idx = ctx.triggered_id.get('index', 0)
    
    # Initialize modes dict if empty
    if not current_modes:
        current_modes = {}
    
    # Update the mode for this cluster index with the new value
    if trigger_idx < len(values_list):
        new_value = values_list[trigger_idx]
        current_modes[str(trigger_idx)] = new_value
    
    return current_modes


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

    # Translate feature labels (use German for PDF report - could be made configurable)
    from backend.translation import translate_feature_labels
    feature_indices = results_data.get('selected_features_indices', [])
    labels = translate_feature_labels(feature_indices, 'DE')  # PDF in German

    pdf_content = generate_pdf_report(
        solutions_to_compare,
        list_of_elites, # Pass all elites for correlation analysis
        labels,
        results_data['grid_geojson'],
        results_data['xy_length']
    )

    if pdf_content:
        return dict(content=pdf_content, filename="OpenSKIZZE_Vergleichsbericht.zip", base64=True)
    else:
        return dict(content="Error: Failed to generate PDF report.", filename="error.txt")