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

TABLE        = "https://cdsarc.cds.unistra.fr/ftp/J/MNRAS/548/G671/table1.dat"
README       = "https://cdsarc.cds.unistra.fr/ftp/J/MNRAS/548/G671/ReadMe"
ADS_URL      = "https://ui.adsabs.harvard.edu/abs/2026MNRAS.548ag671S"
TEFF_ADS_URL = None
INSTRUMENT   = 'TESS'
CATALOG      = 'TIC'
SOURCE       = 'Sreenivas+2026'

output       = Path(f"sources/json/{SOURCE.lower().replace('+','')}.json")

def main():
    print("Loading Sreenivas+2026 from CDS...")
    table = ascii.read(TABLE, readme=README)

    numax = np.array(table["numax"], dtype=float)
    dnu = np.array(table["deltanu"], dtype=float)
    teff  = np.array(table["Teff"],  dtype=float)
    tic   = np.array(table["TIC"],   dtype=int)

    e_numax = np.array(table["e_numax"], dtype=float) if "e_numax" in table.colnames else np.full(len(table), np.nan)
    e_dnu = np.array(table["e_deltanu"], dtype=float) if "e_deltanu" in table.colnames else np.full(len(table), np.nan)
    e_teff  = np.array(table["e_Teff"],  dtype=float) if "e_Teff"  in table.colnames else np.full(len(table), np.nan)

    valid = (((np.isfinite(numax) & (numax > 0)) | (np.isfinite(dnu) & (dnu > 0))) & (np.isnan(teff) | (teff > 0)))
    print(f"  {valid.sum()} / {len(table)} rows with finite non-zero numax or dnu")

    targets = []
    for i in np.where(valid)[0]:
        targets.append({
            "catalog_id": int(tic[i]),
            "numax":      utils.float_for_json(numax[i]), 
            "e_numax":    utils.float_for_json(e_numax[i]), 
            "dnu":      utils.float_for_json(dnu[i]), 
            "e_dnu":    utils.float_for_json(e_dnu[i]),  
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
