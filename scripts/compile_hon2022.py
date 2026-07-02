"""
compile_hon2022.py
------------------
Hon et al. (2022) — HD-TESS: 1709 bright (V~3-10) red giants in the TESS
Continuous Viewing Zones with numax, Dnu and evolutionary states.
CDS: J/AJ/164/135

Expected local files in sources/hon2022/:
    table1.dat   — numax, e_numax, HD, TIC
    table2.dat   — Teff, e_Teff, HD, TIC
    ReadMe.txt

Outputs:
    sources/hon2022.json

Notes:
    - TIC column in table2.dat is a string (right-justified, may have spaces)
      and needs stripping before casting to int.
    - Teff is NULL for ref=7 (no atmospheric parameters); those rows are dropped.
    - Mission is TIC; HD identifiers are stored for reference only.
"""

import json
import numpy as np
from pathlib import Path
from astropy.io import ascii
from astropy.table import join
from asterocat import utils

DATA_DIR   = Path("sources/hon2022")
TABLE1     = DATA_DIR / "table1.dat"
TABLE2     = DATA_DIR / "table2.dat"
README     = DATA_DIR / "ReadMe.txt"
OUTPUT     = Path("sources/hon2022.json")
ADS_URL     = "https://ui.adsabs.harvard.edu/abs/2022AJ....164..135H"
TEFF_ADS_URL = None

def main():
    print("Loading Hon+2022 (HD-TESS)...")
    t1 = ascii.read(TABLE1, readme=README, format="cds")
    t2 = ascii.read(TABLE2, readme=README, format="cds")
    print(f"  table1: {len(t1)} rows, table2: {len(t2)} rows")

    # TIC in table2 is a string column — strip and cast
    t1["TIC_int"] = np.array(t1["TIC"], dtype=int)
    t2["TIC_int"] = np.array([str(v).strip() for v in t2["TIC"]], dtype=int)

    merged = join(
        t1["TIC_int", "numax", "e_numax"],
        t2["TIC_int", "Teff",  "e_Teff"],
        keys="TIC_int", join_type="inner",
    )

    tic     = np.array(merged["TIC_int"], dtype=int)
    numax   = np.ma.filled(merged["numax"].data,   np.nan).astype(float)
    e_numax = np.ma.filled(merged["e_numax"].data, np.nan).astype(float)
    teff    = np.where(merged["Teff"].mask,   np.nan, merged["Teff"].data.astype(float))
    e_teff  = np.where(merged["e_Teff"].mask, np.nan, merged["e_Teff"].data.astype(float))
    

    valid = np.isfinite(numax) & (numax > 0) & (teff > 0)
    print(f"  {valid.sum()} / {len(merged)} rows with finite non-zero numax")

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
        json.dump({"source": "Hon+2022", 
                   "catalog": "TIC",
                   "instrument": "TESS",
                   "ads_url": ADS_URL, 
                   "teff_ads_url": TEFF_ADS_URL, 
                   "targets": targets}, f, indent=2)
    print(f"Written {OUTPUT}  ({len(targets)} entries)")


if __name__ == "__main__":
    main()
