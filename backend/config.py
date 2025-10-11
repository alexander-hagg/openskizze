from backend.translation import T
import numpy as np

QD_CONFIG = {
    'num_niches': 5,
    'num_generations': 100,  # Drastically reduced for a fast web demo
    'num_emitters': 5,      # Reduced for a fast web demo
    'sigma': 0.1,
    'learning_rate': 0.01,
    'output_inv_frequency': 100,
    'batch_size': 16,
}

ENCODING_CONFIG = {
    'max_num_buildings': 10,  # FIXED - always 10 buildings
    'xy_length': 32,  # Updated dynamically per parcel
    'z_length': 30,   # Max height in METERS (default 30m, can be updated from user constraints)
}

# Feature set definitions
# Two feature sets available:
# - 'original': The original 8 features (built area, height, variability, num buildings, distance, GFA, mass X/Y)
# - 'planning': Planning-focused features from BACKLOG.md (GRZ, GFZ, height, variability, num buildings, distance, aspect ratio, SVF)

FEATURE_SETS = {
    'original': {
        'name': 'Original Features',
        'name_de': 'Original-Merkmale',
        'features': [0, 1, 2, 3, 4, 5, 6, 7],  # Indices into calculate_all_features_original
        'description': 'Original 8-feature set',
    },
    'planning': {
        'name': 'Planning-Focused Features (BACKLOG)',
        'name_de': 'Planungs-Merkmale (BACKLOG)',
        'features': [0, 1, 2, 3, 4, 5, 6, 7],  # Indices into calculate_all_features_planning
        'description': 'GRZ, GFZ, height metrics, street canyon aspect ratio, SVF',
    }
}

DOMAIN_CONFIG = {
    'wind_direction': 180,
    'pixel_size_in_meters': 3,
    'feature_set': 'original',  # Default feature set
    'features': [0, 1, 2, 3, 4, 5, 6, 7],
    'labels': [T['DE'][f'MEASURE_{i}'] for i in range(8)],
    'feat_ranges': [
        [0.0, 0.15], [0.0, 3.0], [0.0, 6.0], 
        [0.0, 10.0], [0.0, 1.0], [0.0, 1.0], 
        [0.0, 1.0], [0.0, 1.0],
    ],
    'environment_border_size': 1.2,
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