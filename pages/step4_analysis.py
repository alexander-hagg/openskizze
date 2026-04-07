from dash import dcc, html, Input, Output, State, callback, ALL, no_update
import dash_bootstrap_components as dbc
from backend.translation import T
import pickle
import os
import numpy as np
import pandas as pd
import plotly.express as px
import logging

logger = logging.getLogger(__name__)

def layout(lang='DE'):
    from backend.translation import create_breadcrumb
    return dbc.Container([
        create_breadcrumb(4, lang),
        html.H2(T[lang].get('STEP4_TITLE', 'Results Analysis')),
        
        # TOP ROW: Compact horizontal filtering + axis selection
        dbc.Row([
            dbc.Col([
                html.Div([
                    html.Strong("Filter" if lang == 'EN' else "Filter", className="me-2"),
                    html.Div(id='filter-statistics', className="d-inline"),
                ], className="d-flex align-items-center mb-2"),
                html.Div(id='filter-sliders-container'),
            ], md=8),
            dbc.Col([
                dbc.Row([
                    dbc.Col([
                        dbc.Label(T[lang].get('STEP3_X_AXIS_LABEL', 'X-Axis'), className="small"),
                        dcc.Dropdown(id='x-axis-dropdown', className="small"),
                    ], md=6),
                    dbc.Col([
                        dbc.Label(T[lang].get('STEP3_Y_AXIS_LABEL', 'Y-Axis'), className="small"),
                        dcc.Dropdown(id='y-axis-dropdown', className="small"),
                    ], md=6),
                ]),
            ], md=4),
        ], className="mb-3 p-2 bg-light rounded"),
        
        # MAIN: 3-column layout for visualizations
        dbc.Row([
            # Column 1: Archive visualizations (solutions + heatmap stacked)
            dbc.Col([
                dbc.Card(dbc.CardBody([
                    html.H6(T[lang].get('STEP3_SOLUTION_GRID_HEADER', 'Solution Archive')),
                    dcc.Loading(html.Div(id='solution-archive-grid'))
                ]), className="mb-2"),
                dbc.Card(dbc.CardBody([
                    html.H6(T[lang].get('STEP3_ARCHIVE_HEATMAP_TITLE', 'Archive Heatmap')),
                    dcc.Loading(dcc.Graph(id='archive-heatmap', config={'displayModeBar': False}))
                ])),
            ], md=4),
            
            # Column 2: Parallel Coordinates (row 1) + Correlation (row 2)
            dbc.Col([
                dbc.Card(dbc.CardBody([
                    html.H6(T[lang].get('STEP3_PARALLEL_COORDS_HEADER', 'Parallel Coordinates')),
                    dcc.Loading(dcc.Graph(id='parallel-coords-plot', config={'displayModeBar': False}))
                ]), className="mb-2"),
                dbc.Card(dbc.CardBody([
                    html.H6(T[lang]['STEP5_CORRELATION_HEADER']),
                    dcc.Loading(dcc.Graph(id='correlation-heatmap', config={'displayModeBar': False}))
                ])),
            ], md=4),
            
            # Column 3: Feature vs Objective analysis (full height, no scroll)
            dbc.Col([
                dbc.Card(dbc.CardBody([
                    html.H6(T[lang]['STEP4_FEATURE_VS_OBJECTIVE_HEADER']),
                    dcc.Loading(html.Div(id='feature-objective-plots-container'))
                ]), className="h-100"),
            ], md=4),
        ], className="mb-4"),
        
        # Hidden placeholder for random sample (removed from UI)
        html.Div(id='random-sample-preview', style={'display': 'none'}),
        
        # Uncertainty section placeholder (kept for callback targets)
        html.Div(id='uncertainty-heatmap-container', children=[
            dbc.Checklist(id="show-uncertainty-toggle", value=[], style={'display': 'none'}),
            html.Div(id='uncertainty-heatmap-display'),
        ], style={'display': 'none'}),
        
    ], fluid=True)


# --- Populate axis dropdowns from results ---
@callback(
    Output('x-axis-dropdown', 'options'),
    Output('y-axis-dropdown', 'options'),
    Output('x-axis-dropdown', 'value'),
    Output('y-axis-dropdown', 'value'),
    Input('results-store', 'data'),
    Input('language-store', 'data'),
)
def populate_axis_dropdowns(results_data, language):
    from backend.translation import translate_feature_labels
    
    # Get feature indices from final results only
    if not results_data or 'selected_features_indices' not in results_data:
        return [], [], None, None
    
    feature_indices = results_data['selected_features_indices']
    feature_set = results_data.get('feature_set', 'consolidated')
    
    # Get current language (default to 'DE')
    lang = language if language else 'DE'
    
    # Translate feature labels based on current language and feature set
    labels = translate_feature_labels(feature_indices, lang, feature_set)
    
    options = [{'label': label, 'value': i} for i, label in enumerate(labels)]
    val1 = 0 if len(options) > 0 else None
    val2 = 1 if len(options) > 1 else None
    return options, options, val1, val2


