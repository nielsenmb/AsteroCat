"""
compile_yu2018.py
-----------------
Yu et al. (2018) — 16,094 Kepler red giants with numax, Dnu, masses and radii.
CDS: J/ApJS/236/42  https://cdsarc.cds.unistra.fr/viz-bin/cat/J/ApJS/236/42

Download the following files from CDS and place in sources/yu2018/:
    table1.dat   -- asteroseismic parameters (numax, Dnu, etc.)
    table2.dat   -- stellar parameters (Teff, logg, etc.)
    ReadMe

Outputs:
    sources/yu2018.json
"""

import json
import numpy as np
from pathlib import Path
from astropy.io import ascii
from astropy.table import join
from asterocat import utils

DATA_DIR = Path("sources/yu2018")
TABLE1   = DATA_DIR / "table1.dat"
TABLE2   = DATA_DIR / "table2.dat"
README   = DATA_DIR / "ReadMe.txt"
OUTPUT   = Path("sources/yu2018.json")
ADS_URL     = "https://ui.adsabs.harvard.edu/abs/2018ApJS..236...42Y"
TEFF_ADS_URL = None

def main():
    for f in (TABLE1, TABLE2, README):
        if not f.exists():
            raise FileNotFoundError(
                f"Missing: {f}\n"
                f"Download from https://cdsarc.cds.unistra.fr/viz-bin/cat/J/ApJS/236/42"
                f" and place files in {DATA_DIR}/"
            )

    print("Loading Yu+2018...")
    t1 = ascii.read(TABLE1, readme=README, format="cds")
    t2 = ascii.read(TABLE2, readme=README, format="cds")
    print(f"  table1: {len(t1)} rows, table2: {len(t2)} rows")
    print(f"  table1 columns: {t1.colnames}")
    print(f"  table2 columns: {t2.colnames}")

    merged = join(t1, t2, keys="KIC", join_type="inner")

    def to_float(col):
        if hasattr(col, "mask"):
            return np.where(col.mask, np.nan, col.data.astype(float))
        return np.array(col, dtype=float)

    numax   = to_float(merged["numax"])
    e_numax = to_float(merged["e_numax"])

    
    teff   = to_float(merged["Teff"])
    e_teff = to_float(merged["e_Teff"])

    kic   = np.array(merged["KIC"], dtype=int)
    
    valid = np.isfinite(numax) & (numax > 0) & (teff > 0)
    print(f"  {valid.sum()} / {len(merged)} rows with finite non-zero numax")

    targets = []
    for i in np.where(valid)[0]:
        targets.append({
            "catalog_id": int(kic[i]),
            "numax":      utils.float_for_json(numax[i]), 
            "e_numax":    utils.float_for_json(e_numax[i]),  
            "teff":       utils.float_for_json(teff[i]),  
            "e_teff":     utils.float_for_json(e_teff[i]),
        })

    OUTPUT.parent.mkdir(exist_ok=True)
    with open(OUTPUT, "w") as f:
        json.dump({"source": "Yu+2018", 
                   "catalog": "KIC",
                   "instrument": "Kepler",
                   "ads_url": ADS_URL, 
                   "teff_ads_url": TEFF_ADS_URL, 
                   "targets": targets}, f, indent=2)
    print(f"Written {OUTPUT}  ({len(targets)} entries)")


if __name__ == "__main__":
    main()
