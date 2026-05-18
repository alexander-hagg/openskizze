#
# backend/units.py
# Physical units and conversion utilities for features and objectives
#
import numpy as np
from backend.config import DOMAIN_CONFIG, ENCODING_CONFIG
from backend.translation import T

# Feature type definitions - Consolidated feature set (MVP)
FEATURE_UNITS = {
    0: '',        # GRZ (Site Coverage Ratio) - ratio 0-1
    1: '',        # GFZ (Floor Area Ratio) - ratio
    2: 'm',       # Average Building Height
    3: 'm',       # Height Variability
    4: 'm',       # Average Building Distance
    5: '',        # Number of Buildings (count)
    6: '1/m',     # Compactness (A/V Ratio)
    7: 'm',       # Park Factor (Green Space Radius)
}

def to_physical_units(normalized_values: np.ndarray, feature_indices: list, env_context: dict) -> np.ndarray:
    """
    Convert normalized feature values to physical units.
    
    Args:
        normalized_values: Array of normalized values [0-1 typically]
        feature_indices: List of feature indices being used
        env_context: Dictionary containing:
            - buildable_area_in_sq_meters: float
            - buildable_mask: np.ndarray
            - pixel_size_in_meters: float (from DOMAIN_CONFIG)
            - z_length: int (from ENCODING_CONFIG)
    
    Returns:
        Array of values in physical units
    """
    physical_values = np.zeros_like(normalized_values)
    pixel_size = DOMAIN_CONFIG['pixel_size_in_meters']
    max_height_meters = int(ENCODING_CONFIG['max_building_floors'] * ENCODING_CONFIG['meters_per_floor'])
    
    buildable_mask = env_context.get('buildable_mask')
    
    # Calculate grid dimensions for distance normalization
    if buildable_mask is not None:
        grid_res = buildable_mask.shape[0]
        max_dist_pixels = np.sqrt(2) * grid_res  # Diagonal distance
        max_dist_meters = max_dist_pixels * pixel_size
    else:
        max_dist_meters = 100  # Fallback
    
    # Max GFZ estimation (approximate max possible floor area ratio)
    max_gfz = (max_height_meters / 3.0)  # If entire site was built to max height
    
    for i, feature_idx in enumerate(feature_indices):
        val = normalized_values[i] if i < len(normalized_values) else 0.0
        
        if feature_idx == 0:  # GRZ - ratio 0-1
            physical_values[i] = val
            
        elif feature_idx == 1:  # GFZ - ratio (normalized to max possible GFZ)
            physical_values[i] = val * max_gfz
            
        elif feature_idx == 2:  # Average Height - normalized to max height
            physical_values[i] = val * max_height_meters
            
        elif feature_idx == 3:  # Height Variability - normalized to max height/2
            physical_values[i] = val * (max_height_meters / 2)
            
        elif feature_idx == 4:  # Average Distance - normalized to max diagonal
            physical_values[i] = val * max_dist_meters
            
        elif feature_idx == 5:  # Number of Buildings - normalized to max count
            physical_values[i] = val * ENCODING_CONFIG['max_num_buildings']
            
        elif feature_idx == 6:  # Compactness - normalized to 2.0 (approx max A/V)
            physical_values[i] = val * 2.0
            
        elif feature_idx == 7:  # Park Factor - normalized to max diagonal
            physical_values[i] = val * max_dist_meters
            
        else:
            physical_values[i] = val
    
    return physical_values


def from_physical_units(physical_values: np.ndarray, feature_indices: list, env_context: dict) -> np.ndarray:
    """
    Convert physical unit values back to normalized values for the optimizer.
    
    Args:
        physical_values: Array of values in physical units
        feature_indices: List of feature indices being used
        env_context: Dictionary containing environment context
    
    Returns:
        Array of normalized values
    """
    normalized_values = np.zeros_like(physical_values)
    pixel_size = DOMAIN_CONFIG['pixel_size_in_meters']
    
    buildable_mask = env_context.get('buildable_mask')
    
    if buildable_mask is not None:
        grid_res = buildable_mask.shape[0]
        max_dist_pixels = np.sqrt(2) * grid_res
        max_dist_meters = max_dist_pixels * pixel_size
    else:
        max_dist_meters = 100
    
    default_max_height_meters = int(ENCODING_CONFIG['max_building_floors'] * ENCODING_CONFIG['meters_per_floor'])
    max_height_meters = env_context.get('max_height_meters', default_max_height_meters)
    max_gfz = (max_height_meters / 3.0)
    
    for i, feature_idx in enumerate(feature_indices):
        val = physical_values[i] if i < len(physical_values) else 0.0
        
        if feature_idx == 0:  # GRZ - already 0-1
            normalized_values[i] = val
            
        elif feature_idx == 1:  # GFZ
            normalized_values[i] = val / max_gfz if max_gfz > 0 else 0.0
            
        elif feature_idx == 2:  # Height
            normalized_values[i] = val / max_height_meters if max_height_meters > 0 else 0.0
            
        elif feature_idx == 3:  # Height Variability
            normalized_values[i] = val / (max_height_meters / 2) if max_height_meters > 0 else 0.0
            
        elif feature_idx == 4:  # Distance
            normalized_values[i] = val / max_dist_meters if max_dist_meters > 0 else 0.0
            
        elif feature_idx == 5:  # Number of Buildings
            normalized_values[i] = val / ENCODING_CONFIG['max_num_buildings']
            
        elif feature_idx == 6:  # Compactness
            normalized_values[i] = val / 2.0
            
        elif feature_idx == 7:  # Park Factor
            normalized_values[i] = val / max_dist_meters if max_dist_meters > 0 else 0.0
            
        else:
            normalized_values[i] = val
    
    return normalized_values