@callback(
    Output('filter-sliders-container', 'children'),
    Input('results-store', 'data'),
    State('language-store', 'data'),
)
def create_filter_sliders(results_data, lang):
    """Create range sliders for each feature to filter solutions"""
    if lang is None:
        lang = 'DE'
    
    if not results_data or not results_data.get('full_results_path'):
        return html.Div("No results available" if lang == 'EN' else "Keine Ergebnisse verfügbar", className="text-muted")
    
    try:
        results_path = results_data['full_results_path']
        with open(results_path, 'rb') as f:
            list_of_elites = pickle.load(f)
        
        if not list_of_elites:
            return html.Div("No elite solutions found" if lang == 'EN' else "Keine Elite-Lösungen gefunden", className="text-muted")
        
        # Get feature information
        from backend.translation import translate_feature_labels
        from backend.units import get_unit_label
        
        feature_indices = results_data.get('selected_features_indices', [])
        feature_set = results_data.get('feature_set', 'consolidated')
        feature_labels = translate_feature_labels(feature_indices, lang, feature_set)
        
        # Calculate min/max for each feature from actual data
        measures_array = np.array([elite['measures'] for elite in list_of_elites])
        
        # Create horizontal compact sliders - 4 per row
        slider_cols = []
        for i, (feature_idx, label) in enumerate(zip(feature_indices, feature_labels)):
            feature_values = measures_array[:, i]
            min_val = float(np.min(feature_values))
            max_val = float(np.max(feature_values))
            
            # Get unit - short version
            unit = get_unit_label(feature_idx, lang)
            short_label = f"{label[:12]}..." if len(label) > 12 else label
            label_with_unit = f"{short_label} ({unit})" if unit else short_label
            
            # Create compact slider column
            slider_col = dbc.Col([
                html.Small(label_with_unit, className="text-muted"),
                dcc.RangeSlider(
                    id={'type': 'filter-slider', 'index': i},
                    min=min_val,
                    max=max_val,
                    value=[min_val, max_val],
                    marks=None,  # No marks for compactness
                    tooltip={"placement": "bottom", "always_visible": False},
                    updatemode='mouseup',
                ),
            ], md=3, className="mb-2")
            
            slider_cols.append(slider_col)
        
        return dbc.Row(slider_cols)
        
    except Exception as e:
        return html.Div(f"Error: {str(e)}", className="text-danger")


@callback(
    [Output('filter-statistics', 'children'),
     Output('random-sample-preview', 'children'),
     Output('filter-store', 'data')],
    [Input({'type': 'filter-slider', 'index': ALL}, 'value')],
    [State('results-store', 'data'),
     State('language-store', 'data')],
)
def update_filtered_preview(slider_values, results_data, lang):
    """Filter solutions based on slider values, show stats, and persist filter state to filter-store."""
    if lang is None:
        lang = 'DE'
    
    if not results_data or not results_data.get('full_results_path'):
        return "", "", None
    
    # If no slider values yet, wait for initial values
    if not slider_values or all(v is None for v in slider_values):
        return "", "", None
    
    try:
        results_path = results_data['full_results_path']
        with open(results_path, 'rb') as f:
            list_of_elites = pickle.load(f)
        
        if not list_of_elites:
            return "", "", None
        
        # Convert to numpy array for efficient filtering
        measures_array = np.array([elite['measures'] for elite in list_of_elites])
        objectives = np.array([elite['objective'] for elite in list_of_elites])
        
        # Apply filters
        mask = np.ones(len(list_of_elites), dtype=bool)
        for i, slider_range in enumerate(slider_values):
            if slider_range is None or i >= measures_array.shape[1]:
                continue
            
            min_val, max_val = slider_range
            feature_values = measures_array[:, i]
            
            feature_mask = (feature_values >= min_val) & (feature_values <= max_val)
            mask &= feature_mask
        
        filtered_indices = np.where(mask)[0]
        num_filtered = len(filtered_indices)
        
        
        # Statistics - compact badge format for header
        avg_obj_text = f" | Avg: {objectives[mask].mean():.2f}" if num_filtered > 0 else ""
        stats = dbc.Badge(
            f"{num_filtered} / {len(list_of_elites)} " + 
            ("filtered" if lang == 'EN' else "gefiltert") + avg_obj_text,
            color="info" if num_filtered > 0 else "warning",
            className="ms-3"
        )
        
        # Persist filter state for Step 5 clustering (positional indices matching elite['measures'])
        filter_store_data = {
            'slider_values': slider_values,  # list of [min, max] per positional feature index
            'total_count': len(list_of_elites),
            'filtered_count': num_filtered,
        }
        
        # Random sample preview (hidden now, but keep for compatibility)
        return stats, "", filter_store_data
        
    except Exception as e:
        import traceback
        logger.exception(f"Filter preview error: {str(e)}")
        return "", dbc.Alert(f"Error: {str(e)}", color="danger"), None


