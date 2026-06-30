import numpy as np

def float_for_json(val):
    return float(val) if np.isfinite(val) else None