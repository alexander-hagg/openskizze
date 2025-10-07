#!/usr/bin/env python3
"""
Compare building fetch area before and after optimization.
"""

# Before (neighborhood_expansion = 1.0):
# - Fetches 3x the area (1x on each side)
# - For a 100m x 100m parcel → fetches 300m x 300m = 90,000 m²

# After (using environment_border_size = 1.2):
# - Fetches 1.2x the area (0.1x on each side)  
# - For a 100m x 100m parcel → fetches 120m x 120m = 14,400 m²

# Area reduction: 90,000 → 14,400 = 84% reduction!

import numpy as np

# Example parcel
parcel_size = 100  # meters

# OLD: neighborhood_expansion = 1.0
old_expansion = 1.0
old_fetch_size = parcel_size * (1 + 2 * old_expansion)
old_fetch_area = old_fetch_size ** 2

# NEW: using environment_border_size = 1.2
env_border_size = 1.2
new_expansion = (env_border_size - 1.0) / 2.0  # 0.1
new_fetch_size = parcel_size * env_border_size
new_fetch_area = new_fetch_size ** 2

print("=" * 80)
print("Building Fetch Area Optimization")
print("=" * 80)
print(f"\nExample parcel: {parcel_size}m x {parcel_size}m = {parcel_size**2:,} m²")

print(f"\nOLD (neighborhood_expansion = 1.0):")
print(f"  - Expansion: {old_expansion} on each side (100% extra)")
print(f"  - Fetch area: {old_fetch_size}m x {old_fetch_size}m = {old_fetch_area:,.0f} m²")
print(f"  - Ratio to parcel: {old_fetch_area / (parcel_size**2):.1f}x")

print(f"\nNEW (using environment_border_size = 1.2):")
print(f"  - Expansion: {new_expansion} on each side (10% extra)")
print(f"  - Fetch area: {new_fetch_size}m x {new_fetch_size}m = {new_fetch_area:,.0f} m²")
print(f"  - Ratio to parcel: {new_fetch_area / (parcel_size**2):.1f}x")

print(f"\nIMPROVEMENT:")
reduction = (old_fetch_area - new_fetch_area) / old_fetch_area * 100
print(f"  - Area reduction: {old_fetch_area:,.0f} → {new_fetch_area:,.0f} m²")
print(f"  - Reduction: {reduction:.1f}%")
print(f"  - Buildings fetched: ~{reduction:.0f}% fewer")

# Real-world example: Typical parcel in Bonn
realistic_parcel = 50  # 50m x 50m parcel
old_realistic = (realistic_parcel * (1 + 2 * 1.0)) ** 2
new_realistic = (realistic_parcel * 1.2) ** 2

print(f"\nRealistic example (50m x 50m parcel):")
print(f"  - OLD: {old_realistic:,.0f} m² ({old_realistic / 10000:.2f} hectares)")
print(f"  - NEW: {new_realistic:,.0f} m² ({new_realistic / 10000:.2f} hectares)")
print(f"  - Reduction: {(old_realistic - new_realistic):,.0f} m² ({(old_realistic - new_realistic) / old_realistic * 100:.1f}%)")

print("\n" + "=" * 80)
print("BENEFIT: Faster API calls, less data transfer, better performance!")
print("=" * 80)
