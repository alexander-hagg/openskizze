#
# backend/units.py
# Physical units and conversion utilities for features and objectives
#
import numpy as np
from backend.config import DOMAIN_CONFIG, ENCODING_CONFIG
from backend.translation import T

# Feature type definitions
FEATURE_UNITS = {
    0: 'm²',      # Built Area (bebaute Fläche)
    1: 'm',       # Average Building Height
    2: 'm',       # Height Variability
    3: '',        # Number of Buildings (count)
    4: 'm',       # Average Building Distance
    5: 'm²',      # Gross Floor Area (Brutto-Grundfläche)
    6: '',        # Building Mass X-Axis (normalized)
    7: '',        # Building Mass Y-Axis (normalized)
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
    z_length = ENCODING_CONFIG['z_length']
    meters_per_floor = 3.0  # Approximate 3m per floor
    
    buildable_area_m2 = env_context.get('buildable_area_in_sq_meters', 1000)
    buildable_mask = env_context.get('buildable_mask')
    
    # Calculate grid dimensions for distance normalization
    if buildable_mask is not None:
        grid_res = buildable_mask.shape[0]
        max_dist_pixels = np.sqrt(2) * grid_res  # Diagonal distance
        max_dist_meters = max_dist_pixels * pixel_size
    else:
        max_dist_meters = 100  # Fallback
    
    for i, feature_idx in enumerate(feature_indices):
        val = normalized_values[i] if i < len(normalized_values) else 0.0
        
        if feature_idx == 0:  # Built Area - convert ratio to m²
            physical_values[i] = val * buildable_area_m2
            
        elif feature_idx == 1:  # Average Height - convert floors to meters
            physical_values[i] = val * meters_per_floor
            
        elif feature_idx == 2:  # Height Variability - convert floors to meters
            physical_values[i] = val * meters_per_floor
            
        elif feature_idx == 3:  # Number of Buildings - already a count
            physical_values[i] = val
            
        elif feature_idx == 4:  # Average Distance - convert normalized to meters
            physical_values[i] = val * max_dist_meters
            
        elif feature_idx == 5:  # Gross Floor Area (FSR) - convert ratio to m²
            # FSR is (total floor area) / (buildable area)
            # So total floor area = FSR * buildable area
            physical_values[i] = val * buildable_area_m2
            
        elif feature_idx == 6:  # Building Mass X - keep normalized (0-1)
            physical_values[i] = val
            
        elif feature_idx == 7:  # Building Mass Y - keep normalized (0-1)
            physical_values[i] = val
            
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
    meters_per_floor = 3.0
    
    buildable_area_m2 = env_context.get('buildable_area_in_sq_meters', 1000)
    buildable_mask = env_context.get('buildable_mask')
    
    if buildable_mask is not None:
        grid_res = buildable_mask.shape[0]
        max_dist_pixels = np.sqrt(2) * grid_res
        max_dist_meters = max_dist_pixels * pixel_size
    else:
        max_dist_meters = 100
    
    for i, feature_idx in enumerate(feature_indices):
        val = physical_values[i] if i < len(physical_values) else 0.0
        
        if feature_idx == 0:  # Built Area m² -> ratio
            normalized_values[i] = val / buildable_area_m2 if buildable_area_m2 > 0 else 0.0
            
        elif feature_idx == 1:  # Height meters -> floors
            normalized_values[i] = val / meters_per_floor
            
        elif feature_idx == 2:  # Height Variability meters -> floors
            normalized_values[i] = val / meters_per_floor
            
        elif feature_idx == 3:  # Number of Buildings - already a count
            normalized_values[i] = val
            
        elif feature_idx == 4:  # Distance meters -> normalized
            normalized_values[i] = val / max_dist_meters if max_dist_meters > 0 else 0.0
            
        elif feature_idx == 5:  # Gross Floor Area m² -> FSR
            normalized_values[i] = val / buildable_area_m2 if buildable_area_m2 > 0 else 0.0
            
        elif feature_idx == 6:  # Building Mass X - keep normalized
            normalized_values[i] = val
            
        elif feature_idx == 7:  # Building Mass Y - keep normalized
            normalized_values[i] = val
            
        else:
            normalized_values[i] = val
    
    return normalized_values


def format_value_with_unit(value: float, feature_index: int, lang='DE', decimals=2) -> str:
    """
    Format a value with its appropriate unit.
    
    Args:
        value: The numeric value
        feature_index: Index of the feature (0-7)
        lang: Language code ('DE' or 'EN')
        decimals: Number of decimal places
    
    Returns:
        Formatted string with value and unit
    """
    unit_key = f'MEASURE_{feature_index}_UNIT'
    unit = T[lang].get(unit_key, '')
    
    # Special formatting for different feature types
    if feature_index == 3:  # Number of Buildings - no decimals
        return f"{int(value)}"
    elif feature_index in [6, 7]:  # Normalized positions - show as percentage or 3 decimals
        return f"{value:.3f}"
    elif unit == 'm²':  # Areas - no decimals or 1 decimal
        if value < 10:
            return f"{value:.1f} {unit}"
        else:
            return f"{value:.0f} {unit}"
    elif unit == 'm':  # Distances/heights - 1-2 decimals
        return f"{value:.1f} {unit}"
    elif unit:
        return f"{value:.{decimals}f} {unit}"
    else:
        return f"{value:.{decimals}f}"


def get_unit_label(feature_index: int, lang='DE') -> str:
    """
    Get the unit label for a feature.
    
    Args:
        feature_index: Index of the feature (0-7)
        lang: Language code ('DE' or 'EN')
    
    Returns:
        Unit string (e.g., 'm²', 'm', '')
    """
    unit_key = f'MEASURE_{feature_index}_UNIT'
    return T[lang].get(unit_key, '')


def calculate_dynamic_ranges_physical(buildable_mask: np.ndarray, max_height_floors: int = None) -> list:
    """
    Calculate feature ranges in physical units based on site properties.
    
    Args:
        buildable_mask: Boolean array indicating buildable pixels
        max_height_floors: Maximum allowed building height in floors (from constraints)
    
    Returns:
        List of [min, max] ranges for each of the 8 features in physical units
    """
    pixel_size = DOMAIN_CONFIG['pixel_size_in_meters']
    z_length = ENCODING_CONFIG['z_length']
    meters_per_floor = 3.0
    
    # If no max height constraint, use default z_length
    if max_height_floors is None:
        max_height_floors = z_length
    
    buildable_pixels = np.sum(buildable_mask)
    buildable_area_m2 = buildable_pixels * (pixel_size ** 2)
    
    grid_res = buildable_mask.shape[0]
    max_dist_pixels = np.sqrt(2) * grid_res
    max_dist_meters = max_dist_pixels * pixel_size
    
    # Maximum possible floor area considering max height
    max_possible_floor_area = buildable_area_m2 * max_height_floors
    
    ranges = [
        [0.0, buildable_area_m2],                    # 0: Built Area (m²) - from 0 to full buildable area
        [0.0, max_height_floors * meters_per_floor], # 1: Avg Height (m) - from 0 to max height in meters
        [0.0, max_height_floors * meters_per_floor / 2], # 2: Height Variability (m) - roughly half of max
        [0.0, ENCODING_CONFIG['max_num_buildings']],  # 3: Number of Buildings (count)
        [0.0, max_dist_meters],                      # 4: Avg Distance (m) - from 0 to max diagonal
        [0.0, max_possible_floor_area],              # 5: Gross Floor Area (m²) - depends on max height!
        [0.0, 1.0],                                  # 6: Building Mass X (normalized)
        [0.0, 1.0],                                  # 7: Building Mass Y (normalized)
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
