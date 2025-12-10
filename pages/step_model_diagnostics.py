#!/usr/bin/env python3
"""
Model Diagnostics Page

Visualize and compare objective functions (porosity, street_canyon, SVGP, U-Net)
on archetypical urban designs.
"""

from dash import dcc, html, Input, Output, State, callback, no_update
import dash_bootstrap_components as dbc
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from scipy.stats import pearsonr
import torch

from backend.translation import T
from backend.archetypes import (
    get_all_archetypes, 
    get_archetype_list,
    get_archetype_description
)
from backend.evaluation import (
    _create_3d_from_heightmap_jit,
    _compute_fitness_jit,
    _compute_fitness_street_canyon_jit
)
from backend.model_evaluator import create_evaluator
from backend.config import DOMAIN_CONFIG


def layout(lang='DE'):
    """Create model diagnostics page layout."""
    # Pre-render archetypes to avoid re-rendering callbacks
    # get_all_archetypes now returns (genome, heightmap) tuples
    archetypes = get_all_archetypes()
    archetype_names = get_archetype_list()
    
    # Create gallery rows
    gallery_rows = []
    for i in range(0, len(archetype_names), 3):
        cols = []
        for j in range(3):
            if i + j < len(archetype_names):
                name = archetype_names[i + j]
                genome, heightmap = archetypes[name]
                
                fig = create_3d_plot(heightmap, T[lang][f'ARCHETYPE_{name.upper()}'])
                
                cols.append(
                    dbc.Col([
                        dcc.Graph(
                            figure=fig, 
                            config={
                                'displayModeBar': False, 
                                'staticPlot': True,  # Make it completely static
                                'responsive': False,  # Disable responsive resizing
                                'autosizable': False,  # Disable autosize
                                'displaylogo': False
                            },
                            id=f'archetype-plot-{name}',
                            style={'width': '100%', 'height': '280px'}  # Fixed size
                        ),
                        html.P(
                            get_archetype_description(name, lang),
                            className='text-center small text-muted'
                        )
                    ], md=4)
                )
        
        gallery_rows.append(dbc.Row(cols, className='mb-3'))
    
    return dbc.Container([
        # Header with back button
        dbc.Row([
            dbc.Col([
                dbc.Button(
                    f"← {T[lang]['MODEL_DIAG_BACK_TO_STEP1']}",
                    id='back-to-step1-btn',
                    color='secondary',
                    size='sm',
                    className='mb-3'
                )
            ], width=3),
            dbc.Col([
                html.H2(T[lang]['MODEL_DIAG_TITLE'], className='text-center')
            ], width=6),
            dbc.Col(width=3)
        ], className='mb-4'),
        
        # Archetype Gallery
        dbc.Card([
            dbc.CardHeader(html.H4(T[lang]['MODEL_DIAG_GALLERY_HEADER'])),
            dbc.CardBody([
                html.P(T[lang]['MODEL_DIAG_GALLERY_INFO'], className='text-muted'),
                html.Div(gallery_rows)
            ])
        ], className='mb-4'),
        
        # Evaluation Button
        dbc.Row([
            dbc.Col([
                dbc.Button(
                    T[lang]['MODEL_DIAG_RUN_BTN'],
                    id='run-evaluations-btn',
                    color='primary',
                    size='lg',
                    className='w-100'
                )
            ], md={'size': 6, 'offset': 3})
        ], className='mb-4'),
        
        # Loading indicator
        dcc.Loading(
            id='evaluation-loading',
            type='default',
            children=html.Div(id='evaluation-status')
        ),
        
        # Results section (hidden until evaluation completes)
        html.Div(id='results-section', children=[
            # Ranking Table
            dbc.Card([
                dbc.CardHeader(html.H4(T[lang]['MODEL_DIAG_RANKING'])),
                dbc.CardBody([
                    html.P(T[lang]['MODEL_DIAG_RANKING_INFO'], className='text-muted'),
                    html.Div(id='ranking-table')
                ])
            ], className='mb-4'),
            
            # Correlation Matrix
            dbc.Card([
                dbc.CardHeader(html.H4(T[lang]['MODEL_DIAG_CORRELATION'])),
                dbc.CardBody([
                    html.P(T[lang]['MODEL_DIAG_CORRELATION_INFO'], className='text-muted'),
                    dcc.Graph(id='correlation-matrix')
                ])
            ], className='mb-4'),
            
            # Flow Visualization
            dbc.Card([
                dbc.CardHeader(html.H4(T[lang]['MODEL_DIAG_FLOW_VIZ'])),
                dbc.CardBody([
                    html.P(T[lang]['MODEL_DIAG_FLOW_VIZ_INFO'], className='text-muted'),
                    dbc.Row([
                        dbc.Col([
                            dbc.Label(T[lang]['MODEL_DIAG_SELECT_ARCH']),
                            dcc.Dropdown(
                                id='flow-archetype-dropdown',
                                options=[],
                                value=None,
                                clearable=False
                            )
                        ], md=6),
                        dbc.Col([
                            dbc.Label(T[lang]['MODEL_DIAG_STREAMLINE_DENSITY']),
                            dcc.Slider(
                                id='streamline-density-slider',
                                min=5,
                                max=20,
                                step=1,
                                value=10,
                                marks={5: '5', 10: '10', 15: '15', 20: '20'},
                                tooltip={'placement': 'bottom', 'always_visible': True}
                            )
                        ], md=6)
                    ], className='mb-3'),
                    dbc.Row([
                        dbc.Col([
                            dcc.Loading(dcc.Graph(id='velocity-heatmap'))
                        ], md=6),
                        dbc.Col([
                            dcc.Loading(dcc.Graph(id='streamlines-plot'))
                        ], md=6)
                    ])
                ])
            ], className='mb-4')
        ], style={'display': 'none'}),
        
        # Hidden store for evaluation results
        dcc.Store(id='diagnostics-results-store')
    ], fluid=True)


