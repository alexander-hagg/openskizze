"""
Analyze NRW parcel size distribution to inform KLAM_21 training data generation.

This script:
1. Samples parcels from NRW ALKIS WFS across different cities
2. Calculates parcel dimensions (width, height, area)
3. Generates statistics and visualizations
4. Recommends optimal size grid for KLAM_21 training

Run from repo root: python helper/analyze_parcel_sizes.py
"""

import sys
import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
from shapely.geometry import box
from scipy.stats import gaussian_kde

# Add backend to path
sys.path.insert(0, '/home/alex/Documents/_cloud/Funded_Projects/OpenSKIZZE/code/openskizze')
from backend.data_io import fetch_flurstuecke_data

def get_parcel_dimensions(gdf):
    """Calculate width, height, area for each parcel."""
    dimensions = []
    
    for idx, row in gdf.iterrows():
        geom = row.geometry
        bounds = geom.bounds  # (minx, miny, maxx, maxy)
        
        width = bounds[2] - bounds[0]  # maxx - minx
        height = bounds[3] - bounds[1]  # maxy - miny
        area = geom.area
        
        # Ensure width >= height (standardize orientation)
        w, h = max(width, height), min(width, height)
        
        dimensions.append({
            'width_m': w,
            'height_m': h,
            'area_m2': area,
            'aspect_ratio': w / h if h > 0 else np.nan,
            'perimeter_m': geom.length
        })
    
    return pd.DataFrame(dimensions)

def sample_nrw_parcels(num_samples=1000):
    """Sample parcels from different NRW cities."""
    
    # Representative cities across NRW (Bonn, Köln, Düsseldorf, Münster, Bielefeld)
    sample_locations = [
        {'name': 'Bonn', 'lat': 50.7374, 'lon': 7.0982},
        {'name': 'Köln', 'lat': 50.9375, 'lon': 6.9603},
        {'name': 'Düsseldorf', 'lat': 51.2277, 'lon': 6.7735},
        {'name': 'Münster', 'lat': 51.9607, 'lon': 7.6261},
        {'name': 'Bielefeld', 'lat': 52.0302, 'lon': 8.5325},
    ]
    
    all_parcels = []
    samples_per_location = num_samples // len(sample_locations)
    
    for loc in sample_locations:
        print(f"Fetching parcels from {loc['name']}...")
        
        # Create 500m radius bounding box around city center
        radius_deg = 0.005  # ~500m
        bbox = box(
            loc['lon'] - radius_deg,
            loc['lat'] - radius_deg,
            loc['lon'] + radius_deg,
            loc['lat'] + radius_deg
        )
        
        try:
            # fetch_flurstuecke_data expects bbox as tuple: (minx, miny, maxx, maxy)
            bbox_tuple = (
                loc['lon'] - radius_deg,
                loc['lat'] - radius_deg,
                loc['lon'] + radius_deg,
                loc['lat'] + radius_deg
            )
            parcels_geojson = fetch_flurstuecke_data(bbox_tuple)
            
            if parcels_geojson is not None and parcels_geojson.get('features'):
                # Convert GeoJSON dict to GeoDataFrame
                parcels_gdf = gpd.GeoDataFrame.from_features(parcels_geojson['features'], crs='EPSG:4326')
                
                # Convert to EPSG:25832 for metric dimensions
                parcels_gdf = parcels_gdf.to_crs('EPSG:25832')
                
                # Sample random parcels
                n_sample = min(samples_per_location, len(parcels_gdf))
                sampled = parcels_gdf.sample(n=n_sample)
                
                # Get dimensions
                dims = get_parcel_dimensions(sampled)
                dims['city'] = loc['name']
                
                all_parcels.append(dims)
                print(f"  ✓ Sampled {n_sample} parcels")
            else:
                print(f"  ✗ No parcels found")
                
        except Exception as e:
            print(f"  ✗ Error: {e}")
            continue
    
    if len(all_parcels) == 0:
        print("WARNING: No parcels fetched. Using synthetic data for demonstration.")
        return generate_synthetic_parcel_data(num_samples)
    
    return pd.concat(all_parcels, ignore_index=True)

