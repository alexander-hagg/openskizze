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
        # --- THE PERFORMANCE OPTIMIZATION IS HERE ---

        # 1. Reshape the flat genome into a matrix where each row is a building's genes.
        #    Also convert all gene values from a normal to a uniform distribution at once.
        genes = norm2unif(genome).reshape(self.config['max_num_buildings'], -1)
        
        # 2. Vectorized Calculation: Calculate properties for ALL buildings simultaneously.
        #    Instead of looping, we operate on entire columns (e.g., genes[:, 0] is the
        #    width gene for all buildings). This is executed by NumPy's fast C code.
        
        # Check which buildings are active using the 6th gene.
        is_active = genes[:, 5] > 0.0
        if not np.any(is_active):
            return np.zeros_like(buildable_mask)

        # Filter to only active buildings before calculating properties
        active_genes = genes[is_active]

        w = (active_genes[:, 0] * (self.config['xy_length'] / 2)).astype(int)
        l = (active_genes[:, 1] * (self.config['xy_length'] / 2)).astype(int)
        h = (active_genes[:, 2] * self.config['z_length']).astype(int) + 1
        x_c = (active_genes[:, 3] * self.config['xy_length']).astype(int)
        y_c = (active_genes[:, 4] * self.config['xy_length']).astype(int)
        
        # Calculate start/end coordinates for all buildings, clipping to bounds
        x_start = np.clip(x_c - w // 2, 0, self.config['xy_length'])
        x_end = np.clip(x_c + w // 2, 0, self.config['xy_length'])
        y_start = np.clip(y_c - l // 2, 0, self.config['xy_length'])
        y_end = np.clip(y_c + l // 2, 0, self.config['xy_length'])
        
        # 3. Efficient Drawing: Now that all calculations are done, create the heightmap.
        #    This loop is now much faster because it only performs simple assignments.
        #    Building overlaps are handled correctly (last building drawn wins).
        heightmap = np.zeros((self.config['xy_length'], self.config['xy_length']))
        for i in range(len(active_genes)):
            heightmap[y_start[i]:y_end[i], x_start[i]:x_end[i]] = h[i]
        
        # 4. Final Masking: This is a fast, element-wise operation.
        masked_heightmap = heightmap * buildable_mask
        
        if masked_heightmap.shape != (self.config['xy_length'], self.config['xy_length']):
            print(f"  [DEBUG-ERROR] Heightmap shape is {masked_heightmap.shape}, expected {(self.config['xy_length'], self.config['xy_length'])}")
        
        return masked_heightmap