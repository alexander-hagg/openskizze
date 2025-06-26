import time
import numpy as np
import pandas as pd

# This file contains MOCK functions for the optimization backend.
# In a real implementation, this would connect to the actual QD-algorithm.

def run_optimization_mock(site_polygon, taboo_zones, selected_measures, progress_callback):
    """
    A mock function that simulates a long-running QD optimization.
    It generates a plausible but fake 'result_archive'.
    """
    print("MOCK OPTIMIZATION: Starting...")
    print(f"Site Polygon defined: {'Yes' if site_polygon else 'No'}")
    print(f"Taboo Zones defined: {len(taboo_zones)}")
    print(f"Measures selected: {selected_measures}")

    num_generations = 50
    num_solutions_per_gen = 100

    archive_data = {
        'objective': [],
        'measures': {m: [] for m in selected_measures},
        'heightmaps': []
    }

    # Simulate the generation process
    for gen in range(num_generations):
        # Report progress back to the UI
        progress_callback(
            progress=int(((gen + 1) / num_generations) * 100),
            text=f"Generation: {gen+1}/{num_generations} | Lösungen im Archiv: {len(archive_data['objective'])}"
        )

        for _ in range(num_solutions_per_gen):
            # --- MOCK DATA GENERATION ---
            # Generate a fake objective score (cold airflow improvement)
            objective = np.random.uniform(-5, 25) # % improvement

            # Generate fake measures
            measures = {}
            if 'MEASURE_FOOTPRINT' in selected_measures:
                measures['MEASURE_FOOTPRINT'] = np.random.uniform(2000, 15000)
            if 'MEASURE_LIVING_SPACE' in selected_measures:
                measures['MEASURE_LIVING_SPACE'] = measures.get('MEASURE_FOOTPRINT', 10000) * np.random.uniform(1.5, 4.0)
            if 'MEASURE_DENSITY' in selected_measures:
                measures['MEASURE_DENSITY'] = np.random.uniform(0.4, 2.5)
            if 'MEASURE_PERMEABILITY' in selected_measures:
                measures['MEASURE_PERMEABILITY'] = np.random.uniform(0.1, 0.8)
            if 'MEASURE_OPEN_SPACE' in selected_measures:
                measures['MEASURE_OPEN_SPACE'] = 1.0 - measures.get('MEASURE_DENSITY', 0.8) * 0.8
            if 'MEASURE_NUM_BUILDINGS' in selected_measures:
                measures['MEASURE_NUM_BUILDINGS'] = np.random.randint(5, 50)

            # Generate a fake heightmap (e.g., 64x64 grid)
            heightmap = np.random.rand(64, 64) ** 3 * 15 # Simulate buildings
            # This is where taboo zones would be applied.
            # For now, we just generate a random map.

            # Add to archive
            archive_data['objective'].append(objective)
            for m_key, m_val in measures.items():
                archive_data['measures'][m_key].append(m_val)
            archive_data['heightmaps'].append(heightmap)

        time.sleep(0.1) # Simulate computation time

    print(f"MOCK OPTIMIZATION: Finished. Archive contains {len(archive_data['objective'])} solutions.")
    return archive_data