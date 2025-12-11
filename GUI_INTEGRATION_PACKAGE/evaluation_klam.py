# OpenSKIZZE
# Copyright (C) 2025 [Alexander Hagg]
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
Fitness function using KLAM_21 simulation for evaluation.
"""
import sys
import numpy as np
import yaml
import os
import shutil
import subprocess
import tempfile
from typing import Dict, Tuple, List

try:
    from sklearn.gaussian_process import GaussianProcessRegressor
    from sklearn.gaussian_process.kernels import ConstantKernel, Matern
except ImportError:
    GaussianProcessRegressor = None
    print("Warning: sklearn not found. GP modeling will be disabled.")

from scipy.ndimage import label, center_of_mass

try:
    from rasterio.transform import from_origin
except ImportError:
    from_origin = None
    print("Warning: rasterio not found. KLAM file I/O will be disabled.")

try:
    from .gp_utils import train_gp, eval_gp, acquire_ucb
except ImportError:
    print("Warning: gp_utils not found. Surrogate modeling will be disabled.")
    train_gp, eval_gp, acquire_ucb = None, None, None


# --- Helper functions for file I/O ---
def write_terrain_asc_file(directory, filename, data):
    """Writes terrain array to ASC file with fixed-width format (8 chars per value).
    This matches nsth0=8 parameter in klam_21.in."""
    filepath = os.path.join(directory, filename)
    with open(filepath, 'w') as f:
        for row in data:
            line = ''.join(f'{val:8.2f}' for val in row)
            f.write(line + '\n')

def write_buildings_asc_file(directory, filename, data):
    """Writes buildings array to ASC file with free-format (space-separated).
    KLAM-21 auto-detects this format for b_file."""
    filepath = os.path.join(directory, filename)
    with open(filepath, 'w') as f:
        for row in data:
            line = ' '.join(f'{val:.1f}' for val in row)
            f.write(line + '\n')

def write_landuse_asc_file(directory, filename, data):
    """Writes landuse array to ASC file without header and without space delimiters."""
    filepath = os.path.join(directory, filename)
    with open(filepath, 'w') as f:
        for row in data:
            # Write each row as concatenated digits (no spaces)
            f.write(''.join(str(int(val)) for val in row) + '\n')

def read_asc_file(filepath: str) -> Tuple[np.ndarray, Dict]:
    """
    Reads KLAM-21 output ASC files in fixed-width format.
    
    KLAM-21 outputs have:
    - Header lines starting with '*' containing metadata
    - Fixed-width values (5 chars each) in a continuous stream
    - Data wraps across multiple lines
    """
    with open(filepath, 'r', encoding='latin-1') as f:
        all_lines = f.readlines()
    
    # Parse header for dimensions
    ncols = None
    nrows = None
    chars_per_value = 5  # Default
    
    header_lines = []
    data_start_index = 0
    
    for i, line in enumerate(all_lines):
        if line.strip().startswith('*'):
            header_lines.append(line)
            # Parse header info
            if 'Anzahl Spalten' in line:
                ncols = int(line.split()[-1])
            elif 'Anzahl Zeilen' in line:
                nrows = int(line.split()[-1])
            elif 'Zeichen pro Wert' in line:
                chars_per_value = int(line.split()[-1])
        else:
            data_start_index = i
            break
    
    if ncols is None or nrows is None:
        raise ValueError(f"Could not parse dimensions from header in {filepath}")
    
    # Read all data as one continuous string (excluding header)
    data_text = ''.join(all_lines[data_start_index:])
    
    # Parse fixed-width values
    # Remove newlines and any trailing spaces within each "record"
    # Data is in fixed-width format: each value is exactly chars_per_value characters
    values = []
    pos = 0
    total_values_needed = ncols * nrows
    
    while len(values) < total_values_needed and pos < len(data_text):
        char = data_text[pos]
        if char == '\n' or char == '\r':
            pos += 1
            continue
        
        # Read chars_per_value characters
        value_str = data_text[pos:pos + chars_per_value]
        if len(value_str) < chars_per_value:
            break
        
        try:
            values.append(int(value_str))
        except ValueError:
            # Skip if not a valid number (might be trailing spaces)
            pass
        pos += chars_per_value
    
    if len(values) != total_values_needed:
        raise ValueError(f"Expected {total_values_needed} values, got {len(values)} in {filepath}")
    
    # Reshape to grid
    data = np.array(values, dtype=np.float32).reshape(nrows, ncols)
    
    return data, {'ncols': ncols, 'nrows': nrows}


def collect_all_timestamps(results_dir: str, field_prefix: str) -> Tuple[np.ndarray, List[int]]:
    """
    Collect all timestamped ASC files for a given field prefix.
    
    Args:
        results_dir: Directory containing KLAM output files
        field_prefix: Field name prefix (e.g., 'uq', 'vq', 'uz', 'vz', 'Hx', 'Ex')
    
    Returns:
        Tuple of (data_array, timestamps) where data_array is (T, H, W) and
        timestamps is list of seconds [3600, 7200, 10800, 14400]
    """
    import re
    
    # Find all files for this field
    all_files = sorted(os.listdir(results_dir))
    field_files = [f for f in all_files if f.startswith(field_prefix) and f.endswith('.asc')]
    
    if not field_files:
        return None, []
    
    # Parse timestamps from filenames (e.g., 'uq003600.asc' -> 3600)
    timestamped_files = []
    for f in field_files:
        # Extract numeric part between prefix and .asc
        match = re.match(rf'{field_prefix}(\d+)\.asc', f)
        if match:
            timestamp = int(match.group(1))
            timestamped_files.append((timestamp, f))
    
    # Sort by timestamp
    timestamped_files.sort(key=lambda x: x[0])
    
    if not timestamped_files:
        return None, []
    
    # Read all timestamped files
    timestamps = []
    data_list = []
    
    for timestamp, filename in timestamped_files:
        filepath = os.path.join(results_dir, filename)
        data, _ = read_asc_file(filepath)
        data_list.append(data)
        timestamps.append(timestamp)
    
    # Stack into (T, H, W) array
    data_array = np.stack(data_list, axis=0)
    
    return data_array, timestamps


# --- KLAM_21 Simulation and Fitness Calculation ---
def generate_klam_in(run_dir: str, config: Dict):
    """Generates the klam_21.in file with dynamic output times."""
    nx, ny, dx = config['nx'], config['ny'], config['dx']
    sim_duration = int(config['sim_duration'])
    hourly_timestamps = range(3600, sim_duration, 3600)
    output_times = sorted(list(set(list(hourly_timestamps) + [sim_duration])))
    niozeit = len(output_times)
    iozeit_str = ", ".join(map(str, output_times))
    content = f"""
