import pickle
import os
from datetime import datetime

PROJECT_FILE_EXTENSION = ".skizze"

def gather_application_state(session_data, results_data, comparison_data, filter_data=None):
    """
    Gathers all relevant application state into a single dictionary.
    Embeds the actual optimization results data instead of just file paths.
    
    Args:
        session_data: Dictionary containing user settings from step 1 & 2
            - site_polygon, wind_direction, building_data
            - selected_features, feature_set, feature_ranges
            - hard_constraints, qd_hyperparams, objective_function
        results_data: Dictionary containing optimization results from step 3
            - full_results_path, env_3d_path, archive_dims, labels, etc.
        comparison_data: List of cluster IDs selected for comparison in step 4/5
    
    Returns:
        Dictionary with all application state, ready to be pickled
    """
    # Deep copy to avoid modifying the original
    session_data_copy = session_data.copy() if session_data else {}
    results_data_copy = results_data.copy() if results_data else {}
    comparison_data_copy = comparison_data.copy() if comparison_data else []
    
    # If results_data contains paths to pickle files, load and embed the actual data
    if results_data_copy and 'full_results_path' in results_data_copy:
        full_results_path = results_data_copy['full_results_path']
        if os.path.exists(full_results_path):
            try:
                with open(full_results_path, 'rb') as f:
                    full_results = pickle.load(f)
                # Replace the path with the actual data
                results_data_copy['full_results_data'] = full_results
                # Keep the path for reference but mark it as embedded
                results_data_copy['full_results_embedded'] = True
            except Exception as e:
                print(f"Warning: Could not load results from {full_results_path}: {e}")
    
    # Also embed env_3d data if it exists
    if results_data_copy and 'env_3d_path' in results_data_copy:
        env_3d_path = results_data_copy['env_3d_path']
        if os.path.exists(env_3d_path):
            try:
                with open(env_3d_path, 'rb') as f:
                    env_data = pickle.load(f)
                results_data_copy['env_3d_data'] = env_data
                results_data_copy['env_3d_embedded'] = True
            except Exception as e:
                print(f"Warning: Could not load env_3d from {env_3d_path}: {e}")
    
    return {
        'session_data': session_data_copy,
        'results_data': results_data_copy,
        'comparison_data': comparison_data_copy,
        'filter_data': filter_data,
        'version': '1.0',
        'timestamp': datetime.now().isoformat()
    }

def save_state_to_file(state, file_object):
    """
    Saves the application state to a file-like object using pickle.
    """
    pickle.dump(state, file_object)

def load_state_from_file(file_object):
    """
    Loads the application state from a file-like object.
    Restores embedded results data to temporary files if needed.
    
    Args:
        file_object: File-like object containing pickled state
    
    Returns:
        Dictionary with session_data, results_data, comparison_data keys
    """
    import uuid
    
    state = pickle.load(file_object)
    results_data = state.get('results_data', {})
    
    # If results were embedded, restore them to temporary files
    if results_data and results_data.get('full_results_embedded'):
        full_results = results_data.get('full_results_data')
        if full_results:
            # Create temp_results directory if it doesn't exist
            temp_dir = "temp_results"
            os.makedirs(temp_dir, exist_ok=True)
            
            # Generate a new unique filename
            session_id = str(uuid.uuid4())
            new_path = os.path.join(temp_dir, f"{session_id}.pkl")
            
            # Save the results to the new temporary file
            with open(new_path, 'wb') as f:
                pickle.dump(full_results, f)
            
            # Update the results_data with the new path
            results_data['full_results_path'] = new_path
            # Remove the embedded data to save memory
            del results_data['full_results_data']
            del results_data['full_results_embedded']
    
    # If env_3d data was embedded, restore it to a temporary file
    if results_data and results_data.get('env_3d_embedded'):
        env_data = results_data.get('env_3d_data')
        if env_data:
            temp_dir = "temp_results"
            os.makedirs(temp_dir, exist_ok=True)
            
            # Use same session_id as above if it exists, otherwise generate new
            if 'full_results_path' in results_data:
                session_id = os.path.basename(results_data['full_results_path']).replace('.pkl', '')
            else:
                session_id = str(uuid.uuid4())
            
            env_path = os.path.join(temp_dir, f"{session_id}_env.pkl")
            
            with open(env_path, 'wb') as f:
                pickle.dump(env_data, f)
            
            results_data['env_3d_path'] = env_path
            del results_data['env_3d_data']
            del results_data['env_3d_embedded']
    
    return state

def reset_application_state():
    """
    Returns a dictionary with empty states to reset the application.
    """
    return {
        'session_data': {},
        'results_data': {},
        'comparison_data': []
    }