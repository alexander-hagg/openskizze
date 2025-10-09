#!/usr/bin/env python3
"""
Analyze building categories in WFS ALKIS data to identify what to filter out.
"""
import requests
import geopandas as gpd
import io
import pandas as pd

# Bonn test area (corrected EPSG:25832 coordinates)
bbox_str = "365204,5621522,365938,5622652,EPSG:25832"

url = "https://www.wfs.nrw.de/geobasis/wfs_nw_alkis_vereinfacht"
params = {
    'service': 'WFS',
    'version': '1.1.0',
    'request': 'GetFeature',
    'typeName': 'ave:GebaeudeBauwerk',
    'outputFormat': 'text/xml; subtype=gml/3.2.1',
    'srsName': 'EPSG:25832',
    'BBOX': bbox_str,
    'maxFeatures': 5000
}

print("Fetching WFS ALKIS building data...")
response = requests.get(url, params=params, timeout=60)
gml_content = io.BytesIO(response.content)
gdf = gpd.read_file(gml_content)

# Filter to polygons only
gdf = gdf[gdf.geometry.type.isin(['Polygon', 'MultiPolygon'])].copy()

print(f"\nTotal buildings: {len(gdf)}")
print(f"\nAvailable columns:")
for col in gdf.columns:
    if col != 'geometry':
        print(f"  - {col}")

# ALKIS building function code reference
alkis_function_codes = {
    '31001_1000': 'Wohngebäude (Residential building)',
    '31001_1010': 'Wohnhaus (Residential house)',
    '31001_1020': 'Wohnheim (Dormitory)',
    '31001_1100': 'Gemischt genutztes Gebäude (Mixed-use building)',
    '31001_1110': 'Gemischt genutztes Gebäude mit Wohnen (Mixed-use with residential)',
    '31001_1120': 'Gemischt genutztes Gebäude ohne Wohnen (Mixed-use without residential)',
    '31001_1210': 'Haus für freie Berufe (Professional services building)',
    '31001_1220': 'Gebäude für Wirtschaft oder Gewerbe (Commercial/industrial building)',
    '31001_1221': 'Bürogebäude (Office building)',
    '31001_1222': 'Kreditinstitut (Bank)',
    '31001_1223': 'Versicherung (Insurance)',
    '31001_1230': 'Handelsgebäude (Trade building)',
    '31001_1231': 'Einkaufszentrum (Shopping center)',
    '31001_1240': 'Gebäude für Beherbergung (Hotel/accommodation)',
    '31001_1250': 'Gebäude für Bewirtung (Restaurant/catering)',
    '31001_1260': 'Garage (Garage)',
    '31001_1261': 'Parkhaus (Parking structure)',
    '31001_1262': 'Fahrzeughalle (Vehicle hall)',
    '31001_1263': 'Tiefgarage (Underground parking)',
    '31001_1270': 'Tankstelle (Gas station)',
    '31001_1280': 'Gebäude für Industrie und Produktion (Industrial building)',
    '31001_1290': 'Sonstige Produktion (Other production)',
    '31001_1310': 'Gebäude für öffentliche Zwecke (Public building)',
    '31001_1311': 'Rathaus (Town hall)',
    '31001_1312': 'Post (Post office)',
    '31001_1313': 'Gericht (Court)',
    '31001_1314': 'Finanzamt (Tax office)',
    '31001_2000': 'Gebäude für Bildung und Forschung (Education/research)',
    '31001_2010': 'Schule (School)',
    '31001_2020': 'Hochschule (University)',
    '31001_2030': 'Forschungseinrichtung (Research facility)',
    '31001_2040': 'Gebäude für kulturelle Zwecke (Cultural building)',
    '31001_2050': 'Gebäude für religiöse Zwecke (Religious building)',
    '31001_2051': 'Kirche (Church)',
    '31001_2060': 'Gebäude für Gesundheitswesen (Healthcare building)',
    '31001_2061': 'Krankenhaus (Hospital)',
    '31001_2062': 'Pflegeeinrichtung (Nursing facility)',
    '31001_2070': 'Gebäude für soziale Zwecke (Social services building)',
    '31001_2080': 'Gebäude für Sicherheit und Ordnung (Public safety building)',
    '31001_2081': 'Polizei (Police)',
    '31001_2082': 'Feuerwehr (Fire station)',
    '31001_2090': 'Justizvollzugsanstalt (Prison)',
    '31001_3000': 'Gebäude für Erholung (Recreation building)',
    '31001_3010': 'Gebäude für Sportzwecke (Sports facility)',
    '31001_3020': 'Gebäude für Freizeitzwecke (Leisure facility)',
    '31001_9999': 'Sonstiges (Other)',
}

