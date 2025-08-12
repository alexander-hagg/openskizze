# backend/optimizer.py
import numpy as np
from ribs.archives import GridArchive
from ribs.emitters import GaussianEmitter
from ribs.schedulers import Scheduler
import multiprocessing
import psutil
from backend.evaluation import eval_batch

def run_qd_optimization(encoding_obj, env_config: dict, qd_config: dict, progress_callback=None):
    solution_dim = encoding_obj.get_dimension()
    # --- DEBUG LOG ---
    print(f"[DEBUG] Starting QD setup. Solution dimension: {solution_dim}")
    
    archive = GridArchive(
        solution_dim=solution_dim,
        dims=[qd_config['num_niches']] * len(env_config['labels']),
        ranges=env_config['feat_ranges'],
        learning_rate=qd_config['learning_rate'],
        threshold_min=0.0,
        extra_fields={'heightmaps': ((encoding_obj.config['xy_length']**2,), np.float32)}
    )
    
    bounds = np.array([[-5.0, 5.0]] * solution_dim)
    x0 = np.zeros(solution_dim)
    
    emitters = [
        GaussianEmitter(
            archive, x0=x0, sigma=qd_config['sigma'],
            batch_size=qd_config['batch_size'], bounds=bounds
        ) for _ in range(qd_config['num_emitters'])
    ]
    
    scheduler = Scheduler(archive, emitters)
    nb_cpus = max(1, psutil.cpu_count(logical=True) - 2)
    pool = multiprocessing.Pool(processes=nb_cpus)
    
    print("Starting QD Optimization...")
    for gen in range(1, qd_config['num_generations'] + 1):
        try:
            genomes = scheduler.ask()

            # --- DEBUG LOG ---
            if gen == 1: print(f"[DEBUG] Gen 1: Asked for {len(genomes)} genomes. Shape of first genome: {genomes[0].shape}")

            results = eval_batch(genomes, encoding_obj, env_config, pool)
            
            objectives = results[:, 0]
            features = results[:, 1:len(env_config['labels']) + 1]
            
            # print all objective values for debugging
            # print(f"[DEBUG] Gen 1: Objective values: {objectives}")
            
            
            heightmaps = results[:, len(env_config['labels']) + 1:]
            
            # --- DEBUG LOG ---
            if gen == 1:
                print(f"[DEBUG] Gen 1: Results received. Objectives shape: {objectives.shape}, Features shape: {features.shape}, Heightmaps shape: {heightmaps.shape}")

            scheduler.tell(objectives, features, heightmaps=heightmaps)
            
            if gen % qd_config['output_inv_frequency'] == 0:
                stats = archive.stats
                print(f"Gen {gen}/{qd_config['num_generations']} | QD Score: {stats.qd_score:.2f} | Coverage: {stats.coverage * 100:.2f}% | Elites: {stats.num_elites}")
            
            if progress_callback: progress_callback(100*gen/qd_config["num_generations"], f'Es wird {qd_config["num_generations"]} Generationen optimiert.')
        
        except Exception as e:
            print(f"!!!!!! ERROR during optimization loop at generation {gen} !!!!!!")
            print(f"Error: {e}")
            # In case of memory error, this provides a clear message before crashing.
            if isinstance(e, MemoryError):
                print("!!!!!! MEMORY ERROR DETECTED. This is likely due to an unstable emitter state. !!!!!!")
            pool.close()
            pool.join()
            raise e # Re-raise the exception to stop the process
            
    pool.close()
    pool.join()
    print("Finished QD Optimization.")
    return archive