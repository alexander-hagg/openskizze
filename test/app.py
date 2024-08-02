import streamlit as st
import pandas as pd
import numpy as np
import folium
import json
from streamlit_folium import st_folium
from folium.plugins import Draw
from shapely.geometry import Polygon, box
import rasterio
from rasterio.warp import calculate_default_transform, reproject, Resampling
import geopandas as gpd
from osgeo import gdal
import matplotlib.pyplot as plt

# Load translations
@st.cache_resource
def load_translations(lang):
    with open(f'{lang}.json', 'r') as file:
        translations = json.load(file)
    return translations

# Function to change language
def set_language():
    st.sidebar.title("Language / Idioma / Sprache")
    lang = st.sidebar.selectbox("Select Language", ["English", "Deutsch", "Español"])
    if lang == "Deutsch":
        return "de"
    elif lang == "Español":
        return "es"
    else:
        return "en"

# Global variable for language
lang = set_language()
translations = load_translations(lang)

def translate(key):
    return translations[key]

def main():
    st.title(translate("title"))

    if 'current_page' not in st.session_state:
        st.session_state.current_page = "home"

    # Create a sidebar for navigation with buttons
    st.sidebar.title(translate("navigation"))
    if st.sidebar.button(translate("home")):
        st.session_state.current_page = "home"
    if st.sidebar.button(translate("input_models")):
        st.session_state.current_page = "input_models"
    if st.sidebar.button(translate("visualize_models")):
        st.session_state.current_page = "visualize_models"
    if st.sidebar.button(translate("optimization_criteria")):
        st.session_state.current_page = "optimization_criteria"
    if st.sidebar.button(translate("results")):
        st.session_state.current_page = "results"
    if st.sidebar.button(translate("deduced_rules")):
        st.session_state.current_page = "deduced_rules"

    # Display the current page
    if st.session_state.current_page == 'home':
        home_page()
    elif st.session_state.current_page == 'input_models':
        input_models_page()
    elif st.session_state.current_page == 'visualize_models':
        visualize_models_page()
    elif st.session_state.current_page == 'optimization_criteria':
        optimization_criteria_page()
    elif st.session_state.current_page == 'results':
        results_page()
    elif st.session_state.current_page == 'deduced_rules':
        deduced_rules_page()

def home_page():
    st.header(translate("welcome"))
    st.subheader(translate("how_it_works"))
    st.write(f"""
    1. **{translate('input_models')}**: {translate('upload_models')}
    2. **{translate('visualize_models')}**: {translate('model_visualization')} 
    3. **{translate('optimization_criteria')}**: {translate('optimization_criteria_selection')} 
    4. **{translate('results')}**: {translate('optimization_results')} 
    5. **{translate('deduced_rules')}**: {translate('deduced_rules_consequences')}
    """)
    
    # Placeholder for images, which will be provided later
    # st.image("path/to/your/image1.jpg", caption=translate("placeholder"))
    
uploaded_dsm = None
uploaded_lcm = None
selected_area = []

def load_default_file(filename):
    return open(filename, 'rb')

@st.cache_data
def load_input_models():
    if 'uploaded_dsm' in st.session_state and 'uploaded_lcm' in st.session_state:
        # Define the destination CRS
        dst_crs = 'EPSG:4326'    
        
        with rasterio.open(st.session_state.uploaded_dsm) as dsm_src:
            # Calculate the transform and dimensions of the reprojected raster
            transform, width, height = calculate_default_transform(
                dsm_src.crs, dst_crs, dsm_src.width, dsm_src.height, *dsm_src.bounds)
            
            # Create a new array for the reprojected data
            st.session_state.dsm_data = np.empty((height, width), dtype=dsm_src.dtypes[0])

            # Perform the reprojection
            reproject(
                source=rasterio.band(dsm_src, 1),
                destination=st.session_state.dsm_data,
                src_transform=dsm_src.transform,
                src_crs=dsm_src.crs,
                dst_transform=transform,
                dst_crs=dst_crs,
                resampling=Resampling.nearest
            )

            # Get the bounds of the reprojected raster
            bounds = rasterio.transform.array_bounds(height, width, transform)
            st.session_state.dsm_bounds = [bounds[0], bounds[2], bounds[1], bounds[3]]

            # Normalize the elevation data for better visualization
            st.session_state.dsm_data = np.nan_to_num(st.session_state.dsm_data)
            st.session_state.dsm_data = (st.session_state.dsm_data - np.min(st.session_state.dsm_data)) / (np.max(st.session_state.dsm_data) - np.min(st.session_state.dsm_data)) * 255
            st.session_state.dsm_data = st.session_state.dsm_data.astype(np.uint8)
        with rasterio.open(st.session_state.uploaded_lcm) as lcm_src:
            lcm_data = lcm_src.read(1)
            
def input_models_page():
    st.header(translate("input_models"))
    st.subheader(translate("upload_models"))

    if 'uploaded_dsm' not in st.session_state:
        st.session_state.uploaded_dsm = None
    if 'uploaded_lcm' not in st.session_state:
        st.session_state.uploaded_lcm = None

    uploaded_dsm = st.file_uploader(translate("dsm"), type=["tif", "csv", "txt"])
    uploaded_lcm = st.file_uploader(translate("lcm"), type=["tif", "csv", "txt"])

    if uploaded_dsm:
        st.session_state.uploaded_dsm = uploaded_dsm
    else:
        dsm_path = 'data/Goteborg_SWEREF99_1200/DSM_KRbig.tif'
        st.session_state.uploaded_dsm = load_default_file(dsm_path)

    if uploaded_lcm:
        st.session_state.uploaded_lcm = uploaded_lcm
    else:
        st.session_state.uploaded_lcm = load_default_file('data/example_lcm.tif')

    if st.session_state.uploaded_dsm and st.session_state.uploaded_lcm:
        st.success(translate("success_upload"))

    st.session_state.dsm_width = st.slider(translate("ask_scale"), 30, 300, 90, step=3)

    load_input_models()