@callback(
    Output('correlation-heatmap', 'figure'),
    Input('results-store', 'data'),
    Input('url', 'pathname'),
    State('language-store', 'data'),
)
def generate_correlation_heatmap(results_data, pathname, language):
    """Generate correlation heatmap showing correlations between ALL features and objective"""
    
    # Get current language (default to 'DE')
    lang = language if language else 'DE'
    
    # Only render on this page
    if pathname != '/step4':
        return {}
    
    if not results_data or not results_data.get('full_results_path'):
        # Return empty figure with message
        empty_fig = px.scatter(title=T[lang]['STEP5_NO_RESULTS_TITLE'])
        empty_fig.update_layout(
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
            annotations=[dict(
                text=T[lang]['STEP5_NO_RESULTS_TEXT'],
                xref="paper", yref="paper",
                x=0.5, y=0.5, showarrow=False,
                font=dict(size=14, color="gray")
            )]
        )
        return empty_fig
    
    results_path = results_data.get('full_results_path')
    if not os.path.exists(results_path):
        empty_fig = px.scatter(title=T[lang]['STEP5_FILE_NOT_FOUND'].split('<br>')[0])
        empty_fig.update_layout(
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
            annotations=[dict(
                text=T[lang]['STEP5_FILE_NOT_FOUND'],
                xref="paper", yref="paper",
                x=0.5, y=0.5, showarrow=False,
                font=dict(size=14, color="gray")
            )]
        )
        return empty_fig
    
    try:
        with open(results_path, 'rb') as f:
            list_of_elites = pickle.load(f)
    except Exception as e:
        error_msg = T[lang]['STEP5_LOAD_ERROR'].format(error=str(e))
        empty_fig = px.scatter(title=error_msg.split('<br>')[0])
        empty_fig.update_layout(
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
            annotations=[dict(
                text=error_msg,
                xref="paper", yref="paper",
                x=0.5, y=0.5, showarrow=False,
                font=dict(size=14, color="red")
            )]
        )
        return empty_fig
    
    # Translate feature labels based on current language and feature set
    from backend.translation import translate_feature_labels
    feature_indices = results_data.get('selected_features_indices', [])
    feature_set = results_data.get('feature_set', 'consolidated')
    if not feature_indices:
        empty_fig = px.scatter(title=T[lang]['STEP5_NO_LABELS'])
        empty_fig.update_layout(
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
            annotations=[dict(
                text=T[lang]['STEP5_NO_LABELS'],
                xref="paper", yref="paper",
                x=0.5, y=0.5, showarrow=False,
                font=dict(size=14, color="gray")
            )]
        )
        return empty_fig
    
    labels = translate_feature_labels(feature_indices, lang, feature_set)
    
    # Add units to feature labels
    from backend.units import get_unit_label
    labels_with_units = []
    for i, label in enumerate(labels):
        feature_idx = feature_indices[i]
        unit = get_unit_label(feature_idx, lang)
        if unit:
            labels_with_units.append(f"{label} ({unit})")
        else:
            labels_with_units.append(label)
    
    try:
        # Create dataframe with objectives and measures
        df_for_plot = pd.DataFrame(list_of_elites)
        measures_df = pd.DataFrame(df_for_plot['measures'].tolist(), columns=labels_with_units)
        df_for_plot = pd.concat([df_for_plot['objective'], measures_df], axis=1).copy()
        
        # Use translated objective label
        objective_label = T[lang]['STEP6_OBJECTIVE'].replace(':', '')  # Remove colon
        df_for_plot.rename(columns={'objective': objective_label}, inplace=True)
        
        # Calculate full correlation matrix between ALL variables (objective + all features)
        corr = df_for_plot.corr()
        
        # Create labels with line breaks for better readability
        display_labels = [label.replace(' ', '<br>') if len(label) > 15 else label for label in corr.columns]
        
        # Create heatmap showing all correlations
        heatmap_fig = px.imshow(
            corr, 
            text_auto=".2f",  # Show correlation values with 2 decimal places
            aspect="auto",
            color_continuous_scale="RdBu_r",  # Red for negative, Blue for positive
            range_color=[-1, 1],
            labels=dict(color=T[lang]['STEP5_CORRELATION_LABEL']),
            x=display_labels,
            y=display_labels
        )
        
        # Customize layout for better visibility
        heatmap_fig.update_xaxes(side="top", tickangle=-45, tickfont=dict(size=10))
        heatmap_fig.update_yaxes(tickfont=dict(size=10))
        heatmap_fig.update_layout(
            margin=dict(l=150, r=20, t=150, b=20),
            height=600,  # Increased height for better visibility
            font=dict(size=10)
        )
        
        # Add annotation explaining the heatmap
        heatmap_fig.add_annotation(
            text=T[lang]['STEP5_CORRELATION_LEGEND'],
            xref="paper", yref="paper",
            x=0.5, y=-0.1,
            showarrow=False,
            font=dict(size=9, color="gray"),
            xanchor='center'
        )
        
        return heatmap_fig
        
    except Exception as e:
        # If anything goes wrong, show error message
        import traceback
        error_msg = T[lang]['STEP5_CORRELATION_ERROR'].format(error=str(e))
        error_fig = px.scatter(title=error_msg.split('<br>')[0])
        error_fig.update_layout(
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
            annotations=[dict(
                text=f"{error_msg}<br><br>{traceback.format_exc()}",
                xref="paper", yref="paper",
                x=0.5, y=0.5, showarrow=False,
                font=dict(size=10, color="red"),
                align="left"
            )]
        )
        return error_fig


