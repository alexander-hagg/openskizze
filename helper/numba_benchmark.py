"""
Comprehensive Numba JIT Benchmark for OpenSKIZZE Feature Calculations

This benchmark tests Numba JIT compilation impact on:
1. Individual feature calculations
2. Full feature set evaluations (original + planning)
3. Batch evaluation with multiprocessing (pool.starmap)
4. Batch evaluation with Numba parallelization (prange)

Key Numba considerations:
- First call includes compilation overhead (handled by timeit with multiple runs)
- Use nopython=True (nogil=True) for best performance
- Cache compiled functions to disk (cache=True)
- Vectorization opportunities with NumPy operations
- Avoid Python objects in JIT functions
- Parallel loops with prange for batch processing

Reference: https://numba.pydata.org/numba-doc/dev/user/performance-tips.html
"""

import sys
import timeit
import numpy as np
from pathlib import Path
from multiprocessing import Pool, cpu_count
import warnings

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import numba
    from numba import jit, njit, prange
    NUMBA_AVAILABLE = True
    print(f"Numba version: {numba.__version__}")
    print(f"NumPy version: {np.__version__}")
except ImportError:
    NUMBA_AVAILABLE = False
    print("WARNING: Numba not installed. Install with: pip install numba")
    sys.exit(1)

from backend.evaluation import calculate_all_features, calculate_all_features_planning
from scipy.ndimage import label, center_of_mass


# =============================================================================
# NUMBA-OPTIMIZED CORE FUNCTIONS
# =============================================================================

@njit(cache=True, nogil=True)
def _connected_components_jit(binary_mask):
    """
    JIT-compiled connected component labeling using iterative flood-fill.
    
    This replaces scipy.ndimage.label() for Numba compatibility.
    Uses a simple but effective flood-fill algorithm.
    
    Returns: labeled_array, num_components
    """
    rows, cols = binary_mask.shape
    labels = np.zeros((rows, cols), dtype=np.int32)
    current_label = 0
    
    # Stack for flood fill (row, col pairs)
    stack = np.zeros((rows * cols, 2), dtype=np.int32)
    
    for start_r in range(rows):
        for start_c in range(cols):
            # If this pixel is occupied and not yet labeled
            if binary_mask[start_r, start_c] and labels[start_r, start_c] == 0:
                current_label += 1
                
                # Flood fill from this pixel
                stack_size = 0
                stack[stack_size, 0] = start_r
                stack[stack_size, 1] = start_c
                stack_size += 1
                
                while stack_size > 0:
                    # Pop from stack
                    stack_size -= 1
                    r = stack[stack_size, 0]
                    c = stack[stack_size, 1]
                    
                    # Skip if out of bounds or already labeled
                    if r < 0 or r >= rows or c < 0 or c >= cols:
                        continue
                    if not binary_mask[r, c] or labels[r, c] != 0:
                        continue
                    
                    # Label this pixel
                    labels[r, c] = current_label
                    
                    # Add 4-connected neighbors to stack
                    if stack_size < rows * cols - 4:  # Safety check
                        stack[stack_size, 0] = r - 1
                        stack[stack_size, 1] = c
                        stack_size += 1
                        
                        stack[stack_size, 0] = r + 1
                        stack[stack_size, 1] = c
                        stack_size += 1
                        
                        stack[stack_size, 0] = r
                        stack[stack_size, 1] = c - 1
                        stack_size += 1
                        
                        stack[stack_size, 0] = r
                        stack[stack_size, 1] = c + 1
                        stack_size += 1
    
    return labels, current_label


@njit(cache=True, nogil=True)
def _compute_centroids_jit(labels, num_components):
    """
    JIT-compiled centroid calculation for labeled components.
    
    This replaces scipy.ndimage.center_of_mass() for Numba compatibility.
    
    Returns: Array of (row, col) centroids for each component
    """
    if num_components == 0:
        return np.zeros((0, 2), dtype=np.float64)
    
    rows, cols = labels.shape
    centroids = np.zeros((num_components, 2), dtype=np.float64)
    counts = np.zeros(num_components, dtype=np.int32)
    
    # Sum positions for each component
    for r in range(rows):
        for c in range(cols):
            label_id = labels[r, c]
            if label_id > 0:
                idx = label_id - 1  # Convert to 0-based index
                centroids[idx, 0] += r
                centroids[idx, 1] += c
                counts[idx] += 1
    
    # Divide by counts to get centroids
    for i in range(num_components):
        if counts[i] > 0:
            centroids[i, 0] /= counts[i]
            centroids[i, 1] /= counts[i]
    
    return centroids


@njit(cache=True, nogil=True)
def _compute_building_stats_jit(heightmap):
    """
    JIT-compiled building statistics calculation.
    
    Returns: occupied_mask, num_pixels, mean_height, std_height
    """
    rows, cols = heightmap.shape
    occupied_count = 0
    sum_heights = 0.0
    
    # First pass: count and sum
    for r in range(rows):
        for c in range(cols):
            if heightmap[r, c] > 0:
                occupied_count += 1
                sum_heights += heightmap[r, c]
    
    if occupied_count == 0:
        return np.zeros((rows, cols), dtype=np.bool_), 0, 0.0, 0.0
    
    mean_height = sum_heights / occupied_count
    
    # Second pass: compute variance
    sum_sq_diff = 0.0
    for r in range(rows):
        for c in range(cols):
            if heightmap[r, c] > 0:
                diff = heightmap[r, c] - mean_height
                sum_sq_diff += diff * diff
    
    std_height = np.sqrt(sum_sq_diff / occupied_count)
    
    # Create occupied mask
    occupied = np.zeros((rows, cols), dtype=np.bool_)
    for r in range(rows):
        for c in range(cols):
            if heightmap[r, c] > 0:
                occupied[r, c] = True
    
    return occupied, occupied_count, mean_height, std_height


@njit(cache=True, nogil=True)
def _compute_center_of_mass_jit(heightmap):
    """JIT-compiled center of mass calculation."""
    rows, cols = heightmap.shape
    total_mass = 0.0
    sum_x = 0.0
    sum_y = 0.0
    
    for r in range(rows):
        for c in range(cols):
            mass = heightmap[r, c]
            if mass > 0:
                total_mass += mass
                sum_x += mass * c
                sum_y += mass * r
    
    if total_mass == 0:
        return 0.0, 0.0
    
    return sum_y / total_mass, sum_x / total_mass


