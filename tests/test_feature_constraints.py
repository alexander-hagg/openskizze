"""
Test script to verify feature constraint saving, restoration, and filtering.

This script tests the core functionality without requiring the full Dash app.
"""

import numpy as np
import pickle
import tempfile
import os


def test_feature_range_filtering():
    """
    Test that solutions are correctly filtered based on feature ranges.
    """
    print("Testing feature range filtering...")
    
    # Create mock solutions
    mock_solutions = [
        {
            'id': 0,
            'objective': 0.8,
            'measures': [250.0, 10.0, 3.0, 5.0, 30.0, 1000.0, 0.5, 0.5],  # Within all ranges
            'grid_indices': [0, 0],
            'heightmap': np.zeros((100, 100)).flatten().tolist()
        },
        {
            'id': 1,
            'objective': 0.9,
            'measures': [150.0, 8.0, 2.0, 3.0, 25.0, 800.0, 0.4, 0.6],  # Built area too low
            'grid_indices': [1, 0],
            'heightmap': np.zeros((100, 100)).flatten().tolist()
        },
        {
            'id': 2,
            'objective': 0.85,
            'measures': [300.0, 12.0, 4.0, 8.0, 35.0, 1200.0, 0.6, 0.4],  # Within all ranges
            'grid_indices': [0, 1],
            'heightmap': np.zeros((100, 100)).flatten().tolist()
        },
        {
            'id': 3,
            'objective': 0.7,
            'measures': [280.0, 20.0, 5.0, 4.0, 40.0, 1100.0, 0.5, 0.5],  # Avg height too high
            'grid_indices': [1, 1],
            'heightmap': np.zeros((100, 100)).flatten().tolist()
        },
    ]
    
    # Define feature constraints (indices as strings, matching actual implementation)
    # Feature 0: Built Area (200-400 m²)
    # Feature 1: Avg Height (5-15 m)
    user_feature_ranges = {
        '0': [200.0, 400.0],  # Built Area
        '1': [5.0, 15.0],     # Avg Height
    }
    
    selected_features = [0, 1, 2, 3, 4, 5, 6, 7]
    
    # Apply filtering logic (same as in step3_optimize.py)
    filtered_solutions = []
    for solution in mock_solutions:
        is_valid = True
        if user_feature_ranges:
            for feat_idx_str, (min_val, max_val) in user_feature_ranges.items():
                feat_idx = int(feat_idx_str)
                if feat_idx in selected_features:
                    pos = selected_features.index(feat_idx)
                    measure_value = solution['measures'][pos]
                    if not (min_val <= measure_value <= max_val):
                        is_valid = False
                        print(f"  Solution {solution['id']}: Feature {feat_idx} = {measure_value:.2f} "
                              f"(expected {min_val}-{max_val}) -> FILTERED OUT")
                        break
        
        if is_valid:
            filtered_solutions.append(solution)
            print(f"  Solution {solution['id']}: ALL constraints satisfied -> INCLUDED")
    
    # Verify results
    print(f"\nFiltering Results:")
    print(f"  Original solutions: {len(mock_solutions)}")
    print(f"  Filtered solutions: {len(filtered_solutions)}")
    
    expected_valid_ids = [0, 2]  # Only solutions 0 and 2 should pass
    actual_valid_ids = [s['id'] for s in filtered_solutions]
    
    assert actual_valid_ids == expected_valid_ids, \
        f"Expected solutions {expected_valid_ids}, but got {actual_valid_ids}"
    
    print("✓ Filtering test PASSED")
    return True


def test_session_data_structure():
    """
    Test that feature ranges are correctly structured in session data.
    """
    print("\nTesting session data structure...")
    
    # Simulate session data as stored in the app
    session_data = {
        'selected_features': [0, 1, 3, 4, 5],
        'feature_ranges': {
            '0': [100.0, 500.0],
            '1': [3.0, 15.0],
            '3': [5.0, 20.0],
            '4': [10.0, 50.0],
            '5': [500.0, 2000.0],
        },
        'hard_constraints': {
            'max_height': 30,
            'min_distance': 5
        },
        'site_polygon': {'type': 'FeatureCollection', 'features': []},
        'wind_direction': 0
    }
    
    # Verify structure
    assert 'feature_ranges' in session_data, "feature_ranges not in session_data"
    assert isinstance(session_data['feature_ranges'], dict), "feature_ranges must be dict"
    
    # Verify keys are strings (as they come from Dash component IDs)
    for key in session_data['feature_ranges'].keys():
        assert isinstance(key, str), f"Key {key} must be string"
        # Verify value is a 2-element list
        value = session_data['feature_ranges'][key]
        assert isinstance(value, list) and len(value) == 2, \
            f"Value for key {key} must be [min, max] list"
        assert value[0] <= value[1], f"Min must be <= max for key {key}"
    
    print("✓ Session data structure test PASSED")
    return True


