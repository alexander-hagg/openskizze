# backend/optimizer.py
import numpy as np
from ribs.archives import GridArchive
from ribs.emitters import GaussianEmitter
from ribs.schedulers import Scheduler
import multiprocessing
import psutil
from backend.evaluation import eval_batch
import logging

logger = logging.getLogger(__name__)

def run_qd_optimization(encoding_obj, env_config: dict, qd_config: dict, x0_adaptive=None, progress_callback=None):
    solution_dim = encoding_obj.get_dimension()
    print(f"[QD-SETUP] Archive Configuration:")
    print(f"  Solution Dimension: {solution_dim} (FIXED - always 60)")
    print(f"  Features: {len(env_config['labels'])}")
    print(f"  Niches per Feature: {qd_config['num_niches']}")
    print(f"  Total Archive Size: {qd_config['num_niches'] ** len(env_config['labels'])}")
    
    archive = GridArchive(
        solution_dim=solution_dim,
        dims=[qd_config['num_niches']] * len(env_config['labels']),
        ranges=env_config['feat_ranges'],
        learning_rate=qd_config['learning_rate'],
        threshold_min=0.0
    )
    
    bounds = np.array([[-5.0, 5.0]] * solution_dim)
    
    # Use adaptive x0 if provided, otherwise zeros
    x0 = x0_adaptive if x0_adaptive is not None else np.zeros(solution_dim)
    print(f"  Initial genome: {'Adaptive (biased for parcel)' if x0_adaptive is not None else 'Zeros'}")
    
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
    live_update_interval = qd_config.get('live_update_interval', 100)  # Default to every 50 generations
    
    # Check if using surrogate model
    use_surrogate = env_config.get('use_surrogate', False)
    surrogate_wrapper = env_config.get('surrogate_wrapper', None)
    
    if use_surrogate and surrogate_wrapper is not None:
        logger.info(f"Using SURROGATE evaluation: {surrogate_wrapper.model_type}")
    else:
        logger.info("Using ORIGINAL physics-based evaluation")
    
    for gen in range(1, qd_config['num_generations'] + 1):
        try:
            genomes = scheduler.ask()
            
            # Branch: Surrogate (GPU batch) vs Original (multiprocess)
            if use_surrogate and surrogate_wrapper is not None:
                results = surrogate_wrapper.evaluate_batch(genomes, encoding_obj, env_config)
            else:
                results = eval_batch(genomes, encoding_obj, env_config, pool)
            
            objectives = results[:, 0]
            features = results[:, 1:len(env_config['labels']) + 1]            
            scheduler.tell(objectives, features)
            
            # Print stats at regular intervals (for console output)
            if gen % qd_config['output_inv_frequency'] == 0:
                stats = archive.stats
                print(f"Gen {gen}/{qd_config['num_generations']} | QD Score: {stats.qd_score:.2f} | Coverage: {stats.coverage * 100:.2f}% | Elites: {stats.num_elites}")
            
            # Call progress callback with archive at user-defined generation intervals
            if progress_callback:
                if gen % live_update_interval == 0 or gen == qd_config['num_generations']:
                    # Pass the archive object for live updates
                    progress_callback(100*gen/qd_config["num_generations"], f'Generation {gen} von {qd_config["num_generations"]}', archive)
                elif qd_config['output_inv_frequency'] > qd_config['num_generations']:
                    # Just update progress without archive
                    progress_callback(100*gen/qd_config["num_generations"], f'Generation {gen} von {qd_config["num_generations"]}', None)
        
        except Exception as e:
            print(f"!!!!!! ERROR during optimization loop at generation {gen} !!!!!!")
            print(f"Error: {e}")
            if isinstance(e, MemoryError):
                print("!!!!!! MEMORY ERROR DETECTED. This is likely due to an unstable emitter state. !!!!!!")
            pool.close()
            pool.join()
            raise e
            
    pool.close()
    pool.join()
    
    # Log surrogate performance stats if used
    if use_surrogate and surrogate_wrapper is not None:
        stats = surrogate_wrapper.get_performance_stats()
        logger.info(f"Surrogate Performance Summary:")
        logger.info(f"  Total evaluations: {stats['total_evaluations']}")
        logger.info(f"  Total time: {stats['total_time_s']:.2f}s")
        logger.info(f"  Avg per evaluation: {stats['avg_ms_per_eval']:.2f}ms")
        logger.info(f"  Throughput: {stats['evals_per_second']:.1f} evals/sec")
    
    print("Finished QD Optimization.")
    return archive