def create_3d_plot(heightmap: np.ndarray, title: str) -> go.Figure:
    """Create small plot for archetype preview - using 2D heatmap for stability."""
    pixel_size = 3.0
    rows, cols = heightmap.shape
    
    x = np.arange(cols) * pixel_size
    y = np.arange(rows) * pixel_size
    
    # Use a 2D heatmap instead of 3D surface to avoid rendering issues
    fig = go.Figure(data=[go.Heatmap(
        z=heightmap,
        x=x,
        y=y,
        colorscale='Viridis',
        showscale=False,
        hoverinfo='skip'
    )])
    
    fig.update_layout(
        title=dict(text=title, font=dict(size=12)),
        xaxis=dict(title='', showgrid=False, showticklabels=False, fixedrange=True),
        yaxis=dict(title='', showgrid=False, showticklabels=False, fixedrange=True, scaleanchor='x'),
        height=280,
        margin=dict(l=0, r=0, t=30, b=0),
        uirevision=title,
        hovermode=False,
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)'
    )
    
    return fig


@callback(
    Output('diagnostics-results-store', 'data'),
    Output('evaluation-status', 'children'),
    Output('results-section', 'style'),
    Input('run-evaluations-btn', 'n_clicks'),
    State('language-store', 'data'),
    prevent_initial_call=True
)
def run_evaluations(n_clicks, lang):
    """Run all objective functions on all archetypes."""
    if lang is None:
        lang = 'DE'
    
    if n_clicks is None:
        return no_update
    
    try:
        # Get archetypes (now returns (genome, heightmap) tuples)
        archetypes = get_all_archetypes()
        archetype_names = get_archetype_list()
        
        # Wind direction (from left = 270°)
        wind_direction = 270.0
        
        # Storage for results
        results = {
            'archetypes': archetype_names,
            'genomes': {},
            'heightmaps': {},
            'porosity': [],
            'street_canyon': [],
            'svgp': [],
            'unet': [],
            'unet_flow_fields': {}
        }
        
        # Evaluate each archetype
        for name in archetype_names:
            genome, heightmap = archetypes[name]
            results['genomes'][name] = genome.tolist()
            results['heightmaps'][name] = heightmap.tolist()
            
            # Convert to 3D for JIT functions
            max_height = int(np.max(heightmap)) if np.max(heightmap) > 0 else 1
            heightmap_3d = _create_3d_from_heightmap_jit(heightmap, max_height)
            
            # Porosity
            porosity_score = _compute_fitness_jit(heightmap_3d, wind_direction)
            results['porosity'].append(float(porosity_score))
            
            # Street Canyon
            canyon_score = _compute_fitness_street_canyon_jit(heightmap_3d, wind_direction)
            results['street_canyon'].append(float(canyon_score))
            
            # SVGP - Only if model exists
            try:
                device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
                svgp_eval = create_evaluator('svgp', parcel_size=81, device=device)
                
                # Use the ACTUAL genome from the archetype!
                parcel_sizes = np.array([27.0])  # 27 bins = 81m
                
                svgp_result = svgp_eval.evaluate(genome.reshape(1, -1), parcel_sizes)
                svgp_score = float(svgp_result['objectives'][0])
                results['svgp'].append(svgp_score)
            except Exception as e:
                print(f"SVGP evaluation error for {name}: {e}")
                results['svgp'].append(None)
            
            # U-Net - Only if model exists
            try:
                device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
                unet_eval = create_evaluator('unet', parcel_size=81, device=device)
                
                # Use the ACTUAL genome from the archetype!
                parcel_sizes = np.array([27.0])  # 27 bins = 81m
                
                unet_result = unet_eval.evaluate(genome.reshape(1, -1), parcel_sizes)
                unet_score = float(unet_result['objectives'][0])
                results['unet'].append(unet_score)
                
                # Get ACTUAL flow field from U-Net predictions
                # The evaluate() method already runs the model - we need access to intermediate outputs
                # For now, let's access the model's internal state by re-running evaluation
                # and extracting the velocity fields from the ROI region
                
                # Re-express genome to get heightmap in 66x94 grid (what U-Net expects)
                from backend.fast_encoding import NumbaFastEncoding
                encoding_full = NumbaFastEncoding(parcel_size=81)
                X_27 = encoding_full.express_batch(genome.reshape(1, -1))[0]  # 27x27
                
                # Create 66x94 grid with parcel in center (matching U-Net's ROI logic)
                X_full = np.zeros((1, 3, 66, 94), dtype=np.float32)
                start_row = (66 - 27) // 2
                start_col = (94 - 27) // 2
                X_full[0, 1, start_row:start_row+27, start_col:start_col+27] = X_27
                
                # Run model
                dtype = torch.float16 if device.type == 'cuda' else torch.float32
                X_torch = torch.tensor(X_full, dtype=dtype, device=device)
                
                with torch.no_grad():
                    Y_pred = unet_eval.model(X_torch)  # Shape: (1, 6, 66, 94)
                
                Y_pred = Y_pred.float().cpu().numpy()
                
                # Extract uq and vq from ROI region and denormalize
                uq_full = Y_pred[0, 2, :, :] * unet_eval.uq_std + unet_eval.uq_mean  # cm/s
                vq_full = Y_pred[0, 3, :, :] * unet_eval.vq_std + unet_eval.vq_mean  # cm/s
                
                # Extract ROI (27x27 region)
                uq_roi = uq_full[start_row:start_row+27, start_col:start_col+27]
                vq_roi = vq_full[start_row:start_row+27, start_col:start_col+27]
                
                # Convert cm/s to m/s
                flow_u = uq_roi / 100.0
                flow_v = vq_roi / 100.0
                
                flow_field = np.stack([flow_u, flow_v], axis=-1)  # Shape: (27, 27, 2)
                results['unet_flow_fields'][name] = flow_field.tolist()
                
            except Exception as e:
                print(f"U-Net evaluation error for {name}: {e}")
                import traceback
                traceback.print_exc()
                results['unet'].append(None)
        
        return (
            results,
            dbc.Alert(T[lang]['MODEL_DIAG_EVAL_COMPLETE'], color='success'),
            {'display': 'block'}
        )
    
    except Exception as e:
        return (
            None,
            dbc.Alert(f"{T[lang]['MODEL_DIAG_EVAL_ERROR']}: {str(e)}", color='danger'),
            {'display': 'none'}
        )


