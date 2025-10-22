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

def generate_distinct_colors(n):
    """
    Generate n visually distinct colors using HSV color space.
    Avoids blue (reserved for new design).
    """
    import colorsys
    colors = []
    # Skip blue range (180-240 degrees) as it's reserved for new design
    hue_ranges = [(0, 0.45), (0.55, 1.0)]  # Red to cyan, then green to magenta (skip blue)
    
    total_range = sum(end - start for start, end in hue_ranges)
    step = total_range / n if n > 0 else 0
    
    for i in range(n):
        # Map to non-blue hue ranges
        target_pos = (i * step) % total_range
        
        # Find which range this falls into
        accumulated = 0
        for start, end in hue_ranges:
            range_size = end - start
            if target_pos < accumulated + range_size:
                hue = start + (target_pos - accumulated)
                break
            accumulated += range_size
        else:
            hue = hue_ranges[0][0]
        
        # Convert HSV to RGB (high saturation and value for distinct colors)
        rgb = colorsys.hsv_to_rgb(hue, 0.7, 0.8)
        colors.append(f'rgb({int(rgb[0]*255)}, {int(rgb[1]*255)}, {int(rgb[2]*255)})')
    
    return colors

def create_3d_building_plot(heightmap, grid_bounds_native, env_3d_fixed=None, height_exaggeration=1.0, 
                            camera_state=None, pixel_size_m=3.0, expanded_bounds_native=None, design_offset=None,
                            building_function_map=None, function_lookup=None):
    """
    Create a 3D visualization of the building design as voxel blocks in geographic coordinates
    
    Args:
        heightmap: 2D numpy array of building heights (in meters, 0-33)
        grid_bounds_native: (min_x, min_y, max_x, max_y) in EPSG:25832 for design area
        env_3d_fixed: 3D array of existing buildings (optional, may be larger than design grid)
        height_exaggeration: Factor to exaggerate building heights for visualization
        camera_state: Dict with camera position/orientation to sync across views
        pixel_size_m: Size of each grid pixel in meters (default 3m)
        expanded_bounds_native: (min_x, min_y, max_x, max_y) for expanded visualization area (optional)
        design_offset: (row_offset, col_offset) for design placement within expanded grid (optional)
    """
    # Heightmap values are already in METERS (not floors)
    # This ensures design buildings match the real heights from NRW LOD2 data
    heightmap_meters = heightmap * height_exaggeration
    
    # Get grid dimensions for design
    rows, cols = heightmap_meters.shape
    min_x, min_y, max_x, max_y = grid_bounds_native
    
    # Create geographic coordinate mapping for design
    x_coords_geo = np.linspace(min_x, max_x, cols + 1)
    y_coords_geo = np.linspace(min_y, max_y, rows + 1)
    
    # Create the 3D figure
    fig = go.Figure()
    
    # Helper function to create solid building blocks
    def add_voxel_blocks(height_array, color_value, name, opacity=1.0, show_in_legend=True, voxel_size=3, 
                        x_coords=None, y_coords=None, function_map=None, func_lookup=None):
        # Use provided coordinates or default to design grid coordinates
        if x_coords is None:
            x_coords_base = x_coords_geo
        else:
            x_coords_base = x_coords
        if y_coords is None:
            y_coords_base = y_coords_geo
        else:
            y_coords_base = y_coords
        """
        Render buildings as solid blocks using go.Surface for smoother appearance
        """
        # Group connected cells into larger meshes to reduce seams
        processed = np.zeros_like(height_array, dtype=bool)
        x_coords_list = []
        y_coords_list = []
        z_coords_list = []
        i_indices = []
        j_indices = []
        k_indices = []
        
        vertex_count = 0
        
        # Process each cell and try to merge with neighbors of same height
        for row in range(height_array.shape[0]):
            for col in range(height_array.shape[1]):
                if processed[row, col] or height_array[row, col] <= 1.5:  # Skip if less than half a floor
                    continue
                
                height = height_array[row, col]
                
                # Find the rectangular extent of cells with same height
                # Start with current cell
                min_row, max_row = row, row + 1
                min_col, max_col = col, col + 1
                
                # Expand horizontally (col direction) first
                while max_col < height_array.shape[1] and \
                      not processed[row, max_col] and \
                      abs(height_array[row, max_col] - height) < 1.5:  # Within 1.5m = same floor level
                    max_col += 1
                
                # Try to expand vertically (row direction) with same width
                can_expand = True
                while can_expand and max_row < height_array.shape[0]:
                    for c in range(min_col, max_col):
                        if processed[max_row, c] or abs(height_array[max_row, c] - height) >= 1.5:
                            can_expand = False
                            break
                    if can_expand:
                        max_row += 1
                
                # Mark all cells in this rectangle as processed
                processed[min_row:max_row, min_col:max_col] = True
                
                # Get building function if available
                building_func = None
                if function_map is not None and func_lookup is not None:
                    # Get function ID from the center of the building
                    center_row = (min_row + max_row) // 2
                    center_col = (min_col + max_col) // 2
                    func_id = function_map[center_row, center_col]
                    building_func = func_lookup.get(func_id, 'Unbekannt')
                
                # Get geographic coordinates for this merged rectangle
                x0, x1 = x_coords_base[min_col], x_coords_base[max_col]
                y0, y1 = y_coords_base[min_row], y_coords_base[max_row]
                z0, z1 = 0, height
                
                # Create ONE solid box for this merged region
                vertices = [
                    [x0, y0, z0], [x1, y0, z0], [x1, y1, z0], [x0, y1, z0],  # bottom
                    [x0, y0, z1], [x1, y0, z1], [x1, y1, z1], [x0, y1, z1]   # top
                ]
                
                for v in vertices:
                    x_coords_list.append(v[0])
                    y_coords_list.append(v[1])
                    z_coords_list.append(v[2])
                
                # 12 triangles (2 per face, 6 faces)
                faces = [
                    [0, 2, 1], [0, 3, 2],  # bottom
                    [4, 5, 6], [4, 6, 7],  # top
                    [0, 1, 5], [0, 5, 4],  # front
                    [3, 7, 6], [3, 6, 2],  # back
                    [0, 4, 7], [0, 7, 3],  # left
                    [1, 2, 6], [1, 6, 5]   # right
                ]
                
                for face in faces:
                    i_indices.append(vertex_count + face[0])
                    j_indices.append(vertex_count + face[1])
                    k_indices.append(vertex_count + face[2])
                
                vertex_count += 8
        
        if vertex_count > 0:
            # Safety check: ensure all lists have consistent lengths to avoid JavaScript zip errors
            if not (len(x_coords_list) == len(y_coords_list) == len(z_coords_list)):
                print(f"WARNING: Coordinate list length mismatch in add_voxel_blocks")
                return
            if not (len(i_indices) == len(j_indices) == len(k_indices)):
                print(f"WARNING: Index list length mismatch in add_voxel_blocks")
                return
            
            # Use a single mesh trace with all building blocks combined
            fig.add_trace(go.Mesh3d(
                x=x_coords_list,
                y=y_coords_list,
                z=z_coords_list,
                i=i_indices,
                j=j_indices,
                k=k_indices,
                color=color_value,
                opacity=opacity,
                showscale=False,
                name=name,
                showlegend=show_in_legend,
                hovertemplate=f'{name}<br>X: %{{x:.1f}}m<br>Y: %{{y:.1f}}m<br>Höhe: %{{z:.1f}}m<extra></extra>',
                flatshading=False,  # Smooth shading
                lighting=dict(
                    ambient=0.7,      # Higher ambient for well-lit buildings
                    diffuse=0.8,      # Good diffuse lighting
                    specular=0.2,     # Low specular to reduce shine
                    roughness=0.9,    # Very rough surfaces (matte)
                    fresnel=0.0       # No fresnel effect
                ),
                # Hide mesh edges
                contour=dict(show=False),
                lightposition=dict(x=1e5, y=1e5, z=1e5)  # Distant light source
            ))
    
    # Add existing buildings first (in gray, fully opaque)
    if env_3d_fixed is not None and env_3d_fixed.size > 0:
        # Convert env_3d_fixed to heightmap (max height in each column)
        # env_3d_fixed z-axis is already in meters (1 voxel = 1 meter)
        # No multiplication needed - heights are already correct
        existing_heightmap = np.sum(env_3d_fixed > 0, axis=2) * height_exaggeration
        
        # DEBUG: Print existing building stats
        existing_non_zero = existing_heightmap[existing_heightmap > 0]
        if len(existing_non_zero) > 0:
            print(f"    EXISTING buildings (gray): min={existing_non_zero.min():.2f}m, "
                  f"max={existing_non_zero.max():.2f}m, mean={existing_non_zero.mean():.2f}m")
        
        if existing_heightmap.max() > 0:
            # Determine coordinates for existing buildings
            if expanded_bounds_native is not None:
                exp_min_x, exp_min_y, exp_max_x, exp_max_y = expanded_bounds_native
                exp_rows, exp_cols = existing_heightmap.shape
                x_coords_exp = np.linspace(exp_min_x, exp_max_x, exp_cols + 1)
                y_coords_exp = np.linspace(exp_min_y, exp_max_y, exp_rows + 1)
            else:
                x_coords_exp = x_coords_geo
                y_coords_exp = y_coords_geo
            
            # If we have building function data, create separate traces for each function type
            if building_function_map is not None and function_lookup:
                # Generate distinct colors for each function type
                func_colors = generate_distinct_colors(len(function_lookup))
                
                for idx, (func_id, func_name) in enumerate(sorted(function_lookup.items())):
                    # Create a mask for this function type
                    func_mask = building_function_map == func_id
                    # Create heightmap for only this function type
                    func_heightmap = existing_heightmap.copy()
                    func_heightmap[~func_mask] = 0
                    
                    if func_heightmap.max() > 0:
                        func_color = func_colors[idx] if idx < len(func_colors) else 'rgb(140, 140, 140)'
                        add_voxel_blocks(func_heightmap, func_color, f'Bestand: {func_name}', 
                                       opacity=1.0, show_in_legend=True, x_coords=x_coords_exp, y_coords=y_coords_exp)
            else:
                # No function data, show all as one group
                add_voxel_blocks(existing_heightmap, 'rgb(140, 140, 140)', 'Bestand', 
                               opacity=1.0, show_in_legend=True, x_coords=x_coords_exp, y_coords=y_coords_exp)
    
    # Add new design buildings (in blue, fully opaque)
    if heightmap_meters.max() > 0:
        # DEBUG: Print new design building stats
        new_non_zero = heightmap_meters[heightmap_meters > 0]
        print(f"    NEW DESIGN buildings (blue): min={new_non_zero.min():.2f}m, "
              f"max={new_non_zero.max():.2f}m, mean={new_non_zero.mean():.2f}m")
        
        add_voxel_blocks(heightmap_meters, 'rgb(50, 150, 200)', 'Entwurf', 
                        opacity=1.0, show_in_legend=True)
    
    # Determine scene bounds - use expanded if available
    if expanded_bounds_native is not None:
        scene_min_x, scene_min_y, scene_max_x, scene_max_y = expanded_bounds_native
    else:
        scene_min_x, scene_min_y, scene_max_x, scene_max_y = min_x, min_y, max_x, max_y
    
    # Add simple ground plane
    x_ground = [scene_min_x, scene_max_x, scene_max_x, scene_min_x]
    y_ground = [scene_min_y, scene_min_y, scene_max_y, scene_max_y]
    z_ground = [-1.0, -1.0, -1.0, -1.0]
    
    fig.add_trace(go.Mesh3d(
        x=x_ground,
        y=y_ground,
        z=z_ground,
        i=[0, 0],
        j=[1, 2],
        k=[2, 3],
        color='rgba(200, 220, 200, 0.5)',
        opacity=0.5,
        name='Ground',
        hoverinfo='skip',
        showlegend=False
    ))
    
    # Calculate scene bounds in geographic coordinates
    x_range = [scene_min_x, scene_max_x]
    y_range = [scene_min_y, scene_max_y]
    
    # Calculate max height from both new and existing buildings
    max_z = heightmap_meters.max() if heightmap_meters.max() > 0 else 30
    if env_3d_fixed is not None and env_3d_fixed.size > 0:
        existing_max = np.sum(env_3d_fixed > 0, axis=2).max() * height_exaggeration
        max_z = max(max_z, existing_max)
    z_range = [0, max(max_z * 1.2, 30)]  # At least 30m for empty scenes
    
    # Calculate center and extent for camera positioning
    center_x = (scene_min_x + scene_max_x) / 2
    center_y = (scene_min_y + scene_max_y) / 2
    center_z = 0  # Center vertically on the buildings
    extent_x = scene_max_x - scene_min_x
    extent_y = scene_max_y - scene_min_y
    
    # Set camera with rotation center at mesh center
    if camera_state:
        # Use provided camera state for syncing
        camera = camera_state
    else:
        # Aerial oblique view - positioned to view geographic extent
        # Camera eye in relative coordinates (will be scaled by scene)
        camera = dict(
            eye=dict(x=1.5, y=1.5, z=1.2),
            center=dict(x=0, y=0, z=0),  # Center on mesh center in normalized coords
            up=dict(x=0, y=0, z=1)
        )
    
    # Update layout with geographic coordinate system - SQUARE viewport
    fig.update_layout(
        scene=dict(
            xaxis=dict(title='Ost (m)', range=x_range, showgrid=True),
            yaxis=dict(title='Nord (m)', range=y_range, showgrid=True),
            zaxis=dict(title='Höhe (m)', range=z_range, showgrid=True),
            camera=camera,
            aspectmode='data',  # Force equal aspect ratio on all axes (1m = 1m in all directions)
            # Add sun-like lighting effect with sky blue background
            bgcolor='rgb(230, 240, 255)',  # Light sky blue background
        ),
        height=700,  # Square viewport
        width=700,  # Square viewport
        margin=dict(l=0, r=0, t=30, b=100),  # More bottom margin for legend
        hovermode='closest',
        # Legend at bottom center, horizontal orientation
        legend=dict(
            orientation='h',
            yanchor='top',
            y=-0.12,
            xanchor='center',
            x=0.5
        )
    )
    
    return fig

