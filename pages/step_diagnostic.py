#
# pages/step_diagnostic.py
#
from dash import dcc, html, Input, Output, State, callback
import dash_bootstrap_components as dbc
from backend.translation import T
import numpy as np
from backend.optimization_process import create_environment, _calculate_dynamic_feat_ranges
from backend.encoding import ParametricEncoding
from backend.config import ENCODING_CONFIG, DOMAIN_CONFIG

def _visualize_fitness_calculation(genome, encoding_obj, env_config):
    """
    Step-by-step visualization of fitness calculation for a single solution.
    Now compares BOTH objective functions side-by-side.
    """
    from scipy.ndimage import rotate
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    from backend.evaluation import compute_fitness, compute_fitness_street_canyon
    
    # Step 1: Express genome to heightmap
    heightmap_2d = encoding_obj.express(env_config['buildable_mask'], genome)
    
    # Step 2: Create 3D design array
    # CRITICAL: ALL Z-axes are now in FLOORS throughout the application
    # heightmap_2d is in FLOORS, env_3d_fixed is in FLOORS (1 voxel = 1 floor)
    max_height = env_config['env_3d_fixed'].shape[2]
    z_indices = np.arange(max_height)
    design_3d = (z_indices < heightmap_2d.astype(int)[:, :, np.newaxis]).astype(np.int8)
    
    # Step 3: Combine with existing buildings
    combined_env_3d = np.maximum(env_config['env_3d_fixed'], design_3d)
    
    # Step 4: Compute fitness with BOTH methods
    wind_direction = env_config.get('wind_direction', 0)
    
    # === METHOD 1: Simple Wind Porosity (CORRECTED) ===
    # Rotate so wind direction aligns with Y-axis
    rotation_angle_simple = wind_direction % 360
    rotated_env_simple = rotate(combined_env_3d, angle=rotation_angle_simple, axes=(0, 1), reshape=False, order=0)
    
    # For each (x, z) position, check if there's any obstruction along the entire Y-axis (wind path)
    # Use max instead of sum: if max == 0, the entire horizontal path is clear
    max_along_wind = np.max(rotated_env_simple, axis=1)  # Shape: (X, Z)
    open_paths = np.sum(max_along_wind == 0)
    total_paths = max_along_wind.shape[0] * max_along_wind.shape[1]
    porosity = open_paths / total_paths if total_paths > 0 else 0.0
    fitness_simple = np.clip(porosity, 0.0, 1.0)
    
    # For visualization: Create intuitive top-down view
    # Show buildings from above with wind flow direction marked
    building_footprint = np.max(rotated_env_simple, axis=2)  # Max height at each (X, Y)
    
    # Create wind flow openness map based on the corrected method
    # max_along_wind has shape (X, Z) - shows if path is open at each (x, z) position
    # For top-down visualization, we need to aggregate across Z (height) dimension
    # to show ground-level openness at each (X, Y) position
    openness_per_xz = (max_along_wind == 0).astype(float)  # 1 if path is open, 0 if blocked
    
    # Aggregate across Z to show if ANY height level has an open path at each X position
    # Alternative: use mean to show percentage of heights with open paths
    openness_per_x = np.mean(openness_per_xz, axis=1)  # Average openness across heights for each X
    
    # For top-down view: show building footprint colored by wind openness
    # Use building_footprint shape, but color by openness_per_x at each X position
    wind_flow_map = np.tile(openness_per_x[:, np.newaxis], (1, building_footprint.shape[1]))
    
    # === METHOD 2: Street Canyon Ventilation (OPTIMIZED - vectorized) ===
    # Uses different rotation angle (+90 degrees)
    rotation_angle_street = (wind_direction + 90) % 360
    rotated_env_street = rotate(combined_env_3d, angle=rotation_angle_street, axes=(0, 1), reshape=False, order=0)
    rows, cols, height = rotated_env_street.shape
    
    # Component 1: Ground-level street canyons (VECTORIZED with continuity weighting)
    ground_level = rotated_env_street[:, :, :2]
    ground_occupied = np.any(ground_level > 0, axis=2).astype(np.int8)
    ground_open = 1 - ground_occupied
    
    # Calculate continuity-weighted score
    row_openness = np.mean(ground_open, axis=1)
    transitions = np.abs(np.diff(ground_occupied, axis=1))
    fragmentation = np.mean(transitions, axis=1)
    continuity_weight = 1.0 - np.clip(fragmentation, 0, 1)
    street_canyon_score = np.mean(row_openness * (0.5 + 0.5 * continuity_weight))
    
    # For visualization, use the ground_open map
    corridor_score_map = ground_open.astype(float)
    
    # Component 2: Lateral ventilation (VECTORIZED)
    open_per_col = np.sum(rotated_env_street == 0, axis=(0, 2))
    total_per_col = rows * height
    lateral_openness_per_col = open_per_col / total_per_col
    # Broadcast to 2D map for visualization
    lateral_openness_map = np.tile(lateral_openness_per_col, (rows, 1))
    lateral_ventilation_score = np.mean(lateral_openness_per_col)
    
    # Component 3: Height variation (VECTORIZED)
    max_heights_street = np.max(rotated_env_street, axis=2)
    height_std = np.std(max_heights_street)
    max_possible_std = height / 2.0
    height_variation_score = min(height_std / max_possible_std, 1.0) if max_possible_std > 0 else 0.0
    
    # Component 4: Partial penetration (VECTORIZED)
    projection_street = np.sum(rotated_env_street, axis=1)
    penetration_per_column = 1.0 - np.clip(projection_street / height, 0.0, 1.0)
    penetration_score = np.mean(penetration_per_column)
    
    # Compute final Street Canyon fitness (matches evaluation.py)
    fitness_street_canyon = (
        0.35 * street_canyon_score +
        0.25 * lateral_ventilation_score +
        0.15 * height_variation_score +
        0.25 * penetration_score
    )
    fitness_street_canyon = np.clip(fitness_street_canyon, 0.0, 1.0)
    
    # Create visualizations
    # 1. Heightmap
    fig1 = go.Figure(data=go.Heatmap(
        z=heightmap_2d,
        colorscale='Viridis',
        colorbar=dict(title='Height (floors)')
    ))
    fig1.update_layout(
        title='Step 1: Generated Heightmap',
        width=300, height=300,
        xaxis_title='X', yaxis_title='Y'
    )
    
    # 2. Top view of combined 3D (max projection)
    combined_max_z = np.max(combined_env_3d, axis=2)
    fig2 = go.Figure(data=go.Heatmap(
        z=combined_max_z,
        colorscale='Greys',
        colorbar=dict(title='Occupied')
    ))
    fig2.update_layout(
        title='Step 2: Combined with Existing (Top View)',
        width=300, height=300,
        xaxis_title='X', yaxis_title='Y'
    )
    
    # 3. Rotated environment for simple porosity (show max projection to see all buildings)
    # Use max projection instead of single slice to ensure all buildings are visible
    rotated_max_z = np.max(rotated_env_simple, axis=2)
    fig3 = go.Figure(data=go.Heatmap(
        z=rotated_max_z,
        colorscale='Reds',
        colorbar=dict(title='Occupied')
    ))
    fig3.update_layout(
        title=f'Step 3: Rotated {rotation_angle_simple}° (Simple Porosity)',
        width=300, height=300,
        xaxis_title='X', yaxis_title='Y'
    )
    
    # 4a. Top-down view showing buildings (Simple Porosity method)
    # Shows building footprints from above - wind flows from bottom to top (along Y-axis)
    fig4 = go.Figure(data=go.Heatmap(
        z=building_footprint,
        colorscale='Greys',
        colorbar=dict(title='Height')
    ))
    # Add arrow annotation to show wind direction
    fig4.add_annotation(
        x=building_footprint.shape[1] / 2,
        y=building_footprint.shape[0] + 2,
        text="Wind Direction ↑",
        showarrow=False,
        font=dict(size=10, color="blue"),
        yanchor='bottom'
    )
    fig4.update_layout(
        title=f'Step 4a: Building Footprints (Wind ↑)',
        width=300, height=300,
        xaxis_title='X (perpendicular to wind)', yaxis_title='Y (wind direction)',
        yaxis=dict(scaleanchor='x', scaleratio=1)
    )
    
    # 4b. Horizontal wind path openness map (CORRECTED)
    # Shows ground-level footprint colored by wind path openness
    # For each X position, shows if horizontal wind paths at ANY height are completely unobstructed
    # Note: Horizontal stripes are expected - each X position has same openness regardless of Y,
    # because we're checking if wind can flow THROUGH the entire Y-axis at that X position
    # IMPORTANT: Transpose to match the rotated environment's orientation
    fig4b = go.Figure(data=go.Heatmap(
        z=wind_flow_map.T,  # Transpose to match plotly's convention (row=Y, col=X)
        colorscale='RdYlGn',
        colorbar=dict(title='Avg Path<br>Openness<br>(across heights)')
    ))
    fig4b.add_annotation(
        x=wind_flow_map.shape[0] / 2,  # Now X is first dimension
        y=wind_flow_map.shape[1] + 2,   # Y is second dimension
        text="Wind Direction ↑",
        showarrow=False,
        font=dict(size=10, color="blue"),
        yanchor='bottom'
    )
    fig4b.update_layout(
        title=f'Step 4b: Wind Path Openness (Porosity: {fitness_simple:.2%})',
        width=300, height=300,
        xaxis_title='X (perpendicular to wind)', 
        yaxis_title='Y (wind direction)',
        annotations=[
            dict(text=f'Vertical stripes show wind openness<br>at each X position (averaged across heights)',
                 xref='paper', yref='paper', x=0.5, y=-0.25, 
                 showarrow=False, font=dict(size=8, color='gray'),
                 xanchor='center', yanchor='top')
        ],
        yaxis=dict(scaleanchor='x', scaleratio=1)
    )
    
    # 4c. Side view of wind paths (X vs Z) - MORE INTUITIVE!
    # This directly shows the max_along_wind array: which (X, Z) positions are completely open
    # Green = wind can flow through entire Y-depth unobstructed at this (X, Z)
    # Red = wind is blocked somewhere along Y-depth at this (X, Z)
    # IMPORTANT: This includes BOTH your design AND existing buildings!
    fig4c = go.Figure(data=go.Heatmap(
        z=openness_per_xz.T,  # Transpose so Z is vertical axis
        colorscale='RdYlGn',
        colorbar=dict(title='Open (1)<br>or<br>Blocked (0)'),
        zmin=0, zmax=1
    ))
    fig4c.add_annotation(
        x=openness_per_xz.shape[0] / 2,
        y=-2,
        text="◀─ Wind flows INTO page (along Y) ─▶",
        showarrow=False,
        font=dict(size=10, color="blue"),
        yanchor='top'
    )
    fig4c.update_layout(
        title=f'Step 4c: Wind Paths (Design + Existing Buildings)',
        width=300, height=300,
        xaxis_title='X (perpendicular to wind)',
        yaxis_title='Z (Height in floors)',
        annotations=[
            dict(text=f'Green = open path | Red = blocked by design OR existing buildings<br>1 floor ≈ 3 meters',
                 xref='paper', yref='paper', x=0.5, y=-0.25, 
                 showarrow=False, font=dict(size=8, color='gray'),
                 xanchor='center', yanchor='top')
        ]
    )
    
    # === Street Canyon Method Visualizations (Alternative Method) ===
    
    # 5. Ground-level street canyons (Component 1)
    fig5 = go.Figure(data=go.Heatmap(
        z=1 - ground_occupied,  # Invert so open = bright
        colorscale='Greens',
        colorbar=dict(title='Open (ground)')
    ))
    fig5.update_layout(
        title=f'Step 5a: Street Canyons (Score: {street_canyon_score:.3f})',
        width=300, height=300,
        xaxis_title='X', yaxis_title='Y',
        annotations=[dict(text='Alternative Method', xref='paper', yref='paper', 
                         x=0.5, y=1.1, showarrow=False, font=dict(size=9, color='gray'))]
    )
    
    # 6. Lateral ventilation (Component 2)
    fig6 = go.Figure(data=go.Heatmap(
        z=lateral_openness_map,
        colorscale='Blues',
        colorbar=dict(title='Openness')
    ))
    fig6.update_layout(
        title=f'Step 5b: Lateral Ventilation (Score: {lateral_ventilation_score:.3f})',
        width=300, height=300,
        xaxis_title='X', yaxis_title='Y',
        annotations=[dict(text='Alternative Method', xref='paper', yref='paper', 
                         x=0.5, y=1.1, showarrow=False, font=dict(size=9, color='gray'))]
    )
    
    # 7. Height variation (Component 3)
    fig7 = go.Figure(data=go.Heatmap(
        z=max_heights_street,
        colorscale='Viridis',
        colorbar=dict(title='Max Height')
    ))
    fig7.update_layout(
        title=f'Step 5c: Height Variation (Score: {height_variation_score:.3f})',
        width=300, height=300,
        xaxis_title='X', yaxis_title='Y',
        annotations=[dict(text='Alternative Method', xref='paper', yref='paper', 
                         x=0.5, y=1.1, showarrow=False, font=dict(size=9, color='gray'))]
    )
    
    # 8. Partial penetration (Component 4)
    fig8 = go.Figure(data=go.Heatmap(
        z=penetration_per_column,
        colorscale='Oranges',
        colorbar=dict(title='Penetration')
    ))
    fig8.update_layout(
        title=f'Step 5d: Partial Penetration (Score: {penetration_score:.3f})',
        width=300, height=300,
        xaxis_title='X', yaxis_title='Z',
        annotations=[dict(text='Alternative Method', xref='paper', yref='paper', 
                         x=0.5, y=1.1, showarrow=False, font=dict(size=9, color='gray'))]
    )
    
    # Statistics comparing both methods
    stats = {
        'heightmap_stats': {
            'min': float(np.min(heightmap_2d)),
            'max': float(np.max(heightmap_2d)),
            'mean': float(np.mean(heightmap_2d)),
            'non_zero': int(np.sum(heightmap_2d > 0))
        },
        'combined_3d_stats': {
            'design_voxels': int(np.sum(design_3d > 0)),
            'existing_voxels': int(np.sum(env_config['env_3d_fixed'] > 0)),
            'total_voxels': int(np.sum(combined_env_3d > 0))
        },
        'wind_stats': {
            'rotation_angle_simple': rotation_angle_simple,
            'rotation_angle_street': rotation_angle_street,
            'open_paths': int(open_paths),
            'total_paths': int(total_paths),
            'porosity': float(porosity),
            'fitness_simple_porosity': float(fitness_simple),
            'fitness_street_canyon': float(fitness_street_canyon)
        },
        'street_canyon_components': {
            'street_canyons': float(street_canyon_score),
            'lateral_ventilation': float(lateral_ventilation_score),
            'height_variation': float(height_variation_score),
            'partial_penetration': float(penetration_score)
        }
    }
    
    return {
        'fig1': fig1,
        'fig2': fig2,
        'fig3': fig3,
        'fig4': fig4,
        'fig4b': fig4b,
        'fig4c': fig4c,
        'fig5': fig5,
        'fig6': fig6,
        'fig7': fig7,
        'fig8': fig8,
        'stats': stats
    }