@callback(
    Output('feature-objective-plots-container', 'children'),
    Input('results-store', 'data'),
    Input('url', 'pathname'),
    State('language-store', 'data'),
)
def generate_feature_objective_plots(results_data, pathname, language):
    """Generate scatter plots showing objective vs each feature"""
    from backend.translation import translate_feature_labels
    
    # Get current language (default to 'DE')
    lang = language if language else 'DE'
    
    # Only render on this page
    if pathname != '/step4':
        return []
    
    if not results_data or not results_data.get('full_results_path'):
        return dbc.Alert(T[lang].get('STEP5_NO_RESULTS_TEXT', 'No optimization results available'), color="light")
    
    try:
        # Load elite solutions list
        results_path = results_data['full_results_path']
        with open(results_path, 'rb') as f:
            list_of_elites = pickle.load(f)
        
        if not list_of_elites:
            return dbc.Alert(T[lang].get('STEP5_NO_ELITES', 'No elite solutions found'), color="warning")
        
        # Get feature set from results metadata
        feature_set = results_data.get('feature_set', 'consolidated')
        
        # Get feature indices
        feature_indices = results_data.get('selected_features_indices', [])
        if not feature_indices:
            return dbc.Alert(T[lang].get('STEP5_NO_LABELS', 'No feature labels available'), color="warning")
        
        num_features = len(feature_indices)
        
        # Get feature labels
        feature_labels = translate_feature_labels(feature_indices, lang, feature_set)
        
        # Add units to feature labels
        from backend.units import get_unit_label
        labels_with_units = []
        for i, label in enumerate(feature_labels):
            feature_idx = feature_indices[i]
            unit = get_unit_label(feature_idx, lang)
            if unit:
                labels_with_units.append(f"{label} ({unit})")
            else:
                labels_with_units.append(label)
        
        # Get objective label
        objective_label = T[lang].get('STEP6_OBJECTIVE', 'Objective:').replace(':', '')
        
        # Extract objectives and measures from list of elites
        objectives = [elite['objective'] for elite in list_of_elites]
        measures_list = [elite['measures'] for elite in list_of_elites]
        
        # Create scatter plots for each feature
        scatter_plots = []
        
        # Organize in rows of 4 plots
        for i in range(0, num_features, 4):
            row_plots = []
            
            for j in range(4):
                if i + j >= num_features:
                    break
                
                feature_idx = i + j
                feature_label = labels_with_units[feature_idx]
                
                # Extract feature values for this feature
                feature_values = [measures[feature_idx] for measures in measures_list]
                
                # Create scatter plot
                fig = px.scatter(
                    x=feature_values,
                    y=objectives,
                    opacity=0.6,
                    labels={'x': feature_label, 'y': objective_label},
                    title=f'{feature_label} vs {objective_label}'
                )
                
                # Calculate y-axis range
                max_objective = max(objectives) if objectives else 1.0
                max_objective_ceil = float(np.ceil(max_objective))
                
                # Customize layout
                fig.update_traces(
                    marker=dict(size=5, color='rgb(55, 126, 184)', line=dict(width=0.5, color='white'))
                )
                fig.update_layout(
                    margin=dict(l=50, r=20, t=40, b=40),
                    height=300,
                    plot_bgcolor='white',
                    paper_bgcolor='white',
                    font=dict(size=10),
                    title_font_size=11,
                    showlegend=False
                )
                fig.update_xaxes(showgrid=True, gridwidth=0.5, gridcolor='lightgray')
                fig.update_yaxes(showgrid=True, gridwidth=0.5, gridcolor='lightgray', range=[0.0, max_objective_ceil])
                
                row_plots.append(
                    dbc.Col(dcc.Graph(figure=fig), md=3)
                )
            
            scatter_plots.append(dbc.Row(row_plots, className="mb-3"))
        
        return scatter_plots
        
    except Exception as e:
        import traceback
        error_msg = f"Error generating feature-objective plots: {str(e)}"
        logger.exception(error_msg)
        return dbc.Alert(error_msg, color="danger")

