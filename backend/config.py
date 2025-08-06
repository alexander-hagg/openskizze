# backend/config.py (Corrected for Web Performance)

QD_CONFIG = {
    'num_niches': 4,
    'num_generations': 300,  # Drastically reduced for a fast web demo
    'num_emitters': 4,      # Reduced for a fast web demo
    'sigma': 0.1,
    'learning_rate': 0.01,
    'output_inv_frequency': 5, # More frequent updates
    'batch_size': 20,
}

ENCODING_CONFIG = {
    'max_num_buildings': 5,
    'xy_length': 32, # This can be dynamically updated
    'z_length': 10,
}

DOMAIN_CONFIG = {
    'wind_direction': 180,
    'pixel_size_in_meters': 3,
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