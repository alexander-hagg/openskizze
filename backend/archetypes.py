#!/usr/bin/env python3
"""
Archetypical Urban Design Patterns for Model Diagnostics

Provides 6 predefined building layout patterns for testing and comparing
objective functions (porosity, street_canyon, SVGP, U-Net).

All archetypes use a fixed 27×27 grid (81m × 81m at 3m/pixel).

IMPORTANT: Archetypes are created THROUGH THE ENCODING MECHANISM
using genomes that express to the desired building layouts.
"""

import numpy as np
from typing import Dict, List, Tuple
from scipy.special import erfinv


GRID_SIZE = 27  # cells (= 81m at 3m/pixel)
PIXEL_SIZE = 3.0  # meters
PARCEL_SIZE = 81  # meters


def uniform_to_normal(u: float) -> float:
    """Convert uniform [0,1] value to normal distribution value (inverse CDF)."""
    # Clamp to avoid inf at boundaries
    u = np.clip(u, 0.001, 0.999)
    # Inverse of Φ(z) = 0.5 * (1 + erf(z / sqrt(2)))
    return np.sqrt(2) * erfinv(2 * u - 1)


def create_genome_from_buildings(buildings: List[dict]) -> np.ndarray:
    """
    Create a 60-gene genome from a list of building specifications.
    
    Each building dict has:
    - x: center x position (0-1 normalized)
    - y: center y position (0-1 normalized)  
    - width: width (0-1 normalized, actual = value * grid_size)
    - length: length (0-1 normalized, actual = value * grid_size)
    - height: height in floors (0-1 normalized, actual = value * 10 floors)
    - active: whether building is active (> 0.5 = active)
    
    Returns:
        genome: (60,) array in normal distribution space
    """
    genome_uniform = np.zeros(60)
    
    for i, bldg in enumerate(buildings[:10]):  # Max 10 buildings
        j = i * 6
        genome_uniform[j + 0] = bldg.get('width', 0.0)
        genome_uniform[j + 1] = bldg.get('length', 0.0)
        genome_uniform[j + 2] = bldg.get('height', 0.0)
        genome_uniform[j + 3] = bldg.get('x', 0.5)
        genome_uniform[j + 4] = bldg.get('y', 0.5)
        genome_uniform[j + 5] = bldg.get('active', 0.0)
    
    # Convert uniform [0,1] to normal distribution space
    genome_normal = np.array([uniform_to_normal(u) for u in genome_uniform])
    
    return genome_normal


def get_all_archetypes() -> Dict[str, Tuple[np.ndarray, np.ndarray]]:
    """
    Get all 6 archetypical building layouts as (genome, heightmap) pairs.
    
    Returns:
        Dictionary mapping archetype name to (genome, heightmap) tuple
        - genome: (60,) array in normal distribution space
        - heightmap: (27, 27) array in meters
    """
    from backend.fast_encoding import NumbaFastEncoding
    
    encoding = NumbaFastEncoding(parcel_size=PARCEL_SIZE)
    
    archetypes = {}
    
    for name in get_archetype_list():
        genome = get_archetype_genome(name)
        heightmap = encoding.express_batch(genome.reshape(1, -1))[0]
        archetypes[name] = (genome, heightmap)
    
    return archetypes


def get_archetype_genomes() -> Dict[str, np.ndarray]:
    """Get only the genomes for all archetypes."""
    return {name: get_archetype_genome(name) for name in get_archetype_list()}


def get_archetype_heightmaps() -> Dict[str, np.ndarray]:
    """Get only the heightmaps for all archetypes."""
    archetypes = get_all_archetypes()
    return {name: data[1] for name, data in archetypes.items()}


def get_archetype_list() -> List[str]:
    """Get ordered list of archetype names."""
    return ['empty', 'square', 'two_squares', 'two_squares_rotated', 'u_shape', 'u_shape_rotated', 'grid', 'street_canyon', 'street_canyon_rotated']