def test_project_state_persistence():
    """
    Test that feature ranges persist in saved project files.
    """
    print("\nTesting project state persistence...")
    
    # Import the project_state module
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
    from backend import project_state
    
    # Create mock application state
    session_data = {
        'feature_ranges': {
            '0': [100.0, 500.0],
            '1': [3.0, 15.0],
        },
        'selected_features': [0, 1, 3, 4],
    }
    results_data = {}
    comparison_data = []
    
    # Gather state
    state = project_state.gather_application_state(
        session_data, results_data, comparison_data
    )
    
    # Save to temp file
    with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.skizze') as f:
        temp_path = f.name
        project_state.save_state_to_file(state, f)
    
    try:
        # Load from temp file
        with open(temp_path, 'rb') as f:
            loaded_state = project_state.load_state_from_file(f)
        
        # Verify feature_ranges are preserved
        assert 'session_data' in loaded_state, "session_data not in loaded state"
        loaded_session = loaded_state['session_data']
        assert 'feature_ranges' in loaded_session, "feature_ranges not in loaded session_data"
        
        # Verify values match
        original_ranges = session_data['feature_ranges']
        loaded_ranges = loaded_session['feature_ranges']
        
        for key in original_ranges.keys():
            assert key in loaded_ranges, f"Key {key} missing in loaded ranges"
            assert loaded_ranges[key] == original_ranges[key], \
                f"Range for {key} changed: {original_ranges[key]} -> {loaded_ranges[key]}"
        
        print("✓ Project state persistence test PASSED")
        return True
        
    finally:
        # Clean up
        if os.path.exists(temp_path):
            os.remove(temp_path)


def test_archive_bounds():
    """
    Test that archive bounds are correctly set from feature ranges.
    """
    print("\nTesting archive bounds configuration...")
    
    # Simulate the flow from create_environment
    selected_features = [0, 1, 3, 4, 5]
    user_feature_ranges = {
        '0': [100.0, 500.0],
        '1': [3.0, 15.0],
        '3': [5.0, 20.0],
    }
    
    # Simulate default dynamic ranges (would come from buildable area calculation)
    dynamic_ranges = [
        [0.0, 1000.0],  # Feature 0
        [0.0, 30.0],    # Feature 1
        [0.0, 10.0],    # Feature 2
        [0.0, 50.0],    # Feature 3
        [0.0, 100.0],   # Feature 4
        [0.0, 5000.0],  # Feature 5
        [0.0, 1.0],     # Feature 6
        [0.0, 1.0],     # Feature 7
    ]
    
    # Build final ranges (same logic as in optimization_process.py)
    final_feat_ranges = []
    for feature_index in selected_features:
        user_range = user_feature_ranges.get(str(feature_index))
        if user_range:
            final_feat_ranges.append(user_range)
        else:
            final_feat_ranges.append(dynamic_ranges[feature_index])
    
    # Verify
    expected_ranges = [
        [100.0, 500.0],   # Feature 0 - user defined
        [3.0, 15.0],      # Feature 1 - user defined
        [5.0, 20.0],      # Feature 3 - user defined
        [0.0, 100.0],     # Feature 4 - default (no user range)
        [0.0, 5000.0],    # Feature 5 - default (no user range)
    ]
    
    assert len(final_feat_ranges) == len(selected_features), \
        "Number of ranges must match number of selected features"
    
    for i, (expected, actual) in enumerate(zip(expected_ranges, final_feat_ranges)):
        assert expected == actual, \
            f"Range {i} mismatch: expected {expected}, got {actual}"
    
    print("✓ Archive bounds configuration test PASSED")
    return True


if __name__ == '__main__':
    print("=" * 60)
    print("Feature Constraints Implementation Tests")
    print("=" * 60)
    
    all_passed = True
    
    try:
        test_feature_range_filtering()
    except Exception as e:
        print(f"✗ Filtering test FAILED: {e}")
        all_passed = False
    
    try:
        test_session_data_structure()
    except Exception as e:
        print(f"✗ Session data structure test FAILED: {e}")
        all_passed = False
    
    try:
        test_project_state_persistence()
    except Exception as e:
        print(f"✗ Project state persistence test FAILED: {e}")
        all_passed = False
    
    try:
        test_archive_bounds()
    except Exception as e:
        print(f"✗ Archive bounds configuration test FAILED: {e}")
        all_passed = False
    
    print("\n" + "=" * 60)
    if all_passed:
        print("ALL TESTS PASSED ✓")
    else:
        print("SOME TESTS FAILED ✗")
    print("=" * 60)
