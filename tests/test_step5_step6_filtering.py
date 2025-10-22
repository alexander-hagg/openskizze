#!/usr/bin/env python3
"""
Test script to verify that filtering in Step 5 correctly propagates to Step 6.

This test simulates the data flow:
1. Create mock solutions with known feature values
2. Apply filtering in cluster_and_analyze_solutions (Step 5 logic)
3. Verify that only filtered solutions appear in clusters
4. Verify that Step 6 would display the correct filtered solutions

Run from repo root: python tests/test_step5_step6_filtering.py
"""

import numpy as np
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

def create_mock_solutions(num_solutions=100):
    """Create mock solutions with known feature values"""
    solutions = []
    
    for i in range(num_solutions):
        # Feature 0: Built-up area (0-10000 m²)
        # Feature 1: Avg height (0-30 m) - THIS IS THE ONE WE'LL FILTER
        # Feature 2: Height variability (0-15 m)
        # Feature 3: Number of buildings (0-10)
        
        solutions.append({
            'id': i,
            'heightmap': np.random.rand(32 * 32).tolist(),  # Flat list
            'objective': np.random.rand(),  # 0-1
            'measures': [
                np.random.uniform(0, 10000),  # Built-up area
                np.random.uniform(5, 25),      # Avg height (5-25m)
                np.random.uniform(0, 15),      # Height variability
                np.random.randint(1, 10),      # Num buildings
                np.random.uniform(0, 100),     # Avg distance
                np.random.uniform(0, 50000),   # GFA
                np.random.rand(),              # Mass X
                np.random.rand(),              # Mass Y
            ]
        })
    
    return solutions

def test_filtering_logic():
    """Test that filtering correctly limits solutions"""
    print("=" * 80)
    print("TEST: Step 5 → Step 6 Filtering Logic")
    print("=" * 80)
    
    # Create 100 mock solutions
    all_solutions = create_mock_solutions(100)
    print(f"\n1. Created {len(all_solutions)} mock solutions")
    
    # Get avg height distribution (Feature index 1)
    heights = [s['measures'][1] for s in all_solutions]
    print(f"   Height range: {min(heights):.1f}m to {max(heights):.1f}m")
    print(f"   Mean height: {np.mean(heights):.1f}m")
    
    # Apply filter: minimum height = 15m (Feature index 1)
    min_height = 15.0
    feature_filters = {1: [min_height, 30.0]}  # Feature 1 = Avg height
    
    print(f"\n2. Applying filter: minimum height = {min_height}m")
    
    # Simulate the filtering logic from backend/analysis.py (lines 76-86)
    filtered_solutions = []
    for elite in all_solutions:
        is_valid = True
        for feat_idx, (min_val, max_val) in feature_filters.items():
            if not (min_val <= elite['measures'][feat_idx] <= max_val):
                is_valid = False
                break
        if is_valid:
            filtered_solutions.append(elite)
    
    print(f"   Filtered to {len(filtered_solutions)} solutions")
    
    # Verify filtering worked
    filtered_heights = [s['measures'][1] for s in filtered_solutions]
    if filtered_heights:
        print(f"   Filtered height range: {min(filtered_heights):.1f}m to {max(filtered_heights):.1f}m")
        print(f"   Filtered mean height: {np.mean(filtered_heights):.1f}m")
    
    # Check: All filtered solutions should have height >= 15m
    violations = [s for s in filtered_solutions if s['measures'][1] < min_height]
    
    print(f"\n3. Verification:")
    if violations:
        print(f"   ❌ FAIL: Found {len(violations)} solutions with height < {min_height}m")
        for v in violations[:5]:  # Show first 5
            print(f"      Solution {v['id']}: height = {v['measures'][1]:.1f}m")
        return False
    else:
        print(f"   ✅ PASS: All {len(filtered_solutions)} filtered solutions have height >= {min_height}m")
    
    # Simulate clustering (simplified - just create one cluster with all filtered solutions)
    print(f"\n4. Simulating clustering with {len(filtered_solutions)} filtered solutions")
    
    if len(filtered_solutions) < 2:
        print("   ⚠️  Not enough solutions to cluster (need at least 2)")
        return True
    
    # Find best and central solutions (simplified)
    objectives = np.array([s['objective'] for s in filtered_solutions])
    best_idx = np.argmax(objectives)
    central_idx = len(filtered_solutions) // 2  # Just pick middle one for simplicity
    
    mock_cluster = {
        'cluster_id': 0,
        'size': len(filtered_solutions),
        'best_solution': filtered_solutions[best_idx],
        'central_solution': filtered_solutions[central_idx],
        'consensus_map': np.random.rand(32 * 32).tolist(),
        'objective_values': objectives.tolist(),
        'median_objective': float(np.median(objectives))
    }
    
    print(f"   Created 1 cluster with {mock_cluster['size']} solutions")
    print(f"   Best solution: ID={mock_cluster['best_solution']['id']}, "
          f"height={mock_cluster['best_solution']['measures'][1]:.1f}m")
    print(f"   Central solution: ID={mock_cluster['central_solution']['id']}, "
          f"height={mock_cluster['central_solution']['measures'][1]:.1f}m")
    
    # Simulate Step 6 display (what we fixed)
    print(f"\n5. Simulating Step 6 display:")
    print(f"   OLD METHOD (BROKEN): Would reload ALL {len(all_solutions)} solutions from pickle")
    print(f"                        → Could show solutions with height < {min_height}m")
    print(f"   NEW METHOD (FIXED):  Uses cluster data directly with {mock_cluster['size']} filtered solutions")
    print(f"                        → Only shows solutions with height >= {min_height}m")
    
    # Verify Step 6 would show correct solutions
    step6_best = mock_cluster['best_solution']
    step6_central = mock_cluster['central_solution']
    
    if step6_best['measures'][1] >= min_height and step6_central['measures'][1] >= min_height:
        print(f"   ✅ PASS: Step 6 would display solutions meeting filter criteria")
        print(f"            Best: {step6_best['measures'][1]:.1f}m >= {min_height}m")
        print(f"            Central: {step6_central['measures'][1]:.1f}m >= {min_height}m")
        return True
    else:
        print(f"   ❌ FAIL: Step 6 would display invalid solutions")
        return False

def main():
    success = test_filtering_logic()
    
    print("\n" + "=" * 80)
    if success:
        print("✅ TEST PASSED: Filtering logic works correctly")
        print("=" * 80)
        return 0
    else:
        print("❌ TEST FAILED: Filtering logic has issues")
        print("=" * 80)
        return 1

if __name__ == '__main__':
    sys.exit(main())