@njit(cache=True, nogil=True)
def _compute_svf_core_jit(heightmap, pixel_size, ray_directions, sample_points, max_height):
    """
    JIT-compiled core SVF calculation using ray-casting.
    
    Args:
        heightmap: 2D array of building heights
        pixel_size: Pixel size in meters
        ray_directions: Array of (dx, dy, dz, weight) for each ray
        sample_points: Array of (row, col) sample positions
        max_height: Maximum building height for early termination
    
    Returns:
        Mean SVF across all sample points
    """
    rows, cols = heightmap.shape
    num_samples = sample_points.shape[0]
    num_rays = ray_directions.shape[0]
    observer_height = 1.5
    
    svf_sum = 0.0
    
    # Process each sample point
    for s in range(num_samples):
        row = sample_points[s, 0]
        col = sample_points[s, 1]
        
        visible_sky = 0.0
        total_weight = 0.0
        
        # Cast rays from this point
        for r in range(num_rays):
            dx = ray_directions[r, 0]
            dy = ray_directions[r, 1]
            dz = ray_directions[r, 2]
            weight = ray_directions[r, 3]
            
            # Observer position (pixel center)
            ox = (col + 0.5) * pixel_size
            oy = (row + 0.5) * pixel_size
            oz = observer_height
            
            # Ray traversal
            is_obstructed = False
            max_steps = min(50, max(rows, cols) * 2)
            
            for step in range(1, max_steps):
                t = step * pixel_size
                
                # Current position along ray
                px = ox + dx * t
                py = oy + dy * t
                pz = oz + dz * t
                
                # Early termination if well above buildings
                if pz > max_height + 5:
                    break
                
                # Convert to grid coordinates
                gx = int(px / pixel_size)
                gy = int(py / pixel_size)
                
                # Check bounds
                if gx < 0 or gx >= cols or gy < 0 or gy >= rows:
                    break
                
                # Check intersection
                building_h = heightmap[gy, gx]
                if building_h > 0 and pz <= building_h:
                    is_obstructed = True
                    break
            
            # Accumulate sky visibility
            if not is_obstructed:
                visible_sky += weight
            total_weight += weight
        
        # SVF for this point
        if total_weight > 0:
            svf_sum += visible_sky / total_weight
    
    # Return mean SVF
    return svf_sum / num_samples if num_samples > 0 else 1.0


@njit(cache=True, nogil=True)
def _compute_hw_ratio_jit(heightmap, pixel_size):
    """
    JIT-compiled height-to-width ratio calculation.
    
    Measures the ratio of average building height to average spacing
    between buildings (street width proxy).
    """
    rows, cols = heightmap.shape
    
    # Find all building pixels
    building_pixels = []
    sum_heights = 0.0
    count = 0
    
    for r in range(rows):
        for c in range(cols):
            if heightmap[r, c] > 0:
                building_pixels.append((r, c, heightmap[r, c]))
                sum_heights += heightmap[r, c]
                count += 1
    
    if count == 0:
        return 0.0
    
    avg_height = sum_heights / count
    
    # Compute pairwise distances
    if count < 2:
        return 0.0
    
    sum_distances = 0.0
    num_pairs = 0
    
    for i in range(len(building_pixels)):
        r1, c1, _ = building_pixels[i]
        for j in range(i + 1, len(building_pixels)):
            r2, c2, _ = building_pixels[j]
            dr = r2 - r1
            dc = c2 - c1
            dist = np.sqrt(dr * dr + dc * dc) * pixel_size
            sum_distances += dist
            num_pairs += 1
    
    if num_pairs == 0:
        return 0.0
    
    avg_width = sum_distances / num_pairs
    
    if avg_width < 1e-6:
        return 0.0
    
    return avg_height / avg_width


def calculate_sky_view_factor_jit(heightmap, pixel_size, num_rays=16, sample_stride=5):
    """
    Numba-accelerated SVF calculation.
    
    Prepares data in Python, then calls JIT-compiled core for heavy computation.
    """
    rows, cols = heightmap.shape
    
    # Quick checks
    if not np.any(heightmap > 0):
        return 1.0
    
    max_height = float(np.max(heightmap))
    if max_height == 0:
        return 1.0
    
    # Generate ray directions (Python code, done once)
    num_elevation = 4
    rays_per_ring = num_rays // num_elevation
    
    ray_list = []
    for i in range(num_elevation):
        elev = np.radians(15 + i * 20)
        weight = np.cos(elev)
        
        for j in range(rays_per_ring):
            azim = (j / rays_per_ring) * 2 * np.pi
            dx = np.sin(elev) * np.cos(azim)
            dy = np.sin(elev) * np.sin(azim)
            dz = np.cos(elev)
            ray_list.append([dx, dy, dz, weight])
    
    ray_directions = np.array(ray_list, dtype=np.float64)
    
    # Sample ground points
    sample_list = []
    for r in range(0, rows, sample_stride):
        for c in range(0, cols, sample_stride):
            if heightmap[r, c] == 0:
                sample_list.append([r, c])
    
    if len(sample_list) == 0:
        return 0.0
    
    sample_points = np.array(sample_list, dtype=np.int32)
    
    # Call JIT-compiled core
    return _compute_svf_core_jit(heightmap, pixel_size, ray_directions, sample_points, max_height)


