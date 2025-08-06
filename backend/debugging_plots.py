# backend/debugging_plots.py

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
import os
from backend.config import ENCODING_CONFIG

def create_debug_plots(env_config: dict, sample_genome: np.ndarray, encoding_obj):
    """
    Generates and saves a series of PNG images to visualize the internal state
    of the optimization environment.
    """
    print("[DEBUG] Creating debug plots...")
    
    # Ensure the output directory exists
    output_dir = "debug_plots"
    os.makedirs(output_dir, exist_ok=True)
    
    # --- Data Preparation ---
    buildable_mask = env_config['buildable_mask']
    env_3d_fixed = env_config['env_3d_fixed']
    
    # 1. Generate a sample design
    sample_design_2d = encoding_obj.express(buildable_mask, sample_genome)
    
    # 2. Create the 3-zone visualization mask
    # Zone values: 0=Outside, 1=Buffer, 2=Taboo, 3=Buildable
    zone_map = np.ones_like(buildable_mask, dtype=int) # 1 for Buffer
    zone_map[~buildable_mask] = 2 # 2 for Taboo (within the square)
    zone_map[buildable_mask] = 3 # 3 for Buildable
    
    # 3. Create the combined 3D environment for fitness calculation
    design_3d = np.zeros_like(env_3d_fixed)
    for r in range(sample_design_2d.shape[0]):
        for c in range(sample_design_2d.shape[1]):
            h = int(sample_design_2d[r, c])
            if h > 0: design_3d[r, c, :h] = 1
    combined_env_3d = np.maximum(env_3d_fixed, design_3d)

    # --- Plotting ---
    # Define colors: Buffer=Orange, Taboo=Red, Buildable=White
    cmap = ListedColormap(['#FFC300', '#C70039', '#FFFFFF'])

    # Plot 1: The Buildable Area Mask (Requirement 2)
    plt.figure(figsize=(8, 8))
    plt.imshow(zone_map, cmap=cmap, origin='lower', vmin=1, vmax=3)
    plt.title("1. Buildable Area (White), Taboo (Red), Buffer (Orange)")
    plt.savefig(os.path.join(output_dir, "1_buildable_area_mask.png"))
    plt.close()

    # Plot 2: Existing Buildings in Context (Requirement 3)
    plt.figure(figsize=(8, 8))
    existing_buildings_2d = (np.sum(env_3d_fixed, axis=2) > 0).astype(int)
    plt.imshow(zone_map, cmap=cmap, origin='lower', vmin=1, vmax=3)
    plt.imshow(np.ma.masked_where(existing_buildings_2d == 0, existing_buildings_2d), 
               cmap='Greys', origin='lower', alpha=0.7)
    plt.title("2. Existing Buildings in Context")
    plt.savefig(os.path.join(output_dir, "2_existing_buildings.png"))
    plt.close()

    # Plot 3: Sample Generated Design (Requirement 1)
    plt.figure(figsize=(8, 8))
    plt.imshow(sample_design_2d, cmap='viridis', origin='lower', vmin=0, vmax=ENCODING_CONFIG['z_length'])
    plt.title("3. Sample Generated Design (Encoding Check)")
    plt.savefig(os.path.join(output_dir, "3_sample_generated_design.png"))
    plt.close()
    
    # Plot 4: Combined Environment for Fitness Calculation (Requirement 4)
    plt.figure(figsize=(8, 8))
    combined_env_2d = (np.sum(combined_env_3d, axis=2))
    plt.imshow(combined_env_2d, cmap='cividis', origin='lower')
    plt.title("4. Combined Scene for Porosity Calculation")
    plt.savefig(os.path.join(output_dir, "4_combined_for_fitness.png"))
    plt.close()

    # Plot 5: Area for Feature Calculation (Requirement 5)
    # This is identical to Plot 3, confirming features are calculated on the generated design only.
    plt.figure(figsize=(8, 8))
    plt.imshow(sample_design_2d, cmap='viridis', origin='lower', vmin=0, vmax=ENCODING_CONFIG['z_length'])
    plt.title("5. Area for Feature Calculation (Should be Generated Design Only)")
    plt.savefig(os.path.join(output_dir, "5_feature_calculation_area.png"))
    plt.close()
    
    print(f"[DEBUG] Debug plots saved to '{output_dir}' directory.")