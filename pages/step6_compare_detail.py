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
                            building_function_map=None, function_lookup=None, flow_field=None):
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
        
        # Wireframe coordinates (all edges combined into one trace)
        wireframe_x = []
        wireframe_y = []
        wireframe_z = []
        
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
                
                # Add wireframe edges for this building block (12 edges of the box)
                # Combine all edges into single lists with None separators
                wireframe_edges = [
                    # Bottom rectangle
                    [0, 1], [1, 2], [2, 3], [3, 0],
                    # Top rectangle
                    [4, 5], [5, 6], [6, 7], [7, 4],
                    # Vertical edges
                    [0, 4], [1, 5], [2, 6], [3, 7]
                ]
                
                for edge in wireframe_edges:
                    v0 = vertices[edge[0]]
                    v1 = vertices[edge[1]]
                    
                    # Add edge to combined wireframe (with None separator)
                    wireframe_x.extend([v0[0], v1[0], None])
                    wireframe_y.extend([v0[1], v1[1], None])
                    wireframe_z.extend([v0[2], v1[2], None])
                
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
                flatshading=True,  # Use flat shading to avoid interpolation artifacts
                lighting=dict(
                    ambient=0.9,      # Very high ambient = minimal shadows
                    diffuse=0.5,      # Reduced diffuse to minimize directional effects
                    specular=0.0,     # No specular highlights
                    roughness=1.0,    # Maximum roughness (completely matte)
                    fresnel=0.0       # No fresnel effect
                ),
                lightposition=dict(x=0, y=0, z=1e5)  # Light directly from above (like sun at noon)
            ))
            
            # Add ALL wireframe edges as a SINGLE trace (much faster!)
            if len(wireframe_x) > 0:
                fig.add_trace(go.Scatter3d(
                    x=wireframe_x,
                    y=wireframe_y,
                    z=wireframe_z,
                    mode='lines',
                    line=dict(color='black', width=4),
                    showlegend=False,
                    hoverinfo='skip'
                ))
    
    # Add existing buildings first (in gray, fully opaque)
    if env_3d_fixed is not None and env_3d_fixed.size > 0:
        # Convert env_3d_fixed to heightmap (max height in each column)
        # env_3d_fixed z-axis is already in meters (1 voxel = 1 meter)
        # No multiplication needed - heights are already correct
        existing_heightmap = np.sum(env_3d_fixed > 0, axis=2) * height_exaggeration
        
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
                        func_color = func_colors[idx] if idx < len(func_colors) else 'rgb(160, 160, 160)'
                        add_voxel_blocks(func_heightmap, func_color, f'Bestand: {func_name}', 
                                       opacity=1.0, show_in_legend=True, x_coords=x_coords_exp, y_coords=y_coords_exp)
            else:
                # No function data, show all as concrete gray
                add_voxel_blocks(existing_heightmap, 'rgb(160, 160, 160)', 'Bestand', 
                               opacity=1.0, show_in_legend=True, x_coords=x_coords_exp, y_coords=y_coords_exp)
    
    # Add new design buildings (modern blue)
    if heightmap_meters.max() > 0:        
        add_voxel_blocks(heightmap_meters, 'rgb(70, 140, 200)', 'Entwurf', 
                        opacity=1.0, show_in_legend=True)
    
    # Determine scene bounds - use expanded if available
    if expanded_bounds_native is not None:
        scene_min_x, scene_min_y, scene_max_x, scene_max_y = expanded_bounds_native
    else:
        scene_min_x, scene_min_y, scene_max_x, scene_max_y = min_x, min_y, max_x, max_y
    
    # Add simple shadow projections on ground (light from above-south-east)
    # OPTIMIZED: Combine ALL shadows into ONE mesh trace
    shadow_offset_x = 3  # meters shadow offset in x
    shadow_offset_y = 3  # meters shadow offset in y
    
    shadow_x = []
    shadow_y = []
    shadow_z = []
    shadow_i = []
    shadow_j = []
    shadow_k = []
    shadow_vertex_count = 0
    
    # Shadow for new design buildings
    if heightmap_meters.max() > 0:
        shadow_mask = heightmap_meters > 1.5  # Only cast shadows for buildings > 1.5m
        if shadow_mask.any():
            for row in range(heightmap_meters.shape[0]):
                for col in range(heightmap_meters.shape[1]):
                    if shadow_mask[row, col]:
                        # Get building footprint coordinates
                        x0 = x_coords_geo[col] + shadow_offset_x
                        x1 = x_coords_geo[col + 1] + shadow_offset_x
                        y0 = y_coords_geo[row] + shadow_offset_y
                        y1 = y_coords_geo[row + 1] + shadow_offset_y
                        
                        # Add vertices for this shadow quad
                        shadow_x.extend([x0, x1, x1, x0])
                        shadow_y.extend([y0, y0, y1, y1])
                        shadow_z.extend([0.1, 0.1, 0.1, 0.1])
                        
                        # Add faces (2 triangles per quad)
                        shadow_i.extend([shadow_vertex_count, shadow_vertex_count])
                        shadow_j.extend([shadow_vertex_count + 1, shadow_vertex_count + 2])
                        shadow_k.extend([shadow_vertex_count + 2, shadow_vertex_count + 3])
                        shadow_vertex_count += 4
    
    # Shadow for existing buildings
    if env_3d_fixed is not None and env_3d_fixed.size > 0:
        existing_heightmap = np.sum(env_3d_fixed > 0, axis=2) * height_exaggeration
        shadow_mask_existing = existing_heightmap > 1.5
        
        if shadow_mask_existing.any():
            # Get coordinates for existing buildings
            if expanded_bounds_native is not None:
                exp_min_x, exp_min_y, exp_max_x, exp_max_y = expanded_bounds_native
                exp_rows, exp_cols = existing_heightmap.shape
                x_coords_exp = np.linspace(exp_min_x, exp_max_x, exp_cols + 1)
                y_coords_exp = np.linspace(exp_min_y, exp_max_y, exp_rows + 1)
            else:
                x_coords_exp = x_coords_geo
                y_coords_exp = y_coords_geo
            
            for row in range(existing_heightmap.shape[0]):
                for col in range(existing_heightmap.shape[1]):
                    if shadow_mask_existing[row, col]:
                        x0 = x_coords_exp[col] + shadow_offset_x
                        x1 = x_coords_exp[col + 1] + shadow_offset_x
                        y0 = y_coords_exp[row] + shadow_offset_y
                        y1 = y_coords_exp[row + 1] + shadow_offset_y
                        
                        # Add vertices for this shadow quad
                        shadow_x.extend([x0, x1, x1, x0])
                        shadow_y.extend([y0, y0, y1, y1])
                        shadow_z.extend([0.1, 0.1, 0.1, 0.1])
                        
                        # Add faces
                        shadow_i.extend([shadow_vertex_count, shadow_vertex_count])
                        shadow_j.extend([shadow_vertex_count + 1, shadow_vertex_count + 2])
                        shadow_k.extend([shadow_vertex_count + 2, shadow_vertex_count + 3])
                        shadow_vertex_count += 4
    
    # Add single combined shadow mesh
    if shadow_vertex_count > 0:
        fig.add_trace(go.Mesh3d(
            x=shadow_x,
            y=shadow_y,
            z=shadow_z,
            i=shadow_i,
            j=shadow_j,
            k=shadow_k,
            color='rgb(0, 0, 0)',
            opacity=0.15,
            showlegend=False,
            hoverinfo='skip',
            lighting=dict(ambient=1.0, diffuse=0.0, specular=0.0)
        ))
    
    # Add improved ground plane at z=0
    # Make it slightly larger than the scene for better visual context
    margin = max(scene_max_x - scene_min_x, scene_max_y - scene_min_y) * 0.1
    ground_min_x = scene_min_x - margin
    ground_max_x = scene_max_x + margin
    ground_min_y = scene_min_y - margin
    ground_max_y = scene_max_y + margin
    
    # Create simple ground plane at z=0
    fig.add_trace(go.Mesh3d(
        x=[ground_min_x, ground_max_x, ground_max_x, ground_min_x],
        y=[ground_min_y, ground_min_y, ground_max_y, ground_max_y],
        z=[0, 0, 0, 0],
        i=[0, 0],
        j=[1, 2],
        k=[2, 3],
        color='rgb(180, 200, 180)',  # Light green
        opacity=0.6,
        name='Boden',
        hoverinfo='skip',
        showlegend=False,
        lighting=dict(
            ambient=0.9,
            diffuse=0.3,
            specular=0.0,
            roughness=1.0
        )
    ))
    
    # Add grid lines on ground plane for scale reference
    # OPTIMIZED: Combine all grid lines into ONE trace with None separators
    grid_spacing = max(50, int((ground_max_y - ground_min_y) / 10) // 10 * 10)  # Round to nearest 10m, min 50m
    
    grid_x = []
    grid_y = []
    grid_z = []
    
    # Horizontal grid lines (along x-axis)
    y_lines = np.arange(ground_min_y, ground_max_y + grid_spacing, grid_spacing)
    for y_line in y_lines:
        grid_x.extend([ground_min_x, ground_max_x, None])
        grid_y.extend([y_line, y_line, None])
        grid_z.extend([0, 0, None])
    
    # Vertical grid lines (along y-axis)
    x_lines = np.arange(ground_min_x, ground_max_x + grid_spacing, grid_spacing)
    for x_line in x_lines:
        grid_x.extend([x_line, x_line, None])
        grid_y.extend([ground_min_y, ground_max_y, None])
        grid_z.extend([0, 0, None])
    
    # Add single trace with all grid lines
    if len(grid_x) > 0:
        fig.add_trace(go.Scatter3d(
            x=grid_x,
            y=grid_y,
            z=grid_z,
            mode='lines',
            line=dict(color='rgba(120, 120, 120, 0.3)', width=1),
            showlegend=False,
            hoverinfo='skip'
        ))
    
    # Add 3D compass arrow on ground plane (pointing NORTH)
    # Position to the north of the scene
    compass_length = max(scene_max_x - scene_min_x, scene_max_y - scene_min_y) * 0.15  # 15% of scene size
    compass_x = (scene_min_x + scene_max_x) / 2  # Center horizontally
    compass_y_start = scene_max_y + (scene_max_y - scene_min_y) * 0.05  # Just north of scene
    compass_y_end = compass_y_start + compass_length
    
    # Arrow shaft (thick red line pointing north)
    fig.add_trace(go.Scatter3d(
        x=[compass_x, compass_x],
        y=[compass_y_start, compass_y_end],
        z=[0.2, 0.2],  # Slightly above ground
        mode='lines',
        line=dict(color='red', width=8),
        showlegend=False,
        hoverinfo='skip',
        name='North'
    ))
    
    # Arrow head (cone pointing north)
    arrow_width = compass_length * 0.3
    arrowhead_x = [
        compass_x - arrow_width/2, 
        compass_x + arrow_width/2, 
        compass_x
    ]
    arrowhead_y = [
        compass_y_end - arrow_width * 0.8, 
        compass_y_end - arrow_width * 0.8, 
        compass_y_end
    ]
    arrowhead_z = [0.2, 0.2, 0.2]
    
    fig.add_trace(go.Mesh3d(
        x=arrowhead_x,
        y=arrowhead_y,
        z=arrowhead_z,
        i=[0],
        j=[1],
        k=[2],
        color='red',
        opacity=1.0,
        showlegend=False,
        hoverinfo='skip',
        lighting=dict(ambient=1.0, diffuse=0.0, specular=0.0)
    ))
    
    # Add "N" text label using annotation (in 3D scene coordinates)
    fig.add_trace(go.Scatter3d(
        x=[compass_x],
        y=[compass_y_end + arrow_width * 0.5],
        z=[0.2],
        mode='text',
        text=['<b>N</b>'],
        textfont=dict(size=20, color='red', family='Arial Black'),
        showlegend=False,
        hoverinfo='skip'
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
            xaxis=dict(
                title='Ost (m)', 
                range=x_range, 
                showgrid=True,
                gridcolor='rgba(200, 200, 200, 0.3)',
                gridwidth=1,
                showbackground=True,
                backgroundcolor='rgb(240, 245, 250)'
            ),
            yaxis=dict(
                title='Nord (m)', 
                range=y_range, 
                showgrid=True,
                gridcolor='rgba(200, 200, 200, 0.3)',
                gridwidth=1,
                showbackground=True,
                backgroundcolor='rgb(240, 245, 250)'
            ),
            zaxis=dict(
                title='Höhe (m)', 
                range=z_range, 
                showgrid=True,
                gridcolor='rgba(200, 200, 200, 0.3)',
                gridwidth=1,
                showbackground=True,
                backgroundcolor='rgb(245, 250, 255)'
            ),
            camera=camera,
            aspectmode='data',  # Force equal aspect ratio on all axes (1m = 1m in all directions)
            bgcolor='rgb(235, 245, 255)',  # Soft sky blue background
        ),
        height=700,  # Square viewport
        width=700,  # Square viewport
        margin=dict(l=0, r=0, t=50, b=0),  # Top margin for legend, no bottom margin
        hovermode='closest',
        paper_bgcolor='white',
        plot_bgcolor='white',
        # Legend at top center, horizontal orientation
        legend=dict(
            orientation='h',
            yanchor='bottom',
            y=1.0,
            xanchor='center',
            x=0.5,
            bgcolor='rgba(255, 255, 255, 0.9)',
            bordercolor='rgba(0, 0, 0, 0.1)',
            borderwidth=1
        ),
        annotations=[
            # Scale bar (keep only the scale bar, compass is now 3D on ground plane)
            dict(
                text=f'<b>━━━━</b> {grid_spacing}m',
                x=0.02,
                y=0.05,
                xref='paper',
                yref='paper',
                showarrow=False,
                font=dict(size=12, color='black'),
                bgcolor='rgba(255, 255, 255, 0.8)',
                bordercolor='black',
                borderwidth=1,
                borderpad=4
            )
        ]
    )
    
    # Add flow field visualization if provided
    if flow_field is not None:
        try:
            # Flow field shape: (2, H, W) for (u, v) components
            # Expected: (2, 66, 94) from full U-Net output at 3m resolution
            u = flow_field[0]  # X-component (m/s)
            v = flow_field[1]  # Y-component (m/s)
            
            # Compute velocity magnitude for ground surface coloring
            velocity_magnitude = np.sqrt(u**2 + v**2)
            
            # Create ground-level velocity surface
            # Flow field is 66x94 at 3m resolution = 198m x 282m domain
            rows, cols = u.shape  # Should be 66, 94
            flow_width_m = cols * 3.0  # 94 * 3 = 282m
            flow_height_m = rows * 3.0  # 66 * 3 = 198m
            
            # Center the flow field over the building domain
            # Buildings span from min_x to max_x (parcel extent)
            parcel_center_x = (min_x + max_x) / 2
            parcel_center_y = (min_y + max_y) / 2
            
            flow_min_x = parcel_center_x - flow_width_m / 2
            flow_max_x = parcel_center_x + flow_width_m / 2
            flow_min_y = parcel_center_y - flow_height_m / 2
            flow_max_y = parcel_center_y + flow_height_m / 2
            
            x_flow = np.linspace(flow_min_x, flow_max_x, cols)
            y_flow = np.linspace(flow_min_y, flow_max_y, rows)
            X_flow, Y_flow = np.meshgrid(x_flow, y_flow)
            
            # Create velocity surface slightly above ground (z=0.1m)
            Z_flow = np.full_like(velocity_magnitude, 0.1)
            
            fig.add_trace(go.Surface(
                x=X_flow,
                y=Y_flow,
                z=Z_flow,
                surfacecolor=velocity_magnitude,
                colorscale='Viridis',
                opacity=0.7,
                name='Wind Speed (m/s)',
                colorbar=dict(
                    title=dict(
                        text="Wind Speed (m/s)",
                        side="right"
                    ),
                    x=1.15,  # Move further right to prevent cutoff
                    len=0.7,
                    thickness=20,  # Make colorbar wider
                    xpad=10  # Add padding
                ),
                hovertemplate='<b>Wind Speed</b><br>' +
                            'X: %{x:.1f}m<br>' +
                            'Y: %{y:.1f}m<br>' +
                            'Speed: %{surfacecolor:.2f} m/s<extra></extra>',
                showlegend=True
            ))
            
            # Create 3D streamlines
            # Sample starting points from left edge of domain
            step = max(1, rows // 8)  # ~8 streamlines
            y_starts = np.arange(step//2, rows, step)
            x_start = 2  # Start from left edge
            
            # Function to integrate streamline in 3D
            def integrate_streamline_3d(x0_idx, y0_idx, max_steps=100):
                from scipy.interpolate import RegularGridInterpolator
                
                # Create interpolators for u and v
                y_coords_interp = np.arange(rows)
                x_coords_interp = np.arange(cols)
                u_interp = RegularGridInterpolator(
                    (y_coords_interp, x_coords_interp), u, 
                    bounds_error=False, fill_value=0
                )
                v_interp = RegularGridInterpolator(
                    (y_coords_interp, x_coords_interp), v,
                    bounds_error=False, fill_value=0
                )
                
                points = []
                x_idx, y_idx = x0_idx, y0_idx
                dt = 0.3  # Step size in grid units
                
                for _ in range(max_steps):
                    # Get velocity at current position
                    u_val = u_interp([y_idx, x_idx])[0]
                    v_val = v_interp([y_idx, x_idx])[0]
                    
                    # Convert to geographic coordinates and add height variation
                    x_geo = min_x + (x_idx / cols) * (max_x - min_x)
                    y_geo = min_y + (y_idx / rows) * (max_y - min_y)
                    
                    # Add height based on velocity magnitude for visual effect
                    speed = np.sqrt(u_val**2 + v_val**2)
                    z_height = 2 + speed * 3  # 2-15m height based on speed
                    
                    points.append([x_geo, y_geo, z_height])
                    
                    # Update position using RK2
                    x_mid = x_idx + 0.5 * dt * u_val
                    y_mid = y_idx + 0.5 * dt * v_val
                    
                    u_mid = u_interp([y_mid, x_mid])[0]
                    v_mid = v_interp([y_mid, x_mid])[0]
                    
                    x_new = x_idx + dt * u_mid
                    y_new = y_idx + dt * v_mid
                    
                    # Check bounds and stop conditions
                    if (x_new < 0 or x_new >= cols or y_new < 0 or y_new >= rows or
                        speed < 0.1):  # Stop if velocity too small
                        break
                    
                    # Check if hit a building
                    ix, iy = int(np.round(x_new)), int(np.round(y_new))
                    if (0 <= ix < cols and 0 <= iy < rows and 
                        ix < heightmap.shape[1] and iy < heightmap.shape[0] and
                        heightmap[iy, ix] > 2):  # Stop if hit building
                        break
                    
                    x_idx, y_idx = x_new, y_new
                
                return np.array(points)
            
            # Generate streamlines
            colors = ['red', 'orange', 'yellow', 'green', 'blue', 'purple', 'pink', 'cyan']
            
            for idx, y_start in enumerate(y_starts):
                try:
                    points = integrate_streamline_3d(x_start, y_start)
                    if len(points) > 1:
                        color = colors[idx % len(colors)]
                        
                        fig.add_trace(go.Scatter3d(
                            x=points[:, 0],
                            y=points[:, 1],
                            z=points[:, 2],
                            mode='lines+markers',
                            line=dict(color=color, width=4),
                            marker=dict(size=2, color=color),
                            name=f'Streamline {idx+1}',
                            showlegend=(idx < 3),  # Only show first few in legend
                            hovertemplate='<b>Streamline</b><br>' +
                                        'X: %{x:.1f}m<br>' +
                                        'Y: %{y:.1f}m<br>' +
                                        'Height: %{z:.1f}m<extra></extra>'
                        ))
                except Exception as e:
                    print(f"Error creating streamline {idx}: {e}")
                    
        except Exception as e:
            print(f"Error adding flow visualization: {e}")
    
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
        
        # Global flow visualization toggle (only visible if U-Net model available)
        html.Div([
            dbc.Row([
                dbc.Col([
                    html.Div([
                        html.H6(T[lang].get('STEP6_FLOW_FIELD_HEADER', 'Luftströmungsfeld'), className="d-inline-block mb-0 me-3"),
                        dbc.Checklist(
                            options=[{"label": T[lang].get('STEP6_SHOW_ALL_FLOW', 'Zeige alle Strömungen'), "value": 1}],
                            value=[],
                            id='global-flow-toggle',
                            switch=True,
                            className="d-inline-block"
                        ),
                    ], className="d-flex align-items-center")
                ])
            ], className="mb-3 p-2 bg-light rounded")
        ], id='global-flow-container', style={'display': 'none'}),
        
        # Store for syncing camera state
        dcc.Store(id='camera-sync-store', data={}),
        # Store for solution display mode (central vs best) per cluster
        dcc.Store(id='solution-mode-store', data={}),
        # Store for flow visualization toggle states
        dcc.Store(id='flow-toggle-store', data={}),
        
        dcc.Loading(html.Div(id='comparison-content'))
    ], fluid=True)


def create_diversity_grid(cluster, heightmap_res, cluster_index):
    """Create a 3x3 grid of random solution previews from the cluster"""
    cluster_solutions = cluster.get('all_solutions', [])
    
    if len(cluster_solutions) < 9:
        # If less than 9 solutions, take what we have
        num_samples = min(len(cluster_solutions), 9)
        sampled_solutions = cluster_solutions[:num_samples]
    else:
        # Random sample of 9 solutions
        np.random.seed(cluster_index)  # Consistent randomization per cluster
        sample_indices = np.random.choice(len(cluster_solutions), size=9, replace=False)
        sampled_solutions = [cluster_solutions[idx] for idx in sample_indices]
    
    # Create 3x3 grid
    preview_cards = []
    for idx, sol in enumerate(sampled_solutions):
        heightmap = np.array(sol['heightmap']).reshape(heightmap_res, heightmap_res)
        
        # Create cleaner 3D preview using block-based mesh (same style as main visualization)
        fig = go.Figure()
        
        # Build mesh for buildings as blocks
        x_coords_list = []
        y_coords_list = []
        z_coords_list = []
        i_indices = []
        j_indices = []
        k_indices = []
        vertex_count = 0
        
        for row in range(heightmap.shape[0]):
            for col in range(heightmap.shape[1]):
                height = heightmap[row, col]
                if height <= 1.5:  # Skip cells < half floor
                    continue
                
                # Create box vertices
                x0, x1 = col, col + 1
                y0, y1 = row, row + 1
                z0, z1 = 0, height
                
                vertices = [
                    [x0, y0, z0], [x1, y0, z0], [x1, y1, z0], [x0, y1, z0],
                    [x0, y0, z1], [x1, y0, z1], [x1, y1, z1], [x0, y1, z1]
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
            fig.add_trace(go.Mesh3d(
                x=x_coords_list,
                y=y_coords_list,
                z=z_coords_list,
                i=i_indices,
                j=j_indices,
                k=k_indices,
                color='rgb(100, 149, 237)',  # Cornflower blue
                opacity=1.0,
                flatshading=True,
                lighting=dict(ambient=0.8, diffuse=0.5, specular=0.0, roughness=1.0),
                hoverinfo='skip'
            ))
        
        # Add ground plane
        ground_size = heightmap_res
        fig.add_trace(go.Mesh3d(
            x=[0, ground_size, ground_size, 0],
            y=[0, 0, ground_size, ground_size],
            z=[0, 0, 0, 0],
            i=[0, 0], j=[1, 2], k=[2, 3],
            color='rgb(180, 200, 180)',
            opacity=0.6,
            hoverinfo='skip'
        ))
        
        fig.update_layout(
            scene=dict(
                xaxis=dict(visible=False),
                yaxis=dict(visible=False),
                zaxis=dict(visible=False),
                camera=dict(eye=dict(x=1.5, y=1.5, z=1.2)),
                aspectmode='data'
            ),
            margin=dict(l=0, r=0, t=0, b=0),
            height=120,
            width=120,
            showlegend=False,
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)'
        )
        
        card = dbc.Col([
            dcc.Graph(figure=fig, config={'displayModeBar': False}, 
                     style={'height': '120px', 'width': '120px'})
        ], width=4, className="p-1")
        
        preview_cards.append(card)
    
    # Organize into rows of 3
    rows = []
    for i in range(0, len(preview_cards), 3):
        row_cards = preview_cards[i:i+3]
        rows.append(dbc.Row(row_cards, className="g-1 justify-content-center"))
    
    return html.Div(rows)


@callback(
    Output('comparison-content', 'children'),
    Input('comparison-store', 'data'),
    Input('results-store', 'data'),
    Input('solution-mode-store', 'data'),
    Input('flow-toggle-store', 'data'),
    Input('clustering-data-store', 'data'),  # Get ACTUAL cluster data from Step 5
    State('language-store', 'data'),
    State('camera-sync-store', 'data')
)
def display_comparison(selected_ids, results_data, solution_modes, flow_toggle_states, clustering_data, lang, camera_state):
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
            # Get the display mode for this cluster (default to 'central' = most representative)
            display_mode = solution_modes.get(str(idx), 'central')
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
    feature_set = results_data.get('feature_set', 'consolidated')
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
        
        # Check if flow visualization should be included
        flow_field = None
        show_flow = flow_toggle_states.get(str(i), False) if flow_toggle_states else False
        print(f"DEBUG: Cluster {i}, show_flow = {show_flow}, flow_toggle_states = {flow_toggle_states}")
        
        if show_flow and check_unet_model_availability():
            print(f"DEBUG: Generating flow field for cluster {i}")
            print(f"DEBUG: Solution keys: {list(sol.keys())}")
            try:
                # Generate flow field using U-Net model (regardless of optimization method used)
                import torch
                from backend.model_evaluator import create_evaluator
                from backend.fast_encoding import NumbaFastEncoding
                
                # Get solution genome - handle different possible key names
                genome = None
                if 'genome' in sol:
                    genome = np.array(sol['genome'])
                elif 'x' in sol:  # Some solutions might store genome as 'x'
                    genome = np.array(sol['x'])
                elif 'solution' in sol:
                    genome = np.array(sol['solution'])
                else:
                    # Try to reconstruct genome from heightmap if available
                    print(f"DEBUG: No genome found, available keys: {list(sol.keys())}")
                    print(f"DEBUG: Attempting to use heightmap to generate dummy genome")
                    # For now, skip flow generation if no genome available
                    raise KeyError("No genome data available in solution")
                
                # Ensure genome is numpy array
                genome = np.array(genome) if not isinstance(genome, np.ndarray) else genome
                print(f"DEBUG: Using genome shape: {genome.shape}")
                
                # Create U-Net evaluator
                device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
                print(f"DEBUG: Using device: {device}")
                unet_eval = create_evaluator('unet', parcel_size=81, device=device)
                
                # Generate heightmap using same encoding as in diagnostics
                encoding = NumbaFastEncoding(parcel_size=81)  # 27x27 grid for 81m parcel
                heightmap_27x27 = encoding.express_batch(genome.reshape(1, -1))[0]
                
                # Construct proper 3-channel domain grids for U-Net (terrain, buildings, landuse)
                from backend.model_evaluator import construct_domain_grids_batch
                terrain, buildings, landuse = construct_domain_grids_batch(
                    heightmap_27x27[np.newaxis, :, :],  # Add batch dimension
                    parcel_size_cells=27  # 81m / 3m = 27 cells
                )
                
                # Normalize inputs using the evaluator's normalization stats
                terrain_norm = (terrain - unet_eval.terrain_mean) / unet_eval.terrain_std
                buildings_norm = (buildings - unet_eval.buildings_mean) / unet_eval.buildings_std
                landuse_norm = (landuse - unet_eval.landuse_mean) / unet_eval.landuse_std
                
                # Stack into 3-channel input: (1, 3, 66, 94)
                X = np.stack([terrain_norm[0], buildings_norm[0], landuse_norm[0]], axis=0)
                
                # Prepare input tensor (convert to half precision on CUDA to match model)
                dtype = torch.float16 if device.type == 'cuda' else torch.float32
                X_torch = torch.tensor(X, dtype=dtype, device=device).unsqueeze(0)  # Shape: (1, 3, 66, 94)
                
                # Get U-Net predictions
                with torch.no_grad():
                    Y_pred = unet_eval.model(X_torch)  # Shape: (1, 6, 66, 94)
                    
                    # Extract velocity components (channels 2 and 3: uq, vq) - FULL DOMAIN
                    uq_full = Y_pred[0, 2, :, :] * unet_eval.uq_std + unet_eval.uq_mean  # cm/s
                    vq_full = Y_pred[0, 3, :, :] * unet_eval.vq_std + unet_eval.vq_mean  # cm/s
                    
                    # Convert to numpy and from cm/s to m/s
                    uq_np = uq_full.cpu().numpy() / 100.0  # Convert cm/s to m/s
                    vq_np = vq_full.cpu().numpy() / 100.0
                    
                    # Use ENTIRE flow field (66x94) instead of ROI extraction
                    # Create flow field in expected format: (2, H, W) for (u, v)
                    flow_field = np.stack([uq_np, vq_np], axis=0)  # Shape: (2, 66, 94)
                    print(f"DEBUG: Generated full flow field shape: {flow_field.shape}")
                    
            except Exception as e:
                print(f"Warning: Could not generate flow field with U-Net: {e}")
                import traceback
                print(traceback.format_exc())
                flow_field = None
        else:
            if not show_flow:
                print(f"DEBUG: Flow not requested for cluster {i}")
            elif not check_unet_model_availability():
                print(f"DEBUG: U-Net model not available for cluster {i}")
        
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
            function_lookup=function_lookup,
            flow_field=flow_field
        )
        
        # Format values with physical units and calculate ranges
        formatted_values = []
        formatted_ranges = []
        
        # Get all solutions in cluster to calculate ranges
        cluster_solutions = cluster.get('all_solutions', [cluster['best_solution'], cluster['central_solution']])
        
        for j, value in enumerate(sol['measures']):
            if j < len(feature_indices):
                feature_idx = feature_indices[j]
                formatted_values.append(format_value_with_unit(value, feature_idx, lang))
                
                # Calculate range for this feature across all solutions in cluster
                if len(cluster_solutions) > 1:
                    feature_values = [s['measures'][j] for s in cluster_solutions]
                    min_val = min(feature_values)
                    max_val = max(feature_values)
                    range_str = f"{format_value_with_unit(min_val, feature_idx, lang)} - {format_value_with_unit(max_val, feature_idx, lang)}"
                else:
                    range_str = "-"
                formatted_ranges.append(range_str)
            else:
                formatted_values.append(f"{value:.3f}")  # Fallback
                formatted_ranges.append("-")
        
        range_label = "Bereich" if lang == 'DE' else "Range"
        metrics_data = {
            T[lang]['STEP6_FEATURE_LABEL']: labels, 
            T[lang]['STEP6_VALUE_LABEL']: formatted_values,
            range_label: formatted_ranges
        }
        metrics_df = pd.DataFrame(metrics_data)
        table = dbc.Table.from_dataframe(metrics_df, striped=True, bordered=True, hover=True, size='sm')
        
        # Calculate design robustness based on cluster size
        # Robustness = cluster size as percentage of total solutions in archive
        total_solutions = sum([c.get('size', 0) for c in clusters])
        robustness_percent = (cluster['size'] / total_solutions * 100) if total_solutions > 0 else 0
        robustness_label = "Entwurfsrobustheit" if lang == 'DE' else "Design Robustness"
        robustness_info = (
            f"{robustness_percent:.1f}% der Archive-Lösungen" if lang == 'DE' 
            else f"{robustness_percent:.1f}% of archive solutions"
        )
        
        # Format objective with unit
        objective_unit = T[lang].get('OBJECTIVE_UNIT', '')
        objective_formatted = T[lang]['STEP6_OBJECTIVE_LABEL'].format(value=sol['objective'])
        if objective_unit:
            objective_formatted = f"{objective_formatted} {objective_unit}"
        
        # Create toggle for best/central solution
        toggle_radio = dbc.RadioItems(
            id={'type': 'solution-toggle', 'index': i},
            options=[
                {'label': 'Repräsentativste Lösung' if lang == 'DE' else 'Most Representative Solution', 'value': 'central'},
                {'label': 'Beste Lösung' if lang == 'DE' else 'Best Solution', 'value': 'best'}
            ],
            value=display_mode,
            inline=True,
            className="mb-2"
        )
        
        # Create card with side-by-side layout
        card = dbc.Card([
            dbc.CardHeader([
                html.H5(f"Cluster {cluster['cluster_id']} ({cluster['size']} " + 
                       ("Lösungen" if lang == 'DE' else "solutions") + ")", className="mb-0 d-inline-block"),
            ]),
            dbc.CardBody([
                toggle_radio,
                html.B(objective_formatted, className="d-block mb-2"),
                dbc.Row([
                    # 3D visualization on the left
                    dbc.Col([
                        html.Div([
                            dcc.Graph(
                                figure=fig_3d,
                                id={'type': '3d-plot', 'index': i},
                                config={'displayModeBar': True, 'displaylogo': False},
                                style={'height': '450px', 'width': '100%'}
                            ),
                        ], style={'overflow': 'hidden'}),  # Prevent overflow
                    ], md=8, className="pe-2"),
                    # Metrics table on the right
                    dbc.Col([
                        html.H6(T[lang]['STEP6_METRICS_HEADER'], className="mb-2"),
                        html.Div(table, className="compact-table"),
                        html.Hr(className="my-2"),
                        html.Div([
                            html.Strong(robustness_label + ": ", className="text-muted"),
                            html.Span(robustness_info, className="text-primary")
                        ], className="small mt-2")
                    ], md=4, className="ps-2"),
                ], className="g-0"),  # Remove gutter spacing
                
                # Flow Field Visualization (for U-Net/Hybrid models)
                html.Div([
                    html.Hr(className="my-2"),
                    html.Div([
                        html.H6(T[lang]['STEP6_FLOW_FIELD_HEADER'], className="d-inline-block mb-2"),
                        dbc.Checklist(
                            options=[{"label": T[lang]['STEP6_SHOW_FLOW'], "value": 1}],
                            value=[],
                            id={'type': 'show-flow-toggle', 'index': i},
                            switch=True,
                            className="float-end"
                        ),
                    ], className="clearfix"),
                    html.Div(id={'type': 'flow-field-display', 'index': i})
                ], id={'type': 'flow-field-container', 'index': i}, style={'display': 'none'}),
                
                # 3x3 Diversity preview below
                html.Hr(className="my-2"),
                html.H6(("Diversität (9 zufällige Beispiele)" if lang == 'DE' else "Diversity (9 random samples)"), 
                       className="mb-2 mt-2"),
                html.Div(id={'type': 'diversity-grid', 'index': i}, children=create_diversity_grid(cluster, heightmap_res, i))
            ], className="p-2")
        ], className="mb-3")
        
        col = dbc.Col(card, md=12, lg=12, xl=6)  # Full width on small/medium, half on XL
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
    feature_set = results_data.get('feature_set', 'consolidated')
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

