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

SEISMIC = Path("sources/data/sayeed2024/sayeed_seismic_table.txt")
STELLAR = Path("sources/data/sayeed2024/sayeed_stellar_pars_table.txt")
ADS_URL     = "https://ui.adsabs.harvard.edu/abs/2025AJ....170..212S"
TEFF_ADS_URL = None
INSTRUMENT   = 'Kepler'
CATALOG      = 'KIC'
SOURCE = "Sayeed+2024"

output = Path(f"sources/json/{SOURCE.lower().replace('+','')}.json")

def main():
    print("Loading Sayeed+2024...")
    seismic = ascii.read(SEISMIC, format="mrt")
    stellar = ascii.read(STELLAR, format="mrt")
    merged  = join(seismic, stellar, keys="KIC", join_type="inner")

    numax = np.ma.filled(merged["numax"].data, np.nan).astype(float)
    dnu = np.ma.filled(merged["Dnu"].data, np.nan).astype(float)
    teff  = np.ma.filled(merged["Teff"].data,  np.nan).astype(float)
    kic   = np.array(merged["KIC"], dtype=int)

    # uncertainties — use column names from the MRT if available
    e_numax = np.ma.filled(merged["e_numax"].data, np.nan).astype(float) \
              if "e_numax" in merged.colnames else np.full(len(merged), np.nan)
    e_dnu = np.ma.filled(merged["e_Dnu"].data, np.nan).astype(float) \
              if "e_Dnu" in merged.colnames else np.full(len(merged), np.nan)
    e_teff  = np.ma.filled(merged["e_Teff"].data,  np.nan).astype(float) \
              if "e_Teff"  in merged.colnames else np.full(len(merged), np.nan)

    valid = (((np.isfinite(numax) & (numax > 0)) | (np.isfinite(dnu) & (dnu > 0))) & (np.isnan(teff) | (teff > 0)))
    print(f"  {valid.sum()} / {len(merged)} rows with finite non-zero numax or dnu")

    targets = []
    for i in np.where(valid)[0]:
        targets.append({
            "catalog_id": int(kic[i]),
            "numax":      utils.float_for_json(numax[i]), 
            "e_numax":    utils.float_for_json(e_numax[i]), 
            "dnu":        utils.float_for_json(dnu[i]), 
            "e_dnu":      utils.float_for_json(e_dnu[i]),  
            "teff":       utils.float_for_json(teff[i]),  
            "e_teff":     utils.float_for_json(e_teff[i]),
        })

    output.parent.mkdir(exist_ok=True)
    with open(output, "w") as f:
        json.dump({"source": SOURCE, 
                   "catalog": CATALOG,
                   "instrument": INSTRUMENT,
                   "ads_url": ADS_URL, 
                   "teff_ads_url": TEFF_ADS_URL, 
                   "targets": targets}, f, indent=2)
    print(f"Written {output}  ({len(targets)} entries)")


if __name__ == "__main__":
    main()
