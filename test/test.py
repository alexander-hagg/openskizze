import streamlit as st
import folium
from streamlit_folium import st_folium
import rasterio

@st.cache_resource
def create_map():
    # Create a simple Folium map centered at a fixed location
    m = folium.Map(location=[45.0, -100.0], zoom_start=13)

    # Add a marker for testing
    folium.Marker(location=[45.0, -100.0], popup="Test Marker").add_to(m)
    return m

@st.cache_resource
def create_dem_overlay(dem_path):
    with rasterio.open(dem_path) as dem_src:
        dem_data = dem_src.read(1)
        dem_bounds = dem_src.bounds

    # Normalize the DEM data for visualization
    dem_data_normalized = (dem_data - dem_data.min()) / (dem_data.max() - dem_data.min())

    return dem_data_normalized, dem_bounds

def main():
    st.title("Urban Planning and Climate Impact AI App")

    st.sidebar.title("Navigation")
    page = st.sidebar.radio("Go to", ["Home", "Input Models", "Visualize Models"])

    if page == "Home":
        home_page()
    elif page == "Input Models":
        input_models_page()
    elif page == "Visualize Models":
        visualize_models_page()

def home_page():
    st.header("Welcome to the Urban Planning and Climate Impact AI App")
    st.subheader("How this app works:")
    st.write("""
    This app helps urban planners evaluate and optimize urban development projects with a focus on climate impact.
    """)

def load_default_file(filename):
    return open(filename, 'rb')

def input_models_page():
    st.header("Input Models")
    st.subheader("Upload your models")

    if 'uploaded_dem' not in st.session_state:
        st.session_state.uploaded_dem = None

    uploaded_dem = st.file_uploader("Digital Elevation Model (DEM)", type=["tif", "csv", "txt"])

    if uploaded_dem:
        st.session_state.uploaded_dem = uploaded_dem
    else:
        st.session_state.uploaded_dem = load_default_file('example_dem.tif')

    if st.session_state.uploaded_dem:
        st.success("Model uploaded successfully.")

def visualize_models_page():
    st.header("Visualize Models")
    st.subheader("Model Visualization")

    if 'uploaded_dem' in st.session_state:
        dem_data_normalized, dem_bounds = create_dem_overlay(st.session_state.uploaded_dem)

        # Create map
        m = folium.Map(location=[(dem_bounds.top + dem_bounds.bottom) / 2, (dem_bounds.left + dem_bounds.right) / 2], zoom_start=13)

        # Add DEM overlay
        folium.raster_layers.ImageOverlay(
            image=dem_data_normalized,
            bounds=[[dem_bounds.bottom, dem_bounds.left], [dem_bounds.top, dem_bounds.right]],
            colormap=lambda x: (1, 0, 0, x),  # Red for DEM
            opacity=0.6,
        ).add_to(m)

        # Add the Folium map to Streamlit
        st_folium(m, width=700, height=500)

if __name__ == "__main__":
    main()