def check_unet_model_availability(parcel_size_m=81):
    """Check if U-Net model is available for the given parcel size."""
    from pathlib import Path
    models_dir = Path('models')
    unet_path = models_dir / f'unet_{parcel_size_m}m.pth'
    return unet_path.exists()

# Callback to show/hide global flow toggle based on model availability
@callback(
    Output('global-flow-container', 'style'),
    Input('results-store', 'data'),
    Input('comparison-store', 'data')
)
def toggle_global_flow_container(results_data, selected_ids):
    """Show global flow toggle if U-Net model is available and clusters are selected"""
    unet_available = check_unet_model_availability()
    num_clusters = len(selected_ids) if selected_ids else 0
    
    if unet_available and num_clusters > 0:
        return {'display': 'block'}
    else:
        return {'display': 'none'}

# Callback to show/hide individual flow sections based on model availability
@callback(
    Output({'type': 'flow-field-container', 'index': ALL}, 'style'),
    Input('results-store', 'data'),
    Input('comparison-store', 'data')
)
def toggle_flow_field_sections(results_data, selected_ids):
    """Show individual flow field sections if U-Net model is available"""
    unet_available = check_unet_model_availability()
    num_clusters = len(selected_ids) if selected_ids else 0
    
    if unet_available and num_clusters > 0:
        return [{'display': 'block'}] * num_clusters
    else:
        return [{'display': 'none'}] * num_clusters