def generate_synthetic_parcel_data(num_samples=1000):
    """Fallback: Generate synthetic parcel data based on typical NRW distributions."""
    np.random.seed(42)
    
    # Log-normal distribution for parcel dimensions (typical for urban plots)
    # Mean: 40m, Std: 20m, Range: 20-150m
    widths = np.random.lognormal(mean=3.5, sigma=0.5, size=num_samples)
    widths = np.clip(widths * 10, 20, 150)
    
    heights = np.random.lognormal(mean=3.3, sigma=0.5, size=num_samples)
    heights = np.clip(heights * 10, 20, 150)
    
    # Ensure width >= height
    widths, heights = np.maximum(widths, heights), np.minimum(widths, heights)
    
    return pd.DataFrame({
        'width_m': widths,
        'height_m': heights,
        'area_m2': widths * heights,
        'aspect_ratio': widths / heights,
        'city': 'synthetic'
    })

def recommend_training_grid(df, num_sizes=10):
    """Recommend optimal size grid for KLAM_21 training."""
    
    # Filter extreme outliers (keep 95th percentile)
    df_filtered = df[
        (df['width_m'] >= df['width_m'].quantile(0.05)) &
        (df['width_m'] <= df['width_m'].quantile(0.95)) &
        (df['height_m'] >= df['height_m'].quantile(0.05)) &
        (df['height_m'] <= df['height_m'].quantile(0.95))
    ]
    
    # Determine size range
    min_width = df_filtered['width_m'].min()
    max_width = df_filtered['width_m'].max()
    min_height = df_filtered['height_m'].min()
    max_height = df_filtered['height_m'].max()
    
    print("\n" + "="*60)
    print("PARCEL SIZE STATISTICS (5th-95th percentile)")
    print("="*60)
    print(f"Width:  {min_width:.1f}m - {max_width:.1f}m (median: {df_filtered['width_m'].median():.1f}m)")
    print(f"Height: {min_height:.1f}m - {max_height:.1f}m (median: {df_filtered['height_m'].median():.1f}m)")
    print(f"Area:   {df_filtered['area_m2'].min():.0f}m² - {df_filtered['area_m2'].max():.0f}m²")
    print(f"Aspect ratio: {df_filtered['aspect_ratio'].median():.2f} (median)")
    
    # Generate training grid
    # Strategy: Cover range with log-spaced sizes (more samples at smaller scales)
    square_sizes = np.geomspace(max(min_width, 25), min(max_width, 150), num_sizes)
    square_sizes = np.round(square_sizes / 5) * 5  # Round to nearest 5m
    
    print("\n" + "="*60)
    print("RECOMMENDED TRAINING GRID (Square Parcels)")
    print("="*60)
    for i, size in enumerate(square_sizes, 1):
        count_in_range = len(df_filtered[
            (df_filtered['width_m'] >= size - 10) & 
            (df_filtered['width_m'] <= size + 10)
        ])
        coverage = count_in_range / len(df_filtered) * 100
        print(f"{i:2d}. {size:5.0f}m × {size:5.0f}m  ({size**2:7.0f}m²)  [{coverage:4.1f}% of parcels nearby]")
    
    # Generate rectangular variants
    print("\n" + "="*60)
    print("ADDITIONAL RECTANGULAR PARCELS (Top 5 by coverage)")
    print("="*60)
    
    # Common aspect ratios: 1.5:1, 2:1
    aspect_ratios = [1.5, 2.0]
    rect_variants = []
    
    for size in square_sizes[::2]:  # Every other square size
        for ar in aspect_ratios:
            w = size * np.sqrt(ar)
            h = size / np.sqrt(ar)
            w, h = round(w / 5) * 5, round(h / 5) * 5
            
            count_in_range = len(df_filtered[
                (df_filtered['width_m'] >= w - 10) & 
                (df_filtered['width_m'] <= w + 10) &
                (df_filtered['height_m'] >= h - 10) & 
                (df_filtered['height_m'] <= h + 10)
            ])
            coverage = count_in_range / len(df_filtered) * 100
            
            rect_variants.append({
                'width': w, 'height': h, 
                'area': w*h, 'coverage': coverage
            })
    
    # Sort by coverage and take top 5
    rect_variants = sorted(rect_variants, key=lambda x: x['coverage'], reverse=True)[:5]
    for i, rect in enumerate(rect_variants, 1):
        print(f"{i}. {rect['width']:5.0f}m × {rect['height']:5.0f}m  "
              f"({rect['area']:7.0f}m²)  [{rect['coverage']:4.1f}% coverage]")
    
    # Total training set recommendation
    total_sizes = len(square_sizes) + len(rect_variants)
    genomes_per_size = 5000
    total_klam_runs = total_sizes * genomes_per_size
    
    print("\n" + "="*60)
    print("TRAINING DATA RECOMMENDATION")
    print("="*60)
    print(f"Square parcels:      {len(square_sizes)}")
    print(f"Rectangular parcels: {len(rect_variants)}")
    print(f"Total size variants: {total_sizes}")
    print(f"Genomes per size:    {genomes_per_size:,}")
    print(f"Total KLAM runs:     {total_klam_runs:,}")
    print(f"\nWith 1280 parallel cores:")
    print(f"  Wall time (5 min/run):  {total_klam_runs / 1280 * 5 / 60:.1f} hours")
    print(f"  Wall time (10 min/run): {total_klam_runs / 1280 * 10 / 60:.1f} hours")
    
    return square_sizes, rect_variants

