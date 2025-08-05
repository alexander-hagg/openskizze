# backend/encoding.py
import numpy as np
import numpy.typing as npt
from scipy.stats import norm, uniform

def norm2unif(x):
    p = norm.cdf(x, 0, 1)
    return uniform.ppf(p, 0, 1)

class ParametricEncoding:
    def __init__(self, config: dict):
        self.config = config

    def get_dimension(self) -> int:
        return self.config['max_num_buildings'] * 6

    def express(self, buildable_mask: npt.NDArray, genome: npt.NDArray) -> npt.NDArray:
        genome = norm2unif(genome)
        heightmap = np.zeros((self.config['xy_length'], self.config['xy_length']))
        
        for i in range(self.config['max_num_buildings']):
            genes = genome[i*6 : (i+1)*6]
            if genes[5] > 0.5:
                w = int(genes[0] * (self.config['xy_length'] / 2))
                l = int(genes[1] * (self.config['xy_length'] / 2))
                h = int(genes[2] * self.config['z_length']) + 1
                x_c = int(genes[3] * self.config['xy_length'])
                y_c = int(genes[4] * self.config['xy_length'])
                x_start, x_end = max(0, x_c - w // 2), min(self.config['xy_length'], x_c + w // 2)
                y_start, y_end = max(0, y_c - l // 2), min(self.config['xy_length'], y_c + l // 2)
                heightmap[y_start:y_end, x_start:x_end] = h
        
        masked_heightmap = heightmap * buildable_mask
        # --- DEBUG LOG ---
        if masked_heightmap.shape != (self.config['xy_length'], self.config['xy_length']):
            print(f"  [DEBUG-ERROR] Heightmap shape is {masked_heightmap.shape}, expected {(self.config['xy_length'], self.config['xy_length'])}")
        return masked_heightmap