#
# backend/units.py
# Physical units and conversion utilities for features and objectives
#
import numpy as np
from backend.config import DOMAIN_CONFIG, ENCODING_CONFIG
from backend.translation import T

# Feature type definitions - Original feature set
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

# Feature type definitions - Planning-focused feature set
FEATURE_UNITS_PLANNING = {
    0: '',        # GRZ (Grundflächenzahl) - ratio 0-1
    1: '',        # GFZ (Geschossflächenzahl) - ratio
    2: 'm',       # Average Building Height
    3: 'm',       # Height Variability
    4: '',        # Number of Buildings (count)
    5: 'm',       # Average Building Distance
    6: '',        # Street Canyon Aspect Ratio (H/W)
    7: '',        # Sky View Factor (SVF) - 0-1
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
    z_length = ENCODING_CONFIG['z_length']  # Now in meters (e.g., 30m)
    
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
            
        elif feature_idx == 1:  # Average Height - already in meters
            physical_values[i] = val
            
        elif feature_idx == 2:  # Height Variability - already in meters
            physical_values[i] = val
            
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
    
    buildable_area_m2 = env_context.get('buildable_area_in_sq_meters', 1000)
    buildable_mask = env_context.get('buildable_mask')
    
    if buildable_mask is not None:
        grid_res = buildable_mask.shape[0]
        max_dist_pixels = np.sqrt(2) * grid_res
        max_dist_meters = max_dist_pixels * pixel_size
    else:
        max_dist_meters = 100
    
    # Get max height from environment context (already in meters)
    max_height_meters = env_context.get('max_height_meters', ENCODING_CONFIG['z_length'])
    
    for i, feature_idx in enumerate(feature_indices):
        val = physical_values[i] if i < len(physical_values) else 0.0
        
        if feature_idx == 0:  # Built Area m² -> ratio
            normalized_values[i] = val / buildable_area_m2 if buildable_area_m2 > 0 else 0.0
            
        elif feature_idx == 1:  # Height meters -> normalized by max height
            normalized_values[i] = val / max_height_meters if max_height_meters > 0 else 0.0
            
        elif feature_idx == 2:  # Height Variability meters -> normalized by max height/2
            normalized_values[i] = val / (max_height_meters / 2) if max_height_meters > 0 else 0.0
            
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


def get_unit_label(feature_index: int, lang='DE', feature_set='original') -> str:
    """
    Get the unit label for a feature.
    
    Args:
        feature_index: Index of the feature (0-7)
        lang: Language code ('DE' or 'EN')
        feature_set: 'original' or 'planning'
    
    Returns:
        Unit string (e.g., 'm²', 'm', '')
    """
    if feature_set == 'planning':
        unit_key = f'MEASURE_PLANNING_{feature_index}_UNIT'
    else:
        unit_key = f'MEASURE_{feature_index}_UNIT'
    return T[lang].get(unit_key, '')


def calculate_dynamic_ranges_physical(buildable_mask: np.ndarray, max_height_meters: int = None, min_distance_meters: float = None) -> list:
    """
    Calculate feature ranges in physical units based on site properties and hard constraints.
    
    Args:
        buildable_mask: Boolean array indicating buildable pixels
        max_height_meters: Maximum allowed building height in meters (from constraints)
        min_distance_meters: Minimum required distance between buildings in meters (from constraints)
    
    Returns:
        List of [min, max] ranges for each of the 8 features in physical units
    """
    pixel_size = DOMAIN_CONFIG['pixel_size_in_meters']
    z_length = ENCODING_CONFIG['z_length']  # In meters
    
    # If no max height constraint, use default z_length (in meters)
    if max_height_meters is None:
        max_height_meters = z_length
    
    # If no min distance constraint, use 0
    if min_distance_meters is None:
        min_distance_meters = 0.0
    
    buildable_pixels = np.sum(buildable_mask)
    buildable_area_m2 = buildable_pixels * (pixel_size ** 2)
    
    grid_res = buildable_mask.shape[0]
    max_dist_pixels = np.sqrt(2) * grid_res
    max_dist_meters = max_dist_pixels * pixel_size
    
    # Maximum possible floor area considering max height
    # Convert meters to floors (1 floor = 3m)
    max_floors = max_height_meters / 3.0
    max_possible_floor_area = buildable_area_m2 * max_floors
    
    ranges = [
        [0.0, buildable_area_m2],                # 0: Built Area (m²) - from 0 to full buildable area
        [0.0, max_height_meters],                # 1: Avg Height (m) - from 0 to max height constraint
        [0.0, max_height_meters / 2],            # 2: Height Variability (m) - roughly half of max
        [0.0, ENCODING_CONFIG['max_num_buildings']],  # 3: Number of Buildings (count)
        [min_distance_meters, max_dist_meters],  # 4: Avg Distance (m) - from min distance constraint to max diagonal
        [0.0, max_possible_floor_area],          # 5: Gross Floor Area (m²) - depends on max height constraint
        [0.0, 1.0],                              # 6: Building Mass X (normalized)
        [0.0, 1.0],                              # 7: Building Mass Y (normalized)
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
