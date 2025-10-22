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
    'max_building_floors': 10,  # Maximum building height in FLOORS (e.g., 10 floors = 30m at 3m/floor)
    'meters_per_floor': 3.0,  # Standard floor height in meters (used to convert floors → meters in phenotype)
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
        [0.0, 10000.0],  # 0: Built-up Area (m²) - up to 10,000 m²
        [0.0, 30.0],     # 1: Avg Height (m) - up to 30m
        [0.0, 15.0],     # 2: Height Variability (m) - up to 15m
        [0.0, 10.0],     # 3: Number of Buildings (count) - up to 10
        [0.0, 100.0],    # 4: Avg Distance (m) - up to 100m
        [0.0, 50000.0],  # 5: Gross Floor Area (m²) - up to 50,000 m²
        [0.0, 1.0],      # 6: Building Mass X-axis (normalized 0-1)
        [0.0, 1.0],      # 7: Building Mass Y-axis (normalized 0-1)
    ],
    'feat_ranges_planning': [
        [0.0, 1.0],      # 0: GRZ (Site Coverage Ratio) - FIXED 0-1 (0-100%)
        [0.0, 10.0],     # 1: GFZ (Floor Area Ratio) - FIXED 0-10
        [0.0, 30.0],     # 2: Avg Height (m) - up to 30m
        [0.0, 15.0],     # 3: Height Variability (m) - up to 15m
        [0.0, 10.0],     # 4: Number of Buildings (count) - up to 10
        [0.0, 100.0],    # 5: Avg Distance (m) - up to 100m
        [0.0, 5.0],      # 6: Street Canyon Aspect Ratio (H/W) - up to 5.0
        [0.0, 1.0],      # 7: Sky View Factor (SVF) - FIXED 0-1
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