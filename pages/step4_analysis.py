from dash import dcc, html, Input, Output, State, callback
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
        # Feature vs Objective Scatter Plots
        dbc.Row([
            html.H4(T[lang]['STEP4_FEATURE_VS_OBJECTIVE_HEADER']),
            html.P(T[lang]['STEP4_FEATURE_VS_OBJECTIVE_INFO'],
                    className="text-muted small"),
            dcc.Loading(html.Div(id='feature-objective-plots-container')),
        ], className="mb-4"),

        # Correlation Heatmap
        dbc.Row([
            dbc.Col([
                dbc.Card(dbc.CardBody([
                    html.H4(T[lang]['STEP5_CORRELATION_HEADER']),
                    dcc.Loading(dcc.Graph(id='correlation-heatmap'))
                ]), className="mb-3"),
            ], md=12),
        ], className="mb-4"),
        
    ], fluid=True)


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
    feature_set = results_data.get('feature_set', 'original')
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
        feature_set = results_data.get('feature_set', 'original')
        
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