@callback(
    Output('ranking-table', 'children'),
    Input('diagnostics-results-store', 'data'),
    State('language-store', 'data')
)
def update_ranking_table(results, lang):
    """Create ranking table showing all scores."""
    if lang is None:
        lang = 'DE'
    
    if not results:
        return html.Div()
    
    # Create DataFrame
    df = pd.DataFrame({
        T[lang]['MODEL_DIAG_TABLE_ARCHETYPE']: [
            T[lang][f'ARCHETYPE_{name.upper()}'] for name in results['archetypes']
        ],
        T[lang]['MODEL_DIAG_TABLE_POROSITY']: results['porosity'],
        T[lang]['MODEL_DIAG_TABLE_STREET_CANYON']: results['street_canyon'],
        T[lang]['MODEL_DIAG_TABLE_SVGP']: results['svgp'],
        T[lang]['MODEL_DIAG_TABLE_UNET']: results['unet']
    })
    
    # Format numbers
    for col in df.columns[1:]:
        df[col] = df[col].apply(lambda x: f"{x:.3f}" if x is not None else "N/A")
    
    # Create Bootstrap table
    table = dbc.Table.from_dataframe(
        df,
        striped=True,
        bordered=True,
        hover=True,
        responsive=True,
        class_name='text-center'
    )
    
    return table


