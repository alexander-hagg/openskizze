# import gdal
from osgeo import gdal
dsm_path = 'data/Goteborg_SWEREF99_1200/DSM_KRbig.tif'
ds = gdal.Open(dsm_path)
dsm_data = ds.GetRasterBand(1).ReadAsArray()
print(dsm_data)