@callback(
    Output('uncertainty-heatmap-container', 'style'),
    Input('results-store', 'data')
)
def toggle_uncertainty_section(results_data):
    """Show uncertainty section only if surrogate model was used"""
    if not results_data:
        return {'display': 'none'}
    
    model_type = results_data.get('model_type', 'original')
    # Uncertainty section only applicable for models that provide uncertainties (none currently)
    return {'display': 'none'}

@callback(
    Output('uncertainty-heatmap-display', 'children'),
    Input('show-uncertainty-toggle', 'value'),
    State('results-store', 'data'),
    State('language-store', 'data')
)
def display_uncertainty_heatmap(show_toggle, results_data, lang):
    """Display uncertainty heatmap when toggle is on"""
    if lang is None:
        lang = 'DE'
    
    # Only display if toggle is on
    if not show_toggle or 1 not in show_toggle:
        return html.Div()
    
    if not results_data or not results_data.get('full_results_path'):
        return dbc.Alert("No results available", color="warning")
    
    try:
        # Load the full results to access uncertainty data
        results_path = results_data['full_results_path']
        with open(results_path, 'rb') as f:
            list_of_elites = pickle.load(f)
        
        if not list_of_elites:
            return dbc.Alert("No elite solutions found", color="warning")
        
        # Check if uncertainty data is available
        if 'uncertainty' not in list_of_elites[0]:
            return dbc.Alert(
                "Uncertainty data not available for this optimization run. "
                "Only available when using SVGP or Hybrid surrogate models.",
                color="info"
            )
        
        # Get uncertainty from first solution as example
        # In a more sophisticated version, we could aggregate uncertainties across all solutions
        first_uncertainty = list_of_elites[0]['uncertainty']
        
        # Create heatmap using plotly express
        fig = px.imshow(
            first_uncertainty,
            color_continuous_scale='Reds',
            labels=dict(x="X", y="Y", color="Uncertainty"),
            title=T[lang]['STEP4_UNCERTAINTY_TITLE']
        )
        
        fig.update_layout(
            height=400,
            margin=dict(l=20, r=20, t=40, b=20),
            coloraxis_colorbar=dict(title="σ")
        )
        
        return dcc.Graph(figure=fig)
        
    except Exception as e:
        import traceback
        error_msg = f"Error displaying uncertainty: {str(e)}"
        logger.exception(error_msg)
        return dbc.Alert(error_msg, color="danger")


