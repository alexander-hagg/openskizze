from backend.translation import T

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
    'max_num_buildings': 10,
    'xy_length': 32, # This can be dynamically updated
    'z_length': 3,
}

DOMAIN_CONFIG = {
    'wind_direction': 180,
    'pixel_size_in_meters': 3,
    'features': [0, 1, 2, 3, 4, 5, 6, 7],
    'labels': [T['DE'][f'MEASURE_{i}'] for i in range(8)],
    # 'feat_ranges': [
    #     [0.0, 0.15], [0.0, 9.0], [0.0, 6.0], 
    #     [0.0, 5.0], [0.0, 60.0], [0.0, 0.3], 
    #     [0.0, 60.0], [0.0, 60.0],
    # ],
    'feat_ranges': [
        [0.0, 0.15], [0.0, 3.0], [0.0, 6.0], 
        [0.0, 10.0], [0.0, 1.0], [0.0, 1.0], 
        [0.0, 1.0], [0.0, 1.0],
    ],
    'environment_border_size': 1.2,
}