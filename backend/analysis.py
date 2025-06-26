import numpy as np
import pandas as pd
from backend.translation import T # Import the translation dictionary

LANG = 'DE' # Set default language

def create_parallel_coords_fig(results_archive, measures_map):
    """
    Creates a parallel coordinates plot from the results archive.
    """
    if not results_archive or not results_archive['objective']:
        return None

    df_data = {'objective': results_archive['objective']}
    df_data.update(results_archive['measures'])
    df = pd.DataFrame(df_data)

    # Use the measure keys for dimensions and the translated labels for the UI
    dimensions = ['objective'] + list(results_archive['measures'].keys())
    labels = {'objective': 'Zielfunktion (Kaltluft)'}
    labels.update({key: measures_map[key] for key in results_archive['measures']})

    fig = pd.plotting.parallel_coordinates(df, 'objective', color=plt.cm.viridis)


    return fig

def get_solution_grid(results_archive, x_axis_measure, y_axis_measure, grid_resolution=10):
    """
    MOCK function to bin the archive into a 2D grid for visualization.
    """
    if not all([results_archive, x_axis_measure, y_axis_measure]):
        return np.empty((grid_resolution, grid_resolution), dtype=object)

    x_values = np.array(results_archive['measures'][x_axis_measure])
    y_values = np.array(results_archive['measures'][y_axis_measure])
    objectives = np.array(results_archive['objective'])

    # Create grid bins
    x_bins = np.linspace(x_values.min(), x_values.max(), grid_resolution + 1)
    y_bins = np.linspace(y_values.min(), y_values.max(), grid_resolution + 1)

    # Digitize to find which bin each solution belongs to
    x_indices = np.digitize(x_values, x_bins) - 1
    y_indices = np.digitize(y_values, y_bins) - 1

    # Clamp indices to be within the grid
    x_indices = np.clip(x_indices, 0, grid_resolution - 1)
    y_indices = np.clip(y_indices, 0, grid_resolution - 1)

    # Initialize grid
    grid = np.full((grid_resolution, grid_resolution), None, dtype=object)
    for i in range(grid_resolution):
        for j in range(grid_resolution):
            grid[i, j] = {'solutions': [], 'best_solution_idx': -1, 'best_objective': -np.inf}

    # Populate the grid
    for idx in range(len(objectives)):
        ix, iy = x_indices[idx], y_indices[idx]
        grid[iy, ix]['solutions'].append(idx) # grid is (row, col) -> (y, x)
        if objectives[idx] > grid[iy, ix]['best_objective']:
            grid[iy, ix]['best_objective'] = objectives[idx]
            grid[iy, ix]['best_solution_idx'] = idx

    return grid


def generate_contest_requirements(results_archive):
    """
    MOCK function to generate text for planning contest requirements.
    Analyzes the top-performing solutions.
    """
    if not results_archive or not results_archive['objective']:
        return "Keine Daten zur Analyse vorhanden."

    df = pd.DataFrame({
        'objective': results_archive['objective'],
        **results_archive['measures']
    })

    # Find the top 10% of solutions
    top_10_percentile = df['objective'].quantile(0.9)
    top_solutions = df[df['objective'] >= top_10_percentile]

    if top_solutions.empty:
        return "Keine ausreichend performanten Lösungen gefunden, um Anforderungen abzuleiten."

    # Generate requirements based on the stats of the best solutions
    report = [
        "Basierend auf der Analyse von {} Lösungen wurden folgende Anforderungen für hochperformante Entwürfe (Top 10%) im Hinblick auf die Kaltluftförderung abgeleitet:".format(len(df)),
        "\n"
    ]

    for measure, label in T[LANG].items():
        if measure.startswith('MEASURE_'):
            measure_key = measure
            if measure_key in top_solutions.columns:
                mean_val = top_solutions[measure_key].mean()
                std_val = top_solutions[measure_key].std()
                min_val = top_solutions[measure_key].min()
                max_val = top_solutions[measure_key].max()

                report.append(f"- **{label}:** Optimale Ergebnisse wurden im Bereich von {min_val:.2f} bis {max_val:.2f} erzielt (Mittelwert: {mean_val:.2f} ± {std_val:.2f}).")

    return "\n".join(report)