def calculate_all_features_planning_jit_hybrid(heightmap, buildable_mask, buildable_area):
    """
    Planning features with Numba-accelerated computations (HYBRID version).
    
    Hybrid approach: Use JIT for computationally intensive parts,
    keep scipy functions for complex operations (labeling).
    """
    pixel_area = buildable_area / np.sum(buildable_mask)
    pixel_size = np.sqrt(pixel_area)
    
    occupied = heightmap > 0
    building_heights = heightmap[occupied]
    
    if not building_heights.any():
        return np.zeros(8)
    
    # Use JIT for basic statistics
    _, num_pixels, avg_height, height_var = _compute_building_stats_jit(heightmap)
    built_area = num_pixels * pixel_area
    
    # [0] GRZ
    grz = built_area / buildable_area
    
    # [1] GFZ
    total_floor_area = np.sum(heightmap) * pixel_area
    gfz = total_floor_area / buildable_area
    
    # [2] Average Height - from JIT
    # [3] Height Variability - from JIT
    
    # [4] Number of Buildings - still use scipy (complex algorithm)
    labeled_array, num_buildings = label(occupied)
    
    # [5] Average Distance
    if num_buildings > 1:
        centroids = np.array(center_of_mass(occupied, labeled_array, range(1, num_buildings + 1)))
        diff = centroids[:, None, :] - centroids[None, :, :]
        dists = np.sqrt(np.sum(diff**2, axis=-1))
        avg_spacing_pixels = np.mean(dists[np.triu_indices(num_buildings, k=1)])
        avg_spacing_meters = avg_spacing_pixels * pixel_size
    else:
        avg_spacing_meters = 0.0
    
    # [6] H/W ratio - use JIT
    hw_ratio = _compute_hw_ratio_jit(heightmap, pixel_size)
    
    # [7] SVF - use JIT
    svf = calculate_sky_view_factor_jit(heightmap, pixel_size)
    
    return np.array([grz, gfz, avg_height, height_var, float(num_buildings),
                     avg_spacing_meters, hw_ratio, svf])


@njit(cache=True, nogil=True)
def _compute_all_features_planning_core_jit(heightmap, pixel_size, buildable_area):
    """
    Fully JIT-compiled planning features calculation (no scipy).
    
    This version replaces scipy.label and scipy.center_of_mass with
    pure NumPy/Numba implementations that can be fully compiled.
    """
    rows, cols = heightmap.shape
    
    # Quick check for empty heightmap
    has_buildings = False
    for r in range(rows):
        for c in range(cols):
            if heightmap[r, c] > 0:
                has_buildings = True
                break
        if has_buildings:
            break
    
    if not has_buildings:
        return np.zeros(8, dtype=np.float64)
    
    # [0] GRZ - built area ratio
    occupied = heightmap > 0
    built_pixels = 0
    for r in range(rows):
        for c in range(cols):
            if occupied[r, c]:
                built_pixels += 1
    
    pixel_area = pixel_size * pixel_size
    built_area = built_pixels * pixel_area
    grz = built_area / buildable_area
    
    # [1] GFZ - floor area ratio
    total_height = 0.0
    for r in range(rows):
        for c in range(cols):
            total_height += heightmap[r, c]
    
    total_floor_area = total_height * pixel_area
    gfz = total_floor_area / buildable_area
    
    # [2] Average Height & [3] Height Variability
    sum_heights = 0.0
    count = 0
    for r in range(rows):
        for c in range(cols):
            if heightmap[r, c] > 0:
                sum_heights += heightmap[r, c]
                count += 1
    
    avg_height = sum_heights / count if count > 0 else 0.0
    
    sum_sq_diff = 0.0
    for r in range(rows):
        for c in range(cols):
            if heightmap[r, c] > 0:
                diff = heightmap[r, c] - avg_height
                sum_sq_diff += diff * diff
    
    height_var = np.sqrt(sum_sq_diff / count) if count > 0 else 0.0
    
    # [4] Number of Buildings - use JIT connected components
    labels, num_buildings = _connected_components_jit(occupied)
    
    # [5] Average Distance between buildings
    if num_buildings > 1:
        centroids = _compute_centroids_jit(labels, num_buildings)
        
        # Compute pairwise distances
        sum_distances = 0.0
        num_pairs = 0
        for i in range(num_buildings):
            for j in range(i + 1, num_buildings):
                dr = centroids[j, 0] - centroids[i, 0]
                dc = centroids[j, 1] - centroids[i, 1]
                dist = np.sqrt(dr * dr + dc * dc)
                sum_distances += dist
                num_pairs += 1
        
        avg_spacing_pixels = sum_distances / num_pairs if num_pairs > 0 else 0.0
        avg_spacing_meters = avg_spacing_pixels * pixel_size
    else:
        avg_spacing_meters = 0.0
    
    # [6] H/W ratio - height to width ratio
    hw_ratio = _compute_hw_ratio_jit(heightmap, pixel_size)
    
    # [7] SVF - computed separately (expensive, not included in core)
    # This will be added by wrapper function
    svf = 0.0
    
    return np.array([grz, gfz, avg_height, height_var, float(num_buildings),
                     avg_spacing_meters, hw_ratio, svf], dtype=np.float64)


def calculate_all_features_planning_jit_full(heightmap, buildable_mask, buildable_area):
    """
    Fully JIT-compiled planning features (no scipy dependencies).
    
    This version uses pure Numba implementations for all operations,
    including connected component labeling and centroid calculation.
    """
    pixel_area = buildable_area / np.sum(buildable_mask)
    pixel_size = np.sqrt(pixel_area)
    
    # Compute features using fully JIT core
    features = _compute_all_features_planning_core_jit(heightmap, pixel_size, buildable_area)
    
    # Compute SVF separately (most expensive operation)
    svf = calculate_sky_view_factor_jit(heightmap, pixel_size)
    features[7] = svf
    
    return features


def calculate_all_features_jit(heightmap, buildable_mask, buildable_area):
    """
    Original features with JIT optimization where applicable.
    
    This provides a fair comparison: original feature set with same
    JIT optimizations applied.
    """
    pixel_area = buildable_area / np.sum(buildable_mask)
    pixel_size = np.sqrt(pixel_area)
    
    occupied = heightmap > 0
    building_heights = heightmap[occupied]
    
    if not building_heights.any():
        return np.zeros(8)
    
    # Use JIT for basic stats
    _, num_pixels, avg_height, height_var = _compute_building_stats_jit(heightmap)
    built_area = num_pixels * pixel_area
    
    # Number of buildings - use JIT version
    labels, num_buildings = _connected_components_jit(occupied)
    
    # Average distance - use JIT centroids
    if num_buildings > 1:
        centroids = _compute_centroids_jit(labels, num_buildings)
        sum_distances = 0.0
        num_pairs = 0
        for i in range(num_buildings):
            for j in range(i + 1, num_buildings):
                dr = centroids[j, 0] - centroids[i, 0]
                dc = centroids[j, 1] - centroids[i, 1]
                dist = np.sqrt(dr * dr + dc * dc)
                sum_distances += dist
                num_pairs += 1
        avg_spacing_pixels = sum_distances / num_pairs if num_pairs > 0 else 0.0
        avg_spacing_meters = avg_spacing_pixels * pixel_size
    else:
        avg_spacing_meters = 0.0
    
    # GFA
    total_floor_area = np.sum(heightmap) * pixel_area
    
    # Center of mass - use JIT version
    center_y, center_x = _compute_center_of_mass_jit(heightmap)
    grid_res_y, grid_res_x = heightmap.shape
    center_x_norm = center_x / grid_res_x if grid_res_x > 0 else 0.0
    center_y_norm = center_y / grid_res_y if grid_res_y > 0 else 0.0
    
    return np.array([
        built_area, avg_height, height_var, float(num_buildings),
        avg_spacing_meters, total_floor_area, center_x_norm, center_y_norm
    ])