def layout(lang='DE'):
    from backend.translation import create_breadcrumb
    return dbc.Container([
    dcc.Location(id='url-s6', refresh=False),
    create_breadcrumb(6, lang),
    html.H2(T[lang]['STEP6_TITLE']),
        dbc.Row([
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
    Input('clustering-data-store', 'data'),  # Get ACTUAL cluster data from Step 5
    State('language-store', 'data'),
    State('camera-sync-store', 'data')
)
def display_comparison(selected_ids, results_data, solution_modes, clustering_data, lang, camera_state):
    if lang is None: lang = 'DE'  # Default to German
    
    if not selected_ids:
        return dbc.Alert(T[lang]['STEP6_NO_SELECTION'], color="info")

    if not results_data:
        return dbc.Alert(T[lang]['STEP6_NO_RESULTS'], color="danger")
    
    grid_geojson = results_data.get('grid_geojson')
    if not grid_geojson:
        return dbc.Alert(T[lang]['STEP6_FILE_NOT_FOUND'], color="danger")
    
    # Use the ACTUAL cluster data from Step 5 (no re-clustering!)
    # This ensures consistency - we use the exact same clusters that were displayed in Step 5
    # The clusters already contain the filtered solutions, no need to reload the full pickle!
    if not clustering_data or 'clusters' not in clustering_data:
        return dbc.Alert(T[lang]['STEP6_NO_SELECTION'], color="warning")
    
    clusters = clustering_data['clusters']
    
    # Map selected IDs to their clusters
    solutions_to_compare = []
    solution_modes = solution_modes or {}  # Initialize if None
    
    for idx, cluster_id in enumerate(selected_ids):
        # Find the cluster with this cluster_id (selected_ids now contain cluster_id, not solution ID)
        matching_cluster = None
        for cluster in clusters:
            if cluster['cluster_id'] == cluster_id:
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
    pixel_size = DOMAIN_CONFIG.get('pixel_size_in_meters', 1.0)  # Default 1m per pixel
    
    # Get geographic bounds and existing buildings data
    grid_bounds_native = results_data.get('grid_bounds_native')
    expanded_bounds_native = results_data.get('expanded_bounds_native')  # May be None for old data
    design_offset = results_data.get('design_offset')  # May be None for old data
    
    # Load existing buildings from separate pickle file
    env_3d_fixed = None
    building_function_map = None
    function_lookup = {}
    env_3d_path = results_data.get('env_3d_path')
    if env_3d_path and os.path.exists(env_3d_path):
        try:
            with open(env_3d_path, 'rb') as f:
                env_data = pickle.load(f)
                # Handle both old format (just array) and new format (dict)
                if isinstance(env_data, dict):
                    env_3d_fixed = env_data.get('env_3d_expanded')
                    building_function_map = env_data.get('building_function_map')
                    function_lookup = env_data.get('function_lookup', {})
                else:
                    # Old format compatibility
                    env_3d_fixed = env_data
        except Exception as e:
            print(f"Warning: Could not load existing buildings data: {e}")
            env_3d_fixed = None
    
    # Get feature translation setup
    from backend.translation import translate_feature_labels
    from backend.units import format_value_with_unit
    feature_indices = results_data.get('selected_features_indices', [])
    feature_set = results_data.get('feature_set', 'original')
    labels = translate_feature_labels(feature_indices, lang, feature_set)
    
    cols = []
    for sol_data in solutions_to_compare:
        cluster = sol_data['cluster']
        display_mode = sol_data.get('display_mode', 'best')
        i = sol_data['index']
        
        # Get the solution to display (central or best)
        sol = cluster['central_solution'] if display_mode == 'central' else cluster['best_solution']
        
        # Create heightmap
        heightmap = np.array(sol['heightmap']).reshape(heightmap_res, heightmap_res)
        
        # DEBUG: Check actual heightmap values
        non_zero_heights = heightmap[heightmap > 0]
        if len(non_zero_heights) > 0:
            print(f"  Heightmap stats: min={non_zero_heights.min():.2f}m, "
                  f"max={non_zero_heights.max():.2f}m, "
                  f"mean={non_zero_heights.mean():.2f}m, "
                  f"pixels={len(non_zero_heights)}")
        
        # Create 3D visualization with geographic context
        fig_3d = create_3d_building_plot(
            heightmap, 
            grid_bounds_native if grid_bounds_native else (0, 0, heightmap_res * pixel_size, heightmap_res * pixel_size),
            env_3d_fixed=env_3d_fixed,
            height_exaggeration=1.0,
            camera_state=camera_state,
            pixel_size_m=pixel_size,
            expanded_bounds_native=expanded_bounds_native,
            design_offset=design_offset,
            building_function_map=building_function_map,
            function_lookup=function_lookup
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
                config={'displayModeBar': True, 'displaylogo': False}
            ),
            html.H6(T[lang]['STEP6_METRICS_HEADER'], className="mt-3"),
            html.Div(table, style={'maxHeight': '200px', 'overflowY': 'auto'})
        ], md=12, lg=6, xl=6, className="mb-4")  # 2 designs per row on large screens, 1 on medium
        cols.append(col)
    
    print(f"[STEP 6 DEBUG] Created {len(cols)} comparison columns")
    print("="*80 + "\n")
    
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
    State('clustering-data-store', 'data'),
    prevent_initial_call=True,
)
def export_pdf_report_s6(n_clicks, selected_ids, results_data, clustering_data):
    if not n_clicks or not selected_ids or not results_data:
        return None

    # For PDF export, we need to load ALL elites for correlation analysis
    # This is the one place where we legitimately need the full dataset
    results_path = results_data.get('full_results_path')
    if not os.path.exists(results_path):
        return dict(content="Error: Results file not found.", filename="error.txt")

    with open(results_path, 'rb') as f:
        list_of_elites = pickle.load(f)
    
    # Get the solutions to compare from clustering data (filtered)
    if not clustering_data or 'clusters' not in clustering_data:
        return dict(content="Error: No clustering data available.", filename="error.txt")
    
    clusters = clustering_data['clusters']
    solutions_to_compare = []
    
    # Extract solutions from selected clusters
    for cluster_id in selected_ids:
        matching_cluster = None
        for cluster in clusters:
            if cluster['cluster_id'] == cluster_id:
                matching_cluster = cluster
                break
        
        if matching_cluster:
            # Add both best and central solutions for comprehensive report
            solutions_to_compare.append(matching_cluster['best_solution'])
            if matching_cluster['central_solution']['id'] != matching_cluster['best_solution']['id']:
                solutions_to_compare.append(matching_cluster['central_solution'])
    
    if not solutions_to_compare:
        return dict(content="Error: Selected solutions not found in clustering data.", filename="error.txt")

    # Translate feature labels (use German for PDF report - could be made configurable)
    from backend.translation import translate_feature_labels
    feature_indices = results_data.get('selected_features_indices', [])
    feature_set = results_data.get('feature_set', 'original')
    labels = translate_feature_labels(feature_indices, 'DE', feature_set)  # PDF in German

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