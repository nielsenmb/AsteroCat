"""
asterocat/utils.py
------------------
Shared utilities for AsteroCat compile scripts.
"""

import numpy as np


def float_for_json(val) -> float | None:
    """Convert a scalar to float, or None if non-finite or None."""
    if val is None:
        return None
    try:
        f = float(val)
        return f if np.isfinite(f) else None
    except (TypeError, ValueError):
        return None


def col_to_array(col) -> np.ndarray:
    """
    Convert an astropy Column or MaskedColumn to a float numpy array,
    replacing masked/non-finite values with NaN.

    Handles the two cases that arise with CDS-format tables:
      - MaskedColumn (has a .mask attribute) → fills masked entries with NaN
      - plain Column (no .mask) → straight cast to float
    """
    if hasattr(col, "mask"):
        return np.where(col.mask, np.nan, col.data.astype(float))
    return np.array(col, dtype=float)


def make_targets(
    catalog_ids,
    numax,
    e_numax,
    teff,
    e_teff,
    valid_mask=None,
) -> list[dict]:
    """
    Build the targets list for a compiled JSON file.

    Parameters
    ----------
    catalog_ids : array-like
        Per-target identifier (integer or string).
    numax, e_numax, teff, e_teff : array-like
        Float arrays; use NaN for missing values.
    valid_mask : boolean array, optional
        If None, defaults to np.isfinite(numax) & (numax > 0).

    Returns
    -------
    list of dicts, each with keys: catalog_id, numax, e_numax, teff, e_teff.
    """
    numax   = np.asarray(numax,   dtype=float)
    e_numax = np.asarray(e_numax, dtype=float)
    teff    = np.asarray(teff,    dtype=float)
    e_teff  = np.asarray(e_teff,  dtype=float)

    if valid_mask is None:
        valid_mask = np.isfinite(numax) & (numax > 0)

    targets = []
    for i in np.where(valid_mask)[0]:
        targets.append({
            "catalog_id": int(catalog_ids[i]) if np.issubdtype(
                              type(catalog_ids[i]), np.integer) else str(catalog_ids[i]),
            "numax":   float_for_json(numax[i]),
            "e_numax": float_for_json(e_numax[i]),
            "teff":    float_for_json(teff[i]),
            "e_teff":  float_for_json(e_teff[i]),
        })
    return targets
