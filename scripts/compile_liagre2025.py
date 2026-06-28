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

CATALOG = Path("sources/liagre2025/catalog.dat")
README  = Path("sources/liagre2025/ReadMe.txt")
OUTPUT  = Path("sources/liagre2025.json")


def main():
    print("Loading Liagre+2025...")
    table = ascii.read(CATALOG, readme=README, format="cds")

    numax = np.array(table["numax"], dtype=float)
    teff  = np.array(table["Teff"],  dtype=float)
    tic   = np.array(table["TIC"],   dtype=int)

    e_numax = np.array(table["e_numax"], dtype=float) if "e_numax" in table.colnames else np.full(len(table), np.nan)
    e_teff  = np.array(table["e_Teff"],  dtype=float) if "e_Teff"  in table.colnames else np.full(len(table), np.nan)

    valid = np.isfinite(numax) & np.isfinite(teff)
    print(f"  {valid.sum()} / {len(table)} rows with finite numax and Teff")

    targets = []
    for i in np.where(valid)[0]:
        targets.append({
            "mission_id": int(tic[i]),
            "numax":      float(numax[i]),
            "e_numax":    float(e_numax[i]) if np.isfinite(e_numax[i]) else None,
            "teff":       float(teff[i]),
            "e_teff":     float(e_teff[i])  if np.isfinite(e_teff[i])  else None,
        })

    OUTPUT.parent.mkdir(exist_ok=True)
    with open(OUTPUT, "w") as f:
        json.dump({"source": "Liagre+2025", "mission": "TIC", "targets": targets}, f, indent=2)
    print(f"Written {OUTPUT}  ({len(targets)} entries)")


if __name__ == "__main__":
    main()
