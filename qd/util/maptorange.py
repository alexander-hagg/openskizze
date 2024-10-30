"""Map values in range from 0 to 1, and back."""
import numpy as np
import numpy.typing as npt


def do(x: npt.NDArray, min_expected: float, max_expected: float) -> npt.NDArray:
    """
    Map the values of x into range [0,1].

    Args:
        x (npt.NDArray): values in the original range.

        min_expected (float): Minimum value expected in the original range.

        max_expected (float): Maximum value expected in the original range.

    Returns:
        npt.NDArray: values mapped in the range [0,1].
    """
    x = np.asarray(x)
    x = (x - min_expected) / (max_expected - min_expected)
    return x


def undo(x: npt.NDArray, min_expected: float, max_expected: float) -> npt.NDArray:
    """
    Map the value of x from range [0,1] into his config range.

    Args:
        x (npt.NDArray): Values in range [0,1].

        min_expected (float): Minimum value expected in the original range.

        max_expected (float): Maximum value expected in the original range.

    Returns:
        npt.NDArray: values mapped back to the original range.
    """
    x = np.asarray(x)
    x = x * (max_expected - min_expected) + min_expected
    return x
