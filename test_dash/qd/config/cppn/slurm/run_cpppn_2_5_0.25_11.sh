#!/bin/bash

#SBATCH --output=slurm/slurm.%j.out    # STDOUT
#SBATCH --error=slurm/slurm.%j.err     # STDERR
#SBATCH --partition=hpc         # partition (queue)
#SBATCH --ntasks=110             # use 110 task
#SBATCH --mem=30G               # memory per node in MB (different units with suffix K|M|G|T)
#SBATCH --time=1-23:00:00         # total runtime of job allocation ((format D-HH:MM:SS; first parts optional)

#SBATCH --mail-type=BEGIN        # send mail when job begins
#SBATCH --mail-type=END          # send mail when job ends
#SBATCH --mail-type=FAIL         # send mail if job fails
#SBATCH --mail-user=ludovico.scarton@smail.inf.h-brs.de

source ~/mambaforge/etc/profile.d/conda.sh
conda activate opt

# start program
python3 -m src.optimization --config_file="./data/config/cppn/2layer_5neurons/cppn_prob:0.25_sigma:11.yml" --root_folder="/scratch/stella/fulldafm/enc"
