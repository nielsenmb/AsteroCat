"""
compile_karim2025.py
--------------------
Karim et al. (2025) — TIC targets from a whitespace-delimited text file.

Required files:
    karim2025.txt

Expected columns (comment lines start with #):
    TIC  R  Teff  numax  Dnu  PE  SNR  Cadence

Outputs:
    sources/karim2025.json
"""

import json
import numpy as np
from pathlib import Path
from asterocat import utils

INPUT  = Path("sources/karim2025/karim2025.txt")
OUTPUT = Path("sources/karim2025.json")


def main():
    print("Loading Karim+2025...")
    data = np.genfromtxt(
        INPUT, comments="#", dtype=None, encoding="utf-8",
        names=["TIC", "R", "Teff", "numax", "Dnu", "PE", "SNR", "Cadence"],
    )

    tic   = data["TIC"].astype(int)
    numax = data["numax"].astype(float)
    teff  = data["Teff"].astype(float)

    valid = np.isfinite(numax) & (numax > 0) & (teff > 0)
    print(f"  {valid.sum()} / {len(data)} rows with finite non-zero numax")

    targets = []
    for i in np.where(valid)[0]:
        targets.append({
            "mission_id": int(tic[i]),
            "numax":      utils.float_for_json(numax[i]), 
            "e_numax":    None,
            "teff":       utils.float_for_json(teff[i]), 
            "e_teff":     None,
        })

    OUTPUT.parent.mkdir(exist_ok=True)
    with open(OUTPUT, "w") as f:
        json.dump({"source": "Karim+2025", "mission": "TIC", "targets": targets}, f, indent=2)
    print(f"Written {OUTPUT}  ({len(targets)} entries)")


if __name__ == "__main__":
    main()
