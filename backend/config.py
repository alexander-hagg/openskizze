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
}

ENCODING_CONFIG = {
    'max_num_buildings': 10,  # FIXED - always 10 buildings
    'xy_length': 32,  # Updated dynamically per parcel
    'max_building_floors': 10,  # Maximum building height in FLOORS (e.g., 10 floors = 30m at 3m/floor)
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
    'wind_direction': 180,
    'pixel_size_in_meters': 3,
    'feature_set': 'consolidated',
    'features': [0, 1, 2, 3, 4, 5, 6, 7],
    'labels': [T['DE'][f'MEASURE_{i}'] for i in range(8)],
    'feat_ranges': [
        [0.0, 1.0],      # 0: GRZ (Site Coverage Ratio) - 0-100%
        [0.0, 5.0],      # 1: GFZ (Floor Area Ratio) - 0-5.0
        [0.0, 30.0],     # 2: Avg Height (m)
        [0.0, 15.0],     # 3: Height Variability (m)
        [0.0, 50.0],     # 4: Avg Distance (m)
        [0.0, 10.0],     # 5: Number of Buildings (count)
        [0.0, 2.0],      # 6: Compactness (A/V Ratio) - Lower is better
        [0.0, 50.0],     # 7: Park Factor (Max Green Circle Radius in m)
    ],
    'environment_border_size': 1.2,
}

SURROGATE_CONFIG = {
    'models_dir': 'models',
    # SVGP: Single model trained on square parcels, uses parcel width/length as input features
    # Works for ANY parcel size (parcel dimensions added to input)
    # Normalization stored IN checkpoint: 62D input (60 genome + 2 parcel dims) + scalar output
    'svgp_model_name': 'svgp.pth',
    # U-Net: Fixed input dimensions, need separate model per parcel size
    # Trained sizes (in bins): 27, 33, 39, 45, 51, 57, 63, 69, 75, 81, 87, 93, 99
    'available_parcel_sizes_unet': [27, 33, 39, 45, 51, 57, 63, 69, 75, 81, 87, 93, 99],
    # U-Net normalization: Size-specific (e.g., unet_81m_normalization.json)
    # Each parcel size may have different terrain/building statistics
    'default_ucb_lambda': 1.0,
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