def visualize_models_page():
    st.header(translate("visualize_models"))
    st.subheader(translate("model_visualization"))

    if 'uploaded_dsm' in st.session_state and 'uploaded_lcm' in st.session_state:

        # Calculate the center of the raster for map centering
        rasLon = (st.session_state.dsm_bounds[1] + st.session_state.dsm_bounds[0]) / 2
        rasLat = (st.session_state.dsm_bounds[3] + st.session_state.dsm_bounds[2]) / 2
        mapCenter = [rasLat, rasLon]

        # Create map
        m = folium.Map(location=mapCenter, zoom_start=16)

        # Add DSM overlay
        folium.raster_layers.ImageOverlay(
            image=st.session_state.dsm_data,
            bounds=[[st.session_state.dsm_bounds[2], st.session_state.dsm_bounds[0]], [st.session_state.dsm_bounds[3], st.session_state.dsm_bounds[1]]],
            colormap=lambda x: (x, x, x, 255),  # Grayscale colormap
            opacity=0.8,
            interactive=True,
            cross_origin=False
        ).add_to(m)

        # Create grid
        num_cells = int(st.session_state.dsm_width/3) # We assume dsm_width is x * 3m. So we can divide by 3
        grid_cells = []
        coords_y = np.linspace(st.session_state.dsm_bounds[0], st.session_state.dsm_bounds[1], num_cells+1)
        coords_x = np.linspace(st.session_state.dsm_bounds[2], st.session_state.dsm_bounds[3], num_cells+1)
        for i in range(len(coords_x)-1):
            for j in range(len(coords_y)-1):
                cell = folium.Rectangle(
                    bounds=[[coords_x[i],coords_y[j]],[coords_x[i+1],coords_y[j+1]]],
                    fill=False,
                    color='blue',
                    weight=1
                )
                grid_cells.append(cell)
                cell.add_to(m)

        # Add draw control
        draw = Draw(
            draw_options={
                'circle': False,
                'circlemarker': False,
                'marker': False,
            },
            edit_options={'edit': False}
        )
        draw.add_to(m)

        # Display the map
        output = st_folium(m, width=700, height=500)

        # Process drawn shapes
        if output['last_active_drawing']:
            drawn_shape = output['last_active_drawing']
            if drawn_shape['geometry']['type'] == 'Polygon':
                drawn_polygon = Polygon(drawn_shape['geometry']['coordinates'][0])
                
                # Determine which cells are selected
                selected_cells = []
                for i, cell in enumerate(grid_cells):
                    cell_bounds = cell.get_bounds()
                    cell_polygon = box(cell_bounds[0][1], cell_bounds[0][0], cell_bounds[1][1], cell_bounds[1][0])
                    if drawn_polygon.intersects(cell_polygon):
                        selected_cells.append(i)

                # Save selected cells to session state
                st.session_state.selected_cells = selected_cells
                
                # Color selected cells
                for i in selected_cells:
                    folium.Rectangle(
                        bounds=grid_cells[i].get_bounds(),
                        fill=True,
                        fillColor='green',
                        fillOpacity=0.4,
                        color='green',
                        weight=2
                    ).add_to(m)

                # Re-display the map with colored cells
                st_folium(m, width=700, height=500)
                
                st.success(f"Selected {len(selected_cells)} cells. These will be used in the optimization.")

    # Display selected cells (if any)
    if 'selected_cells' in st.session_state:
        st.write(f"Number of selected cells: {len(st.session_state.selected_cells)}")
        if st.checkbox("Show selected cell indices"):
            st.write(st.session_state.selected_cells)
    


def optimization_criteria_page():
    st.header(translate("optimization_criteria"))
    st.subheader(translate("optimization_criteria_selection"))
    
    criteria = st.multiselect(translate("optimization_criteria_multiselect"), 
                              [translate("porosity"), 
                               translate("volume_airflow"), 
                               translate("area_facade"), 
                               translate("other")])
    
    solution_features = st.multiselect(translate("solution_features_multiselect"), 
                                       [translate("number_buildings"), 
                                        translate("constructed_area"), 
                                        translate("total_area_building"), 
                                        translate("other")])
    
    mutation_rate = st.slider(translate("mutation_rate"), min_value=0.0, max_value=1.0, value=0.1)
    
    if st.button(translate("run_optimization")):
        st.text(translate("running_optimization"))
        # Placeholder for the optimization function
        st.success(translate("optimization_completed"))

def results_page():
    st.header(translate("results"))
    st.subheader(translate("optimization_results"))

    # Placeholder for displaying results
    st.text("Display optimization results here (coming soon)...")
    st.text(translate("select_bins"))

    selected_bins = st.multiselect("Select bins/solutions", options=["Solution 1", "Solution 2", "Solution 3"])
    
    if selected_bins:
        st.text(f"{translate('running_analysis')} {', '.join(selected_bins)}...")
        # Placeholder for the analysis function
        st.success(translate("analysis_completed"))

def deduced_rules_page():
    st.header(translate("deduced_rules"))
    st.subheader(translate("deduced_rules_consequences"))

    # Placeholder for displaying deduced rules and consequences
    st.text("Displaying deduced rules and consequences here (coming soon)...")
    st.text(translate("expected_heat_hotspots"))

if __name__ == "__main__":
    main()
