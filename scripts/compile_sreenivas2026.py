"""
compile_sreenivas2026.py
------------------------
Sreenivas et al. (2026) — TIC targets fetched directly from CDS.

No local files required; data is streamed from:
    https://cdsarc.cds.unistra.fr/ftp/J/MNRAS/548/G671/

Outputs:
    sources/sreenivas2026.json
"""

import json
import numpy as np
from pathlib import Path
from astropy.io import ascii
from asterocat import utils

TABLE_URL  = "https://cdsarc.cds.unistra.fr/ftp/J/MNRAS/548/G671/table1.dat"
README_URL = "https://cdsarc.cds.unistra.fr/ftp/J/MNRAS/548/G671/ReadMe"
OUTPUT     = Path("sources/sreenivas2026.json")


def main():
    print("Loading Sreenivas+2026 from CDS...")
    table = ascii.read(TABLE_URL, readme=README_URL)

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
            "mission_id": int(tic[i]),
            "numax":      utils.float_for_json(numax[i]), 
            "e_numax":    utils.float_for_json(e_numax[i]),  
            "teff":       utils.float_for_json(teff[i]),  
            "e_teff":     utils.float_for_json(e_teff[i]),
        })

    OUTPUT.parent.mkdir(exist_ok=True)
    with open(OUTPUT, "w") as f:
        json.dump({"source": "Sreenivas+2026", "mission": "TIC", "targets": targets}, f, indent=2)
    print(f"Written {OUTPUT}  ({len(targets)} entries)")


if __name__ == "__main__":
    main()