def _test_solution_insertion(env_config, selected_features, hard_constraints):
    """
    Test actual solution generation and archive insertion to identify issues.
    """
    from ribs.archives import GridArchive
    from backend.evaluation import eval_solution
    from backend.config import QD_CONFIG
    
    # Create a test archive
    solution_dim = ParametricEncoding(ENCODING_CONFIG).get_dimension()
    archive = GridArchive(
        solution_dim=solution_dim,
        dims=[QD_CONFIG['num_niches']] * len(env_config['labels']),
        ranges=env_config['feat_ranges'],
        learning_rate=QD_CONFIG['learning_rate'],
        threshold_min=-0.5  # Same as optimizer: allow zero-fitness, reject constraint violations
    )
    
    # Set up environment for evaluation
    env_config['wind_direction'] = 0  # Default wind direction
    env_config['hard_constraints'] = hard_constraints
    encoding_obj = ParametricEncoding(ENCODING_CONFIG)
    
    # Generate and test random solutions
    num_test = 100
    negative_fitness = 0
    zero_fitness = 0
    positive_fitness = 0
    inserted = 0
    
    feature_samples = []
    fitness_samples = []
    
    for i in range(num_test):
        # Generate random genome
        genome = np.random.randn(solution_dim)
        
        # Evaluate solution
        result = eval_solution(genome, encoding_obj, env_config)
        fitness = result[0]
        features = result[1:len(selected_features)+1]
        
        # Track statistics
        if fitness < 0:
            negative_fitness += 1
        elif fitness == 0:
            zero_fitness += 1
        else:
            positive_fitness += 1
        
        # Try to add to archive (pyribs expects batches, so reshape to batch of 1)
        status_dict = archive.add(
            np.array([genome]),      # Shape: (1, solution_dim)
            np.array([fitness]),     # Shape: (1,)
            np.array([features])     # Shape: (1, num_features)
        )
        # Check if any solutions were added
        if status_dict['status'][0]:
            inserted += 1
        
        # Collect samples for analysis
        if i < 10:  # First 10 samples
            feature_samples.append({
                'fitness': fitness,
                'features': features,
                'inserted': bool(status_dict['status'][0])
            })
            fitness_samples.append(fitness)
    
    # Analyze results
    success_rate = inserted / num_test if num_test > 0 else 0
    
    # Check if wind porosity is the issue
    avg_fitness = np.mean(fitness_samples) if fitness_samples else 0
    fitness_variance = np.var(fitness_samples) if len(fitness_samples) > 1 else 0
    
    # Determine primary issue
    if negative_fitness == num_test:
        primary_issue = "ALL solutions violate constraints (fitness = -1). This means NO solutions can meet the hard constraints."
    elif negative_fitness > num_test * 0.9:
        primary_issue = f"{negative_fitness/num_test*100:.0f}% of solutions violate constraints. Constraints are too restrictive."
    elif positive_fitness > 0 and inserted == 0:
        primary_issue = "Solutions have positive fitness but are NOT being inserted. This indicates a feature range or archive configuration issue."
    elif zero_fitness > num_test * 0.5:
        if zero_fitness == num_test:
            primary_issue = (
                f"ALL solutions have ZERO fitness (wind porosity = 0.0).\n\n"
                f"This means buildings completely block wind flow in the current direction.\n\n"
                f"CRITICAL: Archive threshold_min = 0.0, so solutions with fitness = 0.0 are rejected!\n\n"
                f"Possible causes:\n"
                f"  1. Dense existing buildings already block wind\n"
                f"  2. Buildable area is too large/fills entire grid\n"
                f"  3. Random solutions create solid building masses\n\n"
                f"Solutions:\n"
                f"  1. Set threshold_min = -1.0 to accept zero-fitness solutions\n"
                f"  2. Change fitness function to reward other metrics\n"
                f"  3. Adjust wind direction (current: {env_config.get('wind_direction', 0)}°)\n"
                f"  4. Use a different objective (not wind porosity)"
            )
        else:
            primary_issue = f"{zero_fitness/num_test*100:.0f}% of solutions have zero fitness. Check fitness function (wind porosity)."
    else:
        primary_issue = "Unknown issue. Check archive configuration and feature ranges."
    
    # Format feature samples for display
    sample_text = ""
    for idx, sample in enumerate(feature_samples):
        sample_text += f"\nSample {idx+1}:\n"
        sample_text += f"  Fitness: {sample['fitness']:.4f}\n"
        sample_text += f"  Features: {[f'{f:.2f}' for f in sample['features']]}\n"
        sample_text += f"  Inserted: {'YES' if sample['inserted'] else 'NO'}\n"
        sample_text += f"  Feature Ranges: {env_config['feat_ranges']}\n"
    
    # Generate detailed fitness visualizations for first 3 samples
    fitness_visualizations = []
    for i in range(min(3, num_test)):
        genome = np.random.randn(solution_dim)
        viz_data = _visualize_fitness_calculation(genome, encoding_obj, env_config)
        fitness_visualizations.append(viz_data)
    
    return {
        'num_tested': num_test,
        'negative_fitness': negative_fitness,
        'zero_fitness': zero_fitness,
        'positive_fitness': positive_fitness,
        'inserted': inserted,
        'success_rate': success_rate,
        'primary_issue': primary_issue,
        'feature_samples': sample_text,
        'fitness_samples': fitness_samples,
        'fitness_visualizations': fitness_visualizations,
        'archive_stats': {
            'num_elites': archive.stats.num_elites,
            'coverage': archive.stats.coverage
        }
    }


