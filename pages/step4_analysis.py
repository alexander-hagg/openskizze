from dash import dcc, html, Input, Output, State, callback, ALL
import dash_bootstrap_components as dbc
from backend.translation import T
import pickle
import os
import numpy as np
import pandas as pd
import plotly.express as px

def layout(lang='DE'):
    from backend.translation import create_breadcrumb
    return dbc.Container([
        create_breadcrumb(4, lang),
        html.H2(T[lang].get('STEP4_TITLE', 'Results Analysis')),
        
        # NEW: Interactive Filter Section with Random Sample Display
        dbc.Row([
            dbc.Col([
                dbc.Card(dbc.CardBody([
                    html.H4("Filter & Preview Solutions" if lang == 'EN' else "Lösungen filtern & vorschauen"),
                    html.P("Adjust feature ranges to filter solutions in real-time. "
                           "A random selection of high-performing filtered solutions is shown below." 
                           if lang == 'EN' else 
                           "Passen Sie die Merkmalsbereiche an, um Lösungen in Echtzeit zu filtern. "
                           "Eine zufällige Auswahl hochperformanter gefilterter Lösungen wird unten angezeigt.",
                           className="text-muted small"),
                    html.Hr(),
                    # Filter controls will be dynamically generated
                    html.Div(id='filter-sliders-container'),
                    
                ]), className="mb-4"),
            ], md=6),
            dbc.Col([
                dbc.Card(dbc.CardBody([
                    # Statistics about filtered solutions
                    html.Div(id='filter-statistics'),
                    # Random sample preview (3D thumbnails)
                    dcc.Loading(html.Div(id='random-sample-preview')),
                ]), className="mb-4"),
            ], md=6),            
        ], className="mb-4"),
        
        
        # Feature vs Objective Scatter Plots and Correlation Heatmap
        dbc.Row([
            dbc.Col([
                dbc.Card(dbc.CardBody([
                    html.H4(T[lang]['STEP4_FEATURE_VS_OBJECTIVE_HEADER']),
                    html.P(T[lang]['STEP4_FEATURE_VS_OBJECTIVE_INFO'],
                    className="text-muted small"),
                    dcc.Loading(html.Div(id='feature-objective-plots-container')),
                ]), className="mb-3"),
            ], md=6),
            dbc.Col([
                dbc.Card(dbc.CardBody([
                    html.H4(T[lang]['STEP5_CORRELATION_HEADER']),
                    dcc.Loading(dcc.Graph(id='correlation-heatmap'))
                ]), className="mb-3"),
            ], md=6),
        ], className="mb-4"),
        
        # Uncertainty Heatmap Section (for SVGP/Hybrid models)
        html.Div(id='uncertainty-heatmap-container', children=[
            dbc.Row([
                dbc.Col([
                    dbc.Card(dbc.CardBody([
                        html.Div([
                            html.H4(T[lang]['STEP4_UNCERTAINTY_HEADER'], className="d-inline-block"),
                            dbc.Checklist(
                                options=[{"label": T[lang]['STEP4_SHOW_UNCERTAINTY'], "value": 1}],
                                value=[],
                                id="show-uncertainty-toggle",
                                switch=True,
                                className="float-end"
                            ),
                        ], className="clearfix"),
                        html.P(T[lang]['STEP4_UNCERTAINTY_INFO'], className="text-muted small"),
                        dcc.Loading(html.Div(id='uncertainty-heatmap-display')),
                    ]), className="mb-3"),
                ], md=12),
            ])
        ], style={'display': 'none'}),  # Hidden by default, shown only when surrogate model was used
        
    ], fluid=True)


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
        
        sliders = []
        for i, (feature_idx, label) in enumerate(zip(feature_indices, feature_labels)):
            feature_values = measures_array[:, i]
            min_val = float(np.min(feature_values))
            max_val = float(np.max(feature_values))
            
            # Get unit
            unit = get_unit_label(feature_idx, lang)
            label_with_unit = f"{label} ({unit})" if unit else label
            
            # Create range slider
            slider = dbc.Row([
                dbc.Col([
                    html.Label(label_with_unit, className="fw-bold"),
                    dcc.RangeSlider(
                        id={'type': 'filter-slider', 'index': i},
                        min=min_val,
                        max=max_val,
                        value=[min_val, max_val],  # Start with full range
                        marks={
                            min_val: f'{min_val:.1f}',
                            max_val: f'{max_val:.1f}'
                        },
                        tooltip={"placement": "bottom", "always_visible": False},
                        updatemode='mouseup',  # Only update when user releases slider
                    ),
                ], md=6),
            ], className="mb-3")
            
            sliders.append(slider)
        
        return sliders
        
    except Exception as e:
        return html.Div(f"Error: {str(e)}", className="text-danger")