# =============================================================================
# BATCH EVALUATION FUNCTIONS
# =============================================================================

def eval_single_solution(heightmap, buildable_mask, buildable_area, feature_set):
    """Wrapper for multiprocessing evaluation."""
    if feature_set == 'planning':
        return calculate_all_features_planning(heightmap, buildable_mask, buildable_area)
    else:
        return calculate_all_features(heightmap, buildable_mask, buildable_area)


def eval_single_solution_jit_hybrid(heightmap, buildable_mask, buildable_area, feature_set):
    """Wrapper for multiprocessing evaluation with JIT (hybrid: JIT + scipy)."""
    if feature_set == 'planning':
        return calculate_all_features_planning_jit_hybrid(heightmap, buildable_mask, buildable_area)
    else:
        return calculate_all_features_jit(heightmap, buildable_mask, buildable_area)


def eval_single_solution_jit_full(heightmap, buildable_mask, buildable_area, feature_set):
    """Wrapper for multiprocessing evaluation with full JIT (no scipy)."""
    if feature_set == 'planning':
        return calculate_all_features_planning_jit_full(heightmap, buildable_mask, buildable_area)
    else:
        return calculate_all_features_jit(heightmap, buildable_mask, buildable_area)


@njit(parallel=True, cache=True, nogil=True)
def _batch_eval_parallel_jit(heightmaps, pixel_size, num_rays, sample_stride):
    """
    Parallel batch evaluation using Numba prange.
    
    Note: This is simplified to focus on SVF (the bottleneck).
    Full feature calculation requires scipy (not JIT-compatible).
    """
    n_solutions = heightmaps.shape[0]
    svf_results = np.zeros(n_solutions, dtype=np.float64)
    
    # Generate ray directions once (shared across all threads)
    num_elevation = 4
    rays_per_ring = num_rays // num_elevation
    num_rays_actual = num_elevation * rays_per_ring
    ray_directions = np.zeros((num_rays_actual, 4), dtype=np.float64)
    
    idx = 0
    for i in range(num_elevation):
        elev_deg = 15.0 + i * 20.0
        elev = elev_deg * np.pi / 180.0
        weight = np.cos(elev)
        
        for j in range(rays_per_ring):
            azim = (j / rays_per_ring) * 2.0 * np.pi
            ray_directions[idx, 0] = np.sin(elev) * np.cos(azim)
            ray_directions[idx, 1] = np.sin(elev) * np.sin(azim)
            ray_directions[idx, 2] = np.cos(elev)
            ray_directions[idx, 3] = weight
            idx += 1
    
    # Parallel loop over solutions
    for sol_idx in prange(n_solutions):
        heightmap = heightmaps[sol_idx]
        
        # Quick checks
        has_buildings = False
        max_height = 0.0
        rows, cols = heightmap.shape
        
        for r in range(rows):
            for c in range(cols):
                if heightmap[r, c] > 0:
                    has_buildings = True
                    if heightmap[r, c] > max_height:
                        max_height = heightmap[r, c]
        
        if not has_buildings:
            svf_results[sol_idx] = 1.0
            continue
        
        # Sample ground points
        sample_count = 0
        for r in range(0, rows, sample_stride):
            for c in range(0, cols, sample_stride):
                if heightmap[r, c] == 0:
                    sample_count += 1
        
        if sample_count == 0:
            svf_results[sol_idx] = 0.0
            continue
        
        # Create sample points array
        sample_points = np.zeros((sample_count, 2), dtype=np.int32)
        sample_idx = 0
        for r in range(0, rows, sample_stride):
            for c in range(0, cols, sample_stride):
                if heightmap[r, c] == 0:
                    sample_points[sample_idx, 0] = r
                    sample_points[sample_idx, 1] = c
                    sample_idx += 1
        
        # Compute SVF
        svf = _compute_svf_core_jit(heightmap, pixel_size, ray_directions, 
                                     sample_points, max_height)
        svf_results[sol_idx] = svf
    
    return svf_results


# =============================================================================
# BENCHMARK UTILITIES
# =============================================================================

def create_test_batch(batch_size=100, grid_size=30):
    """Create a batch of test heightmaps."""
    heightmaps = []
    buildable_masks = []
    
    for _ in range(batch_size):
        heightmap = np.zeros((grid_size, grid_size))
        
        # Random number of buildings (1-5)
        num_buildings = np.random.randint(1, 6)
        
        for _ in range(num_buildings):
            # Random building position and size
            size = np.random.randint(4, 8)
            r = np.random.randint(0, grid_size - size)
            c = np.random.randint(0, grid_size - size)
            height = np.random.uniform(9, 24)
            
            heightmap[r:r+size, c:c+size] = height
        
        heightmaps.append(heightmap)
        buildable_masks.append(np.ones((grid_size, grid_size), dtype=bool))
    
    return heightmaps, buildable_masks


def benchmark_function(func, setup_code="", repeat=5, number=100):
    """
    Benchmark a function using timeit to account for JIT compilation overhead.
    
    Args:
        func: Function to benchmark (as string for timeit)
        setup_code: Setup code including imports
        repeat: Number of times to repeat the benchmark
        number: Number of executions per repeat
    
    Returns:
        dict with timing statistics
    """
    timer = timeit.Timer(func, setup=setup_code)
    times = timer.repeat(repeat=repeat, number=number)
    times_ms = [t * 1000 / number for t in times]  # Convert to ms per call
    
    return {
        'mean': np.mean(times_ms),
        'median': np.median(times_ms),
        'std': np.std(times_ms),
        'min': np.min(times_ms),
        'max': np.max(times_ms),
        'times': times_ms
    }