def layout(lang='DE'):
    return dbc.Container([
        html.H2("🔍 Diagnostic Page - Parcel & Constraint Validation"),
        html.P("Use this page to validate that your selected parcel and constraints are feasible for optimization."),
        
        dbc.Card([
            dbc.CardHeader(html.H4("Parcel Analysis")),
            dbc.CardBody([
                dbc.Button("Run Parcel Diagnostic", id="run-diagnostic-btn", color="primary", className="mb-3"),
                dcc.Loading(html.Div(id="diagnostic-output"))
            ])
        ])
    ], fluid=True)


@callback(
    Output('diagnostic-output', 'children'),
    Input('run-diagnostic-btn', 'n_clicks'),
    State('session-store', 'data'),
    prevent_initial_call=True
)
def run_diagnostic(n_clicks, session_data):
    if not session_data or 'site_polygon' not in session_data:
        return dbc.Alert("⚠️ No parcel selected. Please go to Step 1 and select a Flurstück first.", color="warning")
    
    # Check if site_polygon is empty/None
    site_polygon = session_data.get('site_polygon')
    if not site_polygon or not site_polygon.get('features'):
        return dbc.Alert("⚠️ No parcel selected. Please go to Step 1 and select a Flurstück first.", color="warning")
    
    try:
        # Get session data
        wind_direction = session_data.get('wind_direction', 0)
        selected_features = session_data.get('selected_features', [0, 1, 2, 3])
        user_feature_ranges = session_data.get('user_feature_ranges', {})
        hard_constraints = session_data.get('hard_constraints', {})
        
        # Create environment
        env_config = create_environment(
            site_polygon, 
            selected_features, 
            user_feature_ranges, 
            hard_constraints
        )
        
        # Extract key metrics
        buildable_mask = env_config['buildable_mask']
        buildable_area_m2 = env_config['buildable_area_in_sq_meters']
        grid_res = buildable_mask.shape[0]
        pixel_size = DOMAIN_CONFIG['pixel_size_in_meters']
        
        buildable_pixels = np.sum(buildable_mask)
        grid_area_m2 = (grid_res * pixel_size) ** 2
        coverage_ratio = buildable_area_m2 / grid_area_m2 if grid_area_m2 > 0 else 0
        
        # Check for shape issues
        rows_occupied = np.any(buildable_mask, axis=1).sum()
        cols_occupied = np.any(buildable_mask, axis=0).sum()
        aspect_ratio = max(rows_occupied, cols_occupied) / min(rows_occupied, cols_occupied) if min(rows_occupied, cols_occupied) > 0 else float('inf')
        
        # Analyze constraints
        max_height_voxels = hard_constraints.get('max_height', ENCODING_CONFIG['z_length'] * 3)
        max_height_floors = max_height_voxels // 3
        max_height_meters = max_height_floors * 3
        
        min_distance_meters = hard_constraints.get('min_distance', 0)
        min_distance_pixels = min_distance_meters / pixel_size if min_distance_meters > 0 else 0
        
        # Estimate feasibility
        issues = []
        warnings = []
        
        # Check 1: Very small parcel
        if buildable_area_m2 < 100:
            issues.append(f"⛔ Parcel is very small ({buildable_area_m2:.1f} m²). Minimum recommended: 100 m²")
        elif buildable_area_m2 < 500:
            warnings.append(f"⚠️ Small parcel ({buildable_area_m2:.1f} m²). May limit solution diversity.")
        
        # Check 2: Extreme aspect ratio
        if aspect_ratio > 5:
            warnings.append(f"⚠️ Unusual parcel shape (aspect ratio: {aspect_ratio:.1f}). May affect optimization.")
        
        # Check 3: Min distance vs parcel size
        if min_distance_meters > 0:
            # Rough estimate: with min distance constraint, effective buildable area shrinks
            erosion_effect = min_distance_pixels * 2  # Approximate erosion from edges
            effective_pixels = buildable_pixels - erosion_effect * (rows_occupied + cols_occupied - 4)
            if effective_pixels <= 0:
                issues.append(f"⛔ Min distance constraint ({min_distance_meters}m = {min_distance_pixels:.1f} pixels) is too large for parcel size. No valid placement possible.")
            elif effective_pixels < buildable_pixels * 0.1:
                warnings.append(f"⚠️ Min distance constraint ({min_distance_meters}m) significantly reduces usable area by ~{100 * (1 - effective_pixels/buildable_pixels):.0f}%")
        
        # Check 4: Max height constraint
        if max_height_floors < 2:
            warnings.append(f"⚠️ Max height is very low ({max_height_meters}m = {max_height_floors} floors). May limit solution space.")
        
        # Check 5: Grid resolution
        if buildable_pixels < 20:
            issues.append(f"⛔ Too few buildable pixels ({buildable_pixels}). Minimum recommended: 20 pixels.")
        
        # Check 6: Coverage ratio
        if coverage_ratio < 0.01:
            issues.append(f"⛔ Buildable area is < 1% of grid. Consider using a smaller buffer or larger pixel size.")
        
        # Feature range analysis
        feat_ranges = env_config['feat_ranges']
        feature_labels = env_config['labels']
        
        # Build diagnostic report
        report = []
        
        # Summary section
        if issues:
            report.append(dbc.Alert([
                html.H5("❌ Critical Issues Detected", className="alert-heading"),
                html.P("These issues will likely cause optimization to fail:"),
                html.Ul([html.Li(issue) for issue in issues])
            ], color="danger"))
        
        if warnings:
            report.append(dbc.Alert([
                html.H5("⚠️ Warnings", className="alert-heading"),
                html.P("These issues may reduce optimization quality:"),
                html.Ul([html.Li(warning) for warning in warnings])
            ], color="warning"))
        
        if not issues and not warnings:
            report.append(dbc.Alert([
                html.H5("✅ No Issues Detected", className="alert-heading"),
                html.P("Parcel and constraints appear feasible for optimization.")
            ], color="success"))
        
        # Detailed metrics
        report.append(dbc.Card([
            dbc.CardHeader(html.H5("📊 Parcel Metrics")),
            dbc.CardBody([
                html.Table([
                    html.Tr([html.Td("Buildable Area:"), html.Td(f"{buildable_area_m2:.1f} m²")]),
                    html.Tr([html.Td("Grid Resolution:"), html.Td(f"{grid_res} x {grid_res} pixels")]),
                    html.Tr([html.Td("Pixel Size:"), html.Td(f"{pixel_size} m")]),
                    html.Tr([html.Td("Buildable Pixels:"), html.Td(f"{buildable_pixels}")]),
                    html.Tr([html.Td("Occupied Rows:"), html.Td(f"{rows_occupied}")]),
                    html.Tr([html.Td("Occupied Cols:"), html.Td(f"{cols_occupied}")]),
                    html.Tr([html.Td("Aspect Ratio:"), html.Td(f"{aspect_ratio:.2f}")]),
                    html.Tr([html.Td("Coverage Ratio:"), html.Td(f"{coverage_ratio * 100:.2f}%")]),
                ], className="table table-sm")
            ])
        ], className="mb-3"))
        
        report.append(dbc.Card([
            dbc.CardHeader(html.H5("🔒 Constraints")),
            dbc.CardBody([
                html.Table([
                    html.Tr([html.Td("Max Height:"), html.Td(f"{max_height_meters}m ({max_height_floors} floors, {max_height_voxels} voxels)")]),
                    html.Tr([html.Td("Min Distance:"), html.Td(f"{min_distance_meters}m ({min_distance_pixels:.1f} pixels)" if min_distance_meters > 0 else "None")]),
                ], className="table table-sm")
            ])
        ], className="mb-3"))
        
        report.append(dbc.Card([
            dbc.CardHeader(html.H5("📐 Feature Ranges")),
            dbc.CardBody([
                html.Table([
                    html.Thead(html.Tr([html.Th("Feature"), html.Th("Min"), html.Th("Max")])),
                    html.Tbody([
                        html.Tr([html.Td(label), html.Td(f"{feat_range[0]:.2f}"), html.Td(f"{feat_range[1]:.2f}")])
                        for label, feat_range in zip(feature_labels, feat_ranges)
                    ])
                ], className="table table-sm table-striped")
            ])
        ], className="mb-3"))
        
        # Recommendations
        if issues or warnings:
            recommendations = []
            if buildable_area_m2 < 500:
                recommendations.append("Consider selecting a larger parcel")
            if min_distance_meters > 10:
                recommendations.append("Reduce min distance constraint or select a larger parcel")
            if aspect_ratio > 5:
                recommendations.append("Select a more compact parcel shape")
            if max_height_floors < 3:
                recommendations.append("Increase max height constraint to allow more variation")
            
            if recommendations:
                report.append(dbc.Alert([
                    html.H5("💡 Recommendations", className="alert-heading"),
                    html.Ul([html.Li(rec) for rec in recommendations])
                ], color="info"))
        
        # --- NEW: Test actual solution generation and archive insertion ---
        report.append(html.Hr())
        report.append(html.H4("🧪 Solution Generation Test"))
        report.append(html.P("Testing random solution generation and archive insertion to identify insertion failures..."))
        
        test_results = _test_solution_insertion(env_config, selected_features, hard_constraints)
        
        if test_results['success_rate'] == 0:
            report.append(dbc.Alert([
                html.H5("❌ Critical: NO solutions can be inserted into archive!", className="alert-heading"),
                html.P(f"Tested {test_results['num_tested']} random solutions, NONE were accepted."),
                html.H6("Detailed Breakdown:"),
                html.Ul([
                    html.Li(f"Solutions with negative fitness (constraint violations): {test_results['negative_fitness']}"),
                    html.Li(f"Solutions with zero fitness: {test_results['zero_fitness']}"),
                    html.Li(f"Solutions with positive fitness: {test_results['positive_fitness']}"),
                    html.Li(f"Solutions actually inserted: {test_results['inserted']}"),
                ]),
                html.H6("Root Cause:"),
                html.Pre(test_results['primary_issue'], style={'whiteSpace': 'pre-wrap', 'fontWeight': 'bold'}),
                html.H6("Feature Values from Sample Solutions:"),
                html.Pre(test_results['feature_samples'], style={'fontSize': '0.85em', 'maxHeight': '200px', 'overflow': 'auto'})
            ], color="danger"))
        elif test_results['success_rate'] < 0.1:
            report.append(dbc.Alert([
                html.H5(f"⚠️ Very Low Success Rate: {test_results['success_rate']*100:.1f}%", className="alert-heading"),
                html.P(f"Only {test_results['inserted']} out of {test_results['num_tested']} solutions were inserted."),
                html.H6("Breakdown:"),
                html.Ul([
                    html.Li(f"Constraint violations (negative fitness): {test_results['negative_fitness']}"),
                    html.Li(f"Zero fitness: {test_results['zero_fitness']}"),
                    html.Li(f"Positive fitness: {test_results['positive_fitness']}"),
                    html.Li(f"Actually inserted: {test_results['inserted']}"),
                ]),
                html.P(test_results['primary_issue'], className="font-weight-bold"),
            ], color="warning"))
        else:
            report.append(dbc.Alert([
                html.H5(f"✅ Success Rate: {test_results['success_rate']*100:.1f}%", className="alert-heading"),
                html.P(f"{test_results['inserted']} out of {test_results['num_tested']} solutions were successfully inserted."),
                html.Ul([
                    html.Li(f"Constraint violations: {test_results['negative_fitness']}"),
                    html.Li(f"Valid solutions: {test_results['positive_fitness']}"),
                ]),
            ], color="success"))
        
        # --- Fitness Calculation Visualization ---
        report.append(html.Hr())
        report.append(html.H4("🔬 Fitness Calculation Visualization"))
        report.append(html.P("Step-by-step breakdown of how fitness (wind porosity) is calculated for 3 sample solutions:"))
        
        for idx, viz in enumerate(test_results['fitness_visualizations']):
            stats = viz['stats']
            report.append(dbc.Card([
                dbc.CardHeader(html.H5(f"Sample Solution {idx+1}")),
                dbc.CardBody([
                    # Statistics summary
                    dbc.Row([
                        dbc.Col([
                            html.H6("Heightmap Stats:"),
                            html.Ul([
                                html.Li(f"Height range: {stats['heightmap_stats']['min']:.1f} - {stats['heightmap_stats']['max']:.1f} floors"),
                                html.Li(f"Mean height: {stats['heightmap_stats']['mean']:.2f} floors"),
                                html.Li(f"Occupied cells: {stats['heightmap_stats']['non_zero']}"),
                            ])
                        ], md=4),
                        dbc.Col([
                            html.H6("3D Building Stats:"),
                            html.Ul([
                                html.Li(f"Design voxels: {stats['combined_3d_stats']['design_voxels']}"),
                                html.Li(f"Existing voxels: {stats['combined_3d_stats']['existing_voxels']}"),
                                html.Li(f"Total voxels: {stats['combined_3d_stats']['total_voxels']}"),
                            ])
                        ], md=4),
                        dbc.Col([
                            html.H6("Wind Analysis:"),
                            html.Ul([
                                html.Li(f"Wind direction: {stats['wind_stats']['rotation_angle_simple']}°"),
                                html.Li(f"Open paths: {stats['wind_stats']['open_paths']} / {stats['wind_stats']['total_paths']}"),
                                html.Li(f"Porosity: {stats['wind_stats']['porosity']:.4f}"),
                            ])
                        ], md=4),
                    ]),
                    html.Hr(),
                    # Fitness comparison
                    dbc.Row([
                        dbc.Col([
                            dbc.Alert([
                                html.H6("🏙️ Simple Wind Porosity", className="alert-heading"),
                                html.P(f"Fitness: {stats['wind_stats']['fitness_simple_porosity']:.4f}", 
                                       style={'fontSize': '1.2em', 'fontWeight': 'bold',
                                              'color': 'red' if stats['wind_stats']['fitness_simple_porosity'] == 0 else 'green'})
                            ], color="light"),
                        ], md=6),
                        dbc.Col([
                            dbc.Alert([
                                html.H6("🌬️ Street Canyon Ventilation", className="alert-heading"),
                                html.P(f"Fitness: {stats['wind_stats']['fitness_street_canyon']:.4f}", 
                                       style={'fontSize': '1.2em', 'fontWeight': 'bold',
                                              'color': 'red' if stats['wind_stats']['fitness_street_canyon'] < 0.2 else 'green'})
                            ], color="info"),
                        ], md=6),
                    ]),
                    html.Hr(),
                    # === Common Visualizations (Steps 1-3) ===
                    html.H6("📊 Common Steps (Both Methods):"),
                    dbc.Row([
                        dbc.Col(dcc.Graph(figure=viz['fig1'], config={'displayModeBar': False}), md=4),
                        dbc.Col(dcc.Graph(figure=viz['fig2'], config={'displayModeBar': False}), md=4),
                        dbc.Col(dcc.Graph(figure=viz['fig3'], config={'displayModeBar': False}), md=4),
                    ]),
                    html.P([
                        html.B("Step 1: "), "Generated building heights. ",
                        html.B("Step 2: "), "Combined with existing buildings. ",
                        html.B("Step 3: "), f"Rotated {stats['wind_stats']['rotation_angle_simple']}° to align with wind direction."
                    ], className="mt-2", style={'fontSize': '0.9em'}),
                    
                    html.Hr(),
                    
                    # === Simple Wind Porosity Visualization ===
                    html.H6("🏙️ Simple Wind Porosity Method:"),
                    dbc.Row([
                        dbc.Col(dcc.Graph(figure=viz['fig4'], config={'displayModeBar': False}), md=4),
                        dbc.Col(dcc.Graph(figure=viz['fig4b'], config={'displayModeBar': False}), md=4),
                        dbc.Col(dcc.Graph(figure=viz['fig4c'], config={'displayModeBar': False}), md=4),
                    ]),
                    html.P([
                        html.B("Step 4a: "), "Building footprints (top view). ",
                        html.B("Step 4b: "), "Top view colored by wind openness (vertical stripes show openness at each X position). ",
                        html.B("Step 4c: "), "Side view showing which (X,Z) positions have unobstructed wind paths. ",
                        html.B("⚠️ Note: "), "Red areas in 4c may include blocking from existing buildings, not just your design! ",
                        html.Br(),
                        html.Span(f"Result: {stats['wind_stats']['open_paths']} / {stats['wind_stats']['total_paths']} paths completely open. ", 
                                 style={'color': 'red' if stats['wind_stats']['fitness_simple_porosity'] == 0 else 'green'}),
                        html.B(f"Fitness = {stats['wind_stats']['fitness_simple_porosity']:.4f}")
                    ], className="mt-2", style={'fontSize': '0.9em'}),
                    
                    html.Hr(),
                    
                    # === Street Canyon Ventilation Visualization ===
                    html.H6("🌬️ Street Canyon Ventilation Method (4 Components):"),
                    dbc.Row([
                        dbc.Col([
                            dcc.Graph(figure=viz['fig5'], config={'displayModeBar': False}),
                            html.Small([
                                html.B("Ground-level Canyons (35%): "),
                                f"{stats['street_canyon_components']['street_canyons']:.3f}"
                            ], style={'display': 'block', 'textAlign': 'center'})
                        ], md=3),
                        dbc.Col([
                            dcc.Graph(figure=viz['fig6'], config={'displayModeBar': False}),
                            html.Small([
                                html.B("Lateral Ventilation (25%): "),
                                f"{stats['street_canyon_components']['lateral_ventilation']:.3f}"
                            ], style={'display': 'block', 'textAlign': 'center'})
                        ], md=3),
                        dbc.Col([
                            dcc.Graph(figure=viz['fig7'], config={'displayModeBar': False}),
                            html.Small([
                                html.B("Height Variation (15%): "),
                                f"{stats['street_canyon_components']['height_variation']:.3f}"
                            ], style={'display': 'block', 'textAlign': 'center'})
                        ], md=3),
                        dbc.Col([
                            dcc.Graph(figure=viz['fig8'], config={'displayModeBar': False}),
                            html.Small([
                                html.B("Partial Penetration (25%): "),
                                f"{stats['street_canyon_components']['partial_penetration']:.3f}"
                            ], style={'display': 'block', 'textAlign': 'center'})
                        ], md=3),
                    ]),
                    html.P([
                        html.B("Components Explained: "),
                        html.Br(),
                        "• ", html.B("Ground Canyons"), " (green): Horizontal corridors at street level. ",
                        html.Br(),
                        "• ", html.B("Lateral Ventilation"), " (blue): Cross-wind flow opportunities. ",
                        html.Br(),
                        "• ", html.B("Height Variation"), " (purple): Building height diversity creates turbulence. ",
                        html.Br(),
                        "• ", html.B("Partial Penetration"), " (orange): Weighted wind penetration through gaps. ",
                        html.Br(),
                        html.B(f"Combined Fitness = {stats['wind_stats']['fitness_street_canyon']:.4f}"),
                        f" = (0.35 × {stats['street_canyon_components']['street_canyons']:.3f}) + ",
                        f"(0.25 × {stats['street_canyon_components']['lateral_ventilation']:.3f}) + ",
                        f"(0.15 × {stats['street_canyon_components']['height_variation']:.3f}) + ",
                        f"(0.25 × {stats['street_canyon_components']['partial_penetration']:.3f})"
                    ], className="mt-2", style={'fontSize': '0.9em'}),
                    html.Div([
                        html.B("Problem: ", style={'color': 'red'}),
                        "If Step 4b shows all red/yellow (no green), it means there are NO completely unobstructed horizontal wind paths through the site, resulting in zero fitness."
                    ] if stats['wind_stats']['fitness_simple_porosity'] == 0 else [], className="alert alert-danger mt-2")
                ])
            ], className="mb-3"))
        
        # Add recommendation based on fitness comparison
        if all(viz['stats']['wind_stats']['fitness_simple_porosity'] == 0 for viz in test_results['fitness_visualizations']):
            # Check if Street Canyon objective would help
            street_canyon_helps = any(viz['stats']['wind_stats']['fitness_street_canyon'] > 0.1 for viz in test_results['fitness_visualizations'])
            
            if street_canyon_helps:
                report.append(dbc.Alert([
                    html.H5("✅ Solution Found: Use Street Canyon Objective", className="alert-heading"),
                    html.P("Simple Wind Porosity returns ZERO for all solutions, but Street Canyon Ventilation provides a gradient!"),
                    html.Ul([
                        html.Li("Simple Porosity requires completely open vertical passages (none exist here)"),
                        html.Li("Street Canyon detects horizontal corridors and lateral ventilation"),
                        html.Li(f"Average Street Canyon fitness: {np.mean([v['stats']['wind_stats']['fitness_street_canyon'] for v in test_results['fitness_visualizations']]):.3f}"),
                    ]),
                    html.H6("Recommendation:", className="mt-3"),
                    html.P([
                        "Go to ", html.B("Step 2 (Constraints)"), " → Scroll to ", html.B("Optimization Criteria"), 
                        " → Select ", html.B("🌬️ Street Canyon Ventilation")
                    ], style={'fontSize': '1.1em'}),
                ], color="success"))
            else:
                report.append(dbc.Alert([
                    html.H5("🚨 Critical Issue Identified", className="alert-heading"),
                    html.P("All sample solutions have ZERO fitness on BOTH objectives because:"),
                    html.Ul([
                        html.Li("Buildings (design + existing) completely block horizontal wind paths in the current direction"),
                        html.Li("No completely unobstructed horizontal passages exist through the entire site depth"),
                        html.Li("Step 4b shows NO green areas (all paths are blocked somewhere along their length)"),
                    ]),
                    html.H6("Solutions:"),
                    html.Ol([
                        html.Li([html.B("Change objective function"), " - Instead of wind porosity, optimize for building coverage, height diversity, or gross floor area"]),
                        html.Li([html.B("Try different wind direction"), f" - Current: {test_results['fitness_visualizations'][0]['stats']['wind_stats']['rotation_angle_simple']}°, try 0°, 90°, 180°, 270°"]),
                        html.Li([html.B("Reduce existing building density"), " - If env is too dense, no design can create porosity"]),
                        html.Li([html.B("Modify fitness calculation"), " - Use partial blockage or weighted porosity instead of strict open paths"]),
                    ])
                ], color="warning"))
        
        return html.Div(report)
        
    except Exception as e:
        return dbc.Alert([
            html.H5("❌ Error Running Diagnostic", className="alert-heading"),
            html.P(f"Error: {str(e)}"),
            html.Pre(str(e.__class__.__name__))
        ], color="danger")
