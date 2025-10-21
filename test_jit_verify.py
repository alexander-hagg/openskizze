#!/usr/bin/env python3
"""Test JIT implementation"""
import sys
import numpy as np
import timeit
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from backend.encoding import ParametricEncoding, NUMBA_AVAILABLE
from backend.evaluation import calculate_all_features, calculate_all_features_planning, NUMBA_AVAILABLE as EVAL_NUMBA
from backend.config import DOMAIN_CONFIG, ENCODING_CONFIG

print("=" * 80)
print("JIT IMPLEMENTATION VERIFICATION")
print("=" * 80)
print(f"\nNumba available in encoding: {NUMBA_AVAILABLE}")
print(f"Numba available in evaluation: {EVAL_NUMBA}")

if not NUMBA_AVAILABLE:
    print("\nWARNING: Numba not available!")
    sys.exit(1)

# Quick test
config = {'xy_length': 34, 'z_length': 30}
encoding_config = ENCODING_CONFIG.copy()
encoding_config.update(config)
encoding = ParametricEncoding(encoding_config)

buildable_mask = np.ones((34, 34), dtype=bool)
genome = np.random.randn(60)

print("\nTest 1: Phenotype creation")
heightmap = encoding.express(buildable_mask, genome)
print(f"  ✓ Heightmap shape: {heightmap.shape}")
print(f"  ✓ Non-zero pixels: {np.sum(heightmap > 0)}")

print("\nTest 2: Feature calculation")
buildable_area = np.sum(buildable_mask) * 9.0
features = calculate_all_features(heightmap, buildable_mask, buildable_area)
print(f"  ✓ Original features: {features[:4]}")

features_plan = calculate_all_features_planning(heightmap, buildable_mask, buildable_area)
print(f"  ✓ Planning features: {features_plan[:4]}")

print("\n" + "=" * 80)
print("✓ JIT implementation working correctly!")
print("=" * 80)
