# backend/config.py

# Configuration for the Quality-Diversity optimization algorithm
QD_CONFIG = {
    'num_niches': 5,
    'num_generations': 200, # Increased for a more thorough search
    'num_emitters': 25,
    'sigma': 0.3,
    'learning_rate': 0.01,
    'output_inv_frequency': 10,
    'batch_size': 32,
}

# Configuration for the parametric encoding
ENCODING_CONFIG = {
    'max_num_buildings': 5, 
    'xy_length': 64,
    'z_length': 3,
}

# Configuration for the domain and evaluation
DOMAIN_CONFIG = {
    'wind_direction': 180, # Default wind direction (South)
    'features': [0, 1, 2, 3, 4, 5, 6, 7],
    'labels': [
        'Building Coverage', 'Avg Building Height', 'Height Variability',
        'Num of Buildings', 'Avg Spacing', 'Floor Space Ratio',
        'Centroid X', 'Centroid Y'
    ],
    'feat_ranges': [
        [0.0, 1.0], [0.0, 10.0], [0.0, 4.0], [0.0, 20.0],
        [0.0, 32.0], [0.0, 3.0], [0.0, 32.0], [0.0, 32.0],
    ],
    'environment_border_size': 1.5,
}