@callback(
    Output('correlation-matrix', 'figure'),
    Input('diagnostics-results-store', 'data'),
    State('language-store', 'data')
)
def update_correlation_matrix(results, lang):
    """Compute and visualize correlation matrix."""
    if lang is None:
        lang = 'DE'
    
    if not results:
        return go.Figure()
    
    # Build data matrix (exclude None values)
    data = {
        T[lang]['MODEL_DIAG_TABLE_POROSITY']: results['porosity'],
        T[lang]['MODEL_DIAG_TABLE_STREET_CANYON']: results['street_canyon'],
        T[lang]['MODEL_DIAG_TABLE_SVGP']: results['svgp'],
        T[lang]['MODEL_DIAG_TABLE_UNET']: results['unet']
    }
    
    df = pd.DataFrame(data)
    
    # Compute correlation
    corr_matrix = df.corr()
    
    # Create heatmap
    fig = go.Figure(data=go.Heatmap(
        z=corr_matrix.values,
        x=corr_matrix.columns,
        y=corr_matrix.columns,
        colorscale='RdBu',
        zmid=0,
        zmin=-1,
        zmax=1,
        text=corr_matrix.values,
        texttemplate='%{text:.2f}',
        textfont={"size": 14},
        colorbar=dict(title=T[lang]['MODEL_DIAG_CORRELATION_LABEL'])
    ))
    
    fig.update_layout(
        title=T[lang]['MODEL_DIAG_CORRELATION'],
        xaxis_title='',
        yaxis_title='',
        height=500
    )
    
    return fig