def get_archetype_genome(name: str) -> np.ndarray:
    """Get genome for a specific archetype."""
    if name == 'empty':
        return create_empty_genome()
    elif name == 'square':
        return create_square_genome()
    elif name == 'two_squares':
        return create_two_squares_genome()
    elif name == 'two_squares_rotated':
        return create_two_squares_rotated_genome()
    elif name == 'u_shape':
        return create_u_shape_genome()
    elif name == 'u_shape_rotated':
        return create_u_shape_rotated_genome()
    elif name == 'grid':
        return create_grid_genome()
    elif name == 'street_canyon':
        return create_street_canyon_genome()
    elif name == 'street_canyon_rotated':
        return create_street_canyon_rotated_genome()
    else:
        raise ValueError(f"Unknown archetype: {name}")


def create_empty_genome() -> np.ndarray:
    """Empty parcel - no buildings (all inactive)."""
    buildings = []  # No buildings
    return create_genome_from_buildings(buildings)


def create_square_genome() -> np.ndarray:
    """
    Single centered square building.
    Size: ~12m × 12m (width=0.44 * 27 ≈ 12 cells)
    Height: 12m (4 floors, height=0.4)
    """
    buildings = [
        {'x': 0.5, 'y': 0.5, 'width': 0.44, 'length': 0.44, 'height': 0.4, 'active': 0.9}
    ]
    return create_genome_from_buildings(buildings)


def create_two_squares_genome() -> np.ndarray:
    """
    Two square buildings side-by-side with gap.
    Each: ~9m × 9m, Height: 12m (4 floors)
    Gap: ~12m between centers
    """
    buildings = [
        {'x': 0.33, 'y': 0.5, 'width': 0.33, 'length': 0.33, 'height': 0.4, 'active': 0.9},
        {'x': 0.67, 'y': 0.5, 'width': 0.33, 'length': 0.33, 'height': 0.4, 'active': 0.9},
    ]
    return create_genome_from_buildings(buildings)


def create_two_squares_rotated_genome() -> np.ndarray:
    """
    Two square buildings top-to-bottom with gap (rotated 90°).
    Each: ~9m × 9m, Height: 12m (4 floors)
    Gap: ~12m between centers
    """
    buildings = [
        {'x': 0.5, 'y': 0.33, 'width': 0.33, 'length': 0.33, 'height': 0.4, 'active': 0.9},
        {'x': 0.5, 'y': 0.67, 'width': 0.33, 'length': 0.33, 'height': 0.4, 'active': 0.9},
    ]
    return create_genome_from_buildings(buildings)


def create_u_shape_genome() -> np.ndarray:
    """
    U-shaped courtyard building using 3 connected blocks.
    Height: 15m (5 floors)
    Opens to the east (wind from west can flow into courtyard)
    """
    buildings = [
        # Left vertical arm
        {'x': 0.25, 'y': 0.5, 'width': 0.18, 'length': 0.55, 'height': 0.5, 'active': 0.9},
        # Bottom horizontal arm  
        {'x': 0.5, 'y': 0.25, 'width': 0.55, 'length': 0.18, 'height': 0.5, 'active': 0.9},
        # Top horizontal arm
        {'x': 0.5, 'y': 0.75, 'width': 0.55, 'length': 0.18, 'height': 0.5, 'active': 0.9},
    ]
    return create_genome_from_buildings(buildings)


def create_u_shape_rotated_genome() -> np.ndarray:
    """
    U-shaped courtyard building rotated 180° (opens to the west).
    Height: 15m (5 floors)
    Opens to the west (wind from east can flow into courtyard)
    """
    buildings = [
        # Right vertical arm
        {'x': 0.75, 'y': 0.5, 'width': 0.18, 'length': 0.55, 'height': 0.5, 'active': 0.9},
        # Bottom horizontal arm
        {'x': 0.5, 'y': 0.25, 'width': 0.55, 'length': 0.18, 'height': 0.5, 'active': 0.9},
        # Top horizontal arm
        {'x': 0.5, 'y': 0.75, 'width': 0.55, 'length': 0.18, 'height': 0.5, 'active': 0.9},
    ]
    return create_genome_from_buildings(buildings)