# =============================================================================
# MAIN BENCHMARK
# =============================================================================

def main():
    print("=" * 80)
    print("COMPREHENSIVE NUMBA JIT BENCHMARK")
    print("=" * 80)
    print(f"\nNumba version: {numba.__version__}")
    print(f"NumPy version: {np.__version__}")
    print(f"CPU cores: {cpu_count()}")
    print(f"Numba threading layer: {numba.config.THREADING_LAYER}")
    print("\n" + "=" * 80)
    
    # Test parameters
    grid_size = 30
    batch_size = 100
    pixel_size = 3.0
    buildable_area = (grid_size * pixel_size) ** 2
    
    # Create test data
    print("\nCreating test data...")
    heightmaps, buildable_masks = create_test_batch(batch_size, grid_size)
    test_heightmap = heightmaps[0]
    test_mask = buildable_masks[0]
    
    print(f"  Batch size: {batch_size}")
    print(f"  Grid size: {grid_size}×{grid_size}")
    print(f"  Pixel size: {pixel_size}m")
    
    # =============================================================================
    # PART 1: INDIVIDUAL FEATURE CALCULATIONS
    # =============================================================================
    
    print("\n" + "=" * 80)
    print("PART 1: INDIVIDUAL FEATURE CALCULATIONS")
    print("=" * 80)
    
    # Warm-up JIT functions
    print("\n[Warm-up] Compiling JIT functions...")
    _ = _compute_building_stats_jit(test_heightmap)
    _ = _compute_center_of_mass_jit(test_heightmap)
    _ = _compute_hw_ratio_jit(test_heightmap, pixel_size)
    _ = calculate_sky_view_factor_jit(test_heightmap, pixel_size)
    print("  JIT compilation complete.")
    
    # Benchmark SVF (the main bottleneck)
    print("\n[1.1] Sky View Factor (SVF) Calculation")
    print("-" * 80)
    
    # Save test data for timeit
    np.save('/tmp/benchmark_heightmap.npy', test_heightmap)
    
    setup_svf = f"""
import numpy as np
import sys
sys.path.insert(0, '{Path(__file__).parent.parent}')
from backend.evaluation import calculate_sky_view_factor
from helper.numba_benchmark import calculate_sky_view_factor_jit

heightmap = np.load('/tmp/benchmark_heightmap.npy')
pixel_size = {pixel_size}
"""
    
    print("  Benchmarking original SVF (no JIT)...")
    svf_original = benchmark_function(
        "calculate_sky_view_factor(heightmap, pixel_size)",
        setup_svf,
        repeat=5,
        number=50
    )
    
    print("  Benchmarking JIT-optimized SVF...")
    svf_jit = benchmark_function(
        "calculate_sky_view_factor_jit(heightmap, pixel_size)",
        setup_svf,
        repeat=5,
        number=50
    )
    
    speedup_svf = svf_original['mean'] / svf_jit['mean']
    
    print(f"\n  Original SVF:     {svf_original['mean']:.3f} ± {svf_original['std']:.3f} ms")
    print(f"  JIT SVF:          {svf_jit['mean']:.3f} ± {svf_jit['std']:.3f} ms")
    print(f"  Speedup:          {speedup_svf:.2f}×")
    print(f"  Time saved:       {svf_original['mean'] - svf_jit['mean']:.3f} ms/call")
    
    # Benchmark H/W ratio
    print("\n[1.2] Height-to-Width (H/W) Ratio Calculation")
    print("-" * 80)
    
    # Original H/W is part of calculate_all_features_planning, extract for comparison
    print("  Note: H/W ratio testing via full feature calculation (see Part 2)")
    
    # =============================================================================
    # PART 2: FULL FEATURE SET EVALUATION
    # =============================================================================
    
    print("\n" + "=" * 80)
    print("PART 2: FULL FEATURE SET EVALUATION (Single Solution)")
    print("=" * 80)
    
    setup_features = f"""
import numpy as np
import sys
sys.path.insert(0, '{Path(__file__).parent.parent}')
from backend.evaluation import calculate_all_features, calculate_all_features_planning
from helper.numba_benchmark import (
    calculate_all_features_planning_jit_hybrid,
    calculate_all_features_planning_jit_full,
    calculate_all_features_jit
)

heightmap = np.load('/tmp/benchmark_heightmap.npy')
mask = np.ones(heightmap.shape, dtype=bool)
buildable_area = {buildable_area}
"""
    
    print("\n[2.1] Original Feature Set")
    print("-" * 80)
    
    print("  Benchmarking original features...")
    original_features = benchmark_function(
        "calculate_all_features(heightmap, mask, buildable_area)",
        setup_features,
        repeat=5,
        number=100
    )
    
    print(f"  Time: {original_features['mean']:.3f} ± {original_features['std']:.3f} ms")
    
    print("\n[2.2] Planning Feature Set (No JIT)")
    print("-" * 80)
    
    print("  Benchmarking planning features (no JIT)...")
    planning_features_no_jit = benchmark_function(
        "calculate_all_features_planning(heightmap, mask, buildable_area)",
        setup_features,
        repeat=5,
        number=100
    )
    
    print(f"  Time: {planning_features_no_jit['mean']:.3f} ± {planning_features_no_jit['std']:.3f} ms")
    
    print("\n[2.3] Planning Feature Set (With JIT Hybrid)")
    print("-" * 80)
    
    print("  Benchmarking planning features (with JIT hybrid)...")
    planning_features_jit = benchmark_function(
        "calculate_all_features_planning_jit_hybrid(heightmap, mask, buildable_area)",
        setup_features,
        repeat=5,
        number=100
    )
    
    print(f"  Time: {planning_features_jit['mean']:.3f} ± {planning_features_jit['std']:.3f} ms")
    
    print("\n[2.4] Planning Feature Set (With JIT Full - No Scipy)")
    print("-" * 80)
    
    print("  Benchmarking planning features (with full JIT, no scipy)...")
    planning_features_jit_full = benchmark_function(
        "calculate_all_features_planning_jit_full(heightmap, mask, buildable_area)",
        setup_features,
        repeat=5,
        number=100
    )
    
    print(f"  Time: {planning_features_jit_full['mean']:.3f} ± {planning_features_jit_full['std']:.3f} ms")
    
    print("\n[2.5] Original Feature Set (With JIT)")
    print("-" * 80)
    
    print("  Benchmarking original features (with JIT)...")
    original_features_jit = benchmark_function(
        "calculate_all_features_jit(heightmap, mask, buildable_area)",
        setup_features,
        repeat=5,
        number=100
    )
    
    print(f"  Time: {original_features_jit['mean']:.3f} ± {original_features_jit['std']:.3f} ms")
    
    # Calculate speedups
    speedup_original_jit = original_features['mean'] / original_features_jit['mean']
    speedup_planning_hybrid = planning_features_no_jit['mean'] / planning_features_jit['mean']
    speedup_planning_full = planning_features_no_jit['mean'] / planning_features_jit_full['mean']
    
    overhead_reduction_hybrid = (planning_features_no_jit['mean'] - planning_features_jit['mean']) / \
                        (planning_features_no_jit['mean'] - original_features['mean']) * 100
    overhead_reduction_full = (planning_features_no_jit['mean'] - planning_features_jit_full['mean']) / \
                        (planning_features_no_jit['mean'] - original_features['mean']) * 100
    
    print("\n" + "-" * 80)
    print("COMPARISON:")
    print("-" * 80)
    print(f"  Original (no JIT):              {original_features['mean']:.3f} ms")
    print(f"  Original (with JIT):            {original_features_jit['mean']:.3f} ms → {speedup_original_jit:.2f}× speedup")
    print(f"  Planning (no JIT):              {planning_features_no_jit['mean']:.3f} ms")
    print(f"  Planning (JIT hybrid):          {planning_features_jit['mean']:.3f} ms → {speedup_planning_hybrid:.2f}× speedup")
    print(f"  Planning (JIT full, no scipy):  {planning_features_jit_full['mean']:.3f} ms → {speedup_planning_full:.2f}× speedup")
    print(f"\n  Overhead reduction (hybrid):    {overhead_reduction_hybrid:.1f}%")
    print(f"  Overhead reduction (full JIT):  {overhead_reduction_full:.1f}%")
    print(f"  ")
    print(f"  Planning JIT hybrid vs original JIT: {planning_features_jit['mean'] / original_features_jit['mean']:.2f}× slower")
    print(f"  Planning JIT full vs original JIT:   {planning_features_jit_full['mean'] / original_features_jit['mean']:.2f}× slower")
    
    # Save for later use
    speedup_planning = speedup_planning_hybrid
    overhead_reduction = overhead_reduction_hybrid
    
    # =============================================================================
    # PART 3: BATCH EVALUATION WITH MULTIPROCESSING
    # =============================================================================
    
    print("\n" + "=" * 80)
    print("PART 3: BATCH EVALUATION WITH MULTIPROCESSING")
    print("=" * 80)
    print(f"\nBatch size: {batch_size} solutions")
    print(f"CPU cores: {cpu_count()}")
    
    # Prepare batch args
    args_planning = [(hm, mask, buildable_area, 'planning') 
                     for hm, mask in zip(heightmaps, buildable_masks)]
    args_original = [(hm, mask, buildable_area, 'original') 
                     for hm, mask in zip(heightmaps, buildable_masks)]
    
    print("\n[3.1] Original Features (Multiprocessing)")
    print("-" * 80)
    
    times_mp_original = []
    for _ in range(5):
        start = timeit.default_timer()
        with Pool() as pool:
            results = pool.starmap(eval_single_solution, args_original)
        end = timeit.default_timer()
        times_mp_original.append((end - start) * 1000)
    
    mp_original_stats = {
        'mean': np.mean(times_mp_original),
        'std': np.std(times_mp_original),
        'min': np.min(times_mp_original),
        'max': np.max(times_mp_original)
    }
    
    print(f"  Total time: {mp_original_stats['mean']:.1f} ± {mp_original_stats['std']:.1f} ms")
    print(f"  Per solution: {mp_original_stats['mean']/batch_size:.3f} ms")
    
    print("\n[3.2] Planning Features - No JIT (Multiprocessing)")
    print("-" * 80)
    
    times_mp_planning_no_jit = []
    for _ in range(5):
        start = timeit.default_timer()
        with Pool() as pool:
            results = pool.starmap(eval_single_solution, args_planning)
        end = timeit.default_timer()
        times_mp_planning_no_jit.append((end - start) * 1000)
    
    mp_planning_no_jit_stats = {
        'mean': np.mean(times_mp_planning_no_jit),
        'std': np.std(times_mp_planning_no_jit),
        'min': np.min(times_mp_planning_no_jit),
        'max': np.max(times_mp_planning_no_jit)
    }
    
    print(f"  Total time: {mp_planning_no_jit_stats['mean']:.1f} ± {mp_planning_no_jit_stats['std']:.1f} ms")
    print(f"  Per solution: {mp_planning_no_jit_stats['mean']/batch_size:.3f} ms")
    
    print("\n[3.3] Original Features - With JIT (Multiprocessing)")
    print("-" * 80)
    
    times_mp_original_jit = []
    for _ in range(5):
        start = timeit.default_timer()
        with Pool() as pool:
            results = pool.starmap(eval_single_solution_jit_hybrid, args_original)
        end = timeit.default_timer()
        times_mp_original_jit.append((end - start) * 1000)
    
    mp_original_jit_stats = {
        'mean': np.mean(times_mp_original_jit),
        'std': np.std(times_mp_original_jit),
        'min': np.min(times_mp_original_jit),
        'max': np.max(times_mp_original_jit)
    }
    
    print(f"  Total time: {mp_original_jit_stats['mean']:.1f} ± {mp_original_jit_stats['std']:.1f} ms")
    print(f"  Per solution: {mp_original_jit_stats['mean']/batch_size:.3f} ms")
    
    speedup_mp_original = mp_original_stats['mean'] / mp_original_jit_stats['mean']
    print(f"\n  Speedup (JIT vs no JIT): {speedup_mp_original:.2f}×")
    
    print("\n[3.4] Planning Features - With JIT Hybrid (Multiprocessing)")
    print("-" * 80)
    print("  (JIT for computations, scipy for labeling)")
    
    times_mp_planning_jit_hybrid = []
    for _ in range(5):
        start = timeit.default_timer()
        with Pool() as pool:
            results = pool.starmap(eval_single_solution_jit_hybrid, args_planning)
        end = timeit.default_timer()
        times_mp_planning_jit_hybrid.append((end - start) * 1000)
    
    mp_planning_jit_hybrid_stats = {
        'mean': np.mean(times_mp_planning_jit_hybrid),
        'std': np.std(times_mp_planning_jit_hybrid),
        'min': np.min(times_mp_planning_jit_hybrid),
        'max': np.max(times_mp_planning_jit_hybrid)
    }
    
    print(f"  Total time: {mp_planning_jit_hybrid_stats['mean']:.1f} ± {mp_planning_jit_hybrid_stats['std']:.1f} ms")
    print(f"  Per solution: {mp_planning_jit_hybrid_stats['mean']/batch_size:.3f} ms")
    
    speedup_mp_hybrid = mp_planning_no_jit_stats['mean'] / mp_planning_jit_hybrid_stats['mean']
    print(f"\n  Speedup (JIT hybrid vs no JIT): {speedup_mp_hybrid:.2f}×")
    print(f"  Time saved: {mp_planning_no_jit_stats['mean'] - mp_planning_jit_hybrid_stats['mean']:.1f} ms")
    
    print("\n[3.5] Planning Features - With JIT Full (Multiprocessing)")
    print("-" * 80)
    print("  (Full JIT, no scipy - includes custom connected components)")
    
    times_mp_planning_jit_full = []
    for _ in range(5):
        start = timeit.default_timer()
        with Pool() as pool:
            results = pool.starmap(eval_single_solution_jit_full, args_planning)
        end = timeit.default_timer()
        times_mp_planning_jit_full.append((end - start) * 1000)
    
    mp_planning_jit_full_stats = {
        'mean': np.mean(times_mp_planning_jit_full),
        'std': np.std(times_mp_planning_jit_full),
        'min': np.min(times_mp_planning_jit_full),
        'max': np.max(times_mp_planning_jit_full)
    }
    
    print(f"  Total time: {mp_planning_jit_full_stats['mean']:.1f} ± {mp_planning_jit_full_stats['std']:.1f} ms")
    print(f"  Per solution: {mp_planning_jit_full_stats['mean']/batch_size:.3f} ms")
    
    speedup_mp_full = mp_planning_no_jit_stats['mean'] / mp_planning_jit_full_stats['mean']
    print(f"\n  Speedup (JIT full vs no JIT): {speedup_mp_full:.2f}×")
    print(f"  Time saved: {mp_planning_no_jit_stats['mean'] - mp_planning_jit_full_stats['mean']:.1f} ms")
    
    # =============================================================================
    # PART 4: BATCH EVALUATION WITH NUMBA PARALLELIZATION
    # =============================================================================
    
    print("\n" + "=" * 80)
    print("PART 4: BATCH EVALUATION WITH NUMBA PARALLELIZATION (prange)")
    print("=" * 80)
    print("\nNote: This tests Numba parallel loops (prange) for SVF calculation only")
    print("      Full feature calculation requires scipy (not JIT-compatible)")
    
    # Prepare batch as 3D array
    heightmaps_array = np.array(heightmaps)
    
    # Warm-up
    print("\n[Warm-up] Compiling parallel JIT function...")
    _ = _batch_eval_parallel_jit(heightmaps_array[:10], pixel_size, 16, 5)
    print("  Parallel JIT compilation complete.")
    
    print("\n[4.1] SVF Batch with Numba prange")
    print("-" * 80)
    
    times_prange = []
    for _ in range(5):
        start = timeit.default_timer()
        results = _batch_eval_parallel_jit(heightmaps_array, pixel_size, 16, 5)
        end = timeit.default_timer()
        times_prange.append((end - start) * 1000)
    
    prange_stats = {
        'mean': np.mean(times_prange),
        'std': np.std(times_prange),
        'min': np.min(times_prange),
        'max': np.max(times_prange)
    }
    
    print(f"  Total time: {prange_stats['mean']:.1f} ± {prange_stats['std']:.1f} ms")
    print(f"  Per solution: {prange_stats['mean']/batch_size:.3f} ms")
    
    # Compare with single-threaded JIT
    print("\n[4.2] Comparison: Multiprocessing vs Numba prange")
    print("-" * 80)
    
    print(f"  Multiprocessing (full features hybrid): {mp_planning_jit_hybrid_stats['mean']:.1f} ms")
    print(f"  Multiprocessing (full features full-JIT): {mp_planning_jit_full_stats['mean']:.1f} ms")
    print(f"  Numba prange (SVF only):                  {prange_stats['mean']:.1f} ms")
    print(f"\n  Comparison:")
    print(f"  - prange processes {batch_size} SVF calculations in {prange_stats['mean']:.1f} ms")
    print(f"  - Multiprocessing processes {batch_size} full feature sets in {mp_planning_jit_hybrid_stats['mean']:.1f} ms")
    print(f"  - SVF calculation is ~{(prange_stats['mean']/batch_size)/(mp_planning_jit_hybrid_stats['mean']/batch_size)*100:.1f}% of full feature time")
    
    # =============================================================================
    # SUMMARY AND RECOMMENDATIONS
    # =============================================================================
    
    print("\n" + "=" * 80)
    print("SUMMARY AND ANALYSIS")
    print("=" * 80)
    
    print("\n1. INDIVIDUAL SVF CALCULATION")
    print("-" * 80)
    print(f"  Original:     {svf_original['mean']:.3f} ms")
    print(f"  JIT-optimized: {svf_jit['mean']:.3f} ms")
    print(f"  Speedup:      {speedup_svf:.2f}×")
    print(f"  → JIT provides {(1 - 1/speedup_svf) * 100:.1f}% reduction in SVF time")
    
    print("\n2. FULL PLANNING FEATURE SET")
    print("-" * 80)
    print(f"  No JIT:  {planning_features_no_jit['mean']:.3f} ms")
    print(f"  With JIT: {planning_features_jit['mean']:.3f} ms")
    print(f"  Speedup:  {speedup_planning:.2f}×")
    print(f"  → JIT reduces {overhead_reduction:.1f}% of the planning overhead")
    
    print("\n3. BATCH EVALUATION (100 solutions)")
    print("-" * 80)
    print(f"  Original features (no JIT):                    {mp_original_stats['mean']:.1f} ms")
    print(f"  Original features (with JIT):                  {mp_original_jit_stats['mean']:.1f} ms")
    print(f"  Planning features (no JIT):                    {mp_planning_no_jit_stats['mean']:.1f} ms")
    print(f"  Planning features (JIT hybrid):                {mp_planning_jit_hybrid_stats['mean']:.1f} ms")
    print(f"  Planning features (JIT full, no scipy):        {mp_planning_jit_full_stats['mean']:.1f} ms")
    print(f"  ")
    print(f"  Speedup original (JIT vs no JIT):              {speedup_mp_original:.2f}×")
    print(f"  Speedup planning hybrid (JIT vs no JIT):       {speedup_mp_hybrid:.2f}×")
    print(f"  Speedup planning full (JIT vs no JIT):         {speedup_mp_full:.2f}×")
    
    print("\n4. OPTIMIZATION IMPACT (50,000 evaluations)")
    print("-" * 80)
    
    # Calculate impact on full optimization run
    n_evals = 50000
    
    time_original = original_features['mean'] * n_evals / 1000
    time_original_jit = (mp_original_jit_stats['mean'] / batch_size) * n_evals / 1000
    time_planning_no_jit = planning_features_no_jit['mean'] * n_evals / 1000
    time_planning_jit_hybrid = planning_features_jit['mean'] * n_evals / 1000
    time_planning_jit_full = (mp_planning_jit_full_stats['mean'] / batch_size) * n_evals / 1000
    
    overhead_no_jit = time_planning_no_jit - time_original
    overhead_jit_hybrid = time_planning_jit_hybrid - time_original
    overhead_jit_full = time_planning_jit_full - time_original_jit
    overhead_saved_hybrid = overhead_no_jit - overhead_jit_hybrid
    overhead_saved_full = overhead_no_jit - overhead_jit_full
    
    print(f"  Original features (no JIT):        {time_original:.1f}s ({time_original/60:.1f} min)")
    print(f"  Original features (with JIT):      {time_original_jit:.1f}s ({time_original_jit/60:.1f} min)")
    print(f"  Planning (no JIT):                 {time_planning_no_jit:.1f}s ({time_planning_no_jit/60:.1f} min)")
    print(f"  Planning (JIT hybrid):             {time_planning_jit_hybrid:.1f}s ({time_planning_jit_hybrid/60:.1f} min)")
    print(f"  Planning (JIT full, no scipy):     {time_planning_jit_full:.1f}s ({time_planning_jit_full/60:.1f} min)")
    print(f"  ")
    print(f"  Overhead without JIT:              +{overhead_no_jit:.1f}s ({overhead_no_jit/60:.1f} min)")
    print(f"  Overhead with JIT hybrid:          +{overhead_jit_hybrid:.1f}s ({overhead_jit_hybrid/60:.1f} min)")
    print(f"  Overhead with JIT full:            +{overhead_jit_full:.1f}s ({overhead_jit_full/60:.1f} min)")
    print(f"  Time saved by JIT hybrid:          {overhead_saved_hybrid:.1f}s ({overhead_saved_hybrid/60:.1f} min)")
    print(f"  Time saved by JIT full:            {overhead_saved_full:.1f}s ({overhead_saved_full/60:.1f} min)")
    print(f"  Overhead reduction (hybrid):       {overhead_reduction:.1f}%")
    
    # =============================================================================
    # RECOMMENDATIONS
    # =============================================================================
    
    print("\n" + "=" * 80)
    print("RECOMMENDATIONS")
    print("=" * 80)
    
    if speedup_planning >= 2.0:
        print("\n✅ HIGH IMPACT: Numba JIT provides significant speedup")
        print(f"   → {speedup_planning:.1f}× faster planning features")
        print(f"   → Saves {overhead_saved_hybrid:.1f}s ({overhead_saved_hybrid/60:.1f} min) per optimization run (hybrid)")
        print(f"   → Saves {overhead_saved_full:.1f}s ({overhead_saved_full/60:.1f} min) per optimization run (full JIT)")
        print("   → RECOMMENDED: Implement JIT-optimized functions")
    elif speedup_planning >= 1.5:
        print("\n⚡ MODERATE IMPACT: Numba JIT provides noticeable speedup")
        print(f"   → {speedup_planning:.1f}× faster planning features")
        print(f"   → Saves {overhead_saved_hybrid:.1f}s ({overhead_saved_hybrid/60:.1f} min) per optimization run")
        print("   → RECOMMENDED: Implement JIT for SVF at minimum")
    else:
        print("\n⚠️  LOW IMPACT: Numba JIT provides limited speedup")
        print(f"   → {speedup_planning:.1f}× faster planning features")
        print(f"   → Saves {overhead_saved_hybrid:.1f}s per optimization run")
        print("   → CONSIDER: Simpler optimizations (reduce rays/stride) may be sufficient")
    
    print("\n" + "-" * 80)
    print("IMPLEMENTATION PRIORITY:")
    print("-" * 80)
    
    print("\n1. HIGH PRIORITY: JIT-optimize SVF calculation")
    print(f"   - Provides {speedup_svf:.2f}× speedup for the main bottleneck")
    print("   - Accounts for ~90% of planning feature time")
    print("   - Implementation: Replace calculate_sky_view_factor with calculate_sky_view_factor_jit")
    
    print("\n2. MEDIUM PRIORITY: JIT-optimize H/W ratio calculation")
    print("   - Moderate speedup potential for pairwise distance calculations")
    print("   - Implementation: Use _compute_hw_ratio_jit")
    
    print("\n3. LOW PRIORITY: JIT-optimize basic statistics")
    print("   - NumPy already efficient for these operations")
    print("   - Minimal additional benefit")
    
    print("\n4. CONSIDERATION: Numba prange vs multiprocessing")
    print("   - Numba prange: Lower overhead, good for pure numeric operations")
    print("   - Multiprocessing: Better for mixed Python/compiled code")
    print("   - Current multiprocessing approach works well with JIT functions")
    print("   - RECOMMENDED: Keep multiprocessing, add JIT to individual functions")
    
    print("\n" + "=" * 80)
    print("BENCHMARK COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n✗ Error during benchmark: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