@callback(
    [Output('filter-statistics', 'children'),
     Output('random-sample-preview', 'children')],
    [Input({'type': 'filter-slider', 'index': ALL}, 'value')],
    [State('results-store', 'data'),
     State('language-store', 'data')],
)
def update_filtered_preview(slider_values, results_data, lang):
    """Filter solutions based on slider values and show random sample"""
    if lang is None:
        lang = 'DE'
    
    if not results_data or not results_data.get('full_results_path'):
        return "", ""
    
    # If no slider values yet, wait for initial values
    if not slider_values or all(v is None for v in slider_values):
        return "", ""
    
    try:
        results_path = results_data['full_results_path']
        with open(results_path, 'rb') as f:
            list_of_elites = pickle.load(f)
        
        if not list_of_elites:
            return "", ""
        
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
        
        
        # Statistics
        stats = dbc.Alert([
            html.Strong(f"{num_filtered} / {len(list_of_elites)} " + 
                       ("solutions match filters" if lang == 'EN' else "Lösungen passen zu den Filtern")),
            html.Br(),
            ("Average objective: " if lang == 'EN' else "Durchschnittliches Ziel: ") + 
            f"{objectives[mask].mean():.3f}" if num_filtered > 0 else ""
        ], color="info" if num_filtered > 0 else "warning", className="mb-3")
        
        # Random sample preview
        if num_filtered == 0:
            return stats, dbc.Alert(
                "No solutions match the current filters. Try relaxing the constraints." if lang == 'EN' else
                "Keine Lösungen entsprechen den aktuellen Filtern. Versuchen Sie, die Einschränkungen zu lockern.",
                color="warning"
            )
        
        # Select random sample of high performers
        # Sort by objective (descending) and take top 50%, then random sample
        sorted_indices = filtered_indices[np.argsort(-objectives[mask])]  # Sort descending
        top_50_percent = max(1, len(sorted_indices) // 2)
        high_performers = sorted_indices[:top_50_percent]

        # Random sample (up to 25 solutions)
        num_samples = min(25, len(high_performers))
        np.random.seed(None)  # Use current time for true randomness
        sampled_indices = np.random.choice(high_performers, size=num_samples, replace=False)
        
        # Create 3D preview thumbnails
        from backend.encoding import ParametricEncoding
        from backend.config import ENCODING_CONFIG
        import plotly.graph_objects as go
        
        xy_length = results_data['xy_length']
        
        preview_cards = []
        for idx in sampled_indices:
            elite = list_of_elites[idx]
            
            # Get heightmap directly from elite (already stored)
            heightmap = np.array(elite['heightmap']).reshape(xy_length, xy_length)
            
            
            # Create simple 3D preview
            fig = go.Figure()
            
            # Add buildings as surface
            x = np.arange(heightmap.shape[1])
            y = np.arange(heightmap.shape[0])
            
            fig.add_trace(go.Surface(
                z=heightmap,
                x=x,
                y=y,
                colorscale='Blues',
                showscale=False,
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
                margin=dict(l=0, r=0, t=20, b=0),
                height=200,
                width=200,
                showlegend=False,
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)'
            )
            
            card = dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        dcc.Graph(figure=fig, config={'displayModeBar': False}),
                        html.Small(f"Obj: {elite['objective']:.3f}", className="text-center d-block")
                    ], className="p-2")
                ])
            ], width=2, className="mb-3")  # width=2 gives us 6 columns, but we'll organize in rows of 5
            
            preview_cards.append(card)
        
        # Organize cards into rows of 5 for 5x5 grid
        rows = []
        for i in range(0, len(preview_cards), 5):
            row_cards = preview_cards[i:i+5]
            rows.append(dbc.Row(row_cards, className="mb-2 justify-content-start"))
        
        return stats, html.Div(rows)
        
    except Exception as e:
        import traceback
        print(f"[ERROR] Filter preview: {str(e)}")
        print(traceback.format_exc())
        return "", dbc.Alert(f"Error: {str(e)}", color="danger")


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
                fig.update_yaxes(showgrid=True, gridwidth=0.5, gridcolor='lightgray')
                
                row_plots.append(
                    dbc.Col(dcc.Graph(figure=fig), md=3)
                )
            
            scatter_plots.append(dbc.Row(row_plots, className="mb-3"))
        
        return scatter_plots
        
    except Exception as e:
        import traceback
        error_msg = f"Error generating feature-objective plots: {str(e)}"
        print(f"[ERROR] {error_msg}")
        print(traceback.format_exc())
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
    # Show section for SVGP and Hybrid models (they provide uncertainties)
    if model_type in ['svgp', 'hybrid']:
        return {'display': 'block'}
    else:
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
        print(f"[ERROR] {error_msg}")
        print(traceback.format_exc())
        return dbc.Alert(error_msg, color="danger")
