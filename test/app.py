import streamlit as st
import pandas as pd
import numpy as np
import folium
import json
from streamlit_folium import st_folium
from shapely.geometry import Polygon
import rasterio
import geopandas as gpd

# Load translations
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
        st.session_state.current_page = 'Home'


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
    
uploaded_dem = None
uploaded_dsm = None
uploaded_lcm = None
selected_area = []

def load_default_file(filename):
    return open(filename, 'rb')

def input_models_page():
    st.header(translate("input_models"))
    st.subheader(translate("upload_models"))

    if 'uploaded_dem' not in st.session_state:
        st.session_state.uploaded_dem = None
    if 'uploaded_dsm' not in st.session_state:
        st.session_state.uploaded_dsm = None
    if 'uploaded_lcm' not in st.session_state:
        st.session_state.uploaded_lcm = None

    uploaded_dem = st.file_uploader(translate("dem"), type=["tif", "csv", "txt"])
    uploaded_dsm = st.file_uploader(translate("dsm"), type=["tif", "csv", "txt"])
    uploaded_lcm = st.file_uploader(translate("lcm"), type=["tif", "csv", "txt"])

    if uploaded_dem:
        st.session_state.uploaded_dem = uploaded_dem
    else:
        st.session_state.uploaded_dem = load_default_file('example_dem.tif')

    if uploaded_dsm:
        st.session_state.uploaded_dsm = uploaded_dsm
    else:
        st.session_state.uploaded_dsm = load_default_file('example_dsm.tif')

    if uploaded_lcm:
        st.session_state.uploaded_lcm = uploaded_lcm
    else:
        st.session_state.uploaded_lcm = load_default_file('example_lcm.tif')

    if st.session_state.uploaded_dem and st.session_state.uploaded_dsm and st.session_state.uploaded_lcm:
        st.success(translate("success_upload"))

def visualize_models_page():
    st.header(translate("visualize_models"))
    st.subheader(translate("model_visualization"))

    if 'uploaded_dem' in st.session_state and 'uploaded_dsm' in st.session_state and 'uploaded_lcm' in st.session_state:
        with rasterio.open(st.session_state.uploaded_dem) as dem_src:
            dem_data = dem_src.read(1)
            dem_bounds = dem_src.bounds
        with rasterio.open(st.session_state.uploaded_dsm) as dsm_src:
            dsm_data = dsm_src.read(1)
        with rasterio.open(st.session_state.uploaded_lcm) as lcm_src:
            lcm_data = lcm_src.read(1)

        # Create map
        m = folium.Map(location=[(dem_bounds.top + dem_bounds.bottom) / 2, (dem_bounds.left + dem_bounds.right) / 2], zoom_start=13)

        # Add DEM overlay
        folium.raster_layers.ImageOverlay(
            image=dem_data,
            bounds=[[dem_bounds.bottom, dem_bounds.left], [dem_bounds.top, dem_bounds.right]],
            colormap=lambda x: (1, 0, 0, x),  # Red for DEM
            opacity=0.6,
        ).add_to(m)

        # Add a simple grid overlay
        for i in range(0, dem_data.shape[0], 10):
            for j in range(0, dem_data.shape[1], 10):
                folium.Rectangle(
                    bounds=[
                        [dem_bounds.bottom + i * (dem_bounds.top - dem_bounds.bottom) / dem_data.shape[0],
                         dem_bounds.left + j * (dem_bounds.right - dem_bounds.left) / dem_data.shape[1]],
                        [dem_bounds.bottom + (i + 10) * (dem_bounds.top - dem_bounds.bottom) / dem_data.shape[0],
                         dem_bounds.left + (j + 10) * (dem_bounds.right - dem_bounds.left) / dem_data.shape[1]]
                    ],
                    fill=False,
                    color='blue'
                ).add_to(m)

        # Add the folium map to Streamlit
        output = st_folium(m, width=700, height=500)

        # Placeholder for selecting boundary using mouse clicks and drag
        st.subheader(translate("select_boundary"))
        st.text("Click and drag over the squares to select the planning area (feature coming soon)")

        # Assume user has selected some areas
        global selected_area
        selected_area = [Polygon([(dem_bounds.left, dem_bounds.bottom), (dem_bounds.left, dem_bounds.top), (dem_bounds.right, dem_bounds.top), (dem_bounds.right, dem_bounds.bottom)])]
        st.text(f"{translate('select_boundary')}: {selected_area}")


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
