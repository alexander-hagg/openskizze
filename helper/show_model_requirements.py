#!/usr/bin/env python3
"""
Display required files and structure for surrogate models.
Run this to understand what files are needed in the models/ directory.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.config import SURROGATE_CONFIG
import json

def show_requirements():
    print('=' * 80)
    print('SURROGATE MODEL FILE REQUIREMENTS')
    print('=' * 80)
    print()
    
    models_dir = Path(SURROGATE_CONFIG['models_dir'])
    print(f"📁 Directory: {models_dir}/")
    print()
    
    # ========================================================================
    # 1. SVGP Model
    # ========================================================================
    print("━" * 80)
    print("1️⃣  SVGP MODEL")
    print("━" * 80)
    svgp_model = SURROGATE_CONFIG['svgp_model_name']
    print(f"File: {svgp_model}")
    print()
    print("Input: genome (60) + parcel width (1) + parcel height (1) = 62 features")
    print("Output: fitness scalar")
    print()
    print("Normalization stored IN checkpoint (lowercase keys):")
    print("  • train_x_mean: (62,) tensor - one per input dimension")
    print("  • train_x_std: (62,) tensor")
    print("  • train_y_mean: scalar - flux mean")
    print("  • train_y_std: scalar - flux std")
    print()
    print("✅ Single model works for ALL parcel sizes")
    print()
    
    # ========================================================================
    # 2. U-Net Normalization files (size-specific)
    # ========================================================================
    print("━" * 80)
    print("2️⃣  U-NET NORMALIZATION FILES (ONE PER PARCEL SIZE)")
    print("━" * 80)
    print("Format: unet_{size_in_meters}m_normalization.json")
    print()
    print("Input: terrain/buildings/landuse grids (3 channels × 66×94)")
    print("Output: Ex/Hx/uq/vq/uz/vz flow fields (6 channels × 66×94)")
    print()
    print("Expected JSON structure (scalar mean/std for each channel):")
    print(json.dumps({
        "terrain_mean": 0.0,
        "terrain_std": 1.0,
        "buildings_mean": 5.0,
        "buildings_std": 10.0,
        "landuse_mean": 3.5,
        "landuse_std": 2.0,
        "ex_mean": -50.0,
        "ex_std": 30.0,
        "uq_mean": 0.0,
        "uq_std": 100.0,
        "vq_mean": 0.0,
        "vq_std": 100.0,
        "uz_mean": 0.0,
        "uz_std": 50.0,
        "vz_mean": 0.0,
        "vz_std": 50.0,
        "hx_mean": 0.0,
        "hx_std": 20.0
    }, indent=2))
    print()
    print("Examples:")
    print("  • unet_81m_normalization.json  (for 81m parcels)")
    print("  • unet_99m_normalization.json  (for 99m parcels)")
    print("  • etc.")
    print()
    
    # ========================================================================
    # 3. U-Net Models
    # ========================================================================
    print("━" * 80)
    print("3️⃣  U-NET MODELS (ONE PER PARCEL SIZE)")
    print("━" * 80)
    print("Format: unet_{size_in_meters}m.pth")
    print()
    print("Available sizes:")
    sizes = SURROGATE_CONFIG['available_parcel_sizes_unet']
    for bins in sizes:
        meters = bins * 3
        print(f"  • unet_{meters}m.pth  (for {bins} bins × 3m = {meters}m parcels)")
    print()
    print("✓ Fixed CNN input dimensions → needs exact size match")
    print("✓ Takes 3-channel input: terrain, buildings, landuse grids (66×94)")
    print("✓ Outputs: 6 channels (Ex, Hx, uq, vq, uz, vz) flow fields")
    print("✓ Fitness computed from cold air flux: mean(Ex) × mean(sqrt(uq² + vq²))")
    print()
    
    # ========================================================================
    # 4. Current Status
    # ========================================================================
    print("━" * 80)
    print("4️⃣  CURRENT STATUS")
    print("━" * 80)
    
    if not models_dir.exists():
        print(f"❌ Directory does not exist: {models_dir}")
        print(f"   → Create: mkdir {models_dir}")
        return
    
    # Check SVGP model (normalization is inside checkpoint)
    svgp_file = SURROGATE_CONFIG['svgp_model_name']
    svgp_path = models_dir / svgp_file
    svgp_exists = svgp_path.exists()
    print(f"{'✅' if svgp_exists else '❌'} {svgp_file}: {'FOUND' if svgp_exists else 'MISSING'}")
    if svgp_exists:
        print("   (contains model + normalization in checkpoint)")
    print()
    
    # Check U-Net models and normalization files
    unet_files = list(models_dir.glob('unet_*.pth'))
    unet_norm_files = list(models_dir.glob('unet_*_normalization.json'))
    
    if unet_files:
        print(f"U-Net models: {len(unet_files)} found")
        for f in sorted(unet_files):
            size_str = f.stem.replace('unet_', '')  # e.g., '81m'
            norm_file = models_dir / f'unet_{size_str}_normalization.json'
            norm_exists = norm_file.exists()
            status = '✅' if norm_exists else '⚠️ (missing normalization)'
            print(f"  {status} {f.name}")
    else:
        print("❌ U-Net models: NONE found")
    
    if unet_norm_files:
        print()
        print(f"U-Net normalization files: {len(unet_norm_files)} found")
        for f in sorted(unet_norm_files):
            print(f"  ✅ {f.name}")
    else:
        print()
        print("❌ U-Net normalization files: NONE found")
    unet_files = list(models_dir.glob('unet_*.pth'))
    if unet_files:
        print(f"✅ U-Net models: {len(unet_files)} found")
        for f in sorted(unet_files):
            print(f"   • {f.name}")
    else:
        print("❌ U-Net models: NONE found")
    
    print()
    # ========================================================================
    # 5. Minimum Setup for Testing
    # ========================================================================
    print("━" * 80)
    print("5️⃣  MINIMUM SETUP FOR TESTING UI")
    print("━" * 80)
    svgp_file = SURROGATE_CONFIG['svgp_model_name']
    print(f"To enable all 5 evaluation methods, create:")
    print(f"  1. {models_dir}/{svgp_file} (contains model + normalization)")
    print(f"  2. {models_dir}/unet_81m.pth")
    print(f"  3. {models_dir}/unet_81m_normalization.json")
    print()
    print("This will enable:")
    print("  ✓ Simple Porosity (geometric, no models needed)")
    print("  ✓ Street Canyon (geometric, no models needed)")
    print("  ✓ SVGP (all parcel sizes)")
    print("  ✓ U-Net (81m parcels only)")
    print("  ✓ Hybrid (81m parcels only)")
    print()


if __name__ == '__main__':
    show_requirements()
