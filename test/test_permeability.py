import numpy as np

def count_paths(matrix, ht):
    rows, cols = matrix.shape
    dp = np.zeros((rows, cols), dtype=object)  # Use object type to store Python int
    max_paths = rows ** (cols - 1)  # Each cell in the first column can connect to every cell in the last column

    # Initialize the DP table for the western cells
    dp[:, 0] = 1

    # Fill the DP table
    for j in range(1, cols):
        for i in range(rows):
            for k in range(rows):
                if abs(matrix[i, j] - matrix[k, j - 1]) <= ht:
                    dp[i, j] += dp[k, j - 1]

    # Calculate the total number of paths from western to eastern cells
    total_paths = sum(dp[:, -1])

    # Correct calculation of maximum potential paths
    max_paths = rows ** (cols - 1) * rows

    # Calculate the relative number of paths
    relative_paths = total_paths / max_paths

    return total_paths, max_paths, relative_paths

# Example usage
matrix = np.array([
    [0, 2, 0],
    [0, 0, 0],
    [0, 0, 0]
])
ht = 1

total_paths, max_paths, relative_paths = count_paths(matrix, ht)
print(f"Total possible paths: {total_paths}")
print(f"Maximum potential paths: {max_paths}")
print(f"Relative number of paths: {relative_paths}")

# Example usage
matrix = np.array([
    [0, 0, 0],
    [0, 0, 0],
    [0, 0, 0]
])
ht = 1

total_paths, max_paths, relative_paths = count_paths(matrix, ht)
print(f"Total possible paths: {total_paths}")
print(f"Maximum potential paths: {max_paths}")
print(f"Relative number of paths: {relative_paths}")

matrix = np.random.randint(0, 3, size=(100, 100))
ht = 1

total_paths, max_paths, relative_paths = count_paths(matrix, ht)
print(matrix)
print(f"Total possible paths: {total_paths}")
print(f"Maximum potential paths: {max_paths}")
print(f"Relative number of paths: {relative_paths}")