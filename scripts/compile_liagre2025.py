"""
compile_liagre2025.py
---------------------
Liagre et al. (2025) — TIC targets from a CDS-format catalog.

Required files:
    liagre/catalog.dat
    liagre/ReadMe.txt

Outputs:
    sources/liagre2025.json
"""

import json
import numpy as np
from pathlib import Path
from astropy.io import ascii
from asterocat import utils

CATALOG = Path("sources/liagre2025/catalog.dat")
README  = Path("sources/liagre2025/ReadMe.txt")
OUTPUT  = Path("sources/liagre2025.json")
ADS_URL     = "https://ui.adsabs.harvard.edu/abs/2025A%26A...702A.144L"
TEFF_ADS_URL = None

def main():
    print("Loading Liagre+2025...")
    table = ascii.read(CATALOG, readme=README, format="cds")

    numax = np.array(table["numax"], dtype=float)
    teff  = np.array(table["Teff"],  dtype=float)
    tic   = np.array(table["TIC"],   dtype=int)

    e_numax = np.array(table["e_numax"], dtype=float) if "e_numax" in table.colnames else np.full(len(table), np.nan)
    e_teff  = np.array(table["e_Teff"],  dtype=float) if "e_Teff"  in table.colnames else np.full(len(table), np.nan)

    valid = np.isfinite(numax) & (numax > 0) & (teff > 0)
    print(f"  {valid.sum()} / {len(table)} rows with finite non-zero numax")

    targets = []
    for i in np.where(valid)[0]:
        targets.append({
            "catalog_id": int(tic[i]),
            "numax":      utils.float_for_json(numax[i]), 
            "e_numax":    utils.float_for_json(e_numax[i]),  
            "teff":       utils.float_for_json(teff[i]),  
            "e_teff":     utils.float_for_json(e_teff[i]),
        })

    OUTPUT.parent.mkdir(exist_ok=True)
    with open(OUTPUT, "w") as f:
        json.dump({"source": "Liagre+2025", 
                   "catalog": "TIC",
                   "instrument": "TESS",
                   "ads_url": ADS_URL, 
                   "teff_ads_url": TEFF_ADS_URL, 
                   "targets": targets}, f, indent=2)
    print(f"Written {OUTPUT}  ({len(targets)} entries)")


if __name__ == "__main__":
    main()
