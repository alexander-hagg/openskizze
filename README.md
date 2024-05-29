# openskizze

Current GUI design:

![Screenshot from 2024-04-30 15-01-45](https://github.com/FullDA-FM/openskizze-gui/assets/1055659/4cc87b6a-9303-4d37-9afe-011e0f3c08f8)


# Requirements

- Installation of three.js. Make sure you provide ./vendor/three/build/three.module.js and ./vendor/three/examples/jsm/controls/OrbitControls.js
- Python: flask, numpy, pillow

# Components

## Input parameters

- REMOVE air flow criteria. Remove ZURES input. CFD should be run based on temperature differences.
- Digital surface model (DSM): A raster grid including both buildings and ground given in meter above sea level.
- Digital elevation model (DEM/DTM): A raster grid including only ground heights given in meter above sea level. 
- Landcover

## Criteria: as objective or feature
- Porosity (nonCFD)
- Airflow volume throughput at eye level (CFD)
- Heat radiation (based on surface type)
- Facade surface area
- Number of buildings
- Building surface area
- Built area
- Sky view factor


## Multilingual
EN + DE