def format_value_with_unit(value: float, feature_index: int, lang='DE', decimals=2) -> str:
    """
    Format a value with its appropriate unit.
    """
    unit_key = f'MEASURE_{feature_index}_UNIT'
    unit = T[lang].get(unit_key, '')
    
    if feature_index == 5:  # Number of Buildings - no decimals
        return f"{int(value)}"
    elif feature_index == 6:  # Compactness - 2 decimals
        return f"{value:.2f} {unit}"
    elif unit == 'm':  # Distances/heights - 1-2 decimals
        return f"{value:.1f} {unit}"
    elif unit:
        return f"{value:.{decimals}f} {unit}"
    else:
        return f"{value:.{decimals}f}"


def get_unit_label(feature_index: int, lang='DE', feature_set='consolidated') -> str:
    """
    Get the unit label for a feature.
    """
    unit_key = f'MEASURE_{feature_index}_UNIT'
    return T[lang].get(unit_key, '')


def calculate_dynamic_ranges_physical(buildable_mask: np.ndarray, max_height_meters: int = None, min_distance_meters: float = None) -> list:
    """
    Calculate feature ranges in physical units based on site properties and hard constraints.
    """
    pixel_size = DOMAIN_CONFIG['pixel_size_in_meters']
    default_max_height_meters = int(ENCODING_CONFIG['max_building_floors'] * ENCODING_CONFIG['meters_per_floor'])
    
    if max_height_meters is None:
        max_height_meters = default_max_height_meters
    
    if min_distance_meters is None:
        min_distance_meters = 0.0
    
    grid_res = buildable_mask.shape[0]
    max_dist_pixels = np.sqrt(2) * grid_res
    max_dist_meters = max_dist_pixels * pixel_size
    
    # Max GFZ estimation
    max_floors = max_height_meters / 3.0
    
    ranges = [
        [0.0, 1.0],                              # 0: GRZ (ratio)
        [0.0, max_floors],                       # 1: GFZ (ratio)
        [0.0, max_height_meters],                # 2: Avg Height (m)
        [0.0, max_height_meters / 2],            # 3: Height Variability (m)
        [min_distance_meters, max_dist_meters],  # 4: Avg Distance (m)
        [0.0, ENCODING_CONFIG['max_num_buildings']],  # 5: Number of Buildings (count)
        [0.0, 2.0],                              # 6: Compactness (1/m)
        [0.0, max_dist_meters / 2],              # 7: Park Factor (m) - usually less than full diagonal
    ]
    
    return ranges


def format_range_with_unit(min_val: float, max_val: float, feature_index: int, lang='DE') -> str:
    """
    Format a range with its appropriate unit for display.
    
    Args:
        min_val: Minimum value
        max_val: Maximum value
        feature_index: Index of the feature (0-7)
        lang: Language code ('DE' or 'EN')
    
    Returns:
        Formatted string like "0 - 500 m²"
    """
    unit = get_unit_label(feature_index, lang)
    
    if feature_index == 3:  # Number of Buildings
        return f"{int(min_val)} - {int(max_val)}"
    elif feature_index in [6, 7]:  # Normalized positions
        return f"{min_val:.2f} - {max_val:.2f}"
    elif unit == 'm²':
        return f"{min_val:.0f} - {max_val:.0f} {unit}"
    elif unit == 'm':
        return f"{min_val:.1f} - {max_val:.1f} {unit}"
    elif unit:
        return f"{min_val:.1f} - {max_val:.1f} {unit}"
    else:
        return f"{min_val:.2f} - {max_val:.2f}"
