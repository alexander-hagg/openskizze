import time
import numpy as np

# Mock functions for the back-end processes
def load_geodata(coordinates):
    # Mocking a delay for data retrieval
    time.sleep(0)
    return f"Mocked GIS data for area with coordinates: {coordinates}"

def run_optimization(morph_features):
    # Initialize a (10, 10, 10) array with zeros
    volume = np.zeros((10, 10, 10))
    
    # Randomly select the starting coordinates and dimensions of the rectangle
    x_start = np.random.randint(0, 7)
    y_start = np.random.randint(0, 7)
    width = np.random.randint(1, 4)
    height = np.random.randint(1, 4)
    
    # Assign random height values between 0 and 3 to the selected rectangle region
    volume[x_start:x_start+width, y_start:y_start+height, :] = np.random.rand(width, height, 10) * 3
    
    return volume

def predict_airflow(selected_design):
    # Generate airflow data influenced by the design
    base_airflow = np.random.rand(100, 100)
    influence = np.sin(np.linspace(0, np.pi, 100))[:, None] * np.cos(np.linspace(0, np.pi, 100))[None, :]
    
    influenced_airflow = base_airflow + influence * selected_design
    return influenced_airflow

def cluster_designs(design_data):
    return np.random.randint(0, 3, size=(10,))

# Helper functions
def meters_to_lat_lon(center_lat, center_lon, meters):
    # Constants
    earth_radius = 6378137.0  # in meters

    # Latitude calculation
    delta_lat = meters / earth_radius
    delta_lat_deg = delta_lat * (180 / np.pi)

    # Longitude calculation (adjusted by latitude)
    delta_lon = meters / (earth_radius * np.cos(np.pi * center_lat / 180))
    delta_lon_deg = delta_lon * (180 / np.pi)

    return delta_lat_deg, delta_lon_deg

def rotate_and_map_points(center_lat, center_lon, wind_dir, grid_size=100):
    wind_dir_rad = np.radians(wind_dir)
    
    # Calculate half the side length
    half_grid_size = grid_size / 2
    
    # Define the rectangle's points around the center (local coordinates)
    local_points = [
        [-half_grid_size, -half_grid_size],  # bottom-left
        [-half_grid_size, half_grid_size],   # top-left
        [half_grid_size, half_grid_size],    # top-right
        [half_grid_size, -half_grid_size]    # bottom-right
    ]

    # Rotate and map to geographic coordinates
    global_points = []
    for x, y in local_points:
        # Rotate the point by the wind direction
        x_rot = x * np.cos(wind_dir_rad) - y * np.sin(wind_dir_rad)
        y_rot = x * np.sin(wind_dir_rad) + y * np.cos(wind_dir_rad)
        
        # Map the rotated point to geographic coordinates
        delta_lat, delta_lon = meters_to_lat_lon(center_lat, center_lon, x_rot)
        mapped_lat = center_lat + delta_lat
        mapped_lon = center_lon + meters_to_lat_lon(center_lat, center_lon, y_rot)[1]
        
        global_points.append([mapped_lat, mapped_lon])

    return global_points


def find_nearest_grid_point(click_lat_lng, polygon_points, num_grid_lines=20):
    # Extract boundaries of the grid
    lat_min, lon_min = polygon_points[0][0], polygon_points[0][1]
    lat_max, lon_max = polygon_points[2][0], polygon_points[2][1]
    
    # Calculate grid cell size
    lat_step = (lat_max - lat_min) / num_grid_lines
    lon_step = (lon_max - lon_min) / num_grid_lines
    
    # Snap to nearest grid point
    lat_idx = np.round((click_lat_lng[0] - lat_min) / lat_step)
    lon_idx = np.round((click_lat_lng[1] - lon_min) / lon_step)
    
    snapped_lat = lat_min + lat_idx * lat_step
    snapped_lon = lon_min + lon_idx * lon_step
    
    return [snapped_lat, snapped_lon]

