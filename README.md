# openskizze

Design:
![GUI_3](https://github.com/alexander-hagg/openskizze/assets/1055659/a421eeaf-89e3-4427-9b38-63bf4e647d19)

Current GUI:
![Screenshot from 2023-11-30 15-35-25](https://github.com/alexander-hagg/openskizze/assets/1055659/8e31743f-37b6-4ae3-8282-a1ef7e53af2f)

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
