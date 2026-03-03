from backend.translation import T
import numpy as np

QD_CONFIG = {
    'num_niches': 5,
    'num_generations': 100,  # Drastically reduced for a fast web demo
    'num_emitters': 10,      # Reduced for a fast web demo
    'sigma': 0.15,
    'learning_rate': 0.02,
    'output_inv_frequency': 100,
    'batch_size': 64,
    'live_update_interval': 10,  # Update progress every 10 generations
}

ENCODING_CONFIG = {
    'max_num_buildings': 10,  # FIXED - always 10 buildings
    'xy_length': 32,  # Updated dynamically per parcel
    'max_building_floors': 4,  # Default maximum building height in FLOORS (e.g., 4 floors = 12m at 3m/floor)
    'meters_per_floor': 3.0,  # Standard floor height in meters (used to convert floors → meters in phenotype)
}

# Feature set definitions
# Consolidated feature set for MVP (GRZ, GFZ, Height, Var, Dist, Count, Compactness, Park Factor)
FEATURE_SETS = {
    'consolidated': {
        'name': 'Consolidated Features (MVP)',
        'name_de': 'Konsolidierte Merkmale (MVP)',
        'features': [0, 1, 2, 3, 4, 5, 6, 7],
        'description': 'GRZ, GFZ, Height, Var, Dist, Count, Compactness, Park Factor',
    }
}

DOMAIN_CONFIG = {
    'wind_direction': 270,  # West wind direction (not used with pure katabatic flow, wind_speed=0)
    'pixel_size_in_meters': 3,
    'feature_set': 'consolidated',
    'features': [0, 1, 2, 3, 4, 5, 6, 7],
    'labels': [T['DE'][f'MEASURE_{i}'] for i in range(8)],
    'feat_ranges': [
        [0.0, 1.0],      # 0: GRZ (Site Coverage Ratio) - 0-100%
        [0.0, 3.0],      # 1: GFZ (Floor Area Ratio) - 0-3.0 (matches training data)
        [0.0, 15.0],     # 2: Avg Height (m) - matches training data max
        [0.0, 8.0],      # 3: Height Variability (m) - matches training data
        [0.0, 50.0],     # 4: Avg Distance (m)
        [0.0, 10.0],     # 5: Number of Buildings (count)
        [0.0, 2.0],      # 6: Compactness (A/V Ratio) - Lower is better
        [0.0, 30.0],     # 7: Park Factor (Max Green Circle Radius in m) - matches training data
    ],
    'environment_border_size': 1.2,
}

SURROGATE_CONFIG = {
    'models_dir': 'models',
    # U-Net: Fixed input dimensions, trained on specific parcel sizes
    # Values are in METERS. Only 60m model available.
    # Parcels <= 60m use U-Net (smaller parcels are zero-padded).
    # Parcels > 60m fall back to geometric methods.
    'available_parcel_sizes_unet_m': [60],
    'default_model_type': 'street_canyon',
}


def calculate_adaptive_phenotype_config(buildable_mask: np.ndarray, 
                                        buildable_area_m2: float,
                                        grid_res: int) -> dict:
    """
    Calculate adaptive phenotype parameters (grid size only).
    Genome encoding stays FIXED at 10 buildings, 60 genes.
    
    Args:
        buildable_mask: Boolean array of buildable cells
        buildable_area_m2: Buildable area in square meters
        grid_res: Grid resolution (number of cells per side)
    
    Returns:
        Dictionary with adaptive parameters for display/logging
    """
    pixel_size = DOMAIN_CONFIG['pixel_size_in_meters']
    buildable_pixels = int(np.sum(buildable_mask))
    buildable_ratio = buildable_pixels / (grid_res ** 2) if grid_res > 0 else 0.0
    
    return {
        'xy_length': grid_res,
        'parcel_area_m2': buildable_area_m2,
        'grid_size_meters': grid_res * pixel_size,
        'buildable_pixels': buildable_pixels,
        'buildable_ratio': buildable_ratio,
        'pixel_size': pixel_size,
    }