&output
  xtension='asc'
  resdir='results'
  niozeit={niozeit}
  iozeit={iozeit_str}
  zaus=2.
/end
&grid
  nx={nx}
  ny={ny}
  dx={dx}
  h0_file='examples/terrain.asc', nsth0=8
  b_file='examples/buildings.asc'
  nesting=.false.
/end
&perform
  ttotal={sim_duration}
  dtmax=0.5
  vregio={config['wind_speed']}
  phiregio={config['wind_direction']}
  ianimat=10
/end
&pollution
  pollut=.FALSE.
/end
&landuse
  fn_file='examples/landuse.asc', nstfn=1
/end
&zeitreihe
  nmesp=0
/end
"""
    with open(os.path.join(run_dir, "klam_21.in"), "w") as f:
        f.write(content)

def compute_fitness_klam(config_environment: Dict, config_encoding: Dict, phenotype_voxels: np.ndarray, phenotype_floors: np.ndarray, debug: bool = False, collect_spatial_data: bool = False) -> Dict:
    klam_config = config_environment['klam_config']
    
    # Get physical dimensions and scales
    design_cells = config_encoding['length_design']
    xy_scale = config_encoding.get('xy_scale', 3.0)
    z_scale = config_encoding.get('z_scale', 3.0)
    
    # Calculate domain size based on parcel size
    # The domain must be large enough to hold the parcel plus buffer zones
    # We use 100% extension on each side: domain = 3 × parcel_size
    parcel_size_m = design_cells * xy_scale
    env_size_m = max(config_environment.get('environment_xy_size', 200), parcel_size_m * 3)
    
    # Calculate grid size of the environment (square base)
    env_cells_base = int(env_size_m / xy_scale)
    
    # Extend domain 100% more to the left (upwind) to avoid inlet artifacts
    # Original offset would be: (env_cells_base - design_cells) // 2
    original_offset = (env_cells_base - design_cells) // 2
    left_extension = original_offset  # Add 100% more space to the left
    
    # New domain dimensions: extended in x (columns), same in y (rows)
    env_cells_x = env_cells_base + left_extension  # Extended width
    env_cells_y = env_cells_base  # Original height
    
    run_dir = tempfile.mkdtemp(prefix="klam_run_")
    cleanup_dir = not debug

    try:
        examples_dir = os.path.join(run_dir, "examples")
        os.makedirs(examples_dir)
        results_dir = os.path.join(run_dir, "results")
        os.makedirs(results_dir)
        
        env_buildings = np.zeros((env_cells_y, env_cells_x))
        
        # Calculate parcel position (shifted right due to left extension)
        offset_cells_x = original_offset + left_extension  # Column offset (x)
        offset_cells_y = original_offset  # Row offset (y) - unchanged
        parcel_center_col = offset_cells_x + design_cells // 2
        
        # Create terrain with continuous 2° slope across entire domain
        # 2° slope = tan(2°) ≈ 0.0349 m drop per 1 m horizontal distance
        # This provides sufficient gravitational forcing for pure katabatic cold air drainage
        slope_angle_deg = 2.0
        slope_gradient = np.tan(np.radians(slope_angle_deg))  # ~0.0349
        
        env_terrain = np.zeros((env_cells_y, env_cells_x))
        # Apply continuous slope to ALL columns (increases toward left/upwind)
        for col in range(env_cells_x):
            # Distance from right edge (slope increases toward left)
            distance_from_right_m = (env_cells_x - col) * xy_scale
            elevation = distance_from_right_m * slope_gradient
            env_terrain[:, col] = elevation
        
        # Set landuse: Left of parcel = 7 (free space), Parcel and right = 2 (low-density buildings)
        env_landuse = np.ones((env_cells_y, env_cells_x), dtype=np.int8)
        env_landuse[:, :offset_cells_x] = 7  # Left side (upwind) = free space
        env_landuse[:, offset_cells_x:] = 2  # Parcel and right side (downwind) = low-density buildings
        
        # Embed the scaled design into the building data
        design_buildings_m = phenotype_floors * z_scale
        env_buildings[offset_cells_y:offset_cells_y+design_cells, offset_cells_x:offset_cells_x+design_cells] = design_buildings_m
        
        # Write ASC files without headers (KLAM expects raw data)
        write_terrain_asc_file(examples_dir, "terrain.asc", env_terrain)
        write_buildings_asc_file(examples_dir, "buildings.asc", env_buildings)
        write_landuse_asc_file(examples_dir, "landuse.asc", env_landuse)
        
        # Configure and run KLAM with correct nx, ny, and dx (rectangular domain)
        sim_config = klam_config.copy()
        sim_config.update({'nx': env_cells_x, 'ny': env_cells_y, 'dx': xy_scale})
        generate_klam_in(run_dir, sim_config)
        
        # Calculate timeout based on domain size (larger domains need more time)
        # Empirical: 60m parcel (5,874 cells) takes ~10s, scales roughly linearly
        # Use generous formula: base 300s + 1s per 100 cells (with 2x safety factor)
        total_cells = env_cells_x * env_cells_y
        timeout_seconds = max(300, 300 + int(total_cells / 50))  # 300s base + 1s per 50 cells
        
        binary_path = os.path.abspath(klam_config['binary_path'])
        proc_result = subprocess.run([binary_path, 'klam_21.in'], cwd=run_dir, capture_output=True, text=True, timeout=timeout_seconds)
        
        if proc_result.returncode != 0:
            raise RuntimeError(f"KLAM_21 failed with return code {proc_result.returncode}.\nSTDERR: {proc_result.stderr}\nSTDOUT: {proc_result.stdout}")
        
        # Parse results from output directory
        results_dir = os.path.join(run_dir, "results")
        all_result_files = sorted(os.listdir(results_dir))
        
        # Collect full spatial data for all timestamps if requested
        if collect_spatial_data:
            # Collect all timestamps for each field (returns (T, H, W) arrays)
            uq_all, timestamps = collect_all_timestamps(results_dir, 'uq')
            vq_all, _ = collect_all_timestamps(results_dir, 'vq')
            uz_all, _ = collect_all_timestamps(results_dir, 'uz')
            vz_all, _ = collect_all_timestamps(results_dir, 'vz')
            hx_all, _ = collect_all_timestamps(results_dir, 'Hx')
            ex_all, _ = collect_all_timestamps(results_dir, 'Ex')
            
            if uq_all is None or vq_all is None:
                raise FileNotFoundError("Could not find 'uq' or 'vq' files.")
            
            # Use final timestamp for fitness calculation
            uq_data = uq_all[-1]
            vq_data = vq_all[-1]
            uz_data = uz_all[-1] if uz_all is not None else None
            vz_data = vz_all[-1] if vz_all is not None else None
            hx_data = hx_all[-1] if hx_all is not None else None
            ex_data = ex_all[-1] if ex_all is not None else None
        else:
            # Original behavior: read only final timestamp
            final_uq_file = next((f for f in reversed(all_result_files) if f.startswith('uq')), None)
            final_vq_file = next((f for f in reversed(all_result_files) if f.startswith('vq')), None)
            final_uz_file = next((f for f in reversed(all_result_files) if f.startswith('uz')), None)
            final_vz_file = next((f for f in reversed(all_result_files) if f.startswith('vz')), None)
            final_hx_file = next((f for f in reversed(all_result_files) if f.startswith('Hx')), None)
            final_ex_file = next((f for f in reversed(all_result_files) if f.startswith('Ex')), None)
            
            if not final_uq_file or not final_vq_file: 
                raise FileNotFoundError("Could not find 'uq' or 'vq' files.")
            
            uq_data, _ = read_asc_file(os.path.join(results_dir, final_uq_file))
            vq_data, _ = read_asc_file(os.path.join(results_dir, final_vq_file))
            
            # Read uz/vz (vertical column averages) if available
            uz_data = None
            vz_data = None
            if final_uz_file and final_vz_file:
                uz_data, _ = read_asc_file(os.path.join(results_dir, final_uz_file))
                vz_data, _ = read_asc_file(os.path.join(results_dir, final_vz_file))
            
            # Read Hx (cold airflow height) if available - output is in 1/10 m
            hx_data = None
            if final_hx_file:
                hx_data, _ = read_asc_file(os.path.join(results_dir, final_hx_file))
            
            # Read Ex (cold air content / Kälteinhalt) if available - output is in 100 J/m²
            ex_data = None
            if final_ex_file:
                ex_data, _ = read_asc_file(os.path.join(results_dir, final_ex_file))
            
            # Initialize for compatibility
            uq_all, vq_all, uz_all, vz_all, hx_all, ex_all, timestamps = None, None, None, None, None, None, []
        
        # Convert Hx from 1/10 m to m (for final timestamp used in fitness calc)
        if hx_data is not None:
            hx_data = hx_data / 10.0
        
        # KLAM outputs velocities in cm/s - convert to m/s
        uq_data = uq_data / 100.0
        vq_data = vq_data / 100.0
        if uz_data is not None:
            uz_data = uz_data / 100.0
        if vz_data is not None:
            vz_data = vz_data / 100.0
        
        # Calculate wind speed at 2m height
        wind_speed_2m = np.sqrt(uq_data**2 + vq_data**2)
        
        # Define ROI: parcel + 50% buffer, extended to right edge (downwind)
        buffer_size = int(design_cells * 0.5)
        roi_start_y = max(0, offset_cells_y - buffer_size)
        roi_end_y = min(env_cells_y, offset_cells_y + design_cells + buffer_size)
        roi_start_x = max(0, offset_cells_x - buffer_size)
        roi_end_x = env_cells_x  # Extend to right edge (downwind direction)
        
        # Calculate mean values over ROI
        wind_speed_2m_roi = wind_speed_2m[roi_start_y:roi_end_y, roi_start_x:roi_end_x]
        mean_wind_speed_2m = np.mean(wind_speed_2m_roi)
        
        # Calculate Cold Air Flux: Φ = Ex × u_2m
        # This captures both thermal content and transport capacity
        if ex_data is not None:
            ex_roi = ex_data[roi_start_y:roi_end_y, roi_start_x:roi_end_x]
            mean_ex = np.mean(ex_roi)
            cold_air_flux = mean_ex * mean_wind_speed_2m  # Units: (100 J/m²) × (m/s) = 100 W/m²
            fitness = cold_air_flux
        else:
            # Fallback to wind speed if Ex not available
            fitness = mean_wind_speed_2m
            print("WARNING: Ex data not available, falling back to wind speed objective")
        
        # Build result dictionary
        result = {
            'fitness': max(0.0, fitness),
            'uq': uq_data, 'vq': vq_data,
            'uz': uz_data, 'vz': vz_data,
            'hx': hx_data, 'ex': ex_data
        }
        
        # Add full spatial data if requested
        if collect_spatial_data:
            result['spatial_data'] = {
                # Grid metadata
                'grid_shape': (env_cells_y, env_cells_x),
                'parcel_offset': (offset_cells_y, offset_cells_x),
                'parcel_size': (design_cells, design_cells),
                'cell_size': xy_scale,
                'timestamps': timestamps,
                
                # KLAM config
                'wind_speed': klam_config['wind_speed'],
                'wind_direction': klam_config['wind_direction'],
                'sim_duration': klam_config['sim_duration'],
                
                # INPUTS (already in correct units)
                'terrain': env_terrain.astype(np.float16),  # meters
                'buildings': env_buildings.astype(np.float16),  # meters
                'landuse': env_landuse.astype(np.int8),  # category codes
                
                # OUTPUTS - raw integer values (cm/s, 1/10 m, 100 J/m²)
                # Keep raw for maximum precision with float16
                'uq_all': uq_all.astype(np.float16) if uq_all is not None else None,
                'vq_all': vq_all.astype(np.float16) if vq_all is not None else None,
                'uz_all': uz_all.astype(np.float16) if uz_all is not None else None,
                'vz_all': vz_all.astype(np.float16) if vz_all is not None else None,
                'hx_all': hx_all.astype(np.float16) if hx_all is not None else None,
                'ex_all': ex_all.astype(np.float16) if ex_all is not None else None,
            }
        
        return result

    except Exception as e:
        import traceback
        print(f"ERROR: KLAM-21 failed. Input files are in: {run_dir}\nReason: {e}\n{traceback.format_exc()}")
        cleanup_dir = False
        result = {'fitness': np.nan, 'uq': None, 'vq': None, 'uz': None, 'vz': None, 'hx': None, 'ex': None}
        if collect_spatial_data:
            result['spatial_data'] = None
        return result
    finally:
        if cleanup_dir: shutil.rmtree(run_dir)


# --- Main Evaluation Functions ---
def init_environment(config_environment: Dict) -> Dict:
    """Passes design length into the config for later use."""
    with open("encodings/parametric/cfg.yml") as f:
        config_solution = yaml.safe_load(f)
    config_environment['length_design'] = config_solution['length_design']
    return config_environment

def convert_from_numpy(solution, solution_template):
    solution_template.set_genome(solution)
    return solution_template

def calculate_compactness(heightmap: np.ndarray, pixel_size: float) -> float:
    """
    Calculate Surface-to-Volume ratio (A/V).
    Lower values indicate more compact forms (better for heat retention).
    """
    from scipy.ndimage import distance_transform_edt
    
    volume = np.sum(heightmap) * (pixel_size ** 2)
    if volume == 0:
        return 0.0
    
    # Roof area
    roof_area = np.sum(heightmap > 0) * (pixel_size ** 2)
    
    # Wall area calculation (vectorized)
    # Pad heightmap to handle boundaries (assume 0 height outside)
    padded = np.pad(heightmap, 1, mode='constant', constant_values=0)
    
    # Calculate positive height differences with 4 neighbors
    # (height - neighbor) > 0 contributes to wall area
    diff_n = np.maximum(0, padded[1:-1, 1:-1] - padded[0:-2, 1:-1])
    diff_s = np.maximum(0, padded[1:-1, 1:-1] - padded[2:, 1:-1])
    diff_w = np.maximum(0, padded[1:-1, 1:-1] - padded[1:-1, 0:-2])
    diff_e = np.maximum(0, padded[1:-1, 1:-1] - padded[1:-1, 2:])
    
    total_height_diff = np.sum(diff_n + diff_s + diff_w + diff_e)
    wall_area = total_height_diff * pixel_size
    
    surface_area = roof_area + wall_area
    
    return surface_area / volume

def calculate_park_factor(heightmap: np.ndarray, pixel_size: float) -> float:
    """
    Calculate 'Park Factor' (Green Space Radius).
    Average distance from any open space pixel to the nearest building.
    Higher values indicate larger contiguous open spaces.
    """
    from scipy.ndimage import distance_transform_edt
    
    open_space = heightmap == 0
    if not np.any(open_space):
        return 0.0
        
    # Distance transform: calculates distance to nearest background (0) pixel.
    # We want distance to nearest BUILDING. So Buildings should be 0, Open Space 1.
    # heightmap > 0 gives True (1) for buildings.
    # We invert it: heightmap == 0 gives True (1) for open space.
    # So input to edt is 1 for open space, 0 for buildings.
    # edt returns distance to nearest 0 (building).
    dist_map_pixels = distance_transform_edt(heightmap == 0)
    
    dist_map_meters = dist_map_pixels * pixel_size
    
    # Average over open pixels only
    return np.mean(dist_map_meters[open_space])

def calculate_planning_features(heightmap: np.ndarray, config_encoding: Dict) -> np.ndarray:
    """
    Calculate the 8 CONSOLIDATED features matching OpenSKIZZE GUI (MVP).
    
    Args:
        heightmap: Building heights in meters (grid)
        config_encoding: Encoding configuration with xy_scale, z_scale, etc.
    
    Returns:
        Array of planning-focused features:
        [0] GRZ (Site Coverage Ratio) - ratio 0-1
        [1] GFZ (Floor Area Ratio) - ratio
        [2] Average Building Height (m)
        [3] Height Variability (m) - Standard Deviation
        [4] Average Building Distance (m) - Porosity
        [5] Number of Buildings (count) - Grain
        [6] Compactness (A/V Ratio) - 1/m - Energy
        [7] Park Factor (Green Space Radius) - m - Social
    """
    grid_res_y, grid_res_x = heightmap.shape
    occupied = heightmap > 0
    pixel_size = config_encoding.get('xy_scale', 1.0)
    pixel_area = pixel_size ** 2
    
    # Calculate buildable area (entire grid for now)
    buildable_area_in_sq_meters = grid_res_y * grid_res_x * pixel_area
    
    building_heights = heightmap[occupied]
    if not building_heights.any():
        return np.zeros(8)  # Return zeros for all 8 features
    
    # [0] GRZ (Grundflächenzahl) - Site Coverage Ratio
    # GRZ = Built Area / Total Site Area
    occupied_pixels = np.sum(occupied)
    built_area_m2 = occupied_pixels * pixel_area
    grz = built_area_m2 / buildable_area_in_sq_meters if buildable_area_in_sq_meters > 0 else 0.0
    grz = np.clip(grz, 0.0, 1.0)
    
    # [1] GFZ (Geschossflächenzahl) - Floor Area Ratio
    # GFZ = Total Floor Area / Total Site Area
    # Each meter of height contributes to floor area
    total_floor_area_m2 = np.sum(heightmap) * pixel_area
    gfz = total_floor_area_m2 / buildable_area_in_sq_meters if buildable_area_in_sq_meters > 0 else 0.0
    
    # [2] Average Height - heightmap is already in METERS
    avg_height_meters = np.mean(building_heights)
    
    # [3] Height Variability (m) - Standard Deviation
    height_std = np.std(building_heights)
    
    # [4] Average Building Distance (m) - Porosity
    labeled_array, num_buildings = label(occupied)
    if num_buildings > 1:
        centroids = np.array(center_of_mass(occupied, labeled_array, range(1, num_buildings + 1)))
        diff = centroids[:, None, :] - centroids[None, :, :]
        dists = np.sqrt(np.sum(diff**2, axis=-1))
        avg_spacing_pixels = np.mean(dists[np.triu_indices(num_buildings, k=1)])
        avg_spacing_meters = avg_spacing_pixels * pixel_size
    else:
        avg_spacing_meters = 0.0
        
    # [5] Number of Buildings (count) - Grain
    # num_buildings already calculated
    
    # [6] Compactness (A/V Ratio) - Energy
    compactness = calculate_compactness(heightmap, pixel_size)
    
    # [7] Park Factor (Green Space Radius) - Social
    park_factor = calculate_park_factor(heightmap, pixel_size)
    
    return np.array([
        grz, gfz, avg_height_meters, height_std,
        avg_spacing_meters, num_buildings, compactness, park_factor
    ])


def eval(solution, config_environment: Dict, config_encoding: Dict, solution_template, use_surrogate=False, debug=False, collect_spatial_data=False) -> Tuple:
    solution_template.set_genome(solution)
    phenotype_voxels = solution_template.express(as_height_map=False)
    phenotype_floors = solution_template.express(as_height_map=True)
    
    # Scale factors for physical dimensions
    xy_scale = config_encoding.get('xy_scale', 1.0)
    z_scale = config_encoding.get('z_scale', 3.0)
    phenotype_heightmap = phenotype_floors * z_scale
    
    # --- Calculate Planning Features (GUI implementation) ---
    all_features = calculate_planning_features(phenotype_heightmap, config_encoding)
    
    # --- Run KLAM simulation if needed ---
    if not use_surrogate:
        sim_results = compute_fitness_klam(config_environment, config_encoding, phenotype_voxels, phenotype_floors, debug=debug, collect_spatial_data=collect_spatial_data)
        fitness = sim_results['fitness']
        debug_data = (sim_results['uq'], sim_results['vq'], sim_results.get('uz'), sim_results.get('vz'), sim_results.get('hx'), sim_results.get('ex'))
        spatial_data = sim_results.get('spatial_data') if collect_spatial_data else None
    else:
        fitness = 0.0
        debug_data = (None, None, None, None, None, None)
        spatial_data = None

    # Select features based on config
    features = all_features[config_environment['features']]
    result_array = np.concatenate(([fitness], features, phenotype_floors.flatten()))
    return result_array, debug_data, spatial_data


def _eval_single_for_pool(args):
    """
    Wrapper for eval() that can be pickled for multiprocessing.
    Takes a tuple of (idx, solution, config_environment, config_encoding, solution_template, use_surrogate, debug, collect_spatial_data).
    Returns (idx, result, error_string_or_None).
    """
    idx, sol, config_environment, config_encoding, solution_template, use_surrogate, debug, collect_spatial_data = args
    try:
        result = eval(sol, config_environment, config_encoding, solution_template, use_surrogate, debug, collect_spatial_data)
        return (idx, result, None)
    except Exception as e:
        # Return a failed result with NaN values
        n_features = len(config_environment.get('features', [0,1,2,3,4,5,6,7]))
        length_design = config_encoding.get('length_design', 17)
        dummy_result = np.full(1 + n_features + length_design * length_design, np.nan)
        dummy_debug = (None, None, None, None, None, None)
        dummy_spatial = None
        return (idx, (dummy_result, dummy_debug, dummy_spatial), str(e))


def eval_multiple(solutions, config_environment: Dict, config_encoding: Dict, solution_template, surrogate_model=None, lambda_ucb=0.1, pool=None, debug=False, collect_spatial_data=False) -> Tuple:
    """
    Evaluates multiple solutions.
    Returns standard numpy results AND a list of debug data if debug=True.
    If collect_spatial_data=True, also returns spatial data for each sample.
    
    Uses pool.imap_unordered for better reliability when using multiprocessing,
    with proper error handling to prevent hangs on worker failures.
    """
    use_surrogate = surrogate_model is not None
    n_solutions = len(solutions)
    
    eval_results = []
    
    if pool is None:
        # Sequential evaluation
        eval_results = [eval(sol, config_environment, config_encoding, solution_template, use_surrogate, debug=debug, collect_spatial_data=collect_spatial_data) for sol in solutions]
    else:
        # Parallel evaluation using imap_unordered for better reliability
        # Pack all arguments into tuples (function must be module-level for pickling)
        indexed_args = [
            (i, sol, config_environment, config_encoding, solution_template, use_surrogate, debug, collect_spatial_data) 
            for i, sol in enumerate(solutions)
        ]
        
        # Use imap_unordered - it yields results as they complete and handles failures better
        results_dict = {}
        errors = []
        
        try:
            for idx, result, error in pool.imap_unordered(_eval_single_for_pool, indexed_args):
                results_dict[idx] = result
                if error:
                    errors.append(f"Sample {idx}: {error}")
        except Exception as e:
            print(f"WARNING: Pool evaluation encountered error: {e}")
            # Fill remaining with NaN
            for i in range(n_solutions):
                if i not in results_dict:
                    n_features = len(config_environment.get('features', [0,1,2,3,4,5,6,7]))
                    length_design = config_encoding.get('length_design', 17)
                    dummy_result = np.full(1 + n_features + length_design * length_design, np.nan)
                    dummy_debug = (None, None, None, None, None, None)
                    dummy_spatial = None
                    results_dict[i] = (dummy_result, dummy_debug, dummy_spatial)
        
        if errors:
            print(f"WARNING: {len(errors)} samples failed evaluation")
        
        # Reconstruct results in original order
        eval_results = [results_dict[i] for i in range(n_solutions)]
        
    # Unpack the results
    results_arrays = np.array([res[0] for res in eval_results])
    debug_data_list = [res[1] for res in eval_results] if debug else None
    spatial_data_list = [res[2] for res in eval_results] if collect_spatial_data else None

    # Surrogate logic (unchanged)
    if surrogate_model is not None:
        heightmap_start = len(config_environment['features']) + 1
        heightmaps = results_arrays[:, heightmap_start:]
        ucb = acquire_ucb(surrogate_model, heightmaps, lambda_ucb=lambda_ucb)
        results_arrays[:, 0] = ucb
        
    return np.atleast_2d(results_arrays), debug_data_list, spatial_data_list

def main(genomes=None):
    run_parallel = False
    debug = False

    with open("domain_description/cfg.yml") as f:
        config_environment = yaml.safe_load(f)
    with open('encodings/parametric/cfg.yml') as f:
        config_encoding: Dict = yaml.safe_load(f)

    from encodings.parametric import ParametricEncoding as Encoding  # Uses NumbaFastEncoding
    solution_template=Encoding()
    if run_parallel:
        import psutil
        import multiprocessing
        nb_cpus = psutil.cpu_count(logical=True)
        pool = multiprocessing.Pool(processes=nb_cpus)
    else:
        pool = None
    
    if genomes is None:
        print("No genomes provided for evaluation. Creating random genomes using generate_sobol_sequence_genome from solution template.")
        genomes = solution_template.generate_sobol_sequence_genome(num_samples_base2=4)
        
    eval_multiple(genomes, config_environment, config_encoding, solution_template, surrogate_model=None, pool=pool, debug=debug)

if __name__ == "__main__":
    from gp_utils import train_gp, eval_gp, acquire_ucb
    genomes = None
    # Load your genomes here!
    print("If no genomes are provided, a random set of genomes will be evaluated.")
    main(genomes)
