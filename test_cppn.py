import sys
sys.path.insert(0, "qd/domain/nsg_cppn")
import cppn
import numpy as np
import matplotlib.pyplot as plt

network = cppn.CPPN(input_dim=2, hidden_layers=[5,5], output_dim=1)
GRID = np.ones((25, 25))

raw_sample = network.sample(GRID)
plt.imshow(raw_sample)
plt.show()