# Callback to display flow field visualization
@callback(
    Output({'type': 'flow-field-display', 'index': MATCH}, 'children'),
    Input({'type': 'show-flow-toggle', 'index': MATCH}, 'value'),
    State('comparison-store', 'data'),
    State('clustering-data-store', 'data'),
    State('results-store', 'data'),
    State('language-store', 'data'),
    State({'type': 'show-flow-toggle', 'index': MATCH}, 'id')
)
def display_flow_field(show_toggle, selected_ids, clustering_data, results_data, lang, component_id):
    """Display flow field visualization when toggle is on"""
    if lang is None:
        lang = 'DE'
    
    print(f"DEBUG: Flow field callback triggered - show_toggle: {show_toggle}, component_id: {component_id}")
    
    # Only display if toggle is on
    if not show_toggle or 1 not in show_toggle:
        print(f"DEBUG: Toggle is off or empty for component {component_id}")
        return html.Div()
    
    print(f"DEBUG: Toggle is ON for component {component_id}")
    
    if not selected_ids or not clustering_data or not results_data:
        print(f"DEBUG: Missing data - selected_ids: {bool(selected_ids)}, clustering_data: {bool(clustering_data)}, results_data: {bool(results_data)}")
        return dbc.Alert("No data available", color="warning")
    
    try:
        # Get cluster index from component ID
        cluster_idx = component_id['index']
        
        # Get selected cluster IDs (comparison_data is just a list of selected IDs)
        if cluster_idx >= len(selected_ids):
            return dbc.Alert("Cluster not found", color="warning")
        
        cluster_id = selected_ids[cluster_idx]
        
        # Load full results to access flow field data
        results_path = results_data['full_results_path']
        with open(results_path, 'rb') as f:
            list_of_elites = pickle.load(f)
        
        # Find the solution for this cluster from clustering data
        clusters = clustering_data.get('clusters', [])
        
        target_cluster = None
        for cluster in clusters:
            if cluster['cluster_id'] == cluster_id:
                target_cluster = cluster
                break
        
        if not target_cluster:
            return dbc.Alert("Cluster data not found", color="warning")
        
        # Get the displayed solution (best or central) - default to central
        solution = target_cluster['central_solution']
        
        # Generate flow field using U-Net model (regardless of optimization method used)
        try:
            # Import necessary modules
            import torch
            from backend.model_evaluator import create_evaluator
            from backend.fast_encoding import NumbaFastEncoding
            
            # Get solution genome
            genome = solution['genome']
            
            # Create U-Net evaluator
            device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
            unet_eval = create_evaluator('unet', parcel_size=81, device=device)
            
            # Generate heightmap using same encoding as in diagnostics
            encoding = NumbaFastEncoding(parcel_size=81)  # 27x27 grid for 81m parcel
            heightmap_27x27 = encoding.express_batch(genome.reshape(1, -1))[0]
            
            # Construct proper 3-channel domain grids for U-Net (terrain, buildings, landuse)
            from backend.model_evaluator import construct_domain_grids_batch
            terrain, buildings, landuse = construct_domain_grids_batch(
                heightmap_27x27[np.newaxis, :, :],  # Add batch dimension
                parcel_size_cells=27  # 81m / 3m = 27 cells
            )
            
            # Normalize inputs using the evaluator's normalization stats
            terrain_norm = (terrain - unet_eval.terrain_mean) / unet_eval.terrain_std
            buildings_norm = (buildings - unet_eval.buildings_mean) / unet_eval.buildings_std
            landuse_norm = (landuse - unet_eval.landuse_mean) / unet_eval.landuse_std
            
            # Stack into 3-channel input: (1, 3, 66, 94)
            X = np.stack([terrain_norm[0], buildings_norm[0], landuse_norm[0]], axis=0)
            
            # Prepare input tensor (convert to half precision on CUDA to match model)
            dtype = torch.float16 if device.type == 'cuda' else torch.float32
            X_torch = torch.tensor(X, dtype=dtype, device=device).unsqueeze(0)  # Shape: (1, 3, 66, 94)
            
            # ROI coordinates for extracting results
            y_start = (66 - 27) // 2  # Center vertically
            x_start = (94 - 27) // 2  # Center horizontally
            
            # Get U-Net predictions
            with torch.no_grad():
                Y_pred = unet_eval.model(X_torch)  # Shape: (1, 6, 66, 94)
                
                # Extract velocity components (channels 2 and 3: uq, vq)
                uq_full = Y_pred[0, 2, :, :] * unet_eval.uq_std + unet_eval.uq_mean  # cm/s
                vq_full = Y_pred[0, 3, :, :] * unet_eval.vq_std + unet_eval.vq_mean  # cm/s
                
                # Convert to numpy and from cm/s to m/s
                uq_np = uq_full.cpu().numpy() / 100.0  # Convert cm/s to m/s
                vq_np = vq_full.cpu().numpy() / 100.0
                
                # Extract ROI (27x27 region where the parcel is)
                uq_roi = uq_np[y_start:y_start+27, x_start:x_start+27]
                vq_roi = vq_np[y_start:y_start+27, x_start:x_start+27]
                
                # Create flow field in expected format: (2, H, W) for (u, v)
                flow_field = np.stack([uq_roi, vq_roi], axis=0)  # Shape: (2, 27, 27)
                
        except Exception as e:
            return dbc.Alert(
                f"Error generating flow field with U-Net model: {str(e)}",
                color="warning"
            )
        
        # Get flow field (u, v velocity components)
        u = flow_field[0]  # X-component  
        v = flow_field[1]  # Y-component
        
        # Create quiver plot using plotly
        import plotly.figure_factory as ff
        
        # Downsample for visualization (every 2nd point)
        step = 2
        y_coords, x_coords = np.mgrid[0:u.shape[0]:step, 0:u.shape[1]:step]
        u_sampled = u[::step, ::step]
        v_sampled = v[::step, ::step]
        
        # Create quiver plot
        fig = ff.create_quiver(
            x_coords, y_coords,
            u_sampled, v_sampled,
            scale=0.1,
            arrow_scale=0.3,
            name='Flow Field',
            line=dict(width=1)
        )
        
        fig.update_layout(
            title=T[lang]['STEP6_FLOW_TITLE'],
            height=400,
            margin=dict(l=20, r=20, t=40, b=20),
            xaxis_title="X",
            yaxis_title="Y",
            yaxis=dict(scaleanchor="x", scaleratio=1)
        )
        
        return dcc.Graph(figure=fig)
        
    except Exception as e:
        import traceback
        error_msg = f"Error displaying flow field: {str(e)}"
        print(f"[ERROR] {error_msg}")
        print(traceback.format_exc())
        return dbc.Alert(error_msg, color="danger")