# --- Update archive heatmap ---
@callback(
    Output('archive-heatmap', 'figure'),
    Input('x-axis-dropdown', 'value'),
    Input('y-axis-dropdown', 'value'),
    Input({'type': 'filter-slider', 'index': ALL}, 'value'),
    Input('results-store', 'data'),
    State('language-store', 'data'),
)
def update_archive_heatmap(x_axis_idx, y_axis_idx, slider_values, results_data, language):
    """Create a heatmap of the archive showing objective values with filtered cells highlighted in red"""
    from backend.config import DOMAIN_CONFIG
    from backend.translation import translate_feature_labels
    import plotly.graph_objects as go
    
    lang = language if language else 'DE'
    
    if not isinstance(x_axis_idx, int) or not isinstance(y_axis_idx, int):
        return px.imshow([[0]], title=T[lang].get('STEP3_NO_AREA', 'Select axes'))
    
    # Load final results only
    if not results_data:
        return px.imshow([[0]], title=T[lang].get('STEP3_NO_SOLUTIONS', 'No results found'))
    
    results_path = results_data.get('full_results_path')
    if not results_path or not os.path.exists(results_path):
        return px.imshow([[0]], title=T[lang].get('STEP3_NO_SOLUTIONS', 'No results found'))
    
    with open(results_path, 'rb') as f:
        list_of_elites = pickle.load(f)
    
    # Get dimensions and feature ranges from final results
    grid_dims = results_data['archive_dims']
    selected_features = results_data['selected_features_indices']
    user_feature_ranges = results_data.get('feature_ranges', {})
    feature_set = results_data.get('feature_set', 'consolidated')
    
    # Build feature ranges for selected features
    feat_ranges = []
    for feature_index in selected_features:
        user_range = user_feature_ranges.get(str(feature_index))
        if user_range:
            feat_ranges.append(user_range)
        else:
            feat_ranges.append(DOMAIN_CONFIG['feat_ranges'][feature_index])
    
    grid_resolution_x = grid_dims[x_axis_idx]
    grid_resolution_y = grid_dims[y_axis_idx]
    
    # Create grids for objectives and filter mask
    heatmap_grid = np.full((grid_resolution_y, grid_resolution_x), np.nan)
    filter_mask_grid = np.zeros((grid_resolution_y, grid_resolution_x), dtype=bool)  # True = excluded by filter
    
    # Apply filter to determine which cells are excluded
    measures_array = np.array([elite['measures'] for elite in list_of_elites])
    elite_filter_mask = np.ones(len(list_of_elites), dtype=bool)
    
    if slider_values:
        for i, slider_range in enumerate(slider_values):
            if slider_range is None or i >= measures_array.shape[1]:
                continue
            min_val, max_val = slider_range
            feature_values = measures_array[:, i]
            elite_filter_mask &= (feature_values >= min_val) & (feature_values <= max_val)
    
    for idx, elite_dict in enumerate(list_of_elites):
        ix = elite_dict['grid_indices'][x_axis_idx]
        iy = elite_dict['grid_indices'][y_axis_idx]
        
        # Update objective value (best per cell)
        if np.isnan(heatmap_grid[iy, ix]) or elite_dict['objective'] > heatmap_grid[iy, ix]:
            heatmap_grid[iy, ix] = elite_dict['objective']
            # Mark as excluded if this elite is filtered out
            if not elite_filter_mask[idx]:
                filter_mask_grid[iy, ix] = True
            else:
                filter_mask_grid[iy, ix] = False
    
    # Get feature labels
    labels = translate_feature_labels(selected_features, lang, feature_set)
    
    # Calculate axis tick positions and labels
    x_range = feat_ranges[x_axis_idx]
    y_range = feat_ranges[y_axis_idx]
    
    # Create tick positions (cell centers)
    x_tick_positions = np.arange(grid_resolution_x)
    y_tick_positions = np.arange(grid_resolution_y)
    
    # Create tick labels (feature values at cell centers)
    x_tick_values = np.linspace(x_range[0], x_range[1], grid_resolution_x)
    y_tick_values = np.linspace(y_range[0], y_range[1], grid_resolution_y)
    
    # Format tick labels
    x_tick_labels = [f"{val:.1f}" for val in x_tick_values]
    y_tick_labels = [f"{val:.1f}" for val in y_tick_values]
    
    # Calculate max objective for color range
    max_objective = np.nanmax(heatmap_grid)
    if np.isnan(max_objective) or max_objective <= 0:
        max_objective = 1.0
    max_objective_ceil = float(np.ceil(max_objective))
    
    # Create figure with both heatmap and overlay for excluded cells
    fig = go.Figure()
    
    # Add main heatmap
    fig.add_trace(go.Heatmap(
        z=heatmap_grid,
        colorscale='Viridis',
        zmin=0.0,
        zmax=max_objective_ceil,
        colorbar=dict(title=T[lang].get('STEP3_HEATMAP_OBJECTIVE_LABEL', 'Objective')),
        hovertemplate='X: %{x}<br>Y: %{y}<br>Objective: %{z:.3f}<extra></extra>'
    ))
    
    # Add red overlay for excluded cells
    # Create a mask where excluded cells are 1 and included are NaN
    exclusion_overlay = np.where(filter_mask_grid & ~np.isnan(heatmap_grid), 1.0, np.nan)
    
    fig.add_trace(go.Heatmap(
        z=exclusion_overlay,
        colorscale=[[0, 'rgba(255,0,0,0.5)'], [1, 'rgba(255,0,0,0.5)']],
        showscale=False,
        hoverinfo='skip'
    ))
    
    # Update axes with proper labels
    fig.update_xaxes(
        tickmode='array',
        tickvals=x_tick_positions[::max(1, grid_resolution_x // 5)],
        ticktext=[x_tick_labels[i] for i in range(0, grid_resolution_x, max(1, grid_resolution_x // 5))],
        title=labels[x_axis_idx]
    )
    
    fig.update_yaxes(
        tickmode='array',
        tickvals=y_tick_positions[::max(1, grid_resolution_y // 5)],
        ticktext=[y_tick_labels[i] for i in range(0, grid_resolution_y, max(1, grid_resolution_y // 5))],
        title=labels[y_axis_idx]
    )
    
    fig.update_layout(
        height=400,
        margin=dict(l=50, r=20, t=30, b=50),
        xaxis=dict(scaleanchor='y', scaleratio=1)
    )
    
    return fig


# --- Update parallel coordinates plot ---
@callback(
    Output('parallel-coords-plot', 'figure'),
    Input({'type': 'filter-slider', 'index': ALL}, 'value'),
    Input('results-store', 'data'),
    State('language-store', 'data'),
)
def update_parallel_coords(slider_values, results_data, language):
    """Create parallel coordinates plot with filtered solutions highlighted"""
    from backend.translation import translate_feature_labels
    from backend.units import get_unit_label
    
    lang = language if language else 'DE'
    
    if not results_data:
        return {}
    
    results_path = results_data.get('full_results_path')
    if not results_path or not os.path.exists(results_path):
        return {}
    
    with open(results_path, 'rb') as f:
        list_of_elites = pickle.load(f)
    
    # Get feature indices and feature set from final results
    feature_indices = results_data.get('selected_features_indices', [])
    feature_set = results_data.get('feature_set', 'consolidated')
    
    # Translate labels based on current language and feature set
    labels = translate_feature_labels(feature_indices, lang, feature_set)
    
    # Add units to feature labels
    labels_with_units = []
    for i, label in enumerate(labels):
        feature_idx = feature_indices[i]
        unit = get_unit_label(feature_idx, lang)
        if unit:
            labels_with_units.append(f"{label}<br>({unit})")
        else:
            labels_with_units.append(label)
    
    # Create dataframe
    df_for_plot = pd.DataFrame(list_of_elites)
    if df_for_plot.empty:
        return {}
    
    measures_df = pd.DataFrame(df_for_plot['measures'].tolist(), columns=labels_with_units)
    df_for_plot = pd.concat([df_for_plot['objective'], measures_df], axis=1).copy()
    
    # Apply filter mask
    measures_array = np.array([elite['measures'] for elite in list_of_elites])
    filter_mask = np.ones(len(list_of_elites), dtype=bool)
    
    if slider_values:
        for i, slider_range in enumerate(slider_values):
            if slider_range is None or i >= measures_array.shape[1]:
                continue
            min_val, max_val = slider_range
            feature_values = measures_array[:, i]
            filter_mask &= (feature_values >= min_val) & (feature_values <= max_val)
    
    # Add filter status as column (1 = included, 0 = excluded)
    df_for_plot['filtered'] = filter_mask.astype(float)
    
    # Use translated objective label
    objective_label = T[lang].get('STEP6_OBJECTIVE', 'Objective:').replace(':', '')
    df_for_plot.rename(columns={'objective': objective_label}, inplace=True)
    
    # Calculate max objective for color range
    max_objective = df_for_plot[objective_label].max()
    if pd.isna(max_objective) or max_objective <= 0:
        max_objective = 1.0
    max_objective_ceil = float(np.ceil(max_objective))
    
    # Create dimension labels with line breaks
    all_dims = [objective_label] + labels_with_units
    dim_labels = {dim: dim.replace(" ", "<br>") for dim in all_dims}
    
    # Color by filter status (filtered solutions in full color, excluded in light gray)
    parallel_fig = px.parallel_coordinates(
        df_for_plot, dimensions=all_dims, color=objective_label,
        labels=dim_labels,
        color_continuous_scale='Viridis',
        range_color=[0.0, max_objective_ceil]
    )
    
    parallel_fig.update_layout(
        height=400,
        margin=dict(l=60, r=60, t=30, b=30),
        font=dict(size=8)
    )
    
    # Reduce tick label font size to prevent overlap
    parallel_fig.update_traces(
        labelfont=dict(size=9),  # Axis labels (feature names)
        tickfont=dict(size=7),   # Tick values on axes
    )
    
    return parallel_fig


# --- Update solution archive grid (simplified mini 3D views) ---
@callback(
    Output('solution-archive-grid', 'children'),
    Input('x-axis-dropdown', 'value'),
    Input('y-axis-dropdown', 'value'),
    Input({'type': 'filter-slider', 'index': ALL}, 'value'),
    Input('results-store', 'data'),
    State('language-store', 'data'),
)
def update_solution_archive_grid(x_axis_idx, y_axis_idx, slider_values, results_data, language):
    """Create a grid of mini 3D views showing solutions in the archive"""
    import plotly.graph_objects as go
    
    lang = language if language else 'DE'
    
    if not isinstance(x_axis_idx, int) or not isinstance(y_axis_idx, int):
        return dbc.Alert("Select axes to view archive" if lang == 'EN' else "Achsen auswählen", color="info")
    
    if not results_data:
        return dbc.Alert("No results" if lang == 'EN' else "Keine Ergebnisse", color="warning")
    
    results_path = results_data.get('full_results_path')
    if not results_path or not os.path.exists(results_path):
        return dbc.Alert("Results file not found" if lang == 'EN' else "Ergebnisdatei nicht gefunden", color="danger")
    
    with open(results_path, 'rb') as f:
        list_of_elites = pickle.load(f)
    
    xy_length = results_data.get('xy_length', 32)
    grid_dims = results_data['archive_dims']
    
    # Apply filter
    measures_array = np.array([elite['measures'] for elite in list_of_elites])
    filter_mask = np.ones(len(list_of_elites), dtype=bool)
    
    if slider_values:
        for i, slider_range in enumerate(slider_values):
            if slider_range is None or i >= measures_array.shape[1]:
                continue
            min_val, max_val = slider_range
            feature_values = measures_array[:, i]
            filter_mask &= (feature_values >= min_val) & (feature_values <= max_val)
    
    # Get grid dimensions for selected axes
    grid_resolution_x = grid_dims[x_axis_idx]
    grid_resolution_y = grid_dims[y_axis_idx]
    
    # Limit to 5x5 grid for performance
    max_grid = 5
    sample_x = max(1, grid_resolution_x // max_grid)
    sample_y = max(1, grid_resolution_y // max_grid)
    
    # Build grid of best solutions per cell
    grid_solutions = {}
    all_objectives = []
    for idx, elite in enumerate(list_of_elites):
        ix = elite['grid_indices'][x_axis_idx]
        iy = elite['grid_indices'][y_axis_idx]
        
        # Sample grid cells
        sampled_ix = ix // sample_x
        sampled_iy = iy // sample_y
        key = (sampled_ix, sampled_iy)
        
        elite_objective = elite.get('objective', 0.0)
        all_objectives.append(elite_objective)
        if key not in grid_solutions or elite_objective > grid_solutions[key].get('elite_objective', 0.0):
            grid_solutions[key] = {
                'elite': elite,
                'elite_objective': elite_objective,
                'idx': idx,
                'filtered': filter_mask[idx]
            }
    
    # Calculate objective range for color scaling
    min_obj = min(all_objectives) if all_objectives else 0.0
    max_obj = max(all_objectives) if all_objectives else 1.0
    obj_range = max_obj - min_obj if max_obj > min_obj else 1.0
    
    # Create mini 3D previews in a grid with viridis coloring by objective
    import matplotlib.colors as mcolors
    viridis = px.colors.sequential.Viridis
    
    def get_viridis_color(value, min_v, max_v):
        """Map value to viridis color"""
        if max_v <= min_v:
            return viridis[len(viridis)//2]
        norm = (value - min_v) / (max_v - min_v)
        idx = int(norm * (len(viridis) - 1))
        return viridis[min(idx, len(viridis)-1)]
    
    rows = []
    for iy in range(min(max_grid, grid_resolution_y)):
        row_cols = []
        for ix in range(min(max_grid, grid_resolution_x)):
            key = (ix, iy)
            
            if key in grid_solutions:
                sol = grid_solutions[key]
                elite = sol['elite']
                is_filtered = sol['filtered']
                elite_obj = sol['elite_objective']
                
                # Get heightmap
                heightmap = np.array(elite['heightmap']).reshape(xy_length, xy_length)
                
                # Color by objective value using viridis
                obj_color = get_viridis_color(elite_obj, min_obj, max_obj)
                
                # Create mini 3D view using block-based mesh (cleaner than Surface)
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
                        
                        # Create box vertices (height in meters, convert to cell units to match x/y)
                        x0, x1 = col, col + 1
                        y0, y1 = row, row + 1
                        z0, z1 = 0, height / 3.0
                        
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
                ground_size = xy_length
                fig.add_trace(go.Mesh3d(
                    x=[0, ground_size, ground_size, 0],
                    y=[0, 0, ground_size, ground_size],
                    z=[0, 0, 0, 0],
                    i=[0, 0], j=[1, 2], k=[2, 3],
                    color='rgb(180, 200, 180)',
                    opacity=0.6,
                    hoverinfo='skip'
                ))
                
                border_color = obj_color if is_filtered else 'red'
                bg_color = 'rgba(255,200,200,0.3)' if not is_filtered else 'rgba(0,0,0,0)'
                
                fig.update_layout(
                    scene=dict(
                        xaxis=dict(visible=False),
                        yaxis=dict(visible=False),
                        zaxis=dict(visible=False),
                        camera=dict(eye=dict(x=1.5, y=1.5, z=1.2)),
                        aspectmode='data'
                    ),
                    margin=dict(l=0, r=0, t=0, b=0),
                    height=80,
                    width=80,
                    showlegend=False,
                    paper_bgcolor=bg_color,
                )
                
                cell = html.Div([
                    dcc.Graph(figure=fig, config={'displayModeBar': False}, style={'height': '80px', 'width': '80px'}),
                    html.Small(f"{elite_obj:.2f}", className="text-center d-block", 
                              style={'color': 'gray' if not is_filtered else 'black', 'fontSize': '10px'})
                ], style={
                    'border': f'2px solid {border_color}',
                    'borderRadius': '4px',
                    'margin': '1px',
                    'opacity': '0.4' if not is_filtered else '1.0'
                })
            else:
                # Empty cell
                cell = html.Div(
                    style={'height': '100px', 'width': '80px', 'backgroundColor': '#f8f9fa', 'margin': '1px', 'borderRadius': '4px'}
                )
            
            row_cols.append(cell)
        
        rows.append(html.Div(row_cols, style={'display': 'flex', 'flexDirection': 'row'}))
    
    # Add color legend
    legend = html.Div([
        html.Small(f"Obj: {min_obj:.2f}", style={'color': viridis[0]}),
        html.Div(style={
            'height': '10px',
            'width': '100px',
            'background': f'linear-gradient(to right, {", ".join(viridis)})',
            'display': 'inline-block',
            'margin': '0 5px',
            'verticalAlign': 'middle'
        }),
        html.Small(f"{max_obj:.2f}", style={'color': viridis[-1]}),
    ], className="text-center mb-2", style={'fontSize': '10px'})
    
    return html.Div([
        legend,
        html.Div(rows, style={'display': 'flex', 'flexDirection': 'column-reverse'})
    ])
