#!/usr/bin/env python3
"""
End-to-End Performance Benchmark - Parcel Size Impact Analysis

This benchmark tests the COMPLETE evaluation pipeline across different parcel sizes:
- 50m × 50m (small urban plot)
- 100m × 100m (medium block)
- 500m × 500m (large development area)

For each parcel size, tests:
1. Phenotype creation (genotype → heightmap)
2. Constraint checking
3. 3D mesh generation
4. Fitness calculation (with rotation)
5. Feature calculation

Goal: Understand HOW and WHY parcel size impacts performance of each component.
"""

import sys
import timeit
import numpy as np
from pathlib import Path
from multiprocessing import Pool, cpu_count

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import numba
    from numba import njit, prange
    NUMBA_AVAILABLE = True
    print(f"Numba version: {numba.__version__}")
    print(f"NumPy version: {np.__version__}")
    print(f"CPU cores: {cpu_count()}")
except ImportError:
    NUMBA_AVAILABLE = False
    print("WARNING: Numba not installed")
    sys.exit(1)

from backend.evaluation import (
    calculate_all_features,
    calculate_all_features_planning,
    check_constraints
)
from backend.encoding import ParametricEncoding, norm2unif
from scipy.ndimage import rotate, label, center_of_mass


# =============================================================================
# JIT-OPTIMIZED PHENOTYPE CREATION
# =============================================================================

