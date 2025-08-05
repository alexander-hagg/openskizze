# backend/config.py (Corrected)

# Configuration for the Quality-Diversity optimization algorithm
QD_CONFIG = {
    'num_niches': 4,        # FIX: Reduced from 10 to prevent memory errors
    'num_generations': 100,
    'num_emitters': 5,
    'sigma': 0.1,
    'learning_rate': 0.01,
    'output_inv_frequency': 10,
    'batch_size': 32,
}

# Configuration for the parametric encoding
ENCODING_CONFIG = {
    'max_num_buildings': 5,
    'xy_length': 32,
    'z_length': 10,
}

# Configuration for the domain and evaluation
DOMAIN_CONFIG = {
    'wind_direction': 0, # Default wind direction (North) if not provided by UI
    'features': [0, 1, 2, 3, 4, 5, 6, 7],
    'labels': [
        'Building Coverage', 'Avg Building Height', 'Height Variability',
        'Num of Buildings', 'Avg Spacing', 'Floor Space Ratio',
        'Centroid X', 'Centroid Y'
    ],
    'feat_ranges': [
        [0.0, 1.0], [1.0, 3.0], [0.0, 1.0], 
        [1.0, 5.0], [0.0, 10.0], [0.0, 1.0], 
        [0.0, 10.0], [0.0, 10.0],
    ],
    'environment_border_size': 1.5,
}