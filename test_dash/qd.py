import numpy as np
from ribs.archives import GridArchive
from ribs.emitters import GaussianEmitter, IsoLineEmitter, EvolutionStrategyEmitter
from ribs.schedulers import Scheduler
from ribs.visualize import parallel_axes_plot

def quality_diversity_optimization():
    mu = 0.0                # Used for initialization, probably want to keep it at 0
    sigma = 2.0             # Used for initialization and mutation
    learning_rate = 0.001

    genome_config: Dict = yaml.safe_load(open(config_file))
    genome_config["methods"]["cppn"]["hidden_layers"] = cppn_config
    genome_config["substrate"] = set_substrate(genome_config)
    genome_config["algorithm_parameters"]["substrate_length"] = genome_config["substrate"].shape[0]
    genome_template = CPPNGenome(genome_config)
    solution_dim, _, _ = genome_template.get_dimension()

    # Define the search space and archive
    archive = GridArchive(
        solution_dim=2,
        dims=[100, 100],
        ranges=[(-1, 1), (-1, 1)],
    )

    # Define the emitter
    emitter = GaussianEmitter(
        archive,
        x0=np.zeros(2),
        sigma=0.1,
        batch_size=15,
    )

    # Define the optimizer
    optimizer = Optimizer(archive, [emitter])

    # Run the optimization
    for _ in range(100):
        solutions = optimizer.ask()
        objective_values = np.sum(solutions ** 2, axis=1)
        behavior_values = solutions
        optimizer.tell(objective_values, behavior_values)

    return archive