@callback(
    Output('flow-archetype-dropdown', 'options'),
    Output('flow-archetype-dropdown', 'value'),
    Input('diagnostics-results-store', 'data'),
    State('language-store', 'data')
)
def update_flow_dropdown(results, lang):
    """Populate flow visualization dropdown."""
    if lang is None:
        lang = 'DE'
    
    # Always show all archetypes, even before evaluation
    archetype_names = get_archetype_list()
    
    if not results or not results.get('unet_flow_fields'):
        # Show all archetypes but disabled if no results yet
        options = [
            {'label': T[lang][f'ARCHETYPE_{name.upper()}'], 'value': name}
            for name in archetype_names
        ]
        return options, options[0]['value'] if options else None
    
    # After evaluation, only show archetypes with flow fields
    options = [
        {'label': T[lang][f'ARCHETYPE_{name.upper()}'], 'value': name}
        for name in results['archetypes']
        if name in results['unet_flow_fields']
    ]
    
    value = options[0]['value'] if options else None
    
    return options, value


@callback(
    Output('velocity-heatmap', 'figure'),
    Output('streamlines-plot', 'figure'),
    Input('flow-archetype-dropdown', 'value'),
    Input('streamline-density-slider', 'value'),
    State('diagnostics-results-store', 'data'),
    State('language-store', 'data')
)
def update_flow_visualizations(archetype_name, density, results, lang):
    """Create velocity heatmap and streamlines."""
    if lang is None:
        lang = 'DE'
    
    if not results or not archetype_name:
        return go.Figure(), go.Figure()
    
    # Get flow field (u, v components)
    flow_field = np.array(results['unet_flow_fields'].get(archetype_name))
    heightmap = np.array(results['heightmaps'][archetype_name])
    
    if flow_field is None or flow_field.size == 0:
        return go.Figure(), go.Figure()
    
    # Extract u, v components (assuming shape is [27, 27, 2])
    u = flow_field[:, :, 0]
    v = flow_field[:, :, 1]
    
    # Compute velocity magnitude
    velocity_mag = np.sqrt(u**2 + v**2)
    
    # Create coordinate arrays
    pixel_size = 3.0
    x = np.arange(27) * pixel_size
    y = np.arange(27) * pixel_size
    
    # Velocity heatmap with building footprint overlay
    fig_heatmap = go.Figure()
    
    # Add velocity heatmap with fixed color range
    fig_heatmap.add_trace(go.Heatmap(
        z=velocity_mag,
        x=x,
        y=y,
        colorscale='Jet',
        zmin=-1.3,
        zmax=1.3,
        colorbar=dict(title=T[lang]['MODEL_DIAG_VELOCITY_MS'])
    ))
    
    # Overlay building footprints as contours
    fig_heatmap.add_trace(go.Contour(
        z=heightmap,
        x=x,
        y=y,
        contours=dict(
            start=0.1,
            size=3,
            coloring='lines'
        ),
        line=dict(color='black', width=2),
        showscale=False,
        name='Buildings'
    ))
    
    fig_heatmap.update_layout(
        title=T[lang]['MODEL_DIAG_VELOCITY_HEATMAP'],
        xaxis_title='X (m)',
        yaxis_title='Y (m)',
        height=400
    )
    
    # Streamlines plot
    fig_streamlines = go.Figure()
    
    # Calculate proper streamlines using integration
    # Sample starting points for streamlines
    step = max(1, 27 // density)
    y_starts = np.arange(0, 27, step)
    x_start = 2  # Start streamlines from left edge
    
    # Create meshgrid for interpolation
    X, Y = np.meshgrid(np.arange(27), np.arange(27))
    
    def integrate_streamline(x0, y0, max_steps=200):
        """Integrate streamline from starting point using RK2.
        
        Args:
            x0, y0: Starting position in grid coordinates (x is column, y is row)
        """
        from scipy.interpolate import RegularGridInterpolator
        
        # Create interpolators for u and v
        # u and v have shape (27, 27) where first index is row (y), second is column (x)
        # RegularGridInterpolator expects points as (row, col) = (y, x)
        y_coords = np.arange(27)
        x_coords = np.arange(27)
        u_interp = RegularGridInterpolator((y_coords, x_coords), u, 
                                          bounds_error=False, fill_value=0)
        v_interp = RegularGridInterpolator((y_coords, x_coords), v,
                                          bounds_error=False, fill_value=0)
        
        points = [[x0, y0]]
        x, y = x0, y0
        dt = 0.3  # Step size in grid units
        
        for _ in range(max_steps):
            # RK2 integration (midpoint method)
            # Query interpolator with (y, x) order
            u1 = u_interp([y, x])[0]
            v1 = v_interp([y, x])[0]
            
            # Update positions: dx/dt = u, dy/dt = v
            x_mid = x + 0.5 * dt * u1
            y_mid = y + 0.5 * dt * v1
            
            u2 = u_interp([y_mid, x_mid])[0]
            v2 = v_interp([y_mid, x_mid])[0]
            
            x_new = x + dt * u2
            y_new = y + dt * v2
            
            # Check if out of bounds or velocity too small
            if (x_new < 0 or x_new >= 27 or y_new < 0 or y_new >= 27 or
                np.sqrt(u2**2 + v2**2) < 0.01):
                break
            
            # Check if hit a building
            # heightmap[row, col] = heightmap[y, x]
            ix, iy = int(np.round(x_new)), int(np.round(y_new))
            if 0 <= ix < 27 and 0 <= iy < 27 and heightmap[iy, ix] > 0:
                break
            
            points.append([x_new, y_new])
            x, y = x_new, y_new
        
        return np.array(points)
    
    # Generate streamlines
    colors = px.colors.sample_colorscale('Viridis', np.linspace(0, 1, len(y_starts)))
    
    for idx, y_start in enumerate(y_starts):
        try:
            points = integrate_streamline(x_start, y_start)
            if len(points) > 1:
                # Convert grid coordinates to meters
                x_line = points[:, 0] * pixel_size
                y_line = points[:, 1] * pixel_size
                
                fig_streamlines.add_trace(go.Scatter(
                    x=x_line,
                    y=y_line,
                    mode='lines',
                    line=dict(color=colors[idx], width=2),
                    showlegend=False,
                    hoverinfo='skip'
                ))
                
                # Add arrowhead at the end
                if len(points) > 2:
                    # Direction from second-to-last to last point
                    dx = points[-1, 0] - points[-2, 0]
                    dy = points[-1, 1] - points[-2, 1]
                    angle = np.degrees(np.arctan2(dy, dx))
                    
                    fig_streamlines.add_trace(go.Scatter(
                        x=[x_line[-1]],
                        y=[y_line[-1]],
                        mode='markers',
                        marker=dict(
                            symbol='arrow',
                            size=10,
                            color=colors[idx],
                            angle=angle,
                            angleref='previous'
                        ),
                        showlegend=False,
                        hoverinfo='skip'
                    ))
        except Exception as e:
            print(f"Error integrating streamline at y={y_start}: {e}")
            continue
    
    # Add building footprints
    fig_streamlines.add_trace(go.Contour(
        z=heightmap,
        x=x,
        y=y,
        contours=dict(
            start=0.1,
            size=3,
            coloring='lines'
        ),
        line=dict(color='black', width=2),
        showscale=False,
        name='Buildings'
    ))
    
    fig_streamlines.update_layout(
        title=T[lang]['MODEL_DIAG_STREAMLINES'],
        xaxis_title='X (m)',
        yaxis_title='Y (m)',
        height=400
    )
    
    return fig_heatmap, fig_streamlines


# Navigation callback
@callback(
    Output('url', 'pathname', allow_duplicate=True),
    Input('back-to-step1-btn', 'n_clicks'),
    prevent_initial_call=True
)
def navigate_back(n_clicks):
    """Navigate back to step 1."""
    if n_clicks:
        return '/step1'
    return no_update