def visualize_distributions(df):
    """Create visualizations of parcel size distributions."""
    
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    
    # 1. Width vs Height scatter
    ax = axes[0, 0]
    ax.scatter(df['width_m'], df['height_m'], alpha=0.3, s=10)
    ax.set_xlabel('Width (m)')
    ax.set_ylabel('Height (m)')
    ax.set_title('Parcel Dimensions')
    ax.plot([0, 150], [0, 150], 'r--', alpha=0.5, label='Square (1:1)')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    # 2. Area distribution
    ax = axes[0, 1]
    ax.hist(df['area_m2'], bins=50, edgecolor='black', alpha=0.7)
    ax.set_xlabel('Area (m²)')
    ax.set_ylabel('Count')
    ax.set_title('Parcel Area Distribution')
    ax.axvline(df['area_m2'].median(), color='r', linestyle='--', 
               label=f'Median: {df["area_m2"].median():.0f}m²')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    # 3. Aspect ratio distribution
    ax = axes[1, 0]
    aspect_ratios = df['aspect_ratio'].dropna()
    aspect_ratios = aspect_ratios[aspect_ratios <= 5]  # Cap at 5:1 for viz
    ax.hist(aspect_ratios, bins=50, edgecolor='black', alpha=0.7)
    ax.set_xlabel('Aspect Ratio (width/height)')
    ax.set_ylabel('Count')
    ax.set_title('Aspect Ratio Distribution')
    ax.axvline(aspect_ratios.median(), color='r', linestyle='--',
               label=f'Median: {aspect_ratios.median():.2f}')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    # 4. 2D density plot
    ax = axes[1, 1]
    # Filter both width and height together to keep matching pairs
    mask = (df['width_m'] >= 20) & (df['width_m'] <= 150) & (df['height_m'] >= 20) & (df['height_m'] <= 150)
    width_filtered = df.loc[mask, 'width_m']
    height_filtered = df.loc[mask, 'height_m']
    
    if len(width_filtered) > 10:
        xy = np.vstack([width_filtered, height_filtered])
        z = gaussian_kde(xy)(xy)
        scatter = ax.scatter(width_filtered, height_filtered, c=z, s=10, cmap='viridis', alpha=0.5)
        plt.colorbar(scatter, ax=ax, label='Density')
    else:
        ax.scatter(df['width_m'], df['height_m'], alpha=0.3, s=10)
    
    ax.set_xlabel('Width (m)')
    ax.set_ylabel('Height (m)')
    ax.set_title('Parcel Size Density')
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig('helper/parcel_size_analysis.png', dpi=150)
    print("\n✓ Saved visualization to: helper/parcel_size_analysis.png")
    plt.show()

def main():
    print("OpenSKIZZE Parcel Size Analysis for KLAM_21 Training")
    print("="*60)
    
    # Sample parcels
    print("\n[1/3] Sampling NRW parcels...")
    df = sample_nrw_parcels(num_samples=1000)
    
    # Analyze and recommend
    print("\n[2/3] Analyzing distributions...")
    square_sizes, rect_variants = recommend_training_grid(df, num_sizes=10)
    
    # Visualize
    print("\n[3/3] Creating visualizations...")
    visualize_distributions(df)
    
    # Export recommendations
    output = {
        'square_sizes': square_sizes.tolist(),
        'rectangular_sizes': [(r['width'], r['height']) for r in rect_variants]
    }
    
    import json
    with open('helper/klam_training_sizes.json', 'w') as f:
        json.dump(output, f, indent=2)
    
    print("\n✓ Saved size recommendations to: helper/klam_training_sizes.json")
    print("\nDone!")

if __name__ == "__main__":
    main()
