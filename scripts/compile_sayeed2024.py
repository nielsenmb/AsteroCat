"""
compile_sayeed2024.py
---------------------
Sayeed et al. (2024) — KIC targets with numax and Teff from MRT tables.

Required files:
    sayeed_seismic_table.txt
    sayeed_stellar_pars_table.txt

Outputs:
    sources/sayeed2024.json
"""

import json
import numpy as np
from pathlib import Path
from astropy.io import ascii
from astropy.table import join
from asterocat import utils

SEISMIC = Path("sources/sayeed2024/sayeed_seismic_table.txt")
STELLAR = Path("sources/sayeed2024/sayeed_stellar_pars_table.txt")
OUTPUT  = Path("sources/sayeed2024.json")


def main():
    print("Loading Sayeed+2024...")
    seismic = ascii.read(SEISMIC, format="mrt")
    stellar = ascii.read(STELLAR, format="mrt")
    merged  = join(seismic, stellar, keys="KIC", join_type="inner")

    numax = np.ma.filled(merged["numax"].data, np.nan).astype(float)
    teff  = np.ma.filled(merged["Teff"].data,  np.nan).astype(float)
    kic   = np.array(merged["KIC"], dtype=int)

    # uncertainties — use column names from the MRT if available
    e_numax = np.ma.filled(merged["e_numax"].data, np.nan).astype(float) \
              if "e_numax" in merged.colnames else np.full(len(merged), np.nan)
    e_teff  = np.ma.filled(merged["e_Teff"].data,  np.nan).astype(float) \
              if "e_Teff"  in merged.colnames else np.full(len(merged), np.nan)

    valid = np.isfinite(numax) & (numax > 0) & (teff > 0)
    print(f"  {valid.sum()} / {len(merged)} rows with finite non-zero numax")

    targets = []
    for i in np.where(valid)[0]:
        targets.append({
            "mission_id": int(kic[i]),
            "numax":      utils.float_for_json(numax[i]), 
            "e_numax":    utils.float_for_json(e_numax[i]),  
            "teff":       utils.float_for_json(teff[i]),  
            "e_teff":     utils.float_for_json(e_teff[i]),
        })

    OUTPUT.parent.mkdir(exist_ok=True)
    with open(OUTPUT, "w") as f:
        json.dump({"source": "Sayeed+2024", "mission": "KIC", "targets": targets}, f, indent=2)
    print(f"Written {OUTPUT}  ({len(targets)} entries)")


if __name__ == "__main__":
    main()
