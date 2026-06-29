"""
compile_hon2021.py
------------------
Hon et al. (2021) — ~158,000 oscillating red giants from the TESS MIT
Quick-Look Pipeline (QLP), Sectors 1-26.
CDS: J/ApJ/919/131  https://cdsarc.cds.unistra.fr/viz-bin/cat/J/ApJ/919/131

Download the following files from CDS and place in sources/hon2021/:
    table1.dat
    ReadMe

Outputs:
    sources/hon2021.json
"""

import json
import numpy as np
from pathlib import Path
from astropy.io import ascii

DATA_DIR = Path("sources/hon2021")
TABLE1   = DATA_DIR / "table1.dat"
README   = DATA_DIR / "ReadMe.txt"
OUTPUT   = Path("sources/hon2021.json")


def main():
    for f in (TABLE1, README):
        if not f.exists():
            raise FileNotFoundError(
                f"Missing: {f}\n"
                f"Download from https://cdsarc.cds.unistra.fr/viz-bin/cat/J/ApJ/919/131"
                f" and place files in {DATA_DIR}/"
            )

    print("Loading Hon+2021...")
    table = ascii.read(TABLE1, readme=README, format="cds")
    print(f"  {len(table)} rows, columns: {table.colnames}")

    tic_col   = next(c for c in table.colnames if c.lower() == "tic")
    numax_col = next(c for c in table.colnames if "numax" in c.lower() and not c.startswith("e_"))
    teff_col  = next(c for c in table.colnames if c.lower() == "teff")
    e_numax_col = next((c for c in table.colnames if c.lower() in ("e_numax", "numax_err")), None)
    e_teff_col  = next((c for c in table.colnames if c.lower() in ("e_teff",  "teff_err")),  None)

    def to_float(col):
        if hasattr(col, 'mask'):
            return np.where(col.mask, np.nan, col.data.astype(float))
        return np.array(col, dtype=float)

    tic     = np.array(table[tic_col], dtype=int)
    numax   = to_float(table[numax_col])
    e_numax = to_float(table[e_numax_col]) if e_numax_col else np.full(len(table), np.nan)
    teff    = to_float(table[teff_col])
    e_teff  = to_float(table[e_teff_col])  if e_teff_col  else np.full(len(table), np.nan)

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
        json.dump({"source": "Hon+2021", "mission": "TIC", "targets": targets}, f, indent=2)
    print(f"Written {OUTPUT}  ({len(targets)} entries)")


if __name__ == "__main__":
    main()
