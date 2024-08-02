
import numpy as np
import rasterio
from rasterio.transform import from_origin

def create_example_data(filename, data, width, height, transform):
    with rasterio.open(
        filename, 'w',
        driver='GTiff',
        height=height,
        width=width,
        count=1,
        dtype=data.dtype,
        crs='+proj=latlong',
        transform=transform,
    ) as dst:
        dst.write(data, 1)

width = 100
height = 100
transform = from_origin(-123.25, 45.75, 0.0001, 0.0001)

# Create DEM data
dem_data = np.random.rand(height, width).astype('float32') * 100
create_example_data('example_dem.tif', dem_data, width, height, transform)

# Create DSM data
dsm_data = dem_data + (np.random.rand(height, width).astype('float32') * 20)
create_example_data('example_dsm.tif', dsm_data, width, height, transform)

# Create LCM data
lcm_data = (np.random.rand(height, width).astype('int32') % 3) + 1  # land cover types 1, 2, 3
create_example_data('example_lcm.tif', lcm_data, width, height, transform)
