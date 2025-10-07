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
        """Genome dimension: ALWAYS 60 (10 buildings × 6 genes)"""
        return self.config['max_num_buildings'] * 6
    
    def update_config(self, new_config: dict):
        """Update xy_length for new parcel (buildings stay 10)"""
        self.config.update(new_config)
    
    def get_adaptive_initial_genome(self, buildable_mask: npt.NDArray) -> npt.NDArray:
        """
        Generate initial genome with reasonable building sizes for parcel.
        Helps optimization start with sensible solutions.
        
        Returns genome in NORMAL distribution space (not uniform).
        
        Args:
            buildable_mask: Boolean array of buildable cells
        
        Returns:
            np.ndarray: Initial genome (60 genes) in normal distribution space
        """
        grid_res = buildable_mask.shape[0]
        
        # For small grids, bias toward smaller buildings
        # For large grids, allow normal-sized buildings
        if grid_res < 20:
            size_bias = -0.5  # Smaller buildings for small parcels
        elif grid_res > 60:
            size_bias = 0.0   # Normal buildings for large parcels
        else:
            size_bias = -0.2  # Slightly smaller for medium parcels
        
        # Initialize genome: 10 buildings × 6 genes
        genome = np.random.randn(60)  # Standard normal distribution
        
        # Bias width/length genes toward smaller values for small parcels
        genome[0::6] += size_bias  # Width genes (0, 6, 12, 18, ...)
        genome[1::6] += size_bias  # Length genes (1, 7, 13, 19, ...)
        
        # Height genes stay neutral (genes 2, 8, 14, ...)
        # Position genes stay neutral (genes 3-4, 9-10, 15-16, ...)
        
        # Active genes: start with ~7 buildings active, 3 inactive
        # Lower variance = more likely to be near 0 = more inactive buildings
        genome[5::6] = np.random.randn(10) * 0.5  # Active/inactive genes
        
        return genome

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