# Store for flow visualization toggle states (handles both global and individual toggles)
@callback(
    Output('flow-toggle-store', 'data'),
    Output({'type': 'show-flow-toggle', 'index': ALL}, 'value'),
    Input('global-flow-toggle', 'value'),
    Input({'type': 'show-flow-toggle', 'index': ALL}, 'value'),
    State({'type': 'show-flow-toggle', 'index': ALL}, 'id'),
    State('comparison-store', 'data'),
    prevent_initial_call=True
)
def store_flow_toggle_states(global_toggle, toggle_values, toggle_ids, selected_ids):
    """Store flow toggle states and handle global toggle"""
    if not ctx.triggered:
        return {}, [no_update] * len(toggle_ids) if toggle_ids else []
    
    triggered_id = ctx.triggered_id
    
    # If global toggle was triggered, set all individual toggles to match
    if triggered_id == 'global-flow-toggle':
        global_on = (global_toggle is not None and 1 in global_toggle)
        num_clusters = len(selected_ids) if selected_ids else len(toggle_ids) if toggle_ids else 0
        
        # Set all individual toggles to match global state
        new_toggle_values = [[1] if global_on else [] for _ in range(num_clusters)]
        
        # Update flow states dictionary
        flow_states = {str(i): global_on for i in range(num_clusters)}
        
        return flow_states, new_toggle_values
    
    # Otherwise, individual toggle was triggered - update only that one
    if not toggle_values or not toggle_ids:
        return {}, []
    
    flow_states = {}
    for i, (value, toggle_id) in enumerate(zip(toggle_values, toggle_ids)):
        cluster_idx = toggle_id['index']
        flow_states[str(cluster_idx)] = 1 in (value or [])
    
    # Return no_update for each individual toggle (preserve current state)
    return flow_states, [no_update] * len(toggle_ids)