rellage_codes = {
    '1200': 'Unter der Erdoberfläche (Below ground)',
    '1400': 'Aufgeständert (Elevated/on stilts)',
    '1000': 'Auf der Erdoberfläche (On ground)',
}

# Check funktion column
if 'funktion' in gdf.columns:
    print(f"\n{'='*80}")
    print("BUILDING FUNCTION CODES (funktion):")
    print(f"{'='*80}")
    funktion_counts = gdf['funktion'].value_counts()
    
    for code, count in funktion_counts.items():
        code_str = str(code) if pd.notna(code) else 'None/Unknown'
        desc = alkis_function_codes.get(code_str, 'UNKNOWN CODE')
        print(f"{code_str:20s} | {count:5d} buildings | {desc}")
    
    print(f"\nTotal unique function codes: {len(funktion_counts)}")

# Check rellage (relative position) column
if 'rellage' in gdf.columns:
    print(f"\n{'='*80}")
    print("RELATIVE POSITION (rellage - above/below ground):")
    print(f"{'='*80}")
    rellage_counts = gdf['rellage'].value_counts()
    
    for code, count in rellage_counts.items():
        code_str = str(code) if pd.notna(code) else 'None/Unknown'
        desc = rellage_codes.get(code_str, 'UNKNOWN CODE')
        print(f"{code_str:20s} | {count:5d} buildings | {desc}")

# Check gebnutzbez column
if 'gebnutzbez' in gdf.columns:
    print(f"\n{'='*80}")
    print("BUILDING USE DESCRIPTION (gebnutzbez) - Top 20:")
    print(f"{'='*80}")
    gebnutzbez_counts = gdf['gebnutzbez'].value_counts()
    for use, count in gebnutzbez_counts.head(20).items():
        use_str = str(use) if pd.notna(use) else 'None/Unknown'
        print(f"{use_str:50s} | {count:5d} buildings")

# Identify buildings to filter out
print(f"\n{'='*80}")
print("BUILDINGS TO FILTER OUT (not impacting cold airflow):")
print(f"{'='*80}")

filter_out_underground = gdf[gdf['rellage'] == '1200'] if 'rellage' in gdf.columns else gpd.GeoDataFrame()
filter_out_parking = gdf[gdf['funktion'].isin(['31001_1260', '31001_1261', '31001_1263'])] if 'funktion' in gdf.columns else gpd.GeoDataFrame()

print(f"Underground buildings (rellage=1200): {len(filter_out_underground)}")
print(f"Parking structures (funktion=1260/1261/1263): {len(filter_out_parking)}")

# Count total to filter
if 'rellage' in gdf.columns and 'funktion' in gdf.columns:
    to_filter = gdf[
        (gdf['rellage'] == '1200') | 
        (gdf['funktion'].isin(['31001_1260', '31001_1261', '31001_1263']))
    ]
    print(f"\nTotal buildings to filter out: {len(to_filter)} ({len(to_filter)/len(gdf)*100:.1f}%)")
    print(f"Buildings remaining: {len(gdf) - len(to_filter)}")

print(f"\n{'='*80}")
print("SAMPLE RECORDS (first 15):")
print(f"{'='*80}")
cols_to_show = ['funktion', 'rellage', 'gebnutzbez', 'name']
cols_available = [c for c in cols_to_show if c in gdf.columns]
print(gdf[cols_available].head(15).to_string())

print("\n" + "="*80)
print("ANALYSIS COMPLETE")
print("="*80)
