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
    # 1. SVGP Normalization file
    # ========================================================================
    print("━" * 80)
    print("1️⃣  SVGP NORMALIZATION FILE")
    print("━" * 80)
    svgp_norm_file = SURROGATE_CONFIG['svgp_normalization_file']
    print(f"File: {svgp_norm_file}")
    print()
    print("Input: genome (60) + parcel width (1) + parcel height (1) = 62 features")
    print("Output: fitness scalar")
    print()
    print("Expected JSON structure:")
    print(json.dumps({
        "train_X_mean": [0.0] * 62,  # 60 genome + 2 parcel dims
        "train_X_std": [1.0] * 62,
        "train_y_mean": 0.5,
        "train_y_std": 0.2
    }, indent=2))
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
    print("Output: Ex/uq/vq flow fields (3 channels × 66×94)")
    print()
    print("Expected JSON structure (same for all sizes):")
    print(json.dumps({
        "input": {
            "terrain": {"mean": 0.0, "std": 1.0},
            "buildings": {"mean": 5.0, "std": 10.0},
            "landuse": {"mean": 3.5, "std": 2.0}
        },
        "output": {
            "Ex": {"mean": -50.0, "std": 30.0},
            "uq": {"mean": 0.0, "std": 100.0},
            "vq": {"mean": 0.0, "std": 100.0}
        }
    }, indent=2))
    print()
    print("Examples:")
    print("  • unet_81m_normalization.json  (for 81m parcels)")
    print("  • unet_99m_normalization.json  (for 99m parcels)")
    print("  • etc.")
    print()
    
    # ========================================================================
    # 3. SVGP Model
    # ========================================================================
    print("━" * 80)
    print("3️⃣  SVGP MODEL (WORKS FOR ALL PARCEL SIZES)")
    print("━" * 80)
    svgp_file = SURROGATE_CONFIG['svgp_model_name']
    print(f"File: {svgp_file}")
    print()
    print("✓ Single model works for ALL parcel sizes")
    print("✓ Takes genome (60) + parcel width (1) + parcel height (1) = 62 inputs")
    print("✓ Trained on square parcels, generalizes to any size via size features")
    print("✓ Outputs: fitness mean + uncertainty (for UCB exploration)")
    print()
    
    # ========================================================================
    # 4. U-Net Models
    # ========================================================================
    print("━" * 80)
    print("4️⃣  U-NET MODELS (ONE PER PARCEL SIZE)")
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
    print("✓ Outputs: Ex, uq, vq flow fields → fitness computed from cold air flux")
    print()
    
    # ========================================================================
    # 5. Current Status
    # ========================================================================
    print("━" * 80)
    print("5️⃣  CURRENT STATUS")
    print("━" * 80)
    
    if not models_dir.exists():
        print(f"❌ Directory does not exist: {models_dir}")
        print(f"   → Create: mkdir {models_dir}")
        return
    
    # Check SVGP normalization
    svgp_norm_path = models_dir / svgp_norm_file
    svgp_norm_exists = svgp_norm_path.exists()
    print(f"{'✅' if svgp_norm_exists else '❌'} {svgp_norm_file}: {'FOUND' if svgp_norm_exists else 'MISSING'}")
    
    # Check SVGP model
    svgp_path = models_dir / svgp_file
    svgp_exists = svgp_path.exists()
    print(f"{'✅' if svgp_exists else '❌'} {svgp_file}: {'FOUND' if svgp_exists else 'MISSING'}")
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
    # 6. Minimum Setup for Testing
    # ========================================================================
    print("━" * 80)
    print("6️⃣  MINIMUM SETUP FOR TESTING UI")
    print("━" * 80)
    print(f"To enable all 5 evaluation methods, create:")
    print(f"  1. {models_dir}/{svgp_norm_file}")
    print(f"  2. {models_dir}/{svgp_file}")
    print(f"  3. {models_dir}/unet_81m_normalization.json")
    print(f"  4. {models_dir}/unet_81m.pth")
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
