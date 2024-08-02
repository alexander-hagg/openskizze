import rasterio
from rasterio.warp import calculate_default_transform, reproject, Resampling
import folium
import numpy as np

filename = 'data/Goteborg_SWEREF99_1200/DSM_KRbig.tif'

# Open the DSM TIF file
with rasterio.open(filename) as src:
    # Define the destination CRS
    dst_crs = 'EPSG:4326'
    
    # Calculate the transform and dimensions of the reprojected raster
    transform, width, height = calculate_default_transform(
        src.crs, dst_crs, src.width, src.height, *src.bounds)
    
    # Create a new array for the reprojected data
    elevArray = np.empty((height, width), dtype=src.dtypes[0])
    
    # Perform the reprojection
    reproject(
        source=rasterio.band(src, 1),
        destination=elevArray,
        src_transform=src.transform,
        src_crs=src.crs,
        dst_transform=transform,
        dst_crs=dst_crs,
        resampling=Resampling.nearest
    )
    
    # Get the bounds of the reprojected raster
    bounds = rasterio.transform.array_bounds(height, width, transform)
    boundList = [bounds[0], bounds[2], bounds[1], bounds[3]]

# Normalize the elevation data for better visualization
elevArray = np.nan_to_num(elevArray)
elevArray = (elevArray - np.min(elevArray)) / (np.max(elevArray) - np.min(elevArray)) * 255
elevArray = elevArray.astype(np.uint8)
print(elevArray)

# Calculate the center of the raster for map centering
rasLon = (boundList[1] + boundList[0]) / 2
rasLat = (boundList[3] + boundList[2]) / 2
mapCenter = [rasLat, rasLon]

# Create a Folium map centered at the raster's center
m = folium.Map(location=mapCenter, zoom_start=18)

# Add raster overlay
image = folium.raster_layers.ImageOverlay(
    image=elevArray,
    bounds=[[boundList[2], boundList[0]], [boundList[3], boundList[1]]],
    opacity=0.8,
    interactive=True,
    cross_origin=False,
    colormap=lambda x: (x, x, x, 255)  # Grayscale colormap
)
image.add_to(m)

# Add layer control
folium.LayerControl().add_to(m)

# Display the map
m.save('map.html')