@njit(cache=True, nogil=True)
def express_jit(genes_uniform, xy_length, z_length, buildable_mask):
    """
    JIT-optimized phenotype creation.
    Converts genome to heightmap much faster than Python loops.
    """
    max_num_buildings = genes_uniform.shape[0]
    
    # Check which buildings are active
    is_active = genes_uniform[:, 5] > 0.0
    if not np.any(is_active):
        return np.zeros_like(buildable_mask, dtype=np.float32)
    
    # Calculate building properties (vectorized)
    w = np.zeros(max_num_buildings, dtype=np.int32)
    l = np.zeros(max_num_buildings, dtype=np.int32)
    h = np.zeros(max_num_buildings, dtype=np.int32)
    x_c = np.zeros(max_num_buildings, dtype=np.int32)
    y_c = np.zeros(max_num_buildings, dtype=np.int32)
    
    active_count = 0
    for i in range(max_num_buildings):
        if is_active[i]:
            w[active_count] = int(genes_uniform[i, 0] * (xy_length / 2))
            l[active_count] = int(genes_uniform[i, 1] * (xy_length / 2))
            h[active_count] = int(genes_uniform[i, 2] * z_length)
            x_c[active_count] = int(genes_uniform[i, 3] * xy_length)
            y_c[active_count] = int(genes_uniform[i, 4] * xy_length)
            active_count += 1
    
    # Create heightmap
    heightmap = np.zeros((xy_length, xy_length), dtype=np.float32)
    
    for i in range(active_count):
        x_start = max(0, x_c[i] - w[i] // 2)
        x_end = min(xy_length, x_c[i] + w[i] // 2)
        y_start = max(0, y_c[i] - l[i] // 2)
        y_end = min(xy_length, y_c[i] + l[i] // 2)
        
        for y in range(y_start, y_end):
            for x in range(x_start, x_end):
                heightmap[y, x] = h[i]
    
    # Apply mask
    for y in range(xy_length):
        for x in range(xy_length):
            if not buildable_mask[y, x]:
                heightmap[y, x] = 0.0
    
    return heightmap


# =============================================================================
# JIT-OPTIMIZED 3D MESH GENERATION
# =============================================================================

@njit(cache=True, nogil=True)
def create_3d_from_heightmap_jit(heightmap_2d, max_height):
    """
    JIT-optimized 3D mesh generation from 2D heightmap.
    Much faster than NumPy broadcasting for large grids.
    """
    rows, cols = heightmap_2d.shape
    result = np.zeros((rows, cols, max_height), dtype=np.int8)
    
    for r in range(rows):
        for c in range(cols):
            h = int(heightmap_2d[r, c])
            if h > 0:
                for z in range(min(h, max_height)):
                    result[r, c, z] = 1
    
    return result


# =============================================================================
# JIT-OPTIMIZED FITNESS CALCULATION
# =============================================================================

@njit(cache=True, nogil=True)
def compute_fitness_jit(heightmap_3d, wind_direction):
    """
    JIT-optimized fitness calculation WITHOUT scipy rotation.
    Uses manual rotation for full JIT compilation.
    """
    rows, cols, height = heightmap_3d.shape
    
    # Simple rotation: approximate with grid sampling
    # For production, use pre-computed rotation indices
    rotation_angle_rad = np.radians((wind_direction + 90) % 360)
    cos_a = np.cos(rotation_angle_rad)
    sin_a = np.sin(rotation_angle_rad)
    
    center_r = rows / 2.0
    center_c = cols / 2.0
    
    # Create rotated environment
    rotated = np.zeros_like(heightmap_3d)
    
    for r in range(rows):
        for c in range(cols):
            # Rotate coordinates
            r_centered = r - center_r
            c_centered = c - center_c
            
            r_rot = r_centered * cos_a - c_centered * sin_a + center_r
            c_rot = r_centered * sin_a + c_centered * cos_a + center_c
            
            # Nearest neighbor sampling
            r_src = int(round(r_rot))
            c_src = int(round(c_rot))
            
            if 0 <= r_src < rows and 0 <= c_src < cols:
                for z in range(height):
                    rotated[r, c, z] = heightmap_3d[r_src, c_src, z]
    
    # Calculate porosity
    open_paths = 0
    total_paths = 0
    
    for r in range(rows):
        for z in range(height):
            # Check if entire Y-axis is clear
            is_clear = True
            for c in range(cols):
                if rotated[r, c, z] > 0:
                    is_clear = False
                    break
            
            if is_clear:
                open_paths += 1
            total_paths += 1
    
    porosity = open_paths / total_paths if total_paths > 0 else 0.0
    return min(max(porosity, 0.0), 1.0)


# =============================================================================
# FEATURE CALCULATION - ORIGINAL FEATURES
# =============================================================================

@njit(cache=True, nogil=True)
def calculate_all_features_jit(heightmap, buildable_mask, buildable_area):
    """
    JIT-optimized ORIGINAL 8 features.
    Simplified version without scipy operations and boolean indexing.
    """
    pixel_size = 3.0  # meters
    pixel_area = pixel_size ** 2
    
    rows, cols = heightmap.shape
    
    # Calculate statistics in one pass
    occupied_pixels = 0
    sum_heights = 0.0
    sum_heights_sq = 0.0
    center_y_sum = 0.0
    center_x_sum = 0.0
    mass = 0.0
    
    for r in range(rows):
        for c in range(cols):
            h = heightmap[r, c]
            if h > 0:
                occupied_pixels += 1
                sum_heights += h
                sum_heights_sq += h * h
                center_y_sum += r * h
                center_x_sum += c * h
                mass += h
    
    if occupied_pixels == 0:
        return np.zeros(8)
    
    # [0] Built Area (m²)
    built_area_m2 = occupied_pixels * pixel_area
    
    # [1] Average Height (m)
    avg_height_meters = sum_heights / occupied_pixels
    
    # [2] Height Variability (m) - std dev
    variance = (sum_heights_sq / occupied_pixels) - (avg_height_meters ** 2)
    height_variability_meters = np.sqrt(max(0.0, variance))
    
    # [3] Number of Buildings - requires scipy.label, use placeholder
    num_buildings = 1.0
    
    # [4] Average Building Distance - requires scipy, use placeholder
    avg_spacing_meters = 0.0
    
    # [5] Gross Floor Area (m²)
    total_floor_area_m2 = mass * pixel_area
    
    # [6] Building Mass X - normalized
    center_x = center_x_sum / mass if mass > 0 else 0.0
    center_x_norm = center_x / cols if cols > 0 else 0.0
    
    # [7] Building Mass Y - normalized
    center_y = center_y_sum / mass if mass > 0 else 0.0
    center_y_norm = center_y / rows if rows > 0 else 0.0
    
    return np.array([
        built_area_m2, avg_height_meters, height_variability_meters, num_buildings,
        avg_spacing_meters, total_floor_area_m2, center_x_norm, center_y_norm
    ])


# =============================================================================
# FEATURE CALCULATION - PLANNING FEATURES
# =============================================================================

@njit(cache=True, nogil=True)
def _compute_svf_core_jit(heightmap, pixel_size, num_rays=16, sample_stride=5):
    """JIT-compiled SVF core."""
    rows, cols = heightmap.shape
    svf_values = []
    
    angles = np.arange(num_rays, dtype=np.float64) * (2.0 * np.pi / num_rays)
    
    for r in range(0, rows, sample_stride):
        for c in range(0, cols, sample_stride):
            origin_height = 1.7
            visible_sky = 0
            
            for angle in angles:
                dx = np.cos(angle)
                dy = np.sin(angle)
                
                max_angle = 0.0
                for step in range(1, max(rows, cols)):
                    x = c + dx * step
                    y = r + dy * step
                    
                    if x < 0 or x >= cols - 1 or y < 0 or y >= rows - 1:
                        break
                    
                    xi, yi = int(x), int(y)
                    obstacle_height = heightmap[yi, xi]
                    
                    if obstacle_height > 0:
                        distance = step * pixel_size
                        height_diff = obstacle_height - origin_height
                        angle_to_top = np.arctan2(height_diff, distance)
                        
                        if angle_to_top > max_angle:
                            max_angle = angle_to_top
                
                if max_angle < np.pi / 2:
                    visible_sky += (np.pi / 2 - max_angle) / (np.pi / 2)
            
            svf = visible_sky / num_rays
            svf_values.append(svf)
    
    return np.mean(np.array(svf_values)) if svf_values else 0.0


@njit(cache=True, nogil=True)
def _compute_building_stats_jit(heightmap):
    """JIT-compiled building statistics."""
    rows, cols = heightmap.shape
    count = 0
    sum_height = 0.0
    sum_sq = 0.0
    
    for r in range(rows):
        for c in range(cols):
            h = heightmap[r, c]
            if h > 0:
                count += 1
                sum_height += h
                sum_sq += h * h
    
    if count == 0:
        return 0.0, 0, 0.0, 0.0
    
    mean_height = sum_height / count
    variance = (sum_sq / count) - (mean_height * mean_height)
    
    return sum_height, count, mean_height, variance


@njit(cache=True, nogil=True)
def _compute_hw_ratio_jit(heightmap, pixel_size):
    """JIT-compiled H/W ratio."""
    rows, cols = heightmap.shape
    building_pixels = []
    
    for r in range(rows):
        for c in range(cols):
            if heightmap[r, c] > 0:
                building_pixels.append((r, c, heightmap[r, c]))
    
    if len(building_pixels) < 2:
        return 0.0
    
    n = len(building_pixels)
    sum_ratio = 0.0
    count = 0
    
    for i in range(n):
        r1, c1, h1 = building_pixels[i]
        for j in range(i + 1, n):
            r2, c2, h2 = building_pixels[j]
            
            dist_pixels = np.sqrt((r2 - r1)**2 + (c2 - c1)**2)
            dist_meters = dist_pixels * pixel_size
            
            if dist_meters > 0.1:
                avg_height = (h1 + h2) / 2.0
                ratio = avg_height / dist_meters
                sum_ratio += ratio
                count += 1
    
    return sum_ratio / count if count > 0 else 0.0


def calculate_all_features_planning_jit(heightmap, buildable_mask, buildable_area):
    """Planning features with JIT (hybrid: JIT + scipy)."""
    pixel_area = buildable_area / np.sum(buildable_mask)
    pixel_size = np.sqrt(pixel_area)
    
    occupied = heightmap > 0
    
    if not np.any(occupied):
        return np.zeros(8)
    
    # JIT-optimized stats
    _, num_pixels, avg_height, height_var = _compute_building_stats_jit(heightmap)
    
    built_area = num_pixels * pixel_area
    grz = built_area / buildable_area
    total_floor_area = np.sum(heightmap) * pixel_area
    gfz = total_floor_area / buildable_area
    
    # Scipy for connected components
    labeled_array, num_buildings = label(occupied)
    
    if num_buildings > 1:
        centroids = np.array(center_of_mass(occupied, labeled_array, 
                                           range(1, num_buildings + 1)))
        diff = centroids[:, None, :] - centroids[None, :, :]
        dists = np.sqrt(np.sum(diff**2, axis=-1))
        avg_spacing_pixels = np.mean(dists[np.triu_indices(num_buildings, k=1)])
        avg_spacing_meters = avg_spacing_pixels * pixel_size
    else:
        avg_spacing_meters = 0.0
    
    # JIT-optimized
    hw_ratio = _compute_hw_ratio_jit(heightmap, pixel_size)
    svf = _compute_svf_core_jit(heightmap, pixel_size)
    
    return np.array([grz, gfz, avg_height, height_var, float(num_buildings),
                     avg_spacing_meters, hw_ratio, svf])


# =============================================================================
# FULL EVALUATION LOOP IMPLEMENTATIONS
# =============================================================================

def eval_solution_no_jit(genome, encoding_obj, env_config):
    """
    Original evaluation WITHOUT JIT.
    Uses Python/NumPy/Scipy throughout.
    """
    # 1. Phenotype creation (Python)
    heightmap = encoding_obj.express(env_config['buildable_mask'], genome)
    
    # 2. Constraint checking
    heightmap, is_violated = check_constraints(heightmap, env_config.get('hard_constraints', {}))
    
    if is_violated:
        return np.concatenate(([-1.0], np.zeros(8), heightmap.flatten()))
    
    # 3. 3D mesh generation (NumPy broadcasting)
    max_height = env_config['env_3d_fixed'].shape[2]
    z_indices = np.arange(max_height)
    design_3d = (z_indices < heightmap.astype(int)[:, :, np.newaxis]).astype(np.int8)
    combined_3d = np.maximum(env_config['env_3d_fixed'], design_3d)
    
    # 4. Fitness calculation (scipy rotation)
    rotation_angle = (env_config['wind_direction'] + 90) % 360
    rotated_env = rotate(combined_3d, angle=rotation_angle, axes=(0, 1), reshape=False, order=0)
    max_along_wind = np.max(rotated_env, axis=1)
    open_paths = np.sum(max_along_wind == 0)
    total_paths = max_along_wind.shape[0] * max_along_wind.shape[1]
    fitness = open_paths / total_paths if total_paths > 0 else 0.0
    
    # 5. Feature calculation
    buildable_area = np.sum(env_config['buildable_mask']) * 9.0  # 3m pixels
    features = calculate_all_features_planning(heightmap, env_config['buildable_mask'], buildable_area)
    
    return np.concatenate(([fitness], features, heightmap.flatten()))


def eval_solution_partial_jit(genome, encoding_obj, env_config):
    """
    Evaluation with PARTIAL JIT.
    Only features are JIT-optimized, rest uses original code.
    """
    # 1-4: Same as no-JIT
    heightmap = encoding_obj.express(env_config['buildable_mask'], genome)
    heightmap, is_violated = check_constraints(heightmap, env_config.get('hard_constraints', {}))
    
    if is_violated:
        return np.concatenate(([-1.0], np.zeros(8), heightmap.flatten()))
    
    max_height = env_config['env_3d_fixed'].shape[2]
    z_indices = np.arange(max_height)
    design_3d = (z_indices < heightmap.astype(int)[:, :, np.newaxis]).astype(np.int8)
    combined_3d = np.maximum(env_config['env_3d_fixed'], design_3d)
    
    rotation_angle = (env_config['wind_direction'] + 90) % 360
    rotated_env = rotate(combined_3d, angle=rotation_angle, axes=(0, 1), reshape=False, order=0)
    max_along_wind = np.max(rotated_env, axis=1)
    open_paths = np.sum(max_along_wind == 0)
    total_paths = max_along_wind.shape[0] * max_along_wind.shape[1]
    fitness = open_paths / total_paths if total_paths > 0 else 0.0
    
    # 5. JIT-optimized features
    buildable_area = np.sum(env_config['buildable_mask']) * 9.0
    features = calculate_all_features_planning_jit(heightmap, env_config['buildable_mask'], buildable_area)
    
    return np.concatenate(([fitness], features, heightmap.flatten()))


def eval_solution_full_jit(genome, encoding_obj, env_config):
    """
    Evaluation with FULL JIT.
    Everything optimized except scipy operations.
    """
    # 1. JIT-optimized phenotype creation
    genes_uniform = norm2unif(genome).reshape(10, 6)
    heightmap = express_jit(
        genes_uniform,
        encoding_obj.config['xy_length'],
        encoding_obj.config['z_length'],
        env_config['buildable_mask']
    )
    
    # 2. Constraint checking (kept as-is, very fast)
    heightmap, is_violated = check_constraints(heightmap, env_config.get('hard_constraints', {}))
    
    if is_violated:
        return np.concatenate(([-1.0], np.zeros(8), heightmap.flatten()))
    
    # 3. JIT-optimized 3D mesh generation
    max_height = env_config['env_3d_fixed'].shape[2]
    design_3d = create_3d_from_heightmap_jit(heightmap, max_height)
    combined_3d = np.maximum(env_config['env_3d_fixed'], design_3d)
    
    # 4. JIT-optimized fitness calculation
    fitness = compute_fitness_jit(combined_3d, env_config['wind_direction'])
    
    # 5. JIT-optimized features
    buildable_area = np.sum(env_config['buildable_mask']) * 9.0
    features = calculate_all_features_planning_jit(heightmap, env_config['buildable_mask'], buildable_area)
    
    return np.concatenate(([fitness], features, heightmap.flatten()))


# =============================================================================
# TEST DATA AND BENCHMARKING
# =============================================================================

def create_test_environment(grid_size=30):
    """Create realistic test environment config."""
    env_config = {
        'buildable_mask': np.ones((grid_size, grid_size), dtype=bool),
        'env_3d_fixed': np.zeros((grid_size, grid_size, 30), dtype=np.int8),
        'wind_direction': 45,
        'hard_constraints': {'max_height': 30, 'min_distance': 6}
    }
    return env_config


def create_test_genomes(batch_size=64):
    """Create test genomes."""
    return [np.random.randn(60) for _ in range(batch_size)]


def benchmark_full_loop(eval_func, genomes, encoding_obj, env_config, name="Function"):
    """Benchmark complete evaluation loop."""
    # Warm up
    _ = eval_func(genomes[0], encoding_obj, env_config)
    
    # Benchmark
    times = []
    for _ in range(5):
        start = timeit.default_timer()
        results = [eval_func(g, encoding_obj, env_config) for g in genomes]
        end = timeit.default_timer()
        times.append((end - start) * 1000)
    
    return {
        'mean': np.mean(times),
        'std': np.std(times),
        'results': results
    }


def print_header(title):
    print("\n" + "=" * 100)
    print(title.center(100))
    print("=" * 100)


def print_subheader(title):
    print("\n" + "-" * 100)
    print(title.center(100))
    print("-" * 100)


def benchmark_single_component(func, args, iterations=50):
    """Benchmark a single component with proper warmup."""
    # Warmup
    for _ in range(3):
        _ = func(*args)
    
    # Measure
    times = []
    for _ in range(5):
        start = timeit.default_timer()
        for _ in range(iterations):
            _ = func(*args)
        end = timeit.default_timer()
        times.append((end - start) * 1000 / iterations)
    
    return np.mean(times), np.std(times)


# =============================================================================
# INDIVIDUAL FEATURE CALCULATION HELPERS (JIT)
# =============================================================================

@njit(cache=True, nogil=True)
def _compute_built_area_jit(occupied, pixel_size):
    """JIT: Built area calculation."""
    occupied_pixels = np.sum(occupied)
    return occupied_pixels * (pixel_size ** 2)


@njit(cache=True, nogil=True)
def _compute_avg_height_jit(heightmap):
    """JIT: Average height calculation."""
    count = 0
    total = 0.0
    for i in range(heightmap.shape[0]):
        for j in range(heightmap.shape[1]):
            if heightmap[i, j] > 0:
                count += 1
                total += heightmap[i, j]
    return total / count if count > 0 else 0.0


@njit(cache=True, nogil=True)
def _compute_height_variability_jit(heightmap):
    """JIT: Height variability (std dev) calculation."""
    count = 0
    total = 0.0
    total_sq = 0.0
    for i in range(heightmap.shape[0]):
        for j in range(heightmap.shape[1]):
            if heightmap[i, j] > 0:
                count += 1
                total += heightmap[i, j]
                total_sq += heightmap[i, j] ** 2
    if count == 0:
        return 0.0
    mean = total / count
    variance = (total_sq / count) - (mean ** 2)
    return np.sqrt(max(0.0, variance))


@njit(cache=True, nogil=True)
def _compute_gross_floor_area_jit(heightmap, pixel_size):
    """JIT: Gross floor area calculation."""
    total = 0.0
    for i in range(heightmap.shape[0]):
        for j in range(heightmap.shape[1]):
            total += heightmap[i, j]
    return total * (pixel_size ** 2)


@njit(cache=True, nogil=True)
def _compute_grz_jit(occupied, pixel_size, buildable_area):
    """JIT: GRZ (Ground coverage ratio) calculation."""
    occupied_pixels = np.sum(occupied)
    built_area = occupied_pixels * (pixel_size ** 2)
    return built_area / buildable_area if buildable_area > 0 else 0.0


@njit(cache=True, nogil=True)
def _compute_gfz_jit(heightmap, pixel_size, buildable_area):
    """JIT: GFZ (Floor area ratio) calculation."""
    total = 0.0
    for i in range(heightmap.shape[0]):
        for j in range(heightmap.shape[1]):
            total += heightmap[i, j]
    floor_area = total * (pixel_size ** 2)
    return floor_area / buildable_area if buildable_area > 0 else 0.0


@njit(cache=True, nogil=True)
def _compute_hw_ratio_jit(heightmap, mask):
    """
    JIT: H/W ratio calculation (HEIGHT/WIDTH).
    Uses building-wise calculation with connected component-like logic.
    WARNING: This is the SLOW version that makes JIT worse!
    """
    rows, cols = heightmap.shape
    building_mask = heightmap > 0
    
    # Simple building detection (very basic, not proper connected components)
    building_heights = []
    building_widths = []
    
    # Find buildings by scanning rows
    for r in range(rows):
        in_building = False
        start_col = 0
        max_height = 0.0
        
        for c in range(cols):
            if building_mask[r, c]:
                if not in_building:
                    in_building = True
                    start_col = c
                    max_height = heightmap[r, c]
                else:
                    max_height = max(max_height, heightmap[r, c])
            else:
                if in_building:
                    width = (c - start_col) * 3.0  # pixel size
                    building_heights.append(max_height)
                    building_widths.append(width)
                    in_building = False
        
        if in_building:
            width = (cols - start_col) * 3.0
            building_heights.append(max_height)
            building_widths.append(width)
    
    if len(building_heights) == 0:
        return 0.0
    
    # Calculate average H/W ratio
    total_ratio = 0.0
    for i in range(len(building_heights)):
        if building_widths[i] > 0:
            total_ratio += building_heights[i] / building_widths[i]
    
    return total_ratio / len(building_heights) if len(building_heights) > 0 else 0.0


def main():
    print_header("PARCEL SIZE IMPACT ANALYSIS - Full Evaluation Loop")
    
    print("\nThis benchmark tests how parcel size affects EACH component:")
    print("  1. Phenotype creation (genotype → heightmap)")
    print("  2. Constraint checking")
    print("  3. 3D mesh generation")
    print("  4. Fitness calculation (with rotation)")
    print("  5. Feature calculation")
    print("\nTesting parcel sizes:")
    print("  - 50m × 50m (17×17 grid @ 3m pixels)")
    print("  - 100m × 100m (34×34 grid @ 3m pixels)")
    print("  - 500m × 500m (167×167 grid @ 3m pixels)")
    
    # Define parcel sizes
    PARCEL_CONFIGS = [
        {'name': '50m × 50m', 'size_m': 50, 'grid_size': 17},
        {'name': '100m × 100m', 'size_m': 100, 'grid_size': 34},
        {'name': '500m × 500m', 'size_m': 500, 'grid_size': 167},
    ]
    
    # Store results for comparison
    all_results = []
    
    for config in PARCEL_CONFIGS:
        print_header(f"TESTING: {config['name']} parcel ({config['grid_size']}×{config['grid_size']} grid)")
        
        grid_size = config['grid_size']
        batch_size = 32  # Smaller batch for faster testing
        
        encoding_config = {
            'xy_length': grid_size,
            'z_length': 30,
            'max_num_buildings': 10
        }
        
        encoding_obj = ParametricEncoding(encoding_config)
        env_config = create_test_environment(grid_size)
        genomes = create_test_genomes(batch_size)
        
        # Warm up JIT (only once for all parcel sizes)
        if config == PARCEL_CONFIGS[0]:
            print("\n🔥 Warming up JIT functions...")
            start = timeit.default_timer()
            _ = eval_solution_full_jit(genomes[0], encoding_obj, env_config)
            warmup_time = (timeit.default_timer() - start) * 1000
            print(f"✓ JIT warm-up complete: {warmup_time:.1f} ms")
        
        # =============================================================================
        # COMPONENT-LEVEL BENCHMARKS
        # =============================================================================
        
        print_subheader("Component-Level Analysis")
        
        genome = genomes[0]
        genes_uniform = norm2unif(genome).reshape(10, 6)
        
        # 1. Phenotype Creation
        print("\n1. PHENOTYPE CREATION")
        time_pheno_orig, std_orig = benchmark_single_component(
            encoding_obj.express,
            (env_config['buildable_mask'], genome)
        )
        time_pheno_jit, std_jit = benchmark_single_component(
            express_jit,
            (genes_uniform, grid_size, 30, env_config['buildable_mask'])
        )
        print(f"   Original:  {time_pheno_orig:>8.4f} ± {std_orig:.4f} ms")
        print(f"   JIT:       {time_pheno_jit:>8.4f} ± {std_jit:.4f} ms")
        print(f"   Speedup:   {time_pheno_orig/time_pheno_jit:>8.2f}×")
        
        # 2. 3D Mesh Generation
        print("\n2. 3D MESH GENERATION")
        heightmap = encoding_obj.express(env_config['buildable_mask'], genome)
        
        def create_3d_numpy(hm, max_h):
            z_indices = np.arange(max_h)
            return (z_indices < hm.astype(int)[:, :, np.newaxis]).astype(np.int8)
        
        time_3d_numpy, std_numpy = benchmark_single_component(
            create_3d_numpy,
            (heightmap, 30)
        )
        time_3d_jit, std_jit = benchmark_single_component(
            create_3d_from_heightmap_jit,
            (heightmap, 30)
        )
        print(f"   NumPy:     {time_3d_numpy:>8.4f} ± {std_numpy:.4f} ms")
        print(f"   JIT:       {time_3d_jit:>8.4f} ± {std_jit:.4f} ms")
        print(f"   Speedup:   {time_3d_numpy/time_3d_jit:>8.2f}×")
        
        # 3. Fitness Calculation (Rotation)
        print("\n3. FITNESS CALCULATION (with scipy rotation)")
        design_3d = create_3d_numpy(heightmap, 30)
        combined_3d = np.maximum(env_config['env_3d_fixed'], design_3d)
        
        def fitness_scipy(hm_3d, wind_dir):
            rotation_angle = (wind_dir + 90) % 360
            rotated = rotate(hm_3d, angle=rotation_angle, axes=(0, 1), reshape=False, order=0)
            max_along_wind = np.max(rotated, axis=1)
            open_paths = np.sum(max_along_wind == 0)
            total = max_along_wind.shape[0] * max_along_wind.shape[1]
            return open_paths / total if total > 0 else 0.0
        
        time_fitness, std_fitness = benchmark_single_component(
            fitness_scipy,
            (combined_3d, 45),
            iterations=20  # Fewer iterations for slow operation
        )
        print(f"   Scipy:     {time_fitness:>8.4f} ± {std_fitness:.4f} ms")
        
        # 4. Feature Calculation - DETAILED PER-FEATURE TIMING (JIT vs NO-JIT)
        print("\n4. FEATURE CALCULATION - PER-FEATURE BREAKDOWN (JIT vs NO-JIT)")
        buildable_area = np.sum(env_config['buildable_mask']) * 9.0
        pixel_size = 3.0
        iterations = 100
        
        # Prepare data
        occupied = heightmap > 0
        building_heights = heightmap[occupied] if np.any(occupied) else np.array([])
        labeled_array, num_buildings = label(occupied)
        
        # ========== ORIGINAL FEATURES ==========
        print("\n4A. ORIGINAL FEATURES (8 features) - JIT vs NO-JIT Comparison:")
        print(f"{'Feature':<25} {'No-JIT (ms)':>12} {'JIT (ms)':>12} {'Speedup':>12} {'% of Total':>12}")
        print("-" * 85)
        
        orig_times_nojit = []
        orig_times_jit = []
        
        # Feature 0: Built Area
        t0 = timeit.default_timer()
        for _ in range(iterations):
            occupied_pixels = np.sum(occupied)
            built_area = occupied_pixels * (pixel_size ** 2)
        time_built_area_nojit = (timeit.default_timer() - t0) / iterations * 1000
        
        t0 = timeit.default_timer()
        for _ in range(iterations):
            built_area_jit = _compute_built_area_jit(occupied, pixel_size)
        time_built_area_jit = (timeit.default_timer() - t0) / iterations * 1000
        orig_times_nojit.append(time_built_area_nojit)
        orig_times_jit.append(time_built_area_jit)
        
        # Feature 1: Average Height
        t0 = timeit.default_timer()
        for _ in range(iterations):
            if building_heights.any():
                avg_h = np.mean(building_heights)
        time_avg_height_nojit = (timeit.default_timer() - t0) / iterations * 1000
        
        t0 = timeit.default_timer()
        for _ in range(iterations):
            avg_h_jit = _compute_avg_height_jit(heightmap)
        time_avg_height_jit = (timeit.default_timer() - t0) / iterations * 1000
        orig_times_nojit.append(time_avg_height_nojit)
        orig_times_jit.append(time_avg_height_jit)
        
        # Feature 2: Height Variability
        t0 = timeit.default_timer()
        for _ in range(iterations):
            if building_heights.any():
                height_var = np.std(building_heights)
        time_height_var_nojit = (timeit.default_timer() - t0) / iterations * 1000
        
        t0 = timeit.default_timer()
        for _ in range(iterations):
            height_var_jit = _compute_height_variability_jit(heightmap)
        time_height_var_jit = (timeit.default_timer() - t0) / iterations * 1000
        orig_times_nojit.append(time_height_var_nojit)
        orig_times_jit.append(time_height_var_jit)
        
        # Feature 3: Number of Buildings (scipy.label - NO JIT VERSION!)
        t0 = timeit.default_timer()
        for _ in range(iterations):
            labeled_array_test, num_buildings_test = label(occupied)
        time_num_buildings_nojit = (timeit.default_timer() - t0) / iterations * 1000
        
        # JIT version doesn't exist - would require reimplementing scipy.label
        time_num_buildings_jit = time_num_buildings_nojit  # Same as no-JIT
        orig_times_nojit.append(time_num_buildings_nojit)
        orig_times_jit.append(time_num_buildings_jit)
        
        # Feature 4: Average Distance (scipy.center_of_mass - NO JIT VERSION!)
        t0 = timeit.default_timer()
        for _ in range(iterations):
            if num_buildings > 1:
                centroids = np.array(center_of_mass(occupied, labeled_array, range(1, num_buildings + 1)))
                diff = centroids[:, None, :] - centroids[None, :, :]
                dists = np.sqrt(np.sum(diff**2, axis=-1))
                avg_spacing = np.mean(dists[np.triu_indices(num_buildings, k=1)])
        time_avg_distance_nojit = (timeit.default_timer() - t0) / iterations * 1000
        
        # JIT version doesn't exist - would require reimplementing scipy operations
        time_avg_distance_jit = time_avg_distance_nojit  # Same as no-JIT
        orig_times_nojit.append(time_avg_distance_nojit)
        orig_times_jit.append(time_avg_distance_jit)
        
        # Feature 5: Gross Floor Area
        t0 = timeit.default_timer()
        for _ in range(iterations):
            gfa = np.sum(heightmap) * (pixel_size ** 2)
        time_gfa_nojit = (timeit.default_timer() - t0) / iterations * 1000
        
        t0 = timeit.default_timer()
        for _ in range(iterations):
            gfa_jit = _compute_gross_floor_area_jit(heightmap, pixel_size)
        time_gfa_jit = (timeit.default_timer() - t0) / iterations * 1000
        orig_times_nojit.append(time_gfa_nojit)
        orig_times_jit.append(time_gfa_jit)
        
        # Feature 6&7: Building Mass X/Y (scipy.center_of_mass - NO JIT VERSION!)
        t0 = timeit.default_timer()
        for _ in range(iterations):
            center_y, center_x = center_of_mass(heightmap)
        time_mass_center_nojit = (timeit.default_timer() - t0) / iterations * 1000
        
        # JIT version doesn't exist - would require reimplementing scipy
        time_mass_center_jit = time_mass_center_nojit  # Same as no-JIT
        orig_times_nojit.append(time_mass_center_nojit)
        orig_times_jit.append(time_mass_center_jit)
        
        total_original_nojit = sum(orig_times_nojit)
        total_original_jit = sum(orig_times_jit)
        
        # Print results
        feature_names = [
            "[0] Built Area",
            "[1] Average Height", 
            "[2] Height Variability",
            "[3] Num Buildings (scipy)",
            "[4] Avg Distance (scipy)",
            "[5] Gross Floor Area",
            "[6,7] Mass Center X/Y"
        ]
        
        for i, name in enumerate(feature_names):
            speedup = orig_times_nojit[i] / orig_times_jit[i] if orig_times_jit[i] > 0 else 1.0
            pct = orig_times_nojit[i] / total_original_nojit * 100
            speedup_str = f"{speedup:.2f}×" if speedup != 1.0 else "N/A"
            print(f"{name:<25} {orig_times_nojit[i]:>12.4f} {orig_times_jit[i]:>12.4f} {speedup_str:>12} {pct:>11.1f}%")
        
        print("-" * 85)
        print(f"{'TOTAL':<25} {total_original_nojit:>12.4f} {total_original_jit:>12.4f} {total_original_nojit/total_original_jit:>11.2f}× {''}")
        
        # ========== PLANNING FEATURES ==========
        print("\n4B. PLANNING FEATURES (8 features) - JIT vs NO-JIT Comparison:")
        print(f"{'Feature':<25} {'No-JIT (ms)':>12} {'JIT (ms)':>12} {'Speedup':>12} {'% of Total':>12}")
        print("-" * 85)
        
        plan_times_nojit = []
        plan_times_jit = []
        
        # Feature 0: GRZ
        t0 = timeit.default_timer()
        for _ in range(iterations):
            grz = (np.sum(occupied) * pixel_size ** 2) / buildable_area
        time_grz_nojit = (timeit.default_timer() - t0) / iterations * 1000
        
        t0 = timeit.default_timer()
        for _ in range(iterations):
            grz_jit = _compute_grz_jit(occupied, pixel_size, buildable_area)
        time_grz_jit = (timeit.default_timer() - t0) / iterations * 1000
        plan_times_nojit.append(time_grz_nojit)
        plan_times_jit.append(time_grz_jit)
        
        # Feature 1: GFZ
        t0 = timeit.default_timer()
        for _ in range(iterations):
            gfz = (np.sum(heightmap) * pixel_size ** 2) / buildable_area
        time_gfz_nojit = (timeit.default_timer() - t0) / iterations * 1000
        
        t0 = timeit.default_timer()
        for _ in range(iterations):
            gfz_jit = _compute_gfz_jit(heightmap, pixel_size, buildable_area)
        time_gfz_jit = (timeit.default_timer() - t0) / iterations * 1000
        plan_times_nojit.append(time_gfz_nojit)
        plan_times_jit.append(time_gfz_jit)
        
        # Feature 2: Average Height (same as original)
        plan_times_nojit.append(time_avg_height_nojit)
        plan_times_jit.append(time_avg_height_jit)
        
        # Feature 3: Height Variability (same as original)
        plan_times_nojit.append(time_height_var_nojit)
        plan_times_jit.append(time_height_var_jit)
        
        # Feature 4: Number of Buildings (same as original - scipy)
        plan_times_nojit.append(time_num_buildings_nojit)
        plan_times_jit.append(time_num_buildings_jit)
        
        # Feature 5: Average Distance (same as original - scipy)
        plan_times_nojit.append(time_avg_distance_nojit)
        plan_times_jit.append(time_avg_distance_jit)
        
        # Feature 6: H/W Ratio
        avg_height_val = np.mean(building_heights) if building_heights.any() else 0.0
        avg_spacing_val = 10.0  # Placeholder
        t0 = timeit.default_timer()
        for _ in range(iterations):
            hw_ratio = avg_height_val / avg_spacing_val if avg_spacing_val > 0 else 0.0
        time_hw_ratio_nojit = (timeit.default_timer() - t0) / iterations * 1000
        
        t0 = timeit.default_timer()
        for _ in range(iterations):
            hw_ratio_jit = _compute_hw_ratio_jit(heightmap, env_config['buildable_mask'])
        time_hw_ratio_jit = (timeit.default_timer() - t0) / iterations * 1000
        plan_times_nojit.append(time_hw_ratio_nojit)
        plan_times_jit.append(time_hw_ratio_jit)
        
        # Feature 7: SVF
        grz_val = 0.3
        max_height = 30.0
        t0 = timeit.default_timer()
        for _ in range(iterations):
            normalized_height = np.clip(avg_height_val / max_height, 0.0, 1.0)
            svf = 1.0 - (grz_val * normalized_height * 0.8)
            svf = np.clip(svf, 0.0, 1.0)
        time_svf_nojit = (timeit.default_timer() - t0) / iterations * 1000
        
        t0 = timeit.default_timer()
        for _ in range(iterations):
            svf_jit = _compute_svf_core_jit(heightmap, pixel_size, num_rays=8, sample_stride=5)
        time_svf_jit = (timeit.default_timer() - t0) / iterations * 1000
        plan_times_nojit.append(time_svf_nojit)
        plan_times_jit.append(time_svf_jit)
        
        total_planning_nojit = sum(plan_times_nojit)
        total_planning_jit = sum(plan_times_jit)
        
        # Print results
        feature_names_plan = [
            "[0] GRZ (Site Coverage)",
            "[1] GFZ (Floor Area)",
            "[2] Average Height",
            "[3] Height Variability",
            "[4] Num Buildings (scipy)",
            "[5] Avg Distance (scipy)",
            "[6] H/W Ratio",
            "[7] SVF"
        ]
        
        for i, name in enumerate(feature_names_plan):
            speedup = plan_times_nojit[i] / plan_times_jit[i] if plan_times_jit[i] > 0 else 1.0
            pct = plan_times_nojit[i] / total_planning_nojit * 100
            speedup_str = f"{speedup:.2f}×" if speedup > 1.01 else f"{speedup:.2f}× SLOWER" if speedup < 0.99 else "~1×"
            print(f"{name:<25} {plan_times_nojit[i]:>12.4f} {plan_times_jit[i]:>12.4f} {speedup_str:>12} {pct:>11.1f}%")
        
        print("-" * 85)
        print(f"{'TOTAL':<25} {total_planning_nojit:>12.4f} {total_planning_jit:>12.4f} {total_planning_nojit/total_planning_jit:>11.2f}× {''}")
        
        # Store summary times
        time_feat_original_nojit = total_original_nojit
        time_feat_planning_nojit = total_planning_nojit
        time_feat_original_jit = total_original_jit
        time_feat_planning_jit = total_planning_jit
        
        print("\n4C. FEATURE SET COMPARISON")
        print(f"   Original (no JIT):       {time_feat_original_nojit:>8.4f} ms")
        print(f"   Original (JIT):          {time_feat_original_jit:>8.4f} ms (speedup: {time_feat_original_nojit/time_feat_original_jit:.2f}×)")
        print(f"   Planning (no JIT):       {time_feat_planning_nojit:>8.4f} ms")
        print(f"   Planning (JIT):          {time_feat_planning_jit:>8.4f} ms (speedup: {time_feat_planning_nojit/time_feat_planning_jit:.2f}×)")
        print(f"   ---")
        print(f"   Planning vs Original:    {time_feat_planning_nojit/time_feat_original_nojit:.2f}× {'slower' if time_feat_planning_nojit > time_feat_original_nojit else 'faster'}")
        
        # =============================================================================
        # FULL PIPELINE BENCHMARKS
        # =============================================================================
        
        print_subheader("Full Pipeline Comparison")
        
        print(f"\nBatch size: {batch_size} solutions")
        
        # NO JIT
        stats_no_jit = benchmark_full_loop(
            eval_solution_no_jit, genomes, encoding_obj, env_config, "No JIT"
        )
        
        # PARTIAL JIT
        stats_partial_jit = benchmark_full_loop(
            eval_solution_partial_jit, genomes, encoding_obj, env_config, "Partial JIT"
        )
        
        # FULL JIT
        stats_full_jit = benchmark_full_loop(
            eval_solution_full_jit, genomes, encoding_obj, env_config, "Full JIT"
        )
        
        speedup_partial = stats_no_jit['mean'] / stats_partial_jit['mean']
        speedup_full = stats_no_jit['mean'] / stats_full_jit['mean']
        
        print(f"\n{'Configuration':<25} {'Time (ms)':>12} {'Per Sol (ms)':>14} {'Speedup':>10}")
        print("-" * 65)
        print(f"{'No JIT (baseline)':<25} {stats_no_jit['mean']:>11.2f}  {stats_no_jit['mean']/batch_size:>13.4f}  {'1.00×':>10}")
        print(f"{'Partial JIT (features)':<25} {stats_partial_jit['mean']:>11.2f}  {stats_partial_jit['mean']/batch_size:>13.4f}  {speedup_partial:>9.2f}×")
        print(f"{'Full JIT (all)':<25} {stats_full_jit['mean']:>11.2f}  {stats_full_jit['mean']/batch_size:>13.4f}  {speedup_full:>9.2f}×")
        
        # Store results
        all_results.append({
            'config': config,
            'grid_size': grid_size,
            'components': {
                'phenotype_orig': time_pheno_orig,
                'phenotype_jit': time_pheno_jit,
                '3d_numpy': time_3d_numpy,
                '3d_jit': time_3d_jit,
                'fitness': time_fitness,
                'features_original_nojit': time_feat_original_nojit,
                'features_original_jit': time_feat_original_jit,
                'features_planning_nojit': time_feat_planning_nojit,
                'features_planning_jit': time_feat_planning_jit,
            },
            'pipeline': {
                'no_jit': stats_no_jit['mean'] / batch_size,
                'partial_jit': stats_partial_jit['mean'] / batch_size,
                'full_jit': stats_full_jit['mean'] / batch_size,
            }
        })
    
    # =============================================================================
    # CROSS-PARCEL COMPARISON
    # =============================================================================
    
    print_header("PARCEL SIZE IMPACT ANALYSIS")
    
    print("\n" + "="*100)
    print("COMPONENT SCALING WITH PARCEL SIZE")
    print("="*100)
    
    print(f"\n{'Parcel Size':<15} {'Grid':<10} {'Pheno(ms)':<12} {'3D(ms)':<12} {'Fitness(ms)':<15} {'Feat-Orig(ms)':<15} {'Feat-Plan(ms)':<15}")
    print("-" * 95)
    
    for result in all_results:
        grid = f"{result['grid_size']}²"
        pheno = result['components']['phenotype_jit']
        mesh = result['components']['3d_jit']
        fitness = result['components']['fitness']
        features_orig = result['components']['features_original_nojit']
        features_plan = result['components']['features_planning_nojit']
        
        print(f"{result['config']['name']:<15} {grid:<10} {pheno:<11.4f} {mesh:<11.4f} {fitness:<14.4f} {features_orig:<14.4f} {features_plan:<15.4f}")
    
    # Calculate scaling factors
    print("\n" + "="*100)
    print("SCALING FACTORS (relative to 50m×50m parcel)")
    print("="*100)
    
    base = all_results[0]['components']
    
    print(f"\n{'Parcel Size':<15} {'Grid Pixels':<15} {'Pheno':<10} {'3D Mesh':<10} {'Fitness':<10} {'Feat-Orig':<12} {'Feat-Plan':<12}")
    print("-" * 85)
    
    for result in all_results:
        comp = result['components']
        grid_pixels = result['grid_size'] ** 2
        base_pixels = all_results[0]['grid_size'] ** 2
        pixel_ratio = grid_pixels / base_pixels
        
        pheno_scale = comp['phenotype_jit'] / base['phenotype_jit']
        mesh_scale = comp['3d_jit'] / base['3d_jit']
        fitness_scale = comp['fitness'] / base['fitness']
        features_orig_scale = comp['features_original_nojit'] / base['features_original_nojit']
        features_plan_scale = comp['features_planning_nojit'] / base['features_planning_nojit']
        
        print(f"{result['config']['name']:<15} {pixel_ratio:<14.1f}× {pheno_scale:<9.2f}× {mesh_scale:<9.2f}× {fitness_scale:<9.2f}× {features_orig_scale:<11.2f}× {features_plan_scale:<12.2f}×")
    
    # Complexity analysis
    print("\n" + "="*100)
    print("COMPLEXITY ANALYSIS")
    print("="*100)
    
    print("\nTheoretical complexity for N×N grid:")
    print("  - Phenotype creation:  O(N²) - drawing buildings on grid")
    print("  - 3D mesh generation:  O(N² × H) - height H for each of N² pixels")
    print("  - Fitness (rotation):  O(N² × H) - rotate 3D volume")
    print("  - Features (original): O(N²) - basic grid statistics")
    print("  - Features (planning): O(N³) - SVF ray casting dominates")
    
    print("\nObserved scaling:")
    base_result = all_results[0]
    large_result = all_results[-1]
    
    pixel_ratio = (large_result['grid_size'] / base_result['grid_size']) ** 2
    
    for component_name, base_key, large_key in [
        ('Phenotype (JIT)', 'phenotype_jit', 'phenotype_jit'),
        ('3D Mesh (JIT)', '3d_jit', '3d_jit'),
        ('Fitness (scipy)', 'fitness', 'fitness'),
        ('Features Original (no JIT)', 'features_original_nojit', 'features_original_nojit'),
        ('Features Planning (no JIT)', 'features_planning_nojit', 'features_planning_nojit'),
    ]:
        base_time = base_result['components'][base_key]
        large_time = large_result['components'][large_key]
        observed_ratio = large_time / base_time
        
        # Calculate complexity exponent: observed_ratio = pixel_ratio^exponent
        exponent = np.log(observed_ratio) / np.log(pixel_ratio)
        
        print(f"\n{component_name}:")
        print(f"  Pixel ratio: {pixel_ratio:.1f}×")
        print(f"  Time ratio: {observed_ratio:.1f}×")
        print(f"  Complexity: O(N^{exponent:.2f})")
    
    # =============================================================================
    # RECOMMENDATIONS
    # =============================================================================
    
    print("\n" + "="*100)
    print("RECOMMENDATIONS BY PARCEL SIZE")
    print("="*100)
    
    for result in all_results:
        print(f"\n{result['config']['name']} ({result['grid_size']}×{result['grid_size']} grid)")
        print("-" * 70)
        
        comp = result['components']
        
        # Calculate total time with ORIGINAL features (no JIT)
        total_original = comp['phenotype_jit'] + comp['3d_jit'] + comp['fitness'] + comp['features_original_nojit']
        
        # Calculate total time with PLANNING features (no JIT)
        total_planning = comp['phenotype_jit'] + comp['3d_jit'] + comp['fitness'] + comp['features_planning_nojit']
        
        print(f"\n  WITH ORIGINAL FEATURES (no JIT):")
        print(f"    Total:        {total_original:.4f} ms")
        print(f"    - Phenotype:  {comp['phenotype_jit']:>8.4f} ms ({comp['phenotype_jit']/total_original*100:>5.1f}%)")
        print(f"    - 3D Mesh:    {comp['3d_jit']:>8.4f} ms ({comp['3d_jit']/total_original*100:>5.1f}%)")
        print(f"    - Fitness:    {comp['fitness']:>8.4f} ms ({comp['fitness']/total_original*100:>5.1f}%)")
        print(f"    - Features:   {comp['features_original_nojit']:>8.4f} ms ({comp['features_original_nojit']/total_original*100:>5.1f}%)")
        
        print(f"\n  WITH PLANNING FEATURES (no JIT):")
        print(f"    Total:        {total_planning:.4f} ms")
        print(f"    - Phenotype:  {comp['phenotype_jit']:>8.4f} ms ({comp['phenotype_jit']/total_planning*100:>5.1f}%)")
        print(f"    - 3D Mesh:    {comp['3d_jit']:>8.4f} ms ({comp['3d_jit']/total_planning*100:>5.1f}%)")
        print(f"    - Fitness:    {comp['fitness']:>8.4f} ms ({comp['fitness']/total_planning*100:>5.1f}%)")
        print(f"    - Features:   {comp['features_planning_nojit']:>8.4f} ms ({comp['features_planning_nojit']/total_planning*100:>5.1f}%)")
        
        # Compare feature sets
        print(f"\n  📊 Planning features are {total_planning/total_original:.2f}× slower than original features")
        
        # Identify bottleneck for each configuration
        bottleneck_orig = max(
            [('Phenotype', comp['phenotype_jit']),
             ('3D Mesh', comp['3d_jit']),
             ('Fitness', comp['fitness']),
             ('Features-Orig', comp['features_original_nojit'])],
            key=lambda x: x[1]
        )
        
        bottleneck_plan = max(
            [('Phenotype', comp['phenotype_jit']),
             ('3D Mesh', comp['3d_jit']),
             ('Fitness', comp['fitness']),
             ('Features-Plan', comp['features_planning_nojit'])],
            key=lambda x: x[1]
        )
        
        print(f"  🎯 Bottleneck (original features): {bottleneck_orig[0]} ({bottleneck_orig[1]/total_original*100:.1f}%)")
        print(f"  🎯 Bottleneck (planning features): {bottleneck_plan[0]} ({bottleneck_plan[1]/total_planning*100:.1f}%)")
    
    print("\n" + "="*100)


if __name__ == "__main__":
    main()