def create_grid_genome() -> np.ndarray:
    """
    Grid pattern - 3×3 array of small buildings.
    Each building: ~6m × 6m (2 cells)
    Height: 9m (3 floors)
    """
    buildings = []
    for i in range(3):
        for j in range(3):
            x = 0.25 + i * 0.25  # 0.25, 0.5, 0.75
            y = 0.25 + j * 0.25  # 0.25, 0.5, 0.75
            buildings.append({
                'x': x, 'y': y, 
                'width': 0.15, 'length': 0.15, 
                'height': 0.3, 'active': 0.9
            })
    return create_genome_from_buildings(buildings[:10])  # Max 10 buildings


def create_street_canyon_genome() -> np.ndarray:
    """
    Street canyon - two parallel bars perpendicular to wind.
    Each bar: ~60m long × 9m wide
    Height: 18m (6 floors)
    Gap: ~18m (street canyon)
    Wind flows through the canyon (perpendicular to bars)
    """
    buildings = [
        # North bar (top)
        {'x': 0.5, 'y': 0.7, 'width': 0.85, 'length': 0.15, 'height': 0.6, 'active': 0.9},
        # South bar (bottom)
        {'x': 0.5, 'y': 0.3, 'width': 0.85, 'length': 0.15, 'height': 0.6, 'active': 0.9},
    ]
    return create_genome_from_buildings(buildings)


def create_street_canyon_rotated_genome() -> np.ndarray:
    """
    Street canyon rotated 90° - two parallel bars running north-south.
    Each bar: ~60m long × 9m wide
    Height: 18m (6 floors)
    Gap: ~18m (street canyon)
    Wind flows through the canyon (parallel to bars)
    """
    buildings = [
        # East bar (right)
        {'x': 0.7, 'y': 0.5, 'width': 0.15, 'length': 0.85, 'height': 0.6, 'active': 0.9},
        # West bar (left)
        {'x': 0.3, 'y': 0.5, 'width': 0.15, 'length': 0.85, 'height': 0.6, 'active': 0.9},
    ]
    return create_genome_from_buildings(buildings)


def get_archetype_description(name: str, lang: str = 'EN') -> str:
    """
    Get human-readable description of archetype.
    
    Args:
        name: Archetype name
        lang: 'DE' or 'EN'
    
    Returns:
        Description string
    """
    descriptions = {
        'DE': {
            'empty': 'Leere Parzelle ohne Bebauung',
            'square': 'Einzelnes zentrales Gebäude (~12m×12m, 12m hoch)',
            'two_squares': 'Zwei separate Gebäude mit Lücke (je ~9m×9m)',
            'two_squares_rotated': 'Zwei separate Gebäude vertikal (90° gedreht)',
            'u_shape': 'U-förmige Hofbebauung (15m hoch, öffnet nach Osten)',
            'u_shape_rotated': 'U-förmige Hofbebauung (180° gedreht, öffnet nach Westen)',
            'grid': '3×3 Raster kleiner Gebäude (je ~6m×6m, 9m hoch)',
            'street_canyon': 'Straßenschlucht mit zwei parallelen Riegeln (18m hoch)',
            'street_canyon_rotated': 'Straßenschlucht (90° gedreht, Nord-Süd-Ausrichtung)'
        },
        'EN': {
            'empty': 'Empty parcel with no buildings',
            'square': 'Single centered building (~12m×12m, 12m tall)',
            'two_squares': 'Two separate buildings with gap (~9m×9m each)',
            'two_squares_rotated': 'Two separate buildings vertical (rotated 90°)',
            'u_shape': 'U-shaped courtyard building (15m tall, opens eastward)',
            'u_shape_rotated': 'U-shaped courtyard (rotated 180°, opens westward)',
            'grid': '3×3 grid of small buildings (~6m×6m each, 9m tall)',
            'street_canyon': 'Street canyon with two parallel bars (18m tall)',
            'street_canyon_rotated': 'Street canyon (rotated 90°, north-south orientation)'
        }
    }
    
    return descriptions.get(lang, descriptions['EN']).get(name, 'Unknown archetype')
